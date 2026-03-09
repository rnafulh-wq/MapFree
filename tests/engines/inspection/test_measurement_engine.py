"""Tests for mapfree.engines.inspection.measurement_engine.MeasurementEngine and CRSManager."""
import numpy as np
import pytest

from mapfree.engines.inspection.crs_manager import CRSManager
from mapfree.engines.inspection.measurement_engine import MeasurementEngine


# ─── helpers ──────────────────────────────────────────────────────────────────

def _flat_mesh():
    """Flat mesh at z=0 over [0,2]x[0,2]."""
    verts = np.array([
        [0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)
    return verts, faces


def _point_cloud():
    rng = np.random.default_rng(0)
    return rng.random((20, 3)).astype(np.float64)


# ─── CRSManager ───────────────────────────────────────────────────────────────

class TestCRSManager:
    def test_default_empty(self):
        crs = CRSManager()
        assert crs.get_crs() == ""
        assert crs.unit() == "meter"
        assert crs.validate_projected() is False

    def test_set_crs_via_init(self):
        crs = CRSManager("32648")
        assert crs.get_crs() == "32648"
        assert crs.validate_projected() is True

    def test_set_crs_method(self):
        crs = CRSManager()
        crs.set_crs("32632")
        assert crs.get_crs() == "32632"

    def test_unit_always_meter(self):
        crs = CRSManager("32648")
        assert crs.unit() == "meter"


# ─── MeasurementEngine ────────────────────────────────────────────────────────

class TestMeasurementEngine:
    def setup_method(self):
        self.engine = MeasurementEngine()
        self.verts, self.faces = _flat_mesh()

    def test_set_mesh(self):
        self.engine.set_mesh(self.verts, self.faces)
        assert self.engine.mesh_vertices is not None
        assert self.engine.mesh_faces is not None

    def test_set_mesh_invalid_verts(self):
        with pytest.raises(ValueError):
            self.engine.set_mesh(np.zeros((3, 2)), np.zeros((1, 3), dtype=np.intp))

    def test_set_mesh_invalid_faces(self):
        with pytest.raises(ValueError):
            self.engine.set_mesh(self.verts, np.zeros((1, 2), dtype=np.intp))

    def test_set_point_cloud(self):
        pc = _point_cloud()
        self.engine.set_point_cloud(pc)
        assert self.engine.point_cloud is not None

    def test_set_point_cloud_invalid(self):
        with pytest.raises(ValueError):
            self.engine.set_point_cloud(np.zeros((5, 2)))

    def test_set_crs(self):
        self.engine.set_crs("32648")
        assert self.engine.crs_manager.get_crs() == "32648"

    def test_measure_distance(self):
        result = self.engine.measure_distance([0, 0, 0], [3, 4, 0])
        assert result.value == pytest.approx(5.0)
        assert result.unit == "meter"
        assert result.method == "distance_3d"

    def test_measure_polyline(self):
        pts = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]
        result = self.engine.measure_polyline(pts)
        assert result.value == pytest.approx(2.0)
        assert result.method == "polyline_length"

    def test_measure_polyline_too_short(self):
        with pytest.raises(ValueError):
            self.engine.measure_polyline([[0, 0, 0]])

    def test_measure_area_polygon_2d(self):
        pts = [[0, 0], [1, 0], [1, 1], [0, 1]]
        result = self.engine.measure_area_polygon_2d(pts)
        assert result.value == pytest.approx(1.0)
        assert result.method == "polygon_area_2d"

    def test_measure_area_polygon_3d(self):
        pts = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        result = self.engine.measure_area_polygon_3d(pts)
        assert result.value == pytest.approx(0.5)
        assert result.method == "polygon_area_3d"

    def test_query_elevation_with_mesh(self):
        """Vertical ray hits flat mesh at z=0 using mocked BVH to avoid slow BVH traversal."""
        from unittest.mock import patch
        self.engine.set_mesh(self.verts, self.faces)
        hit_point = np.array([1.0, 1.0, 0.0], dtype=np.float64)
        with patch.object(self.engine._bvh, "ray_intersect_accelerated", return_value=hit_point):
            result = self.engine.query_elevation(1.0, 1.0)
        assert result.value == pytest.approx(0.0, abs=0.01)
        assert result.method == "query_elevation_mesh"

    def test_query_elevation_no_data_raises(self):
        with pytest.raises(RuntimeError):
            self.engine.query_elevation(1.0, 1.0)

    def test_query_elevation_from_point_cloud(self):
        """Elevation from point cloud nearest neighbor (3D distance)."""
        # KDTree searches in 3D: query at (1,1,0), pc[0]=(1,1,5) dist=5, pc[1]=(10,10,3) dist≈14
        pc = np.array([[1.0, 1.0, 5.0], [10.0, 10.0, 3.0]], dtype=np.float64)
        self.engine.set_point_cloud(pc)
        result = self.engine.query_elevation(1.0, 1.0)
        assert result.value == pytest.approx(5.0, abs=0.1)
        assert result.method == "query_elevation_point_cloud"

    def test_ray_pick_hit(self):
        """Ray directly above mesh center going down should hit."""
        self.engine.set_mesh(self.verts, self.faces)
        # Ray from just above z=0 (mesh is at z=0), going down by 0.5 → hit at z=0
        result = self.engine.ray_pick([1.0, 1.0, 0.5], [0.0, 0.0, -1.0])
        assert result is not None
        assert result.value == pytest.approx(0.5, abs=0.1)
        assert result.method == "ray_pick"

    def test_ray_pick_no_mesh_raises(self):
        with pytest.raises(RuntimeError):
            self.engine.ray_pick([1.0, 1.0, 5.0], [0.0, 0.0, -1.0])

    def test_ray_pick_miss_mocked(self):
        """ray_pick returns None when no intersection (BVH and fallback both miss)."""
        from unittest.mock import patch
        self.engine.set_mesh(self.verts, self.faces)
        with patch.object(self.engine._bvh, "ray_intersect_accelerated", return_value=None), \
             patch("mapfree.engines.inspection.measurement_engine.ray_mesh_intersect", return_value=None):
            result = self.engine.ray_pick([0.0, 0.0, 1.0], [0.0, 0.0, -1.0])
            assert result is None

    def test_extract_profile_requires_mesh(self):
        line_pts = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        with pytest.raises(RuntimeError):
            self.engine.extract_profile(line_pts, 0.25)

    def test_extract_profile_with_mesh(self):
        self.engine.set_mesh(self.verts, self.faces)
        line_pts = np.array([[0.5, 0.5, 0.0], [1.5, 0.5, 0.0]], dtype=np.float64)
        result = self.engine.extract_profile(line_pts, 0.25)
        assert "distances" in result
        assert "elevations" in result

    def test_compute_volume_requires_crs(self):
        """compute_volume raises without CRS."""
        def surf(x, y):
            return np.zeros_like(x)
        with pytest.raises(RuntimeError):
            self.engine.compute_volume(surf, surf, (0.0, 1.0, 0.0, 1.0), 0.1)

    def test_compute_volume_with_crs(self):
        self.engine.set_crs("32648")

        def surf_a(x, y):
            return np.zeros_like(x)

        def surf_b(x, y):
            return np.ones_like(x)

        result = self.engine.compute_volume(surf_a, surf_b, (0.0, 1.0, 0.0, 1.0), 0.1)
        assert result["fill_volume"] == pytest.approx(1.0, rel=0.05)

    def test_save_and_load_session(self, tmp_path):
        measurements = [{"value": 5.0, "unit": "meter", "method": "distance_3d"}]
        path = tmp_path / "session.json"
        self.engine.set_crs("32648")
        save_result = self.engine.save_session(path, measurements, project="test_proj")
        assert save_result["count"] == 1
        load_result = self.engine.load_session(path)
        assert load_result["count"] == 1
        assert load_result["project"] == "test_proj"

    def test_crs_manager_default(self):
        assert self.engine.crs_manager is not None
        assert self.engine.crs_manager.unit() == "meter"
