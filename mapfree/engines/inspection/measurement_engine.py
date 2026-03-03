"""
Measurement engine: mesh/point-cloud distance, polyline, area, elevation, ray pick.
Stage 2: volume, profile, optional spatial index. Headless; no UI.
"""
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from mapfree.engines.inspection.models import MeasurementResult
from mapfree.engines.inspection.geometry_utils import (
    distance_3d,
    distance_2d,
    polyline_length,
    polygon_area_2d,
    polygon_area_3d,
)
from mapfree.engines.inspection.crs_manager import CRSManager
from mapfree.engines.inspection.picking import ray_mesh_intersect

logger = logging.getLogger(__name__)


def _as_float64_3(p) -> np.ndarray:
    a = np.asarray(p, dtype=np.float64)
    if a.ndim != 1 or a.size != 3:
        raise ValueError("Expected 1D array of length 3, got shape %s" % (a.shape,))
    return a.reshape(3)


def _as_float64_2(p) -> np.ndarray:
    a = np.asarray(p, dtype=np.float64)
    if a.ndim != 1 or a.size != 2:
        raise ValueError("Expected 1D array of length 2, got shape %s" % (a.shape,))
    return a.reshape(2)


def _as_points_3d(points) -> np.ndarray:
    a = np.asarray(points, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 3:
        raise ValueError("Expected array of shape (N, 3), got %s" % (a.shape,))
    return a


def _as_points_2d(points) -> np.ndarray:
    a = np.asarray(points, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 2:
        raise ValueError("Expected array of shape (N, 2), got %s" % (a.shape,))
    return a


class MeasurementEngine:
    """
    Core measurement engine for mesh and/or point cloud data.
    All methods return MeasurementResult; use CRSManager for units/CRS.
    """

    def __init__(self) -> None:
        self.mesh_vertices: Optional[np.ndarray] = None  # (V, 3) float64
        self.mesh_faces: Optional[np.ndarray] = None    # (F, 3) int
        self.point_cloud: Optional[np.ndarray] = None   # (N, 3) float64
        self.crs_manager = CRSManager()
        self._bvh = None  # Optional SimpleBVH for accelerated ray_mesh
        self._kdtree = None  # Optional KDTreeWrapper for point cloud

    def set_mesh(self, vertices: Union[list, np.ndarray], faces: Union[list, np.ndarray]) -> None:
        """
        Set the mesh for measurements and ray picking.

        Args:
            vertices: (V, 3) float64.
            faces: (F, 3) vertex indices.

        Raises:
            ValueError: If shapes are invalid.
        """
        v = np.asarray(vertices, dtype=np.float64)
        f = np.asarray(faces, dtype=np.intp)
        if v.ndim != 2 or v.shape[1] != 3:
            raise ValueError("vertices must have shape (V, 3), got %s" % (v.shape,))
        if f.ndim != 2 or f.shape[1] != 3:
            raise ValueError("faces must have shape (F, 3), got %s" % (f.shape,))
        self.mesh_vertices = v
        self.mesh_faces = f
        self._bvh = None
        try:
            from mapfree.engines.inspection.spatial_index import SimpleBVH
            self._bvh = SimpleBVH(v, f)
        except Exception:
            self._bvh = None

    def set_point_cloud(self, points: Union[list, np.ndarray]) -> None:
        """
        Set the point cloud for elevation query when no mesh is set.

        Args:
            points: (N, 3) float64.

        Raises:
            ValueError: If shape is not (N, 3).
        """
        p = np.asarray(points, dtype=np.float64)
        if p.ndim != 2 or p.shape[1] != 3:
            raise ValueError("point_cloud must have shape (N, 3), got %s" % (p.shape,))
        self.point_cloud = p
        self._kdtree = None
        try:
            from mapfree.engines.inspection.spatial_index import KDTreeWrapper
            kdt = KDTreeWrapper()
            kdt.build(p)
            self._kdtree = kdt
        except Exception:
            self._kdtree = None

    def set_crs(self, epsg_code: str) -> None:
        """Set the coordinate reference system (EPSG code)."""
        self.crs_manager.set_crs(epsg_code)

    def measure_distance(
        self,
        p1: Union[list, np.ndarray],
        p2: Union[list, np.ndarray],
    ) -> MeasurementResult:
        """
        Measure 3D distance between two points.

        Returns:
            MeasurementResult with value in CRS unit (meter for projected).
        """
        d = distance_3d(p1, p2)
        return MeasurementResult(
            value=float(d),
            unit=self.crs_manager.unit(),
            precision=np.finfo(np.float64).resolution,
            crs=self.crs_manager.get_crs(),
            method="distance_3d",
        )

    def measure_polyline(self, points: Union[list, np.ndarray]) -> MeasurementResult:
        """
        Measure total length of a polyline (3D).

        Returns:
            MeasurementResult with length in CRS unit.
        """
        length = polyline_length(points)
        return MeasurementResult(
            value=float(length),
            unit=self.crs_manager.unit(),
            precision=np.finfo(np.float64).resolution,
            crs=self.crs_manager.get_crs(),
            method="polyline_length",
        )

    def measure_area_polygon_2d(self, points: Union[list, np.ndarray]) -> MeasurementResult:
        """
        Measure area of a 2D polygon (x, y). Uses absolute (unsigned) area.

        Returns:
            MeasurementResult with area in square CRS units.
        """
        area = polygon_area_2d(points)
        return MeasurementResult(
            value=float(area),
            unit=self.crs_manager.unit() + "^2",
            precision=np.finfo(np.float64).resolution,
            crs=self.crs_manager.get_crs(),
            method="polygon_area_2d",
        )

    def measure_area_polygon_3d(self, points: Union[list, np.ndarray]) -> MeasurementResult:
        """
        Measure area of a 3D planar polygon.

        Returns:
            MeasurementResult with area in square CRS units.
        """
        area = polygon_area_3d(points)
        return MeasurementResult(
            value=float(area),
            unit=self.crs_manager.unit() + "^2",
            precision=np.finfo(np.float64).resolution,
            crs=self.crs_manager.get_crs(),
            method="polygon_area_3d",
        )

    def query_elevation(self, x: float, y: float) -> MeasurementResult:
        """
        Query elevation (z) at given (x, y). Uses mesh if set (vertical ray);
        otherwise nearest point in point cloud.

        Returns:
            MeasurementResult with value = z, unit = meter.

        Raises:
            RuntimeError: If neither mesh nor point cloud is set, or no hit/sample.
        """
        x_f = np.float64(x)
        y_f = np.float64(y)
        if self.mesh_vertices is not None and self.mesh_faces is not None:
            verts = self.mesh_vertices
            z_max = np.max(verts[:, 2])
            ray_origin = np.array([x_f, y_f, z_max + 1.0], dtype=np.float64)
            ray_direction = np.array([0.0, 0.0, -1.0], dtype=np.float64)
            hit = None
            if self._bvh is not None:
                hit = self._bvh.ray_intersect_accelerated(ray_origin, ray_direction)
            if hit is None:
                hit = ray_mesh_intersect(
                    ray_origin, ray_direction,
                    self.mesh_vertices, self.mesh_faces,
                )
            if hit is None:
                raise RuntimeError("No mesh intersection at (%.6f, %.6f)" % (x_f, y_f))
            return MeasurementResult(
                value=float(hit[2]),
                unit=self.crs_manager.unit(),
                precision=np.finfo(np.float64).resolution,
                crs=self.crs_manager.get_crs(),
                method="query_elevation_mesh",
            )
        if self.point_cloud is not None and len(self.point_cloud) > 0:
            pc = self.point_cloud
            if self._kdtree is not None:
                idx, _ = self._kdtree.nearest([x_f, y_f, 0.0])
                z = pc[idx, 2]
            else:
                dx = pc[:, 0] - x_f
                dy = pc[:, 1] - y_f
                dist_sq = dx * dx + dy * dy
                idx = np.argmin(dist_sq)
                z = pc[idx, 2]
            return MeasurementResult(
                value=float(z),
                unit=self.crs_manager.unit(),
                precision=np.finfo(np.float64).resolution,
                crs=self.crs_manager.get_crs(),
                method="query_elevation_point_cloud",
            )
        raise RuntimeError("No mesh or point cloud set for elevation query")

    def ray_pick(
        self,
        ray_origin: Union[list, np.ndarray],
        ray_direction: Union[list, np.ndarray],
    ) -> Optional[MeasurementResult]:
        """
        Cast a ray against the mesh; return distance and hit point as measurement.

        Returns:
            MeasurementResult with value = distance from ray_origin to hit, or None if no hit.
        """
        if self.mesh_vertices is None or self.mesh_faces is None:
            raise RuntimeError("No mesh set for ray_pick")
        orig = _as_float64_3(ray_origin)
        direc = _as_float64_3(ray_direction)
        hit = None
        if self._bvh is not None:
            hit = self._bvh.ray_intersect_accelerated(orig, direc)
        if hit is None:
            hit = ray_mesh_intersect(
                orig, direc,
                self.mesh_vertices, self.mesh_faces,
            )
        if hit is None:
            return None
        dist = np.float64(np.linalg.norm(hit - orig))
        return MeasurementResult(
            value=float(dist),
            unit=self.crs_manager.unit(),
            precision=np.finfo(np.float64).resolution,
            crs=self.crs_manager.get_crs(),
            method="ray_pick",
        )

    def compute_volume(
        self,
        surface_a: Callable,
        surface_b: Callable,
        bounds: Tuple[float, float, float, float],
        resolution: float,
    ) -> Dict:
        """
        Compute cut/fill volume between two surfaces over a rectangular domain.
        Surfaces are callables z = f(x, y); x, y can be arrays.

        Args:
            surface_a: First surface elevation callable.
            surface_b: Second surface elevation callable.
            bounds: (xmin, xmax, ymin, ymax).
            resolution: Grid cell spacing.

        Returns:
            Structured dict: cut_volume, fill_volume, net_volume, area, value, unit, precision, method.

        Raises:
            RuntimeError: If CRS is not validated (projected).
        """
        if not self.crs_manager.validate_projected():
            raise RuntimeError("CRS must be set and projected before volume computation")
        from mapfree.engines.inspection.volume import VolumeEngine
        engine = VolumeEngine()
        return engine.compute_volume_grid(surface_a, surface_b, bounds, resolution)

    def extract_profile(
        self,
        line_points: Union[list, np.ndarray],
        sampling_distance: float,
    ) -> Dict:
        """
        Extract elevation profile along a polyline from the current mesh.

        Args:
            line_points: (N, 3) polyline vertices.
            sampling_distance: Step length along the line.

        Returns:
            Structured dict: distances, elevations, points, value, unit, precision, method.

        Raises:
            RuntimeError: If no mesh is set.
        """
        if self.mesh_vertices is None or self.mesh_faces is None:
            raise RuntimeError("Mesh must be set before profile extraction")
        from mapfree.engines.inspection.profile import ProfileEngine
        engine = ProfileEngine()
        return engine.extract_profile(
            self.mesh_vertices,
            self.mesh_faces,
            line_points,
            sampling_distance,
        )

    def compute_tin_volume(
        self,
        vertices_a: Union[list, np.ndarray],
        faces_a: Union[list, np.ndarray],
        vertices_b: Union[list, np.ndarray],
        faces_b: Union[list, np.ndarray],
    ) -> dict:
        """
        Compute cut/fill volume between two TINs (B - A) by prism integration.

        Args:
            vertices_a: (V, 3) reference surface.
            faces_a: (F, 3) reference triangles.
            vertices_b: (V, 3) comparison surface.
            faces_b: (F, 3) comparison triangles.

        Returns:
            Structured dict: cut_volume, fill_volume, net_volume, method "tin_prism_integration", etc.

        Raises:
            RuntimeError: If CRS is not validated (projected).
        """
        if not self.crs_manager.validate_projected():
            raise RuntimeError("CRS must be set and projected before TIN volume computation")
        from mapfree.engines.inspection.tin_volume import TINVolumeEngine
        engine = TINVolumeEngine(use_parallel=True)
        return engine.compute_tin_volume(vertices_a, faces_a, vertices_b, faces_b)

    def compute_surface_deviation(
        self,
        vertices_ref: Union[list, np.ndarray],
        faces_ref: Union[list, np.ndarray],
        vertices_target: Union[list, np.ndarray],
        faces_target: Union[list, np.ndarray],
    ) -> dict:
        """
        Compute per-vertex signed vertical deviation of target from reference surface.

        Args:
            vertices_ref: (V, 3) reference surface.
            faces_ref: (F, 3) reference triangles.
            vertices_target: (V, 3) target surface.
            faces_target: (F, 3) target triangles.

        Returns:
            Structured dict: deviations (array), statistics (min, max, mean, std), etc.

        Raises:
            ValueError: If mesh shapes are invalid.
        """
        if vertices_ref is None or faces_ref is None or len(vertices_ref) == 0 or len(faces_ref) == 0:
            raise ValueError("Reference mesh must be non-empty")
        if vertices_target is None or len(vertices_target) == 0:
            raise ValueError("Target vertices must be non-empty")
        from mapfree.engines.inspection.deviation import SurfaceDeviationEngine
        engine = SurfaceDeviationEngine(use_parallel=True)
        return engine.compute_deviation(
            vertices_ref, faces_ref, vertices_target, faces_target,
        )

    def save_session(
        self,
        path: Union[str, Path],
        measurements: list,
        project: str = "",
    ) -> dict:
        """
        Save a measurement session (CRS, timestamp, measurements) to JSON.

        Args:
            path: Output file path.
            measurements: List of structured result dicts to store.
            project: Optional project name.

        Returns:
            Structured dict with path, project, crs, count.
        """
        from mapfree.engines.inspection.session import MeasurementSession
        session = MeasurementSession(project=project, crs=self.crs_manager.get_crs())
        for m in measurements:
            session.add_measurement(m)
        session.export_json(path)
        return {
            "path": str(Path(path).resolve()),
            "project": session.project,
            "crs": session.crs,
            "count": len(session.measurements),
            "method": "save_session",
        }

    def load_session(self, path: Union[str, Path]) -> dict:
        """
        Load a measurement session from JSON.

        Args:
            path: JSON file path.

        Returns:
            Structured dict: project, crs, timestamp, measurements (list), count.
        """
        from mapfree.engines.inspection.session import MeasurementSession
        session = MeasurementSession.load_json(path)
        return {
            "project": session.project,
            "crs": session.crs,
            "timestamp": session.timestamp,
            "measurements": session.measurements,
            "count": len(session.measurements),
            "method": "load_session",
        }


if __name__ == "__main__":
    # Manual dev test: simple triangle mesh, distance, area, ray pick
    logging.basicConfig(level=logging.INFO)

    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.5, 1.0, 0.0],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2]], dtype=np.intp)

    engine = MeasurementEngine()
    engine.set_mesh(vertices, faces)
    engine.set_crs("32632")

    d = engine.measure_distance([0, 0, 0], [1, 0, 0])
    assert abs(d.value - 1.0) < 1e-9
    logger.info("distance: %s %s", d.value, d.unit)

    pts_3d = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 1.0, 0.0]], dtype=np.float64)
    area = engine.measure_area_polygon_3d(pts_3d)
    logger.info("area_3d: %s %s", area.value, area.unit)

    ray_origin = np.array([0.5, 0.3, 1.0], dtype=np.float64)
    ray_direction = np.array([0.0, 0.0, -1.0], dtype=np.float64)
    hit_result = engine.ray_pick(ray_origin, ray_direction)
    if hit_result is not None:
        logger.info("ray_pick distance: %s %s", hit_result.value, hit_result.unit)
    else:
        logger.info("ray_pick: no hit")

    logger.info("Measurement & Inspection Stage 1 stub tests done.")
