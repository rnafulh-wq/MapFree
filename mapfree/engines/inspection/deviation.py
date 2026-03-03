"""
Surface deviation analysis: per-vertex signed vertical deviation from reference surface.
Numeric only; no visualization.
"""
import logging
from typing import Union

import numpy as np

from mapfree.engines.inspection.parallel import ParallelExecutor

logger = logging.getLogger(__name__)


def _closest_point_on_triangle(
    p: np.ndarray,
    t0: np.ndarray,
    t1: np.ndarray,
    t2: np.ndarray,
) -> np.ndarray:
    """Return closest point on triangle (t0,t1,t2) to point p. (3,) float64."""
    e0 = t1 - t0
    e1 = t2 - t0
    v0 = t0 - p
    a = np.dot(e0, e0)
    b = np.dot(e0, e1)
    c = np.dot(e1, e1)
    d = np.dot(e0, v0)
    e = np.dot(e1, v0)
    det = a * c - b * b
    s = b * e - c * d
    t = b * d - a * e
    if s + t <= det:
        if s <= 0:
            if t <= 0:
                if d <= 0:
                    t = 0.0
                    s = max(0.0, min(-d / a, 1.0))
                else:
                    s = 0.0
                    t = max(0.0, min(-e / c, 1.0))
            else:
                s = 0.0
                t = max(0.0, min(-e / c, 1.0))
        elif t <= 0:
            t = 0.0
            s = max(0.0, min(-d / a, 1.0))
        else:
            inv_det = 1.0 / det
            s *= inv_det
            t *= inv_det
    else:
        if s <= 0:
            if t >= 1:
                t = 1.0
                s = max(0.0, min(-(d + b) / a, 1.0))
            else:
                s = 0.0
                t = max(0.0, min(-e / c, 1.0))
        elif t <= 0:
            t = 0.0
            s = max(0.0, min(-d / a, 1.0))
        else:
            numer = (c + e) - (b + d)
            if numer <= 0:
                s = 0.0
                t = 1.0
            else:
                denom = a - 2 * b + c
                s = min(numer / denom, 1.0)
                t = 1.0 - s
    return t0 + s * e0 + t * e1


def _nearest_point_on_mesh(p: np.ndarray, vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Return nearest point on mesh to p. (3,) float64."""
    best_dist_sq = np.inf
    best_point = None
    for i in range(len(faces)):
        i0, i1, i2 = faces[i, 0], faces[i, 1], faces[i, 2]
        t0 = vertices[i0]
        t1 = vertices[i1]
        t2 = vertices[i2]
        q = _closest_point_on_triangle(p, t0, t1, t2)
        d = np.sum((p - q) ** 2)
        if d < best_dist_sq:
            best_dist_sq = d
            best_point = q
    return best_point if best_point is not None else p.copy()


class SurfaceDeviationEngine:
    """
    Compute signed vertical deviation of target mesh vertices from reference surface.
    For each target vertex: find nearest point on reference surface; deviation = target_z - ref_z.
    """

    def __init__(self, use_parallel: bool = True, max_workers: int = 4) -> None:
        self._use_parallel = bool(use_parallel)
        self._max_workers = max(1, int(max_workers))

    def compute_deviation(
        self,
        vertices_ref: Union[list, np.ndarray],
        faces_ref: Union[list, np.ndarray],
        vertices_target: Union[list, np.ndarray],
        faces_target: Union[list, np.ndarray],
    ) -> dict:
        """
        Compute per-vertex signed vertical deviation (target - reference).

        Args:
            vertices_ref: (V_r, 3) reference surface.
            faces_ref: (F_r, 3) reference triangles.
            vertices_target: (V_t, 3) target surface.
            faces_target: (F_t, 3) target triangles (unused for vertex list; kept for API).

        Returns:
            Dict: deviations (array), statistics (min, max, mean, std), value (mean), unit, method.
        """
        vref = np.asarray(vertices_ref, dtype=np.float64)
        fref = np.asarray(faces_ref, dtype=np.intp)
        vtar = np.asarray(vertices_target, dtype=np.float64)
        if vref.ndim != 2 or vref.shape[1] != 3:
            raise ValueError("vertices_ref must have shape (V, 3), got %s" % (vref.shape,))
        if fref.ndim != 2 or fref.shape[1] != 3:
            raise ValueError("faces_ref must have shape (F, 3), got %s" % (fref.shape,))
        if vtar.ndim != 2 or vtar.shape[1] != 3:
            raise ValueError("vertices_target must have shape (V, 3), got %s" % (vtar.shape,))

        n = len(vtar)
        if n == 0:
            return {
                "deviations": np.array([], dtype=np.float64),
                "statistics": {"min": np.nan, "max": np.nan, "mean": np.nan, "std": np.nan},
                "value": np.nan,
                "unit": "meter",
                "precision": np.finfo(np.float64).resolution,
                "method": "surface_deviation",
            }

        def dev_at(i: int) -> float:
            p = vtar[i]
            nearest = _nearest_point_on_mesh(p, vref, fref)
            return float(p[2] - nearest[2])

        if self._use_parallel and n > 1:
            try:
                devs = ParallelExecutor.run_parallel(
                    dev_at,
                    range(n),
                    max_workers=self._max_workers,
                )
                deviations = np.array(devs, dtype=np.float64)
            except Exception as e:
                logger.warning("Deviation parallel failed, using sequential: %s", e)
                deviations = np.array([dev_at(i) for i in range(n)], dtype=np.float64)
        else:
            deviations = np.array([dev_at(i) for i in range(n)], dtype=np.float64)

        valid = np.isfinite(deviations)
        if np.any(valid):
            min_d = float(np.min(deviations[valid]))
            max_d = float(np.max(deviations[valid]))
            mean_d = float(np.mean(deviations[valid]))
            std_d = float(np.std(deviations[valid]))
        else:
            min_d = max_d = mean_d = std_d = np.nan

        return {
            "deviations": deviations,
            "statistics": {"min": min_d, "max": max_d, "mean": mean_d, "std": std_d},
            "value": mean_d if np.any(valid) else np.nan,
            "unit": "meter",
            "precision": np.finfo(np.float64).resolution,
            "method": "surface_deviation",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Ref: z=0 plane; target: z=0.1 plane
    vref = np.array([[0,0,0],[2,0,0],[1,1,0],[0,2,0],[2,2,0]], dtype=np.float64)
    fref = np.array([[0,1,2],[0,2,3],[2,1,4],[2,4,3]], dtype=np.intp)
    vtar = vref + np.array([0, 0, 0.1])
    ftar = fref.copy()
    engine = SurfaceDeviationEngine(use_parallel=False)
    out = engine.compute_deviation(vref, fref, vtar, ftar)
    logger.info("deviation stats: %s", out["statistics"])
    assert np.allclose(out["deviations"], 0.1)
    logger.info("SurfaceDeviationEngine manual test passed.")
