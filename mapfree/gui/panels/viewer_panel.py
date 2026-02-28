"""Viewer panel — placeholder for future OpenGL / PyQtGraph 3D or image view."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QFrame
from PySide6.QtCore import Qt


class ViewerPanel(QWidget):
    """Central viewer area. Placeholder; future: OpenGL / PyQtGraph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QLabel("Viewer\n(3D / Image)")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        placeholder.setStyleSheet("""
            QLabel {
                color: #6a6a6a;
                font-size: 14px;
                background-color: #252525;
                border: 1px dashed #3d3d3d;
                border-radius: 8px;
            }
        """)
        layout.addWidget(placeholder)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
