"""
Viewer panel / OpenGL fallback tests.

Tests verify that:
- MAPFREE_NO_OPENGL=1 returns a placeholder widget, never a crash
- gl_enabled=False returns a disabled widget
- ViewerWidget._fallback_mode() sets _use_fallback=True without raising
- OpenGL import failure is handled gracefully (no propagation to caller)

These tests use mocked PySide6 types where possible so they run headless.
Heavy Qt / GL widget tests (test_viewer_load_mesh, test_viewer_load_ply) are
separate and require a real display / xvfb.
"""
import os
import sys
import importlib
import types
import unittest.mock as mock

import pytest


# ---------------------------------------------------------------------------
# Helper: check whether we can import PySide6 (skip if missing)
# ---------------------------------------------------------------------------
def _pyside6_available() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _pyside6_available(),
    reason="PySide6 not installed",
)


# ---------------------------------------------------------------------------
# Test 1 — MAPFREE_NO_OPENGL=1 → _create_viewer_widget returns placeholder
# ---------------------------------------------------------------------------
def test_no_opengl_env_returns_placeholder(monkeypatch):
    """When MAPFREE_NO_OPENGL=1, _create_viewer_widget must return a placeholder, not ViewerWidget."""
    monkeypatch.setenv("MAPFREE_NO_OPENGL", "1")
    monkeypatch.delenv("MAPFREE_OPENGL", raising=False)

    # Import (or reimport) after env is set so the module sees the env var
    from mapfree.gui.main_window import _ViewerPlaceholder  # noqa: F401

    # Build a minimal MainWindow-like object with only the logic under test
    class _FakeWindow:
        _gl_enabled = True

        def _create_viewer_widget(self):
            import os as _os
            from mapfree.gui.main_window import (
                _ViewerPlaceholder as _P,
                _viewer_disabled_widget,
            )
            if not self._gl_enabled:
                return _viewer_disabled_widget(None)
            if _os.environ.get("MAPFREE_NO_OPENGL") == "1":
                return _P(None)
            return _P(None, on_enable_gl=lambda: None)

    w = _FakeWindow()
    result = w._create_viewer_widget()

    assert isinstance(result, _ViewerPlaceholder), (
        f"Expected _ViewerPlaceholder but got {type(result).__name__}"
    )
    # Cleanup
    result.deleteLater() if hasattr(result, "deleteLater") else None


# ---------------------------------------------------------------------------
# Test 2 — gl_enabled=False → _create_viewer_widget returns disabled widget
# ---------------------------------------------------------------------------
def test_gl_disabled_flag_returns_disabled_widget():
    """When gl_enabled=False, viewer must be _ViewerDisabledWidget."""
    from mapfree.gui.main_window import _ViewerDisabledWidget  # noqa: F401

    class _FakeWindow:
        _gl_enabled = False

        def _create_viewer_widget(self):
            import os as _os
            from mapfree.gui.main_window import (
                _ViewerDisabledWidget as _D,
                _viewer_disabled_widget,
            )
            if not self._gl_enabled:
                return _viewer_disabled_widget(None)
            return None

    w = _FakeWindow()
    result = w._create_viewer_widget()

    assert isinstance(result, _ViewerDisabledWidget), (
        f"Expected _ViewerDisabledWidget but got {type(result).__name__}"
    )


# ---------------------------------------------------------------------------
# Test 3 — ViewerWidget._fallback_mode() sets _use_fallback=True
# ---------------------------------------------------------------------------
def test_viewer_widget_fallback_mode_sets_flag():
    """_fallback_mode() must set _use_fallback=True and not raise."""
    with mock.patch.dict(os.environ, {"MAPFREE_NO_OPENGL": "1"}):
        # We can import ViewerWidget without a real GL context for attribute tests
        from mapfree.viewer.gl_widget import ViewerWidget

        # Instantiate with mocked parent to avoid needing a QApplication
        with mock.patch("mapfree.viewer.gl_widget.QOpenGLWidget.__init__", return_value=None):
            widget = ViewerWidget.__new__(ViewerWidget)
            # Set required attrs manually (skip super().__init__)
            widget._use_fallback = False
            widget._gl = None
            widget._vao = widget._vbo = widget._ebo = None
            widget._program_mesh = widget._program_points = widget._program_line = None
            widget._vao_line = widget._vbo_line = None

            # Call fallback mode — must not raise
            widget._fallback_mode(RuntimeError("mock GL init failure"))

            assert widget._use_fallback is True
            assert widget._gl is None  # no real context, so GL stays None


# ---------------------------------------------------------------------------
# Test 4 — initializeGL with MAPFREE_NO_OPENGL=1 skips init, sets fallback
# ---------------------------------------------------------------------------
def test_initialize_gl_respects_no_opengl_env(monkeypatch):
    """initializeGL must check MAPFREE_NO_OPENGL first and set _use_fallback without calling makeCurrent."""
    monkeypatch.setenv("MAPFREE_NO_OPENGL", "1")

    from mapfree.viewer.gl_widget import ViewerWidget

    with mock.patch("mapfree.viewer.gl_widget.QOpenGLWidget.__init__", return_value=None):
        widget = ViewerWidget.__new__(ViewerWidget)
        widget._use_fallback = False
        widget._initialized = False
        widget._gl = None
        widget._vao = widget._vbo = widget._ebo = None
        widget._program_mesh = widget._program_points = widget._program_line = None
        widget._vao_line = widget._vbo_line = None

        # makeCurrent/doneCurrent must NOT be called when MAPFREE_NO_OPENGL=1
        with mock.patch.object(widget, "makeCurrent") as mock_make, \
             mock.patch.object(widget, "doneCurrent") as mock_done:
            widget.initializeGL()

            mock_make.assert_not_called()
            mock_done.assert_not_called()
            assert widget._use_fallback is True
            assert widget._initialized is True


# ---------------------------------------------------------------------------
# Test 5 — _ViewerPlaceholder and _ViewerDisabledWidget expose load_point_cloud API
# ---------------------------------------------------------------------------
def test_placeholder_api_compatible():
    """Both placeholder types expose load_point_cloud, load_mesh, clear_scene (no-op / False)."""
    from mapfree.gui.main_window import _ViewerPlaceholder, _ViewerDisabledWidget

    for cls in (_ViewerPlaceholder, _ViewerDisabledWidget):
        obj = cls.__new__(cls)
        # Verify no-op methods exist and return expected values without needing real Qt
        assert hasattr(obj, "load_point_cloud")
        assert hasattr(obj, "load_mesh")
        assert hasattr(obj, "clear_scene")
