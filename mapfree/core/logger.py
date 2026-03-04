"""
Logging: level, file log, timestamp, per-chunk context.
Configure once with setup_logging(); use get_logger() / get_chunk_logger() everywhere.

File logging uses RotatingFileHandler (10 MB per file, 5 backup files).
Log dir: MAPFREE_LOG_DIR env → ~/.mapfree/logs (default).
Log level: MAPFREE_LOG_LEVEL env → INFO (default).

Crash reports are written to <project_path>/crash_report.txt via write_crash_report().
"""
import logging
import logging.handlers
import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import ENV_LOG_LEVEL, ENV_LOG_DIR

_ROTATE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_ROTATE_BACKUP_COUNT = 5
_STRUCTURED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

ROOT_NAME = "mapfree"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_setup_done = False


class MapFreeFormatter(logging.Formatter):
    """Formatter with timestamp and optional chunk; safe when record has no chunk."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        fmt = fmt or "%(asctime)s [%(levelname)s] %(name)s%(chunk)s %(message)s"
        super().__init__(fmt=fmt, datefmt=datefmt or _DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        setattr(record, "chunk", getattr(record, "chunk", ""))
        return super().format(record)


class ChunkAdapter(logging.LoggerAdapter):
    """Logger that adds chunk context so formatter shows e.g. [chunk_001]."""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra") or {}
        chunk = self.extra.get("chunk", "")
        extra["chunk"] = f" [{chunk}]" if chunk else ""
        kwargs["extra"] = extra
        return msg, kwargs


def _get_level_from_env() -> int:
    raw = os.environ.get(ENV_LOG_LEVEL, "").strip().upper()
    return getattr(logging, raw, logging.INFO)


def _ensure_log_dir(log_dir: Optional[Path]) -> Optional[Path]:
    """Resolve and create log directory; falls back to ~/.mapfree/logs if env is unset."""
    if log_dir is None:
        env_val = os.environ.get(ENV_LOG_DIR)
        if env_val:
            log_dir = Path(env_val)
        else:
            log_dir = Path.home() / ".mapfree" / "logs"
    log_dir = Path(log_dir)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # Permission error or other OS error — disable file logging gracefully
        logging.getLogger(ROOT_NAME).warning(
            "Cannot create log directory %s (%s). File logging disabled.", log_dir, e
        )
        return None
    return log_dir


def _make_rotating_handler(path: Path, level: int, formatter: logging.Formatter) -> logging.Handler:
    """Create a RotatingFileHandler with standard MapFree rotation settings."""
    fh = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=_ROTATE_MAX_BYTES,
        backupCount=_ROTATE_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    return fh


def setup_logging(
    level: Optional[int] = None,
    log_file: Optional[os.PathLike | str] = None,
    log_dir: Optional[os.PathLike | str] = None,
    format_string: Optional[str] = None,
    use_console: bool = True,
) -> None:
    """
    Configure mapfree root logger: level, console handler, RotatingFileHandler.
    Idempotent; safe to call once at startup.

    File logging:
    - If ``log_file`` is given, write to that exact path (RotatingFileHandler).
    - Else resolve ``log_dir`` (from env MAPFREE_LOG_DIR or ~/.mapfree/logs/)
      and write to ``log_dir/mapfree.log``.
    - If the log directory cannot be created (permission error), file logging is
      disabled and a warning is emitted on the console.
    """
    global _setup_done
    if _setup_done:
        return

    root = logging.getLogger(ROOT_NAME)
    if level is None:
        level = _get_level_from_env()
    root.setLevel(level)

    # Use structured format for file handler; legacy format for console
    structured_formatter = MapFreeFormatter(_STRUCTURED_FORMAT)
    console_formatter = MapFreeFormatter(format_string)

    if use_console:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(console_formatter)
        root.addHandler(console)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = _make_rotating_handler(path, level, structured_formatter)
        root.addHandler(fh)
    else:
        resolved_dir = _ensure_log_dir(Path(log_dir) if log_dir else None)
        if resolved_dir is not None:
            path = resolved_dir / "mapfree.log"
            fh = _make_rotating_handler(path, level, structured_formatter)
            root.addHandler(fh)

    _setup_done = True


def write_crash_report(project_path: os.PathLike | str, exc: BaseException) -> Optional[Path]:
    """
    Write a crash_report.txt to ``project_path`` containing timestamp, exception
    type, traceback, and system information.

    Args:
        project_path: Project output directory.
        exc: The exception that caused the crash.

    Returns:
        Path to crash_report.txt or None if writing failed.
    """
    try:
        out_dir = Path(project_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "crash_report.txt"
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        lines = [
            "=" * 72,
            f"MapFree Crash Report — {datetime.now().isoformat()}",
            "=" * 72,
            f"Exception: {type(exc).__name__}: {exc}",
            "",
            "Traceback:",
            tb,
            "System Info:",
            f"  Python:   {sys.version}",
            f"  Platform: {platform.platform()}",
            f"  CWD:      {os.getcwd()}",
            "=" * 72,
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logging.getLogger(ROOT_NAME).info("Crash report written: %s", report_path)
        return report_path
    except Exception as write_err:
        logging.getLogger(ROOT_NAME).warning(
            "Failed to write crash report to %s: %s", project_path, write_err
        )
        return None


def get_logger(name: str) -> logging.Logger:
    """Return a logger under mapfree.* (e.g. mapfree.pipeline)."""
    if not name.startswith(ROOT_NAME + "."):
        name = f"{ROOT_NAME}.{name}"
    return logging.getLogger(name)


def get_chunk_logger(logger: logging.Logger, chunk_name: str):
    """
    Return an adapter that adds chunk context to every log line.
    Use for per-chunk logs: get_chunk_logger(get_logger('pipeline'), 'chunk_001').
    Formatter will show [chunk_001] when chunk_name is set.
    """
    if isinstance(logger, ChunkAdapter):
        base = logger.logger
        # Nest chunk: outer chunk wins or combine
        prev = logger.extra.get("chunk", "")
        chunk_name = f"{prev} {chunk_name}".strip() if prev else chunk_name
    else:
        base = logger
    return ChunkAdapter(base, {"chunk": chunk_name})


def set_log_file_for_project(project_path: os.PathLike | str) -> Optional[Path]:
    """
    Add a RotatingFileHandler writing to project_path/logs/mapfree.log.
    Call when starting a pipeline run so logs go next to the project.
    Returns the log file path or None.
    """
    root = logging.getLogger(ROOT_NAME)
    project_path = Path(project_path)
    log_dir = project_path / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        root.warning("Cannot create project log dir %s: %s", log_dir, e)
        return None

    log_file = log_dir / "mapfree.log"

    # Avoid duplicate handlers to the same path
    resolved = str(log_file.resolve())
    for h in root.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == resolved:
            return log_file

    formatter = MapFreeFormatter(_STRUCTURED_FORMAT)
    fh = _make_rotating_handler(log_file, root.level, formatter)
    root.addHandler(fh)
    return log_file
