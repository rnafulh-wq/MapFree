"""
Performance and memory tests for the pipeline.
Uses mock engines (no real COLMAP) to assert timing and memory bounds.
"""
import gc
import time
import weakref
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from mapfree.core.context import ProjectContext
from mapfree.core.event_bus import EventBus
from mapfree.core.pipeline import Pipeline
from mapfree.core.profiles import get_profile


def _make_dummy_jpeg(path: Path, width: int = 1024, height: int = 768) -> None:
    """Write a minimal valid JPEG file (numpy + PIL if available, else minimal blob)."""
    try:
        import numpy as np
        from PIL import Image
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        arr[:] = (70, 130, 180)
        img = Image.fromarray(arr)
        img.save(path, format="JPEG", quality=85)
        return
    except ImportError:
        pass
    # Fallback: minimal JFIF so suffix is .jpg and file is non-empty
    path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")


class MockSlowEngine:
    """Engine that sleeps 100ms per image (simulated) and writes minimal valid outputs."""

    def __init__(self, delay_per_image_sec: float = 0.1):
        self.delay_per_image = delay_per_image_sec

    def _image_count(self, ctx) -> int:
        from mapfree.core.config import IMAGE_EXTENSIONS
        p = Path(ctx.image_path)
        return sum(1 for f in p.iterdir() if f.is_file() and f.suffix in IMAGE_EXTENSIONS)

    def _write_minimal_sparse(self, ctx) -> None:
        sparse_0 = Path(ctx.sparse_path) / "0"
        sparse_0.mkdir(parents=True, exist_ok=True)
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            (sparse_0 / name).write_bytes(b"\x00\x01\x02\x03")

    def _write_minimal_dense(self, ctx) -> None:
        Path(ctx.dense_path).mkdir(parents=True, exist_ok=True)
        (Path(ctx.dense_path) / "fused.ply").write_bytes(b"ply\nformat ascii 1.0\nend_header\n")

    def feature_extraction(self, ctx):
        n = self._image_count(ctx)
        time.sleep(self.delay_per_image * n)

    def matching(self, ctx):
        pass

    def sparse(self, ctx):
        self._write_minimal_sparse(ctx)

    def dense(self, ctx, vram_watchdog=False):
        self._write_minimal_dense(ctx)


@pytest.fixture
def dummy_image_dir_50(tmp_path):
    """Create 50 dummy 1024x768 JPEG files."""
    for i in range(50):
        _make_dummy_jpeg(tmp_path / f"img_{i:04d}.jpg")
    return tmp_path


@pytest.fixture
def project_dir(tmp_path):
    """Fresh project directory."""
    proj = tmp_path / "project"
    proj.mkdir()
    return proj


def test_pipeline_50_images(dummy_image_dir_50, project_dir):
    """Pipeline with 50 images and MockSlowEngine (100ms per image) finishes in < 30s and memory delta < 200MB."""
    try:
        import psutil
        process = psutil.Process()
    except ImportError:
        pytest.skip("psutil required for memory assertion")
    baseline_rss = process.memory_info().rss

    profile = get_profile(1024)
    ctx = ProjectContext(project_dir, dummy_image_dir_50, profile)
    ctx.prepare()
    engine = MockSlowEngine(delay_per_image_sec=0.1)

    with patch("mapfree.core.config.get_geospatial_config", return_value={"enable": False}):
        pipeline = Pipeline(engine, ctx, chunk_size=100, force_profile="LOW")
        start = time.perf_counter()
        pipeline.run()
        elapsed = time.perf_counter() - start

    assert elapsed < 30.0, "Pipeline should finish in under 30 seconds"
    rss_after = process.memory_info().rss
    delta_mb = (rss_after - baseline_rss) / (1024 * 1024)
    assert delta_mb < 200, f"Memory delta should be < 200 MB, got {delta_mb:.1f} MB"


def test_pipeline_memory_no_leak(dummy_image_dir_50, tmp_path):
    """Run pipeline 3 times on different projects; memory after run 3 <= run 1 + 50MB."""
    try:
        import psutil
        process = psutil.Process()
    except ImportError:
        pytest.skip("psutil required for memory assertion")

    def run_once(project_dir):
        profile = get_profile(1024)
        ctx = ProjectContext(project_dir, dummy_image_dir_50, profile)
        ctx.prepare()
        engine = MockSlowEngine(delay_per_image_sec=0.01)
        with patch("mapfree.core.config.get_geospatial_config", return_value={"enable": False}):
            pipeline = Pipeline(engine, ctx, chunk_size=100, force_profile="LOW")
            pipeline.run()
        gc.collect()
        return process.memory_info().rss

    proj1 = tmp_path / "p1"
    proj2 = tmp_path / "p2"
    proj3 = tmp_path / "p3"
    proj1.mkdir()
    proj2.mkdir()
    proj3.mkdir()

    rss1 = run_once(proj1)
    rss2 = run_once(proj2)
    rss3 = run_once(proj3)

    delta_3_vs_1_mb = (rss3 - rss1) / (1024 * 1024)
    assert delta_3_vs_1_mb <= 50.0, (
        f"Memory after 3 runs should be at most run1 + 50 MB, got delta {delta_3_vs_1_mb:.1f} MB"
    )


def test_eventbus_no_leak():
    """Subscribe 1000 callbacks, unsubscribe all, emit 1000 events; EventBus retains no handlers."""
    bus = EventBus()
    topic = "test_topic"
    refs = []

    def make_cb():
        def cb(_, data=None):
            pass
        refs.append(weakref.ref(cb))
        return cb

    callbacks = [make_cb() for _ in range(1000)]
    for cb in callbacks:
        bus.subscribe(topic, cb)
    for cb in callbacks:
        bus.unsubscribe(topic, cb)
    del callbacks  # drop local refs so only EventBus could hold them

    for _ in range(1000):
        bus.emit(topic, None)

    # EventBus must not retain any handler for this topic
    with bus._lock:
        assert topic not in bus._handlers or len(bus._handlers[topic]) == 0, (
            "EventBus should not retain callbacks after unsubscribe"
        )
    gc.collect()
    # Most callbacks should be collectable (allow 1 edge case on some interpreters)
    alive = sum(1 for r in refs if r() is not None)
    assert alive <= 1, f"At most 1 callback may be retained by interpreter, got {alive}"


def test_concurrent_pipelines(dummy_image_dir_50, tmp_path):
    """Two pipelines run in parallel without deadlock or race."""
    results = [None, None]
    errors = [None, None]

    def run_pipeline(index: int):
        try:
            project_dir = tmp_path / f"proj_{index}"
            project_dir.mkdir(exist_ok=True)
            profile = get_profile(1024)
            ctx = ProjectContext(project_dir, dummy_image_dir_50, profile)
            ctx.prepare()
            engine = MockSlowEngine(delay_per_image_sec=0.02)
            with patch("mapfree.core.config.get_geospatial_config", return_value={"enable": False}):
                pipeline = Pipeline(engine, ctx, chunk_size=100, force_profile="LOW")
                pipeline.run()
            results[index] = "done"
        except Exception as e:
            errors[index] = e

    t1 = Thread(target=run_pipeline, args=(0,))
    t2 = Thread(target=run_pipeline, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    assert t1.is_alive() is False, "Thread 1 should complete"
    assert t2.is_alive() is False, "Thread 2 should complete"
    assert results[0] == "done", f"Pipeline 0 failed: {errors[0]}"
    assert results[1] == "done", f"Pipeline 1 failed: {errors[1]}"
