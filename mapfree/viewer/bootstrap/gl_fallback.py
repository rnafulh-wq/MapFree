"""
Fallback widget when OpenGL is unavailable or disabled. Same API surface as
ViewerWidget (load_point_cloud, load_mesh, clear_scene, zoom_fit, toggle_axes)
so callers can use it as a drop-in placeholder.

GLFallbackManager: if safe_probe() returns None → disable 3D; if context creation
fails → downgrade profile once; if still fails → disable 3D entirely. Never crash.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from mapfree.viewer.bootstrap.gl_log import log_disable, log_error, log_fallback


def _safe_format_21() -> QSurfaceFormat:
    """Minimum compatibility format; never raises."""
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    return fmt


class GLFallbackManager:
    """
    If safe_probe() returns None → disable 3D.
    If context creation later fails → downgrade profile once.
    If still fails → disable 3D entirely.
    """

    def __init__(self, probe_timeout: float = 5.0):
        self._disabled = True
        self._downgraded = False
        self._capabilities: dict | None = None
        try:
            from mapfree.viewer.bootstrap.gl_probe import safe_probe
            result = safe_probe(timeout=probe_timeout)
            if result is None:
                log_disable("GLFallbackManager: probe returned None")
                self._disabled = True
            else:
                self._disabled = False
                self._capabilities = result
        except Exception as e:
            log_error(str(e))
            log_disable("GLFallbackManager: probe exception")
            self._disabled = True

    def should_enable_3d(self) -> bool:
        """True if 3D is enabled (probe succeeded and not disabled after failures)."""
        try:
            return not self._disabled and self._capabilities is not None
        except Exception:
            return False

    def get_surface_format(self) -> QSurfaceFormat | None:
        """Format to use for GL context, or None if 3D is disabled. Never raises."""
        try:
            if self._disabled:
                return None
            if self._downgraded:
                return _safe_format_21()
            if self._capabilities is None:
                return None
            from mapfree.viewer.bootstrap.gl_selector import choose_surface_format
            return choose_surface_format(self._capabilities)
        except Exception:
            self._downgraded = True
            return _safe_format_21()

    def notify_context_failed(self) -> None:
        """Call when context creation fails. Downgrade once, then disable 3D. Never raises."""
        try:
            if self._downgraded:
                log_fallback("context failed again, disabling 3D")
                log_disable("GLFallbackManager: context failed after downgrade")
                self._disabled = True
            else:
                log_fallback("context failed, downgrading profile")
                self._downgraded = True
        except Exception as e:
            log_error(str(e))
            self._disabled = True


class GLFallbackWidget(QWidget):
    """
    Non-OpenGL placeholder with ViewerWidget-compatible API.
    Use when bootstrap backend is "placeholder".
    """

    def __init__(self, parent=None, message: str | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        text = message or (
            "3D Viewer (placeholder).\n"
            "OpenGL is disabled or unavailable on this system."
        )
        lab = QLabel(text)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet("color: #8a8a8a; font-size: 12px;")
        layout.addWidget(lab)

    def load_point_cloud(self, file_path: str) -> bool:
        return False

    def load_mesh(self, file_path: str) -> bool:
        return False

    def clear_scene(self) -> None:
        pass

    def zoom_fit(self) -> None:
        pass

    def toggle_axes(self) -> None:
        pass
