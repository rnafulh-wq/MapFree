"""
Logging: level, file log, timestamp, per-chunk context.
Configure once with setup_logging(); use get_logger() / get_chunk_logger() everywhere.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from .config import ENV_LOG_LEVEL, ENV_LOG_DIR

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
    if log_dir is None:
        log_dir = os.environ.get(ENV_LOG_DIR)
        if log_dir:
            log_dir = Path(log_dir)
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    level: Optional[int] = None,
    log_file: Optional[os.PathLike | str] = None,
    log_dir: Optional[os.PathLike | str] = None,
    format_string: Optional[str] = None,
    use_console: bool = True,
) -> None:
    """
    Configure mapfree root logger: level, console handler, optional file handler.
    Idempotent; safe to call once at startup.
    """
    global _setup_done
    if _setup_done:
        return

    root = logging.getLogger(ROOT_NAME)
    if level is None:
        level = _get_level_from_env()
    root.setLevel(level)

    formatter = MapFreeFormatter(format_string)

    if use_console:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(path, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    else:
        log_dir = _ensure_log_dir(Path(log_dir) if log_dir else None)
        if log_dir is not None:
            path = log_dir / "mapfree.log"
            fh = logging.FileHandler(path, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            root.addHandler(fh)

    _setup_done = True


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
    Add a file handler writing to project_path/logs/mapfree.log.
    Call when starting a pipeline run so logs go next to the project.
    Returns the log file path or None.
    """
    root = logging.getLogger(ROOT_NAME)
    project_path = Path(project_path)
    log_dir = project_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "mapfree.log"

    # Avoid duplicate file handlers to the same path
    for h in root.handlers:
        if isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file.resolve()):
            return log_file

    formatter = MapFreeFormatter()
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(root.level)
    fh.setFormatter(formatter)
    root.addHandler(fh)
    return log_file
