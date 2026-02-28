"""License activation dialog. Production stub."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox


class LicenseDialog(QDialog):
    """Enter or validate license key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("License")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("License key:"))
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("Enter key...")
        layout.addWidget(self._key_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
