"""
Raster generation: convert dense point cloud to DTM and DSM rasters.

DTM/DSM: PDAL writers.gdal (readers.las -> writers.gdal). GDAL does not read LAS
directly in many builds; using PDAL avoids "dense.las not recognized" errors.
GDAL used only for raster finishing (gdal_translate, gdaladdo), reprojection, validation.
"""

import json
import math
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from mapfree.geospatial.rasterizer import rasterize

log = logging.getLogger(__name__)

# ASPRS LAS classification: 2 = ground (from classify_ground)
GROUND_CLASS = 2
DEFAULT_NODATA = -9999.0
DTM_RAW_SUFFIX = "_dtm_raw.tif"


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


def _point_count_and_bounds_from_pdal(
    input_las: Path,
) -> Tuple[int, float, float, float, float]:
    """Get (point_count, minx, maxx, miny, maxy) from pdal info --metadata."""
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
    minx, maxx, miny, maxy = bounds

    count = meta.get("count")
    if count is not None:
        try:
            n = int(count)
        except (TypeError, ValueError):
            n = 0
    else:
        n = 0
    return (n, minx, maxx, miny, maxy)


def estimate_resolution(
    las_path: Path | str,
    min_resolution: float = 0.01,
    max_resolution: float = 2.0,
    target_points_per_cell: float = 4.0,
) -> float:
    """
    Estimate DTM resolution from bounding box and point density.

    resolution = sqrt(area / (point_count / target_points_per_cell))
    Clamped to [min_resolution, max_resolution].
    """
    las_path = Path(las_path)
    if not las_path.exists():
        raise RuntimeError("estimate_resolution: input does not exist: %s" % las_path)
    count, minx, maxx, miny, maxy = _point_count_and_bounds_from_pdal(las_path)
    area = (maxx - minx) * (maxy - miny)
    if area <= 0 or count <= 0:
        return min_resolution
    cells = max(1, count / target_points_per_cell)
    res = math.sqrt(area / cells)
    res = max(min_resolution, min(max_resolution, res))
    log.info(
        "estimate_resolution: %s -> %.4f (count=%d, area=%.2f)",
        las_path, res, count, area,
    )
    return res


def _run_pdal_dsm_pipeline(
    input_las: Path,
    dsm_raw_tif: Path,
    resolution: float,
    nodata: float,
    timeout: int,
) -> None:
    """Run PDAL pipeline: readers.las -> writers.gdal (output_type=max) -> DSM GeoTIFF.

    Uses PDAL so GDAL never reads LAS directly (avoids 'dense.las not recognized').
    """
    pipeline: Dict[str, Any] = {
        "pipeline": [
            str(input_las.resolve()),
            {
                "type": "writers.gdal",
                "filename": str(dsm_raw_tif.resolve()),
                "output_type": "max",
                "resolution": resolution,
                "nodata": nodata,
                "dimension": "Z",
                "gdaldriver": "GTiff",
                "data_type": "float",
            },
        ]
    }
    import tempfile
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
            cwd=str(input_las.parent),
        )
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "pdal pipeline failed").strip()
            raise RuntimeError("generate_dsm PDAL writers.gdal failed: %s" % msg)
        if not dsm_raw_tif.exists():
            raise RuntimeError(
                "generate_dsm: PDAL did not create output: %s" % dsm_raw_tif
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def generate_dsm(
    input_las: Path | str,
    output_tif: Path | str,
    resolution: float,
    timeout: int = 3600,
) -> Path:
    """
    Generate a DSM (digital surface model) GeoTIFF from a LAS point cloud.

    Uses PDAL writers.gdal (output_type=max), not gdal_grid on LAS, so that
    GDAL never reads LAS directly (avoids ERROR 4: 'dense.las' not recognized).

    Raises RuntimeError if input is missing, pdal fails, or output is not created.
    Returns output_tif path.
    """
    input_las = Path(input_las)
    output_tif = Path(output_tif)
    if not input_las.exists():
        raise RuntimeError("generate_dsm: input does not exist: %s" % input_las)
    if input_las.stat().st_size == 0:
        raise RuntimeError("generate_dsm: input LAS is empty: %s" % input_las)
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    out_dir = output_tif.parent
    dsm_raw_tif = out_dir / (output_tif.stem + "_dsm_raw.tif")
    if dsm_raw_tif == output_tif:
        dsm_raw_tif = out_dir / "._dsm_raw.tif"

    _run_pdal_dsm_pipeline(
        input_las, dsm_raw_tif, resolution, DEFAULT_NODATA, timeout
    )

    translate_cmd = [
        "gdal_translate", "-q",
        "-ot", "Float32",
        "-a_nodata", str(DEFAULT_NODATA),
        str(dsm_raw_tif.resolve()),
        str(output_tif.resolve()),
    ]
    try:
        result = subprocess.run(
            translate_cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("generate_dsm gdal_translate failed: %s" % e) from e
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdal_translate failed"
        raise RuntimeError("generate_dsm gdal_translate failed: %s" % msg.strip())
    if not output_tif.exists():
        raise RuntimeError("generate_dsm: output was not created: %s" % output_tif)
    try:
        dsm_raw_tif.unlink(missing_ok=True)
    except OSError:
        pass
    log.info(
        "generate_dsm: %s -> %s (res=%s, PDAL writers.gdal)",
        input_las, output_tif, resolution,
    )
    return output_tif


def _run_pdal_dtm_pipeline(
    ground_las: Path,
    dtm_raw_tif: Path,
    resolution: float,
    nodata: float,
    timeout: int,
) -> None:
    """Run PDAL pipeline: readers.las -> writers.gdal (output_type=min) -> dtm_raw.tif."""
    pipeline = {
        "pipeline": [
            str(ground_las.resolve()),
            {
                "type": "writers.gdal",
                "filename": str(dtm_raw_tif.resolve()),
                "output_type": "min",
                "resolution": resolution,
                "nodata": nodata,
                "dimension": "Z",
                "gdaldriver": "GTiff",
                "data_type": "float",
            },
        ]
    }
    import tempfile
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
            cwd=str(ground_las.parent),
        )
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "pdal pipeline failed").strip()
            raise RuntimeError("generate_dtm PDAL writers.gdal failed: %s" % msg)
        if not dtm_raw_tif.exists():
            raise RuntimeError(
                "generate_dtm: PDAL did not create output: %s" % dtm_raw_tif
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def generate_dtm(
    ground_las: Path | str,
    output_tif: Path | str,
    resolution: float,
    timeout: int = 3600,
    epsg: Optional[int] = None,
    nodata: float = DEFAULT_NODATA,
) -> Path:
    """
    Generate a DTM (digital terrain model) GeoTIFF from ground-class LAS.

    Uses PDAL writers.gdal (no gdal_grid): readers.las -> writers.gdal (min Z)
    -> dtm_raw.tif, then gdal_translate (Float32, nodata, CRS), then gdaladdo
    overviews. Expects ground_las to be output of classify_ground (Classification=2).

    Args:
        ground_las: Path to classified LAS (ground = 2).
        output_tif: Output GeoTIFF path.
        resolution: Ground sampling distance (units per pixel).
        timeout: Subprocess timeout in seconds.
        epsg: Optional EPSG code to embed CRS (e.g. 32648).
        nodata: NoData value for output (default -9999).

    Returns:
        output_tif path.
    """
    ground_las = Path(ground_las)
    output_tif = Path(output_tif)
    if not ground_las.exists():
        raise RuntimeError("generate_dtm: input does not exist: %s" % ground_las)
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    out_dir = output_tif.parent
    dtm_raw_tif = out_dir / (output_tif.stem + DTM_RAW_SUFFIX)
    if dtm_raw_tif == output_tif:
        dtm_raw_tif = out_dir / ("._dtm_raw.tif")

    _run_pdal_dtm_pipeline(
        ground_las, dtm_raw_tif, resolution, nodata, timeout
    )

    translate_cmd = [
        "gdal_translate", "-q",
        "-ot", "Float32",
        "-a_nodata", str(nodata),
        str(dtm_raw_tif.resolve()),
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
            dtm_raw_tif.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("generate_dtm gdal_translate failed: %s" % e) from e
    try:
        dtm_raw_tif.unlink(missing_ok=True)
    except OSError:
        pass
    if r2.returncode != 0:
        raise RuntimeError(
            "generate_dtm gdal_translate failed: %s"
            % (r2.stderr or r2.stdout or "unknown").strip()
        )
    if not output_tif.exists():
        raise RuntimeError("generate_dtm: output was not created: %s" % output_tif)

    # Overviews
    try:
        subprocess.run(
            ["gdaladdo", "-q", "-r", "average", str(output_tif.resolve()), "2", "4", "8", "16"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        log.warning("generate_dtm: gdaladdo overviews failed or timed out; continuing")

    log.info(
        "generate_dtm: %s -> %s (res=%s, class=%d)",
        ground_las, output_tif, resolution, GROUND_CLASS,
    )
    return output_tif


def _gdalinfo_json(path: Path, timeout: int = 30) -> Optional[dict]:
    """Return gdalinfo -json as a dict, or None on failure."""
    try:
        result = subprocess.run(
            ["gdalinfo", "-json", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, json.JSONDecodeError):
        return None


def validate_dtm(path: Path | str) -> Dict[str, Any]:
    """
    Validate a DTM raster: CRS exists, pixel size > 0, not all nodata, bbox sane.

    Returns dict with keys: valid (bool), crs_exists, pixel_size_positive,
    not_all_nodata, bbox_sane, [message].
    Raises RuntimeError if file does not exist or is not readable.
    """
    path = Path(path)
    if not path.exists():
        raise RuntimeError("validate_dtm: file does not exist: %s" % path)
    info = _gdalinfo_json(path)
    if not info:
        raise RuntimeError("validate_dtm: gdalinfo failed for %s" % path)

    result = {
        "valid": True,
        "crs_exists": False,
        "pixel_size_positive": False,
        "not_all_nodata": False,
        "bbox_sane": False,
    }

    cs = info.get("coordinateSystem") or {}
    wkt = cs.get("wkt") if isinstance(cs, dict) else None
    result["crs_exists"] = bool(wkt and str(wkt).strip())
    if not result["crs_exists"]:
        result["valid"] = False
        result["message"] = "CRS missing"
        return result

    gt = info.get("geoTransform")
    if not gt or len(gt) < 6:
        result["valid"] = False
        result["message"] = "GeoTransform missing or invalid"
        return result
    res_x = abs(float(gt[1]))
    res_y = abs(float(gt[5]))
    result["pixel_size_positive"] = res_x > 0 and res_y > 0
    if not result["pixel_size_positive"]:
        result["valid"] = False
        result["message"] = "Pixel size not positive"
        return result

    bands = info.get("bands") or []
    if not bands:
        result["valid"] = False
        result["not_all_nodata"] = False
        result["message"] = "No bands"
        return result
    band0 = bands[0] if isinstance(bands[0], dict) else {}
    nodata_val = band0.get("noDataValue")
    stats = band0.get("statistics") or {}
    min_val = stats.get("minimum")
    max_val = stats.get("maximum")
    if min_val is not None and max_val is not None:
        if nodata_val is not None and min_val == nodata_val and max_val == nodata_val:
            result["not_all_nodata"] = False
            result["valid"] = False
            result["message"] = "Raster is all nodata"
            return result
        result["not_all_nodata"] = True
    else:
        # No statistics (e.g. RGB ortho); assume data present
        result["not_all_nodata"] = True

    corners = info.get("cornerCoordinates") or {}
    ul = corners.get("upperLeft", [0, 0])
    lr = corners.get("lowerRight", [0, 0])
    try:
        xmin, ymin = min(ul[0], lr[0]), min(ul[1], lr[1])
        xmax, ymax = max(ul[0], lr[0]), max(ul[1], lr[1])
    except (TypeError, ValueError):
        result["bbox_sane"] = False
        result["valid"] = False
        result["message"] = "Invalid corner coordinates"
        return result
    extent_ok = (xmax - xmin) > 0 and (ymax - ymin) > 0
    finite = (
        math.isfinite(xmin) and math.isfinite(xmax)
        and math.isfinite(ymin) and math.isfinite(ymax)
    )
    result["bbox_sane"] = bool(extent_ok and finite)
    if not result["bbox_sane"]:
        result["valid"] = False
        result["message"] = "Bounding box invalid or degenerate"
        return result

    return result


__all__ = [
    "generate_dsm",
    "generate_dtm",
    "rasterize",
    "estimate_resolution",
    "validate_dtm",
    "DEFAULT_NODATA",
    "GROUND_CLASS",
]
