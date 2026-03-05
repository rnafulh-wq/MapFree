"""Startup dependency checker dialog.

Displays a table of required and optional dependencies with their
availability status, version, and actionable install hints.  Shown
automatically at startup when a critical dependency (COLMAP) is missing.
"""
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from mapfree.utils.dependency_check import DependencyStatus

_README_URL = "https://github.com/rnafulh-wq/MapFree#installation"


class DependencyDialog(QDialog):
    """Show dependency status with install hints.

    Args:
        results: ``dict[name, DependencyStatus]`` from
            :func:`~mapfree.utils.dependency_check.check_all_dependencies`.
        parent: Parent widget.

    Example::

        results = check_all_dependencies()
        dlg = DependencyDialog(results, parent=main_window)
        dlg.exec()
    """

    def __init__(
        self,
        results: dict[str, DependencyStatus],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Setup Diperlukan — MapFree")
        self.setMinimumSize(680, 420)
        self.setStyleSheet(
            "QDialog { background: #2b2b2b; color: #ddd; }"
            "QLabel { color: #ddd; }"
            "QTableWidget { background: #1e1e1e; color: #ddd; gridline-color: #3a3a3a;"
            "  border: 1px solid #3a3a3a; }"
            "QHeaderView::section { background: #2d2d2d; color: #aaa; padding: 4px; }"
            "QPushButton { background: #3a3a3a; color: #ddd; border: 1px solid #555;"
            "  border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background: #4a4a4a; }"
        )
        self._results = results
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Title
        title = QLabel("Setup Diperlukan")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Beberapa dependency tidak ditemukan.  "
            "Klik 'Buka Panduan Instalasi' untuk instruksi lengkap."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        # Table: Nama | Status | Versi | Cara Install
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Dependency", "Status", "Versi", "Cara Install"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 160)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 120)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { alternate-background-color: #222; }"
        )
        self._populate_table()
        layout.addWidget(self._table)

        # Buttons
        btn_row = QHBoxLayout()
        guide_btn = QPushButton("Buka Panduan Instalasi")
        guide_btn.clicked.connect(lambda: webbrowser.open(_README_URL))
        btn_row.addWidget(guide_btn)
        btn_row.addStretch()

        continue_btn = QPushButton("Lanjutkan")
        continue_btn.setStyleSheet(
            "QPushButton { background:#2d6fa8; color:white; border:none; }"
            "QPushButton:hover { background:#3d8fc8; }"
        )
        continue_btn.clicked.connect(self.accept)
        btn_row.addWidget(continue_btn)

        layout.addLayout(btn_row)

    def _populate_table(self) -> None:
        for name, status in self._results.items():
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Name + critical badge
            name_text = f"{name}  ({'Wajib' if status.critical else 'Opsional'})"
            name_item = QTableWidgetItem(name_text)
            name_item.setForeground(
                Qt.GlobalColor.white if status.critical else Qt.GlobalColor.gray
            )
            self._table.setItem(row, 0, name_item)

            # Status
            if status.available:
                status_item = QTableWidgetItem("✓ Tersedia")
                status_item.setForeground(Qt.GlobalColor.green)
            else:
                label = "✗ Tidak ada"
                color = Qt.GlobalColor.red if status.critical else Qt.GlobalColor.yellow
                status_item = QTableWidgetItem(label)
                status_item.setForeground(color)
            self._table.setItem(row, 1, status_item)

            # Version
            ver_item = QTableWidgetItem(status.version or "—")
            ver_item.setForeground(Qt.GlobalColor.lightGray)
            self._table.setItem(row, 2, ver_item)

            # Install hint
            hint_item = QTableWidgetItem(status.install_hint or "—")
            hint_item.setForeground(Qt.GlobalColor.lightGray)
            self._table.setItem(row, 3, hint_item)
