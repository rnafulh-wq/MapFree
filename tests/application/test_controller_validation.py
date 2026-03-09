"""Tests for MapFreeController path validation (ProjectValidationError)."""
import sys
from pathlib import Path

import pytest

from mapfree.application.controller import MapFreeController
from mapfree.core.exceptions import ProjectValidationError


def test_run_project_rejects_path_in_system_dir():
    """run_project raises ProjectValidationError when path is inside a forbidden system directory."""
    if sys.platform == "win32":
        import os
        path = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "drivers"
        if not path.exists():
            path = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32"
    else:
        path = Path("/etc") / "subdir"
    controller = MapFreeController()
    with pytest.raises(ProjectValidationError):
        controller.run_project(
            image_path=str(path),
            project_path=str(path),
        )


def test_run_project_accepts_valid_path(tmp_path):
    """run_project accepts any valid writable path (e.g. tmp_path, or E:\\output on Windows)."""
    img = tmp_path / "images"
    proj = tmp_path / "project"
    img.mkdir(parents=True, exist_ok=True)
    proj.mkdir(parents=True, exist_ok=True)
    (img / "a.jpg").write_bytes(b"\xff\xd8\xff")
    controller = MapFreeController()
    controller.run_project(image_path=str(img), project_path=str(proj))
    if controller.worker_thread is not None:
        controller.worker_thread.join(timeout=2)
