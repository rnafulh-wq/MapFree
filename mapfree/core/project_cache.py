"""Per-project cache: .cache/temp under project root, cleaned when pipeline finishes."""

import logging
import shutil
from pathlib import Path
from typing import Union

log = logging.getLogger(__name__)

CACHE_SUBDIR = ".cache"
TEMP_SUBDIR = "temp"


def get_project_cache_dir(project_path: Union[Path, str]) -> Path:
    """Return project cache temp dir: <project_root>/.cache/temp."""
    root = Path(project_path).resolve()
    return root / CACHE_SUBDIR / TEMP_SUBDIR


def get_project_cache_root(project_path: Union[Path, str]) -> Path:
    """Return project cache root: <project_root>/.cache."""
    root = Path(project_path).resolve()
    return root / CACHE_SUBDIR


def ensure_project_cache_dir(project_path: Union[Path, str]) -> Path:
    """Create .cache/temp under project root; return path. Idempotent."""
    cache_dir = get_project_cache_dir(project_path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def cleanup_project_cache(project_path: Union[Path, str]) -> None:
    """Remove .cache/ under project root (and .cache/temp). No-op if missing."""
    cache_root = get_project_cache_root(project_path)
    if not cache_root.is_dir():
        return
    try:
        shutil.rmtree(cache_root, ignore_errors=True)
        log.debug("Cleaned project cache: %s", cache_root)
    except OSError as e:
        log.debug("Could not remove project cache %s: %s", cache_root, e)
