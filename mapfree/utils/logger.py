"""
Structured logging setup for MapFree.

Use configure_logging() at application startup (CLI or GUI).
Then use get_logger(name) or get_chunk_logger(logger, chunk_name) everywhere.
"""

import logging
from pathlib import Path
from typing import Optional

from mapfree.core.logger import (
    get_logger,
    get_chunk_logger,
    setup_logging as _setup_logging,
    set_log_file_for_project,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "get_chunk_logger",
    "set_log_file_for_project",
]


def configure_logging(
    level: Optional[str] = None,
    log_dir: Optional[Path] = None,
    use_console: bool = True,
) -> None:
    """
    Configure application-wide logging. Call once at startup.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR. Default from MAPFREE_LOG_LEVEL or INFO.
        log_dir: Directory for mapfree.log. Default from MAPFREE_LOG_DIR or console only.
        use_console: Whether to attach a console handler.
    """
    level_int = logging.INFO
    if level is not None:
        level_int = getattr(logging, level.upper(), logging.INFO)
    _setup_logging(
        level=level_int,
        log_dir=str(log_dir) if log_dir else None,
        use_console=use_console,
    )
