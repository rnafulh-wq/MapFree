"""Tests for mapfree.engines.inspection.spatial_index - KDTreeWrapper and SimpleBVH."""
import numpy as np
import pytest

from mapfree.engines.inspection.spatial_index import KDTreeWrapper, SimpleBVH


# ─── helpers ──────────────────────────────────────────────────────────────────

def _unit_triangle():
    verts = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]], dtype=np.float64)
    faces = np.array([[0, 1, 2]], dtype=np.intp)
    return verts, faces


def _quad_mesh():
    verts = np.array([[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)
    return verts, faces


# ─── KDTreeWrapper ────────────────────────────────────────────────────────────

class TestKDTreeWrapper:
    def test_build_and_nearest(self):
        kd = KDTreeWrapper()
        pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float64)
        kd.build(pts)
        idx, dist = kd.nearest([0.1, 0.0, 0.0])
        assert idx == 0
        assert dist == pytest.approx(0.1, rel=0.01)

    def test_not_built_returns_minus1(self):
        kd = KDTreeWrapper()
        idx, dist = kd.nearest([0.0, 0.0, 0.0])
        assert idx == -1
        assert dist == np.inf

    def test_invalid_shape_raises(self):
        kd = KDTreeWrapper()
        with pytest.raises(ValueError):
            kd.build(np.array([[1, 2], [3, 4]], dtype=np.float64))

    def test_empty_points_raises(self):
        kd = KDTreeWrapper()
        with pytest.raises(ValueError):
            kd.build(np.zeros((0, 3), dtype=np.float64))

    def test_radius_search_finds_points(self):
        kd = KDTreeWrapper()
        pts = np.array([[0, 0, 0], [0.1, 0, 0], [5, 0, 0]], dtype=np.float64)
        kd.build(pts)
        result = kd.radius_search([0, 0, 0], 0.2)
        assert 0 in result
        assert 1 in result
        assert 2 not in result

    def test_radius_search_not_built_returns_empty(self):
        kd = KDTreeWrapper()
        result = kd.radius_search([0, 0, 0], 1.0)
        assert len(result) == 0

    def test_nearest_closest_point(self):
        kd = KDTreeWrapper()
        pts = np.array([[0, 0, 0], [3, 4, 0]], dtype=np.float64)
        kd.build(pts)
        idx, dist = kd.nearest([3.0, 4.0, 0.0])
        assert idx == 1
        assert dist == pytest.approx(0.0, abs=1e-10)

    def test_many_points(self):
        rng = np.random.default_rng(42)
        pts = rng.random((200, 3)).astype(np.float64)
        kd = KDTreeWrapper()
        kd.build(pts)
        idx, dist = kd.nearest([0.5, 0.5, 0.5])
        assert 0 <= idx < 200
        assert dist >= 0.0


# ─── SimpleBVH ────────────────────────────────────────────────────────────────

class TestSimpleBVH:
    def test_hit_single_triangle(self):
        verts, faces = _unit_triangle()
        bvh = SimpleBVH(verts, faces)
        hit = bvh.ray_intersect_accelerated([0.3, 0.3, 1.0], [0, 0, -1.0])
        assert hit is not None
        assert np.allclose(hit[2], 0.0, atol=0.1)

    def test_zero_direction_returns_none(self):
        verts, faces = _unit_triangle()
        bvh = SimpleBVH(verts, faces)
        hit = bvh.ray_intersect_accelerated([0.3, 0.3, 1.0], [0, 0, 0])
        assert hit is None

    def test_quad_mesh_hit(self):
        verts, faces = _quad_mesh()
        bvh = SimpleBVH(verts, faces)
        hit = bvh.ray_intersect_accelerated([1.0, 1.0, 2.0], [0, 0, -1.0])
        assert hit is not None

    def test_invalid_verts_shape(self):
        with pytest.raises(ValueError):
            SimpleBVH(np.zeros((3, 2)), np.zeros((1, 3), dtype=np.intp))

    def test_invalid_faces_shape(self):
        with pytest.raises(ValueError):
            SimpleBVH(np.zeros((3, 3)), np.zeros((1, 2), dtype=np.intp))
