"""Tests for mapfree.utils.exif_order - helper functions for EXIF GPS/time parsing."""
import pytest

from mapfree.utils.exif_order import (
    _rational_to_float,
    _dms_to_decimal,
)


class TestRationalToFloat:
    def test_tuple_rational(self):
        result = _rational_to_float((3, 2))
        assert result == pytest.approx(1.5)

    def test_integer(self):
        result = _rational_to_float(42)
        assert result == pytest.approx(42.0)

    def test_none_returns_zero(self):
        result = _rational_to_float(None)
        assert result == pytest.approx(0.0)

    def test_fraction_object(self):
        from fractions import Fraction
        result = _rational_to_float(Fraction(3, 4))
        assert result == pytest.approx(0.75)

    def test_denominator_zero(self):
        result = _rational_to_float((5, 0))
        assert result == pytest.approx(5.0)  # val[1] or 1 → denom=1

    def test_list_input(self):
        result = _rational_to_float([4, 2])
        assert result == pytest.approx(2.0)


class TestDmsToDecimal:
    def test_north(self):
        # 13°45'30" N = 13 + 45/60 + 30/3600 = 13.758333...
        dms = [(13, 1), (45, 1), (30, 1)]
        result = _dms_to_decimal(dms, "N")
        assert result == pytest.approx(13.758333, rel=1e-4)

    def test_south_negative(self):
        dms = [(13, 1), (45, 1), (30, 1)]
        result = _dms_to_decimal(dms, "S")
        assert result == pytest.approx(-13.758333, rel=1e-4)

    def test_west_negative(self):
        dms = [(100, 1), (0, 1), (0, 1)]
        result = _dms_to_decimal(dms, "W")
        assert result == pytest.approx(-100.0)

    def test_east_positive(self):
        dms = [(100, 1), (0, 1), (0, 1)]
        result = _dms_to_decimal(dms, "E")
        assert result == pytest.approx(100.0)

    def test_empty_dms_returns_zero(self):
        result = _dms_to_decimal([], "N")
        assert result == pytest.approx(0.0)

    def test_none_returns_zero(self):
        result = _dms_to_decimal(None, "N")
        assert result == pytest.approx(0.0)

    def test_bytes_ref(self):
        """Ref as bytes (from raw EXIF) should work."""
        dms = [(13, 1), (45, 1), (30, 1)]
        result = _dms_to_decimal(dms, b"S")
        assert result < 0

    def test_equatorial(self):
        dms = [(0, 1), (0, 1), (0, 1)]
        assert _dms_to_decimal(dms, "N") == pytest.approx(0.0)
