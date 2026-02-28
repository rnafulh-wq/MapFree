"""Settings dialog. Production stub."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox


class SettingsDialog(QDialog):
    """Application and pipeline settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings (stub)"))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
