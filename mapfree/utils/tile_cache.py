"""Global OSM tile cache under ~/.mapfree/tiles/. Cleanup of old tiles at startup."""

import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

TILES_DIR = Path.home() / ".mapfree" / "tiles"
DEFAULT_MAX_AGE_DAYS = 30


def cleanup_old_tiles(max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> None:
    """
    Remove tile files under ~/.mapfree/tiles/ older than max_age_days.
    Safe to call from a background thread; does not block GUI.
    """
    if not TILES_DIR.is_dir():
        return
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    try:
        for z_dir in list(TILES_DIR.iterdir()):
            if not z_dir.is_dir():
                continue
            for x_dir in list(z_dir.iterdir()):
                if not x_dir.is_dir():
                    continue
                for f in list(x_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() == ".png":
                        try:
                            if f.stat().st_mtime < cutoff:
                                f.unlink()
                                removed += 1
                        except OSError:
                            pass
        if removed:
            log.info("Tile cache: removed %d files older than %d days", removed, max_age_days)
    except OSError as e:
        log.debug("Tile cache cleanup failed: %s", e)
