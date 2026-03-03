"""
Real CRS transformation using pyproj (optional dependency).
Raises clear exception if pyproj is not installed.
"""
import logging
from typing import Union

import numpy as np

logger = logging.getLogger(__name__)

try:
    from pyproj import Transformer
    _PYPROJ_AVAILABLE = True
except ImportError:
    _PYPROJ_AVAILABLE = False
    Transformer = None


def _require_pyproj() -> None:
    if not _PYPROJ_AVAILABLE:
        raise RuntimeError(
            "pyproj is required for CRS transformation. Install with: pip install pyproj"
        )


class CRSTransformer:
    """
    Transform points between EPSG coordinate reference systems using pyproj.
    Requires pyproj to be installed.
    """

    @staticmethod
    def transform_points(
        points: Union[list, np.ndarray],
        source_epsg: Union[int, str],
        target_epsg: Union[int, str],
    ) -> np.ndarray:
        """
        Transform (x, y) from source CRS to target CRS. Z is preserved unchanged.

        Args:
            points: (N, 2) or (N, 3) float64 array (x, y) or (x, y, z).
            source_epsg: Source EPSG code (e.g. 4326 or "4326").
            target_epsg: Target EPSG code.

        Returns:
            (N, 3) float64 array with transformed (x, y, z). If input was (N, 2), z=0.

        Raises:
            RuntimeError: If pyproj is not installed.
            ValueError: If points shape is invalid or transformation fails.
        """
        _require_pyproj()
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] not in (2, 3):
            raise ValueError("points must have shape (N, 2) or (N, 3), got %s" % (pts.shape,))
        n = len(pts)
        if pts.shape[1] == 2:
            z = np.zeros((n,), dtype=np.float64)
        else:
            z = pts[:, 2].copy()
        src = str(int(source_epsg)) if isinstance(source_epsg, (int, float)) else str(source_epsg).strip()
        tgt = str(int(target_epsg)) if isinstance(target_epsg, (int, float)) else str(target_epsg).strip()
        trans = Transformer.from_crs("EPSG:" + src, "EPSG:" + tgt, always_xy=True)
        xx, yy = trans.transform(pts[:, 0], pts[:, 1])
        out = np.column_stack([np.asarray(xx, dtype=np.float64), np.asarray(yy, dtype=np.float64), z])
        return out

    @staticmethod
    def validate_epsg(epsg: Union[int, str]) -> bool:
        """
        Check that the given EPSG code is valid (can create a transformer).

        Returns:
            True if valid, False otherwise.
        """
        _require_pyproj()
        try:
            code = str(int(epsg)) if isinstance(epsg, (int, float)) else str(epsg).strip()
            Transformer.from_crs("EPSG:" + code, "EPSG:" + code, always_xy=True)
            return True
        except Exception:
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if _PYPROJ_AVAILABLE:
        t = CRSTransformer()
        pts = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float64)
        out = t.transform_points(pts, 4326, 32648)
        logger.info("transform_points WGS84 -> UTM48N: %s", out)
        logger.info("validate_epsg 32648: %s", t.validate_epsg(32648))
    else:
        logger.info("pyproj not installed, skip CRS transform test")
