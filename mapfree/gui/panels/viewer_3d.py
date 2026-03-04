"""Point Cloud Viewer using PyQtGraph OpenGL.

Provides :class:`PointCloudViewer` which loads and renders PLY point clouds
using ``pyqtgraph.opengl.GLScatterPlotItem``.  Falls back to a styled
placeholder widget when pyqtgraph is not installed or ``MAPFREE_NO_OPENGL=1``
is set.

PLY parsing is delegated to :mod:`mapfree.utils.ply_parser` (pure numpy,
no Qt dependency).
"""
import logging
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from mapfree.utils.ply_parser import parse_ply_file  # re-export for API compat

logger = logging.getLogger("mapfree.viewer_3d")

# Public re-export so callers can do `from mapfree.gui.panels.viewer_3d import parse_ply_file`
__all__ = ["PointCloudViewer", "parse_ply_file"]

# ---------------------------------------------------------------------------
# Availability guards — checked once at import time
# ---------------------------------------------------------------------------

_OPENGL_DISABLED: bool = os.environ.get("MAPFREE_NO_OPENGL", "0") == "1"

try:
    if _OPENGL_DISABLED:
        raise ImportError("OpenGL disabled via MAPFREE_NO_OPENGL env var")
    import pyqtgraph as _pg              # type: ignore[import]
    import pyqtgraph.opengl as _gl      # type: ignore[import]
    _PYQTGRAPH_AVAILABLE = True
except Exception:
    _pg = None   # type: ignore[assignment]
    _gl = None   # type: ignore[assignment]
    _PYQTGRAPH_AVAILABLE = False


# ---------------------------------------------------------------------------
# PointCloudViewer widget
# ---------------------------------------------------------------------------

class PointCloudViewer(QWidget):
    """Widget that renders a PLY point cloud using pyqtgraph.opengl.

    Falls back to a styled placeholder label when:

    * ``pyqtgraph`` is not installed, or
    * the environment variable ``MAPFREE_NO_OPENGL=1`` is set.

    Mouse controls (when pyqtgraph is available):

    * **Left drag** — orbit / rotate
    * **Middle drag** — pan
    * **Scroll wheel** — zoom in / out

    Signals:
        pointsLoaded (int): Emitted with the number of loaded points on
            a successful :meth:`load_ply` call.
        loadError (str): Emitted with an error message when :meth:`load_ply`
            fails.

    Example::

        viewer = PointCloudViewer()
        viewer.pointsLoaded.connect(lambda n: print(f"{n:,} points loaded"))
        viewer.load_ply("/path/to/scan.ply")
    """

    pointsLoaded: Signal = Signal(int)
    loadError: Signal = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._xyz: Optional[np.ndarray] = None
        self._colors: Optional[np.ndarray] = None
        self._scatter: Any = None       # GLScatterPlotItem or None
        self._gl_view: Any = None       # GLViewWidget or None
        self._status_label: Optional[QLabel] = None
        self._centroid: np.ndarray = np.zeros(3, dtype=np.float32)
        self._fit_distance: float = 5.0
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build either the OpenGL view or the fallback placeholder."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if _PYQTGRAPH_AVAILABLE:
            self._setup_gl_view(layout)
        else:
            self._setup_placeholder(layout)

    def _setup_placeholder(self, layout: QVBoxLayout) -> None:
        """Create a styled label when pyqtgraph / OpenGL is unavailable."""
        if _OPENGL_DISABLED:
            detail = "(OpenGL disabled — set MAPFREE_NO_OPENGL=0 to enable)"
        else:
            detail = "(pyqtgraph not installed)\npip install pyqtgraph"
        placeholder = QLabel(f"Point Cloud Viewer\n\n{detail}")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "QLabel {"
            "  color: #6a6a6a; font-size: 13px;"
            "  background-color: #1e1e1e;"
            "  border: 1px dashed #3d3d3d; border-radius: 8px;"
            "}"
        )
        placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(placeholder)

        self._status_label = QLabel("No point cloud loaded")
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._status_label.setStyleSheet(
            "QLabel { color: #888; font-size: 11px; padding: 4px 8px; background: #252525; }"
        )
        layout.addWidget(self._status_label)

    def _setup_gl_view(self, layout: QVBoxLayout) -> None:
        """Create GLViewWidget and control toolbar."""
        self._gl_view = _gl.GLViewWidget()
        self._gl_view.setBackgroundColor("#1a1a1a")
        self._gl_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self._gl_view)

        # Controls bar
        controls = QWidget()
        controls.setStyleSheet("background-color: #2a2a2a;")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(6, 4, 6, 4)
        ctrl_layout.setSpacing(6)

        reset_btn = QPushButton("Reset View")
        reset_btn.setFixedWidth(100)
        reset_btn.setStyleSheet(
            "QPushButton {"
            "  color: #ddd; background: #3a3a3a;"
            "  border: 1px solid #555; border-radius: 4px; padding: 4px 8px;"
            "}"
            "QPushButton:hover { background: #4a4a4a; }"
        )
        reset_btn.clicked.connect(self._reset_camera)
        ctrl_layout.addWidget(reset_btn)
        ctrl_layout.addStretch()

        self._status_label = QLabel("No point cloud loaded")
        self._status_label.setStyleSheet(
            "QLabel { color: #888; font-size: 11px; }"
        )
        ctrl_layout.addWidget(self._status_label)

        layout.addWidget(controls)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_ply(self, path: str | Path) -> bool:
        """Load a PLY file and render it.

        Uses :func:`mapfree.utils.ply_parser.parse_ply_file` to parse the
        file with no Qt dependency.

        Args:
            path: Path to the ``.ply`` file.

        Returns:
            ``True`` on success, ``False`` if the file could not be loaded.
        """
        path = Path(path)
        xyz, colors = parse_ply_file(path)
        if xyz is None:
            msg = f"Could not load PLY: {path.name}"
            logger.warning(msg)
            self._set_status(msg)
            self.loadError.emit(msg)
            return False

        self._xyz = xyz
        self._colors = colors
        self._centroid = xyz.mean(axis=0)

        span = np.linalg.norm(xyz.max(axis=0) - xyz.min(axis=0))
        self._fit_distance = float(span) * 1.5 if span > 0 else 5.0

        self._update_render()

        count = len(xyz)
        self._set_status(f"{count:,} points loaded")
        self.pointsLoaded.emit(count)
        logger.info("Loaded %d points from '%s'", count, path)
        return True

    def refresh_points(self, xyz_rgb: np.ndarray) -> None:
        """Update the rendered point cloud from an Nx3 or Nx6 array.

        Designed for live-preview use (TASK 2.3).  Colours in columns 3-5
        are treated as uint8 [0, 255] when the array dtype is integral.

        Args:
            xyz_rgb: Shape ``(N, 3)`` or ``(N, 6)`` array. When 6 columns
                are present, columns 3-5 are interpreted as R, G, B.
        """
        if xyz_rgb.ndim != 2 or xyz_rgb.shape[1] < 3:
            logger.warning(
                "refresh_points: expected (N, ≥3) array, got %s", xyz_rgb.shape
            )
            return

        xyz = xyz_rgb[:, :3].astype(np.float32)
        self._xyz = xyz
        self._centroid = xyz.mean(axis=0)

        if xyz_rgb.shape[1] >= 6:
            rgb = xyz_rgb[:, 3:6].astype(np.float32)
            if not np.issubdtype(xyz_rgb.dtype, np.floating):
                rgb = rgb / 255.0
            alpha = np.ones((len(xyz), 1), dtype=np.float32)
            self._colors = np.concatenate([rgb, alpha], axis=1)
        else:
            self._colors = None

        span = np.linalg.norm(xyz.max(axis=0) - xyz.min(axis=0))
        self._fit_distance = float(span) * 1.5 if span > 0 else 5.0

        self._update_render()
        self._set_status(f"{len(xyz):,} points (live)")

    def point_count(self) -> int:
        """Return the number of currently displayed points, or 0."""
        return len(self._xyz) if self._xyz is not None else 0

    def clear(self) -> None:
        """Remove the currently displayed point cloud."""
        self._xyz = None
        self._colors = None
        if _PYQTGRAPH_AVAILABLE and self._scatter is not None:
            self._gl_view.removeItem(self._scatter)
            self._scatter = None
        self._set_status("No point cloud loaded")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        """Update the status label text."""
        if self._status_label is not None:
            self._status_label.setText(message)

    def _reset_camera(self) -> None:
        """Reset the camera to look at the centroid of the loaded cloud."""
        if not _PYQTGRAPH_AVAILABLE or self._gl_view is None:
            return
        self._gl_view.opts["center"] = _pg.Vector(
            float(self._centroid[0]),
            float(self._centroid[1]),
            float(self._centroid[2]),
        )
        self._gl_view.setCameraPosition(
            distance=self._fit_distance,
            elevation=30,
            azimuth=45,
        )
        self._gl_view.update()

    def _update_render(self) -> None:
        """Push current xyz/colors data into the GLScatterPlotItem."""
        if not _PYQTGRAPH_AVAILABLE or self._gl_view is None:
            return
        if self._xyz is None:
            return

        color: Any = self._colors if self._colors is not None else (1.0, 1.0, 1.0, 1.0)

        if self._scatter is None:
            self._scatter = _gl.GLScatterPlotItem(
                pos=self._xyz,
                color=color,
                size=1.5,
                pxMode=True,
            )
            self._gl_view.addItem(self._scatter)
        else:
            self._scatter.setData(pos=self._xyz, color=color)

        self._reset_camera()
