"""
Check availability of external tools (PDAL, GDAL) for geospatial stages.
"""

import shutil
import subprocess
import logging

log = logging.getLogger(__name__)

# Commands to check: (executable, version_args)
_VERSION_CHECKS = [
    ("pdal", ["--version"]),
    ("gdalinfo", ["--version"]),
    ("gdal_grid", ["--version"]),
    ("gdal_translate", "--version"),
    ("gdalwarp", "--version"),
]


def _run_version(cmd: str, args) -> tuple[bool, str]:
    """Run command with version args. Return (success, message)."""
    argv = [cmd] + (args if isinstance(args, list) else [args])
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            out = (result.stdout or result.stderr or "").strip()
            return True, out.splitlines()[0] if out else cmd
        return False, "exit code %s" % result.returncode
    except FileNotFoundError:
        return False, "not found"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def check_geospatial_dependencies() -> None:
    """
    Verify that pdal, gdalinfo, gdal_grid, gdal_translate, gdalwarp are available.
    Raises RuntimeError with a clear message if any are missing.
    """
    missing = []
    for cmd, version_args in _VERSION_CHECKS:
        if not shutil.which(cmd):
            missing.append(cmd)
            continue
        ok, msg = _run_version(cmd, version_args)
        if not ok:
            missing.append("%s (%s)" % (cmd, msg))
        else:
            log.debug("%s: %s", cmd, msg)

    if missing:
        raise RuntimeError(
            "Geospatial dependencies missing or failed. Install PDAL and GDAL and ensure they are on PATH.\n"
            "Missing or failed: %s\n"
            "Example (Ubuntu): sudo apt install pdal gdal-bin\n"
            "Example (conda): conda install -c conda-forge pdal gdal"
            % ", ".join(missing)
        )
