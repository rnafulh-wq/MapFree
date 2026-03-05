"""Tests for the updated mapfree.utils.dependency_check (DependencyStatus + check_all_dependencies)."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from mapfree.utils.dependency_check import (
    DependencyStatus,
    _load_cache,
    _save_cache,
    check_all_dependencies,
    invalidate_cache,
)


# ─── DependencyStatus ────────────────────────────────────────────────────────


class TestDependencyStatus:
    def test_to_dict_round_trip(self):
        ds = DependencyStatus(
            available=True, version="1.2.3", path="/usr/bin/colmap",
            install_hint="brew install colmap", critical=True,
        )
        d = ds.to_dict()
        restored = DependencyStatus.from_dict(d)
        assert restored.available is True
        assert restored.version == "1.2.3"
        assert restored.critical is True

    def test_from_dict_defaults(self):
        ds = DependencyStatus.from_dict({})
        assert ds.available is False
        assert ds.version is None
        assert ds.critical is False

    def test_unavailable_status(self):
        ds = DependencyStatus(available=False, install_hint="pip install x")
        assert not ds.available
        assert ds.path is None


# ─── cache helpers ───────────────────────────────────────────────────────────


class TestCache:
    def test_save_and_load_roundtrip(self, tmp_path):
        cache_file = tmp_path / "dep_cache.json"
        results = {
            "colmap": DependencyStatus(available=True, version="3.9", path="/bin/colmap", critical=True),
            "pdal": DependencyStatus(available=False, install_hint="conda install pdal"),
        }
        with patch("mapfree.utils.dependency_check._CACHE_PATH", cache_file):
            _save_cache(results)
            loaded = _load_cache()

        assert loaded is not None
        assert "colmap" in loaded
        assert loaded["colmap"].available is True
        assert loaded["colmap"].version == "3.9"
        assert loaded["pdal"].available is False

    def test_expired_cache_returns_none(self, tmp_path):
        cache_file = tmp_path / "dep_cache.json"
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        cache_file.write_text(
            json.dumps({"cached_at": past, "results": {}})
        )
        with patch("mapfree.utils.dependency_check._CACHE_PATH", cache_file):
            assert _load_cache() is None

    def test_no_cache_file_returns_none(self, tmp_path):
        with patch("mapfree.utils.dependency_check._CACHE_PATH", tmp_path / "missing.json"):
            assert _load_cache() is None

    def test_invalidate_deletes_file(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("{}")
        with patch("mapfree.utils.dependency_check._CACHE_PATH", cache_file):
            invalidate_cache()
        assert not cache_file.exists()

    def test_invalidate_cache_unlink_raises_handled(self):
        """invalidate_cache does not raise when unlink fails (e.g. permission)."""
        mock_path = MagicMock()
        mock_path.is_file.return_value = True
        mock_path.unlink.side_effect = OSError("Permission denied")
        with patch("mapfree.utils.dependency_check._CACHE_PATH", mock_path):
            invalidate_cache()
        mock_path.unlink.assert_called_once()

    def test_save_cache_handles_write_error(self, tmp_path):
        """_save_cache does not raise when write fails (e.g. permission)."""
        results = {"colmap": DependencyStatus(available=True, critical=True)}
        mock_path = MagicMock()
        mock_path.parent.mkdir = MagicMock()
        mock_path.write_text.side_effect = OSError("Permission denied")
        with patch("mapfree.utils.dependency_check._CACHE_PATH", mock_path):
            _save_cache(results)
        mock_path.write_text.assert_called_once()

    def test_load_cache_invalid_json_returns_none(self, tmp_path):
        """_load_cache returns None when cache file content is invalid."""
        cache_file = tmp_path / "bad.json"
        cache_file.write_text("not valid json {")
        with patch("mapfree.utils.dependency_check._CACHE_PATH", cache_file):
            assert _load_cache() is None

    def test_load_cache_tz_naive_cached_at_accepts(self, tmp_path):
        """_load_cache accepts cached_at without timezone (replaces with UTC)."""
        cache_file = tmp_path / "cache.json"
        now_naive = datetime.now(timezone.utc).isoformat().replace("+00:00", "")
        cache_file.write_text(
            json.dumps({
                "cached_at": now_naive,
                "results": {"colmap": {"available": True, "version": "3.8", "path": None,
                                       "install_hint": "", "critical": True}},
            })
        )
        with patch("mapfree.utils.dependency_check._CACHE_PATH", cache_file):
            loaded = _load_cache()
        assert loaded is not None
        assert "colmap" in loaded
        assert loaded["colmap"].available is True


# ─── check_all_dependencies ──────────────────────────────────────────────────


class TestCheckAllDependencies:
    def test_returns_expected_keys(self, tmp_path):
        """check_all_dependencies returns dict with colmap and OpenMVS tools."""
        with (
            patch("mapfree.utils.dependency_check._CACHE_PATH", tmp_path / "cache.json"),
            patch("mapfree.utils.dependency_check._load_cache", return_value=None),
            patch("shutil.which", return_value=None),  # all missing
        ):
            results = check_all_dependencies()

        expected_keys = {"colmap", "DensifyPointCloud", "ReconstructMesh", "TextureMesh",
                         "pdal", "gdalinfo"}
        assert expected_keys.issubset(results.keys())

    def test_colmap_is_critical(self, tmp_path):
        with (
            patch("mapfree.utils.dependency_check._CACHE_PATH", tmp_path / "cache.json"),
            patch("mapfree.utils.dependency_check._load_cache", return_value=None),
            patch("shutil.which", return_value=None),
        ):
            results = check_all_dependencies()
        assert results["colmap"].critical is True

    def test_openmvs_not_critical(self, tmp_path):
        with (
            patch("mapfree.utils.dependency_check._CACHE_PATH", tmp_path / "cache.json"),
            patch("mapfree.utils.dependency_check._load_cache", return_value=None),
            patch("shutil.which", return_value=None),
        ):
            results = check_all_dependencies()
        assert results["DensifyPointCloud"].critical is False

    def test_cache_hit_skips_subprocess(self, tmp_path):
        """Cached results should be returned without running subprocesses."""
        cached = {
            "colmap": DependencyStatus(available=True, version="3.8", critical=True),
        }
        with patch("mapfree.utils.dependency_check._load_cache", return_value=cached):
            with patch("subprocess.run") as mock_run:
                results = check_all_dependencies()
        mock_run.assert_not_called()
        assert results["colmap"].available is True

    def test_colmap_found_on_path(self, tmp_path):
        with (
            patch("mapfree.utils.dependency_check._CACHE_PATH", tmp_path / "cache.json"),
            patch("mapfree.utils.dependency_check._load_cache", return_value=None),
            patch("shutil.which", return_value="/usr/bin/colmap"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout="COLMAP 3.9", stderr=""
            )
            results = check_all_dependencies()
        assert results["colmap"].available is True
        assert results["colmap"].path == "/usr/bin/colmap"

    def test_check_external_tools_success_logs(self):
        """When tools are found and run OK, check_external_tools does not raise."""
        from mapfree.utils.dependency_check import check_external_tools
        with (
            patch("shutil.which", return_value="/usr/bin/pdal"),
            patch("mapfree.utils.dependency_check._run_version", return_value=(True, "2.0.0")),
        ):
            check_external_tools(["pdal"])

    def test_check_geospatial_dependencies_success(self):
        """When PDAL/GDAL are found, check_geospatial_dependencies does not raise."""
        from mapfree.utils.dependency_check import check_geospatial_dependencies
        with (
            patch("shutil.which", return_value="/usr/bin/pdal"),
            patch("mapfree.utils.dependency_check._run_version", return_value=(True, "OK")),
        ):
            check_geospatial_dependencies()
