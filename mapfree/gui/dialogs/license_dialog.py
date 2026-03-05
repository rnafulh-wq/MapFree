"""License activation dialog.

Features:

* Auto-formats key input as ``XXXX-XXXX-XXXX-XXXX`` while the user types.
* Converts input to uppercase automatically.
* Displays status indicator (green ✓ valid, red ✗ invalid, orange trial).
* Shows Machine ID for support reference.
* "Beli Lisensi" button opens the website URL.
"""
import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from mapfree.application.license_manager import (
    LicenseStatus,
    get_machine_id,
    validate,
)

_BUY_URL = "https://mapfree.app/pricing"   # placeholder


class LicenseDialog(QDialog):
    """License activation dialog with auto-formatted key input.

    Allows the user to enter a ``XXXX-XXXX-XXXX-XXXX`` key, validates it
    against :func:`~mapfree.application.license_manager.validate`, and shows
    a colour-coded status label.

    Example::

        dlg = LicenseDialog(parent=main_window)
        dlg.exec()
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aktivasi Lisensi — MapFree")
        self.setMinimumWidth(480)
        self.setStyleSheet(
            "QDialog { background: #2b2b2b; color: #ddd; }"
            "QLabel { color: #ddd; }"
            "QLineEdit { background: #1e1e1e; color: #fff; border: 1px solid #555;"
            "  border-radius: 4px; padding: 6px 10px; font-size: 14px;"
            "  letter-spacing: 2px; }"
            "QPushButton { background: #3a3a3a; color: #ddd; border: 1px solid #555;"
            "  border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background: #4a4a4a; }"
            "QPushButton#activateBtn { background: #2d6fa8; color: white; border: none; }"
            "QPushButton#activateBtn:hover { background: #3d8fc8; }"
        )
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel("Aktivasi Lisensi MapFree")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        # Key input
        key_label = QLabel("License Key:")
        key_label.setStyleSheet("font-size: 12px; color: #aaa;")
        layout.addWidget(key_label)

        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self._key_edit.setMaxLength(19)
        self._key_edit.textChanged.connect(self._on_key_changed)
        layout.addWidget(self._key_edit)

        # Activate button
        activate_btn = QPushButton("Aktivasi")
        activate_btn.setObjectName("activateBtn")
        activate_btn.setFixedHeight(36)
        activate_btn.clicked.connect(self._on_activate)
        layout.addWidget(activate_btn)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            "font-size: 13px; padding: 8px; border-radius: 4px;"
        )
        self._status_label.hide()
        layout.addWidget(self._status_label)

        # Machine ID
        machine_id = get_machine_id()
        mid_label = QLabel(f"Machine ID: {machine_id}")
        mid_label.setStyleSheet("font-size: 10px; color: #666;")
        mid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mid_label)

        # Buy license row
        buy_row = QHBoxLayout()
        buy_row.addStretch()
        buy_btn = QPushButton("Beli Lisensi →")
        buy_btn.setStyleSheet(
            "QPushButton { color: #5ba3d9; background: transparent; border: none;"
            "  font-size: 12px; text-decoration: underline; }"
            "QPushButton:hover { color: #7ec3f9; }"
        )
        buy_btn.clicked.connect(lambda: webbrowser.open(_BUY_URL))
        buy_row.addWidget(buy_btn)
        layout.addLayout(buy_row)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_key_changed(self, text: str) -> None:
        """Auto-format key as XXXX-XXXX-XXXX-XXXX and uppercase."""
        cursor = self._key_edit.cursorPosition()
        # Strip non-hex and non-dash, uppercase
        clean = "".join(c for c in text.upper() if c in "0123456789ABCDEF-")
        # Remove all dashes then re-insert every 4 chars
        hex_only = clean.replace("-", "")[:16]
        parts = [hex_only[i:i + 4] for i in range(0, len(hex_only), 4)]
        formatted = "-".join(parts)

        if formatted != text:
            self._key_edit.blockSignals(True)
            self._key_edit.setText(formatted)
            # Adjust cursor: count dashes before old cursor pos
            new_cursor = min(cursor, len(formatted))
            self._key_edit.setCursorPosition(new_cursor)
            self._key_edit.blockSignals(False)

        # Hide status when user is typing
        self._status_label.hide()

    def _on_activate(self) -> None:
        """Run validation and update status label."""
        key = self._key_edit.text().strip()
        if not key:
            self._show_status("Masukkan license key terlebih dahulu.", "orange")
            return

        status = validate(key)
        if status == LicenseStatus.VALID:
            self._show_status("✓ Lisensi Valid", "#2d8a4e")
            # Close after brief delay
            QTimer.singleShot(1500, self.accept)
        elif status == LicenseStatus.EXPIRED:
            self._show_status("✗ Lisensi sudah kadaluwarsa.", "#a03030")
        elif status == LicenseStatus.INVALID:
            self._show_status("✗ Key tidak valid.", "#a03030")
        elif status in (LicenseStatus.TRIAL, LicenseStatus.TRIAL_EXPIRED):
            self._show_status("Trial mode aktif — masukkan key untuk mengaktifkan.", "#b87a20")
        else:
            self._show_status("Status tidak diketahui.", "#888")

    def _show_status(self, message: str, bg_color: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(
            f"font-size: 13px; padding: 8px; border-radius: 4px;"
            f"background: {bg_color}22; color: {bg_color}; border: 1px solid {bg_color}44;"
        )
        self._status_label.show()
