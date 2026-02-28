"""About dialog."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class AboutDialog(QDialog):
    """About MapFree Engine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("MapFree Engine"))
        layout.addWidget(QLabel("Modular photogrammetry pipeline."))
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
