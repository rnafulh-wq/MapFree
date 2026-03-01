"""
Viewer load_point_cloud tests. Require headless Qt/OpenGL (conftest sets
QT_QPA_PLATFORM=offscreen on Linux; or run with: xvfb-run -a pytest ...).
"""
from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication
from mapfree.viewer.gl_widget import set_default_opengl_format, ViewerWidget


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
POINT_CLOUD_PLY = FIXTURES_DIR / "point_cloud.ply"


@pytest.fixture(scope="module")
def qapp():
    """Single QApplication for the module; OpenGL format set before first widget."""
    set_default_opengl_format()
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def viewer_widget(qapp):
    """ViewerWidget with GL context realized (show + processEvents)."""
    widget = ViewerWidget()
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()


def test_load_point_cloud_success(viewer_widget):
    """load_point_cloud returns True and widget has geometry for valid PLY."""
    assert POINT_CLOUD_PLY.exists(), "fixture point_cloud.ply missing"
    ok = viewer_widget.load_point_cloud(str(POINT_CLOUD_PLY))
    assert ok is True
    assert viewer_widget._num_vertices == 3


def test_load_point_cloud_invalid_path(viewer_widget):
    """load_point_cloud returns False for non-existent file."""
    ok = viewer_widget.load_point_cloud("/nonexistent/path.ply")
    assert ok is False
