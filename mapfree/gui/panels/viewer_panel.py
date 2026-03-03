"""Viewer panel — placeholder and raster image display (no 3D engine)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QToolBar,
)
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt


class ViewerPanel(QWidget):
    """Central viewer area: placeholder message and raster image display via QLabel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._fallback_label = None
        self._viewer_toolbar = self._create_viewer_toolbar()
        self._layout.addWidget(self._viewer_toolbar)
        self._raster_label = QLabel(self)
        self._raster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._raster_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._raster_label.setStyleSheet("background-color: #252525;")
        self._raster_label.setScaledContents(False)
        self._raster_label.hide()
        self._raster_pixmap_path = None
        self._layout.addWidget(self._raster_label)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(400)
        self.setStyleSheet("background-color: #252525;")
        self._show_placeholder()

    def showEvent(self, event):
        super().showEvent(event)
        if self._fallback_label is not None and self._raster_label.isHidden():
            self._fallback_label.show()

    def _show_placeholder(self):
        """Show placeholder message when no raster is loaded."""
        if self._fallback_label is not None:
            return
        self._fallback_label = QLabel("Viewer\n\n(No 3D engine)")
        self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback_label.setStyleSheet("""
            QLabel {
                color: #6a6a6a;
                font-size: 13px;
                background-color: #252525;
                border: 1px dashed #3d3d3d;
                border-radius: 8px;
            }
        """)
        self._fallback_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._layout.addWidget(self._fallback_label)
        self._viewer_toolbar.setEnabled(False)

    def _create_viewer_toolbar(self) -> QToolBar:
        """Toolbar: Points/Mesh, Reset Camera, Top View, Side View, Wireframe (no-op without 3D)."""
        bar = QToolBar(self)
        bar.setObjectName("ViewerToolbar")
        bar.setStyleSheet("""
            QToolBar { background-color: #2d2d2d; border: none; padding: 4px; spacing: 4px; }
            QToolButton { color: #e0e0e0; padding: 6px 10px; }
            QToolButton:hover { background-color: #404040; }
            QToolButton:checked { background-color: #3d6fa8; }
        """)
        bar.addAction(QAction("Points / Mesh", self))
        bar.addSeparator()
        bar.addAction(QAction("Reset Camera", self))
        bar.addAction(QAction("Top View", self))
        bar.addAction(QAction("Side View", self))
        bar.addSeparator()
        bar.addAction(QAction("Wireframe", self))
        bar.setEnabled(False)
        return bar

    def get_visualizer(self):
        """Return None (no 3D visualizer). Kept for API compatibility."""
        return None

    def _show_raster_label(self, file_path: str) -> bool:
        """Display image in QLabel. Returns True on success."""
        path = Path(file_path)
        if not path.exists():
            return False
        pix = QPixmap(str(path))
        if pix.isNull():
            return False
        self._raster_pixmap_path = str(path)
        self._update_raster_pixmap()
        self._raster_label.show()
        if self._fallback_label is not None:
            self._fallback_label.hide()
        self._viewer_toolbar.setEnabled(False)
        return True

    def _update_raster_pixmap(self):
        """Scale and set pixmap on _raster_label from _raster_pixmap_path."""
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

    def _hide_raster_label(self):
        """Switch back from raster QLabel to placeholder."""
        self._raster_pixmap_path = None
        self._raster_label.hide()
        if self._fallback_label is not None:
            self._fallback_label.show()
        self._viewer_toolbar.setEnabled(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._raster_pixmap_path and self._raster_label.isVisible():
            self._update_raster_pixmap()

    def load_raster(self, file_path: str) -> bool:
        """Load a raster image (e.g. orthophoto) and display in QLabel. Returns True on success."""
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False
        return self._show_raster_label(file_path)

    def load_point_cloud(self, file_path: str) -> bool:
        """No 3D engine; point cloud cannot be displayed. Returns False."""
        self._hide_raster_label()
        return False

    def load_mesh(self, file_path: str) -> bool:
        """No 3D engine; mesh cannot be displayed. Returns False."""
        self._hide_raster_label()
        return False

    def clear_scene(self) -> None:
        """Hide raster image and show placeholder."""
        self._raster_label.hide()
        if self._fallback_label is not None:
            self._fallback_label.show()
        self._viewer_toolbar.setEnabled(False)
