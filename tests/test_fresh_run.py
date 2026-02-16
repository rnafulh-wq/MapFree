"""
STEP 5 — Clean Build Reproducibility Check
Simulates fresh pipeline run: state auto-created, no crash, no manual intervention.
Run: python tests/test_fresh_run.py > audit_report/fresh_run_test.txt 2>&1
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.config import load_config, reset_config
reset_config()
load_config()

from mapfree.core.state import load_state, save_state, is_step_done, mark_step_done, reset_state
from mapfree.core.context import ProjectContext
from mapfree.core.engine import BaseEngine
from mapfree.core.pipeline import Pipeline
from mapfree.core.validation import sparse_valid, dense_valid
from mapfree.core.events import Event

PASS = 0
FAIL = 0
events_log = []

def report(name, ok, detail=""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


def event_collector(e: Event):
    events_log.append((e.type, e.message))


class MockEngine(BaseEngine):
    """Engine that creates fake outputs instead of running COLMAP."""
    def __init__(self):
        self.calls = []

    def feature_extraction(self, ctx):
        self.calls.append("feature_extraction")

    def matching(self, ctx):
        self.calls.append("matching")

    def sparse(self, ctx):
        self.calls.append("sparse")
        sp = Path(ctx.sparse_path) / "0"
        sp.mkdir(parents=True, exist_ok=True)
        for f in ("cameras.bin", "images.bin", "points3D.bin"):
            (sp / f).write_bytes(b"\x00" * 64)

    def dense(self, ctx, vram_watchdog=False):
        self.calls.append("dense")
        d = Path(ctx.dense_path)
        d.mkdir(parents=True, exist_ok=True)
        (d / "fused.ply").write_bytes(b"\x00" * 128)


print("=" * 60)
print(" STEP 5 — Clean Build Reproducibility Check")
print("=" * 60)

# ---------------------------------------------------------------
# 1. Fresh workspace — no state file
# ---------------------------------------------------------------
print("\n1. Fresh workspace (no prior state)")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / "project"
    img = Path(tmp) / "images"
    img.mkdir()
    for i in range(5):
        (img / f"IMG_{i:04d}.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)

    # State should not exist
    state_file = ws / ".mapfree_state.json"
    report("no state file initially", not state_file.exists())

    # Load state → should return defaults
    s = load_state(ws)
    report("default state on fresh", s["feature_extraction"] is False)
    report("default state chunks empty", s.get("chunks") == {})

# ---------------------------------------------------------------
# 2. Mock pipeline run (no COLMAP needed)
# ---------------------------------------------------------------
print("\n2. Mock pipeline run")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / "project"
    img = Path(tmp) / "images"
    img.mkdir()
    for i in range(5):
        (img / f"IMG_{i:04d}.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)

    events_log.clear()
    engine = MockEngine()
    profile = {"profile": "LOW", "max_image_size": 1600, "max_features": 8000,
               "matcher": "exhaustive", "use_gpu": 0}
    ctx = ProjectContext(ws, img, profile)
    pipeline = Pipeline(engine, ctx, on_event=event_collector, chunk_size=999, force_profile="CPU_SAFE")

    error = None
    try:
        pipeline.run()
    except Exception as e:
        error = e

    report("pipeline did not crash", error is None,
           f"error: {error}" if error else "")
    report("engine called feature_extraction", "feature_extraction" in engine.calls)
    report("engine called matching", "matching" in engine.calls)
    report("engine called sparse", "sparse" in engine.calls)
    report("engine called dense", "dense" in engine.calls)

    # State should be cleaned up (all done)
    state_file = ws / ".mapfree_state.json"
    report("state file cleaned after complete", not state_file.exists(),
           "state file still exists" if state_file.exists() else "")

    # Events
    types = [t for t, m in events_log]
    report("got 'start' event", "start" in types)
    report("got 'complete' event", "complete" in types)
    report("no 'error' event", "error" not in types)

# ---------------------------------------------------------------
# 3. Second run on completed project → no re-run
# ---------------------------------------------------------------
print("\n3. Idempotent re-run")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / "project"
    img = Path(tmp) / "images"
    img.mkdir()
    for i in range(5):
        (img / f"IMG_{i:04d}.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)

    engine = MockEngine()
    profile = {"profile": "CPU_SAFE", "max_image_size": 1600, "max_features": 8000,
               "matcher": "exhaustive", "use_gpu": 0}
    ctx = ProjectContext(ws, img, profile)
    pipeline = Pipeline(engine, ctx, on_event=lambda e: None, chunk_size=999, force_profile="CPU_SAFE")

    # First run
    pipeline.run()
    calls_first = list(engine.calls)

    # Second run (same workspace, outputs exist)
    engine.calls.clear()
    ctx2 = ProjectContext(ws, img, profile)
    pipeline2 = Pipeline(engine, ctx2, on_event=lambda e: None, chunk_size=999, force_profile="CPU_SAFE")
    pipeline2.run()

    report("second run calls engine again (state was reset)",
           len(engine.calls) > 0,
           f"calls: {engine.calls}")

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
