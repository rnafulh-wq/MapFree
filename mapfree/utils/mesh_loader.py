"""OBJ and PLY mesh loader — returns (vertices, faces, vertex_colors) arrays.

All face lists are triangulated: quads are split into two triangles.

Typical usage::

    from mapfree.utils.mesh_loader import load_mesh

    verts, faces, colors = load_mesh("/path/to/model.ply")
    if verts is not None:
        print(f"Loaded {len(faces):,} faces")
"""
import logging
import struct
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("mapfree.mesh_loader")

# (vertices (N,3) float32, faces (M,3) int32, colors (N,4) float32 | None)
MeshResult = Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]

_PLY_DTYPE: dict = {
    "char": np.int8,    "int8": np.int8,
    "uchar": np.uint8,  "uint8": np.uint8,
    "short": np.int16,  "int16": np.int16,
    "ushort": np.uint16, "uint16": np.uint16,
    "int": np.int32,    "int32": np.int32,
    "uint": np.uint32,  "uint32": np.uint32,
    "float": np.float32, "float32": np.float32,
    "double": np.float64, "float64": np.float64,
}
_PLY_SIZE = {np.int8: 1, np.uint8: 1, np.int16: 2, np.uint16: 2,
             np.int32: 4, np.uint32: 4, np.float32: 4, np.float64: 8}


def load_mesh(path: str | Path) -> MeshResult:
    """Load an OBJ or PLY mesh file.

    Args:
        path: Path to a ``.obj`` or ``.ply`` file.

    Returns:
        A tuple ``(vertices, faces, colors)`` where:

        * ``vertices`` — shape ``(N, 3)`` float32.
        * ``faces``    — shape ``(M, 3)`` int32 (triangulated).
        * ``colors``   — shape ``(N, 4)`` float32 RGBA in ``[0, 1]``, or ``None``.

        All three entries are ``None`` on any parse error.
    """
    path = Path(path)
    if not path.is_file():
        logger.warning("Mesh file not found: %s", path)
        return None, None, None
    try:
        suffix = path.suffix.lower()
        if suffix == ".obj":
            return _load_obj(path)
        elif suffix == ".ply":
            return _load_ply_mesh(path)
        else:
            logger.warning("Unsupported mesh format: %s", suffix)
            return None, None, None
    except Exception as exc:
        logger.warning("Failed to load mesh '%s': %s", path, exc)
        return None, None, None


# ---------------------------------------------------------------------------
# OBJ loader
# ---------------------------------------------------------------------------

def _load_obj(path: Path) -> MeshResult:
    """Parse a Wavefront OBJ file."""
    verts: list[list[float]] = []
    faces: list[list[int]] = []

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            ln = raw_line.strip()
            if ln.startswith("v "):
                parts = ln.split()
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif ln.startswith("f "):
                face_indices = []
                for tok in ln.split()[1:]:
                    # token can be "v", "v/vt", "v/vt/vn", "v//vn"
                    idx = int(tok.split("/")[0])
                    # OBJ is 1-indexed; negative = relative to current count
                    if idx > 0:
                        face_indices.append(idx - 1)
                    else:
                        face_indices.append(len(verts) + idx)
                # Triangulate (fan decomposition for polygons)
                for i in range(1, len(face_indices) - 1):
                    faces.append([face_indices[0], face_indices[i], face_indices[i + 1]])

    if not verts or not faces:
        raise ValueError("OBJ has no vertices or faces")

    v_arr = np.array(verts, dtype=np.float32)
    f_arr = np.array(faces, dtype=np.int32)
    return v_arr, f_arr, None


# ---------------------------------------------------------------------------
# PLY mesh loader
# ---------------------------------------------------------------------------

def _load_ply_mesh(path: Path) -> MeshResult:
    """Parse a PLY file returning vertices, faces, and optional per-vertex colours."""
    with open(path, "rb") as fh:
        raw = fh.read()

    header_end = raw.find(b"end_header")
    if header_end < 0:
        raise ValueError("Missing 'end_header' in PLY file")
    header_text = raw[:header_end].decode("ascii", errors="replace")
    data_start = header_end + len("end_header")
    while data_start < len(raw) and raw[data_start] in (ord("\n"), ord("\r")):
        data_start += 1

    lines = [ln.strip() for ln in header_text.splitlines()]
    if not lines or lines[0] != "ply":
        raise ValueError("Not a valid PLY file")

    fmt = "ascii"
    elements: list[dict] = []
    current_elem: dict | None = None

    for ln in lines:
        if ln.startswith("format "):
            parts = ln.split()
            fmt = parts[1] if len(parts) > 1 else "ascii"
        elif ln.startswith("element "):
            parts = ln.split()
            name = parts[1]
            count = int(parts[2]) if len(parts) > 2 else 0
            current_elem = {"name": name, "count": count, "props": [], "list_props": []}
            elements.append(current_elem)
        elif ln.startswith("property list") and current_elem is not None:
            # property list <count_type> <index_type> <name>
            parts = ln.split()
            if len(parts) >= 5:
                current_elem["list_props"].append({
                    "count_type": parts[2],
                    "index_type": parts[3],
                    "name": parts[4],
                })
        elif ln.startswith("property ") and current_elem is not None:
            parts = ln.split()
            if len(parts) >= 3 and parts[1] != "list":
                current_elem["props"].append({"name": parts[2].lower(), "type": parts[1].lower()})

    vertex_elem = next((e for e in elements if e["name"] == "vertex"), None)
    face_elem = next((e for e in elements if e["name"] == "face"), None)

    if vertex_elem is None or vertex_elem["count"] == 0:
        raise ValueError("PLY has no vertices")
    if face_elem is None or face_elem["count"] == 0:
        raise ValueError("PLY has no face element")
    if not any(p["name"] == "x" for p in vertex_elem["props"]):
        raise ValueError("PLY vertex element has no 'x' property")

    endian = "<" if "little" in fmt else ">"
    body = raw[data_start:]
    offset = 0

    # --- read vertex block ---
    v_dtype_fields = [(p["name"], _PLY_DTYPE.get(p["type"], np.float32))
                      for p in vertex_elem["props"]]
    v_dt = np.dtype(v_dtype_fields).newbyteorder(endian if fmt != "ascii" else "=")
    vertex_count = vertex_elem["count"]

    if fmt == "ascii":
        body_text = body.decode("ascii", errors="replace").splitlines()
        v_arr_s, body_text = _ascii_read_vertices(body_text, vertex_count, vertex_elem["props"])
        face_lines = body_text[:face_elem["count"]]
    else:
        v_bytes = vertex_count * v_dt.itemsize
        vertices_raw = np.frombuffer(body[:v_bytes], dtype=v_dt).copy()
        offset = v_bytes

    # --- extract xyz + colours (binary) ---
    if fmt != "ascii":
        verts = np.stack([
            vertices_raw["x"], vertices_raw["y"], vertices_raw["z"]
        ], axis=1).astype(np.float32)

        r_name = next((n for n in ("red", "r") if n in vertices_raw.dtype.names), None)
        g_name = next((n for n in ("green", "g") if n in vertices_raw.dtype.names), None)
        b_name = next((n for n in ("blue", "b") if n in vertices_raw.dtype.names), None)
        colors = _extract_colors_from_struct(vertices_raw, r_name, g_name, b_name)

        # --- read face block (binary) ---
        faces = _read_binary_faces(body[offset:], face_elem, endian)
    else:
        verts = v_arr_s
        colors = None   # ASCII colour extraction skipped for mesh (unusual)
        faces = _read_ascii_faces(face_lines, face_elem)

    if faces is None or len(faces) == 0:
        raise ValueError("PLY mesh has no parseable triangles")

    return verts, faces, colors


def _ascii_read_vertices(
    lines: list[str], count: int, props: list[dict]
) -> tuple[np.ndarray, list[str]]:
    dtype_fields = [(p["name"], _PLY_DTYPE.get(p["type"], np.float32)) for p in props]
    dt = np.dtype(dtype_fields)
    out = np.empty(count, dtype=dt)
    for i in range(min(count, len(lines))):
        vals = lines[i].split()
        for j, p in enumerate(props):
            if j < len(vals):
                out[p["name"]][i] = vals[j]

    verts = np.stack([out["x"], out["y"], out["z"]], axis=1).astype(np.float32)
    return verts, lines[count:]


def _extract_colors_from_struct(
    data: np.ndarray,
    r_name: str | None, g_name: str | None, b_name: str | None,
) -> Optional[np.ndarray]:
    if not (r_name and g_name and b_name):
        return None
    r = data[r_name].astype(np.float32)
    g = data[g_name].astype(np.float32)
    b = data[b_name].astype(np.float32)
    if data.dtype[r_name] == np.uint8:
        r, g, b = r / 255.0, g / 255.0, b / 255.0
    a = np.ones(len(data), dtype=np.float32)
    return np.stack([r, g, b, a], axis=1).astype(np.float32)


def _read_binary_faces(body: bytes, face_elem: dict, endian: str) -> Optional[np.ndarray]:
    """Read binary PLY face list — handles list properties (uchar count + int/uint indices)."""
    count = face_elem["count"]
    if not face_elem["list_props"]:
        return None

    lp = face_elem["list_props"][0]
    count_np = _PLY_DTYPE.get(lp["count_type"], np.uint8)
    index_np = _PLY_DTYPE.get(lp["index_type"], np.int32)
    count_size = _PLY_SIZE.get(count_np, 1)
    index_size = _PLY_SIZE.get(index_np, 4)
    endian_char = "<" if endian == "<" else ">"
    count_fmt = endian_char + {1: "B", 2: "H", 4: "I"}[count_size]
    index_fmt = endian_char + {1: "b", 2: "h", 4: "i", "uint": "I"}.get(index_size, "i")
    if index_np in (np.uint32,):
        index_fmt = endian_char + "I"

    triangles: list[list[int]] = []
    pos = 0
    for _ in range(count):
        if pos >= len(body):
            break
        n = struct.unpack_from(count_fmt, body, pos)[0]
        pos += count_size
        if pos + n * index_size > len(body):
            break
        indices = [struct.unpack_from(index_fmt, body, pos + j * index_size)[0]
                   for j in range(n)]
        pos += n * index_size
        # Fan triangulation
        for i in range(1, len(indices) - 1):
            triangles.append([indices[0], indices[i], indices[i + 1]])

    if not triangles:
        return None
    return np.array(triangles, dtype=np.int32)


def _read_ascii_faces(lines: list[str], face_elem: dict) -> Optional[np.ndarray]:
    """Read ASCII PLY face lines."""
    count = face_elem["count"]
    triangles: list[list[int]] = []
    for i in range(min(count, len(lines))):
        parts = lines[i].split()
        if not parts:
            continue
        n = int(parts[0])
        indices = [int(parts[j + 1]) for j in range(n) if j + 1 < len(parts)]
        for j in range(1, len(indices) - 1):
            triangles.append([indices[0], indices[j], indices[j + 1]])
    if not triangles:
        return None
    return np.array(triangles, dtype=np.int32)
