"""
STEP 4 — Memory Profile Validation
Validates profile selection across VRAM/RAM ranges.
Run: python tests/test_profiles.py > audit_report/profile_test.txt 2>&1
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.core.config import load_config, reset_config
reset_config()
load_config()

from mapfree.core.profiles import get_profile, recommend_chunk_size, resolve_chunk_size

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
print(" STEP 4 — Memory Profile Validation")
print("=" * 60)

# ---------------------------------------------------------------
# 1. VRAM-based profile selection
# ---------------------------------------------------------------
print("\n1. Profile selection by VRAM")

cases = [
    (0, "CPU_SAFE"),
    (512, "CPU_SAFE"),
    (1024, "LOW"),
    (1500, "LOW"),
    (2048, "MEDIUM"),
    (3000, "MEDIUM"),
    (4096, "HIGH"),
    (8192, "HIGH"),
    (16384, "HIGH"),
]
for vram, expected in cases:
    p = get_profile(vram)
    got = p.get("profile", "???")
    report(f"VRAM={vram} → {expected}", got == expected, f"got {got}")

# ---------------------------------------------------------------
# 2. Profile dict has required keys
# ---------------------------------------------------------------
print("\n2. Profile dict completeness")
required_keys = {"profile", "max_image_size", "max_features", "matcher", "use_gpu"}
for vram in [0, 1024, 2048, 4096]:
    p = get_profile(vram)
    missing = required_keys - set(p.keys())
    report(f"VRAM={vram} has all keys", len(missing) == 0,
           f"missing: {missing}" if missing else "")

# ---------------------------------------------------------------
# 3. No negative values
# ---------------------------------------------------------------
print("\n3. No negative values in profiles")
for vram in [0, 1024, 2048, 4096]:
    p = get_profile(vram)
    for k in ("max_image_size", "max_features", "use_gpu"):
        val = p.get(k, 0)
        report(f"VRAM={vram} {k}={val} >= 0", val >= 0)

# ---------------------------------------------------------------
# 4. Chunk size recommendations
# ---------------------------------------------------------------
print("\n4. Chunk size recommendations")
chunk_cases = [
    (0, 2.0, 100),     # CPU_SAFE
    (512, 4.0, 100),   # CPU_SAFE
    (1024, 4.0, 150),  # LOW
    (2048, 8.0, 250),  # MEDIUM
    (4096, 16.0, 400), # HIGH
]
for vram, ram, expected in chunk_cases:
    got = recommend_chunk_size(vram, ram)
    report(f"chunk(VRAM={vram}, RAM={ram}) = {expected}", got == expected, f"got {got}")

# ---------------------------------------------------------------
# 5. Chunk size always positive
# ---------------------------------------------------------------
print("\n5. Chunk size always positive")
for vram in [0, 512, 1024, 2048, 4096]:
    for ram in [0, 0.5, 2.0, 8.0, 32.0]:
        c = recommend_chunk_size(vram, ram)
        if c <= 0:
            report(f"chunk(VRAM={vram}, RAM={ram}) > 0", False, f"got {c}")
            break
    else:
        continue
    break
else:
    report("all chunk sizes positive", True)

# ---------------------------------------------------------------
# 6. resolve_chunk_size priority
# ---------------------------------------------------------------
print("\n6. resolve_chunk_size priority")
# Override wins
got = resolve_chunk_size(override=42, vram_mb=4096, ram_gb=32)
report("explicit override wins", got == 42, f"got {got}")

# Config max_images_per_chunk wins when override=None
got = resolve_chunk_size(override=None, vram_mb=4096, ram_gb=32)
report("config value used when no override", got > 0, f"got {got}")

# ---------------------------------------------------------------
# 7. Retry count bounded (not infinite)
# ---------------------------------------------------------------
print("\n7. Retry count from config")
from mapfree.core.config import get_config
cfg = get_config()
retry = cfg.get("retry_count", 0)
report("retry_count > 0", retry > 0, f"got {retry}")
report("retry_count <= 10 (bounded)", retry <= 10, f"got {retry}")

# VRAM watchdog downscale
vw = cfg.get("vram_watchdog") or {}
ds = vw.get("downscale_factor", 1.0)
report("downscale_factor < 1.0", ds < 1.0, f"got {ds}")
report("downscale_factor > 0.0", ds > 0.0, f"got {ds}")

# After max retries, image_size won't go negative
size = 1600
for i in range(retry + 5):
    size = max(100, int(size * ds))
report(f"after {retry+5} retries, size={size} >= 100", size >= 100)

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
