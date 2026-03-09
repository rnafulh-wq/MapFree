"""COLMAP binary format I/O utilities.

Currently provides a parser for ``points3D.bin`` — the sparse point cloud
written by the COLMAP mapper.

Binary format reference: https://colmap.github.io/format.html#binary-file-format

::

    uint64  num_points3D
    For each point:
        uint64  point3D_id
        float64 x, y, z
        uint8   r, g, b
        float64 error
        uint64  track_length
        For each track element (track_length times):
            uint32  image_id
            uint32  point2D_idx

Typical usage::

    from mapfree.utils.colmap_io import read_points3d_bin

    xyz_rgb = read_points3d_bin("/project/sparse/0/points3D.bin")
    if xyz_rgb is not None:
        print(f"Loaded {len(xyz_rgb):,} sparse points")
"""
import logging
import struct
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

logger = logging.getLogger("mapfree.colmap_io")


def read_points3d_bin(path: str | Path) -> Optional[np.ndarray]:
    """Parse a COLMAP ``points3D.bin`` file.

    Args:
        path: Path to the ``points3D.bin`` file.

    Returns:
        Shape ``(N, 6)`` float32 array with columns ``[x, y, z, r, g, b]``
        where RGB is in ``[0, 255]``.  Returns ``None`` if the file does not
        exist or cannot be parsed.
    """
    path = Path(path)
    if not path.is_file():
        logger.debug("points3D.bin not found: %s", path)
        return None
    try:
        return _parse_points3d_bin(path)
    except Exception as exc:
        logger.warning("Failed to parse points3D.bin '%s': %s", path, exc)
        return None


def _parse_points3d_bin(path: Path) -> Optional[np.ndarray]:
    """Internal parser — reads the variable-length binary format."""
    with open(path, "rb") as fh:
        data = fh.read()

    if len(data) < 8:
        return None

    offset = 0
    (num_points,) = struct.unpack_from("<Q", data, offset)
    offset += 8

    if num_points == 0:
        return np.empty((0, 6), dtype=np.float32)

    # Pre-allocate output: x, y, z (float64 → float32), r, g, b (uint8 → float32)
    out = np.empty((num_points, 6), dtype=np.float32)

    for i in range(num_points):
        # point3D_id (uint64) + x,y,z (float64 each) + r,g,b (uint8 each)
        # + error (float64) + track_length (uint64)
        if offset + 43 > len(data):
            # Truncated — return what we have so far
            return out[:i] if i > 0 else None

        # Skip point3D_id (8 bytes)
        offset += 8
        x, y, z = struct.unpack_from("<ddd", data, offset)
        offset += 24
        r, g, b = struct.unpack_from("<BBB", data, offset)
        offset += 3
        # Skip error (8 bytes)
        offset += 8
        (track_length,) = struct.unpack_from("<Q", data, offset)
        offset += 8
        # Skip track data: each element = uint32 image_id + uint32 point2D_idx = 8 bytes
        offset += int(track_length) * 8

        out[i, 0] = x
        out[i, 1] = y
        out[i, 2] = z
        out[i, 3] = r
        out[i, 4] = g
        out[i, 5] = b

    return out


def read_points3d_txt(path: str | Path) -> Optional[np.ndarray]:
    """Parse a COLMAP ``points3D.txt`` file (ASCII format).

    Format (one point per line, after 3 header comment lines)::

        POINT3D_ID X Y Z R G B ERROR [TRACK: IMAGE_ID POINT2D_IDX ...]

    Args:
        path: Path to the ``points3D.txt`` file.

    Returns:
        Shape ``(N, 6)`` float32 array ``[x, y, z, r, g, b]`` or ``None``.
    """
    path = Path(path)
    if not path.is_file():
        return None
    try:
        rows: list[list[float]] = []
        with open(path, "r") as fh:
            for raw in fh:
                ln = raw.strip()
                if not ln or ln.startswith("#"):
                    continue
                parts = ln.split()
                if len(parts) < 8:
                    continue
                # parts[0]=id, [1]=X,[2]=Y,[3]=Z,[4]=R,[5]=G,[6]=B,[7]=err,...
                rows.append([
                    float(parts[1]), float(parts[2]), float(parts[3]),
                    float(parts[4]), float(parts[5]), float(parts[6]),
                ])
        if not rows:
            return None
        return np.array(rows, dtype=np.float32)
    except Exception as exc:
        logger.warning("Failed to parse points3D.txt '%s': %s", path, exc)
        return None


def read_images_binary(path: str | Path) -> Optional[List[dict[str, Any]]]:
    """Parse a COLMAP ``images.bin`` file (extrinsics: qvec, tvec per image).

    Binary format: num_images (uint64); per image: image_id (uint32),
    qvec 4*float64, tvec 3*float64, camera_id (uint32), name (str\\0),
    num_points2D (uint64), points2D (num_points2D x float64,float64,uint64).

    Args:
        path: Path to the ``images.bin`` file (e.g. sparse/0/images.bin).

    Returns:
        List of dicts with keys: image_id, qvec (4-tuple float), tvec (3-tuple
        float), camera_id, name (str). Returns None if file missing or parse fails.
    """
    path = Path(path)
    if not path.is_file():
        logger.debug("images.bin not found: %s", path)
        return None
    try:
        return _parse_images_bin(path)
    except Exception as exc:
        logger.warning("Failed to parse images.bin '%s': %s", path, exc)
        return None


def _parse_images_bin(path: Path) -> List[dict[str, Any]]:
    """Internal parser for COLMAP images.bin (little-endian)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 8:
        return []
    offset = 0
    (num_images,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    out: List[dict[str, Any]] = []
    for _ in range(num_images):
        if offset + 4 + 8 * 4 + 8 * 3 + 4 > len(data):
            break
        (image_id,) = struct.unpack_from("<I", data, offset)
        offset += 4
        qvec = struct.unpack_from("<dddd", data, offset)
        offset += 32
        tvec = struct.unpack_from("<ddd", data, offset)
        offset += 24
        (camera_id,) = struct.unpack_from("<I", data, offset)
        offset += 4
        end = data.index(b"\x00", offset)
        name = data[offset:end].decode("utf-8", errors="replace")
        offset = end + 1
        if offset + 8 > len(data):
            break
        (num_points2d,) = struct.unpack_from("<Q", data, offset)
        offset += 8
        offset += int(num_points2d) * (8 + 8 + 8)
        if offset > len(data):
            break
        out.append({
            "image_id": image_id,
            "qvec": qvec,
            "tvec": tvec,
            "camera_id": camera_id,
            "name": name,
        })
    return out
