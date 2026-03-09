"""Tests for mapfree.engines.inspection.crs_transform.CRSTransformer."""
import numpy as np
import pytest

from mapfree.engines.inspection.crs_transform import CRSTransformer, _PYPROJ_AVAILABLE


# ─── Tests that run regardless of pyproj ─────────────────────────────────────

class TestCRSTransformerNoPyproj:
    """Tests that verify behaviour when pyproj is NOT available."""

    def test_transform_raises_without_pyproj(self, monkeypatch):
        monkeypatch.setattr("mapfree.engines.inspection.crs_transform._PYPROJ_AVAILABLE", False)
        pts = np.array([[0.0, 0.0]], dtype=np.float64)
        with pytest.raises(RuntimeError, match="pyproj"):
            CRSTransformer.transform_points(pts, 4326, 32648)

    def test_validate_raises_without_pyproj(self, monkeypatch):
        monkeypatch.setattr("mapfree.engines.inspection.crs_transform._PYPROJ_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="pyproj"):
            CRSTransformer.validate_epsg(4326)

    def test_invalid_points_shape_raises(self, monkeypatch):
        """Shape validation should run before pyproj call."""
        # even with pyproj available, bad shape raises ValueError
        if not _PYPROJ_AVAILABLE:
            pytest.skip("pyproj not installed — shape error raised after pyproj check")
        pts = np.array([[1.0, 2.0, 3.0, 4.0]], dtype=np.float64)
        with pytest.raises(ValueError):
            CRSTransformer.transform_points(pts, 4326, 32648)


# ─── Tests that require pyproj ────────────────────────────────────────────────

@pytest.mark.skipif(not _PYPROJ_AVAILABLE, reason="pyproj not installed")
class TestCRSTransformerWithPyproj:
    def test_transform_2d_points(self):
        pts = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float64)
        result = CRSTransformer.transform_points(pts, 4326, 4326)
        assert result.shape == (2, 3)

    def test_transform_3d_points_preserves_z(self):
        pts = np.array([[0.0, 0.0, 42.0]], dtype=np.float64)
        result = CRSTransformer.transform_points(pts, 4326, 4326)
        assert result[0, 2] == pytest.approx(42.0)

    def test_validate_epsg_valid(self):
        assert CRSTransformer.validate_epsg(4326) is True

    def test_validate_epsg_invalid(self):
        assert CRSTransformer.validate_epsg(99999999) is False

    def test_transform_identity(self):
        """Transform from EPSG to same EPSG → coordinates unchanged."""
        pts = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float64)
        result = CRSTransformer.transform_points(pts, 4326, 4326)
        assert result.shape == (2, 3)
        assert np.allclose(result[:, 0], pts[:, 0], atol=1e-6)
        assert np.allclose(result[:, 1], pts[:, 1], atol=1e-6)
