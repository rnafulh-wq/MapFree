"""
Pytest configuration and shared fixtures.

Headless Qt/OpenGL on Linux: set QT_QPA_PLATFORM=offscreen so that QOpenGLWidget
and context creation work in CI without a display. For environments where offscreen
is not available, run tests under Xvfb (install: apt install xvfb):

  xvfb-run -a pytest tests/test_viewer_load_ply.py tests/test_viewer_load_mesh.py -v
"""
import os
import sys

# Must set before any PySide6/Qt import so viewer tests get a valid GL context in CI
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
