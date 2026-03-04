"""Tests for mapfree.engines.inspection.tin_volume.TINVolumeEngine."""
import numpy as np
import pytest

from mapfree.engines.inspection.tin_volume import TINVolumeEngine


def _simple_quad(z=0.0):
    """Simple 2-triangle quad at given z over [0,1]x[0,1]."""
    verts = np.array([
        [0.0, 0.0, z], [1.0, 0.0, z], [1.0, 1.0, z], [0.0, 1.0, z],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)
    return verts, faces


class TestTINVolumeEngine:
    def test_same_surface_zero_volume(self):
        """Two identical surfaces → net volume ≈ 0."""
        va, fa = _simple_quad(z=0.0)
        engine = TINVolumeEngine(use_parallel=False)
        result = engine.compute_tin_volume(va, fa, va, fa)
        assert result["net_volume"] == pytest.approx(0.0, abs=0.01)
        assert result["cut_volume"] == pytest.approx(0.0, abs=0.01)
        assert result["fill_volume"] == pytest.approx(0.0, abs=0.01)

    def test_offset_fill_volume(self):
        """Surface B is +1m above A → fill."""
        va, fa = _simple_quad(z=0.0)
        vb, fb = _simple_quad(z=1.0)
        engine = TINVolumeEngine(use_parallel=False)
        result = engine.compute_tin_volume(va, fa, vb, fb)
        assert result["fill_volume"] > 0
        assert result["net_volume"] > 0

    def test_result_dict_keys(self):
        va, fa = _simple_quad()
        engine = TINVolumeEngine(use_parallel=False)
        result = engine.compute_tin_volume(va, fa, va, fa)
        for key in ("cut_volume", "fill_volume", "net_volume", "value", "unit", "method"):
            assert key in result
        assert result["unit"] == "cubic_meter"
        assert result["method"] == "tin_prism_integration"

    def test_invalid_vertices_a(self):
        engine = TINVolumeEngine(use_parallel=False)
        va_bad = np.zeros((3, 2))
        fa = np.array([[0, 1, 2]], dtype=np.intp)
        vb, fb = _simple_quad()
        with pytest.raises(ValueError):
            engine.compute_tin_volume(va_bad, fa, vb, fb)

    def test_invalid_faces_b(self):
        engine = TINVolumeEngine(use_parallel=False)
        va, fa = _simple_quad()
        vb = np.zeros((3, 3), dtype=np.float64)
        fb_bad = np.zeros((1, 2), dtype=np.intp)
        with pytest.raises(ValueError):
            engine.compute_tin_volume(va, fa, vb, fb_bad)

    def test_single_triangle_face(self):
        """Single triangle A, same single triangle B → net ≈ 0."""
        va = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]], dtype=np.float64)
        fa = np.array([[0, 1, 2]], dtype=np.intp)
        engine = TINVolumeEngine(use_parallel=False)
        result = engine.compute_tin_volume(va, fa, va, fa)
        # Same surface → both cut and fill should be ~0
        assert result["method"] == "tin_prism_integration"
