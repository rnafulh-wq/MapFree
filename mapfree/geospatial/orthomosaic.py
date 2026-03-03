"""
Orthomosaic generation: project imagery onto DEM/DSM to produce ortho image.
Simplified gdalwarp-based orthophoto. Pure backend; no GUI.
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

import logging

log = logging.getLogger(__name__)

# Common raster extensions
_IMAGE_EXTENSIONS = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".vrt"}


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
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return None


def _is_georeferenced(path: Path) -> bool:
    """True if the raster has a coordinate system and non-identity geotransform."""
    info = _gdalinfo_json(path)
    if not info:
        return False
    cs = info.get("coordinateSystem")
    if not cs or not cs.get("wkt"):
        return False
    gt = info.get("geoTransform")
    if not gt or len(gt) < 6:
        return False
    # Identity/unreferenced: [0, 1, 0, 0, 0, 1]
    if gt[1] == 1.0 and gt[5] in (1.0, -1.0) and gt[2] == 0 and gt[4] == 0:
        return False
    return True


def _raster_info(path: Path) -> Optional[dict]:
    """
    Return dict with srs_wkt, extent (xmin, ymin, xmax, ymax), res_x, res_y.
    None if not a valid georeferenced raster.
    """
    info = _gdalinfo_json(path)
    if not info:
        return None
    cs = info.get("coordinateSystem")
    wkt = cs.get("wkt") if cs else None
    if not wkt:
        return None
    gt = info.get("geoTransform")
    if not gt or len(gt) < 6:
        return None
    ul = info.get("cornerCoordinates", {}).get("upperLeft", [0, 0])
    lr = info.get("cornerCoordinates", {}).get("lowerRight", [0, 0])
    xmin = min(ul[0], lr[0])
    xmax = max(ul[0], lr[0])
    ymin = min(ul[1], lr[1])
    ymax = max(ul[1], lr[1])
    res_x = abs(float(gt[1]))
    res_y = abs(float(gt[5]))
    if res_x <= 0 or res_y <= 0:
        return None
    return {
        "srs_wkt": wkt,
        "extent": (xmin, ymin, xmax, ymax),
        "res_x": res_x,
        "res_y": res_y,
    }


def generate_orthophoto(
    input_images_dir: Path,
    dtm_tif: Path,
    output_ortho: Path,
    timeout: int = 3600,
) -> Path:
    """
    Generate an orthophoto by warping georeferenced images in input_images_dir
    onto the DTM grid using gdalwarp. Output extent, resolution, and CRS match
    the DTM. Requires at least one georeferenced image.
    Raises RuntimeError with message 'Orthophoto requires georeferenced dataset.'
    if no georeferenced imagery is found.
    """
    input_images_dir = Path(input_images_dir)
    dtm_tif = Path(dtm_tif)
    output_ortho = Path(output_ortho)
    if not input_images_dir.is_dir():
        raise RuntimeError(
            "generate_orthophoto: input directory does not exist: %s" % input_images_dir
        )
    if not dtm_tif.exists():
        raise RuntimeError("generate_orthophoto: DTM does not exist: %s" % dtm_tif)

    dtm_info = _raster_info(dtm_tif)
    if not dtm_info:
        raise RuntimeError(
            "generate_orthophoto: DTM is not a valid georeferenced raster: %s" % dtm_tif
        )

    candidates: List[Path] = []
    for p in input_images_dir.iterdir():
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS:
            candidates.append(p)
    georef_images: List[Path] = [p for p in candidates if _is_georeferenced(p)]
    if not georef_images:
        raise RuntimeError("Orthophoto requires georeferenced dataset.")

    output_ortho.parent.mkdir(parents=True, exist_ok=True)
    xmin, ymin, xmax, ymax = dtm_info["extent"]
    res_x, res_y = dtm_info["res_x"], dtm_info["res_y"]
    srs_wkt = dtm_info["srs_wkt"]

    cmd = [
        "gdalwarp",
        "-te", str(xmin), str(ymin), str(xmax), str(ymax),
        "-tr", str(res_x), str(res_y),
        "-t_srs", srs_wkt,
        "-r", "bilinear",
        "-overwrite",
        *[str(p.resolve()) for p in georef_images],
        str(output_ortho.resolve()),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdalwarp failed"
        raise RuntimeError("generate_orthophoto failed: %s" % msg.strip())
    if not output_ortho.exists():
        raise RuntimeError(
            "generate_orthophoto: output was not created: %s" % output_ortho
        )
    log.info(
        "generate_orthophoto: %s + DTM %s -> %s (%d images)",
        input_images_dir, dtm_tif, output_ortho, len(georef_images),
    )
    return output_ortho


def build_orthomosaic(
    image_folder: Path,
    sparse_or_dense_path: Path,
    dem_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    resolution: float = 1.0,
) -> Path:
    """
    Build orthomosaic from images using sparse/dense model and optional DEM.
    If dem_path is None, use surface from sparse_or_dense_path.
    Returns path to orthomosaic (e.g. .tif).
    """
    if output_path is None:
        output_path = Path(sparse_or_dense_path).parent / "orthomosaic.tif"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log.info(
        "build_orthomosaic: images=%s, model=%s -> %s",
        image_folder,
        sparse_or_dense_path,
        output_path,
    )
    # Stub: actual implementation would run ortho pipeline
    return output_path
