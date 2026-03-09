"""
Volume computation: cut/fill between two surfaces via grid integration.
Surface A and B are elevation callables z = f(x, y). All float64.
"""
import logging
from typing import Callable, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _check_bounds(bounds: Tuple[float, float, float, float]) -> None:
    xmin, xmax, ymin, ymax = bounds
    if xmax <= xmin or ymax <= ymin:
        raise ValueError("bounds must have xmax > xmin and ymax > ymin, got %s" % (bounds,))


def _check_resolution(resolution: float) -> None:
    if not np.isfinite(resolution) or resolution <= 0.0:
        raise ValueError("resolution must be positive finite, got %s" % (resolution,))


class VolumeEngine:
    """
    Compute cut/fill volume between two surfaces over a rectangular domain.
    Surfaces are callables: z = surface(x, y) with x, y float or arrays; return float64.
    """

    def compute_volume_grid(
        self,
        surface_a: Callable,
        surface_b: Callable,
        bounds: Tuple[float, float, float, float],
        resolution: float,
    ) -> dict:
        """
        Integrate signed volume (surface_b - surface_a) over a uniform grid.

        Args:
            surface_a: Elevation of first surface, callable(x, y) -> z (float or array).
            surface_b: Elevation of second surface, callable(x, y) -> z.
            bounds: (xmin, xmax, ymin, ymax).
            resolution: Grid cell spacing (same in x and y).

        Returns:
            Dict with cut_volume, fill_volume, net_volume, area (all float64),
            plus value, unit, precision, method for structured result.
        """
        _check_bounds(bounds)
        _check_resolution(resolution)
        xmin, xmax, ymin, ymax = bounds

        # Cell-aligned grid: Nx * resolution <= (xmax - xmin), same for y
        nx = max(1, int(np.ceil((xmax - xmin) / resolution)))
        ny = max(1, int(np.ceil((ymax - ymin) / resolution)))
        dx = (xmax - xmin) / nx
        dy = (ymax - ymin) / ny
        # Sample at cell centers
        x = np.linspace(xmin + 0.5 * dx, xmax - 0.5 * dx, nx, dtype=np.float64)
        y = np.linspace(ymin + 0.5 * dy, ymax - 0.5 * dy, ny, dtype=np.float64)
        xx, yy = np.meshgrid(x, y, indexing="xy")
        xx_flat = xx.ravel()
        yy_flat = yy.ravel()

        za = np.asarray(surface_a(xx_flat, yy_flat), dtype=np.float64).ravel()
        zb = np.asarray(surface_b(xx_flat, yy_flat), dtype=np.float64).ravel()
        if za.size != xx_flat.size or zb.size != xx_flat.size:
            raise ValueError(
                "surface_a and surface_b must return array same size as input, "
                "got za.size=%s zb.size=%s grid=%s" % (za.size, zb.size, xx_flat.size)
            )

        delta_z = zb - za
        cell_area = dx * dy
        fill_mask = delta_z > 0.0
        cut_mask = delta_z < 0.0
        fill_volume = np.float64(np.sum(delta_z[fill_mask]) * cell_area)
        cut_volume = np.float64(np.sum(-delta_z[cut_mask]) * cell_area)
        net_volume = np.float64(np.sum(delta_z) * cell_area)
        area = np.float64(nx * ny * cell_area)

        return {
            "cut_volume": float(cut_volume),
            "fill_volume": float(fill_volume),
            "net_volume": float(net_volume),
            "area": float(area),
            "value": float(net_volume),
            "unit": "cubic_meter",
            "precision": np.finfo(np.float64).resolution,
            "method": "grid_integration",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # z1 = 0, z2 = 0.5*x + 0.2*y over [0,1] x [0,1]
    def surface_a(x, y):
        return np.zeros_like(np.atleast_1d(x) + np.atleast_1d(y))

    def surface_b(x, y):
        x_ = np.atleast_1d(np.asarray(x, dtype=np.float64))
        y_ = np.atleast_1d(np.asarray(y, dtype=np.float64))
        return 0.5 * x_ + 0.2 * y_

    engine = VolumeEngine()
    out = engine.compute_volume_grid(surface_a, surface_b, (0.0, 1.0, 0.0, 1.0), 0.1)
    logger.info(
        "cut=%s fill=%s net=%s area=%s",
        out["cut_volume"], out["fill_volume"], out["net_volume"], out["area"],
    )
    # Exact: int_0^1 int_0^1 (0.5*x + 0.2*y) dx dy = 0.5/2 + 0.2/2 = 0.35
    assert abs(out["net_volume"] - 0.35) < 0.01
    logger.info("VolumeEngine manual test passed.")
