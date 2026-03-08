"""Startup dependency checker dialog.

Displays a table of required and optional dependencies with their
availability status, version, and actionable install hints.  Shown
automatically at startup when a critical dependency (COLMAP) is missing.
"""
import webbrowser

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mapfree.utils.dependency_check import DependencyStatus

_README_URL = "https://github.com/rnafulh-wq/MapFree#installation"

# Dependencies that support auto-install via first-run wizard flow
_AUTO_INSTALL_DEPS = {"colmap", "DensifyPointCloud", "ReconstructMesh", "TextureMesh"}


class _InstallWorker(QThread):
    """Run dependency download+install in background; emit progress and result."""
    progress = Signal(int, int)  # current, total (steps or 0-100)
    log_line = Signal(str)
    finished_ok = Signal(str)   # dep name
    finished_error = Signal(str, str)  # dep name, message

    def __init__(self, dep_name: str):
        super().__init__()
        self._dep_name = dep_name
        self._cancelled = False

    def run(self):
        try:
            from pathlib import Path
            from mapfree.utils.hardware_detector import detect_system
            from mapfree.utils.dependency_resolver import DependencyResolver
            from mapfree.utils.dependency_downloader import DependencyDownloader
            from mapfree.utils.dependency_check import invalidate_cache
            from mapfree.gui.dialogs.first_run_wizard import _register_installed_binaries

            self.log_line.emit("Mendeteksi hardware…")
            self.progress.emit(1, 4)
            info = detect_system()
            resolver = DependencyResolver(info)
            dest_dir = Path.home() / ".mapfree" / "deps"
            dest_dir.mkdir(parents=True, exist_ok=True)
            downloader = DependencyDownloader()

            if self._dep_name == "colmap":
                packages = resolver.get_required_packages()
            else:
                packages = [p for p in resolver.get_optional_packages() if p.name == "OpenMVS"]
            if not packages:
                self.finished_error.emit(self._dep_name, "Tidak ada paket untuk diinstall.")
                return
            pkg = packages[0]
            if not (pkg.download_url or "").strip():
                self.finished_error.emit(self._dep_name, "URL download tidak tersedia untuk OS ini.")
                return
            self.log_line.emit("Mengunduh %s…" % pkg.name)
            self.progress.emit(2, 4)
            path = downloader.download(pkg, dest_dir, progress_callback=lambda a, b: None)
            self.log_line.emit("Menginstall…")
            self.progress.emit(3, 4)
            ok = downloader.install(pkg, path)
            if not ok:
                self.finished_error.emit(self._dep_name, "Install gagal.")
                return
            _register_installed_binaries(pkg, dest_dir)
            invalidate_cache()
            self.progress.emit(4, 4)
            self.finished_ok.emit(self._dep_name)
        except Exception as e:
            self.finished_error.emit(self._dep_name, str(e))


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
        self._install_worker = None
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

        # Table: Nama | Status | Versi | Cara Install | Aksi
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Dependency", "Status", "Versi", "Cara Install", "Aksi"]
        )
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(0, 140)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 180)
        self._table.setColumnWidth(4, 100)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { alternate-background-color: #222; }"
        )
        self._populate_table()
        layout.addWidget(self._table)

        # Progress bar (hidden until auto-install runs)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Buttons
        btn_row = QHBoxLayout()
        guide_btn = QPushButton("Buka Panduan Instalasi")
        guide_btn.clicked.connect(lambda: webbrowser.open(_README_URL))
        btn_row.addWidget(guide_btn)
        refresh_btn = QPushButton("Cek Ulang")
        refresh_btn.setToolTip("Jalankan pengecekan dependency ulang tanpa restart aplikasi.")
        refresh_btn.clicked.connect(self._on_refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()

        continue_btn = QPushButton("Lanjutkan")
        continue_btn.setStyleSheet(
            "QPushButton { background:#2d6fa8; color:white; border:none; }"
            "QPushButton:hover { background:#3d8fc8; }"
        )
        continue_btn.clicked.connect(self._on_continue)
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

            # Install hint (short text; full in tooltip + path)
            hint_short = (status.install_hint or "—").strip().split("\n")[0]
            if len(hint_short) > 50:
                hint_short = hint_short[:47] + "..."
            hint_item = QTableWidgetItem(hint_short)
            hint_item.setForeground(Qt.GlobalColor.lightGray)
            full_tip = (status.install_hint or "").strip()
            if status.path:
                full_tip += "\n\nPath: " + (status.path or "")
            if full_tip:
                hint_item.setToolTip(full_tip)
            self._table.setItem(row, 3, hint_item)

            # Aksi: Auto Install for colmap / OpenMVS when not available
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            if name in _AUTO_INSTALL_DEPS and not status.available:
                auto_btn = QPushButton("Auto Install")
                auto_btn.setStyleSheet(
                    "QPushButton { background:#2d6fa8; color:white; border:none; "
                    "padding: 4px 10px; font-size: 11px; }"
                    "QPushButton:hover { background:#3d8fc8; }"
                    "QPushButton:disabled { background:#555; color:#888; }"
                )
                auto_btn.setProperty("dep_name", name)
                auto_btn.clicked.connect(self._on_auto_install_clicked)
                action_layout.addWidget(auto_btn)
            else:
                action_layout.addWidget(QLabel("—"))
            self._table.setCellWidget(row, 4, action_widget)

    def _on_refresh(self) -> None:
        """Re-run dependency check and refresh table."""
        from mapfree.utils.dependency_check import check_all_dependencies, invalidate_cache
        invalidate_cache()
        self._results = check_all_dependencies()
        self._table.setRowCount(0)
        self._populate_table()

    def _on_continue(self) -> None:
        """Invalidate cache, re-check, save setup state (with colmap_path), then close."""
        from mapfree.utils.dependency_check import check_all_dependencies, invalidate_cache
        from mapfree.application.setup_state import save_setup_state
        invalidate_cache()
        results = check_all_dependencies()
        save_setup_state(results)
        self.accept()

    def _on_auto_install_clicked(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QPushButton) or self._install_worker is not None:
            return
        dep_name = sender.property("dep_name")
        if not dep_name:
            return
        self._install_button = sender
        sender.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._install_worker = _InstallWorker(dep_name)
        self._install_worker.progress.connect(self._on_install_progress)
        self._install_worker.finished_ok.connect(self._on_install_finished_ok)
        self._install_worker.finished_error.connect(self._on_install_finished_error)
        self._install_worker.start()

    def _on_install_progress(self, current: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(100 * current / total))

    def _on_install_finished_ok(self, dep_name: str) -> None:
        self._install_worker = None
        self._progress_bar.setVisible(False)
        self._progress_bar.setValue(0)
        from mapfree.utils.dependency_check import check_all_dependencies
        self._results = check_all_dependencies()
        self._table.setRowCount(0)
        self._populate_table()

    def _on_install_finished_error(self, dep_name: str, message: str) -> None:
        self._install_worker = None
        self._progress_bar.setVisible(False)
        if getattr(self, "_install_button", None) is not None:
            self._install_button.setEnabled(True)
            self._install_button = None
        QMessageBox.critical(self, "Auto Install", "Gagal: %s" % message)
