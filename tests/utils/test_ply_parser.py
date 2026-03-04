"""Tests for mapfree.utils.ply_parser (pure numpy — no Qt required).

Test cases:
- ASCII PLY with xyz only
- ASCII PLY with xyz + uchar rgb colours
- Binary little-endian PLY
- Missing file → (None, None), no exception
- Corrupt / non-PLY file → (None, None), no exception
- PLY without xyz properties → (None, None)
- PLY with vertex count 0 → (None, None)
"""
import struct
from pathlib import Path

import numpy as np
import pytest

from mapfree.utils.ply_parser import parse_ply_file


# ─── helpers ─────────────────────────────────────────────────────────────────


def _write_ascii_ply(path: Path, xyz: np.ndarray, rgb: np.ndarray | None = None) -> None:
    """Write a minimal ASCII PLY file."""
    has_color = rgb is not None
    props = [
        "property float x",
        "property float y",
        "property float z",
    ]
    if has_color:
        props += [
            "property uchar red",
            "property uchar green",
            "property uchar blue",
        ]
    header = "\n".join(["ply", "format ascii 1.0", f"element vertex {len(xyz)}", *props,
                        "end_header"]) + "\n"
    with open(path, "w") as fh:
        fh.write(header)
        for i, (x, y, z) in enumerate(xyz):
            if has_color:
                r, g, b = rgb[i]
                fh.write(f"{x} {y} {z} {int(r)} {int(g)} {int(b)}\n")
            else:
                fh.write(f"{x} {y} {z}\n")


def _write_binary_ply(path: Path, xyz: np.ndarray) -> None:
    """Write a minimal binary little-endian PLY file with float xyz."""
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {len(xyz)}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "end_header\n"
    ).encode("ascii")
    with open(path, "wb") as fh:
        fh.write(header)
        for x, y, z in xyz:
            fh.write(struct.pack("<fff", float(x), float(y), float(z)))


# ─── ASCII PLY tests ──────────────────────────────────────────────────────────


class TestParsePlyAscii:
    def test_xyz_only(self, tmp_path):
        """ASCII PLY with only xyz returns correct shape; colors is None."""
        xyz = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]], dtype=np.float32)
        ply = tmp_path / "pts.ply"
        _write_ascii_ply(ply, xyz)

        result_xyz, result_colors = parse_ply_file(ply)

        assert result_xyz is not None
        assert result_xyz.shape == (2, 3)
        assert result_colors is None
        np.testing.assert_allclose(result_xyz, xyz, atol=1e-5)

    def test_xyz_with_rgb(self, tmp_path):
        """ASCII PLY with uchar rgb normalises colours to [0, 1]."""
        xyz = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
        rgb = np.array([[255, 0, 0], [0, 255, 128]], dtype=np.uint8)
        ply = tmp_path / "colored.ply"
        _write_ascii_ply(ply, xyz, rgb)

        result_xyz, result_colors = parse_ply_file(ply)

        assert result_xyz is not None
        assert result_colors is not None
        assert result_colors.shape == (2, 4)          # RGBA
        assert result_colors[0, 0] == pytest.approx(1.0, abs=1e-3)   # red[0] == 1
        assert result_colors[0, 1] == pytest.approx(0.0, abs=1e-3)   # green[0] == 0
        assert result_colors[1, 0] == pytest.approx(0.0, abs=1e-3)   # red[1] == 0
        assert result_colors[1, 1] == pytest.approx(1.0, abs=1e-3)   # green[1] == 1
        # Alpha should be 1.0 (no alpha channel in file)
        assert result_colors[0, 3] == pytest.approx(1.0, abs=1e-3)

    def test_many_points(self, tmp_path):
        """Large ASCII PLY is parsed correctly."""
        rng = np.random.default_rng(42)
        xyz = rng.random((500, 3)).astype(np.float32)
        ply = tmp_path / "large.ply"
        _write_ascii_ply(ply, xyz)

        result_xyz, _ = parse_ply_file(ply)

        assert result_xyz is not None
        assert result_xyz.shape == (500, 3)

    def test_xyz_values_correct(self, tmp_path):
        """Parsed XYZ values match the written values numerically."""
        xyz = np.array([[-1.5, 2.5, -3.5], [4.0, -5.0, 6.0]], dtype=np.float32)
        ply = tmp_path / "vals.ply"
        _write_ascii_ply(ply, xyz)

        result_xyz, _ = parse_ply_file(ply)
        np.testing.assert_allclose(result_xyz, xyz, atol=1e-5)


# ─── Binary PLY tests ────────────────────────────────────────────────────────


class TestParsePlyBinary:
    def test_binary_little_endian_round_trip(self, tmp_path):
        """Binary LE PLY data round-trips correctly."""
        xyz = np.array([[1.5, 2.5, 3.5], [4.0, 5.0, 6.0]], dtype=np.float32)
        ply = tmp_path / "binary.ply"
        _write_binary_ply(ply, xyz)

        result_xyz, result_colors = parse_ply_file(ply)

        assert result_xyz is not None
        assert result_xyz.shape == (2, 3)
        assert result_colors is None
        np.testing.assert_allclose(result_xyz, xyz, atol=1e-5)

    def test_binary_many_points(self, tmp_path):
        """Binary PLY with 1000 points parses correctly."""
        rng = np.random.default_rng(7)
        xyz = rng.standard_normal((1000, 3)).astype(np.float32)
        ply = tmp_path / "big_binary.ply"
        _write_binary_ply(ply, xyz)

        result_xyz, _ = parse_ply_file(ply)

        assert result_xyz is not None
        assert result_xyz.shape == (1000, 3)
        np.testing.assert_allclose(result_xyz, xyz, atol=1e-5)


# ─── Error / edge-case tests ─────────────────────────────────────────────────


class TestParsePlyErrors:
    def test_missing_file_returns_none(self, tmp_path):
        """Missing file → (None, None) with no exception."""
        xyz, colors = parse_ply_file(tmp_path / "nonexistent.ply")
        assert xyz is None
        assert colors is None

    def test_corrupt_file_returns_none(self, tmp_path):
        """Non-PLY content → (None, None) with no exception."""
        bad = tmp_path / "corrupt.ply"
        bad.write_bytes(b"this is not a ply file at all\x00\xff")
        xyz, colors = parse_ply_file(bad)
        assert xyz is None
        assert colors is None

    def test_empty_file_returns_none(self, tmp_path):
        """Empty file → (None, None)."""
        empty = tmp_path / "empty.ply"
        empty.write_bytes(b"")
        xyz, colors = parse_ply_file(empty)
        assert xyz is None
        assert colors is None

    def test_ply_no_xyz_returns_none(self, tmp_path):
        """PLY with properties but no x/y/z → (None, None)."""
        no_xyz = tmp_path / "no_xyz.ply"
        no_xyz.write_text(
            "ply\nformat ascii 1.0\n"
            "element vertex 2\n"
            "property float intensity\n"
            "end_header\n"
            "1.0\n2.0\n"
        )
        xyz, colors = parse_ply_file(no_xyz)
        assert xyz is None
        assert colors is None

    def test_zero_vertex_count_returns_none(self, tmp_path):
        """PLY with element vertex 0 → (None, None)."""
        zero = tmp_path / "zero.ply"
        zero.write_text(
            "ply\nformat ascii 1.0\n"
            "element vertex 0\n"
            "property float x\n"
            "property float y\n"
            "property float z\n"
            "end_header\n"
        )
        xyz, colors = parse_ply_file(zero)
        assert xyz is None
        assert colors is None

    def test_binary_truncated_returns_none(self, tmp_path):
        """Truncated binary PLY (insufficient data bytes) → (None, None)."""
        ply = tmp_path / "trunc.ply"
        header = (
            "ply\nformat binary_little_endian 1.0\n"
            "element vertex 100\n"
            "property float x\nproperty float y\nproperty float z\n"
            "end_header\n"
        ).encode("ascii")
        ply.write_bytes(header + b"\x00" * 4)   # far too few bytes
        xyz, colors = parse_ply_file(ply)
        assert xyz is None
        assert colors is None
