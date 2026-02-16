"""
BUG-002 Regression Test — COLMAP parameter validation.
Ensures no duplicate flags, correct parameter names, no deprecated flags.
Run: python tests/test_colmap_params.py
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.config import reset_config, load_config
reset_config()
load_config()

from mapfree.core.context import ProjectContext
from mapfree.engines.colmap_engine import ColmapEngine

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


def capture_cmd(engine_method, ctx, **kwargs):
    """Call engine method but capture the command instead of running it."""
    captured = []
    def fake_run(cmd, **kw):
        captured.append(cmd)
    with patch("mapfree.engines.colmap_engine._run", side_effect=fake_run):
        try:
            engine_method(ctx, **kwargs) if kwargs else engine_method(ctx)
        except Exception:
            pass
    return captured


def check_no_duplicate_flags(cmd, label):
    """Check that no COLMAP flag appears twice in the command."""
    flags = [arg for arg in cmd if arg.startswith("--")]
    seen = {}
    dups = []
    for f in flags:
        if f in seen:
            dups.append(f)
        seen[f] = True
    report(f"{label}: no duplicate flags", len(dups) == 0,
           f"duplicates: {dups}" if dups else "")
    return len(dups) == 0


KNOWN_MAPPER_FLAGS = {
    "--database_path", "--image_path", "--output_path",
    "--Mapper.ba_global_max_num_iterations",
    "--Mapper.ba_local_max_num_iterations",
}

KNOWN_FEATURE_FLAGS = {
    "--database_path", "--image_path",
    "--ImageReader.single_camera", "--ImageReader.camera_model",
    "--SiftExtraction.max_image_size", "--SiftExtraction.max_num_features",
    "--SiftExtraction.use_gpu",
}

KNOWN_MATCHER_FLAGS = {
    "--database_path",
    "--SiftMatching.use_gpu",
}

KNOWN_DENSE_FLAGS = {
    "--image_path", "--input_path", "--output_path", "--output_type",
    "--workspace_path", "--workspace_format",
    "--PatchMatchStereo.gpu_index", "--PatchMatchStereo.max_image_size",
    "--PatchMatchStereo.cache_size", "--PatchMatchStereo.window_step",
    "--PatchMatchStereo.geom_consistency",
    "--input_type", "--StereoFusion.max_image_size",
}


print("=" * 60)
print(" BUG-002 Regression — COLMAP Parameter Validation")
print("=" * 60)

with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp)
    img = ws / "images"
    img.mkdir()
    (img / "test.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)

    profile = {"profile": "LOW", "max_image_size": 1600, "max_features": 8000,
               "matcher": "exhaustive", "use_gpu": 1}
    ctx = ProjectContext(ws, img, profile)
    ctx.prepare()
    engine = ColmapEngine()

    # ---------------------------------------------------------------
    # 1. Feature extraction
    # ---------------------------------------------------------------
    print("\n1. Feature extraction parameters")
    cmds = capture_cmd(engine.feature_extraction, ctx)
    report("feature_extraction produces 1 command", len(cmds) == 1)
    if cmds:
        cmd = cmds[0]
        report("command starts with 'colmap feature_extractor'",
               cmd[0] == "colmap" and cmd[1] == "feature_extractor")
        check_no_duplicate_flags(cmd, "feature_extraction")
        flags = {a for a in cmd if a.startswith("--")}
        unknown = flags - KNOWN_FEATURE_FLAGS
        report("no unknown flags", len(unknown) == 0,
               f"unknown: {unknown}" if unknown else "")

    # ---------------------------------------------------------------
    # 2. Matching
    # ---------------------------------------------------------------
    print("\n2. Matching parameters")
    cmds = capture_cmd(engine.matching, ctx)
    report("matching produces 1 command", len(cmds) == 1)
    if cmds:
        cmd = cmds[0]
        report("command starts with 'colmap exhaustive_matcher'",
               cmd[0] == "colmap" and "matcher" in cmd[1])
        check_no_duplicate_flags(cmd, "matching")

    # ---------------------------------------------------------------
    # 3. Sparse (mapper) — BUG-002 regression target
    # ---------------------------------------------------------------
    print("\n3. Sparse (mapper) parameters — BUG-002 regression")
    cmds = capture_cmd(engine.sparse, ctx)
    report("sparse produces 1 command", len(cmds) == 1)
    if cmds:
        cmd = cmds[0]
        report("command starts with 'colmap mapper'",
               cmd[0] == "colmap" and cmd[1] == "mapper")
        check_no_duplicate_flags(cmd, "sparse")

        # Specific BUG-002 check: ba_global and ba_local must be DIFFERENT flags
        ba_flags = [i for i, a in enumerate(cmd) if "ba_" in a and "max_num_iterations" in a]
        if len(ba_flags) == 2:
            flag1 = cmd[ba_flags[0]]
            flag2 = cmd[ba_flags[1]]
            report("ba_global and ba_local are DIFFERENT flags",
                   flag1 != flag2,
                   f"flag1={flag1}, flag2={flag2}")
            report("has ba_global_max_num_iterations",
                   "--Mapper.ba_global_max_num_iterations" in cmd)
            report("has ba_local_max_num_iterations",
                   "--Mapper.ba_local_max_num_iterations" in cmd)

            # Check values
            global_val = cmd[ba_flags[0] + 1]
            local_val = cmd[ba_flags[1] + 1]
            report(f"ba_global value = {global_val}", global_val.isdigit() and int(global_val) > 0)
            report(f"ba_local value = {local_val}", local_val.isdigit() and int(local_val) > 0)
        else:
            report("exactly 2 BA iteration flags", False,
                   f"found {len(ba_flags)}")

    # ---------------------------------------------------------------
    # 4. Dense
    # ---------------------------------------------------------------
    print("\n4. Dense parameters")
    # Create fake sparse output for dense
    sp = ctx.sparse_path / "0"
    sp.mkdir(parents=True, exist_ok=True)
    for f in ("cameras.bin", "images.bin", "points3D.bin"):
        (sp / f).write_bytes(b"\x00" * 64)

    cmds = capture_cmd(engine.dense, ctx, vram_watchdog=False)
    report(f"dense produces 3 commands", len(cmds) == 3,
           f"got {len(cmds)}")
    for i, cmd in enumerate(cmds):
        check_no_duplicate_flags(cmd, f"dense_step_{i}")

    # ---------------------------------------------------------------
    # 5. Profile safety: LOW profile caps
    # ---------------------------------------------------------------
    print("\n5. Profile safety checks")
    cmds = capture_cmd(engine.feature_extraction, ctx)
    if cmds:
        cmd = cmds[0]
        # max_image_size should be capped at 1600
        idx = None
        for j, a in enumerate(cmd):
            if a == "--SiftExtraction.max_image_size":
                idx = j + 1
                break
        if idx and idx < len(cmd):
            val = int(cmd[idx])
            report(f"feature max_image_size={val} <= 1600", val <= 1600)
        # max_features capped at 8000
        idx2 = None
        for j, a in enumerate(cmd):
            if a == "--SiftExtraction.max_num_features":
                idx2 = j + 1
                break
        if idx2 and idx2 < len(cmd):
            val2 = int(cmd[idx2])
            report(f"feature max_features={val2} <= 8000", val2 <= 8000)

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
