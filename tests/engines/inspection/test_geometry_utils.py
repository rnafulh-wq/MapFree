"""Tests for mapfree.engines.inspection.geometry_utils."""
import numpy as np
import pytest

from mapfree.engines.inspection.geometry_utils import (
    _as_float64_3,
    _as_float64_2,
    _as_points_3d,
    _as_points_2d,
    distance_3d,
    distance_2d,
    polyline_length,
    polygon_area_2d,
    polygon_area_3d,
)


class TestAs3D:
    def test_list_input(self):
        a = _as_float64_3([1.0, 2.0, 3.0])
        assert a.shape == (3,)
        assert a.dtype == np.float64

    def test_invalid_length(self):
        with pytest.raises(ValueError):
            _as_float64_3([1.0, 2.0])

    def test_2d_array_raises(self):
        with pytest.raises(ValueError):
            _as_float64_3(np.array([[1, 2, 3]]))


class TestAs2D:
    def test_list_input(self):
        a = _as_float64_2([1.0, 2.0])
        assert a.shape == (2,)

    def test_invalid_length(self):
        with pytest.raises(ValueError):
            _as_float64_2([1.0, 2.0, 3.0])


class TestAsPoints3D:
    def test_valid(self):
        pts = _as_points_3d([[1, 2, 3], [4, 5, 6]])
        assert pts.shape == (2, 3)

    def test_wrong_cols(self):
        with pytest.raises(ValueError):
            _as_points_3d([[1, 2], [3, 4]])


class TestAsPoints2D:
    def test_valid(self):
        pts = _as_points_2d([[1, 2], [3, 4]])
        assert pts.shape == (2, 2)

    def test_wrong_cols(self):
        with pytest.raises(ValueError):
            _as_points_2d([[1, 2, 3]])


class TestDistance3D:
    def test_origin(self):
        assert distance_3d([0, 0, 0], [0, 0, 0]) == pytest.approx(0.0)

    def test_unit_distance(self):
        d = distance_3d([0, 0, 0], [1, 0, 0])
        assert d == pytest.approx(1.0)

    def test_diagonal(self):
        d = distance_3d([0, 0, 0], [1, 1, 1])
        assert d == pytest.approx(np.sqrt(3))

    def test_numpy_arrays(self):
        p1 = np.array([1.0, 2.0, 3.0])
        p2 = np.array([4.0, 6.0, 3.0])
        assert distance_3d(p1, p2) == pytest.approx(5.0)


class TestDistance2D:
    def test_zero(self):
        assert distance_2d([0, 0], [0, 0]) == pytest.approx(0.0)

    def test_three_four_five(self):
        assert distance_2d([0, 0], [3, 4]) == pytest.approx(5.0)


class TestPolylineLength:
    def test_two_points(self):
        pts = [[0, 0, 0], [3, 4, 0]]
        assert polyline_length(pts) == pytest.approx(5.0)

    def test_three_points(self):
        pts = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]
        assert polyline_length(pts) == pytest.approx(2.0)

    def test_less_than_two_points(self):
        with pytest.raises(ValueError):
            polyline_length([[0, 0, 0]])

    def test_wrong_shape(self):
        with pytest.raises(ValueError):
            polyline_length([[0, 0], [1, 1]])


class TestPolygonArea2D:
    def test_unit_square(self):
        pts = [[0, 0], [1, 0], [1, 1], [0, 1]]
        assert polygon_area_2d(pts) == pytest.approx(1.0)

    def test_triangle(self):
        pts = [[0, 0], [1, 0], [0, 1]]
        assert polygon_area_2d(pts) == pytest.approx(0.5)

    def test_less_than_three_points(self):
        with pytest.raises(ValueError):
            polygon_area_2d([[0, 0], [1, 1]])


class TestPolygonArea3D:
    def test_flat_triangle(self):
        pts = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        assert polygon_area_3d(pts) == pytest.approx(0.5)

    def test_flat_square(self):
        pts = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]]
        assert polygon_area_3d(pts) == pytest.approx(4.0)

    def test_less_than_three_points(self):
        with pytest.raises(ValueError):
            polygon_area_3d([[0, 0, 0], [1, 1, 1]])
