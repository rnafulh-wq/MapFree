"""
Sort images by EXIF: GPS (lat, lon) first, then datetime.
Produces an image list file for COLMAP --image_list_path so sequential matcher
uses flight order.
"""
from pathlib import Path
from typing import List, Tuple

# EXIF tag numbers
TAG_DATETIME_ORIGINAL = 36867
GPS_IFD = 0x8825  # 34853
GPS_LAT_REF = 1
GPS_LAT = 2
GPS_LON_REF = 3
GPS_LON = 4


def _rational_to_float(val) -> float:
    """Convert EXIF rational (num, den) or Rational to float."""
    if val is None:
        return 0.0
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        d = val.denominator or 1
        return float(val.numerator) / float(d)
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return float(val[0]) / float(val[1] or 1)
    return float(val)


def _dms_to_decimal(dms, ref) -> float:
    """Convert EXIF DMS (deg, min, sec) and ref (N/S, E/W) to decimal degrees."""
    if not dms or len(dms) < 3:
        return 0.0
    deg = _rational_to_float(dms[0])
    min_ = _rational_to_float(dms[1])
    sec = _rational_to_float(dms[2])
    decimal = deg + min_ / 60.0 + sec / 3600.0
    if ref in ("S", "W", b"S", b"W"):
        decimal = -decimal
    return decimal


def _get_exif_gps_time(image_path: Path) -> Tuple[float, float, str]:
    """
    Return (lat, lon, datetime_str) from EXIF. (0, 0, "") if missing.
    """
    try:
        from PIL import Image
    except ImportError:
        return (0.0, 0.0, "")
    try:
        with Image.open(image_path) as im:
            exif = im.getexif() if hasattr(im, "getexif") else None
            if not exif:
                return (0.0, 0.0, "")
            gps_ifd = exif.get_ifd(GPS_IFD) if hasattr(exif, "get_ifd") else {}
            if not gps_ifd:
                lat, lon = 0.0, 0.0
            else:
                lat = _dms_to_decimal(
                    gps_ifd.get(GPS_LAT),
                    gps_ifd.get(GPS_LAT_REF),
                )
                lon = _dms_to_decimal(
                    gps_ifd.get(GPS_LON),
                    gps_ifd.get(GPS_LON_REF),
                )
            dt = exif.get(TAG_DATETIME_ORIGINAL)
            if dt is None:
                dt_str = ""
            else:
                dt_str = str(dt).strip() if dt else ""
            return (lat, lon, dt_str)
    except Exception:
        return (0.0, 0.0, "")


def build_sorted_image_list(
    image_dir: Path,
    extensions: set,
) -> List[Path]:
    """
    List image files in image_dir, read EXIF GPS and datetime, sort by (lat, lon, datetime).
    Secondary sort: filename. Returns list of Paths in order.
    """
    image_dir = Path(image_dir)
    if not image_dir.is_dir():
        return []
    paths = sorted(
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix in extensions
    )
    if not paths:
        return []

    rows: List[Tuple[float, float, str, Path]] = []
    for p in paths:
        lat, lon, dt = _get_exif_gps_time(p)
        rows.append((lat, lon, dt, p))

    # Sort: GPS first (lat, lon), then datetime, then filename
    # Items with no GPS (0,0) sort last; then by filename
    def key(row):
        lat, lon, dt, path = row
        has_gps = (lat != 0.0 or lon != 0.0)
        return (not has_gps, lat, lon, dt, path.name)

    rows.sort(key=key)
    return [r[3] for r in rows]


def write_image_list_for_colmap(
    image_dir: Path,
    output_list_path: Path,
    extensions: set,
) -> Path | None:
    """
    Write a sorted image list to output_list_path (one filename per line, relative to image_dir).
    Order: EXIF GPS (lat, lon) then datetime. For sequential matcher / feature_extractor.
    Returns output_list_path if written, None if no images or error.
    """
    image_dir = Path(image_dir)
    output_list_path = Path(output_list_path)
    sorted_paths = build_sorted_image_list(image_dir, extensions)
    if not sorted_paths:
        return None
    try:
        output_list_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_list_path, "w") as f:
            for p in sorted_paths:
                # COLMAP expects path relative to --image_path, so use filename only
                f.write(p.name + "\n")
        return output_list_path
    except OSError:
        return None
