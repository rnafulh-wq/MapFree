"""Tests for mapfree.geospatial.exif_reader."""
import pytest
from unittest.mock import patch

from mapfree.geospatial import exif_reader
from mapfree.geospatial.exif_reader import (
    extract_gps_from_images,
    _rational_to_float,
    _dms_to_decimal,
)


class TestExifReaderImport:
    """Module and import sanity."""

    def test_import_module(self):
        """Module imports without error."""
        assert exif_reader is not None
        assert hasattr(exif_reader, "extract_gps_from_images")


class TestRationalToFloat:
    """Internal helper _rational_to_float."""

    def test_none_returns_zero(self):
        assert _rational_to_float(None) == 0.0

    def test_rational_like(self):
        class R:
            numerator = 3
            denominator = 2
        assert _rational_to_float(R()) == 1.5

    def test_tuple_two_elements(self):
        assert _rational_to_float((6, 2)) == 3.0

    def test_float_passthrough(self):
        assert _rational_to_float(2.5) == 2.5

    def test_invalid_returns_zero(self):
        assert _rational_to_float("x") == 0.0


class TestDmsToDecimal:
    """Internal helper _dms_to_decimal."""

    def test_empty_returns_zero(self):
        assert _dms_to_decimal([], None) == 0.0
        assert _dms_to_decimal(None, None) == 0.0

    def test_north_east_positive(self):
        # 1 deg 30 min 0 sec N = 1.5
        dms = [(1, 1), (30, 1), (0, 1)]
        assert _dms_to_decimal(dms, b"N") == pytest.approx(1.5)
        assert _dms_to_decimal(dms, "E") == pytest.approx(1.5)

    def test_south_west_negative(self):
        dms = [(1, 1), (0, 1), (0, 1)]
        assert _dms_to_decimal(dms, b"S") == pytest.approx(-1.0)
        assert _dms_to_decimal(dms, "W") == pytest.approx(-1.0)


class TestExtractGpsFromImages:
    """Public API extract_gps_from_images."""

    def test_not_a_directory_returns_empty(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("x")
        assert extract_gps_from_images(str(file_path)) == []

    def test_empty_directory_returns_empty(self, tmp_path):
        assert extract_gps_from_images(str(tmp_path)) == []

    def test_skips_non_jpg(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        (tmp_path / "b.png").write_text("x")
        assert extract_gps_from_images(str(tmp_path)) == []

    @patch.object(exif_reader, "_read_exif_for_file")
    def test_returns_gps_for_jpg_when_reader_returns_data(self, mock_read, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"fake")
        mock_read.return_value = {
            "filename": "photo.jpg",
            "lat": 1.5,
            "lon": 100.5,
            "alt": 100.0,
            "timestamp": "2024:01:15 12:00:00",
        }

        result = extract_gps_from_images(str(tmp_path))

        assert len(result) == 1
        rec = result[0]
        assert rec["filename"] == "photo.jpg"
        assert rec["lat"] == pytest.approx(1.5)
        assert rec["lon"] == pytest.approx(100.5)
        assert rec["alt"] == pytest.approx(100.0)
        assert rec["timestamp"] == "2024:01:15 12:00:00"

    @patch.object(exif_reader, "_read_exif_for_file")
    def test_skips_image_with_no_gps_ifd(self, mock_read, tmp_path):
        (tmp_path / "nogps.jpg").write_bytes(b"fake")
        mock_read.return_value = None

        result = extract_gps_from_images(str(tmp_path))

        assert result == []

    @patch.object(exif_reader, "_read_exif_for_file")
    def test_skips_image_when_reader_returns_none(self, mock_read, tmp_path):
        (tmp_path / "zero.jpg").write_bytes(b"fake")
        mock_read.return_value = None

        result = extract_gps_from_images(str(tmp_path))

        assert result == []
