"""
Pytest configuration and shared fixtures for non-GUI tests.

GUI tests (viewer, Qt, OpenGL) live in tests/gui/ and are skipped automatically
when run headless (no DISPLAY on Linux). To run them in CI or headless env:

  xvfb-run pytest tests/gui
"""
import os
import sys

# Optional: set for any test that might use Qt; tests/gui/conftest also sets it for its scope
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
