"""Dependency checker for MapFree — verifies external binaries at startup.

Provides:

* :class:`DependencyStatus` — dataclass describing one dependency.
* :func:`check_all_dependencies` — check COLMAP, OpenMVS, PDAL, GDAL.
* :func:`check_geospatial_dependencies` — legacy; checks PDAL + GDAL only.
* :func:`check_external_tools` — legacy; raw subprocess version check.

Results are cached to ``~/.mapfree/dependency_cache.json`` for 1 hour to
avoid re-probing on every launch.

Typical startup usage::

    from mapfree.utils.dependency_check import check_all_dependencies

    results = check_all_dependencies()
    missing_critical = [
        name for name, s in results.items()
        if s.critical and not s.available
    ]
"""
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_CACHE_PATH = Path.home() / ".mapfree" / "dependency_cache.json"
_CACHE_TTL_SECONDS = 3600  # 1 hour

_OPENMVS_BINARIES = [
    "DensifyPointCloud",
    "ReconstructMesh",
    "TextureMesh",
]


def _find_colmap() -> Optional[str]:
    """Find COLMAP executable via shared colmap_finder (env, config, registry, dirs, PATH)."""
    from mapfree.utils.colmap_finder import find_colmap_executable
    path = find_colmap_executable()
    if path:
        log.info("COLMAP found: %s", path)
    else:
        log.debug("COLMAP not found")
    return path


@dataclass
class DependencyStatus:
    """Status of a single external dependency.

    Attributes:
        available:     Whether the binary was found and executed successfully.
        version:       Version string from ``--version`` output, or ``None``.
        path:          Absolute path to the binary, or ``None``.
        install_hint:  Human-readable install instructions.
        critical:      If ``True``, the application cannot run without this dep.
    """

    available: bool
    version: Optional[str] = None
    path: Optional[str] = None
    install_hint: str = ""
    critical: bool = False

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "version": self.version,
            "path": self.path,
            "install_hint": self.install_hint,
            "critical": self.critical,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DependencyStatus":
        return cls(
            available=bool(d.get("available", False)),
            version=d.get("version"),
            path=d.get("path"),
            install_hint=d.get("install_hint", ""),
            critical=bool(d.get("critical", False)),
        )


__all__ = [
    "DependencyStatus",
    "check_all_dependencies",
    "check_geospatial_dependencies",
    "check_external_tools",
    "invalidate_cache",
]


def check_all_dependencies() -> Dict[str, DependencyStatus]:
    """Check all MapFree external dependencies and return a status dict.

    Results are read from cache (1-hour TTL) when available.

    Checks:

    * ``colmap`` — critical; 3D reconstruction.
    * ``DensifyPointCloud``, ``ReconstructMesh``, ``TextureMesh`` (OpenMVS) —
      non-critical; dense reconstruction.
    * ``pdal``, ``gdalinfo`` — optional; geospatial stages.

    Returns:
        ``dict[name, DependencyStatus]`` for each checked dependency.
    """
    cached = _load_cache()
    if cached is not None:
        return cached

    results: Dict[str, DependencyStatus] = {}

    # --- COLMAP (critical): extended search (registry, PATH, extra dirs) ---
    results["colmap"] = _check_colmap()

    # --- OpenMVS binaries (optional) ---
    for binary in _OPENMVS_BINARIES:
        results[binary] = _check_binary(
            binary,
            version_args=["--version"],
            install_hint=(
                "OpenMVS: https://github.com/cdcseacave/openMVS/releases\n"
                "Windows: place binaries on PATH or set OPENMVS_BIN"
            ),
            critical=False,
        )

    # --- Geospatial (optional) ---
    for cmd, hint in [
        ("pdal", "conda install -c conda-forge pdal  OR  sudo apt install pdal"),
        ("gdalinfo", "conda install -c conda-forge gdal  OR  sudo apt install gdal-bin"),
    ]:
        results[cmd] = _check_binary(
            cmd,
            version_args=["--version"],
            install_hint=hint,
            critical=False,
        )

    _save_cache(results)
    return results


_COLMAP_INSTALL_HINT = (
    "Windows: scripts/install_colmap_windows.md or MapFree First-Run Wizard\n"
    "Linux:   sudo apt install colmap\n"
    "macOS:   brew install colmap"
)


def _check_colmap() -> DependencyStatus:
    """Check COLMAP with extended search (registry, PATH, extra dirs). Log result."""
    found_path = _find_colmap()
    if not found_path:
        return DependencyStatus(
            available=False,
            install_hint=_COLMAP_INSTALL_HINT,
            critical=True,
        )
    ok, version = _run_version(found_path, ["--version"])
    return DependencyStatus(
        available=ok,
        version=version if ok else None,
        path=found_path if ok else None,
        install_hint="" if ok else _COLMAP_INSTALL_HINT,
        critical=True,
    )


def _check_binary(
    name: str,
    version_args: List[str],
    install_hint: str,
    critical: bool,
) -> DependencyStatus:
    """Check a single binary and return its :class:`DependencyStatus`.

    Prefer PathManager registry (MapFree-installed deps) over system PATH.
    """
    try:
        from mapfree.utils.path_manager import PathManager
        reg_path = PathManager.get_dep_path(name)
    except Exception:
        reg_path = None
    if reg_path is not None:
        found_path = str(reg_path)
    else:
        found_path = shutil.which(name)
    if not found_path:
        return DependencyStatus(
            available=False,
            install_hint=install_hint,
            critical=critical,
        )

    ok, version = _run_version(found_path, version_args)
    return DependencyStatus(
        available=ok,
        version=version if ok else None,
        path=found_path if ok else None,
        install_hint="" if ok else install_hint,
        critical=critical,
    )


def _run_version(cmd: str, args: List[str]) -> tuple[bool, str]:
    """Run ``cmd + args`` and return ``(success, first_line_of_output)``.
    On Windows, .bat/.cmd are run via cmd /c so subprocess finds them.
    """
    run_args = [cmd] + args
    if sys.platform == "win32" and (cmd.lower().endswith(".bat") or cmd.lower().endswith(".cmd")):
        run_args = ["cmd", "/c", cmd] + args
    try:
        result = subprocess.run(
            run_args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Many tools write version to stderr (e.g. colmap)
        if result.returncode != 0:
            out = (result.stdout or result.stderr or "").strip()
            detail = out.splitlines()[0] if out else f"exit code {result.returncode}"
            return False, detail
        out = (result.stdout or result.stderr or "").strip()
        version = out.splitlines()[0] if out else cmd
        return True, version
    except FileNotFoundError:
        return False, "not found"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _save_cache(results: Dict[str, DependencyStatus]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "results": {k: v.to_dict() for k, v in results.items()},
        }
        _CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        log.debug("Could not write dependency cache: %s", exc)


def _load_cache() -> Optional[Dict[str, DependencyStatus]]:
    try:
        if not _CACHE_PATH.is_file():
            return None
        # If deps_registry was updated after cache (e.g. wizard just installed COLMAP), re-check
        try:
            from mapfree.utils.path_manager import PathManager
            reg_path = PathManager._registry_path()
            if reg_path.is_file() and reg_path.stat().st_mtime > _CACHE_PATH.stat().st_mtime:
                log.debug("deps_registry.json newer than cache; re-checking dependencies")
                return None
        except Exception:
            pass
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        cached_at_str = raw.get("cached_at", "")
        cached_at = datetime.fromisoformat(cached_at_str)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age > _CACHE_TTL_SECONDS:
            return None
        return {k: DependencyStatus.from_dict(v) for k, v in raw.get("results", {}).items()}
    except Exception:
        return None


def invalidate_cache() -> None:
    """Delete the dependency cache, forcing a fresh check on next call."""
    try:
        if _CACHE_PATH.is_file():
            _CACHE_PATH.unlink()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Legacy functions (kept for backward compatibility)
# ---------------------------------------------------------------------------

_DEFAULT_TOOLS = ["pdal", "gdalinfo", "gdalwarp"]
_VERSION_ARGS: dict = {
    "pdal": ["--version"],
    "gdalinfo": ["--version"],
    "gdalwarp": ["--version"],
}

_VERSION_CHECKS = [
    ("pdal", ["--version"]),
    ("gdalinfo", ["--version"]),
    ("gdal_grid", ["--version"]),
    ("gdal_translate", ["--version"]),
    ("gdalwarp", ["--version"]),
]


def check_external_tools(tools: Optional[List[str]] = None) -> None:
    """Check that *tools* are available.  Raises :class:`RuntimeError` if any are missing."""
    if tools is None:
        tools = _DEFAULT_TOOLS
    missing = []
    for cmd in tools:
        args = _VERSION_ARGS.get(cmd, ["--version"])
        if not shutil.which(cmd):
            missing.append(cmd)
            continue
        ok, msg = _run_version(cmd, args)
        if not ok:
            missing.append(f"{cmd} ({msg})")
        else:
            log.debug("%s: %s", cmd, msg)

    if missing:
        raise RuntimeError(
            "Required external tools missing or failed: %s\n"
            "Example: conda install -c conda-forge pdal gdal" % ", ".join(missing)
        )


def check_geospatial_dependencies() -> None:
    """Check PDAL + GDAL tools.  Raises :class:`RuntimeError` if missing."""
    missing = []
    for cmd, version_args in _VERSION_CHECKS:
        if not shutil.which(cmd):
            missing.append(cmd)
            continue
        ok, msg = _run_version(cmd, list(version_args))
        if not ok:
            missing.append(f"{cmd} ({msg})")
        else:
            log.debug("%s: %s", cmd, msg)

    if missing:
        raise RuntimeError(
            "Geospatial dependencies missing: %s\n"
            "Example: conda install -c conda-forge pdal gdal" % ", ".join(missing)
        )
