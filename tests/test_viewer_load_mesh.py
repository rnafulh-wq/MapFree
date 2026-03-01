"""
Viewer load_mesh tests. Require headless Qt/OpenGL (conftest sets
QT_QPA_PLATFORM=offscreen on Linux; or run with: xvfb-run -a pytest ...).
"""
from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication
from mapfree.viewer.gl_widget import set_default_opengl_format, ViewerWidget


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MESH_PLY = FIXTURES_DIR / "mesh.ply"


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


def test_load_mesh_success(viewer_widget):
    """load_mesh returns True and widget has vertices and indices for valid PLY mesh."""
    assert MESH_PLY.exists(), "fixture mesh.ply missing"
    ok = viewer_widget.load_mesh(str(MESH_PLY))
    assert ok is True
    assert viewer_widget._num_vertices == 3
    assert viewer_widget._num_indices == 3


def test_load_mesh_invalid_path(viewer_widget):
    """load_mesh returns False for non-existent file."""
    ok = viewer_widget.load_mesh("/nonexistent/mesh.ply")
    assert ok is False
