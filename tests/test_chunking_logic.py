"""
STEP 3 — Chunking Integrity Test
Validates split_dataset logic: no duplicates, no missing, correct chunk sizes.
Run: python tests/test_chunking_logic.py > audit_report/chunking_test.txt 2>&1
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.core.chunking import split_dataset, count_images, _list_images
from mapfree.core.config import IMAGE_EXTENSIONS

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
    """Create dummy .jpg files."""
    folder.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(count):
        name = f"IMG_{i:04d}.jpg"
        (folder / name).write_bytes(b"\xff\xd8" + b"\x00" * 100)
        names.append(name)
    return sorted(names)


print("=" * 60)
print(" STEP 3 — Chunking Integrity Test")
print("=" * 60)

# ---------------------------------------------------------------
# 1. Small dataset → no chunking
# ---------------------------------------------------------------
print("\n1. Small dataset (10 images, chunk_size=250)")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    orig = _create_images(img, 10)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=250)
    report("no chunking (returns original)", len(chunks) == 1 and chunks[0] == img)
    report("count_images correct", count_images(img) == 10)

# ---------------------------------------------------------------
# 2. Medium dataset → chunks created
# ---------------------------------------------------------------
print("\n2. Medium dataset (30 images, chunk_size=10)")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    orig = _create_images(img, 30)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=10)
    report("3 chunks created", len(chunks) == 3, f"got {len(chunks)}")

    # Collect all images across chunks
    all_chunk_images = []
    for c in chunks:
        all_chunk_images.extend(sorted(p.name for p in c.iterdir() if p.is_file()))

    report("no missing images", len(all_chunk_images) == 30,
           f"got {len(all_chunk_images)}")

    # Check for duplicates
    unique = set(all_chunk_images)
    report("no duplicate images", len(unique) == len(all_chunk_images),
           f"unique={len(unique)}, total={len(all_chunk_images)}")

    # All original names present
    missing = set(orig) - unique
    report("all originals present", len(missing) == 0,
           f"missing: {missing}" if missing else "")

# ---------------------------------------------------------------
# 3. Large dataset → more chunks
# ---------------------------------------------------------------
print("\n3. Large dataset (100 images, chunk_size=30)")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    orig = _create_images(img, 100)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=30)
    expected_chunks = 4  # ceil(100/30)
    report("4 chunks created", len(chunks) == expected_chunks,
           f"got {len(chunks)}")

    all_names = []
    for c in chunks:
        names = sorted(p.name for p in c.iterdir() if p.is_file())
        all_names.extend(names)

    report("total images = 100", len(all_names) == 100,
           f"got {len(all_names)}")
    report("no duplicates", len(set(all_names)) == len(all_names))
    report("no missing", set(orig) == set(all_names))

    # Chunk sizes: 30, 30, 30, 10
    sizes = [len(list(c.iterdir())) for c in chunks]
    report("chunk sizes correct", sizes == [30, 30, 30, 10],
           f"got {sizes}")

# ---------------------------------------------------------------
# 4. Empty dataset
# ---------------------------------------------------------------
print("\n4. Empty dataset")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    img.mkdir()
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=10)
    report("empty returns []", chunks == [])
    report("count_images = 0", count_images(img) == 0)

# ---------------------------------------------------------------
# 5. Exact chunk_size boundary
# ---------------------------------------------------------------
print("\n5. Boundary: 10 images, chunk_size=10")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    _create_images(img, 10)
    proj.mkdir()

    chunks = split_dataset(img, proj, chunk_size=10)
    report("no chunking at exact boundary", len(chunks) == 1 and chunks[0] == img)

# ---------------------------------------------------------------
# 6. Non-image files ignored
# ---------------------------------------------------------------
print("\n6. Non-image files ignored")
with tempfile.TemporaryDirectory() as tmp:
    img = Path(tmp) / "images"
    proj = Path(tmp) / "project"
    _create_images(img, 5)
    (img / "readme.txt").write_text("hello")
    (img / "data.csv").write_text("a,b,c")
    proj.mkdir()

    report("count_images ignores non-images", count_images(img) == 5)

print("\n" + "=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
