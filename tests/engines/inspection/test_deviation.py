"""Tests for mapfree.engines.inspection.deviation.SurfaceDeviationEngine."""
import numpy as np
import pytest

from mapfree.engines.inspection.deviation import SurfaceDeviationEngine, _closest_point_on_triangle


# Simple reference mesh: flat z=0 over [0,2]x[0,2]
REF_VERTS = np.array([
    [0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0],
], dtype=np.float64)
REF_FACES = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)


class TestClosestPointOnTriangle:
    def setup_method(self):
        self.t0 = np.array([0.0, 0.0, 0.0])
        self.t1 = np.array([1.0, 0.0, 0.0])
        self.t2 = np.array([0.0, 1.0, 0.0])

    def test_point_inside(self):
        p = np.array([0.25, 0.25, 0.0])
        q = _closest_point_on_triangle(p, self.t0, self.t1, self.t2)
        assert np.allclose(q, p, atol=1e-10)

    def test_point_above(self):
        """Point directly above center of triangle."""
        p = np.array([0.25, 0.25, 1.0])
        q = _closest_point_on_triangle(p, self.t0, self.t1, self.t2)
        assert np.allclose(q, [0.25, 0.25, 0.0], atol=1e-10)

    def test_point_outside_clamped(self):
        """Point outside triangle — clamps to nearest vertex/edge."""
        p = np.array([-1.0, -1.0, 0.0])
        q = _closest_point_on_triangle(p, self.t0, self.t1, self.t2)
        # Should be close to t0 (origin)
        assert np.linalg.norm(q - self.t0) < 0.1


class TestSurfaceDeviationEngine:
    def test_zero_deviation(self):
        """Target same as reference → deviation ≈ 0."""
        engine = SurfaceDeviationEngine(use_parallel=False)
        result = engine.compute_deviation(REF_VERTS, REF_FACES, REF_VERTS, REF_FACES)
        assert np.allclose(result["deviations"], 0.0, atol=0.01)
        assert result["statistics"]["mean"] == pytest.approx(0.0, abs=0.01)

    def test_constant_offset(self):
        """Target is +0.1m above reference → mean deviation ≈ 0.1."""
        target_verts = REF_VERTS + np.array([0, 0, 0.1])
        engine = SurfaceDeviationEngine(use_parallel=False)
        result = engine.compute_deviation(REF_VERTS, REF_FACES, target_verts, REF_FACES)
        assert np.allclose(result["deviations"], 0.1, atol=0.01)
        assert result["statistics"]["mean"] == pytest.approx(0.1, abs=0.01)

    def test_empty_target(self):
        """Empty target → deviations empty, stats NaN."""
        empty_verts = np.zeros((0, 3), dtype=np.float64)
        engine = SurfaceDeviationEngine(use_parallel=False)
        result = engine.compute_deviation(REF_VERTS, REF_FACES, empty_verts, REF_FACES)
        assert result["deviations"].shape == (0,)
        assert np.isnan(result["value"])

    def test_result_keys(self):
        engine = SurfaceDeviationEngine(use_parallel=False)
        result = engine.compute_deviation(REF_VERTS, REF_FACES, REF_VERTS, REF_FACES)
        for key in ("deviations", "statistics", "value", "unit", "method"):
            assert key in result
        assert result["unit"] == "meter"
        assert result["method"] == "surface_deviation"

    def test_invalid_ref_shape(self):
        engine = SurfaceDeviationEngine(use_parallel=False)
        with pytest.raises(ValueError):
            engine.compute_deviation(np.zeros((3, 2)), np.zeros((1, 3), dtype=np.intp), REF_VERTS, REF_FACES)

    def test_invalid_faces_ref_shape(self):
        engine = SurfaceDeviationEngine(use_parallel=False)
        with pytest.raises(ValueError):
            engine.compute_deviation(REF_VERTS, np.zeros((1, 2), dtype=np.intp), REF_VERTS, REF_FACES)

    def test_invalid_target_shape(self):
        engine = SurfaceDeviationEngine(use_parallel=False)
        with pytest.raises(ValueError):
            engine.compute_deviation(REF_VERTS, REF_FACES, np.zeros((3, 2)), REF_FACES)

    def test_parallel_mode_matches_sequential(self):
        target_verts = REF_VERTS + np.array([0, 0, 0.05])
        engine_seq = SurfaceDeviationEngine(use_parallel=False)
        engine_par = SurfaceDeviationEngine(use_parallel=True, max_workers=2)
        r_seq = engine_seq.compute_deviation(REF_VERTS, REF_FACES, target_verts, REF_FACES)
        r_par = engine_par.compute_deviation(REF_VERTS, REF_FACES, target_verts, REF_FACES)
        assert np.allclose(r_seq["deviations"], r_par["deviations"], atol=0.001)
