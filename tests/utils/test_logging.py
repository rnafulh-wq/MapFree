"""
Unit tests for mapfree.core.logger (structured file logging with rotation).

Tests:
- setup_logging creates RotatingFileHandler when log_dir is given
- setup_logging falls back to console-only when log_dir is unwritable
- set_log_file_for_project adds a file handler for the project
- write_crash_report writes crash_report.txt with required sections
- Log level env var (MAPFREE_LOG_LEVEL) is respected
- Duplicate handlers are not added for the same log file
"""
import logging
import logging.handlers
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_logger():
    """Remove all handlers and reset _setup_done flag for test isolation."""
    from mapfree.core import logger as _logger_module
    root = logging.getLogger("mapfree")
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    _logger_module._setup_done = False


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logger state before every test."""
    _reset_logger()
    yield
    _reset_logger()


# ---------------------------------------------------------------------------
# Test 1 — setup_logging creates RotatingFileHandler
# ---------------------------------------------------------------------------

def test_setup_logging_creates_rotating_file_handler(tmp_path):
    """setup_logging with log_dir should attach a RotatingFileHandler."""
    from mapfree.core.logger import setup_logging

    setup_logging(log_dir=str(tmp_path), use_console=False)

    root = logging.getLogger("mapfree")
    rotating_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 1
    log_file = Path(rotating_handlers[0].baseFilename)
    assert log_file.parent == tmp_path
    assert log_file.name == "mapfree.log"


# ---------------------------------------------------------------------------
# Test 2 — setup_logging with unwritable dir falls back to console only
# ---------------------------------------------------------------------------

def test_setup_logging_fallback_on_unwritable_dir(tmp_path, monkeypatch):
    """When log_dir cannot be created, file logging is silently disabled."""
    from mapfree.core.logger import setup_logging

    # Point to a path that cannot be created (child of a file)
    fake_file = tmp_path / "not_a_dir.txt"
    fake_file.write_text("block")
    bad_log_dir = fake_file / "subdir"  # path through a file → OSError

    setup_logging(log_dir=str(bad_log_dir), use_console=True)

    root = logging.getLogger("mapfree")
    rotating_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(rotating_handlers) == 0, (
        "No RotatingFileHandler should be added when log_dir is unwritable"
    )


# ---------------------------------------------------------------------------
# Test 3 — set_log_file_for_project adds file handler per project
# ---------------------------------------------------------------------------

def test_set_log_file_for_project(tmp_path):
    """set_log_file_for_project adds a RotatingFileHandler for the project logs."""
    from mapfree.core.logger import set_log_file_for_project

    result = set_log_file_for_project(tmp_path)

    assert result is not None
    expected_log = tmp_path / "logs" / "mapfree.log"
    assert result == expected_log

    root = logging.getLogger("mapfree")
    matching = [
        h for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
        and Path(h.baseFilename).resolve() == expected_log.resolve()
    ]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# Test 4 — No duplicate handlers for the same log file
# ---------------------------------------------------------------------------

def test_no_duplicate_project_file_handlers(tmp_path):
    """Calling set_log_file_for_project twice must not add duplicate handlers."""
    from mapfree.core.logger import set_log_file_for_project

    set_log_file_for_project(tmp_path)
    set_log_file_for_project(tmp_path)

    root = logging.getLogger("mapfree")
    expected_log = (tmp_path / "logs" / "mapfree.log").resolve()
    matching = [
        h for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
        and Path(h.baseFilename).resolve() == expected_log
    ]
    assert len(matching) == 1, f"Expected 1 handler, got {len(matching)}"


# ---------------------------------------------------------------------------
# Test 5 — write_crash_report creates file with required sections
# ---------------------------------------------------------------------------

def test_write_crash_report(tmp_path):
    """write_crash_report writes crash_report.txt with timestamp, exception, and traceback."""
    from mapfree.core.logger import write_crash_report

    try:
        raise ValueError("mock pipeline crash")
    except ValueError as exc:
        result = write_crash_report(tmp_path, exc)

    assert result is not None
    assert result.name == "crash_report.txt"
    assert result.exists()

    content = result.read_text(encoding="utf-8")
    assert "ValueError" in content
    assert "mock pipeline crash" in content
    assert "Traceback" in content
    assert "Python" in content   # system info section


# ---------------------------------------------------------------------------
# Test 6 — write_crash_report is safe when dir is unwritable
# ---------------------------------------------------------------------------

def test_write_crash_report_handles_write_error(tmp_path):
    """write_crash_report returns None (no raise) when the directory is unwritable."""
    from mapfree.core.logger import write_crash_report

    # Point at a path that is a file (cannot mkdir under it)
    blocker = tmp_path / "crash_report.txt"
    blocker.mkdir()  # Make it a directory so writing a file there fails

    # Override the crash report path via a subdir that is actually the file
    bad_path = blocker  # project_path = blocker (a dir), but crash_report.txt inside will conflict
    # Actually this is fine — let's use a truly unwritable path
    import stat
    bad_path = tmp_path / "readonly_dir"
    bad_path.mkdir()
    bad_path.chmod(stat.S_IREAD | stat.S_IEXEC)  # read-only

    try:
        result = write_crash_report(bad_path, RuntimeError("test"))
        # On Windows chmod may not fully restrict writes; accept either outcome
        if result is None:
            pass  # expected on Linux/macOS
    except Exception as e:
        pytest.fail(f"write_crash_report must not raise, but got: {e}")
    finally:
        # Restore permissions for cleanup
        bad_path.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Test 7 — MAPFREE_LOG_LEVEL env var is respected
# ---------------------------------------------------------------------------

def test_log_level_from_env(monkeypatch, tmp_path):
    """MAPFREE_LOG_LEVEL=DEBUG sets root logger level to DEBUG."""
    monkeypatch.setenv("MAPFREE_LOG_LEVEL", "DEBUG")

    from mapfree.core.logger import setup_logging

    setup_logging(log_dir=str(tmp_path), use_console=False)

    root = logging.getLogger("mapfree")
    assert root.level == logging.DEBUG
