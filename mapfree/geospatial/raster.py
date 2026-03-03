"""
Raster generation: convert dense point cloud to DTM and DSM rasters.

DTM (Digital Terrain Model): ground surface only.
DSM (Digital Surface Model): top-of-surface (ground + buildings, vegetation).
Uses PDAL/gdal_grid for LAS input. Outputs GeoTIFF (Float32, nodata, CRS). Pure backend; no GUI.
"""

import json
import math
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

from mapfree.geospatial.rasterizer import rasterize

log = logging.getLogger(__name__)

# ASPRS LAS classification: 2 = ground (from classify_ground)
GROUND_CLASS = 2
DEFAULT_NODATA = -9999.0


def _bounds_from_pdal(input_las: Path) -> Tuple[float, float, float, float]:
    """Get (minx, maxx, miny, maxy) from pdal info --metadata."""
    try:
        result = subprocess.run(
            ["pdal", "info", str(input_las), "--metadata"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("pdal info failed: %s" % e) from e
    if result.returncode != 0:
        raise RuntimeError(
            "pdal info failed: %s"
            % (result.stderr or result.stdout or "unknown").strip()
        )
    data = json.loads(result.stdout)
    meta = data.get("metadata") or {}

    def find_bounds(obj, depth: int = 0):
        if depth > 20:
            return None
        if isinstance(obj, dict):
            if "minx" in obj and "maxx" in obj and "miny" in obj and "maxy" in obj:
                return (
                    float(obj["minx"]),
                    float(obj["maxx"]),
                    float(obj["miny"]),
                    float(obj["maxy"]),
                )
            for v in obj.values():
                b = find_bounds(v, depth + 1)
                if b is not None:
                    return b
        return None

    bounds = find_bounds(meta)
    if bounds is None:
        minx, maxx = meta.get("minx"), meta.get("maxx")
        miny, maxy = meta.get("miny"), meta.get("maxy")
        if None in (minx, maxx, miny, maxy):
            raise RuntimeError(
                "pdal info: could not find minx/maxx/miny/maxy in metadata"
            )
        bounds = (float(minx), float(maxx), float(miny), float(maxy))
    return bounds


def generate_dsm(
    input_las: Path | str,
    output_tif: Path | str,
    resolution: float,
    timeout: int = 3600,
) -> Path:
    """
    Generate a DSM (digital surface model) GeoTIFF from a LAS point cloud.

    Uses gdal_grid with inverse-distance interpolation (-zfield Z,
    -a invdist:power=2.0:smoothing=1.0). Bounds are taken from pdal info
    --metadata; raster size is computed from resolution (units per pixel).

    Raises RuntimeError if input is missing, pdal/gdal_grid fail, or output
    is not created. Returns output_tif path.
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
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("generate_dsm failed: %s" % e) from e
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdal_grid failed"
        raise RuntimeError("generate_dsm failed: %s" % msg.strip())
    if not output_tif.exists():
        raise RuntimeError("generate_dsm: output was not created: %s" % output_tif)
    log.info(
        "generate_dsm: %s -> %s (res=%s, %dx%d)",
        input_las, output_tif, resolution, width, height,
    )
    return output_tif


def generate_dtm(
    ground_las: Path | str,
    output_tif: Path | str,
    resolution: float,
    timeout: int = 3600,
    epsg: Optional[int] = None,
    nodata: float = DEFAULT_NODATA,
) -> Path:
    """
    Generate a DTM (digital terrain model) GeoTIFF from ground-class LAS only.

    Expects ground_las to be the output of classify_ground (Classification=2).
    Uses gdal_grid then gdal_translate for Float32, nodata, and optional CRS.
    Bounds from pdal info --metadata; raster size from resolution.

    Args:
        ground_las: Path to classified LAS (ground = 2).
        output_tif: Output GeoTIFF path.
        resolution: Ground sampling distance (units per pixel).
        timeout: Subprocess timeout in seconds.
        epsg: Optional EPSG code to embed CRS (e.g. 32648).
        nodata: NoData value for output (default -9999).

    Returns:
        output_tif path.

    Raises:
        RuntimeError: If input missing, pdal/gdal fail, or output not created.
    """
    ground_las = Path(ground_las)
    output_tif = Path(output_tif)
    if not ground_las.exists():
        raise RuntimeError("generate_dtm: input does not exist: %s" % ground_las)
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    minx, maxx, miny, maxy = _bounds_from_pdal(ground_las)
    width = max(1, int(math.ceil((maxx - minx) / resolution)))
    height = max(1, int(math.ceil((maxy - miny) / resolution)))

    grid_out = output_tif.parent / "._dtm_tmp.tif"

    cmd = [
        "gdal_grid",
        "-zfield", "Z",
        "-a", "invdist:power=2.0:smoothing=1.0",
        "-where", "Classification=%d" % GROUND_CLASS,
        "-txe", str(minx), str(maxx),
        "-tye", str(miny), str(maxy),
        "-outsize", str(width), str(height),
        str(ground_las.resolve()),
        str(grid_out.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("generate_dtm gdal_grid failed: %s" % e) from e
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdal_grid failed"
        raise RuntimeError("generate_dtm failed: %s" % msg.strip())
    if not grid_out.exists():
        raise RuntimeError("generate_dtm: output was not created: %s" % grid_out)

    # Finalize: Float32, nodata, optional CRS
    translate_cmd = [
        "gdal_translate", "-q",
        "-ot", "Float32",
        "-a_nodata", str(nodata),
        str(grid_out.resolve()),
        str(output_tif.resolve()),
    ]
    if epsg is not None:
        translate_cmd.insert(-2, "-a_srs")
        translate_cmd.insert(-2, "EPSG:%d" % epsg)
    try:
        r2 = subprocess.run(
            translate_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        try:
            grid_out.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("generate_dtm gdal_translate failed: %s" % e) from e
    try:
        grid_out.unlink(missing_ok=True)
    except OSError:
        pass
    if r2.returncode != 0:
        raise RuntimeError(
            "generate_dtm gdal_translate failed: %s"
            % (r2.stderr or r2.stdout or "unknown").strip()
        )

    log.info(
        "generate_dtm: %s -> %s (res=%s, class=%d, %dx%d)",
        ground_las, output_tif, resolution, GROUND_CLASS, width, height,
    )
    return output_tif


__all__ = [
    "generate_dsm",
    "generate_dtm",
    "rasterize",
]
