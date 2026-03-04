"""Pure-numpy PLY file parser.

Supports ASCII, binary_little_endian, and binary_big_endian formats.
No external PLY library or Qt dependency required.

Typical usage::

    from mapfree.utils.ply_parser import parse_ply_file

    xyz, colors = parse_ply_file("/path/to/cloud.ply")
    if xyz is not None:
        print(f"Loaded {len(xyz):,} points")
"""
import logging
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

logger = logging.getLogger("mapfree.ply_parser")

# ---------------------------------------------------------------------------
# PLY type → numpy dtype mapping
# ---------------------------------------------------------------------------

_PLY_DTYPE: dict[str, Any] = {
    "char": np.int8,    "int8": np.int8,
    "uchar": np.uint8,  "uint8": np.uint8,
    "short": np.int16,  "int16": np.int16,
    "ushort": np.uint16, "uint16": np.uint16,
    "int": np.int32,    "int32": np.int32,
    "uint": np.uint32,  "uint32": np.uint32,
    "float": np.float32, "float32": np.float32,
    "double": np.float64, "float64": np.float64,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ply_file(
    path: str | Path,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Parse a PLY file and return ``(xyz, colors)`` numpy arrays.

    Supports ASCII, binary_little_endian, and binary_big_endian formats.
    Per-vertex colours are normalised to float32 in [0, 1].

    Args:
        path: Path to the ``.ply`` file.

    Returns:
        A tuple ``(xyz, colors)`` where:

        * ``xyz``    — shape ``(N, 3)`` float32.  ``None`` on parse error.
        * ``colors`` — shape ``(N, 4)`` float32 RGBA.  ``None`` when the file
          contains no colour properties (white is not assumed).

        Both entries are ``None`` when the file cannot be found or parsed.
    """
    path = Path(path)
    if not path.is_file():
        logger.warning("PLY file not found: %s", path)
        return None, None
    try:
        return _parse_ply(path)
    except Exception as exc:
        logger.warning("Failed to parse PLY '%s': %s", path, exc)
        return None, None


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

def _parse_ply(path: Path) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Parse PLY header then dispatch to ASCII or binary reader."""
    with open(path, "rb") as fh:
        raw = fh.read()

    # --- locate header end ------------------------------------------------
    header_end = raw.find(b"end_header")
    if header_end < 0:
        raise ValueError("Missing 'end_header' in PLY file")
    header_text = raw[:header_end].decode("ascii", errors="replace")
    data_start = header_end + len("end_header")
    while data_start < len(raw) and raw[data_start] in (ord("\n"), ord("\r")):
        data_start += 1
    body = raw[data_start:]

    # --- parse header lines -----------------------------------------------
    lines = [ln.strip() for ln in header_text.splitlines()]
    if not lines or lines[0] != "ply":
        raise ValueError("Not a valid PLY file (missing 'ply' magic)")

    fmt = "ascii"
    vertex_count = 0
    props: list[tuple[str, str]] = []   # (name, ply_type)
    in_vertex = False

    for ln in lines:
        if ln.startswith("format "):
            parts = ln.split()
            fmt = parts[1] if len(parts) > 1 else "ascii"
        elif ln.startswith("element vertex"):
            parts = ln.split()
            vertex_count = int(parts[2]) if len(parts) > 2 else 0
            in_vertex = True
        elif ln.startswith("element ") and "vertex" not in ln:
            in_vertex = False
        elif ln.startswith("property ") and in_vertex:
            parts = ln.split()
            if len(parts) >= 3 and parts[1] != "list":
                props.append((parts[2].lower(), parts[1].lower()))

    if vertex_count == 0:
        raise ValueError("PLY vertex_count is 0")
    if not any(p[0] == "x" for p in props):
        raise ValueError("PLY has no 'x' vertex property")

    # --- build numpy structured dtype -------------------------------------
    dtype_fields: list[tuple[str, Any]] = []
    for name, ply_type in props:
        np_type = _PLY_DTYPE.get(ply_type)
        if np_type is None:
            raise ValueError(f"Unknown PLY property type '{ply_type}'")
        dtype_fields.append((name, np_type))
    dt = np.dtype(dtype_fields)

    # --- read vertex data -------------------------------------------------
    if fmt == "ascii":
        vertices = _read_ascii(body, vertex_count, props)
    elif fmt in ("binary_little_endian", "binary_big_endian"):
        endian = "<" if "little" in fmt else ">"
        vertices = _read_binary(body, vertex_count, dt, endian)
    else:
        raise ValueError(f"Unsupported PLY format: '{fmt}'")

    # --- extract xyz ------------------------------------------------------
    xyz = np.stack(
        [vertices["x"], vertices["y"], vertices["z"]], axis=1
    ).astype(np.float32)

    # --- extract colours (optional) --------------------------------------
    r_name = next((n for n in ("red", "r") if n in vertices.dtype.names), None)
    g_name = next((n for n in ("green", "g") if n in vertices.dtype.names), None)
    b_name = next((n for n in ("blue", "b") if n in vertices.dtype.names), None)
    a_name = next((n for n in ("alpha", "a") if n in vertices.dtype.names), None)

    if r_name and g_name and b_name:
        r = vertices[r_name].astype(np.float32)
        g = vertices[g_name].astype(np.float32)
        b = vertices[b_name].astype(np.float32)
        if vertices.dtype[r_name] == np.uint8:
            r, g, b = r / 255.0, g / 255.0, b / 255.0
        if a_name is not None:
            a = vertices[a_name].astype(np.float32)
            if vertices.dtype[a_name] == np.uint8:
                a = a / 255.0
        else:
            a = np.ones(len(xyz), dtype=np.float32)
        colors: Optional[np.ndarray] = np.stack([r, g, b, a], axis=1).astype(np.float32)
    else:
        colors = None

    return xyz, colors


def _read_ascii(
    body: bytes,
    count: int,
    props: list[tuple[str, str]],
) -> np.ndarray:
    """Parse an ASCII PLY vertex block into a structured numpy array."""
    text = body.decode("ascii", errors="replace")
    raw_lines = text.splitlines()
    dtype_fields: list[tuple[str, Any]] = [
        (name, _PLY_DTYPE.get(ply_t, np.float32)) for name, ply_t in props
    ]
    dt = np.dtype(dtype_fields)
    out = np.empty(count, dtype=dt)
    for i in range(min(count, len(raw_lines))):
        vals = raw_lines[i].split()
        for j, (name, _) in enumerate(props):
            if j < len(vals):
                out[name][i] = vals[j]
    return out


def _read_binary(
    body: bytes,
    count: int,
    dt: np.dtype,
    endian: str,
) -> np.ndarray:
    """Parse a binary PLY vertex block using a numpy structured dtype."""
    native_dt = dt.newbyteorder(endian)
    expected = count * native_dt.itemsize
    if len(body) < expected:
        raise ValueError(
            f"Binary PLY body too short: need {expected} bytes, got {len(body)}"
        )
    return np.frombuffer(body[:expected], dtype=native_dt).copy()
