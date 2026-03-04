"""
Deviation heatmap: convert per-vertex deviation array to vertex colors.
Blue = negative, green = zero, red = positive. No custom shader; output feeds existing GL pipeline.
"""
import numpy as np


def deviation_to_vertex_colors(
    vertices: np.ndarray,
    deviations: np.ndarray,
    max_abs: float | None = None,
) -> np.ndarray:
    """
    Map per-vertex deviations to RGB vertex colors for rendering.

    Args:
        vertices: (N, 3) mesh vertices (unused; for API consistency).
        deviations: (N,) per-vertex signed deviation values.
        max_abs: Scale range; deviations are normalized to [-max_abs, +max_abs].
                 If None, use max(abs(deviations)) or 1.0 if all zero.

    Returns:
        (N, 3) float array in [0, 1]: R, G, B. Blue = negative, green = zero, red = positive.
    """
    dev = np.asarray(deviations, dtype=np.float64)
    if dev.size == 0:
        return np.zeros((0, 3), dtype=np.float32)
    if dev.ndim != 1:
        dev = dev.ravel()
    if max_abs is None or max_abs <= 0:
        max_abs = float(np.nanmax(np.abs(dev))) if np.any(np.isfinite(dev)) else 1.0
        if max_abs <= 0:
            max_abs = 1.0
    # Normalize to [-1, 1]
    t = np.clip(dev / max_abs, -1.0, 1.0)
    # Blue (0,0,1) at t=-1, green (0,1,0) at t=0, red (1,0,0) at t=1
    r = np.where(t <= 0, 0.0, np.where(t >= 1, 1.0, t))
    g = np.where(t <= 0, 1.0 + t, np.where(t >= 1, 1.0 - t, 1.0 - np.abs(t)))
    b = np.where(t >= 0, 0.0, np.clip(-t, 0.0, 1.0))
    g = np.clip(g, 0.0, 1.0)
    colors = np.stack([r, g, b], axis=1).astype(np.float32)
    return colors
