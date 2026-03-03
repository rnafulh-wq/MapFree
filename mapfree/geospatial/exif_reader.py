"""
Extract GPS and timestamp from image EXIF. Used for CRS detection and ordering.
"""
from pathlib import Path
from typing import Any

# EXIF tag numbers (PIL/ExifRead)
TAG_DATETIME_ORIGINAL = 36867
GPS_IFD = 0x8825
GPS_LAT_REF = 1
GPS_LAT = 2
GPS_LON_REF = 3
GPS_LON = 4
GPS_ALT_REF = 5
GPS_ALTITUDE = 6

_JPG_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}


def _rational_to_float(val: Any) -> float:
    """Convert EXIF rational (num, den) or Rational to float."""
    if val is None:
        return 0.0
    try:
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            d = val.denominator or 1
            return float(val.numerator) / float(d)
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            return float(val[0]) / float(val[1] or 1)
        return float(val)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _dms_to_decimal(dms: Any, ref: Any) -> float:
    """Convert EXIF DMS (deg, min, sec) and ref (N/S, E/W) to decimal degrees."""
    if not dms or len(dms) < 3:
        return 0.0
    try:
        deg = _rational_to_float(dms[0])
        min_ = _rational_to_float(dms[1])
        sec = _rational_to_float(dms[2])
        decimal = deg + min_ / 60.0 + sec / 3600.0
        if ref in ("S", "W", b"S", b"W"):
            decimal = -decimal
        return decimal
    except (TypeError, ValueError, IndexError):
        return 0.0


def _extract_gps_altitude(gps_ifd: dict) -> float | None:
    """Get GPS altitude in meters from GPS IFD. None if missing or invalid."""
    try:
        alt = gps_ifd.get(GPS_ALTITUDE)
        if alt is None:
            return None
        val = _rational_to_float(alt)
        ref = gps_ifd.get(GPS_ALT_REF, 0)
        if ref == 1:  # below sea level
            val = -val
        return val
    except Exception:
        return None


def _read_exif_for_file(path: Path) -> dict | None:
    """
    Read EXIF from one image. Return dict with lat, lon, alt, timestamp or None if no GPS.
    Does not raise; returns None on any error or missing GPS.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as im:
            exif = im.getexif() if hasattr(im, "getexif") else None
            if not exif:
                return None
            gps_ifd = exif.get_ifd(GPS_IFD) if hasattr(exif, "get_ifd") else {}
            if not gps_ifd:
                return None
            lat = _dms_to_decimal(
                gps_ifd.get(GPS_LAT),
                gps_ifd.get(GPS_LAT_REF),
            )
            lon = _dms_to_decimal(
                gps_ifd.get(GPS_LON),
                gps_ifd.get(GPS_LON_REF),
            )
            if lat == 0.0 and lon == 0.0:
                return None
            alt = _extract_gps_altitude(gps_ifd)
            dt = exif.get(TAG_DATETIME_ORIGINAL)
            timestamp = str(dt).strip() if dt else None
            return {
                "filename": path.name,
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "timestamp": timestamp,
            }
    except Exception:
        return None


def extract_gps_from_images(images_dir: str) -> list[dict]:
    """
    Extract GPS and timestamp from all JPG/JPEG files in a directory.

    Returns a list of dicts, one per image that has valid GPS:
      - filename: str
      - lat: float (decimal degrees)
      - lon: float (decimal degrees)
      - alt: float | None (meters, or None if missing)
      - timestamp: str | None (DateTimeOriginal, or None if missing)

    Images without GPS are skipped. Malformed EXIF is ignored (no crash).
    """
    root = Path(images_dir)
    if not root.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix not in _JPG_EXTENSIONS:
            continue
        rec = _read_exif_for_file(path)
        if rec is not None:
            out.append(rec)
    return out
