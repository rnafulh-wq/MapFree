"""
Dataset chunking and sparse model merge.
Uses only stdlib: pathlib, shutil, subprocess.
"""
import shutil
import subprocess
from pathlib import Path

from . import hardware
from .config import IMAGE_EXTENSIONS
from .profiles import resolve_chunk_size as _profiles_resolve
from .wrapper import get_process_env


def _colmap_bin():
    from mapfree.engines.colmap_engine import get_colmap_bin
    return get_colmap_bin()


def resolve_chunk_size(override: int | None = None) -> int:
    """
    Convenience: detect hardware then resolve chunk size via profiles.
    manual override > MAPFREE_CHUNK_SIZE env > hardware (VRAM + RAM).
    """
    vram_mb = hardware.detect_gpu_vram()
    ram_gb = hardware.detect_system_ram_gb()
    return _profiles_resolve(override, vram_mb, ram_gb)


def _list_images(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix in IMAGE_EXTENSIONS
    )


def count_images(folder: Path) -> int:
    """Return number of images in folder."""
    return len(_list_images(Path(folder)))


def split_dataset(
    image_folder: Path,
    project_path: Path,
    chunk_size: int | None = None,
) -> list[Path]:
    """
    If image count > chunk_size, copy images into project/chunks/chunk_001, chunk_002, ...
    Returns list of chunk folder paths. If image_count <= chunk_size, returns [image_folder].
    """
    image_folder = Path(image_folder)
    project_path = Path(project_path)
    effective = resolve_chunk_size(chunk_size)
    images = _list_images(image_folder)
    n = len(images)
    if n == 0:
        return []
    if n <= effective:
        return [image_folder]

    chunks_dir = project_path / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_folders: list[Path] = []
    for i in range(0, n, effective):
        batch = images[i : i + effective]
        chunk_idx = len(chunk_folders) + 1
        chunk_name = f"chunk_{chunk_idx:03d}"
        chunk_path = chunks_dir / chunk_name
        chunk_path.mkdir(parents=True, exist_ok=True)
        for src in batch:
            shutil.copy2(src, chunk_path / src.name)
        chunk_folders.append(chunk_path)
    return chunk_folders


def merge_sparse_models(project_path: Path, sparse_dirs: list[Path]) -> Path:
    """
    Merge multiple sparse models into project/sparse_merged/0.
    Uses colmap model_merger. If only one dir, copies it.
    Returns path to merged sparse (sparse_merged/0). This is the canonical final sparse
    output for chunked runs; the pipeline also exports it to final_results/ (copy + .ply).
    """
    project_path = Path(project_path)
    out_merged = project_path / "sparse_merged" / "0"
    out_merged.mkdir(parents=True, exist_ok=True)

    normalized = []
    for d in sparse_dirs:
        d = Path(d)
        if (d / "cameras.bin").exists():
            normalized.append(d)
        elif (d / "0" / "cameras.bin").exists():
            normalized.append(d / "0")
        else:
            continue
    if not normalized:
        raise FileNotFoundError("No valid sparse model dirs to merge")
    if len(normalized) == 1:
        for f in ("cameras.bin", "images.bin", "points3D.bin"):
            src = normalized[0] / f
            if src.exists():
                shutil.copy2(src, out_merged / f)
        return out_merged

    current = normalized[0]
    for i in range(1, len(normalized)):
        next_dir = normalized[i]
        if i == len(normalized) - 1:
            out = out_merged
        else:
            out = project_path / "sparse_merged" / f"tmp_{i}"
            out.mkdir(parents=True, exist_ok=True)
        cmd = [
            _colmap_bin(), "model_merger",
            "--input_path1", str(current),
            "--input_path2", str(next_dir),
            "--output_path", str(out),
        ]
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=get_process_env(),
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"COLMAP model_merger failed: {r.stderr or r.stdout or 'unknown'}"
            )
        current = out
    return out_merged
