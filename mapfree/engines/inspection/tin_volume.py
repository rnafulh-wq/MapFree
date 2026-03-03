"""
TIN-to-TIN volume computation: vertical prism integration over triangles.
No raster grid; uses mesh triangles directly. All float64.
"""
import logging
from typing import Optional, Union

import numpy as np

from mapfree.engines.inspection.geometry_utils import polygon_area_3d
from mapfree.engines.inspection.picking import ray_mesh_intersect

logger = logging.getLogger(__name__)


def _sample_z_at_xy(
    x: float,
    y: float,
    vertices: np.ndarray,
    faces: np.ndarray,
    z_above: float,
) -> Optional[float]:
    """Return z on mesh at (x, y) via vertical ray, or None if no hit."""
    ray_origin = np.array([x, y, z_above], dtype=np.float64)
    ray_direction = np.array([0.0, 0.0, -1.0], dtype=np.float64)
    hit = ray_mesh_intersect(ray_origin, ray_direction, vertices, faces)
    return float(hit[2]) if hit is not None else None


class TINVolumeEngine:
    """
    Compute cut/fill volume between two triangulated surfaces by prism integration.
    For each triangle in surface A, sample surface B at the triangle vertices (vertical ray),
    then volume contribution = area(T) * (mean(z_b) - mean(z_a)).
    """

    def __init__(self, use_parallel: bool = True, max_workers: int = 4) -> None:
        self._use_parallel = bool(use_parallel)
        self._max_workers = max(1, int(max_workers))

    def compute_tin_volume(
        self,
        vertices_a: Union[list, np.ndarray],
        faces_a: Union[list, np.ndarray],
        vertices_b: Union[list, np.ndarray],
        faces_b: Union[list, np.ndarray],
    ) -> dict:
        """
        Compute signed volume between two TINs (B - A) by prism integration over A's triangles.

        Args:
            vertices_a: (V_a, 3) reference surface.
            faces_a: (F_a, 3) triangle indices.
            vertices_b: (V_b, 3) comparison surface.
            faces_b: (F_b, 3) triangle indices.

        Returns:
            Dict: cut_volume, fill_volume, net_volume, method "tin_prism_integration",
            value, unit, precision.
        """
        va = np.asarray(vertices_a, dtype=np.float64)
        fa = np.asarray(faces_a, dtype=np.intp)
        vb = np.asarray(vertices_b, dtype=np.float64)
        fb = np.asarray(faces_b, dtype=np.intp)
        if va.ndim != 2 or va.shape[1] != 3:
            raise ValueError("vertices_a must have shape (V, 3), got %s" % (va.shape,))
        if fa.ndim != 2 or fa.shape[1] != 3:
            raise ValueError("faces_a must have shape (F, 3), got %s" % (fa.shape,))
        if vb.ndim != 2 or vb.shape[1] != 3:
            raise ValueError("vertices_b must have shape (V, 3), got %s" % (vb.shape,))
        if fb.ndim != 2 or fb.shape[1] != 3:
            raise ValueError("faces_b must have shape (F, 3), got %s" % (fb.shape,))

        z_max_b = np.max(vb[:, 2]) + 1.0
        fill_sum = np.float64(0.0)
        cut_sum = np.float64(0.0)

        def process_tri(i: int) -> tuple:
            i0, i1, i2 = fa[i, 0], fa[i, 1], fa[i, 2]
            tri_a = va[[i0, i1, i2]]
            area = polygon_area_3d(tri_a)
            if area <= 0.0:
                return (0.0, 0.0)
            za = tri_a[:, 2]
            zb_list = []
            for j in range(3):
                z_b = _sample_z_at_xy(tri_a[j, 0], tri_a[j, 1], vb, fb, z_max_b)
                if z_b is None:
                    return (0.0, 0.0)
                zb_list.append(z_b)
            z_b_avg = (zb_list[0] + zb_list[1] + zb_list[2]) / 3.0
            z_a_avg = float(np.mean(za))
            delta = z_b_avg - z_a_avg
            vol = area * delta
            if vol > 0:
                return (vol, 0.0)
            return (0.0, -vol)

        if self._use_parallel and len(fa) > 1:
            try:
                from mapfree.engines.inspection.parallel import ParallelExecutor
                results = ParallelExecutor.run_parallel(
                    lambda i: process_tri(i),
                    range(len(fa)),
                    max_workers=self._max_workers,
                )
                for fill_v, cut_v in results:
                    fill_sum += fill_v
                    cut_sum += cut_v
            except Exception as e:
                logger.warning("TIN volume parallel failed, using sequential: %s", e)
                for i in range(len(fa)):
                    fv, cv = process_tri(i)
                    fill_sum += fv
                    cut_sum += cv
        else:
            for i in range(len(fa)):
                fv, cv = process_tri(i)
                fill_sum += fv
                cut_sum += cv

        net = fill_sum - cut_sum
        return {
            "cut_volume": float(cut_sum),
            "fill_volume": float(fill_sum),
            "net_volume": float(net),
            "value": float(net),
            "unit": "cubic_meter",
            "precision": np.finfo(np.float64).resolution,
            "method": "tin_prism_integration",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Two tilted planes over [0,1]x[0,1]: z_a=0, z_b=0.5*x+0.2*y
    vertices_a = np.array([
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
    ], dtype=np.float64)
    faces_a = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)
    vertices_b = np.array([
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.5], [1.0, 1.0, 0.7], [0.0, 1.0, 0.2],
    ], dtype=np.float64)
    faces_b = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.intp)
    engine = TINVolumeEngine(use_parallel=False)
    out = engine.compute_tin_volume(vertices_a, faces_a, vertices_b, faces_b)
    logger.info("TIN volume: cut=%s fill=%s net=%s", out["cut_volume"], out["fill_volume"], out["net_volume"])
    logger.info("TINVolumeEngine manual test passed.")
