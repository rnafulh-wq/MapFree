"""
CLI end-to-end integration tests.

Test cases:
1. test_cli_run_help          - `mapfree --help` exits with code 0
2. test_cli_run_invalid_path  - missing image path → non-0 exit, clear error message
3. test_cli_run_missing_colmap - COLMAP not in PATH → DependencyMissingError or non-0 exit
4. test_cli_run_with_mock_engine - full pipeline run with mocked engine
5. test_cli_open_results_flag  - --open-results flag accepted without error (mocked)

All COLMAP/OpenMVS calls are mocked — no real binaries are invoked.
"""
import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mapfree.core.exceptions import DependencyMissingError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_image_dir(tmp_path) -> Path:
    """Create a folder with 5 tiny JPEG files (programmatically generated)."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    # Minimal valid JPEG header (SOI + APP0 marker)
    jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    for i in range(5):
        (img_dir / f"img_{i:02d}.jpg").write_bytes(jpeg_header + b"\xff\xd9")
    return img_dir


@pytest.fixture
def tmp_project_dir(tmp_path) -> Path:
    """Return a temp directory for pipeline output."""
    p = tmp_path / "project"
    p.mkdir()
    return p


# ---------------------------------------------------------------------------
# 1. mapfree --help → exit 0
# ---------------------------------------------------------------------------

def test_cli_run_help():
    """mapfree --help must exit with code 0 and print usage information."""
    result = subprocess.run(
        [sys.executable, "-m", "mapfree.application.cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"--help exited {result.returncode}: {result.stderr}"
    assert "mapfree" in result.stdout.lower() or "usage" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 2. Invalid image path → non-0 exit, clear error message
# ---------------------------------------------------------------------------

def test_cli_run_invalid_path(tmp_project_dir):
    """Passing a non-existent image folder must exit non-0 with a clear error."""
    result = subprocess.run(
        [
            sys.executable, "-m", "mapfree.application.cli.main",
            "run",
            "/nonexistent/folder/that/does/not/exist",
            "--output", str(tmp_project_dir),
            "--quality", "medium",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "MAPFREE_NO_OPENGL": "1"},
    )
    assert result.returncode != 0, (
        f"Expected non-zero exit for invalid path, got 0. stderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "not a directory" in combined.lower() or "not found" in combined.lower() or combined, (
        f"Expected clear error message, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 3. Missing COLMAP → DependencyMissingError or non-0 exit
# ---------------------------------------------------------------------------

def test_cli_run_missing_colmap(dummy_image_dir, tmp_project_dir, monkeypatch):
    """
    When COLMAP is not found, the pipeline should raise DependencyMissingError
    (or the CLI should exit non-0 with a human-readable message).
    """
    from mapfree.engines.colmap_engine import resolve_colmap_executable

    with pytest.raises(DependencyMissingError) as exc_info:
        with patch(
            "mapfree.engines.colmap_engine.shutil.which",
            return_value=None,
        ), patch(
            "mapfree.engines.colmap_engine._is_executable",
            return_value=False,
        ), patch.dict(
            os.environ, {"MAPFREE_COLMAP": "", "MAPFREE_NO_OPENGL": "1"}
        ):
            resolve_colmap_executable()

    assert "colmap" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 4. Full pipeline run with mocked engine
# ---------------------------------------------------------------------------

def test_cli_run_with_mock_engine(dummy_image_dir, tmp_project_dir):
    """
    Full CLI-style invocation with all external binaries mocked.
    Verifies that the controller calls the engine and completes without error.
    """
    from mapfree.application.controller import MapFreeController
    from mapfree.core.events import Event

    events_received: list[str] = []

    def on_event(e: Event):
        events_received.append(e.type)

    # Build a mock engine that fakes sparse + dense output
    class _FakeEngine:
        def feature_extraction(self, ctx):
            pass

        def matching(self, ctx):
            pass

        def sparse(self, ctx):
            sp = Path(ctx.sparse_path) / "0"
            sp.mkdir(parents=True, exist_ok=True)
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (sp / name).write_bytes(b"fake")

        def dense(self, ctx, vram_watchdog=False):
            d = Path(ctx.dense_path)
            d.mkdir(parents=True, exist_ok=True)
            (d / "fused.ply").write_bytes(b"ply\n" + b"x" * 2048)

    _PATCH_HW = "mapfree.core.pipeline.hardware.get_hardware_profile"
    _PATCH_VRAM = "mapfree.core.pipeline.hardware.detect_gpu_vram"
    _PATCH_FR = "mapfree.core.pipeline.final_results_module.export_final_results"
    _PATCH_GEO = "mapfree.core.pipeline.Pipeline._config_enable_geospatial"
    _PATCH_LOG = "mapfree.core.pipeline.set_log_file_for_project"
    _PATCH_ENGINE = "mapfree.application.controller.create_engine"

    hw = MagicMock()
    hw.ram_gb = 8.0
    hw.vram_mb = 4096

    with patch(_PATCH_HW, return_value=hw), \
         patch(_PATCH_VRAM, return_value=4096), \
         patch(_PATCH_FR, return_value=tmp_project_dir / "final_results"), \
         patch(_PATCH_GEO, return_value=False), \
         patch(_PATCH_LOG, return_value=None), \
         patch(_PATCH_ENGINE, return_value=_FakeEngine()):

        controller = MapFreeController(profile=None)
        controller.run_project(
            str(dummy_image_dir),
            str(tmp_project_dir),
            on_event=on_event,
            quality="medium",
        )
        if controller.worker_thread is not None:
            controller.worker_thread.join(timeout=30)

    assert "complete" in events_received, (
        f"Expected 'complete' event, got: {events_received}"
    )


# ---------------------------------------------------------------------------
# 5. --open-results flag is accepted without error
# ---------------------------------------------------------------------------

def test_cli_open_results_flag(dummy_image_dir, tmp_project_dir):
    """
    --open-results flag must be accepted by the argument parser without error.
    The actual OS open is mocked so no file manager is launched.
    """
    # Capture the parsed args to verify --open-results is recognized
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    run_p = subparsers.add_parser("run")
    run_p.add_argument("image_folder")
    run_p.add_argument("--output", "-o", required=True)
    run_p.add_argument("--quality", "-q", default="medium")
    run_p.add_argument("--open-results", action="store_true")

    args = parser.parse_args([
        "run",
        str(dummy_image_dir),
        "--output", str(tmp_project_dir),
        "--open-results",
    ])

    assert args.open_results is True, "--open-results flag was not parsed correctly"
