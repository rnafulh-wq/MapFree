"""First-run setup wizard: hardware detection, component selection, download and install."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWizard,
    QWizardPage,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QFrame,
)

from mapfree.utils.hardware_detector import detect_system
from mapfree.utils.dependency_resolver import DependencyResolver, DependencyPackage
from mapfree.utils.dependency_downloader import DependencyDownloader
from mapfree.utils.path_manager import PathManager

logger = logging.getLogger(__name__)

SETUP_COMPLETE_FILE = Path.home() / ".mapfree" / "setup_complete.json"

# Registry names and binary names for PathManager after install
_REGISTRY_BINARIES = {
    "COLMAP": ["colmap.exe", "colmap"],
    "OpenMVS": ["DensifyPointCloud.exe", "ReconstructMesh.exe", "TextureMesh.exe",
                "DensifyPointCloud", "ReconstructMesh", "TextureMesh"],
}


def _register_installed_binaries(pkg: DependencyPackage, dest_dir: Path) -> None:
    """Find installed binaries under dest_dir and register them with PathManager."""
    names = _REGISTRY_BINARIES.get(pkg.name)
    if not names:
        return
    dest_dir = Path(dest_dir)
    if not dest_dir.is_dir():
        return
    for candidate in names:
        for path in dest_dir.rglob(candidate):
            if path.is_file():
                reg_name = path.stem if path.suffix.lower() == ".exe" else path.name
                try:
                    PathManager.register_dep(reg_name, path)
                    logger.debug("Registered %s -> %s", reg_name, path)
                except Exception as e:
                    logger.debug("Could not register %s: %s", reg_name, e)


MAPFREE_VERSION = "1.1"


def _ensure_installer_components_copied() -> None:
    """When running from bundle, copy installer's components.json to ~/.mapfree so wizard uses it."""
    if not getattr(sys, "frozen", False):
        return
    exe_dir = Path(sys.executable).resolve().parent
    source = exe_dir / "components.json"
    if not source.is_file():
        return
    dest_dir = Path.home() / ".mapfree"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "components.json"
    try:
        dest.write_bytes(source.read_bytes())
        logger.debug("Copied installer components.json to %s", dest)
    except OSError as e:
        logger.debug("Could not copy components.json: %s", e)


def _load_components_preference() -> dict[str, bool]:
    """Load optional component choices from installer-written components.json if present."""
    _ensure_installer_components_copied()
    components_file = Path.home() / ".mapfree" / "components.json"
    if not components_file.is_file():
        return {}
    try:
        with open(components_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "openmvs": data.get("openmvs", False),
            "pdal_gdal": data.get("pdal_gdal", False),
        }
    except (json.JSONDecodeError, OSError):
        return {}


def _save_setup_complete(system_info: dict[str, Any], components: dict[str, bool]) -> None:
    """Write setup_complete.json so next startup skips the wizard."""
    SETUP_COMPLETE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": MAPFREE_VERSION,
        "profile": system_info.get("recommended_profile", "medium"),
        "colmap": system_info.get("recommended_colmap", "no_cuda"),
        "openmvs": components.get("openmvs", False),
        "pdal_gdal": components.get("pdal_gdal", False),
    }
    with open(SETUP_COMPLETE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Setup complete saved to %s", SETUP_COMPLETE_FILE)


def should_show_first_run_wizard() -> bool:
    """Return True if setup_complete.json is missing or invalid (show wizard)."""
    if not SETUP_COMPLETE_FILE.is_file():
        return True
    try:
        with open(SETUP_COMPLETE_FILE, "r", encoding="utf-8") as f:
            json.load(f)
        return False
    except (json.JSONDecodeError, OSError):
        return True


# ---------------------------------------------------------------------------
# Worker: run detect_system() in background
# ---------------------------------------------------------------------------
class HardwareDetectionWorker(QThread):
    result = Signal(dict)

    def run(self) -> None:
        try:
            info = detect_system()
            self.result.emit(info)
        except Exception as e:
            logger.exception("Hardware detection failed: %s", e)
            self.result.emit({"error": str(e)})


# ---------------------------------------------------------------------------
# Worker: download and install selected packages
# ---------------------------------------------------------------------------
class InstallWorker(QThread):
    log_line = Signal(str)
    package_progress = Signal(str, int, int)  # name, current_mb, total_mb
    overall_progress = Signal(int, int)        # value, maximum
    finished_ok = Signal()
    finished_error = Signal(str)

    def __init__(self, packages: list[DependencyPackage], dest_dir: Path) -> None:
        super().__init__()
        self._packages = packages
        self._dest_dir = Path(dest_dir)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            downloader = DependencyDownloader()
            total = len(self._packages)
            for idx, pkg in enumerate(self._packages):
                if self._cancelled:
                    self.log_line.emit("Dibatalkan oleh pengguna.")
                    break
                if not (pkg.download_url or "").strip():
                    self.log_line.emit("[%s] Lewat (tanpa URL download)." % pkg.name)
                    self.overall_progress.emit(idx + 1, total)
                    continue
                self.log_line.emit("[%s] Mengunduh..." % pkg.name)
                try:
                    def _progress(done: int, total_bytes: int) -> None:
                        total_mb = (total_bytes // (1024 * 1024)) if total_bytes > 0 else pkg.install_size_mb
                        done_mb = done // (1024 * 1024)
                        self.package_progress.emit(pkg.name, done_mb, total_mb)
                    path = downloader.download(pkg, self._dest_dir, progress_callback=_progress)
                    self.log_line.emit("[%s] Menginstall..." % pkg.name)
                    ok = downloader.install(pkg, path)
                    if ok:
                        _register_installed_binaries(pkg, self._dest_dir)
                        self.log_line.emit("[%s] Selesai." % pkg.name)
                    else:
                        self.log_line.emit("[%s] Install gagal (lanjut)." % pkg.name)
                except Exception as e:
                    self.log_line.emit("[%s] Error: %s" % (pkg.name, e))
                self.overall_progress.emit(idx + 1, total)
            if not self._cancelled:
                self.finished_ok.emit()
            else:
                self.finished_error.emit("Dibatalkan")
        except Exception as e:
            logger.exception("Install worker failed: %s", e)
            self.finished_error.emit(str(e))


# ---------------------------------------------------------------------------
# Page 1 — Welcome
# ---------------------------------------------------------------------------
class WelcomePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Selamat Datang")
        layout = QVBoxLayout(self)
        title = QLabel("Selamat datang di MapFree Engine v%s" % MAPFREE_VERSION)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #fff;")
        layout.addWidget(title)
        desc = QLabel(
            "Wizard ini akan mendeteksi hardware Anda dan menginstall komponen yang diperlukan."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #ccc;")
        layout.addWidget(desc)
        layout.addStretch()


# ---------------------------------------------------------------------------
# Page 2 — Hardware detection (async)
# ---------------------------------------------------------------------------
class HardwarePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Deteksi Hardware")
        self.setSubTitle("Mendeteksi CPU, RAM, dan GPU...")
        self._layout = QVBoxLayout(self)
        self._spinner = QLabel("Memeriksa sistem...")
        self._spinner.setStyleSheet("color: #aaa;")
        self._layout.addWidget(self._spinner)
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Komponen", "Hasil"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._layout.addWidget(self._table)
        self._table.hide()
        self._worker: HardwareDetectionWorker | None = None
        self._system_info: dict[str, Any] = {}

    def initializePage(self) -> None:
        self._table.hide()
        self._spinner.show()
        self._spinner.setText("Memeriksa sistem...")
        self._worker = HardwareDetectionWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, info: dict[str, Any]) -> None:
        if "error" in info:
            self._spinner.setText("Gagal: %s" % info["error"])
            return
        self._system_info = info
        self._spinner.hide()
        self._fill_table(info)
        self._table.show()
        self.setSubTitle("Hasil deteksi hardware")
        self.wizard().setProperty("system_info", info)

    def _fill_table(self, info: dict[str, Any]) -> None:
        rows = []
        cpu = info.get("cpu") or {}
        rows.append(("CPU", "%s (%s cores)" % (cpu.get("name", "—"), cpu.get("cores", "—"))))
        rows.append(("RAM", "%s GB" % info.get("ram_gb", "—")))
        gpus = info.get("gpu") or []
        if gpus:
            g = gpus[0]
            rows.append(("GPU", "%s (%s MB VRAM)" % (g.get("name", "—"), g.get("vram_mb", 0))))
            rows.append(("CUDA", g.get("cuda_version") or "Tidak tersedia"))
        else:
            rows.append(("GPU", "Tidak terdeteksi"))
            rows.append(("CUDA", "—"))
        rows.append(("Profil", info.get("recommended_profile", "—")))
        self._table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(k))
            self._table.setItem(i, 1, QTableWidgetItem(str(v)))
        self._table.resizeRowsToContents()

    def system_info(self) -> dict[str, Any]:
        return self._system_info


# ---------------------------------------------------------------------------
# Page 3 — Component selection
# ---------------------------------------------------------------------------
class ComponentsPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Pilih Komponen")
        self.setSubTitle("Pilih komponen yang akan diunduh dan diinstall.")
        layout = QVBoxLayout(self)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Komponen", "Ukuran"])
        layout.addWidget(self._tree)
        self._total_label = QLabel("Total download: 0 MB")
        self._total_label.setStyleSheet("font-weight: bold; color: #ccc;")
        layout.addWidget(self._total_label)
        self._colmap_item: QTreeWidgetItem | None = None
        self._openmvs_item: QTreeWidgetItem | None = None
        self._pdal_item: QTreeWidgetItem | None = None
        self._prefs = _load_components_preference()

    def initializePage(self) -> None:
        info = self.wizard().property("system_info")
        if not info:
            return
        resolver = DependencyResolver(info)
        required = resolver.get_required_packages()
        optional = resolver.get_optional_packages()
        self._tree.clear()
        total_mb = 0
        for pkg in required:
            item = QTreeWidgetItem([pkg.name + " (Wajib)", "~%s MB" % pkg.install_size_mb])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(0, Qt.ItemDataRole.UserRole, pkg)
            item.setCheckState(0, Qt.CheckState.Checked)
            self._tree.addTopLevelItem(item)
            self._colmap_item = item
            total_mb += pkg.install_size_mb
        for pkg in optional:
            if pkg.name == "OpenMVS":
                item = QTreeWidgetItem([pkg.name + " — mesh 3D", "~%s MB" % pkg.install_size_mb])
                self._openmvs_item = item
            else:
                item = QTreeWidgetItem([pkg.name + " — DTM/orthophoto", "~%s MB" % pkg.install_size_mb])
                self._pdal_item = item
            item.setData(0, Qt.ItemDataRole.UserRole, pkg)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if pkg.name == "OpenMVS":
                item.setCheckState(0, Qt.CheckState.Checked if self._prefs.get("openmvs") else Qt.CheckState.Unchecked)
            elif pkg.name == "PDAL":
                item.setCheckState(0, Qt.CheckState.Checked if self._prefs.get("pdal_gdal") else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.addTopLevelItem(item)
            total_mb += pkg.install_size_mb
        self._tree.itemChanged.connect(self._update_total)
        self._update_total()

    def _update_total(self) -> None:
        total = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                pkg = item.data(0, Qt.ItemDataRole.UserRole)
                if pkg:
                    total += getattr(pkg, "install_size_mb", 0)
        self._total_label.setText("Total download: %s MB" % total)

    def get_selected_packages(self) -> list[DependencyPackage]:
        """Return list of packages that are checked (required always, optional if checked)."""
        selected: list[DependencyPackage] = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            pkg = item.data(0, Qt.ItemDataRole.UserRole)
            if pkg:
                selected.append(pkg)
        return selected

    def get_components_dict(self) -> dict[str, bool]:
        """Return {openmvs: bool, pdal_gdal: bool} for setup_complete.json."""
        openmvs = False
        pdal_gdal = False
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            pkg = item.data(0, Qt.ItemDataRole.UserRole)
            if not pkg:
                continue
            if item.checkState(0) == Qt.CheckState.Checked:
                if pkg.name == "OpenMVS":
                    openmvs = True
                elif pkg.name in ("PDAL", "GDAL"):
                    pdal_gdal = True
        return {"openmvs": openmvs, "pdal_gdal": pdal_gdal}


# ---------------------------------------------------------------------------
# Page 4 — Download & install
# ---------------------------------------------------------------------------
class InstallPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Instalasi")
        self.setSubTitle("Mengunduh dan menginstall komponen...")
        layout = QVBoxLayout(self)
        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, 100)
        self._overall_bar.setValue(0)
        layout.addWidget(QLabel("Progress keseluruhan:"))
        layout.addWidget(self._overall_bar)
        self._package_labels: dict[str, QLabel] = {}
        self._package_container = QFrame()
        self._package_layout = QVBoxLayout(self._package_container)
        layout.addWidget(self._package_container)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(180)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self._log)
        self._cancel_btn = QPushButton("Batalkan")
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn)
        self._worker: InstallWorker | None = None
        self._dest_dir = Path.home() / ".mapfree" / "deps"
        self._dest_dir.mkdir(parents=True, exist_ok=True)

    def initializePage(self) -> None:
        wizard = self.wizard()
        comp_page = getattr(wizard, "_comp_page", None)
        if comp_page is not None and hasattr(comp_page, "get_selected_packages"):
            packages = comp_page.get_selected_packages()
        else:
            packages = []
        self._log.clear()
        self._overall_bar.setValue(0)
        for name, lbl in list(self._package_labels.items()):
            lbl.deleteLater()
        self._package_labels.clear()
        while self._package_layout.count():
            item = self._package_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not packages:
            self._append_log("Tidak ada yang diunduh.")
            self._overall_bar.setValue(100)
            self._cancel_btn.setEnabled(False)
            wizard.setButtonText(QWizard.WizardButton.FinishButton, "Selesai & Buka MapFree")
            self._worker = None
            return
        for pkg in packages:
            lbl = QLabel("[%s] Menunggu..." % pkg.name)
            lbl.setStyleSheet("color: #aaa;")
            self._package_layout.addWidget(lbl)
            self._package_labels[pkg.name] = lbl
        self._worker = InstallWorker(packages, self._dest_dir)
        self._worker.log_line.connect(self._append_log)
        self._worker.package_progress.connect(self._on_package_progress)
        self._worker.overall_progress.connect(self._on_overall)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.start()

    def _append_log(self, line: str) -> None:
        self._log.append(line)

    def _on_package_progress(self, name: str, current_mb: int, total_mb: int) -> None:
        if name in self._package_labels:
            if total_mb > 0:
                self._package_labels[name].setText(
                    "[%s] %s/%s MB" % (name, current_mb, total_mb)
                )
            else:
                self._package_labels[name].setText("[%s] Mengunduh..." % name)

    def _on_overall(self, value: int, maximum: int) -> None:
        if maximum > 0:
            self._overall_bar.setMaximum(100)
            self._overall_bar.setValue(int(100 * value / maximum))

    def _on_finished_ok(self) -> None:
        self._overall_bar.setValue(100)
        self._append_log("Semua selesai. Klik 'Selesai' untuk membuka MapFree.")
        self._cancel_btn.setEnabled(False)
        wizard = self.wizard()
        wizard.setButtonText(QWizard.WizardButton.FinishButton, "Selesai & Buka MapFree")

    def _on_finished_error(self, msg: str) -> None:
        self._append_log("Gagal: %s" % msg)
        self._cancel_btn.setEnabled(False)

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._cancel_btn.setEnabled(False)


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------
class FirstRunWizard(QWizard):
    """First-run setup: hardware detection, component choice, download and install."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MapFree — First Run Setup")
        self.setMinimumSize(640, 480)
        self.setStyleSheet(
            "QWidget { background: #2b2b2b; color: #ddd; }"
            "QLabel { color: #ddd; }"
            "QTableWidget { background: #1e1e1e; color: #ddd; }"
            "QTreeWidget { background: #1e1e1e; color: #ddd; }"
            "QTextEdit { background: #1e1e1e; color: #ccc; }"
            "QProgressBar { border: 1px solid #555; border-radius: 4px; text-align: center; }"
            "QPushButton { background: #3a3a3a; color: #ddd; border: 1px solid #555; padding: 6px 14px; }"
        )
        self.addPage(WelcomePage(self))
        self._hw_page = HardwarePage(self)
        self.addPage(self._hw_page)
        self._comp_page = ComponentsPage(self)
        self.addPage(self._comp_page)
        self._install_page = InstallPage(self)
        self.addPage(self._install_page)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

    def accept(self) -> None:
        """On Finish: save setup_complete.json and close."""
        info = self.property("system_info")
        if info and hasattr(self._comp_page, "get_components_dict"):
            comp = self._comp_page.get_components_dict()
            _save_setup_complete(info, comp)
        super().accept()
