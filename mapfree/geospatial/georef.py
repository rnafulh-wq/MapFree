"""
Georeferencing: assign CRS and optional GCP-based transform to sparse/dense output.
PLY to LAS conversion via PDAL; GPS-based UTM injection for geographic DSM/DTM.
Pure backend; no GUI.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict

import logging

log = logging.getLogger(__name__)


def get_utm_epsg_from_gps(lat: float, lon: float) -> int:
    """
    Return EPSG code for UTM zone containing (lat, lon).
    North: 32600 + zone (e.g. 32651). South: 32700 + zone (e.g. 32751).
    """
    zone = int((lon + 180) / 6) + 1
    zone = max(1, min(60, zone))
    if lat >= 0:
        return 32600 + zone
    return 32700 + zone


def find_fused_ply(output_dir: Path) -> Optional[Path]:
    """
    Locate fused.ply under output_dir. Tries known paths then rglob fallback.

    Candidates: 02_dense/fused.ply, 02_dense/dense/fused.ply, dense/fused.ply.
    """
    output_dir = Path(output_dir)
    candidates = [
        output_dir / "02_dense" / "fused.ply",
        output_dir / "02_dense" / "dense" / "fused.ply",
        output_dir / "dense" / "fused.ply",
    ]
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            log.info("fused.ply ditemukan: %s", candidate)
            return candidate
    found = list(output_dir.rglob("fused.ply"))
    if found:
        p = next((f for f in found if f.is_file() and f.stat().st_size > 0), found[0])
        log.info("fused.ply ditemukan via rglob: %s", p)
        return p
    log.warning("fused.ply tidak ditemukan di %s", output_dir)
    return None


def _gps_to_utm(
    lat: float, lon: float, alt: float, epsg: int
) -> Optional[Tuple[float, float, float]]:
    """Convert (lat, lon, alt) WGS84 to (easting, northing, elevation) in UTM (epsg)."""
    try:
        from osgeo import osr
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)
        utm_srs = osr.SpatialReference()
        utm_srs.ImportFromEPSG(epsg)
        transform = osr.CoordinateTransformation(wgs84, utm_srs)
        pt = transform.TransformPoint(lon, lat, alt)
        # GDAL TransformPoint returns (x,y,z) or (x,y,z,t); unpack 3 only
        if len(pt) < 3:
            return None
        east, north, up = float(pt[0]), float(pt[1]), float(pt[2])
        return (east, north, up)
    except Exception as e:
        log.warning("_gps_to_utm failed (epsg=%s): %s", epsg, e)
        return None


def _get_ply_bounds(ply_path: Path, timeout: int = 60) -> Tuple[float, float, float, float, float, float]:
    """
    Get (minx, maxx, miny, maxy, minz, maxz) from PLY using pdal info --summary.

    PDAL reads both ASCII and binary_little_endian PLY; no manual parsing.
    Raises RuntimeError if pdal info fails or bounds cannot be read.
    """
    result = subprocess.run(
        ["pdal", "info", str(ply_path), "--summary"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "non-zero exit")[:200]
        raise RuntimeError("pdal info gagal untuk %s: %s" % (ply_path, err))
    data = json.loads(result.stdout)
    try:
        bounds = data["summary"]["bounds"]
        return (
            float(bounds["minx"]),
            float(bounds["maxx"]),
            float(bounds["miny"]),
            float(bounds["maxy"]),
            float(bounds["minz"]),
            float(bounds["maxz"]),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError("pdal info: bounds tidak valid untuk %s: %s" % (ply_path, e)) from e


def georeference_point_cloud(
    ply_path: Path,
    las_path: Path,
    gps_center: Tuple[float, float, float],
    database_path: Optional[Path] = None,
    timeout: int = 3600,
) -> Path:
    """
    Convert PLY to LAS with UTM CRS by translating local COLMAP coords to UTM.

    gps_center: (lat, lon, alt) WGS84 from EXIF (e.g. first image). Used as origin
    so the point cloud is placed in the correct geographic location.
    """
    ply_path = Path(ply_path)
    las_path = Path(las_path)
    if not ply_path.exists():
        raise RuntimeError("georeference_point_cloud: PLY does not exist: %s" % ply_path)
    las_path.parent.mkdir(parents=True, exist_ok=True)

    lat, lon, alt = gps_center
    epsg = get_utm_epsg_from_gps(lat, lon)
    utm_center = _gps_to_utm(lat, lon, alt, epsg)
    if utm_center is None:
        raise RuntimeError(
            "georeference_point_cloud: could not convert GPS to UTM (epsg=%s)" % epsg
        )
    east, north, up = utm_center

    minx, maxx, miny, maxy, minz, maxz = _get_ply_bounds(ply_path, timeout=timeout)
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    cz = (minz + maxz) / 2.0
    tx = east - cx
    ty = north - cy
    tz = up - cz

    pipeline: Dict[str, Any] = {
        "pipeline": [
            {"type": "readers.ply", "filename": str(ply_path.resolve())},
            {
                "type": "filters.transformation",
                "matrix": (
                    "1 0 0 %f "
                    "0 1 0 %f "
                    "0 0 1 %f "
                    "0 0 0 1" % (tx, ty, tz)
                ),
            },
            {
                "type": "writers.las",
                "filename": str(las_path.resolve()),
                "a_srs": "EPSG:%d" % epsg,
                "scale_x": 0.01,
                "scale_y": 0.01,
                "scale_z": 0.01,
            },
        ]
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(pipeline, f, indent=2)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ["pdal", "pipeline", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "pdal pipeline failed").strip()
            raise RuntimeError("georeference_point_cloud failed: %s" % msg)
        if not las_path.exists():
            raise RuntimeError("georeference_point_cloud: output was not created: %s" % las_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    log.info(
        "georeference_point_cloud: %s -> %s (EPSG:%d, origin UTM %.2f, %.2f, %.2f)",
        ply_path, las_path, epsg, east, north, up,
    )
    return las_path


# Event names for pipeline integration
EVENT_STAGE_STARTED = "geospatial_stage_started"
EVENT_STAGE_COMPLETED = "geospatial_stage_completed"


def convert_ply_to_las(
    input_ply: Path,
    output_las: Path,
    event_bus: Optional[Any] = None,
    timeout: int = 3600,
) -> Path:
    """
    Convert PLY point cloud to LAS using: pdal translate input.ply output.las
    Raises RuntimeError on failure. If event_bus is provided (has .emit(name, data)),
    emits geospatial_stage_started and geospatial_stage_completed.
    """
    input_ply = Path(input_ply)
    output_las = Path(output_las)
    if not input_ply.exists():
        raise RuntimeError("convert_ply_to_las: input does not exist: %s" % input_ply)
    output_las.parent.mkdir(parents=True, exist_ok=True)

    payload_start = {"stage": "convert_ply_to_las", "input": str(input_ply), "output": str(output_las)}
    if event_bus is not None and getattr(event_bus, "emit", None):
        event_bus.emit(EVENT_STAGE_STARTED, payload_start)

    try:
        result = subprocess.run(
            ["pdal", "translate", str(input_ply), str(output_las)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            msg = result.stderr or result.stdout or "pdal translate failed"
            raise RuntimeError("convert_ply_to_las failed: %s" % msg.strip())
    except subprocess.TimeoutExpired:
        raise RuntimeError("convert_ply_to_las timed out after %s seconds" % timeout)
    except FileNotFoundError:
        raise RuntimeError("convert_ply_to_las: pdal not found. Install PDAL and ensure it is on PATH.")

    payload_done = {"stage": "convert_ply_to_las", "output": str(output_las)}
    if event_bus is not None and getattr(event_bus, "emit", None):
        event_bus.emit(EVENT_STAGE_COMPLETED, payload_done)

    log.info("convert_ply_to_las: %s -> %s", input_ply, output_las)
    return output_las


def georeference(
    sparse_or_dense_path: Path,
    crs: str = "EPSG:4326",
    gcps: Optional[List[Tuple[float, float, float, float, float]]] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Apply CRS and optional GCP transform to model at sparse_or_dense_path.
    gcps: list of (x, y, z, lon, lat) or (x, y, lon, lat) for 2D.
    Returns path to georeferenced output (default: same dir, suffix _georef).
    """
    if output_path is None:
        output_path = Path(sparse_or_dense_path) / "_georef"
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    log.info("georeference: %s -> %s (crs=%s)", sparse_or_dense_path, output_path, crs)
    # Stub: actual implementation would write transformed model
    return output_path
