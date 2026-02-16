"""
Validation of engine outputs (sparse/dense dirs).
State does not know engine output layout; this module does.
"""
from pathlib import Path


def file_valid(path) -> bool:
    """File exists and has size > 0."""
    p = Path(path)
    return p.is_file() and p.stat().st_size > 0


def sparse_valid(sparse_dir) -> bool:
    """Sparse dir (e.g. .../sparse/0) has cameras.bin and non-empty images/points3D."""
    d = Path(sparse_dir)
    cam = d / "cameras.bin"
    if not file_valid(cam):
        return False
    for name in ("images.bin", "points3D.bin"):
        f = d / name
        if f.exists() and f.stat().st_size == 0:
            return False
    return True


def dense_valid(dense_path) -> bool:
    """Dense folder has fused.ply (size > 0) and is non-empty."""
    d = Path(dense_path)
    fused = d / "fused.ply"
    if not file_valid(fused):
        return False
    try:
        return any(d.iterdir())
    except OSError:
        return False
