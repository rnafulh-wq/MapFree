"""Viewer panel — 2D raster display, 3D point-cloud viewer, and placeholder.

Layout managed by QStackedWidget with three pages:

    0  Placeholder  — shown when nothing is loaded
    1  PointCloudViewer — 3D point cloud / mesh (pyqtgraph.opengl)
    2  Raster label — orthophoto / image (QLabel with scaled QPixmap)
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from mapfree.gui.panels.viewer_3d import PointCloudViewer

_PAGE_PLACEHOLDER = 0
_PAGE_3D = 1
_PAGE_RASTER = 2


class ViewerPanel(QWidget):
    """Central viewer area with three display modes: placeholder, 3D point cloud, raster image.

    The 3D viewer is provided by :class:`PointCloudViewer` and automatically
    falls back to a placeholder when pyqtgraph is unavailable or
    ``MAPFREE_NO_OPENGL=1``.

    Public API (unchanged from previous version):
        * :meth:`load_point_cloud` — load a PLY file into the 3D viewer
        * :meth:`load_mesh`        — alias; delegates to :meth:`load_point_cloud`
        * :meth:`load_raster`      — display a raster image (QLabel)
        * :meth:`clear_scene`      — return to placeholder
        * :meth:`get_visualizer`   — return the underlying PointCloudViewer
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._viewer_toolbar = self._create_viewer_toolbar()
        self._layout.addWidget(self._viewer_toolbar)

        self._stack = QStackedWidget(self)
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._stack)

        # Page 0 — placeholder
        self._placeholder = self._create_placeholder()
        self._stack.addWidget(self._placeholder)

        # Page 1 — 3D point cloud viewer
        self._pc_viewer = PointCloudViewer(self)
        self._pc_viewer.pointsLoaded.connect(self._on_points_loaded)
        self._stack.addWidget(self._pc_viewer)

        # Page 2 — raster image label
        self._raster_label = QLabel(self)
        self._raster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._raster_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._raster_label.setStyleSheet("background-color: #252525;")
        self._raster_label.setScaledContents(False)
        self._stack.addWidget(self._raster_label)

        self._raster_pixmap_path: str | None = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(400)
        self.setStyleSheet("background-color: #252525;")

        # Start on placeholder
        self._stack.setCurrentIndex(_PAGE_PLACEHOLDER)
        self._viewer_toolbar.setEnabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_point_cloud(self, file_path: str) -> bool:
        """Load a PLY file into the 3D point cloud viewer.

        Args:
            file_path: Path to the .ply file.

        Returns:
            ``True`` on success; ``False`` if the file could not be loaded or
            pyqtgraph / OpenGL is unavailable.
        """
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False

        ok = self._pc_viewer.load_ply(file_path)
        if ok:
            self._stack.setCurrentIndex(_PAGE_3D)
            self._sync_toolbar_to_3d()
        return ok

    def load_mesh(self, file_path: str) -> bool:
        """Load a mesh PLY/OBJ file (currently delegates to point-cloud view).

        Args:
            file_path: Path to the mesh file.

        Returns:
            ``True`` on success; ``False`` otherwise.
        """
        return self.load_point_cloud(file_path)

    def load_raster(self, file_path: str) -> bool:
        """Display a raster image (orthophoto, etc.) in the 2D label.

        Args:
            file_path: Path to an image file.

        Returns:
            ``True`` on success; ``False`` if the image cannot be loaded.
        """
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False
        pix = QPixmap(file_path)
        if pix.isNull():
            return False
        self._raster_pixmap_path = file_path
        self._stack.setCurrentIndex(_PAGE_RASTER)
        self._update_raster_pixmap()
        self._viewer_toolbar.setEnabled(False)
        return True

    def clear_scene(self) -> None:
        """Return to the placeholder page."""
        self._pc_viewer.clear()
        self._raster_pixmap_path = None
        self._stack.setCurrentIndex(_PAGE_PLACEHOLDER)
        self._viewer_toolbar.setEnabled(False)

    def get_visualizer(self) -> PointCloudViewer:
        """Return the underlying PointCloudViewer widget.

        Returns:
            The :class:`PointCloudViewer` instance (always present; may be
            in fallback mode if OpenGL is unavailable).
        """
        return self._pc_viewer

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        """Re-scale raster image on resize."""
        super().resizeEvent(event)
        if (
            self._stack.currentIndex() == _PAGE_RASTER
            and self._raster_pixmap_path
        ):
            self._update_raster_pixmap()

    def showEvent(self, event) -> None:
        """Ensure correct page is shown after widget becomes visible."""
        super().showEvent(event)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_placeholder(self) -> QLabel:
        """Create the dark placeholder label shown when nothing is loaded."""
        label = QLabel("Viewer\n\n(Load a PLY point cloud or image)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "QLabel {"
            "  color: #6a6a6a;"
            "  font-size: 13px;"
            "  background-color: #252525;"
            "  border: 1px dashed #3d3d3d;"
            "  border-radius: 8px;"
            "}"
        )
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return label

    def _create_viewer_toolbar(self) -> QToolBar:
        """Build the viewer toolbar (Points/Mesh, Reset Camera, wireframe, etc.)."""
        bar = QToolBar(self)
        bar.setObjectName("ViewerToolbar")
        bar.setStyleSheet(
            "QToolBar { background-color: #2d2d2d; border: none; padding: 4px; spacing: 4px; }"
            "QToolButton { color: #e0e0e0; padding: 6px 10px; }"
            "QToolButton:hover { background-color: #404040; }"
            "QToolButton:checked { background-color: #3d6fa8; }"
        )
        bar.addAction(QAction("Points / Mesh", self))
        bar.addSeparator()

        reset_action = QAction("Reset Camera", self)
        reset_action.triggered.connect(self._on_reset_camera)
        bar.addAction(reset_action)

        bar.addAction(QAction("Top View", self))
        bar.addAction(QAction("Side View", self))
        bar.addSeparator()
        bar.addAction(QAction("Wireframe", self))
        bar.setEnabled(False)
        return bar

    def _on_reset_camera(self) -> None:
        """Delegate Reset Camera action to the 3D viewer."""
        self._pc_viewer._reset_camera()  # noqa: SLF001 — intentional friend access

    def _on_points_loaded(self, count: int) -> None:
        """Called when PointCloudViewer finishes loading data."""
        self._sync_toolbar_to_3d()

    def _sync_toolbar_to_3d(self) -> None:
        """Enable toolbar actions relevant to the 3D view."""
        self._viewer_toolbar.setEnabled(True)

    def _update_raster_pixmap(self) -> None:
        """Scale and display the raster pixmap to fill the label."""
        if not self._raster_pixmap_path:
            return
        pix = QPixmap(self._raster_pixmap_path)
        if pix.isNull():
            return
        sz = self._raster_label.size()
        if sz.width() > 0 and sz.height() > 0:
            self._raster_label.setPixmap(
                pix.scaled(
                    sz,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
