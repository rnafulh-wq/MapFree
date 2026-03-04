"""Tests for mapfree.engines.inspection.profile.ProfileEngine."""
import numpy as np
import pytest

from mapfree.engines.inspection.profile import ProfileEngine


def _flat_mesh_at_z1():
    """Flat horizontal mesh at z=1 over [0,2]x[0,2]."""
    vertices = np.array([
        [0.0, 0.0, 1.0],
        [2.0, 0.0, 1.0],
        [2.0, 2.0, 1.0],
        [0.0, 2.0, 1.0],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)
    return vertices, faces


class TestProfileEngine:
    def setup_method(self):
        self.engine = ProfileEngine()
        self.vertices, self.faces = _flat_mesh_at_z1()

    def test_basic_profile(self):
        """Profile along flat mesh should give elevations ≈ 1.0."""
        line_points = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        result = self.engine.extract_profile(self.vertices, self.faces, line_points, 0.25)
        assert "distances" in result
        assert "elevations" in result
        valid = np.isfinite(result["elevations"])
        assert np.all(result["elevations"][valid] == pytest.approx(1.0, abs=0.01))

    def test_result_keys(self):
        line_points = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        result = self.engine.extract_profile(self.vertices, self.faces, line_points, 0.5)
        for key in ("distances", "elevations", "points", "value", "unit", "method", "precision"):
            assert key in result
        assert result["unit"] == "meter"
        assert result["method"] == "profile_extraction"

    def test_invalid_sampling_distance(self):
        line_points = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        with pytest.raises(ValueError):
            self.engine.extract_profile(self.vertices, self.faces, line_points, 0.0)

    def test_insufficient_line_points(self):
        line_points = np.array([[0.5, 0.5, 0.0]], dtype=np.float64)
        with pytest.raises(ValueError):
            self.engine.extract_profile(self.vertices, self.faces, line_points, 0.25)

    def test_invalid_mesh_vertices(self):
        verts_bad = np.zeros((3, 2))
        line_points = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        with pytest.raises(ValueError):
            self.engine.extract_profile(verts_bad, self.faces, line_points, 0.25)

    def test_distances_monotonically_increasing(self):
        line_points = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        result = self.engine.extract_profile(self.vertices, self.faces, line_points, 0.1)
        dists = result["distances"]
        assert np.all(np.diff(dists) >= 0)

    def test_multipoint_line(self):
        """Three-point polyline."""
        line_points = np.array([
            [0.5, 0.5, 0.0],
            [1.0, 0.5, 0.0],
            [1.5, 0.5, 0.0],
        ], dtype=np.float64)
        result = self.engine.extract_profile(self.vertices, self.faces, line_points, 0.2)
        assert result["distances"].shape == result["elevations"].shape
