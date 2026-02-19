"""
Final results export: copy/link merged sparse to final_results/ and export to PLY.
The pipeline stores the final sparse model in sparse_merged/0/ (chunked) or sparse/0/ (single).
This module exposes that as final_results/sparse and final_results/sparse.ply.
If dense/fused.ply exists, it is copied to final_results/dense.ply (with empty-model warning if < 1KB).
"""
import shutil
import subprocess
from pathlib import Path

from .logger import get_logger
from .validation import sparse_valid
from .wrapper import get_process_env


FINAL_RESULTS_DIR = "final_results"
SPARSE_SUBDIR = "sparse"
SPARSE_PLY_NAME = "sparse.ply"
DENSE_PLY_NAME = "dense.ply"
FUSED_PLY_MIN_SIZE = 1024  # bytes; below this log VRAM/empty-model warning

_log = get_logger("mapfree.final_results")


def _get_colmap_bin() -> str:
    from mapfree.engines.colmap_engine import get_colmap_bin
    return get_colmap_bin()


def export_sparse_to_ply(sparse_dir: Path, output_ply_path: Path, timeout: int = 300) -> None:
    """
    Export a COLMAP sparse model (cameras.bin, images.bin, points3D.bin) to a single PLY file.
    Uses the venv colmap binary and LD_LIBRARY_PATH so shared libs (e.g. libonnxruntime) are found.
    Raises RuntimeError on failure.
    """
    sparse_dir = Path(sparse_dir)
    output_ply_path = Path(output_ply_path)
    if not sparse_valid(sparse_dir):
        raise ValueError(f"Invalid sparse model dir: {sparse_dir}")
    output_ply_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _get_colmap_bin(),
        "model_converter",
        "--input_path", str(sparse_dir),
        "--output_path", str(output_ply_path),
        "--output_type", "PLY",
    ]
    env = get_process_env()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=sparse_dir.parent)
    if r.returncode != 0:
        raise RuntimeError(
            f"COLMAP model_converter failed: {r.stderr or r.stdout or 'unknown'}"
        )


def export_final_results(project_path: Path, sparse_source_dir: Path) -> Path:
    """
    Copy the final sparse model to project_path/final_results/sparse and export to PLY.
    sparse_source_dir should be the path to the final sparse model (e.g. sparse_merged/0 or sparse/0).
    Returns the final_results directory path.
    """
    project_path = Path(project_path)
    sparse_source_dir = Path(sparse_source_dir)
    if not sparse_valid(sparse_source_dir):
        raise ValueError(f"Invalid sparse model: {sparse_source_dir}")

    final_dir = project_path / FINAL_RESULTS_DIR
    final_dir.mkdir(parents=True, exist_ok=True)
    dest_sparse = final_dir / SPARSE_SUBDIR
    dest_sparse.mkdir(parents=True, exist_ok=True)

    for name in ("cameras.bin", "images.bin", "points3D.bin"):
        src = sparse_source_dir / name
        if src.exists():
            shutil.copy2(src, dest_sparse / name)

    ply_path = final_dir / SPARSE_PLY_NAME
    export_sparse_to_ply(sparse_source_dir, ply_path)

    # Copy dense fused.ply to final_results/dense.ply if present
    dense_dir = project_path / "dense"
    fused_src = dense_dir / "fused.ply"
    if fused_src.exists():
        size = fused_src.stat().st_size
        if size < FUSED_PLY_MIN_SIZE:
            _log.warning(
                "Dense fusion produced an empty model, possibly due to VRAM limits (fused.ply %d bytes)",
                size,
            )
        dest_dense_ply = final_dir / DENSE_PLY_NAME
        shutil.copy2(fused_src, dest_dense_ply)

    return final_dir
