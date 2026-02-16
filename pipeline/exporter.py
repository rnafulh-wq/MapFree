"""Output helpers: paths and optional copy for sparse/dense results."""

from pathlib import Path


def get_sparse_model_path(project_path: Path) -> Path:
    """Path to sparse reconstruction (sparse/0 with cameras, images, points3D)."""
    return Path(project_path) / "sparse" / "0"


def get_dense_ply_path(project_path: Path) -> Path:
    """Path to dense fused point cloud (PLY)."""
    return Path(project_path) / "dense" / "fused.ply"


def ensure_dense_ply_copy(project_path: Path, name: str = "dense_pointcloud.ply") -> Path:
    """
    Copy fused.ply to project_path/dense/<name> for a predictable filename.
    Return path to the copy. No-op if source missing.
    """
    src = get_dense_ply_path(project_path)
    dst = Path(project_path) / "dense" / name
    if not src.exists():
        return src
    if dst.resolve() != src.resolve():
        import shutil
        shutil.copy2(src, dst)
    return dst
