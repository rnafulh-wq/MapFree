"""
Pytest configuration for tests/gui.

- On Linux without DISPLAY (headless CI): all tests in this directory are skipped automatically.
- Run GUI tests with:  xvfb-run pytest tests/gui

Qt/OpenGL: QT_QPA_PLATFORM=offscreen is set so that QOpenGLWidget can get a context
when DISPLAY is available (e.g. under xvfb). Without DISPLAY, tests are skipped before any Qt import.
"""
import os
import sys

import pytest

# Set before any PySide6/Qt import so viewer tests get a valid GL context when DISPLAY is set
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "gui: marks tests as GUI tests (require DISPLAY on Linux; run with: xvfb-run pytest tests/gui)",
    )


def pytest_collection_modifyitems(config, items):
    """In headless CI (no DISPLAY on Linux), skip all tests collected from tests/gui."""
    if sys.platform != "linux":
        return
    if os.environ.get("DISPLAY"):
        return
    for item in items:
        try:
            path_str = str(item.fspath).replace("\\", "/")
        except Exception:
            continue
        if "tests/gui" in path_str:
            item.add_marker(
                pytest.mark.skip(reason="Headless: no DISPLAY. Run with: xvfb-run pytest tests/gui")
            )
