"""Tests for mapfree.application.setup_state (skip setup dialog when complete)."""

import json
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from mapfree.application.setup_state import (
    load_setup_state,
    save_setup_state,
    should_skip_dependency_dialog,
)


def _status(available: bool, path: str = None, version: str = None):
    return MagicMock(available=available, path=path, version=version)


def test_show_dialog_if_no_flag_file(tmp_path):
    """When setup_complete.json is missing, do not skip dialog."""
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", tmp_path / "setup_complete.json"):
        assert should_skip_dependency_dialog() is False


def test_show_dialog_if_colmap_missing(tmp_path):
    """When completed=true but colmap.found=false, do not skip dialog."""
    path = tmp_path / "setup_complete.json"
    path.write_text(json.dumps({
        "completed": True,
        "checked_at": "2026-03-06T10:00:00Z",
        "dependencies": {
            "colmap": {"found": False},
            "openmvs": {"found": False},
            "pdal": {"found": False},
            "gdal": {"found": False},
        },
    }), encoding="utf-8")
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", path):
        assert should_skip_dependency_dialog() is False


def test_skip_dialog_if_setup_complete(tmp_path):
    """When file exists with completed=true and colmap.found=true and recent, skip dialog."""
    path = tmp_path / "setup_complete.json"
    path.write_text(json.dumps({
        "completed": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "colmap": {"found": True, "path": "C:/colmap/colmap.exe", "version": "3.9"},
            "openmvs": {"found": False},
            "pdal": {"found": False},
            "gdal": {"found": False},
        },
    }), encoding="utf-8")
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", path):
        assert should_skip_dependency_dialog() is True


def test_flag_written_after_successful_setup(tmp_path):
    """save_setup_state writes completed=true when colmap is found."""
    path = tmp_path / "setup_complete.json"
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", path):
        results = {"colmap": _status(True, "C:/colmap/colmap.exe", "3.9")}
        save_setup_state(results)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["completed"] is True
    assert data["dependencies"]["colmap"]["found"] is True
    assert "checked_at" in data


def test_flag_written_incomplete_when_colmap_missing(tmp_path):
    """save_setup_state writes completed=false when colmap not found."""
    path = tmp_path / "setup_complete.json"
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", path):
        results = {"colmap": _status(False)}
        save_setup_state(results)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["completed"] is False
    assert data["dependencies"]["colmap"]["found"] is False


def test_recheck_after_7_days(tmp_path):
    """When file is older than 7 days, skip only if recheck_results has colmap."""
    path = tmp_path / "setup_complete.json"
    path.write_text(json.dumps({
        "completed": True,
        "checked_at": "2020-01-01T00:00:00Z",
        "dependencies": {"colmap": {"found": True}, "openmvs": {}, "pdal": {}, "gdal": {}},
    }), encoding="utf-8")
    # Make file old by setting mtime
    old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).timestamp()
    path.touch()
    os.utime(path, (old_ts, old_ts))
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", path):
        assert should_skip_dependency_dialog() is False
        assert should_skip_dependency_dialog(recheck_results={"colmap": _status(True)}) is True
        assert should_skip_dependency_dialog(recheck_results={"colmap": _status(False)}) is False


def test_load_setup_state_missing(tmp_path):
    """load_setup_state returns None when file does not exist."""
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", tmp_path / "nonexistent.json"):
        assert load_setup_state() is None


def test_load_setup_state_invalid_json(tmp_path):
    """load_setup_state returns None when file is invalid JSON."""
    path = tmp_path / "setup_complete.json"
    path.write_text("not json", encoding="utf-8")
    with patch("mapfree.application.setup_state.SETUP_COMPLETE_PATH", path):
        assert load_setup_state() is None
