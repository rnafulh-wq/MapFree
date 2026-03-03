"""
Georeferencing: assign CRS and optional GCP-based transform to sparse/dense output.
PLY to LAS conversion via PDAL. Pure backend; no GUI.
"""

import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Any

import logging

log = logging.getLogger(__name__)

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
