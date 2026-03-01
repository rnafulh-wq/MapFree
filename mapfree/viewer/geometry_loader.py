"""Geometry loader — load meshes and point clouds; return vertex buffers ready for OpenGL (VBO).

Uses pure Python + numpy only (no laspy/lazy loading or other heavy deps).
"""

from pathlib import Path
from typing import Any

import numpy as np


def _ensure_float32_3(arr: np.ndarray | None, n: int, default: tuple[float, float, float]) -> np.ndarray:
    """Return (n, 3) float32; create from default if arr is None or wrong shape."""
    if arr is not None and arr.shape == (n, 3):
        return np.asarray(arr, dtype=np.float32)
    out = np.empty((n, 3), dtype=np.float32)
    out[:] = default
    return out


def _build_vbo_interleaved(
    positions: np.ndarray,
    colors: np.ndarray,
    normals: np.ndarray,
) -> np.ndarray:
    """Build interleaved VBO: [x,y,z, r,g,b, nx,ny,nz] per vertex, (N, 9) float32."""
    n = len(positions)
    vbo = np.empty((n, 9), dtype=np.float32)
    vbo[:, 0:3] = positions
    vbo[:, 3:6] = colors
    vbo[:, 6:9] = normals
    return vbo


# -----------------------------------------------------------------------------
# PLY
# -----------------------------------------------------------------------------

def load_ply(file_path: str) -> dict[str, Any] | None:
    """Load a PLY file. Returns dict with VBO-ready arrays or None on failure.

    Returned keys:
      positions: (N, 3) float32
      normals: (N, 3) float32 or None
      colors: (N, 3) float32 in [0,1] or None
      indices: (M,) uint32 triangle indices or None
      vbo: (N, 9) float32 interleaved [pos, color, normal] for glBufferData
      ebo: (M,) uint32 or None for element buffer
    """
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".ply":
        return None
    data = path.read_bytes()
    try:
        out = _parse_ply(data)
    except Exception:
        return None
    if out is None or len(out["vertices"]) == 0:
        return None

    vertices = np.array(out["vertices"], dtype=np.float32)
    n = len(vertices)
    normals = _ensure_float32_3(
        np.array(out["normals"], dtype=np.float32) if out.get("normals") else None,
        n, (0.0, 1.0, 0.0),
    )
    colors = _ensure_float32_3(
        np.array(out["colors"], dtype=np.float32) if out.get("colors") else None,
        n, (0.7, 0.7, 0.7),
    )
    indices = np.array(out["indices"], dtype=np.uint32) if out.get("indices") else None

    vbo = _build_vbo_interleaved(vertices, colors, normals)
    return {
        "positions": vertices,
        "normals": normals,
        "colors": colors,
        "indices": indices,
        "vbo": vbo,
        "ebo": indices,
    }


def _parse_ply(data: bytes) -> dict[str, Any] | None:
    import struct
    text = data.decode("utf-8", errors="replace")
    lines = [s.strip() for s in text.splitlines()]
    if not lines or lines[0].lower() != "ply":
        return None

    fmt = "ascii"
    num_vertices = 0
    num_faces = 0
    vertex_props = []
    current_element = None
    i = 1
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith("format "):
            fmt = "ascii" if "ascii" in line.lower() else "binary"
        elif line.startswith("element vertex "):
            num_vertices = int(line.split()[-1])
            current_element = "vertex"
        elif line.startswith("element face "):
            num_faces = int(line.split()[-1])
            current_element = "face"
        elif line.startswith("property ") and current_element == "vertex":
            parts = line.split()
            if len(parts) >= 3:
                vertex_props.append((parts[2].lower(), parts[1]))
        elif line == "end_header":
            break

    v_x = v_y = v_z = v_nx = v_ny = v_nz = v_r = v_g = v_b = -1
    for idx, (name, _) in enumerate(vertex_props):
        if name == "x": v_x = idx
        elif name == "y": v_y = idx
        elif name == "z": v_z = idx
        elif name == "nx": v_nx = idx
        elif name == "ny": v_ny = idx
        elif name == "nz": v_nz = idx
        elif name in ("red", "r"): v_r = idx
        elif name in ("green", "g"): v_g = idx
        elif name in ("blue", "b"): v_b = idx
    if v_x < 0 or v_y < 0 or v_z < 0:
        return None

    vertices = []
    normals = [] if (v_nx >= 0 and v_ny >= 0 and v_nz >= 0) else None
    colors = [] if (v_r >= 0 and v_g >= 0 and v_b >= 0) else None

    header_end = data.find(b"end_header")
    if header_end < 0:
        return None
    header_end += len(b"end_header")
    while header_end < len(data) and data[header_end:header_end + 1] in (b"\n", b"\r"):
        header_end += 1

    if fmt == "ascii":
        ascii_body = data[header_end:].decode("utf-8", errors="replace")
        ascii_lines = [ln.split() for ln in ascii_body.splitlines() if ln.strip()]
        line_idx = 0
        for _ in range(num_vertices):
            if line_idx >= len(ascii_lines):
                break
            tok = ascii_lines[line_idx]
            line_idx += 1
            if len(tok) <= max(v_x, v_y, v_z):
                continue
            x, y, z = float(tok[v_x]), float(tok[v_y]), float(tok[v_z])
            vertices.append((x, y, z))
            if normals is not None and len(tok) > v_nz:
                normals.append((float(tok[v_nx]), float(tok[v_ny]), float(tok[v_nz])))
            if colors is not None and len(tok) > v_b:
                r, g, b = float(tok[v_r]), float(tok[v_g]), float(tok[v_b])
                if r > 1 or g > 1 or b > 1:
                    r, g, b = r / 255.0, g / 255.0, b / 255.0
                colors.append((r, g, b))
        indices = []
        for _ in range(num_faces):
            if line_idx >= len(ascii_lines):
                break
            tok = ascii_lines[line_idx]
            line_idx += 1
            if len(tok) < 4:
                continue
            n = int(tok[0])
            if n == 3:
                indices.extend([int(tok[1]), int(tok[2]), int(tok[3])])
            elif n == 4:
                indices.extend([int(tok[1]), int(tok[2]), int(tok[3]), int(tok[1]), int(tok[3]), int(tok[4])])
    else:
        vertex_stride = 4 * len(vertex_props)
        offset = header_end
        for _ in range(num_vertices):
            if offset + vertex_stride > len(data):
                break
            floats = struct.unpack_from(f"{len(vertex_props)}f", data, offset)
            offset += vertex_stride
            vertices.append((float(floats[v_x]), float(floats[v_y]), float(floats[v_z])))
            if normals is not None:
                normals.append((float(floats[v_nx]), float(floats[v_ny]), float(floats[v_nz])))
            if colors is not None:
                r, g, b = floats[v_r], floats[v_g], floats[v_b]
                if r > 1 or g > 1 or b > 1:
                    r, g, b = r / 255.0, g / 255.0, b / 255.0
                colors.append((r, g, b))
        indices = []
        for _ in range(num_faces):
            if offset >= len(data):
                break
            n = struct.unpack_from("B", data, offset)[0]
            offset += 1
            if n >= 3 and offset + n * 4 <= len(data):
                idxs = struct.unpack_from(f"{n}i", data, offset)
                offset += n * 4
                if n == 3:
                    indices.extend(idxs)
                else:
                    for k in range(1, n - 1):
                        indices.extend([idxs[0], idxs[k], idxs[k + 1]])

    return {
        "vertices": vertices,
        "normals": normals,
        "colors": colors,
        "indices": indices if indices else None,
    }


# -----------------------------------------------------------------------------
# LAS (ASPRS LiDAR, pure binary read)
# -----------------------------------------------------------------------------

def load_las(file_path: str) -> dict[str, Any] | None:
    """Load a LAS 1.0–1.2 point cloud. Returns dict with VBO-ready arrays or None.

    Returned keys: positions (N,3) float32, normals (N,3) float32 (dummy),
    colors (N,3) float32 if RGB in file else gray, indices None, vbo (N,9) float32, ebo None.
    """
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() not in (".las", ".las1", ".las2"):
        return None
    try:
        data = path.read_bytes()
    except Exception:
        return None
    if len(data) < 227:
        return None
    import struct
    # Public header block (little-endian)
    sig = data[0:4]
    if sig != b"LASF":
        return None
    offset_to_point = struct.unpack_from("<I", data, 96)[0]
    point_format = data[104]
    point_record_length = struct.unpack_from("<H", data, 105)[0]
    num_points = struct.unpack_from("<I", data, 107)[0]
    scale = struct.unpack_from("<ddd", data, 131)
    offset_xyz = struct.unpack_from("<ddd", data, 155)
    if offset_to_point + num_points * point_record_length > len(data):
        num_points = (len(data) - offset_to_point) // max(1, point_record_length)
    # Point format 0: 20 bytes. 1: 28 bytes (+GPS). 2: 26 bytes (+RGB at 20). 3: 34 bytes (+GPS + RGB at 28)
    has_rgb = point_format in (2, 3) and point_record_length >= 26
    rgb_offset = 20 if point_format == 2 else 28 if point_format == 3 else 0
    if has_rgb and point_record_length < rgb_offset + 6:
        has_rgb = False

    xs = np.empty(num_points, dtype=np.float64)
    ys = np.empty(num_points, dtype=np.float64)
    zs = np.empty(num_points, dtype=np.float64)
    if has_rgb:
        rs = np.empty(num_points, dtype=np.uint16)
        gs = np.empty(num_points, dtype=np.uint16)
        bs = np.empty(num_points, dtype=np.uint16)

    base = offset_to_point
    for i in range(num_points):
        o = base + i * point_record_length
        if o + 12 > len(data):
            break
        x, y, z = struct.unpack_from("<iii", data, o)
        xs[i] = x * scale[0] + offset_xyz[0]
        ys[i] = y * scale[1] + offset_xyz[1]
        zs[i] = z * scale[2] + offset_xyz[2]
        if has_rgb and o + rgb_offset + 6 <= len(data):
            rs[i], gs[i], bs[i] = struct.unpack_from("<HHH", data, o + rgb_offset)

    n = num_points
    positions = np.column_stack((xs, ys, zs)).astype(np.float32)
    normals = np.full((n, 3), (0.0, 1.0, 0.0), dtype=np.float32)
    if has_rgb:
        colors = np.column_stack((rs / 65535.0, gs / 65535.0, bs / 65535.0)).astype(np.float32)
    else:
        colors = np.full((n, 3), 0.7, dtype=np.float32)
    vbo = _build_vbo_interleaved(positions, colors, normals)
    return {
        "positions": positions,
        "normals": normals,
        "colors": colors,
        "indices": None,
        "vbo": vbo,
        "ebo": None,
    }


# -----------------------------------------------------------------------------
# OBJ
# -----------------------------------------------------------------------------

def load_obj(file_path: str) -> dict[str, Any] | None:
    """Load an OBJ mesh. Returns dict with VBO-ready arrays or None.

    Returned keys: positions (N,3), normals (N,3), colors (N,3) default gray,
    indices (M,) uint32 triangle indices, vbo (N,9) float32, ebo (M,) uint32.
    """
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".obj":
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    v_list = []
    vn_list = []
    vt_list = []
    faces = []  # list of (v_indices, vn_indices, vt_indices) per face

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "v":
            if len(parts) >= 4:
                v_list.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "vn":
            if len(parts) >= 4:
                vn_list.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "vt":
            if len(parts) >= 3:
                vt_list.append((float(parts[1]), float(parts[2])))
        elif parts[0] == "f":
            # f v1/vt1/vn1 v2/vt2/vn2 v3/vt3/vn3 [v4/...]
            face_verts = []
            face_norms = []
            for i in range(1, len(parts)):
                segs = parts[i].split("/")
                vi = int(segs[0]) - 1 if (segs and segs[0].strip()) else -1
                vti = int(segs[1]) - 1 if (len(segs) > 1 and segs[1].strip()) else -1
                vni = int(segs[2]) - 1 if (len(segs) > 2 and segs[2].strip()) else -1
                face_verts.append((vi, vni, vti))
            # Triangulate polygon
            for k in range(1, len(face_verts) - 1):
                faces.append((face_verts[0], face_verts[k], face_verts[k + 1]))

    if not v_list:
        return None

    # Build unique vertex key (v, vn, vt) -> index for expanded vertex array
    v_to_idx = {}
    positions = []
    normals = []
    indices = []
    default_n = (0.0, 1.0, 0.0)
    nv = len(v_list)
    nn = len(vn_list)

    for face in faces:
        for v_idx, vn_idx, _ in face:
            if v_idx < 0 or v_idx >= nv:
                continue
            key = (v_idx, vn_idx if 0 <= vn_idx < nn else -1)
            if key not in v_to_idx:
                idx = len(positions)
                v_to_idx[key] = idx
                positions.append(v_list[v_idx])
                normals.append(vn_list[vn_idx] if 0 <= vn_idx < nn else default_n)
            indices.append(v_to_idx[key])

    if not positions:
        return None

    positions = np.array(positions, dtype=np.float32)
    normals = np.array(normals, dtype=np.float32)
    n = len(positions)
    colors = np.full((n, 3), 0.7, dtype=np.float32)
    indices = np.array(indices, dtype=np.uint32)
    vbo = _build_vbo_interleaved(positions, colors, normals)
    return {
        "positions": positions,
        "normals": normals,
        "colors": colors,
        "indices": indices,
        "vbo": vbo,
        "ebo": indices,
    }


# -----------------------------------------------------------------------------
# Class API (backward compatible)
# -----------------------------------------------------------------------------

class GeometryLoader:
    """Load mesh and point cloud data; return VBO-ready numpy arrays."""

    @staticmethod
    def load_ply(file_path: str) -> dict[str, Any] | None:
        return load_ply(file_path)

    @staticmethod
    def load_las(file_path: str) -> dict[str, Any] | None:
        return load_las(file_path)

    @staticmethod
    def load_obj(file_path: str) -> dict[str, Any] | None:
        return load_obj(file_path)

    @staticmethod
    def load_point_cloud(file_path: str) -> dict[str, Any] | None:
        path = Path(file_path)
        if not path.exists():
            return None
        suf = path.suffix.lower()
        if suf == ".ply":
            return load_ply(file_path)
        if suf in (".las", ".las1", ".las2"):
            return load_las(file_path)
        return None

    @staticmethod
    def load_mesh(file_path: str) -> dict[str, Any] | None:
        path = Path(file_path)
        if not path.exists():
            return None
        suf = path.suffix.lower()
        if suf == ".ply":
            return load_ply(file_path)
        if suf == ".obj":
            return load_obj(file_path)
        return None
