"""
Pure geometry functions for distances and areas. NumPy, float64, no side effects.
"""
from typing import Union

import numpy as np


def _as_float64_3(p: Union[list, np.ndarray]) -> np.ndarray:
    """Convert to (3,) float64 array. Raises ValueError if invalid."""
    a = np.asarray(p, dtype=np.float64)
    if a.ndim != 1 or a.size != 3:
        raise ValueError("Expected 1D array of length 3, got shape %s" % (a.shape,))
    return a.reshape(3)


def _as_float64_2(p: Union[list, np.ndarray]) -> np.ndarray:
    """Convert to (2,) float64 array. Raises ValueError if invalid."""
    a = np.asarray(p, dtype=np.float64)
    if a.ndim != 1 or a.size != 2:
        raise ValueError("Expected 1D array of length 2, got shape %s" % (a.shape,))
    return a.reshape(2)


def _as_points_3d(points: Union[list, np.ndarray]) -> np.ndarray:
    """Convert to (N, 3) float64 array. Raises ValueError if invalid."""
    a = np.asarray(points, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 3:
        raise ValueError("Expected array of shape (N, 3), got %s" % (a.shape,))
    return a


def _as_points_2d(points: Union[list, np.ndarray]) -> np.ndarray:
    """Convert to (N, 2) float64 array. Raises ValueError if invalid."""
    a = np.asarray(points, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 2:
        raise ValueError("Expected array of shape (N, 2), got %s" % (a.shape,))
    return a


def distance_3d(
    p1: Union[list, np.ndarray],
    p2: Union[list, np.ndarray],
) -> np.float64:
    """
    Euclidean distance between two 3D points.

    Args:
        p1: First point (3 elements).
        p2: Second point (3 elements).

    Returns:
        Distance as float64.

    Raises:
        ValueError: If input shape is not valid.
    """
    a = _as_float64_3(p1)
    b = _as_float64_3(p2)
    return np.float64(np.linalg.norm(a - b))


def distance_2d(
    p1: Union[list, np.ndarray],
    p2: Union[list, np.ndarray],
) -> np.float64:
    """
    Euclidean distance between two 2D points (x, y).

    Args:
        p1: First point (2 elements).
        p2: Second point (2 elements).

    Returns:
        Distance as float64.

    Raises:
        ValueError: If input shape is not valid.
    """
    a = _as_float64_2(p1)
    b = _as_float64_2(p2)
    return np.float64(np.linalg.norm(a - b))


def polyline_length(points: Union[list, np.ndarray]) -> np.float64:
    """
    Total length of a polyline (sum of segment lengths).

    Args:
        points: Array of shape (N, 3) for 3D points.

    Returns:
        Total length as float64.

    Raises:
        ValueError: If points shape is not (N, 3) or N < 2.
    """
    pts = _as_points_3d(points)
    if len(pts) < 2:
        raise ValueError("Polyline requires at least 2 points, got %d" % len(pts))
    diffs = np.diff(pts, axis=0)
    return np.float64(np.sum(np.linalg.norm(diffs, axis=1)))


def polygon_area_2d(points: Union[list, np.ndarray]) -> np.float64:
    """
    Signed area of a 2D polygon using the shoelace formula.
    Counter-clockwise vertices yield positive area.

    Args:
        points: Array of shape (N, 2) for (x, y) vertices.

    Returns:
        Signed area as float64.

    Raises:
        ValueError: If points shape is not (N, 2) or N < 3.
    """
    pts = _as_points_2d(points)
    if len(pts) < 3:
        raise ValueError("Polygon requires at least 3 points, got %d" % len(pts))
    x = pts[:, 0]
    y = pts[:, 1]
    return np.float64(0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def polygon_area_3d(points: Union[list, np.ndarray]) -> np.float64:
    """
    Area of a 3D polygon (planar) using cross product of edge vectors.
    Assumes polygon is planar; uses first three points to define plane.

    Args:
        points: Array of shape (N, 3) for 3D vertices.

    Returns:
        Area as float64 (non-negative).

    Raises:
        ValueError: If points shape is not (N, 3) or N < 3.
    """
    pts = _as_points_3d(points)
    if len(pts) < 3:
        raise ValueError("Polygon requires at least 3 points, got %d" % len(pts))
    n = len(pts)
    total = np.float64(0.0)
    ref = np.array(pts[0], dtype=np.float64)
    for i in range(1, n - 1):
        v1 = np.asarray(pts[i], dtype=np.float64) - ref
        v2 = np.asarray(pts[i + 1], dtype=np.float64) - ref
        total += np.float64(0.5 * np.linalg.norm(np.cross(v1, v2)))
    return total
