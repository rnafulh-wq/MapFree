"""File and path helpers. Production stub."""

from pathlib import Path
from typing import List, Optional


def ensure_dir(path: Path) -> Path:
    """Create directory and parents if needed. Return path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_remove(path: Path) -> bool:
    """Remove file if exists. Return True if removed."""
    try:
        if path.exists():
            path.unlink()
            return True
    except OSError:
        pass
    return False


def list_images(dir_path: Path, extensions: Optional[List[str]] = None) -> List[Path]:
    """Return sorted list of image paths in directory. Optional filter by extensions."""
    exts = extensions or {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    paths = [p for p in dir_path.iterdir() if p.suffix.lower() in exts]
    return sorted(paths)
