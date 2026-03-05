"""Tests for mapfree.utils.mesh_loader (pure numpy — no Qt required)."""
import struct
from pathlib import Path

import numpy as np

from mapfree.utils.mesh_loader import load_mesh


# ─── helpers ─────────────────────────────────────────────────────────────────


def _write_obj(path: Path, verts: np.ndarray, faces: np.ndarray) -> None:
    with open(path, "w") as fh:
        for v in verts:
            fh.write(f"v {v[0]} {v[1]} {v[2]}\n")
        for f in faces:
            # OBJ is 1-indexed
            fh.write(f"f {f[0]+1} {f[1]+1} {f[2]+1}\n")


def _write_ply_ascii_mesh(path: Path, verts: np.ndarray, faces: np.ndarray) -> None:
    header = (
        "ply\nformat ascii 1.0\n"
        f"element vertex {len(verts)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\n"
        "property list uchar int vertex_indices\n"
        "end_header\n"
    )
    with open(path, "w") as fh:
        fh.write(header)
        for v in verts:
            fh.write(f"{v[0]} {v[1]} {v[2]}\n")
        for f in faces:
            fh.write(f"3 {f[0]} {f[1]} {f[2]}\n")


def _write_ply_binary_mesh(path: Path, verts: np.ndarray, faces: np.ndarray) -> None:
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(verts)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\n"
        "property list uchar int vertex_indices\n"
        "end_header\n"
    ).encode("ascii")
    with open(path, "wb") as fh:
        fh.write(header)
        for v in verts:
            fh.write(struct.pack("<fff", float(v[0]), float(v[1]), float(v[2])))
        for f in faces:
            fh.write(struct.pack("<Biii", 3, int(f[0]), int(f[1]), int(f[2])))


# ─── sample geometry ─────────────────────────────────────────────────────────

_VERTS = np.array([
    [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 1.0, 0.0], [0.5, 0.5, 1.0]
], dtype=np.float32)

_FACES = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=np.int32)


# ─── OBJ tests ───────────────────────────────────────────────────────────────


class TestLoadOBJ:
    def test_valid_triangle_mesh(self, tmp_path):
        obj = tmp_path / "tetra.obj"
        _write_obj(obj, _VERTS, _FACES)
        v, f, c = load_mesh(str(obj))
        assert v is not None
        assert f is not None
        assert v.shape == (4, 3)
        assert f.shape == (4, 3)
        assert c is None

    def test_vertex_values(self, tmp_path):
        obj = tmp_path / "vert.obj"
        _write_obj(obj, _VERTS, _FACES)
        v, _, _ = load_mesh(str(obj))
        np.testing.assert_allclose(v, _VERTS, atol=1e-5)

    def test_quad_face_triangulated(self, tmp_path):
        """An OBJ quad face is split into 2 triangles."""
        obj = tmp_path / "quad.obj"
        with open(obj, "w") as fh:
            fh.write("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n")
            fh.write("f 1 2 3 4\n")   # quad → 2 triangles
        v, f, c = load_mesh(str(obj))
        assert f is not None
        assert len(f) == 2

    def test_obj_with_texture_coords(self, tmp_path):
        """OBJ with v/vt/vn format parses correctly."""
        obj = tmp_path / "textured.obj"
        with open(obj, "w") as fh:
            fh.write("v 0 0 0\nv 1 0 0\nv 0.5 1 0\n")
            fh.write("vt 0 0\nvt 1 0\nvt 0.5 1\n")
            fh.write("f 1/1 2/2 3/3\n")
        v, f, c = load_mesh(str(obj))
        assert v is not None and f is not None
        assert v.shape == (3, 3)
        assert f.shape == (1, 3)

    def test_missing_file_returns_none(self, tmp_path):
        v, f, c = load_mesh(str(tmp_path / "missing.obj"))
        assert v is None and f is None and c is None

    def test_empty_obj_returns_none(self, tmp_path):
        obj = tmp_path / "empty.obj"
        obj.write_text("# empty\n")
        v, f, c = load_mesh(str(obj))
        assert v is None and f is None and c is None


# ─── PLY mesh tests ──────────────────────────────────────────────────────────


class TestLoadPLYMesh:
    def test_ascii_ply_mesh(self, tmp_path):
        ply = tmp_path / "tetra.ply"
        _write_ply_ascii_mesh(ply, _VERTS, _FACES)
        v, f, c = load_mesh(str(ply))
        assert v is not None and f is not None
        assert v.shape == (4, 3)
        assert f.shape == (4, 3)

    def test_binary_ply_mesh(self, tmp_path):
        ply = tmp_path / "binary.ply"
        _write_ply_binary_mesh(ply, _VERTS, _FACES)
        v, f, c = load_mesh(str(ply))
        assert v is not None and f is not None
        assert v.shape == (4, 3)
        assert f.shape == (4, 3)
        np.testing.assert_allclose(v, _VERTS, atol=1e-5)

    def test_ply_face_indices_in_range(self, tmp_path):
        ply = tmp_path / "range.ply"
        _write_ply_ascii_mesh(ply, _VERTS, _FACES)
        v, f, c = load_mesh(str(ply))
        assert f is not None
        assert f.min() >= 0
        assert f.max() < len(v)

    def test_ply_no_faces_returns_none(self, tmp_path):
        ply = tmp_path / "nofaces.ply"
        ply.write_text(
            "ply\nformat ascii 1.0\n"
            "element vertex 3\n"
            "property float x\nproperty float y\nproperty float z\n"
            "end_header\n"
            "0 0 0\n1 0 0\n0 1 0\n"
        )
        v, f, c = load_mesh(str(ply))
        assert v is None and f is None and c is None

    def test_corrupt_ply_returns_none(self, tmp_path):
        ply = tmp_path / "corrupt.ply"
        ply.write_bytes(b"garbage\xff")
        v, f, c = load_mesh(str(ply))
        assert v is None and f is None and c is None

    def test_unsupported_format_returns_none(self, tmp_path):
        f_path = tmp_path / "model.stl"
        f_path.write_text("solid test\nendsolid test\n")
        v, f, c = load_mesh(str(f_path))
        assert v is None and f is None and c is None
