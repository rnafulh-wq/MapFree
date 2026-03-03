"""
Spatial indices: KDTree for point cloud, SimpleBVH (grid buckets) for mesh.
No heavy dependencies; scipy.spatial.KDTree optional.
"""
import logging
from typing import List, Optional, Union

import numpy as np

from mapfree.engines.inspection.picking import ray_triangle_intersect

logger = logging.getLogger(__name__)

try:
    from scipy.spatial import KDTree as SciPyKDTree
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


class KDTreeWrapper:
    """
    Point cloud spatial index: nearest neighbor and radius search.
    Uses scipy.spatial.KDTree if available, else numpy fallback.
    """

    def __init__(self) -> None:
        self._points: Optional[np.ndarray] = None
        self._tree = None  # scipy KDTree or None for fallback
        self._built = False

    def build(self, points: Union[list, np.ndarray]) -> None:
        """
        Build index from (N, 3) float64 points.

        Raises:
            ValueError: If points shape is not (N, 3) or empty.
        """
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 3:
            raise ValueError("points must have shape (N, 3), got %s" % (pts.shape,))
        if len(pts) == 0:
            raise ValueError("points must not be empty")
        self._points = pts
        self._built = True
        if _SCIPY_AVAILABLE:
            self._tree = SciPyKDTree(pts)
        else:
            self._tree = None

    def nearest(self, point: Union[list, np.ndarray]) -> tuple:
        """
        Return (index, distance) of nearest point. point: (3,) float64.

        Returns:
            (index, distance) or (-1, inf) if not built or empty.
        """
        p = np.asarray(point, dtype=np.float64).reshape(3)
        if not self._built or self._points is None or len(self._points) == 0:
            return (-1, np.float64(np.inf))
        if self._tree is not None:
            d, idx = self._tree.query(p, k=1)
            return (int(idx), np.float64(d))
        # Numpy fallback: brute force
        d = np.linalg.norm(self._points - p, axis=1)
        idx = np.argmin(d)
        return (int(idx), np.float64(d[idx]))

    def radius_search(self, point: Union[list, np.ndarray], r: float) -> np.ndarray:
        """
        Return indices of all points within radius r. point: (3,), r: float64.

        Returns:
            Integer array of indices (empty if none).
        """
        p = np.asarray(point, dtype=np.float64).reshape(3)
        r = np.float64(r)
        if not self._built or self._points is None or len(self._points) == 0:
            return np.array([], dtype=np.intp)
        if self._tree is not None:
            idx = self._tree.query_ball_point(p, r)
            return np.asarray(idx, dtype=np.intp)
        # Numpy fallback
        d = np.linalg.norm(self._points - p, axis=1)
        return np.nonzero(d <= r)[0].astype(np.intp)


class SimpleBVH:
    """
    Lightweight mesh acceleration: per-triangle AABBs and grid buckets.
    ray_intersect_accelerated() only tests triangles in cells along the ray.
    """

    def __init__(self, vertices: np.ndarray, faces: np.ndarray) -> None:
        """
        Build from mesh. vertices (V,3), faces (F,3).

        Raises:
            ValueError: If shapes invalid.
        """
        self._verts = np.asarray(vertices, dtype=np.float64)
        self._faces = np.asarray(faces, dtype=np.intp)
        if self._verts.ndim != 2 or self._verts.shape[1] != 3:
            raise ValueError("vertices must have shape (V, 3), got %s" % (self._verts.shape,))
        if self._faces.ndim != 2 or self._faces.shape[1] != 3:
            raise ValueError("faces must have shape (F, 3), got %s" % (self._faces.shape,))
        self._n_tri = len(self._faces)
        self._tri_mins = np.zeros((self._n_tri, 3), dtype=np.float64)
        self._tri_maxs = np.zeros((self._n_tri, 3), dtype=np.float64)
        for i in range(self._n_tri):
            i0, i1, i2 = self._faces[i, 0], self._faces[i, 1], self._faces[i, 2]
            tri = self._verts[[i0, i1, i2]]
            self._tri_mins[i] = np.min(tri, axis=0)
            self._tri_maxs[i] = np.max(tri, axis=0)
        # Grid: choose cell size from average AABB extent
        margin = 1e-6
        all_min = np.min(self._tri_mins, axis=0) - margin
        all_max = np.max(self._tri_maxs, axis=0) + margin
        extent = all_max - all_min
        cell_size = max(np.max(extent) / max(1, int(np.sqrt(self._n_tri)) * 2), 1e-9)
        self._cell_size = np.float64(cell_size)
        self._grid_min = all_min
        nx = max(1, int(np.ceil(extent[0] / cell_size)))
        ny = max(1, int(np.ceil(extent[1] / cell_size)))
        nz = max(1, int(np.ceil(extent[2] / cell_size)))
        self._shape = (nx, ny, nz)
        # Buckets: list of triangle indices per cell (flat index)
        self._buckets = [[] for _ in range(nx * ny * nz)]
        for i in range(self._n_tri):
            mn = self._tri_mins[i]
            mx = self._tri_maxs[i]
            ix0 = int((mn[0] - all_min[0]) / cell_size)
            iy0 = int((mn[1] - all_min[1]) / cell_size)
            iz0 = int((mn[2] - all_min[2]) / cell_size)
            ix1 = int((mx[0] - all_min[0]) / cell_size)
            iy1 = int((mx[1] - all_min[1]) / cell_size)
            iz1 = int((mx[2] - all_min[2]) / cell_size)
            ix0, ix1 = max(0, ix0), min(nx - 1, ix1)
            iy0, iy1 = max(0, iy0), min(ny - 1, iy1)
            iz0, iz1 = max(0, iz0), min(nz - 1, iz1)
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    for iz in range(iz0, iz1 + 1):
                        idx = ix * (ny * nz) + iy * nz + iz
                        self._buckets[idx].append(i)

    def ray_intersect_accelerated(
        self,
        ray_origin: Union[list, np.ndarray],
        ray_direction: Union[list, np.ndarray],
    ) -> Optional[np.ndarray]:
        """
        Ray-mesh intersection using grid buckets (only test triangles in traversed cells).

        Returns:
            Closest hit point (3,) float64 or None.
        """
        orig = np.asarray(ray_origin, dtype=np.float64).reshape(3)
        direc = np.asarray(ray_direction, dtype=np.float64).reshape(3)
        dnorm = np.linalg.norm(direc)
        if dnorm <= np.finfo(np.float64).eps:
            return None
        direc = direc / dnorm
        cs = self._cell_size
        nx, ny, nz = self._shape
        gmin = self._grid_min

        def cell_index(px, py, pz):
            ix = int((px - gmin[0]) / cs)
            iy = int((py - gmin[1]) / cs)
            iz = int((pz - gmin[2]) / cs)
            if 0 <= ix < nx and 0 <= iy < ny and 0 <= iz < nz:
                return ix * (ny * nz) + iy * nz + iz
            return -1

        # DDA-like step along ray (simplified: step by cell_size)
        t = 0.0
        max_t = 1e10
        best_hit = None
        best_t = np.inf
        seen = set()
        while t < max_t:
            p = orig + t * direc
            cidx = cell_index(p[0], p[1], p[2])
            if cidx >= 0 and cidx not in seen:
                seen.add(cidx)
                for tri_idx in self._buckets[cidx]:
                    i0, i1, i2 = self._faces[tri_idx, 0], self._faces[tri_idx, 1], self._faces[tri_idx, 2]
                    tri = np.array([self._verts[i0], self._verts[i1], self._verts[i2]], dtype=np.float64)
                    hit = ray_triangle_intersect(orig, direc, tri)
                    if hit is not None:
                        thit = np.dot(hit - orig, direc)
                        if thit >= 0.0 and thit < best_t:
                            best_t = thit
                            best_hit = hit
            if best_hit is not None:
                break
            t += cs
        return best_hit


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # KDTree
    pts = np.random.rand(100, 3).astype(np.float64)
    kdt = KDTreeWrapper()
    kdt.build(pts)
    idx, d = kdt.nearest([0.5, 0.5, 0.5])
    logger.info("KDTree nearest: index=%s dist=%s", idx, d)
    ids = kdt.radius_search([0.5, 0.5, 0.5], 0.2)
    logger.info("KDTree radius_search: %s points", len(ids))

    # SimpleBVH
    verts = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]], dtype=np.float64)
    faces = np.array([[0, 1, 2]], dtype=np.intp)
    bvh = SimpleBVH(verts, faces)
    hit = bvh.ray_intersect_accelerated([0.5, 0.3, 1.0], [0, 0, -1.0])
    logger.info("SimpleBVH ray_intersect: %s", hit is not None)
    logger.info("spatial_index manual test passed.")
