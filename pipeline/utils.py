"""Small helpers for the pipeline."""

from pathlib import Path

# Extensions we consider as images (drone JPG + common RAW)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG", ".tif", ".tiff", ".TIF", ".TIFF"}
# Add common RAW if needed; COLMAP supports many
RAW_EXTENSIONS = {".cr2", ".CR2", ".nef", ".NEF", ".arw", ".ARW", ".dng", ".DNG"}
IMAGE_EXTENSIONS |= RAW_EXTENSIONS


def find_images(directory: Path) -> list[Path]:
    """Return sorted list of image paths in directory (by name)."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix in IMAGE_EXTENSIONS)
