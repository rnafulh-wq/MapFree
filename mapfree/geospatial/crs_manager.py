"""
CRS detection from EXIF GPS and reprojection of rasters/LAS.
No GUI dependency.
"""
import json
import math
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Any

import logging

from mapfree.utils.exif_order import _get_exif_gps_time

log = logging.getLogger(__name__)

# Image extensions for EXIF scan
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def _utm_zone_and_hemisphere(lon: float, lat: float) -> tuple[int, str]:
    """
    Compute UTM zone (1-60) and hemisphere ("N" or "S") from WGS84 lon, lat.
    """
    if lon < -180 or lon > 180 or lat < -90 or lat > 90:
        raise ValueError("Longitude or latitude out of range")
    zone = int(math.floor((lon + 180) / 6)) + 1
    zone = max(1, min(60, zone))
    hemisphere = "N" if lat >= 0 else "S"
    return zone, hemisphere


def _utm_zone_to_epsg(zone: int, hemisphere: str) -> int:
    """
    Return EPSG code for UTM zone and hemisphere.
    North: EPSG 32600 + zone (e.g. 32648 for UTM 48N)
    South: EPSG 32700 + zone (e.g. 32748 for UTM 48S)
    """
    if hemisphere == "N":
        return 32600 + zone
    return 32700 + zone


class CRSManager:
    """Detect CRS from images and reproject rasters/LAS. No GUI dependency."""

    @staticmethod
    def detect_crs_from_images(images_dir: Path) -> Optional[int]:
        """
        Read EXIF GPS from the first image that has GPS. If found, detect UTM zone
        and hemisphere and return the corresponding EPSG code (e.g. 32648 or 32748).
        If no GPS is found in any image, return None.

        images_dir: directory containing images (e.g. JPG, PNG).
        """
        images_dir = Path(images_dir)
        if not images_dir.is_dir():
            log.warning("detect_crs_from_images: not a directory: %s", images_dir)
            return None

        paths = sorted(
            p for p in images_dir.iterdir()
            if p.is_file() and p.suffix in _IMAGE_EXTENSIONS
        )
        for path in paths:
            lat, lon, _ = _get_exif_gps_time(path)
            if lat == 0.0 and lon == 0.0:
                continue
            try:
                zone, hemisphere = _utm_zone_and_hemisphere(lon, lat)
                epsg = _utm_zone_to_epsg(zone, hemisphere)
                log.info(
                    "detect_crs_from_images: from %s (lat=%.4f, lon=%.4f) -> UTM %d%s -> EPSG:%d",
                    path.name, lat, lon, zone, hemisphere, epsg,
                )
                return epsg
            except ValueError as e:
                log.warning("detect_crs_from_images: invalid coordinates from %s: %s", path.name, e)
                continue
        log.info("detect_crs_from_images: no GPS found in %d images", len(paths))
        return None

    _PROGRESS_RE = re.compile(r"\b([0-9]{1,3})\b")

    @staticmethod
    def reproject_raster(
        input_tif: Path,
        output_tif: Path,
        target_epsg: int,
        timeout: int = 3600,
        event_bus: Optional[Any] = None,
    ) -> Path:
        """
        Reproject a raster to target CRS using gdalwarp with -progress.
        Captures stdout/stderr, parses percentage, and emits "reprojection_progress"
        on event_bus when provided. Raises RuntimeError on failure.
        """
        input_tif = Path(input_tif)
        output_tif = Path(output_tif)
        if not input_tif.exists():
            raise RuntimeError("reproject_raster: input file does not exist: %s" % input_tif)
        output_tif.parent.mkdir(parents=True, exist_ok=True)

        srs = "EPSG:%d" % target_epsg
        cmd = [
            "gdalwarp",
            "-progress",
            "-t_srs", srs,
            "-overwrite",
            str(input_tif.resolve()),
            str(output_tif.resolve()),
        ]

        def emit_progress(pct: int):
            if event_bus is not None and 0 <= pct <= 100:
                try:
                    event_bus.emit("reprojection_progress", pct)
                except Exception:
                    pass

        def read_stderr(stream, lines_out):
            for line in iter(stream.readline, ""):
                lines_out.append(line)
                for m in CRSManager._PROGRESS_RE.finditer(line):
                    try:
                        pct = int(m.group(1))
                        if 0 <= pct <= 100:
                            emit_progress(pct)
                    except ValueError:
                        pass

        def drain(stream):
            for _ in iter(stream.readline, ""):
                pass

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            stderr_list: list[str] = []
            err_reader = threading.Thread(
                target=read_stderr, args=(proc.stderr, stderr_list), daemon=True
            )
            out_reader = threading.Thread(target=drain, args=(proc.stdout,), daemon=True)
            err_reader.start()
            out_reader.start()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise RuntimeError(
                    "reproject_raster failed: gdalwarp timed out after %d seconds. "
                    "Check input size and target CRS." % timeout
                )
            err_reader.join(timeout=2.0)
            out_reader.join(timeout=1.0)
            stderr_lines = stderr_list
            returncode = proc.returncode
        except FileNotFoundError:
            raise RuntimeError(
                "reproject_raster failed: gdalwarp not found. "
                "Install GDAL and ensure gdalwarp is on PATH."
            )

        if returncode != 0:
            msg = "".join(stderr_lines).strip() or "gdalwarp failed"
            raise RuntimeError(
                "reproject_raster failed (exit %d): %s" % (returncode, msg)
            )
        if not output_tif.exists():
            raise RuntimeError("reproject_raster failed: output was not created: %s" % output_tif)
        emit_progress(100)
        log.info("reproject_raster: %s -> %s (EPSG:%d)", input_tif, output_tif, target_epsg)
        return output_tif

    @staticmethod
    def reproject_las(
        input_las: Path,
        output_las: Path,
        target_epsg: int,
        timeout: int = 3600,
    ) -> Path:
        """
        Reproject a LAS point cloud to target CRS using a PDAL pipeline with
        filters.reprojection. Raises RuntimeError with a clear message if reprojection fails.
        """
        input_las = Path(input_las)
        output_las = Path(output_las)
        if not input_las.exists():
            raise RuntimeError("reproject_las: input file does not exist: %s" % input_las)
        output_las.parent.mkdir(parents=True, exist_ok=True)

        out_srs = "EPSG:%d" % target_epsg
        pipeline = {
            "pipeline": [
                str(input_las.resolve()),
                {
                    "type": "filters.reprojection",
                    "out_srs": out_srs,
                },
                str(output_las.resolve()),
            ],
        }
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
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
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "reproject_las failed: pdal pipeline timed out after %d seconds. "
                "Check input size and target CRS." % timeout
            )
        except FileNotFoundError:
            raise RuntimeError(
                "reproject_las failed: pdal not found. "
                "Install PDAL and ensure it is on PATH."
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "pdal pipeline failed").strip()
            raise RuntimeError(
                "reproject_las failed (exit %d): %s" % (result.returncode, msg)
            )
        if not output_las.exists():
            raise RuntimeError("reproject_las failed: output was not created: %s" % output_las)
        log.info("reproject_las: %s -> %s (EPSG:%d)", input_las, output_las, target_epsg)
        return output_las
