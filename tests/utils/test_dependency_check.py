"""Tests for mapfree.utils.dependency_check."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from mapfree.utils.dependency_check import (
    check_external_tools,
    check_geospatial_dependencies,
    _run_version,
)


class TestRunVersion:
    def test_success(self):
        ok, msg = _run_version("python", ["--version"])
        assert ok is True
        assert "Python" in msg or len(msg) > 0

    def test_not_found(self):
        ok, msg = _run_version("nonexistent_binary_xyz_test", ["--version"])
        assert ok is False
        assert "not found" in msg

    def test_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            ok, msg = _run_version("any_cmd", ["--version"])
        assert ok is False
        assert "timeout" in msg

    def test_generic_exception(self):
        with patch("subprocess.run", side_effect=OSError("some error")):
            ok, msg = _run_version("any_cmd", ["--version"])
        assert ok is False
        assert "some error" in msg

    def test_nonzero_exit(self):
        mock = MagicMock()
        mock.returncode = 1
        mock.stdout = ""
        mock.stderr = ""
        with patch("subprocess.run", return_value=mock):
            ok, msg = _run_version("cmd", ["--version"])
        assert ok is False
        assert "exit code 1" in msg


class TestCheckExternalTools:
    def test_all_missing_raises(self):
        """If shutil.which returns None for all tools, RuntimeError is raised."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="missing or failed"):
                check_external_tools(["pdal", "gdalinfo"])

    def test_tools_present_no_error(self):
        """If all tools are found and return 0, no exception."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.0.0"
        mock_result.stderr = ""
        with patch("shutil.which", return_value="/usr/bin/pdal"), \
             patch("subprocess.run", return_value=mock_result):
            check_external_tools(["pdal"])  # no exception

    def test_custom_tools_list(self):
        """Custom tools list: only check specified tools."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc:
                check_external_tools(["custom_tool_xyz"])
        assert "custom_tool_xyz" in str(exc.value)

    def test_default_tools_missing(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError):
                check_external_tools()


class TestCheckGeospatialDependencies:
    def test_all_missing_raises(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="Geospatial dependencies"):
                check_geospatial_dependencies()

    def test_partial_missing_raises(self):
        """Even if pdal found, missing others still raises."""
        def which_side_effect(cmd):
            return "/usr/bin/pdal" if cmd == "pdal" else None

        with patch("shutil.which", side_effect=which_side_effect):
            with pytest.raises(RuntimeError):
                check_geospatial_dependencies()
