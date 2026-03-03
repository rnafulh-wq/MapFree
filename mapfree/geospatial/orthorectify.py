"""
Orthorectification: project imagery onto a DEM/DTM to produce orthophoto.

Removes perspective and relief distortion so the output has uniform scale
and can be used as a map. Uses DTM/DSM and georeferenced images; gdalwarp-based.
Pure backend; no GUI.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from mapfree.geospatial.orthomosaic import (
    _gdalinfo_json,
    _is_georeferenced,
    _raster_info,
    build_orthomosaic,
)

log = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".vrt"}


def _epsg_from_raster(path: Path) -> Optional[int]:
    """Get EPSG code from raster CRS if present in gdalinfo -json."""
    info = _gdalinfo_json(path)
    if not info:
        return None
    cs = info.get("coordinateSystem") or {}
    sid = cs.get("id")
    if isinstance(sid, dict) and sid.get("authority") == "EPSG":
        try:
            return int(sid.get("code", 0))
        except (TypeError, ValueError):
            pass
    return None


def generate_orthophoto(
    images_dir: Path | str,
    dtm_tif: Path | str,
    output_ortho: Path | str,
    timeout: int = 3600,
) -> Path:
    """
    Orthorectify all images in images_dir onto the DTM and write a georeferenced
    orthophoto using gdalwarp.

    Uses: gdalwarp -t_srs EPSG:<code> -r near -of GTiff -overwrite
    (plus extent/resolution from DTM). Output is georeferenced (e.g. orthophoto.tif).
    Requires at least one georeferenced image in images_dir.
    Raises RuntimeError if inputs are missing, DTM is invalid, or gdalwarp fails.
    """
    images_dir = Path(images_dir)
    dtm_tif = Path(dtm_tif)
    output_ortho = Path(output_ortho)
    if not images_dir.is_dir():
        raise RuntimeError(
            "generate_orthophoto: images directory does not exist: %s" % images_dir
        )
    if not dtm_tif.exists():
        raise RuntimeError("generate_orthophoto: DTM does not exist: %s" % dtm_tif)

    dtm_info = _raster_info(dtm_tif)
    if not dtm_info:
        raise RuntimeError(
            "generate_orthophoto: DTM is not a valid georeferenced raster: %s"
            % dtm_tif
        )

    candidates: List[Path] = [
        p for p in images_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    ]
    georef_images = [p for p in candidates if _is_georeferenced(p)]
    if not georef_images:
        raise RuntimeError("generate_orthophoto: no georeferenced images in %s" % images_dir)

    output_ortho.parent.mkdir(parents=True, exist_ok=True)
    xmin, ymin, xmax, ymax = dtm_info["extent"]
    res_x, res_y = dtm_info["res_x"], dtm_info["res_y"]
    epsg = _epsg_from_raster(dtm_tif)
    t_srs = "EPSG:%d" % epsg if epsg else dtm_info["srs_wkt"]

    cmd = [
        "gdalwarp",
        "-t_srs", t_srs,
        "-r", "near",
        "-of", "GTiff",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=IF_SAFER",
        "-te", str(xmin), str(ymin), str(xmax), str(ymax),
        "-tr", str(res_x), str(res_y),
        "-overwrite",
        *[str(p.resolve()) for p in georef_images],
        str(output_ortho.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("generate_orthophoto failed: %s" % e) from e
    if result.returncode != 0:
        msg = result.stderr or result.stdout or "gdalwarp failed"
        raise RuntimeError("generate_orthophoto failed: %s" % msg.strip())
    if not output_ortho.exists():
        raise RuntimeError(
            "generate_orthophoto: output was not created: %s" % output_ortho
        )
    log.info(
        "generate_orthophoto: %s + DTM %s -> %s (%d images)",
        images_dir, dtm_tif, output_ortho, len(georef_images),
    )
    return output_ortho


__all__ = [
    "build_orthomosaic",
    "generate_orthophoto",
]
