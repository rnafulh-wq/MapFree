"""Unit tests for mapfree.utils.path_manager."""

import json
import os
from unittest.mock import patch

import pytest

from mapfree.utils.path_manager import PathManager


@pytest.fixture
def tmp_registry(tmp_path):
    """Point registry to a temp file."""
    reg_file = tmp_path / "deps_registry.json"
    with patch.object(PathManager, "_registry_path", return_value=reg_file):
        yield reg_file


def test_get_deps_dir_windows():
    with patch("os.name", "nt"):
        d = PathManager.get_deps_dir()
    assert "MapFree" in str(d)
    assert "deps" in str(d)


def test_get_deps_dir_linux():
    with patch("os.name", "posix"):
        d = PathManager.get_deps_dir()
    assert ".mapfree" in str(d)
    assert "deps" in str(d)


def test_register_and_get_dep_path(tmp_registry, tmp_path):
    bin_path = tmp_path / "colmap.exe"
    bin_path.touch()
    PathManager.register_dep("colmap", bin_path)
    assert tmp_registry.is_file()
    data = json.loads(tmp_registry.read_text())
    assert data.get("colmap") == str(bin_path.resolve())
    got = PathManager.get_dep_path("colmap")
    assert got is not None
    assert got.name == "colmap.exe"
    assert PathManager.get_dep_path("nonexistent") is None


def test_get_dep_path_returns_none_when_file_missing(tmp_registry):
    """When registered path does not exist on disk, get_dep_path returns None."""
    with open(tmp_registry, "w", encoding="utf-8") as f:
        json.dump({"colmap": "/nonexistent/path/colmap.exe"}, f)
    assert PathManager.get_dep_path("colmap") is None


def test_inject_to_env_prepends_path(tmp_registry, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "colmap.exe").touch()
    PathManager.register_dep("colmap", bin_dir / "colmap.exe")
    with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=False):
        PathManager.inject_to_env()
        path = os.environ.get("PATH", "")
        assert str(bin_dir) in path
        assert path.startswith(str(bin_dir))


def test_inject_to_env_empty_registry_does_nothing(tmp_registry):
    with patch.dict(os.environ, {"PATH": "/original"}, clear=False):
        PathManager.inject_to_env()
        assert os.environ.get("PATH") == "/original"


def test_add_to_system_path_windows_returns_false_on_posix():
    with patch("os.name", "posix"):
        assert PathManager.add_to_system_path_windows("/some/path") is False
