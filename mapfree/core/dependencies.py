"""
Resolve paths to optional external tools (GDAL/PDAL) for geospatial stages.

Uses the same idea as find_colmap_executable(): check PATH first, then
search in the mapfree_engine conda environment so MapFree (running in base)
can find tools installed in mapfree_engine.
"""
import shutil
import sys
from pathlib import Path
from typing import Optional

_GDAL_PDAL_TOOLS = [
    "gdalinfo",
    "gdal_translate",
    "gdal_grid",
    "gdalwarp",
    "pdal",
]


def _mapfree_engine_search_dirs() -> list[Path]:
    """Return directories to search for GDAL/PDAL in mapfree_engine conda env."""
    home = Path.home()
    candidates = [
        home / "miniconda3" / "envs" / "mapfree_engine",
        home / "anaconda3" / "envs" / "mapfree_engine",
    ]
    for base in candidates:
        if base.exists():
            if sys.platform == "win32":
                return [
                    base / "Library" / "bin",
                    base / "bin",
                    base / "Scripts",
                ]
            return [base / "bin"]
    if sys.platform == "win32":
        base = home / "miniconda3" / "envs" / "mapfree_engine"
        return [
            base / "Library" / "bin",
            base / "bin",
            base / "Scripts",
        ]
    return [home / "miniconda3" / "envs" / "mapfree_engine" / "bin"]


def find_gdal_tools() -> dict[str, Optional[str]]:
    """
    Resolve paths for gdalinfo, gdal_translate, gdal_grid, gdalwarp, pdal.

    Checks PATH first, then mapfree_engine conda env (Library/bin, bin, Scripts
    on Windows; bin on Linux/macOS). Returns dict mapping tool name to absolute
    path string or None if not found.
    """
    result: dict[str, Optional[str]] = {}
    search_dirs = _mapfree_engine_search_dirs()
    suffix = ".exe" if sys.platform == "win32" else ""

    for tool in _GDAL_PDAL_TOOLS:
        found = shutil.which(tool)
        if found:
            result[tool] = str(Path(found).resolve())
            continue
        for d in search_dirs:
            if not d.exists():
                continue
            candidate = d / (tool + suffix)
            if candidate.is_file():
                result[tool] = str(candidate.resolve())
                break
        else:
            result[tool] = None
    return result
