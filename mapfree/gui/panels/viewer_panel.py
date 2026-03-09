"""Viewer panel — QTabWidget with Sparse, Dense, and Ortho tabs.

Tab layout:

    0  Sparse  — PointCloudViewer (OpenGL) or MatplotlibPointCloudViewer (fallback)
    1  Dense   — MeshViewer (pyqtgraph.opengl mesh)
    2  Ortho   — QLabel raster image (shown only when a raster is loaded)
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from mapfree.gui.panels import viewer_3d
from mapfree.gui.panels.viewer_3d import MeshViewer, PointCloudViewer
from mapfree.gui.panels.viewer_matplotlib import MatplotlibPointCloudViewer

_OPENGL_AVAILABLE = getattr(viewer_3d, "_PYQTGRAPH_AVAILABLE", False)

_TAB_SPARSE = 0
_TAB_DENSE = 1
_TAB_ORTHO = 2


class ViewerPanel(QWidget):
    """Central viewer panel with Sparse, Dense, and Ortho tabs.

    Sparse tab:
        :class:`PointCloudViewer` — PLY point clouds from COLMAP sparse output.

    Dense tab:
        :class:`MeshViewer` — OBJ/PLY mesh from dense reconstruction.

    Ortho tab (hidden until a raster is loaded):
        Scaled :class:`~PySide6.QtWidgets.QLabel` for orthophoto display.

    Public API (backward-compatible):
        * :meth:`load_point_cloud` — load PLY into Sparse tab
        * :meth:`load_mesh`        — load OBJ/PLY into Dense tab
        * :meth:`load_raster`      — display raster image in Ortho tab
        * :meth:`clear_scene`      — reset all viewers
        * :meth:`get_visualizer`   — return PointCloudViewer
        * :meth:`get_mesh_viewer`  — return MeshViewer
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._viewer_toolbar = self._create_viewer_toolbar()
        self._layout.addWidget(self._viewer_toolbar)

        self._tabs = QTabWidget(self)
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #252525; }"
            "QTabBar::tab { background: #2d2d2d; color: #aaa;"
            "  padding: 6px 18px; border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { color: #fff; border-bottom: 2px solid #3d6fa8; }"
            "QTabBar::tab:hover { background: #363636; }"
        )
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._tabs)

        # Tab 0 — Sparse (OpenGL or matplotlib fallback)
        if _OPENGL_AVAILABLE:
            self._pc_viewer = PointCloudViewer(self)
        else:
            self._pc_viewer = MatplotlibPointCloudViewer(self)
        self._pc_viewer.pointsLoaded.connect(self._on_points_loaded)
        self._tabs.addTab(self._pc_viewer, "Sparse")

        # Tab 1 — Dense
        self._mesh_viewer = MeshViewer(self)
        self._mesh_viewer.meshLoaded.connect(self._on_mesh_loaded)
        self._tabs.addTab(self._mesh_viewer, "Dense")

        # Tab 2 — Ortho (hidden by default)
        self._raster_label = QLabel(self)
        self._raster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._raster_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self._raster_label.setStyleSheet("background-color: #252525;")
        self._tabs.addTab(self._raster_label, "Ortho")
        self._tabs.setTabVisible(_TAB_ORTHO, False)

        self._raster_pixmap_path: str | None = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(400)
        self.setStyleSheet("background-color: #252525;")
        self._viewer_toolbar.setEnabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_point_cloud(self, file_path: str) -> bool:
        """Load a PLY file into the Sparse tab.

        Args:
            file_path: Path to the ``.ply`` file.

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False
        ok = self._pc_viewer.load_ply(file_path)
        if ok:
            self._tabs.setCurrentIndex(_TAB_SPARSE)
        return ok

    def load_mesh(self, file_path: str) -> bool:
        """Load an OBJ or PLY mesh into the Dense tab.

        Args:
            file_path: Path to the ``.obj`` or ``.ply`` file.

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False
        ok = self._mesh_viewer.load_mesh(file_path)
        if ok:
            self._tabs.setCurrentIndex(_TAB_DENSE)
        return ok

    def load_raster(self, file_path: str) -> bool:
        """Display a raster image (orthophoto) in the Ortho tab.

        Args:
            file_path: Path to an image file.

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False
        pix = QPixmap(file_path)
        if pix.isNull():
            return False
        self._raster_pixmap_path = file_path
        self._tabs.setTabVisible(_TAB_ORTHO, True)
        self._tabs.setCurrentIndex(_TAB_ORTHO)
        self._update_raster_pixmap()
        self._viewer_toolbar.setEnabled(False)
        return True

    def clear_scene(self) -> None:
        """Reset all viewers and hide the Ortho tab."""
        self._pc_viewer.clear()
        self._mesh_viewer.clear()
        self._raster_pixmap_path = None
        self._tabs.setTabVisible(_TAB_ORTHO, False)
        self._tabs.setCurrentIndex(_TAB_SPARSE)
        self._viewer_toolbar.setEnabled(False)

    def get_visualizer(self):
        """Return the point cloud viewer in the Sparse tab (OpenGL or matplotlib fallback)."""
        return self._pc_viewer

    def get_mesh_viewer(self) -> MeshViewer:
        """Return the :class:`MeshViewer` in the Dense tab."""
        return self._mesh_viewer

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._raster_pixmap_path and self._tabs.currentIndex() == _TAB_ORTHO:
            self._update_raster_pixmap()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_viewer_toolbar(self) -> QToolBar:
        bar = QToolBar(self)
        bar.setObjectName("ViewerToolbar")
        bar.setStyleSheet(
            "QToolBar { background-color:#2d2d2d; border:none; padding:4px; spacing:4px; }"
            "QToolButton { color:#e0e0e0; padding:6px 10px; }"
            "QToolButton:hover { background-color:#404040; }"
            "QToolButton:checked { background-color:#3d6fa8; }"
        )
        first_label = (
            "Load Point Cloud (2D/3D Viewer)"
            if not _OPENGL_AVAILABLE
            else "Enable 3D viewer (OpenGL)"
        )
        bar.addAction(QAction(first_label, self))
        bar.addSeparator()
        reset_action = QAction("Reset Camera", self)
        reset_action.triggered.connect(self._on_reset_camera)
        bar.addAction(reset_action)
        bar.addAction(QAction("Top View", self))
        bar.addAction(QAction("Side View", self))
        bar.addSeparator()
        wire_action = QAction("Wireframe", self)
        wire_action.triggered.connect(self._on_wireframe_toggle)
        bar.addAction(wire_action)
        bar.setEnabled(False)
        return bar

    def _on_reset_camera(self) -> None:
        idx = self._tabs.currentIndex()
        if idx == _TAB_SPARSE:
            self._pc_viewer._reset_camera()  # noqa: SLF001
        elif idx == _TAB_DENSE:
            self._mesh_viewer._reset_camera()  # noqa: SLF001

    def _on_wireframe_toggle(self) -> None:
        idx = self._tabs.currentIndex()
        if idx == _TAB_DENSE:
            self._mesh_viewer._toggle_wireframe()  # noqa: SLF001

    def _on_points_loaded(self, count: int) -> None:
        self._viewer_toolbar.setEnabled(True)

    def _on_mesh_loaded(self, count: int) -> None:
        self._viewer_toolbar.setEnabled(True)

    def _update_raster_pixmap(self) -> None:
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
