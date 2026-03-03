"""
Lightweight dataclasses for measurement results and 3D points.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Point3D:
    """A 3D point (x, y, z)."""

    x: float
    y: float
    z: float

    def to_array(self) -> np.ndarray:
        """Return as float64 array of shape (3,)."""
        return np.array([self.x, self.y, self.z], dtype=np.float64)

    @classmethod
    def from_array(cls, arr) -> "Point3D":
        """Build from sequence or array of length 3."""
        a = np.asarray(arr, dtype=np.float64)
        if a.shape != (3,):
            raise ValueError("Point3D requires 3 elements, got shape %s" % (a.shape,))
        return cls(x=float(a[0]), y=float(a[1]), z=float(a[2]))


@dataclass
class MeasurementResult:
    """Result of a single measurement: value, unit, precision, CRS, and method."""

    value: float
    unit: str
    precision: float
    crs: str
    method: str
