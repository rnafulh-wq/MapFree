"""
Resolve paths to optional external tools (GDAL/PDAL) for geospatial stages.

Portable single-env: tools are found in the current Python environment first
(sys.executable), then PATH. No hardcoded user or env names.
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


def find_tool(name: str) -> Optional[str]:
    """
    Resolve path to a binary: PATH first, then current Python environment.

    When MapFree runs inside mapfree_engine conda env, tools (gdalinfo, pdal, ...)
    live in that env's Library/bin or Scripts; this finds them without relying
    on user-specific paths (e.g. C:\\Users\\ryan\\...).
    """
    found = shutil.which(name)
    if found:
        return str(Path(found).resolve())

    # Search in the environment of the running Python (e.g. mapfree_engine)
    # sys.executable = .../mapfree_engine/python.exe or .../Scripts/python.exe
    python_exe = Path(sys.executable).resolve()
    python_dir = python_exe.parent
    search_dirs = [
        python_dir,
        python_dir / "Scripts",
        python_dir.parent / "Library" / "bin",
        python_dir / "Library" / "bin",
    ]
    exts = ["", ".exe", ".bat"] if sys.platform == "win32" else [""]
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in exts:
            candidate = d / (name + ext)
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def find_gdal_tools() -> dict[str, Optional[str]]:
    """
    Resolve paths for gdalinfo, gdal_translate, gdal_grid, gdalwarp, pdal.

    Uses find_tool() so the current Python env (single-install mapfree_engine)
    is searched; no dependency on conda env name or user home.
    """
    result: dict[str, Optional[str]] = {}
    for tool in _GDAL_PDAL_TOOLS:
        result[tool] = find_tool(tool)
    return result
