"""
Orthorectification: project imagery onto a DEM/DTM to produce orthophoto.

Removes perspective and relief distortion so the output has uniform scale
and can be used as a map. Uses DTM/DSM and georeferenced images; gdalwarp-based.
Pure backend; no GUI.
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from mapfree.geospatial.orthomosaic import (
    _gdalinfo_json,
    _is_georeferenced,
    _raster_info,
    build_orthomosaic,
)
from mapfree.geospatial.raster import validate_dtm

log = logging.getLogger(__name__)


def _image_size_from_gdal(path: Path) -> Optional[tuple[int, int]]:
    """Return (width, height) from gdalinfo -json, or None."""
    info = _gdalinfo_json(path)
    if not info:
        return None
    try:
        w = int(info.get("size", [0, 0])[0])
        h = int(info.get("size", [0, 0])[1])
        if w > 0 and h > 0:
            return (w, h)
    except (TypeError, ValueError, IndexError):
        pass
    return None


def prepare_georeferenced_vrts(
    images_dir: Path | str,
    dtm_tif: Path | str,
    output_dir: Path | str,
    epsg: Optional[int] = None,
    res_xy: Optional[float] = None,
) -> Optional[Path]:
    """
    Create VRTs with geotransform from EXIF GPS so gdalwarp can use them.
    images_dir: folder of JPGs; dtm_tif: for CRS/res if not given; output_dir: where to write VRTs.
    Returns output_dir if at least one VRT was written, else None.
    """
    images_dir = Path(images_dir)
    dtm_tif = Path(dtm_tif)
    output_dir = Path(output_dir)
    if not images_dir.is_dir() or not dtm_tif.exists():
        return None
    dtm_info = _raster_info(dtm_tif)
    if not dtm_info:
        return None
    if epsg is None:
        epsg = _epsg_from_raster(dtm_tif)
    if res_xy is None:
        res_xy = (float(dtm_info["res_x"]) + float(dtm_info["res_y"])) / 2.0
    try:
        from mapfree.geospatial.exif_reader import extract_gps_from_images
        from mapfree.geospatial.georef import _gps_to_utm
    except ImportError:
        return None
    gps_list = extract_gps_from_images(str(images_dir))
    if not gps_list:
        log.debug(
            "prepare_georeferenced_vrts: no GPS in EXIF di %s",
            images_dir,
        )
        return None
    if epsg is None:
        try:
            from mapfree.geospatial.georef import get_utm_epsg_from_gps
            rec = gps_list[0]
            epsg = get_utm_epsg_from_gps(
                float(rec.get("lat", 0)), float(rec.get("lon", 0))
            )
            log.debug(
                "prepare_georeferenced_vrts: EPSG from GPS (DTM has no CRS): %s",
                epsg,
            )
        except (ImportError, IndexError, KeyError, TypeError, ValueError):
            pass
    if epsg is None:
        log.debug(
            "prepare_georeferenced_vrts: tidak ada EPSG (DTM tanpa CRS dan gagal dari GPS)",
        )
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for rec in gps_list:
        fname = rec.get("filename")
        if not fname:
            continue
        img_path = images_dir / fname
        if not img_path.is_file():
            continue
        size = _image_size_from_gdal(img_path)
        if not size:
            continue
        w, h = size
        lat = float(rec.get("lat", 0))
        lon = float(rec.get("lon", 0))
        alt = float(rec.get("alt") or 0)
        utm = _gps_to_utm(lat, lon, alt, epsg)
        if not utm:
            continue
        east, north, _ = utm
        ulx = east - (w / 2.0) * res_xy
        uly = north + (h / 2.0) * res_xy
        vrt_path = output_dir / (img_path.stem + ".vrt")
        src = str(img_path.resolve())
        bands_xml = "".join(
            '  <VRTRasterBand dataType="Byte" band="%d">\n'
            '    <SimpleSource>\n'
            '      <SourceFilename relativeToVRT="0">%s</SourceFilename>\n'
            '      <SourceBand>%d</SourceBand>\n'
            '    </SimpleSource>\n'
            '  </VRTRasterBand>\n' % (b, src, b)
            for b in (1, 2, 3)
        )
        vrt_content = (
            '<VRTDataset rasterXSize="%d" rasterYSize="%d">\n'
            '  <SRS>EPSG:%d</SRS>\n'
            '  <GeoTransform>%.12g, %.12g, 0, %.12g, 0, -%.12g</GeoTransform>\n'
            "%s"
            '</VRTDataset>\n'
        ) % (w, h, epsg, ulx, res_xy, uly, res_xy, bands_xml)
        try:
            vrt_path.write_text(vrt_content, encoding="utf-8")
            count += 1
        except OSError:
            continue
    if count == 0:
        log.debug(
            "prepare_georeferenced_vrts: tidak ada VRT terbentuk (gdalinfo/utm gagal untuk semua gambar)",
        )
        return None
    log.info("prepare_georeferenced_vrts: wrote %d VRTs to %s", count, output_dir)
    return output_dir

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


def finalize_orthophoto(
    path: Path | str,
    target_epsg: int,
    output_path: Optional[Path | str] = None,
    timeout: int = 3600,
) -> Path:
    """
    Reproject orthophoto to target_epsg, apply tiling + compression, add overviews,
    then validate. Uses gdalwarp (reprojection), gdal_translate (tiling, compression),
    gdaladdo (overviews). Returns path to finalized raster.

    If output_path is None, writes to a file in the same directory with suffix
    _epsg<target_epsg>.tif and returns that path.
    """
    path = Path(path)
    if not path.exists():
        raise RuntimeError("finalize_orthophoto: file does not exist: %s" % path)
    if output_path is None:
        output_path = path.parent / ("%s_epsg%d.tif" % (path.stem, target_epsg))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mapfree_ortho_") as tmp:
        tmp_dir = Path(tmp)
        warped = tmp_dir / "warped.tif"
        cmd_warp = [
            "gdalwarp",
            "-t_srs", "EPSG:%d" % target_epsg,
            "-r", "near",
            "-of", "GTiff",
            "-co", "TILED=YES",
            "-co", "BIGTIFF=IF_SAFER",
            "-overwrite",
            str(path.resolve()),
            str(warped),
        ]
        result = subprocess.run(
            cmd_warp,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            msg = result.stderr or result.stdout or "gdalwarp failed"
            raise RuntimeError("finalize_orthophoto gdalwarp failed: %s" % msg.strip())
        if not warped.exists():
            raise RuntimeError("finalize_orthophoto: warped output was not created")

        translated = tmp_dir / "translated.tif"
        cmd_translate = [
            "gdal_translate",
            "-q",
            "-co", "TILED=YES",
            "-co", "COMPRESS=LZW",
            "-co", "BIGTIFF=IF_SAFER",
            str(warped),
            str(translated),
        ]
        r2 = subprocess.run(
            cmd_translate,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r2.returncode != 0:
            msg = r2.stderr or r2.stdout or "gdal_translate failed"
            raise RuntimeError("finalize_orthophoto gdal_translate failed: %s" % msg.strip())

        subprocess.run(
            ["gdaladdo", "-q", "-r", "average", str(translated), "2", "4", "8", "16"],
            capture_output=True,
            text=True,
            timeout=120,
        )

        shutil.copy2(translated, output_path)

    v = validate_dtm(output_path)
    if not v.get("valid", True):
        log.warning("finalize_orthophoto: validation reported: %s", v.get("message", v))
    log.info(
        "finalize_orthophoto: %s -> %s (EPSG:%d)",
        path, output_path, target_epsg,
    )
    return output_path


__all__ = [
    "build_orthomosaic",
    "finalize_orthophoto",
    "generate_orthophoto",
    "prepare_georeferenced_vrts",
]
