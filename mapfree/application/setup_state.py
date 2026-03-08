"""Dependency setup state: skip 'Setup Diperlukan' dialog when already verified.

Uses ~/.mapfree/setup_complete.json (merged with first-run wizard data if present).
When completed=true and colmap.found=true, startup skips the dialog; re-checks
if the file is older than 7 days.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

SETUP_COMPLETE_PATH = Path.home() / ".mapfree" / "setup_complete.json"
_MAX_AGE_DAYS = 7


def _deps_from_results(results: dict) -> dict[str, dict[str, Any]]:
    """Build dependencies dict for JSON from check_all_dependencies() results."""
    # results keys: colmap, DensifyPointCloud, ReconstructMesh, TextureMesh, pdal, gdalinfo
    def one(name: str) -> dict:
        s = results.get(name)
        if not s:
            return {"found": False}
        return {
            "found": getattr(s, "available", False),
            "path": getattr(s, "path", None),
            "version": getattr(s, "version", None),
        }

    openmvs_binaries = ("DensifyPointCloud", "ReconstructMesh", "TextureMesh")
    first_openmvs = next(
        (results.get(b) for b in openmvs_binaries
         if results.get(b) and getattr(results.get(b), "available", False)),
        None,
    )
    openmvs_status = (
        {"found": True, "path": getattr(first_openmvs, "path", None),
         "version": getattr(first_openmvs, "version", None)}
        if first_openmvs else {"found": False}
    )

    return {
        "colmap": one("colmap"),
        "openmvs": openmvs_status,
        "pdal": one("pdal"),
        "gdal": one("gdalinfo"),
    }


def load_setup_state() -> Optional[dict[str, Any]]:
    """Load setup_complete.json if present. Returns None on missing/invalid."""
    flag_path = SETUP_COMPLETE_PATH
    log.debug("Looking for setup flag at: %s", flag_path)
    log.debug("Flag exists: %s", flag_path.exists())
    if not flag_path.is_file():
        return None
    try:
        with open(flag_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.debug("Could not load setup state: %s", e)
        return None


def save_setup_state(results: dict) -> None:
    """Write completed, checked_at, and dependencies to setup_complete.json.

    Merges with existing JSON so first-run wizard keys (version, profile, etc.)
    are preserved. Also writes setup_complete, colmap_path, timestamp for
    startup skip logic (skip dialog when file exists and colmap_path valid).
    """
    deps = _deps_from_results(results)
    colmap = deps.get("colmap") or {}
    colmap_found = bool(colmap.get("found"))
    colmap_path = colmap.get("path")
    now = datetime.now(timezone.utc).isoformat()
    data: dict[str, Any] = load_setup_state() or {}
    data["completed"] = colmap_found
    data["checked_at"] = now
    data["dependencies"] = deps
    data["setup_complete"] = colmap_found
    data["colmap_path"] = colmap_path
    data["timestamp"] = now
    flag_path = SETUP_COMPLETE_PATH
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Saving setup state to %s (completed=%s)", flag_path, colmap_found)
    with open(flag_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log.info("Setup state saved (completed=%s) to %s", colmap_found, flag_path)


def _file_age_days() -> Optional[float]:
    """Return age of setup_complete.json in days, or None if missing."""
    if not SETUP_COMPLETE_PATH.is_file():
        return None
    try:
        mtime = SETUP_COMPLETE_PATH.stat().st_mtime
        return (datetime.now(timezone.utc).timestamp() - mtime) / 86400.0
    except OSError:
        return None


def _colmap_path_still_valid(state: dict[str, Any]) -> bool:
    """Return True if saved colmap_path exists and is valid."""
    colmap_path = state.get("colmap_path")
    if not colmap_path:
        colmap_path = (state.get("dependencies") or {}).get("colmap") or {}
        colmap_path = colmap_path.get("path") if isinstance(colmap_path, dict) else None
    if not colmap_path:
        return False
    return Path(colmap_path).exists()


def should_skip_dependency_dialog(
    recheck_results: Optional[dict] = None,
) -> bool:
    """Return True if we can skip the 'Setup Diperlukan' dialog.

    Skip when:
    - setup_complete.json has completed=true and dependencies.colmap.found=true,
    - saved colmap_path still exists (valid),
    - and either file age <= 7 days, or recheck_results is provided and colmap found.

    When recheck_results is provided (e.g. from a re-check because file was old),
    we do not update the file here; the caller should call save_setup_state(recheck_results)
    if they want to refresh the timestamp.
    """
    state = load_setup_state()
    if not state:
        return False
    if not (state.get("completed") or state.get("setup_complete")):
        return False
    deps = state.get("dependencies") or {}
    colmap = deps.get("colmap") or {}
    if not colmap.get("found"):
        return False
    if not _colmap_path_still_valid(state):
        # Fallback: live search in case conda path differs across sessions
        try:
            from mapfree.utils.colmap_finder import find_colmap_executable
            if not find_colmap_executable():
                return False
        except Exception:
            return False
    age = _file_age_days()
    if age is None:
        return False
    if age <= _MAX_AGE_DAYS:
        return True
    # File older than 7 days: use recheck if provided
    if recheck_results is not None:
        colmap_status = recheck_results.get("colmap")
        if colmap_status and getattr(colmap_status, "available", False):
            return True
    return False
