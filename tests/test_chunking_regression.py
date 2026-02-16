"""
BUG-003 Regression Test — Chunking copy destination.
Ensures images are copied INTO chunk folders, not to CWD.
Run: python tests/test_chunking_regression.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.core.chunking import split_dataset, count_images

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


def _create_images(folder, count):
    folder.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(count):
        name = f"IMG_{i:04d}.jpg"
        (folder / name).write_bytes(b"\xff\xd8" + b"\x00" * 100)
        names.append(name)
    return sorted(names)


print("=" * 60)
print(" BUG-003 Regression — Chunking Copy Destination")
print("=" * 60)

# ---------------------------------------------------------------
# 1. Images must be INSIDE chunk folders (not CWD)
# ---------------------------------------------------------------
print("\n1. Images copied to chunk folders, not CWD")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    orig_names = _create_images(img, 20)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=7)
    # 20 / 7 = 3 chunks (7, 7, 6)
    report("3 chunks created", len(chunks) == 3, f"got {len(chunks)}")

    for c in chunks:
        files = sorted(p.name for p in c.iterdir() if p.is_file())
        report(f"{c.name} has images inside", len(files) > 0, f"count={len(files)}")

        # Verify files are actually in the chunk folder, not elsewhere
        for f in files:
            full = c / f
            report(f"{c.name}/{f} exists in chunk dir", full.exists())
            break  # one sample per chunk is enough

    # Total images across all chunks
    all_imgs = []
    for c in chunks:
        all_imgs.extend(p.name for p in c.iterdir() if p.is_file())
    report("total images = 20", len(all_imgs) == 20, f"got {len(all_imgs)}")
    report("no duplicates", len(set(all_imgs)) == len(all_imgs))

    # No images leaked to CWD
    import os
    cwd_jpgs = [f for f in os.listdir(".") if f.endswith(".jpg") and f.startswith("IMG_")]
    report("no images in CWD", len(cwd_jpgs) == 0,
           f"found in CWD: {cwd_jpgs[:5]}" if cwd_jpgs else "")

# ---------------------------------------------------------------
# 2. No chunking case still works
# ---------------------------------------------------------------
print("\n2. Small dataset (no chunking)")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    _create_images(img, 5)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=100)
    report("returns original folder", len(chunks) == 1 and chunks[0] == img)

# ---------------------------------------------------------------
# 3. Chunk folder names are sequential
# ---------------------------------------------------------------
print("\n3. Chunk folder naming")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    _create_images(img, 15)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=5)
    names = [c.name for c in chunks]
    report("3 chunks", len(chunks) == 3)
    report("chunk names sequential", names == ["chunk_001", "chunk_002", "chunk_003"],
           f"got {names}")

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
