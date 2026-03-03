"""
Ray-triangle and ray-mesh intersection. Möller–Trumbore algorithm.
No OpenGL; numpy only. No BVH in Stage 1.
"""
from typing import Optional, Union

import numpy as np


def ray_triangle_intersect(
    ray_origin: Union[list, np.ndarray],
    ray_direction: Union[list, np.ndarray],
    triangle: Union[list, np.ndarray],
) -> Optional[np.ndarray]:
    """
    Möller–Trumbore ray-triangle intersection.
    Returns the closest intersection point (float64 array of shape (3,)) or None.

    Args:
        ray_origin: (3,) ray origin.
        ray_direction: (3,) ray direction (need not be normalized).
        triangle: (3, 3) array of three vertices.

    Returns:
        Intersection point as (3,) float64, or None if no hit.
    """
    orig = np.asarray(ray_origin, dtype=np.float64).reshape(3)
    direc = np.asarray(ray_direction, dtype=np.float64).reshape(3)
    tri = np.asarray(triangle, dtype=np.float64)
    if tri.shape != (3, 3):
        raise ValueError("triangle must have shape (3, 3), got %s" % (tri.shape,))

    v0, v1, v2 = tri[0], tri[1], tri[2]
    edge1 = v1 - v0
    edge2 = v2 - v0
    h = np.cross(direc, edge2)
    a = np.dot(edge1, h)

    eps = np.finfo(np.float64).eps
    if np.abs(a) < eps:
        return None

    f = 1.0 / a
    s = orig - v0
    u = f * np.dot(s, h)
    if u < 0.0 or u > 1.0:
        return None

    q = np.cross(s, edge1)
    v = f * np.dot(direc, q)
    if v < 0.0 or u + v > 1.0:
        return None

    t = f * np.dot(edge2, q)
    if t <= eps:
        return None

    return orig + t * direc


def ray_mesh_intersect(
    ray_origin: Union[list, np.ndarray],
    ray_direction: Union[list, np.ndarray],
    vertices: Union[list, np.ndarray],
    faces: Union[list, np.ndarray],
) -> Optional[np.ndarray]:
    """
    Find the closest ray-mesh intersection point.
    Iterates over all triangles; no BVH. Returns first (closest) hit.

    Args:
        ray_origin: (3,) ray origin.
        ray_direction: (3,) ray direction.
        vertices: (V, 3) vertex array.
        faces: (F, 3) face index array (zero-based indices into vertices).

    Returns:
        Closest intersection point as (3,) float64, or None if no hit.
    """
    verts = np.asarray(vertices, dtype=np.float64)
    faces_arr = np.asarray(faces, dtype=np.intp)
    if verts.ndim != 2 or verts.shape[1] != 3:
        raise ValueError("vertices must have shape (V, 3), got %s" % (verts.shape,))
    if faces_arr.ndim != 2 or faces_arr.shape[1] != 3:
        raise ValueError("faces must have shape (F, 3), got %s" % (faces_arr.shape,))

    orig = np.asarray(ray_origin, dtype=np.float64).reshape(3)
    direc = np.asarray(ray_direction, dtype=np.float64).reshape(3)
    dnorm = np.linalg.norm(direc)
    if dnorm <= np.finfo(np.float64).eps:
        raise ValueError("ray_direction must be non-zero")
    direc = direc / dnorm

    best_t = np.inf
    best_point: Optional[np.ndarray] = None

    for i in range(len(faces_arr)):
        i0, i1, i2 = faces_arr[i, 0], faces_arr[i, 1], faces_arr[i, 2]
        tri = np.array([verts[i0], verts[i1], verts[i2]], dtype=np.float64)
        hit = ray_triangle_intersect(orig, direc, tri)
        if hit is not None:
            t = np.dot(hit - orig, direc)
            if t >= 0.0 and t < best_t:
                best_t = t
                best_point = hit

    return best_point
