"""Tests for mapfree.utils.colmap_finder.find_colmap_executable."""

from unittest.mock import patch

from mapfree.utils.colmap_finder import find_colmap_executable


def test_find_colmap_not_found_returns_none():
    """When no COLMAP anywhere, returns None."""
    # Empty PATH so which() finds nothing; keep HOME for path_manager import
    with patch.dict("os.environ", {"PATH": "", "MAPFREE_COLMAP": "", "MAPFREE_COLMAP_PATH": ""}, clear=False), \
         patch("mapfree.core.config.get_config", return_value={}), \
         patch("mapfree.utils.path_manager.PathManager.get_dep_path", return_value=None), \
         patch("sys.platform", "linux"):
        import mapfree.utils.colmap_finder as m
        with patch.object(m, "_extra_dirs", return_value=[]), \
             patch.object(m, "_default_windows", return_value=[]):
            result = find_colmap_executable()
    assert result is None


def test_find_colmap_in_path(tmp_path):
    """When colmap is on PATH (shutil.which), returns that path."""
    fake_colmap = tmp_path / "colmap.exe"
    fake_colmap.touch()
    path_val = str(fake_colmap.parent)
    with patch.dict("os.environ", {"PATH": path_val, "MAPFREE_COLMAP": "", "MAPFREE_COLMAP_PATH": ""}, clear=False), \
         patch("mapfree.core.config.get_config", return_value={}), \
         patch("mapfree.utils.path_manager.PathManager.get_dep_path", return_value=None), \
         patch("sys.platform", "linux"):
        import mapfree.utils.colmap_finder as m
        with patch.object(m, "_extra_dirs", return_value=[]), \
             patch.object(m, "_default_windows", return_value=[]):
            result = find_colmap_executable()
    assert result is not None
    assert result == str(fake_colmap.resolve())


def test_find_colmap_in_registry(tmp_path):
    """When deps_registry has colmap path, returns that path."""
    colmap_exe = tmp_path / "colmap.exe"
    colmap_exe.touch()
    with patch.dict("os.environ", {"PATH": "", "MAPFREE_COLMAP": "", "MAPFREE_COLMAP_PATH": ""}, clear=False), \
         patch("mapfree.core.config.get_config", return_value={}), \
         patch("mapfree.utils.path_manager.PathManager.get_dep_path", return_value=colmap_exe), \
         patch("sys.platform", "linux"):
        import mapfree.utils.colmap_finder as m
        with patch.object(m, "_extra_dirs", return_value=[]), \
             patch.object(m, "_default_windows", return_value=[]):
            result = find_colmap_executable()
    assert result == str(colmap_exe)


def test_find_colmap_env_override(tmp_path):
    """When MAPFREE_COLMAP is set and valid, returns that path."""
    custom = tmp_path / "my_colmap.exe"
    custom.touch()
    with patch.dict("os.environ", {"MAPFREE_COLMAP": str(custom)}, clear=False):
        result = find_colmap_executable()
    assert result == str(custom.resolve())


def test_find_colmap_in_default_dirs_win32(tmp_path):
    """On Windows, default dirs are checked; if colmap.exe exists there, return it."""
    colmap_exe = tmp_path / "colmap.exe"
    colmap_exe.touch()
    with patch.dict("os.environ", {"PATH": "", "MAPFREE_COLMAP": "", "MAPFREE_COLMAP_PATH": ""}, clear=False), \
         patch("mapfree.core.config.get_config", return_value={}), \
         patch("mapfree.utils.path_manager.PathManager.get_dep_path", return_value=None), \
         patch("sys.platform", "win32"):
        import mapfree.utils.colmap_finder as m
        with patch.object(m, "_extra_dirs", return_value=[]), \
             patch.object(m, "_default_windows", return_value=[colmap_exe]):
            result = find_colmap_executable()
    assert result is not None
    assert result == str(colmap_exe.resolve())
