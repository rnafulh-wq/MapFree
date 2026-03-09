"""
Single source of truth for finding the COLMAP executable.

Used by dependency_check and colmap_engine so pipeline and GUI
agree on the same binary. Supports: env, config, PathManager registry,
default Windows dirs, extra dirs (wizard/portable), PATH.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_COLMAP_NAMES = ["colmap.exe", "COLMAP.exe", "COLMAP.bat", "colmap.bat", "colmap"]


def _extra_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / ".mapfree" / "deps" / "colmap",
        home / ".mapfree" / "deps",
        Path("C:/MapFree/deps/colmap"),
        Path("C:/MapFree/deps"),
        Path("C:/colmap/bin"),
        Path("C:/colmap"),
    ]


def _default_windows() -> list[Path]:
    return [
        Path("C:/tools/COLMAP/COLMAP.bat"),
        Path("C:/tools/COLMAP/colmap.exe"),
    ]


def _is_executable(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file():
        return os.access(path, os.X_OK) or path.suffix.lower() in (".bat", ".cmd", ".exe")
    return False


def find_colmap_executable() -> Optional[str]:
    """
    Find COLMAP executable in order:
    1. MAPFREE_COLMAP or MAPFREE_COLMAP_PATH env
    2. Config colmap_path / colmap.colmap_bin
    3. PathManager deps_registry.json (colmap / COLMAP)
    4. Default Windows: C:/tools/COLMAP, C:/colmap, C:/MapFree/deps/colmap
    5. Extra dirs (wizard/portable)
    6. Conda env (Library/bin, Scripts) of current Python — find_tool("colmap")
    7. shutil.which on PATH

    Returns absolute path string or None if not found.
    """
    import shutil

    # 1. Environment
    env_path = (
        os.environ.get("MAPFREE_COLMAP", "").strip()
        or os.environ.get("MAPFREE_COLMAP_PATH", "").strip()
    )
    if env_path:
        p = Path(env_path).resolve()
        if _is_executable(p):
            return str(p)
        which = shutil.which(env_path)
        if which:
            return os.path.abspath(which)
        return None

    # 2. Config
    try:
        from mapfree.core.config import get_config
        cfg = get_config()
        for key in ("colmap_path", "colmap_bin"):
            val = cfg.get(key) if key == "colmap_path" else (cfg.get("colmap") or {}).get(key)
            if val and str(val).strip():
                path_str = str(val).strip()
                p = Path(path_str).resolve()
                if _is_executable(p):
                    return str(p)
                if os.path.sep not in path_str:
                    which = shutil.which(path_str)
                    if which:
                        return os.path.abspath(which)
    except Exception:
        pass

    # 3. PathManager registry
    try:
        from mapfree.utils.path_manager import PathManager
        for key in ("colmap", "COLMAP"):
            p = PathManager.get_dep_path(key)
            if p is not None:
                return str(p)
    except Exception:
        pass

    # 4. Default Windows paths
    if sys.platform == "win32":
        for p in _default_windows():
            p = p.resolve()
            if _is_executable(p):
                return str(p)

    # 5. Extra dirs (direct + one level subdir)
    for base in _extra_dirs():
        if not base.exists():
            continue
        for cand in _COLMAP_NAMES:
            p = base / cand
            if p.is_file() and _is_executable(p):
                return str(p)
        try:
            for sub in base.iterdir():
                if sub.is_dir():
                    for cand in _COLMAP_NAMES:
                        p = sub / cand
                        if p.is_file() and _is_executable(p):
                            return str(p)
        except OSError:
            pass

    # 6. Conda env (Library/bin, Scripts) of current Python — same as find_tool for GDAL/PDAL
    try:
        from mapfree.core.dependencies import find_tool
        found = find_tool("colmap")
        if found:
            return str(Path(found).resolve())
    except Exception:
        pass

    # 7. PATH
    for name in _COLMAP_NAMES:
        found = shutil.which(name)
        if found:
            return os.path.abspath(found)

    return None
