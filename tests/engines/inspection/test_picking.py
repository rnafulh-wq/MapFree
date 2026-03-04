"""Tests for mapfree.engines.inspection.picking - ray intersection."""
import numpy as np
import pytest

from mapfree.engines.inspection.picking import ray_triangle_intersect, ray_mesh_intersect


# Simple unit triangle in Z=0 plane: v0=(0,0,0), v1=(1,0,0), v2=(0,1,0)
TRIANGLE = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)


class TestRayTriangleIntersect:
    def test_hit_center(self):
        """Ray straight down hitting triangle center."""
        origin = np.array([0.25, 0.25, 1.0])
        direction = np.array([0.0, 0.0, -1.0])
        hit = ray_triangle_intersect(origin, direction, TRIANGLE)
        assert hit is not None
        assert np.allclose(hit, [0.25, 0.25, 0.0], atol=1e-10)

    def test_miss_outside(self):
        """Ray aimed outside triangle — no hit."""
        origin = np.array([2.0, 2.0, 1.0])
        direction = np.array([0.0, 0.0, -1.0])
        hit = ray_triangle_intersect(origin, direction, TRIANGLE)
        assert hit is None

    def test_ray_parallel(self):
        """Ray parallel to triangle plane — no hit."""
        origin = np.array([0.5, 0.5, 0.0])
        direction = np.array([1.0, 0.0, 0.0])
        hit = ray_triangle_intersect(origin, direction, TRIANGLE)
        assert hit is None

    def test_ray_from_behind(self):
        """Ray pointing away — no hit (t <= eps)."""
        origin = np.array([0.25, 0.25, -1.0])
        direction = np.array([0.0, 0.0, -1.0])
        hit = ray_triangle_intersect(origin, direction, TRIANGLE)
        assert hit is None

    def test_invalid_triangle_shape(self):
        """Wrong triangle shape raises ValueError."""
        with pytest.raises(ValueError):
            ray_triangle_intersect([0, 0, 1], [0, 0, -1], [[0, 0, 0], [1, 0, 0]])

    def test_hit_at_vertex(self):
        """Ray hitting exactly at vertex."""
        origin = np.array([0.0, 0.0, 1.0])
        direction = np.array([0.0, 0.0, -1.0])
        hit = ray_triangle_intersect(origin, direction, TRIANGLE)
        assert hit is not None


class TestRayMeshIntersect:
    def setup_method(self):
        """Simple mesh: two triangles forming a Z=0 quad."""
        self.vertices = np.array([
            [0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0],
        ], dtype=np.float64)
        self.faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)

    def test_hit(self):
        hit = ray_mesh_intersect([1.0, 1.0, 2.0], [0.0, 0.0, -1.0], self.vertices, self.faces)
        assert hit is not None
        assert np.allclose(hit[2], 0.0, atol=1e-10)

    def test_miss(self):
        hit = ray_mesh_intersect([5.0, 5.0, 1.0], [0.0, 0.0, -1.0], self.vertices, self.faces)
        assert hit is None

    def test_zero_direction_raises(self):
        with pytest.raises(ValueError):
            ray_mesh_intersect([0, 0, 1], [0, 0, 0], self.vertices, self.faces)

    def test_invalid_vertices_shape(self):
        with pytest.raises(ValueError):
            ray_mesh_intersect([0, 0, 1], [0, 0, -1], [[0, 0], [1, 0]], [[0, 1, 2]])

    def test_invalid_faces_shape(self):
        with pytest.raises(ValueError):
            ray_mesh_intersect([0, 0, 1], [0, 0, -1], self.vertices, [[0, 1]])

    def test_closest_hit_returned(self):
        """Two parallel triangles at z=0 and z=1; should return z=1 (closer)."""
        verts = np.array([
            [0, 0, 0], [2, 0, 0], [1, 2, 0],
            [0, 0, 1], [2, 0, 1], [1, 2, 1],
        ], dtype=np.float64)
        faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.intp)
        hit = ray_mesh_intersect([0.5, 0.5, 5.0], [0, 0, -1], verts, faces)
        assert hit is not None
        assert hit[2] == pytest.approx(1.0, abs=0.1)
