"""
Rasterization: convert point cloud or mesh to raster (DEM, DSM, etc.).
DSM via gdal_grid from LAS. Pure backend; no GUI.
"""

import json
import math
import subprocess
from pathlib import Path
from typing import Optional, Literal, Tuple

import logging

log = logging.getLogger(__name__)


def _bounds_from_pdal(input_las: Path) -> Tuple[float, float, float, float]:
    """Get (minx, maxx, miny, maxy) from pdal info --metadata."""
    result = subprocess.run(
        ["pdal", "info", str(input_las), "--metadata"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "pdal info failed: %s" % (result.stderr or result.stdout or "unknown").strip()
        )
    data = json.loads(result.stdout)
    meta = data.get("metadata") or {}

    def find_bounds(obj, depth=0):
        if depth > 20:
            return None
        if isinstance(obj, dict):
            if "minx" in obj and "maxx" in obj and "miny" in obj and "maxy" in obj:
                return (float(obj["minx"]), float(obj["maxx"]), float(obj["miny"]), float(obj["maxy"]))
            for v in obj.values():
                b = find_bounds(v, depth + 1)
                if b is not None:
                    return b
        return None

    bounds = find_bounds(meta)
    if bounds is None:
        minx = meta.get("minx")
        maxx = meta.get("maxx")
        miny = meta.get("miny")
        maxy = meta.get("maxy")
        if None in (minx, maxx, miny, maxy):
            raise RuntimeError("pdal info: could not find minx/maxx/miny/maxy in metadata")
        bounds = (float(minx), float(maxx), float(miny), float(maxy))
    return bounds


def generate_dsm(
    input_las: Path,
    output_tif: Path,
    resolution: float = 0.05,
    timeout: int = 3600,
) -> Path:
    """
    Generate a DSM (digital surface model) raster from a LAS point cloud using
    gdal_grid with inverse-distance interpolation. Bounds are taken from
    pdal info --metadata; raster size is computed from resolution.
    """
    input_las = Path(input_las)
    output_tif = Path(output_tif)
    if not input_las.exists():
        raise RuntimeError("generate_dsm: input does not exist: %s" % input_las)
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    minx, maxx, miny, maxy = _bounds_from_pdal(input_las)
    width = max(1, int(math.ceil((maxx - minx) / resolution)))
    height = max(1, int(math.ceil((maxy - miny) / resolution)))

    cmd = [
        "gdal_grid",
        "-zfield", "Z",
        "-a", "invdist:power=2.0:smoothing=1.0",
        "-txe", str(minx), str(maxx),
        "-tye", str(miny), str(maxy),
        "-outsize", str(width), str(height),
        str(input_las.resolve()),
        str(output_tif.resolve()),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdal_grid failed"
        raise RuntimeError("generate_dsm failed: %s" % msg.strip())
    if not output_tif.exists():
        raise RuntimeError("generate_dsm: output was not created: %s" % output_tif)
    log.info("generate_dsm: %s -> %s (res=%.2f, %dx%d)", input_las, output_tif, resolution, width, height)
    return output_tif


# ASPRS LAS classification: 2 = ground
GROUND_CLASS = 2


def generate_dtm(
    classified_las: Path,
    output_tif: Path,
    resolution: float = 0.05,
    timeout: int = 3600,
) -> Path:
    """
    Generate a DTM (digital terrain model) raster from a classified LAS point
    cloud using only ground points (Classification=2). Uses gdal_grid with
    -where "Classification=2" and inverse-distance interpolation. Bounds and
    raster size are derived from the point cloud and resolution.
    """
    classified_las = Path(classified_las)
    output_tif = Path(output_tif)
    if not classified_las.exists():
        raise RuntimeError("generate_dtm: input does not exist: %s" % classified_las)
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    minx, maxx, miny, maxy = _bounds_from_pdal(classified_las)
    width = max(1, int(math.ceil((maxx - minx) / resolution)))
    height = max(1, int(math.ceil((maxy - miny) / resolution)))

    cmd = [
        "gdal_grid",
        "-zfield", "Z",
        "-a", "invdist:power=2.0:smoothing=1.0",
        "-where", "Classification=%d" % GROUND_CLASS,
        "-txe", str(minx), str(maxx),
        "-tye", str(miny), str(maxy),
        "-outsize", str(width), str(height),
        str(classified_las.resolve()),
        str(output_tif.resolve()),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdal_grid failed"
        raise RuntimeError("generate_dtm failed: %s" % msg.strip())
    if not output_tif.exists():
        raise RuntimeError("generate_dtm: output was not created: %s" % output_tif)
    log.info(
        "generate_dtm: %s -> %s (res=%.2f, class=%d, %dx%d)",
        classified_las, output_tif, resolution, GROUND_CLASS, width, height,
    )
    return output_tif


def rasterize(
    input_path: Path,
    output_path: Optional[Path] = None,
    resolution: float = 1.0,
    product: Literal["dem", "dsm", "dtm"] = "dsm",
) -> Path:
    """
    Rasterize input (point cloud or mesh) to a grid.
    resolution: ground sampling distance (units per pixel).
    product: dem, dsm, or dtm.
    Returns path to output raster (e.g. .tif).
    """
    if output_path is None:
        output_path = Path(input_path).parent / f"{product}.tif"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("rasterize: %s -> %s (%s, res=%.2f)", input_path, output_path, product, resolution)
    # Stub: actual implementation would run rasterizer
    return output_path
