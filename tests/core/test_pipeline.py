"""
Pipeline unit and integration tests.

Test cases:
1. test_stage_ordering        - stages execute in correct order
2. test_pipeline_emits_started_event
3. test_pipeline_emits_completed_event
4. test_pipeline_stop         - stop() halts pipeline gracefully
5. test_resume_skips_completed_stages
6. test_engine_error_emits_event
7. test_pipeline_with_mock_engine - full run with MockEngine

All subprocess/binary calls are mocked; no real COLMAP/OpenMVS is invoked.
"""
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mapfree.core.event_bus import EventBus
from mapfree.core.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

class _MockEngine:
    """Minimal engine that records which methods were called in order."""

    def __init__(self, fail_on: str | None = None):
        self._call_order: list[str] = []
        self._fail_on = fail_on  # stage name that raises EngineError

    def feature_extraction(self, ctx):
        self._record("feature_extraction")

    def matching(self, ctx):
        self._record("matching")

    def sparse(self, ctx):
        self._record("sparse")
        # Simulate a valid sparse output so pipeline proceeds
        sp = Path(ctx.sparse_path) / "0"
        sp.mkdir(parents=True, exist_ok=True)
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            (sp / name).write_bytes(b"mock")

    def dense(self, ctx, vram_watchdog=False):
        self._record("dense")
        # Simulate fused.ply
        d = Path(ctx.dense_path)
        d.mkdir(parents=True, exist_ok=True)
        (d / "fused.ply").write_bytes(b"ply\nmock\n" + b"x" * 2048)

    def _record(self, name: str):
        self._call_order.append(name)
        if self._fail_on == name:
            from mapfree.core.exceptions import EngineError
            raise EngineError(name.upper(), f"mock failure in {name}", returncode=1)


def _make_context(tmp_path: Path, images_path: Path | None = None):
    """Return a minimal ProjectContext for a temp project."""
    from mapfree.core.context import ProjectContext
    img = images_path or tmp_path / "images"
    img.mkdir(exist_ok=True)
    # Create at least one dummy image so count_images > 0
    (img / "img_01.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    ctx = ProjectContext(tmp_path, img, {})
    ctx.event_bus = EventBus()
    ctx.stop_event = threading.Event()
    return ctx


def _make_pipeline(ctx, engine, **kwargs) -> Pipeline:
    return Pipeline(engine, ctx, **kwargs)


# ---------------------------------------------------------------------------
# Patch targets that prevent test isolation
# ---------------------------------------------------------------------------
_PATCH_HARDWARE = "mapfree.core.pipeline.hardware.get_hardware_profile"
_PATCH_HARDWARE_VRAM = "mapfree.core.pipeline.hardware.detect_gpu_vram"
_PATCH_FINAL_RESULTS = "mapfree.core.pipeline.final_results_module.export_final_results"
_PATCH_GEO_ENABLED = "mapfree.core.pipeline.Pipeline._config_enable_geospatial"
_PATCH_SET_LOG = "mapfree.core.pipeline.set_log_file_for_project"


def _hw_mock():
    hw = MagicMock()
    hw.ram_gb = 8.0
    hw.vram_mb = 4096
    return hw


# ---------------------------------------------------------------------------
# 1. Stage ordering
# ---------------------------------------------------------------------------

def test_stage_ordering(tmp_path):
    """feature_extraction → matching → sparse → dense are called in order."""
    ctx = _make_context(tmp_path)
    engine = _MockEngine()

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        pipe = _make_pipeline(ctx, engine)
        pipe.run()

    assert engine._call_order == [
        "feature_extraction", "matching", "sparse", "dense"
    ], f"Unexpected stage order: {engine._call_order}"


# ---------------------------------------------------------------------------
# 2. Pipeline emits pipeline_started event
# ---------------------------------------------------------------------------

def test_pipeline_emits_started_event(tmp_path):
    """pipeline_started is emitted via EventBus at the beginning of run()."""
    ctx = _make_context(tmp_path)
    engine = _MockEngine()
    started_events = []
    ctx.event_bus.subscribe("pipeline_started", lambda n, d: started_events.append(n))

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        _make_pipeline(ctx, engine).run()

    assert len(started_events) >= 1, "pipeline_started event was not emitted"


# ---------------------------------------------------------------------------
# 3. Pipeline emits pipeline_finished event
# ---------------------------------------------------------------------------

def test_pipeline_emits_completed_event(tmp_path):
    """pipeline_finished is emitted at the end of a successful run()."""
    ctx = _make_context(tmp_path)
    engine = _MockEngine()
    finished_events = []
    ctx.event_bus.subscribe("pipeline_finished", lambda n, d: finished_events.append(n))

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        _make_pipeline(ctx, engine).run()

    assert len(finished_events) >= 1, "pipeline_finished event was not emitted"


# ---------------------------------------------------------------------------
# 4. Pipeline stop via EventBus
# ---------------------------------------------------------------------------

def test_pipeline_stop(tmp_path):
    """
    Emitting pipeline_stop_requested sets stop_event and causes the pipeline
    to report 'Stopped by user' in pipeline_error. The stop mechanism coordinates
    with subprocess stop_event; in-flight engine calls finish but new ones abort.
    """
    ctx = _make_context(tmp_path)

    class _StopEngine:
        """Engine that emits stop_requested during feature_extraction then raises."""
        def feature_extraction(self, c):
            # Signal stop
            ctx.event_bus.emit("pipeline_stop_requested")
            # Raise so the pipeline sees an exception while _stop_requested is True
            raise RuntimeError("stopped by test")

        def matching(self, c):
            pass

        def sparse(self, c):
            pass

        def dense(self, c, vram_watchdog=False):
            pass

    engine = _StopEngine()
    error_messages: list[str] = []
    ctx.event_bus.subscribe("pipeline_error", lambda n, d: error_messages.append(str(d)))

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        try:
            _make_pipeline(ctx, engine).run()
        except Exception:
            pass  # expected: pipeline re-raises

    # stop_event must be set
    assert ctx.stop_event.is_set(), "ctx.stop_event must be set after stop_requested"
    # pipeline_error must carry a user-readable message
    assert len(error_messages) >= 1
    assert any("stop" in m.lower() or "user" in m.lower() for m in error_messages), (
        f"Expected 'Stopped by user' in error messages, got: {error_messages}"
    )


# ---------------------------------------------------------------------------
# 5. Resume skips completed stages
# ---------------------------------------------------------------------------

def test_resume_skips_completed_stages(tmp_path):
    """When sparse state is already marked done, feature_extraction is skipped."""
    ctx = _make_context(tmp_path)
    engine = _MockEngine()

    # Pre-mark sparse steps as done so pipeline skips them
    from mapfree.core.state import mark_step_done
    ctx.prepare()
    mark_step_done(tmp_path, "feature_extraction")
    mark_step_done(tmp_path, "matching")
    # Also create a valid sparse directory so sparse_valid() passes
    sp0 = Path(ctx.sparse_path) / "0"
    sp0.mkdir(parents=True, exist_ok=True)
    for name in ("cameras.bin", "images.bin", "points3D.bin"):
        (sp0 / name).write_bytes(b"mock")
    mark_step_done(tmp_path, "sparse")

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        _make_pipeline(ctx, engine).run()

    assert "feature_extraction" not in engine._call_order, (
        "feature_extraction should have been skipped (already done)"
    )
    assert "matching" not in engine._call_order, (
        "matching should have been skipped (already done)"
    )
    assert "sparse" not in engine._call_order, (
        "sparse should have been skipped (already done)"
    )
    # dense must still run (not pre-marked)
    assert "dense" in engine._call_order


# ---------------------------------------------------------------------------
# 6. EngineError emits pipeline_error event, does not silently swallow
# ---------------------------------------------------------------------------

def test_engine_error_emits_event(tmp_path):
    """EngineError from engine is re-raised and pipeline_error event is emitted."""
    from mapfree.core.exceptions import EngineError

    ctx = _make_context(tmp_path)
    engine = _MockEngine(fail_on="feature_extraction")
    error_events: list = []
    ctx.event_bus.subscribe("pipeline_error", lambda n, d: error_events.append(d))

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        with pytest.raises(EngineError):
            _make_pipeline(ctx, engine).run()

    assert len(error_events) >= 1, "pipeline_error event was not emitted on EngineError"


# ---------------------------------------------------------------------------
# 7. Integration test: full run with MockEngine
# ---------------------------------------------------------------------------

def test_pipeline_with_mock_engine(tmp_path):
    """Full pipeline run with MockEngine completes without errors."""
    ctx = _make_context(tmp_path)
    engine = _MockEngine()
    events: list[str] = []

    for ev in ("pipeline_started", "pipeline_finished"):
        ctx.event_bus.subscribe(ev, lambda n, d, _n=ev: events.append(_n))

    with patch(_PATCH_HARDWARE, return_value=_hw_mock()), \
         patch(_PATCH_HARDWARE_VRAM, return_value=4096), \
         patch(_PATCH_FINAL_RESULTS, return_value=tmp_path / "final_results"), \
         patch(_PATCH_GEO_ENABLED, return_value=False), \
         patch(_PATCH_SET_LOG, return_value=None):
        _make_pipeline(ctx, engine).run()

    assert "pipeline_started" in events
    assert "pipeline_finished" in events
    assert engine._call_order == ["feature_extraction", "matching", "sparse", "dense"]
