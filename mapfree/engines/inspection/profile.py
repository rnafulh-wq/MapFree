"""
Profile extraction along a polyline: sample elevation from mesh at regular steps.
Returns distances along line and elevations. All float64.
"""
import logging
from typing import List, Union

import numpy as np

from mapfree.engines.inspection.picking import ray_mesh_intersect

logger = logging.getLogger(__name__)


def _as_points_3d(points) -> np.ndarray:
    a = np.asarray(points, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 3:
        raise ValueError("line_points must have shape (N, 3), got %s" % (a.shape,))
    return a


class ProfileEngine:
    """
    Extract elevation profile along a polyline by casting vertical rays at the mesh.
    """

    def extract_profile(
        self,
        mesh_vertices: Union[list, np.ndarray],
        mesh_faces: Union[list, np.ndarray],
        line_points: Union[list, np.ndarray],
        sampling_distance: float,
    ) -> dict:
        """
        Sample elevation along the polyline at given step size.

        Args:
            mesh_vertices: (V, 3) float64.
            mesh_faces: (F, 3) vertex indices.
            line_points: (N, 3) polyline vertices (x, y, z); z can be ignored for ray origin height.
            sampling_distance: Step length along the polyline for sampling.

        Returns:
            Dict with distances (array of cumulative distance along line),
            elevations (array of z at each sample),
            points (N_sample, 3) sample positions,
            value (total length), unit, precision, method.
        """
        verts = np.asarray(mesh_vertices, dtype=np.float64)
        faces = np.asarray(mesh_faces, dtype=np.intp)
        if verts.ndim != 2 or verts.shape[1] != 3:
            raise ValueError("mesh_vertices must have shape (V, 3), got %s" % (verts.shape,))
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise ValueError("mesh_faces must have shape (F, 3), got %s" % (faces.shape,))
        pts = _as_points_3d(line_points)
        if len(pts) < 2:
            raise ValueError("line_points must have at least 2 points, got %d" % len(pts))
        if not np.isfinite(sampling_distance) or sampling_distance <= 0.0:
            raise ValueError("sampling_distance must be positive finite, got %s" % (sampling_distance,))

        # Cumulative segment lengths
        seg_len = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cum_len = np.concatenate([[0.0], np.cumsum(seg_len)])
        total_len = cum_len[-1]
        if total_len <= 0.0:
            raise ValueError("line_points total length is zero")

        # Sample distances along polyline
        num_samples = max(1, int(np.ceil(total_len / sampling_distance)))
        dist_samples = np.linspace(0.0, total_len, num_samples, endpoint=True, dtype=np.float64)

        # Interpolate (x, y) and ray origin z above mesh
        z_high = np.max(verts[:, 2]) + 1.0
        ray_direction = np.array([0.0, 0.0, -1.0], dtype=np.float64)

        distances = []
        elevations = []
        sample_pts = []

        for d in dist_samples:
            if d <= 0.0:
                x, y = pts[0, 0], pts[0, 1]
            elif d >= total_len:
                x, y = pts[-1, 0], pts[-1, 1]
            else:
                idx = np.searchsorted(cum_len, d, side="right") - 1
                idx = min(idx, len(seg_len) - 1)
                t = (d - cum_len[idx]) / seg_len[idx] if seg_len[idx] > 0 else 0.0
                t = np.clip(t, 0.0, 1.0)
                x = (1 - t) * pts[idx, 0] + t * pts[idx + 1, 0]
                y = (1 - t) * pts[idx, 1] + t * pts[idx + 1, 1]
            ray_origin = np.array([x, y, z_high], dtype=np.float64)
            hit = ray_mesh_intersect(ray_origin, ray_direction, verts, faces)
            if hit is not None:
                distances.append(np.float64(d))
                elevations.append(np.float64(hit[2]))
                sample_pts.append([x, y, hit[2]])
            else:
                distances.append(np.float64(d))
                elevations.append(np.nan)
                sample_pts.append([x, y, np.nan])

        distances_arr = np.array(distances, dtype=np.float64)
        elevations_arr = np.array(elevations, dtype=np.float64)
        sample_pts_arr = np.array(sample_pts, dtype=np.float64)

        return {
            "distances": distances_arr,
            "elevations": elevations_arr,
            "points": sample_pts_arr,
            "value": float(total_len),
            "unit": "meter",
            "precision": np.finfo(np.float64).resolution,
            "method": "profile_extraction",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Simple horizontal plane at z=1
    vertices = np.array([
        [0.0, 0.0, 1.0],
        [2.0, 0.0, 1.0],
        [1.0, 1.0, 1.0],
        [0.0, 2.0, 1.0],
        [2.0, 2.0, 1.0],
    ], dtype=np.float64)
    faces = np.array([
        [0, 1, 2],
        [0, 2, 3],
        [2, 1, 4],
        [2, 4, 3],
    ], dtype=np.intp)
    line_points = np.array([
        [0.5, 0.5, 0.0],
        [1.5, 0.5, 0.0],
        [1.5, 1.5, 0.0],
    ], dtype=np.float64)
    engine = ProfileEngine()
    out = engine.extract_profile(vertices, faces, line_points, 0.25)
    logger.info("distances=%s elevations=%s", out["distances"].shape, out["elevations"].shape)
    assert np.allclose(out["elevations"], 1.0, equal_nan=True)
    logger.info("ProfileEngine manual test passed.")
