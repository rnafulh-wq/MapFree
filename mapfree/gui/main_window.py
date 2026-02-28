"""Main application window — Blender/Metashape-style layout and dark theme."""

import time
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QMenuBar,
    QMenu,
    QToolBar,
    QStatusBar,
    QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt

from mapfree.gui.panels import (
    ProjectPanel,
    ConsolePanel,
    ProgressPanel,
    ViewerPanel,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_DONE,
    STATUS_ERROR,
)
from mapfree.gui.qt_controller import QtController
from mapfree.gui.workers import PipelineWorker

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
        file_menu.addAction("&New...")
        file_menu.addAction("&Open...")
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction("&Preferences...")

        view_menu = menubar.addMenu("&View")
        view_menu.addAction("&Toolbar", self._toggle_toolbar).setCheckable(True)
        view_menu.actions()[-1].setChecked(True)
        view_menu.addAction("&Status Bar", self._toggle_statusbar).setCheckable(True)
        view_menu.actions()[-1].setChecked(True)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About")

    def _setup_toolbar(self):
        self._toolbar = QToolBar("Main")
        self._toolbar.setMovable(True)
        self.addToolBar(self._toolbar)
        self._toolbar.addAction("New")
        self._toolbar.addAction("Open")
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
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(self._viewer_panel)
        vertical.addWidget(self._console_panel)
        horizontal.addWidget(vertical)
        horizontal.setStretchFactor(0, 0)
        horizontal.setStretchFactor(1, 1)
        horizontal.setSizes([320, 880])

        main_layout.addWidget(horizontal)
        main_layout.addWidget(self._progress_panel)

        self.setCentralWidget(central)

    def _connect_project_panel(self):
        self._project_panel.startRequested.connect(self._start_pipeline)
        self._project_panel.stopRequested.connect(self._on_stop_requested)

    def _connect_controller_signals(self):
        self._controller.progressChanged.connect(self._progress_panel.update_progress)
        self._controller.logReceived.connect(self._console_panel.append_log)
        self._controller.stateChanged.connect(self._on_state_changed)
        self._controller.pipelineFinished.connect(self._on_pipeline_finished)
        self._controller.pipelineError.connect(self._on_pipeline_error)

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
        self._project_panel.set_running(True)
        self._project_panel.set_all_pending()
        self._worker = PipelineWorker(
            self._controller,
            "",
            "",
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self):
        self._worker = None
        self._project_panel.set_running(False)
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
