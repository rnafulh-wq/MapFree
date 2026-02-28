"""Logging facade. Re-exports from core.logger for application use."""

from mapfree.core.logger import (
    get_logger,
    get_chunk_logger,
    setup_logging,
    set_log_file_for_project,
)

__all__ = [
    "get_logger",
    "get_chunk_logger",
    "setup_logging",
    "set_log_file_for_project",
]
