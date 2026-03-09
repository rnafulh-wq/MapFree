"""Tests for mapfree.engines.inspection.volume.VolumeEngine."""
import numpy as np
import pytest

from mapfree.engines.inspection.volume import VolumeEngine, _check_bounds, _check_resolution


class TestCheckBounds:
    def test_valid(self):
        _check_bounds((0.0, 1.0, 0.0, 1.0))  # no exception

    def test_invalid_x(self):
        with pytest.raises(ValueError):
            _check_bounds((1.0, 0.0, 0.0, 1.0))

    def test_invalid_y(self):
        with pytest.raises(ValueError):
            _check_bounds((0.0, 1.0, 1.0, 0.0))


class TestCheckResolution:
    def test_valid(self):
        _check_resolution(0.1)

    def test_zero(self):
        with pytest.raises(ValueError):
            _check_resolution(0.0)

    def test_negative(self):
        with pytest.raises(ValueError):
            _check_resolution(-1.0)

    def test_inf(self):
        with pytest.raises(ValueError):
            _check_resolution(np.inf)


class TestVolumeEngine:
    def setup_method(self):
        self.engine = VolumeEngine()

    def test_flat_surfaces_zero_volume(self):
        """Two identical flat surfaces → net volume ≈ 0."""
        def surface(x, y):
            return np.zeros_like(x)

        result = self.engine.compute_volume_grid(surface, surface, (0.0, 1.0, 0.0, 1.0), 0.1)
        assert result["net_volume"] == pytest.approx(0.0, abs=1e-10)
        assert result["cut_volume"] == pytest.approx(0.0, abs=1e-10)
        assert result["fill_volume"] == pytest.approx(0.0, abs=1e-10)

    def test_constant_offset_fill(self):
        """Surface B is uniformly +1m above surface A → all fill."""
        def surface_a(x, y):
            return np.zeros_like(x)

        def surface_b(x, y):
            return np.ones_like(x)

        result = self.engine.compute_volume_grid(surface_a, surface_b, (0.0, 1.0, 0.0, 1.0), 0.1)
        assert result["fill_volume"] == pytest.approx(1.0, rel=0.01)
        assert result["cut_volume"] == pytest.approx(0.0, abs=1e-10)
        assert result["net_volume"] == pytest.approx(1.0, rel=0.01)

    def test_constant_offset_cut(self):
        """Surface B is uniformly -1m below A → all cut."""
        def surface_a(x, y):
            return np.ones_like(x)

        def surface_b(x, y):
            return np.zeros_like(x)

        result = self.engine.compute_volume_grid(surface_a, surface_b, (0.0, 1.0, 0.0, 1.0), 0.1)
        assert result["cut_volume"] == pytest.approx(1.0, rel=0.01)
        assert result["fill_volume"] == pytest.approx(0.0, abs=1e-10)

    def test_result_dict_keys(self):
        def surface(x, y):
            return np.zeros_like(x)
        result = self.engine.compute_volume_grid(surface, surface, (0.0, 1.0, 0.0, 1.0), 0.5)
        for key in ("cut_volume", "fill_volume", "net_volume", "area", "value", "unit", "precision", "method"):
            assert key in result
        assert result["unit"] == "cubic_meter"
        assert result["method"] == "grid_integration"

    def test_invalid_bounds(self):
        def surface(x, y):
            return np.zeros_like(x)
        with pytest.raises(ValueError):
            self.engine.compute_volume_grid(surface, surface, (1.0, 0.0, 0.0, 1.0), 0.1)

    def test_invalid_resolution(self):
        def surface(x, y):
            return np.zeros_like(x)
        with pytest.raises(ValueError):
            self.engine.compute_volume_grid(surface, surface, (0.0, 1.0, 0.0, 1.0), -0.1)

    def test_tilted_surface_net_volume(self):
        """Exact: int_0^1 int_0^1 (0.5*x + 0.2*y) dx dy = 0.35"""
        def surface_a(x, y):
            return np.zeros_like(np.atleast_1d(x) + np.atleast_1d(y))

        def surface_b(x, y):
            x_ = np.atleast_1d(np.asarray(x, dtype=np.float64))
            y_ = np.atleast_1d(np.asarray(y, dtype=np.float64))
            return 0.5 * x_ + 0.2 * y_

        result = self.engine.compute_volume_grid(surface_a, surface_b, (0.0, 1.0, 0.0, 1.0), 0.05)
        assert result["net_volume"] == pytest.approx(0.35, rel=0.01)
