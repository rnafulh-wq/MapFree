"""
BUG-001 Regression Test — Event.progress must be stored and readable.
Run: python tests/test_progress_tracking.py
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.config import reset_config, load_config
reset_config()
load_config()

from mapfree.core.events import Event, EventEmitter
from mapfree.core.state import load_state, save_state, mark_step_done, is_step_done, reset_state
from mapfree.core.context import ProjectContext
from mapfree.core.engine import BaseEngine
from mapfree.core.pipeline import Pipeline

PASS = 0
FAIL = 0

def report(name, ok, detail=""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print(" BUG-001 Regression — Progress Tracking")
print("=" * 60)

# ---------------------------------------------------------------
# 1. Event.progress stores value
# ---------------------------------------------------------------
print("\n1. Event.progress attribute")
e = Event("step", "test message", 0.42)
report("Event.progress is set", hasattr(e, "progress") and e.progress is not None,
       f"got {getattr(e, 'progress', 'MISSING')}")
report("Event.progress == 0.42", e.progress == 0.42, f"got {e.progress}")

e2 = Event("step", "no progress")
report("Event.progress defaults to None", e2.progress is None, f"got {e2.progress}")

e3 = Event("step", "zero", 0.0)
report("Event.progress == 0.0", e3.progress == 0.0, f"got {e3.progress}")

e4 = Event("step", "one", 1.0)
report("Event.progress == 1.0", e4.progress == 1.0, f"got {e4.progress}")

# ---------------------------------------------------------------
# 2. Pipeline emits progress through to on_event callback
# ---------------------------------------------------------------
print("\n2. Pipeline progress delivery")


class FakeEngine(BaseEngine):
    def feature_extraction(self, ctx): pass
    def matching(self, ctx): pass
    def sparse(self, ctx):
        sp = Path(ctx.sparse_path) / "0"
        sp.mkdir(parents=True, exist_ok=True)
        for f in ("cameras.bin", "images.bin", "points3D.bin"):
            (sp / f).write_bytes(b"\x00" * 64)
    def dense(self, ctx, vram_watchdog=False):
        d = Path(ctx.dense_path)
        d.mkdir(parents=True, exist_ok=True)
        (d / "fused.ply").write_bytes(b"\x00" * 128)


collected = []

def on_event(e: Event):
    collected.append({"type": e.type, "message": e.message, "progress": e.progress})


with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp) / "project"
    img = Path(tmp) / "images"
    img.mkdir()
    for i in range(3):
        (img / f"IMG_{i:04d}.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)

    ctx = ProjectContext(ws, img, {})
    pipeline = Pipeline(FakeEngine(), ctx, on_event=on_event, chunk_size=999, force_profile="CPU_SAFE")
    pipeline.run()

    # Check that progress values were delivered
    step_events = [e for e in collected if e["type"] == "step"]
    with_progress = [e for e in step_events if e["progress"] is not None]
    report("step events emitted", len(step_events) > 0, f"count={len(step_events)}")
    report("some step events have progress", len(with_progress) > 0, f"count={len(with_progress)}")

    # Progress values are floats 0.0-1.0
    for e in with_progress:
        p = e["progress"]
        if not (isinstance(p, (int, float)) and 0.0 <= p <= 1.0):
            report(f"progress {p} in range [0,1]", False, f"msg={e['message']}")
            break
    else:
        report("all progress values in [0.0, 1.0]", True)

    complete = [e for e in collected if e["type"] == "complete"]
    report("complete event has progress=1.0", len(complete) > 0 and complete[-1]["progress"] == 1.0,
           f"got {complete[-1]['progress'] if complete else 'NO COMPLETE EVENT'}")

# ---------------------------------------------------------------
# 3. State persistence survives simulated crash
# ---------------------------------------------------------------
print("\n3. State persistence across crash")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)

    # Simulate: step 1 done, then "crash"
    mark_step_done(ws, "feature_extraction")
    # "crash" — just stop here. State should be on disk.

    # "Resume" — reload state from disk
    s = load_state(ws)
    report("feature_extraction survived crash", s["feature_extraction"] is True)
    report("matching still False after crash", s["matching"] is False)

    # Continue: mark more done
    mark_step_done(ws, "matching")
    mark_step_done(ws, "sparse")

    s2 = load_state(ws)
    report("all three steps persisted", s2["feature_extraction"] and s2["matching"] and s2["sparse"])

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
