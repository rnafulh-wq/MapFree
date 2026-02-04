"""Logging setup for MapFree pipeline."""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> None:
    """Configure root logger: console and optional file."""
    root = logging.getLogger("mapfree")
    root.setLevel(level)
    root.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the mapfree namespace."""
    return logging.getLogger(f"mapfree.{name}")
