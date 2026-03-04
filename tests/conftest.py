"""
Pytest configuration and shared fixtures for non-GUI tests.

GUI tests (viewer, Qt, OpenGL) live in tests/gui/ and are skipped automatically
when run headless (no DISPLAY on Linux). To run them in CI or headless env:

  xvfb-run pytest tests/gui
"""
import os
import sys
from pathlib import Path

# Optional: set for any test that might use Qt; tests/gui/conftest also sets it for its scope
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Exclude script-style test files that run code at module level and call sys.exit().
# Also exclude GUI tests that require OpenGL/Qt display.
_HERE = Path(__file__).parent
collect_ignore = [
    str(_HERE / "test_engine_wrapper.py"),
    str(_HERE / "test_fresh_run.py"),
    str(_HERE / "test_resume_engine.py"),
    str(_HERE / "test_progress_tracking.py"),
    str(_HERE / "data" / "make_20_photos.py"),
    str(_HERE / "gui" / "test_viewer_load_mesh.py"),
    str(_HERE / "gui" / "test_viewer_load_ply.py"),
]
