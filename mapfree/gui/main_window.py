"""Main application window — Blender/Metashape-style layout and dark theme."""

import time
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QToolBar,
    QStatusBar,
    QMessageBox,
    QApplication,
    QFileDialog,
)
from PySide6.QtCore import Qt

from mapfree.gui.panels import (
    ProjectPanel,
    ConsolePanel,
    ProgressPanel,
    ViewerPanel,
    STATUS_RUNNING,
    STATUS_DONE,
    STATUS_ERROR,
)
from mapfree.gui.qt_controller import QtController
from mapfree.gui.workers import PipelineWorker
from mapfree.utils.file_utils import list_images

# Order of stages for "done" progression
_STAGE_ORDER = [
    "feature_extraction",
    "matching",
    "sparse",
    "dense",
    "post_process",
]


def _load_stylesheet():
    qss_path = Path(__file__).resolve().parent / "resources" / "styles.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


class MainWindow(QMainWindow):
    """Main window: menu, toolbar, Project | Viewer+Console, Progress. Dark theme."""

    def __init__(self):
        super().__init__()
        self._controller = QtController()
        self._worker = None
        self._current_stage = None
        self._image_path = None
        self._project_path = None
        self._setup_window()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_central_widget()
        self._apply_style()
        self._connect_controller_signals()
        self._connect_project_panel()

    def _setup_window(self):
        self.setWindowTitle("MapFree Engine")
        self.setMinimumSize(1200, 800)

    def _apply_style(self):
        sheet = _load_stylesheet()
        if sheet:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(sheet)

    def _setup_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction("&New Project", self._on_new_job)
        file_menu.addAction("&Open Project", self._on_open)
        export_menu = file_menu.addMenu("&Export")
        export_menu.addAction("Export &DTM", self._on_export_dtm)
        export_menu.addAction("Export &DSM", self._on_export_dsm)
        export_menu.addAction("Export &Orthophoto", self._on_export_orthophoto)
        export_menu.addAction("Export &All", self._on_export_all)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction("&Preferences...")

        view_menu = menubar.addMenu("&View")
        view_menu.addAction("&Toolbar", self._toggle_toolbar).setCheckable(True)
        view_menu.actions()[-1].setChecked(True)
        view_menu.addAction("&Status Bar", self._toggle_statusbar).setCheckable(True)
        view_menu.actions()[-1].setChecked(True)
        self._toggle_console_action = view_menu.addAction("Toggle &Console", self._toggle_console)
        self._toggle_console_action.setCheckable(True)
        self._toggle_console_action.setChecked(True)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About")

    def _setup_toolbar(self):
        self._toolbar = QToolBar("Main")
        self._toolbar.setMovable(True)
        self.addToolBar(self._toolbar)
        self._toolbar.addAction("New job", self._on_new_job)
        self._toolbar.addAction("Import Photos", self._on_import_photos)
        self._toolbar.addAction("Set output", self._on_set_output_folder)
        self._toolbar.addSeparator()
        self._toolbar.addAction("Run", self._start_pipeline)

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    def _setup_central_widget(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._project_panel = ProjectPanel()
        self._console_panel = ConsolePanel()
        self._progress_panel = ProgressPanel()
        self._viewer_panel = ViewerPanel()

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        horizontal.addWidget(self._project_panel)
        self._vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self._vertical_splitter.addWidget(self._viewer_panel)
        self._vertical_splitter.addWidget(self._console_panel)
        # Viewer : Console = 4 : 1 (stretch and initial sizes)
        self._vertical_splitter.setStretchFactor(0, 4)  # Viewer
        self._vertical_splitter.setStretchFactor(1, 1)  # Console
        _unit = 200
        self._vertical_splitter.setSizes([4 * _unit, 1 * _unit])  # proportional 4:1
        self._vertical_splitter.setHandleWidth(6)
        horizontal.addWidget(self._vertical_splitter)
        horizontal.setStretchFactor(0, 0)
        horizontal.setStretchFactor(1, 1)
        horizontal.setSizes([320, 880])

        main_layout.addWidget(horizontal)
        main_layout.addWidget(self._progress_panel)

        self.setCentralWidget(central)

    def _connect_project_panel(self):
        self._project_panel.startRequested.connect(self._start_pipeline)
        self._project_panel.stopRequested.connect(self._on_stop_requested)
        self._project_panel.importPhotosRequested.connect(self._on_import_photos)
        self._project_panel.outputFolderRequested.connect(self._on_set_output_folder)
        self._project_panel.stepsChanged.connect(self._update_run_enabled)
        self._update_run_enabled()

    def _can_run(self):
        """Semua 4 langkah harus terisi: nama job, foto, penyimpanan, kualitas."""
        job = self._project_panel.get_job_name()
        return bool(job and self._image_path and self._project_path)

    def _update_run_enabled(self):
        self._project_panel.set_run_enabled(self._can_run())

    def _refresh_project_panel(self):
        image_count = 0
        if self._image_path:
            try:
                image_count = len(list_images(Path(self._image_path)))
            except (OSError, TypeError):
                pass
        self._project_panel.set_image_count(image_count)
        self._project_panel.set_output_folder(
            str(self._project_path) if self._project_path else ""
        )

    def _on_new_job(self):
        """Reset: kosongkan nama job, foto, penyimpanan. Run dinonaktifkan sampai 4 langkah terisi."""
        self._image_path = None
        self._project_path = None
        self._project_panel.set_job_name("")
        self._project_panel.set_image_count(0)
        self._project_panel.set_output_folder("")
        self._update_run_enabled()
        self._statusbar.showMessage("New job. Isi 1–4: nama, import foto, penyimpanan, kualitas.")

    def _on_set_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Pilih folder penyimpanan job",
            str(self._project_path) if self._project_path else "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self._project_path = Path(folder)
        self._refresh_project_panel()
        self._update_run_enabled()
        self._statusbar.showMessage("Penyimpanan: %s" % folder)

    def _require_project_for_export(self) -> bool:
        """Return True if project_path is set; else show warning and return False."""
        if not self._project_path or not Path(self._project_path).is_dir():
            QMessageBox.warning(
                self,
                "Export",
                "No project open. Open or create a project first.",
            )
            return False
        return True

    def _on_export_dtm(self):
        if not self._require_project_for_export():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Export DTM — Select output folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self._controller.export_dtm(self._project_path, Path(folder) / "dtm.tif")

    def _on_export_dsm(self):
        if not self._require_project_for_export():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Export DSM — Select output folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self._controller.export_dsm(self._project_path, Path(folder) / "dsm.tif")

    def _on_export_orthophoto(self):
        if not self._require_project_for_export():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Export Orthophoto — Select output folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self._controller.export_orthophoto(
            self._project_path, Path(folder) / "orthophoto.tif"
        )

    def _on_export_all(self):
        if not self._require_project_for_export():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Export All — Select output folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        self._controller.export_all(self._project_path, Path(folder))

    def _on_export_started(self):
        self._statusbar.showMessage("Export in progress…")

    def _on_export_finished(self, result):
        self._statusbar.showMessage("Export completed.")
        if isinstance(result, dict):
            QMessageBox.information(
                self, "Export", "DTM, DSM, and Orthophoto exported successfully."
            )
        else:
            QMessageBox.information(self, "Export", "Export completed successfully.")

    def _on_export_error(self, message: str):
        self._statusbar.showMessage("Export failed.")
        QMessageBox.critical(self, "Export Error", message or "Export failed.")

    def _on_dense_ready(self, file_path: str):
        """Load fused.ply into the 3D viewer when dense reconstruction completes."""
        if file_path and Path(file_path).exists():
            self._viewer_panel.load_point_cloud(file_path)

    def _on_open(self):
        """Buka folder proyek (penyimpanan). Jika ada subfolder 'images', dipakai sebagai folder foto."""
        project_folder = QFileDialog.getExistingDirectory(
            self,
            "Open project",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not project_folder:
            return
        self._project_path = Path(project_folder)
        images_sub = self._project_path / "images"
        if images_sub.is_dir():
            self._image_path = images_sub
        self._project_panel.set_job_name(self._project_path.name)
        self._refresh_project_panel()
        self._update_run_enabled()
        self._statusbar.showMessage("Opened: %s" % project_folder)

    def _on_import_photos(self):
        image_folder = QFileDialog.getExistingDirectory(
            self,
            "Import foto — Pilih folder berisi foto",
            str(self._image_path) if self._image_path else "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not image_folder:
            return
        self._image_path = Path(image_folder)
        if not self._project_path:
            self._project_path = self._image_path / "output"
        self._refresh_project_panel()
        self._update_run_enabled()
        try:
            n = len(list_images(self._image_path)) if self._image_path else 0
        except (OSError, TypeError):
            n = 0
        self._statusbar.showMessage("Foto: %s (%d file)" % (image_folder, n))

    def _connect_controller_signals(self):
        self._controller.progressChanged.connect(self._progress_panel.update_progress)
        self._controller.logReceived.connect(self._console_panel.append_log)
        self._controller.stateChanged.connect(self._on_state_changed)
        self._controller.pipelineFinished.connect(self._on_pipeline_finished)
        self._controller.pipelineError.connect(self._on_pipeline_error)
        self._controller.exportStarted.connect(self._on_export_started)
        self._controller.exportFinished.connect(self._on_export_finished)
        self._controller.exportError.connect(self._on_export_error)
        self._controller.denseReady.connect(self._on_dense_ready)

    def _on_state_changed(self, state: str):
        self._statusbar.showMessage(state)
        self._progress_panel.update_state(state)
        self._update_stage_tree(state)

    def _update_stage_tree(self, state: str):
        if state == "idle":
            self._project_panel.set_all_pending()
            self._current_stage = None
            return
        if state == "running":
            self._project_panel.set_all_pending()
            self._project_panel.set_stage_status("feature_extraction", STATUS_RUNNING)
            self._current_stage = "feature_extraction"
            return
        if state == "sparse":
            self._project_panel.set_stage_status("feature_extraction", STATUS_DONE)
            self._project_panel.set_stage_status("matching", STATUS_DONE)
            self._project_panel.set_stage_status("sparse", STATUS_RUNNING)
            self._current_stage = "sparse"
            return
        if state == "dense":
            self._project_panel.set_stage_status("sparse", STATUS_DONE)
            self._project_panel.set_stage_status("dense", STATUS_RUNNING)
            self._current_stage = "dense"
            return
        if state == "finished":
            for key in _STAGE_ORDER:
                self._project_panel.set_stage_status(key, STATUS_DONE)
            self._current_stage = None
            return
        if state == "error":
            if self._current_stage:
                self._project_panel.set_stage_status(self._current_stage, STATUS_ERROR)
            self._current_stage = None

    def _on_pipeline_finished(self):
        self._statusbar.showMessage("Pipeline finished successfully.")
        self._progress_panel.update_progress(100)
        for key in _STAGE_ORDER:
            self._project_panel.set_stage_status(key, STATUS_DONE)
        self._project_panel.set_running(False)

    def _on_pipeline_error(self, message: str):
        self._statusbar.showMessage("Pipeline error.")
        if self._current_stage:
            self._project_panel.set_stage_status(self._current_stage, STATUS_ERROR)
        self._project_panel.set_running(False)
        QMessageBox.critical(
            self,
            "Pipeline Error",
            message or "An error occurred.",
        )

    def _on_stop_requested(self):
        self._controller.stop_project()

    def _start_pipeline(self):
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._can_run():
            miss = []
            if not self._project_panel.get_job_name():
                miss.append("1. Nama job")
            if not self._image_path:
                miss.append("2. Import foto")
            if not self._project_path:
                miss.append("3. Penyimpanan job")
            QMessageBox.warning(
                self,
                "Run Pipeline",
                "Lengkapi dulu:\n" + "\n".join(miss or ["Semua langkah 1–4."]),
            )
            return
        image_path = str(self._image_path)
        project_path = str(self._project_path)
        quality = self._project_panel.get_quality()
        self._project_panel.set_running(True)
        self._project_panel.set_all_pending()
        self._worker = PipelineWorker(
            self._controller,
            image_path,
            project_path,
            quality=quality,
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self):
        self._worker = None
        self._project_panel.set_running(False)
        self._update_run_enabled()
        self._progress_panel.update_state("idle")

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Exit",
                "Pipeline is running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._controller.stop_project()
            deadline = time.monotonic() + 15.0
            while self._worker.isRunning() and time.monotonic() < deadline:
                QApplication.processEvents()
                time.sleep(0.05)
            if self._worker.isRunning():
                QMessageBox.warning(
                    self,
                    "Exit",
                    "Pipeline did not stop in time. Exiting anyway.",
                )
        event.accept()

    def _toggle_toolbar(self, checked: bool):
        self._toolbar.setVisible(checked)

    def _toggle_statusbar(self, checked: bool):
        self._statusbar.setVisible(checked)

    def _toggle_console(self):
        if self._console_panel.isVisible():
            self._console_panel.hide()
            self._toggle_console_action.setChecked(False)
            # Give all vertical space to viewer
            h = self._vertical_splitter.size().height()
            self._vertical_splitter.setSizes([h, 0])
        else:
            self._console_panel.show()
            self._toggle_console_action.setChecked(True)
            _unit = 200
            self._vertical_splitter.setSizes([4 * _unit, 1 * _unit])
        self._vertical_splitter.updateGeometry()
