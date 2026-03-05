"""Tests for mapfree.utils.colmap_io (pure Python/numpy — no Qt required)."""
import struct
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from mapfree.utils.colmap_io import read_points3d_bin, read_points3d_txt


# ─── helpers ─────────────────────────────────────────────────────────────────


def _write_points3d_bin(path: Path, points: list[tuple]) -> None:
    """Write a minimal COLMAP points3D.bin.

    points: list of (x, y, z, r, g, b) tuples.
    """
    with open(path, "wb") as fh:
        fh.write(struct.pack("<Q", len(points)))
        for i, (x, y, z, r, g, b) in enumerate(points):
            fh.write(struct.pack("<Q", i + 1))       # point3D_id
            fh.write(struct.pack("<ddd", x, y, z))   # xyz
            fh.write(struct.pack("<BBB", r, g, b))   # rgb
            fh.write(struct.pack("<d", 0.5))          # error
            fh.write(struct.pack("<Q", 0))            # track_length = 0


def _write_points3d_txt(path: Path, points: list[tuple]) -> None:
    """Write a minimal COLMAP points3D.txt."""
    with open(path, "w") as fh:
        fh.write("# 3D point list\n# header\n# more header\n")
        for i, (x, y, z, r, g, b) in enumerate(points):
            fh.write(f"{i+1} {x} {y} {z} {int(r)} {int(g)} {int(b)} 0.5\n")


_SAMPLE = [
    (1.0, 2.0, 3.0, 255, 0, 0),
    (4.0, 5.0, 6.0, 0, 255, 128),
    (-1.5, 0.0, 2.5, 100, 100, 100),
]


# ─── binary parser tests ─────────────────────────────────────────────────────


class TestReadPoints3dBin:
    def test_valid_file_returns_correct_shape(self, tmp_path):
        f = tmp_path / "points3D.bin"
        _write_points3d_bin(f, _SAMPLE)
        result = read_points3d_bin(f)
        assert result is not None
        assert result.shape == (3, 6)

    def test_xyz_values_correct(self, tmp_path):
        f = tmp_path / "points3D.bin"
        _write_points3d_bin(f, _SAMPLE)
        result = read_points3d_bin(f)
        assert result is not None
        np.testing.assert_allclose(result[0, :3], [1.0, 2.0, 3.0], atol=1e-4)
        np.testing.assert_allclose(result[1, :3], [4.0, 5.0, 6.0], atol=1e-4)

    def test_rgb_values_correct(self, tmp_path):
        f = tmp_path / "points3D.bin"
        _write_points3d_bin(f, _SAMPLE)
        result = read_points3d_bin(f)
        assert result is not None
        assert result[0, 3] == pytest.approx(255.0)   # R of first point
        assert result[0, 4] == pytest.approx(0.0)     # G
        assert result[0, 5] == pytest.approx(0.0)     # B

    def test_empty_file_returns_none(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert read_points3d_bin(f) is None

    def test_zero_points_returns_empty_array(self, tmp_path):
        f = tmp_path / "zero.bin"
        f.write_bytes(struct.pack("<Q", 0))
        result = read_points3d_bin(f)
        assert result is not None
        assert result.shape == (0, 6)

    def test_missing_file_returns_none(self, tmp_path):
        assert read_points3d_bin(tmp_path / "nonexistent.bin") is None

    def test_corrupt_binary_returns_none(self, tmp_path):
        """File exists but binary content causes parse error → returns None."""
        f = tmp_path / "points3D.bin"
        f.write_bytes(struct.pack("<Q", 1) + b"truncated_garbage")
        assert read_points3d_bin(f) is None

    def test_read_raises_returns_none(self, tmp_path):
        """When reading the file raises, read_points3d_bin returns None."""
        f = tmp_path / "points3D.bin"
        f.write_bytes(struct.pack("<Q", 0))
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            assert read_points3d_bin(f) is None

    def test_truncated_returns_partial_or_none(self, tmp_path):
        """Truncated file should not crash; may return partial or None."""
        f = tmp_path / "trunc.bin"
        f.write_bytes(struct.pack("<Q", 100) + b"\x00" * 10)
        result = read_points3d_bin(f)
        # Must not raise; result is None or partial array
        assert result is None or isinstance(result, np.ndarray)

    def test_with_track_data(self, tmp_path):
        """Points with non-zero track_length are parsed correctly."""
        f = tmp_path / "tracked.bin"
        with open(f, "wb") as fh:
            fh.write(struct.pack("<Q", 1))
            fh.write(struct.pack("<Q", 1))            # point3D_id
            fh.write(struct.pack("<ddd", 7.0, 8.0, 9.0))
            fh.write(struct.pack("<BBB", 50, 100, 150))
            fh.write(struct.pack("<d", 0.1))          # error
            fh.write(struct.pack("<Q", 2))            # track_length = 2
            fh.write(struct.pack("<II", 1, 0))        # image_id=1, point2D_idx=0
            fh.write(struct.pack("<II", 2, 1))        # image_id=2, point2D_idx=1
        result = read_points3d_bin(f)
        assert result is not None
        assert result.shape == (1, 6)
        np.testing.assert_allclose(result[0, :3], [7.0, 8.0, 9.0], atol=1e-4)


# ─── text parser tests ───────────────────────────────────────────────────────


class TestReadPoints3dTxt:
    def test_valid_txt_file(self, tmp_path):
        f = tmp_path / "points3D.txt"
        _write_points3d_txt(f, _SAMPLE)
        result = read_points3d_txt(f)
        assert result is not None
        assert result.shape == (3, 6)

    def test_xyz_correct(self, tmp_path):
        f = tmp_path / "pts.txt"
        _write_points3d_txt(f, _SAMPLE)
        result = read_points3d_txt(f)
        assert result is not None
        np.testing.assert_allclose(result[0, :3], [1.0, 2.0, 3.0], atol=1e-4)

    def test_missing_file_returns_none(self, tmp_path):
        assert read_points3d_txt(tmp_path / "nope.txt") is None

    def test_empty_file_returns_none(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("# just comments\n")
        result = read_points3d_txt(f)
        assert result is None

    def test_line_with_fewer_than_8_parts_skipped(self, tmp_path):
        """Lines with < 8 tokens are skipped; valid line is parsed."""
        f = tmp_path / "points3D.txt"
        f.write_text(
            "# header\n"
            "1 10.0 20.0 30.0 255 0 0 0.5\n"
            "2 3 4 5 6 7\n"
            "3 1.0 2.0 3.0 4 5 6 0.1\n"
        )
        result = read_points3d_txt(f)
        assert result is not None
        assert len(result) == 2
        np.testing.assert_allclose(result[0], [10.0, 20.0, 30.0, 255, 0, 0], atol=1e-4)
        np.testing.assert_allclose(result[1], [1.0, 2.0, 3.0, 4, 5, 6], atol=1e-4)

    def test_invalid_float_in_line_returns_none(self, tmp_path):
        """Parse error (e.g. non-numeric) causes function to return None."""
        f = tmp_path / "bad.txt"
        f.write_text("# header\n1 x y z 255 0 0 0.5\n")
        result = read_points3d_txt(f)
        assert result is None
