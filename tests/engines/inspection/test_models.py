"""Tests for mapfree.engines.inspection.models."""
import numpy as np
import pytest

from mapfree.engines.inspection.models import Point3D, MeasurementResult


class TestPoint3D:
    def test_creation(self):
        p = Point3D(1.0, 2.0, 3.0)
        assert p.x == 1.0 and p.y == 2.0 and p.z == 3.0

    def test_to_array(self):
        p = Point3D(1.0, 2.0, 3.0)
        arr = p.to_array()
        assert arr.shape == (3,)
        assert arr.dtype == np.float64
        assert np.allclose(arr, [1.0, 2.0, 3.0])

    def test_from_array(self):
        p = Point3D.from_array([4.0, 5.0, 6.0])
        assert p.x == pytest.approx(4.0)
        assert p.y == pytest.approx(5.0)
        assert p.z == pytest.approx(6.0)

    def test_from_array_wrong_length(self):
        with pytest.raises(ValueError):
            Point3D.from_array([1.0, 2.0])

    def test_frozen(self):
        p = Point3D(1.0, 2.0, 3.0)
        with pytest.raises(Exception):
            p.x = 99.0  # frozen dataclass


class TestMeasurementResult:
    def test_creation(self):
        r = MeasurementResult(value=5.0, unit="meter", precision=0.001, crs="EPSG:32648", method="distance")
        assert r.value == 5.0
        assert r.unit == "meter"
        assert r.crs == "EPSG:32648"
        assert r.method == "distance"
