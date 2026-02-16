"""
STEP 2 — Resume Reliability Test
Simulates pipeline interruptions and validates resume behavior.
Run: python tests/test_resume_engine.py > audit_report/resume_test.txt 2>&1
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.core.state import (
    load_state, save_state, mark_step_done, is_step_done, reset_state,
)
from mapfree.core.validation import sparse_valid, dense_valid
from mapfree.core.config import COMPLETION_STEPS

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


def _make_sparse(d):
    """Create fake valid sparse output."""
    sp = d / "sparse" / "0"
    sp.mkdir(parents=True, exist_ok=True)
    for f in ("cameras.bin", "images.bin", "points3D.bin"):
        (sp / f).write_bytes(b"\x00" * 64)
    return sp


def _make_dense(d):
    """Create fake valid dense output."""
    dense = d / "dense"
    dense.mkdir(parents=True, exist_ok=True)
    (dense / "fused.ply").write_bytes(b"\x00" * 128)
    return dense


print("=" * 60)
print(" STEP 2 — Resume Reliability Test")
print("=" * 60)

# ---------------------------------------------------------------
# A. Sparse interruption → resume should continue to dense
# ---------------------------------------------------------------
print("\nA. Sparse interruption simulation")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)

    # Simulate: sparse just finished, dense not done
    state = load_state(ws)
    state["feature_extraction"] = True
    state["matching"] = True
    state["sparse"] = True
    state["dense"] = False
    save_state(ws, state)

    # Verify state loads correctly
    s = load_state(ws)
    report("feature_extraction=True after save", s["feature_extraction"] is True)
    report("matching=True after save", s["matching"] is True)
    report("sparse=True after save", s["sparse"] is True)
    report("dense=False after save", s["dense"] is False)

    # Simulate resume: pipeline checks is_step_done
    report("is_step_done(sparse)=True", is_step_done(ws, "sparse") is True)
    report("is_step_done(dense)=False", is_step_done(ws, "dense") is False)

    # Pipeline would skip sparse, run dense. Mark dense done.
    _make_dense(ws)
    mark_step_done(ws, "dense")
    report("dense marked done", is_step_done(ws, "dense") is True)

    # Post-process: all COMPLETION_STEPS done → state reset
    s = load_state(ws)
    all_done = all(s.get(step, False) for step in COMPLETION_STEPS)
    report("all COMPLETION_STEPS done", all_done)
    if all_done:
        reset_state(ws)
    report("state file removed", not (ws / ".mapfree_state.json").exists())

# ---------------------------------------------------------------
# B. Dense interruption → resume should go straight to dense
# ---------------------------------------------------------------
print("\nB. Dense interruption simulation")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)

    state = load_state(ws)
    state["feature_extraction"] = True
    state["matching"] = True
    state["sparse"] = True
    state["dense"] = False
    save_state(ws, state)

    # Resume: should skip sparse, go to dense
    report("skip feature_extraction", is_step_done(ws, "feature_extraction") is True)
    report("skip matching", is_step_done(ws, "matching") is True)
    report("skip sparse", is_step_done(ws, "sparse") is True)
    report("run dense", is_step_done(ws, "dense") is False)

# ---------------------------------------------------------------
# C. Corrupt dense folder → should rebuild dense
# ---------------------------------------------------------------
print("\nC. Corrupt dense folder simulation")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)

    # Sparse done, dense marked done but folder is corrupt/missing
    state = load_state(ws)
    state["feature_extraction"] = True
    state["matching"] = True
    state["sparse"] = True
    state["dense"] = True
    save_state(ws, state)

    # Create empty dense (no fused.ply)
    dense_dir = ws / "dense"
    dense_dir.mkdir(parents=True, exist_ok=True)

    # dense_valid should fail
    report("empty dense_dir invalid", dense_valid(dense_dir) is False)

    # Pipeline logic: is_step_done AND dense_valid
    should_rebuild = is_step_done(ws, "dense") and not dense_valid(dense_dir)
    report("should rebuild dense", should_rebuild is True)

    # Now delete dense entirely
    shutil.rmtree(dense_dir)
    report("deleted dense_dir invalid", dense_valid(dense_dir) is False)
    report("should rebuild after delete", not dense_valid(dense_dir))

# ---------------------------------------------------------------
# D. Corrupt state file → should recover gracefully
# ---------------------------------------------------------------
print("\nD. Corrupt state file simulation")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)
    state_path = ws / ".mapfree_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{invalid json!!!}")

    s = load_state(ws)
    report("corrupt JSON returns default state", s.get("feature_extraction") is False)
    report("corrupt JSON chunks empty", s.get("chunks") == {})

# ---------------------------------------------------------------
# E. Legacy chunk_sparse_done migration
# ---------------------------------------------------------------
print("\nE. Legacy state migration")
with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)
    state_path = ws / ".mapfree_state.json"
    ws.mkdir(parents=True, exist_ok=True)
    legacy = {
        "feature_extraction": True,
        "matching": True,
        "sparse": False,
        "dense": False,
        "mesh": False,
        "chunk_sparse_done": ["chunk_001", "chunk_002"],
    }
    state_path.write_text(json.dumps(legacy))

    s = load_state(ws)
    report("legacy migrated to chunks dict", "chunk_001" in s.get("chunks", {}))
    report("chunk_001 mapping=True", s["chunks"]["chunk_001"].get("mapping") is True)
    report("chunk_sparse_done removed", "chunk_sparse_done" not in s)

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
