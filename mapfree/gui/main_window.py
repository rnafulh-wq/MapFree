"""Main application window — Blender/Metashape-style layout and dark theme."""

import os
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QStatusBar,
    QMessageBox,
    QApplication,
    QFileDialog,
    QLabel,
    QComboBox,
    QStyle,
)
from PySide6.QtCore import Qt

from mapfree.gui.panels import (
    ProjectPanel,
    ConsolePanel,
    ProgressPanel,
    STATUS_RUNNING,
    STATUS_DONE,
    STATUS_ERROR,
)
from mapfree.gui.map_widget import MapWidget
from mapfree.gui.qt_controller import QtController
from mapfree.gui.workers import PipelineWorker
from mapfree.utils.file_utils import list_images

# When GL is disabled: simple label, same no-op API as viewer so callers don't break
class _ViewerDisabledWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        lab = QLabel("3D Viewer Disabled")
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet("color: #8a8a8a; font-size: 12px;")
        layout.addWidget(lab)

    def load_point_cloud(self, file_path: str) -> bool:
        return False

    def load_mesh(self, file_path: str) -> bool:
        return False

    def clear_scene(self) -> None:
        pass

    def zoom_fit(self) -> None:
        pass

    def toggle_axes(self) -> None:
        pass


def _viewer_disabled_widget(parent=None):
    return _ViewerDisabledWidget(parent)


# Placeholder when OpenGL not yet enabled; same API as ViewerWidget
class _ViewerPlaceholder(QWidget):
    """Placeholder until real 3D viewer is enabled. Supports 'Enable 3D viewer' callback."""

    def __init__(self, parent=None, on_enable_gl=None, message: str | None = None):
        super().__init__(parent)
        self._on_enable_gl = on_enable_gl
        layout = QVBoxLayout(self)
        default_msg = (
            "3D Viewer (placeholder). Pipeline, Export, Open Project work.\n"
            "Click the button below to open the 3D viewer in a new window."
        )
        lab = QLabel(message if message else default_msg)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet("color: #8a8a8a; font-size: 12px;")
        layout.addWidget(lab)
        if on_enable_gl is not None:
            from PySide6.QtWidgets import QPushButton
            btn = QPushButton("Open 3D viewer (new window)")
            btn.setStyleSheet("padding: 8px 16px; font-size: 13px;")
            btn.clicked.connect(self._request_enable_gl)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _request_enable_gl(self):
        if self._on_enable_gl is not None:
            self._on_enable_gl()

    def load_point_cloud(self, file_path: str) -> bool:
        return False

    def load_mesh(self, file_path: str) -> bool:
        return False

    def clear_scene(self) -> None:
        pass

    def zoom_fit(self) -> None:
        pass

    def toggle_axes(self) -> None:
        pass


# Order of stages for "done" progression (sparse → dense → geospatial → post_process)
_STAGE_ORDER = [
    "feature_extraction",
    "matching",
    "sparse",
    "dense",
    "geospatial",
    "post_process",
]


def _get_best_result_path(project_path: Path):
    """
    Return (path_str, is_mesh) for the best 3D result to show in viewer (WebODM/Metashape-style).
    Priority: mvs/ mesh > openmvs/ mesh > dense fused.ply > final_results/dense.ply > final_results/sparse.ply.
    """
    proj = Path(project_path)
    # OpenMVS mesh from mvs/ (new engine) or openmvs/ (legacy)
    for mvs_dir in ("mvs", "openmvs"):
        mvs = proj / mvs_dir
        for name in ("scene_mesh_refine.ply", "scene_mesh.ply"):
            p = mvs / name
            if p.exists() and p.stat().st_size > 0:
                return str(p), True
    # Dense point cloud
    fused = proj / "dense" / "fused.ply"
    if fused.exists() and fused.stat().st_size >= 1024:
        return str(fused), False
    final = proj / "final_results"
    dense_ply = final / "dense.ply"
    if dense_ply.exists() and dense_ply.stat().st_size >= 1024:
        return str(dense_ply), False
    sparse_ply = final / "sparse.ply"
    if sparse_ply.exists():
        return str(sparse_ply), False
    return None, False


def _load_stylesheet():
    qss_path = Path(__file__).resolve().parent / "resources" / "styles.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


class MainWindow(QMainWindow):
    """Main window: menu, toolbar, Project | Viewer+Console, Progress. Dark theme."""

    def __init__(self, gl_enabled: bool = True):
        super().__init__()
        self._gl_enabled = gl_enabled
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
        if not self._gl_enabled:
            self._statusbar.showMessage("3D viewer disabled due to OpenGL incompatibility.")
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
        self._export_actions = []
        for label, slot in [
            ("Export &DTM", self._on_export_dtm),
            ("Export &DSM", self._on_export_dsm),
            ("Export &Orthophoto", self._on_export_orthophoto),
            ("Export &All", self._on_export_all),
        ]:
            a = export_menu.addAction(label, slot)
            self._export_actions.append(a)
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
        self._toggle_console_action.setChecked(False)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About")

    def _setup_toolbar(self):
        self._toolbar = QToolBar("Main")
        self._toolbar.setMovable(True)
        self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(self._toolbar)
        style = QApplication.style()
        self._run_action = self._toolbar.addAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Run", self._start_pipeline
        )
        self._stop_action = self._toolbar.addAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "Stop", self._on_stop_requested
        )
        self._stop_action.setEnabled(False)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(QLabel("View:"))
        self._view_mode_combo = QComboBox()
        self._view_mode_combo.addItems(["3D", "Map"])
        self._view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        self._toolbar.addWidget(self._view_mode_combo)
        self._toolbar.addSeparator()
        self._toolbar.addAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            "Load Point Cloud",
            self._on_load_point_cloud,
        )
        self._toolbar.addAction(
            style.standardIcon(QStyle.StandardPixmap.SP_FileIcon),
            "Load Mesh",
            self._on_load_mesh,
        )
        self._toolbar.addSeparator()
        self._toggle_console_action.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self._toolbar.addAction(self._toggle_console_action)

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
        self._viewer_panel = self._create_viewer_widget()
        self.map_widget = MapWidget()

        self._workspace = QStackedWidget()
        self._workspace.addWidget(self._viewer_panel)   # index 0 = 3D
        self._workspace.addWidget(self.map_widget)      # index 1 = Map
        self._workspace.setCurrentIndex(0)  # default 3D until GPS available

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        horizontal.addWidget(self._project_panel)
        self._vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self._vertical_splitter.addWidget(self._workspace)
        self._vertical_splitter.addWidget(self._console_panel)
        self._vertical_splitter.setStretchFactor(0, 1)
        self._vertical_splitter.setStretchFactor(1, 0)
        self._vertical_splitter.setHandleWidth(6)
        # Default: console collapsed (height 0); toggle via toolbar/menu
        self._vertical_splitter.setSizes([1, 0])
        horizontal.addWidget(self._vertical_splitter)
        horizontal.setStretchFactor(0, 0)
        horizontal.setStretchFactor(1, 1)
        horizontal.setSizes([300, 900])

        main_layout.addWidget(horizontal)
        main_layout.addWidget(self._progress_panel)

        self.setCentralWidget(central)

    def _create_viewer_widget(self):
        if not self._gl_enabled:
            return _viewer_disabled_widget(self)
        if os.environ.get("MAPFREE_NO_OPENGL") == "1":
            return _ViewerPlaceholder(self)
        if os.environ.get("MAPFREE_OPENGL") == "1":
            return self._create_gl_viewer()
        return _ViewerPlaceholder(self, on_enable_gl=self._replace_with_gl_viewer)

    def _create_gl_viewer(self):
        from mapfree.viewer.gl_widget import ViewerWidget, set_default_opengl_format
        from mapfree.gui.interaction import ToolManager
        from mapfree.gui.controllers import MeasurementController
        from mapfree.engines.inspection import MeasurementEngine
        set_default_opengl_format()
        viewer = ViewerWidget()
        engine = MeasurementEngine()
        measurement_controller = MeasurementController(engine)
        measurement_controller.set_ray_callback(viewer.compute_ray_from_screen)
        tool_manager = ToolManager()
        viewer.set_tool_manager(tool_manager)
        viewer.measurement_controller = measurement_controller
        return viewer

    def _replace_with_gl_viewer(self):
        """Open 3D viewer in a separate process so a segfault does not close MapFree."""
        import subprocess
        project_path = str(self._project_path) if self._project_path else ""
        env = os.environ.copy()
        env.setdefault("QT_OPENGL", "software")
        env.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        try:
            subprocess.Popen(
                [sys.executable, "-m", "mapfree.viewer.standalone", project_path],
                env=env,
                start_new_session=True,
            )
            self._statusbar.showMessage("3D viewer opened in a new window.")
        except Exception as e:
            self._statusbar.showMessage("Could not start 3D viewer: %s" % e)
            QMessageBox.warning(
                self,
                "3D Viewer",
                "Could not start 3D viewer: %s\n\nOpen PLY files with MeshLab or CloudCompare." % e,
            )

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
        can_run = self._can_run() and (self._worker is None or not self._worker.isRunning())
        self._run_action.setEnabled(can_run)

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
        for a in getattr(self, "_export_actions", []):
            a.setEnabled(False)

    def _on_export_finished(self, result):
        for a in getattr(self, "_export_actions", []):
            a.setEnabled(True)
        self._statusbar.showMessage("Export completed.")
        if isinstance(result, dict):
            QMessageBox.information(
                self, "Export", "DTM, DSM, and Orthophoto exported successfully."
            )
        else:
            QMessageBox.information(self, "Export", "Export completed successfully.")

    def _on_export_error(self, message: str):
        for a in getattr(self, "_export_actions", []):
            a.setEnabled(True)
        self._statusbar.showMessage("Export failed.")
        QMessageBox.critical(self, "Export Error", message or "Export failed.")

    def _on_load_point_cloud(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Point Cloud",
            str(self._project_path) if self._project_path else "",
            "PLY files (*.ply);;LAS files (*.las);;All files (*)",
        )
        if path:
            if self._viewer_panel.load_point_cloud(path):
                mc = getattr(self._viewer_panel, "measurement_controller", None)
                if mc:
                    mc.set_geometry_from_file(path)
                self._statusbar.showMessage("Loaded point cloud: %s" % path)
            else:
                self._statusbar.showMessage("Failed to load point cloud.")

    def _on_load_mesh(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Mesh",
            str(self._project_path) if self._project_path else "",
            "PLY/OBJ files (*.ply *.obj);;PLY (*.ply);;OBJ (*.obj);;All files (*)",
        )
        if path:
            if self._viewer_panel.load_mesh(path):
                mc = getattr(self._viewer_panel, "measurement_controller", None)
                if mc:
                    mc.set_geometry_from_file(path)
                self._statusbar.showMessage("Loaded mesh: %s" % path)
            else:
                self._statusbar.showMessage("Failed to load mesh.")

    def _on_clear_view(self):
        self._viewer_panel.clear_scene()
        self._statusbar.showMessage("View cleared.")

    def _on_zoom_fit(self):
        self._viewer_panel.zoom_fit()
        self._statusbar.showMessage("Zoom fit.")

    def _on_toggle_axes(self):
        self._viewer_panel.toggle_axes()
        self._statusbar.showMessage("Axes toggled.")

    def _on_view_mode_changed(self, index: int):
        self._workspace.setCurrentIndex(index)

    def _switch_to_map_if_gps(self):
        """Switch to Map view when GPS/cameras are available (default mode)."""
        if self._view_mode_combo.currentIndex() == 0:
            self._view_mode_combo.setCurrentIndex(1)

    def _on_open(self):
        """Buka folder proyek (penyimpanan). Jika ada subfolder 'images', dipakai sebagai folder foto. Auto-load 3D result di viewer."""
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
        # Auto-load 3D result into viewer (WebODM/Metashape-style)
        path, is_mesh = _get_best_result_path(self._project_path)
        if path:
            if is_mesh:
                self._viewer_panel.load_mesh(path)
            else:
                self._viewer_panel.load_point_cloud(path)
            self._viewer_panel.zoom_fit()
            self._statusbar.showMessage("Opened: %s — 3D model loaded." % project_folder)

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
        try:
            from mapfree.geospatial.exif_reader import extract_gps_from_images
            from mapfree.geospatial.geojson_builder import build_geojson_points
            points = extract_gps_from_images(image_folder)
            if len(points) > 0:
                geojson = build_geojson_points(points)
                self._controller.camerasLoaded.emit(geojson)
                # Switch to Map and load camera layer (queued if map not ready); auto zoom in addGeoJSONLayer
                self._switch_to_map_if_gps()
                self.map_widget.load_geojson_layer("Cameras", geojson)
            else:
                self._statusbar.showMessage("No GPS metadata found in selected images.")
        except Exception:
            pass

    def _connect_controller_signals(self):
        self._controller.progressChanged.connect(self._progress_panel.update_progress)
        self._controller.logReceived.connect(self._console_panel.append_log)
        self._controller.stateChanged.connect(self._on_state_changed)
        self._controller.pipelineFinished.connect(self._on_pipeline_finished)
        self._controller.pipelineError.connect(self._on_pipeline_error)
        self._controller.exportStarted.connect(self._on_export_started)
        self._controller.exportFinished.connect(self._on_export_finished)
        self._controller.exportError.connect(self._on_export_error)
        def _on_point_cloud_loaded(path):
            self._viewer_panel.load_point_cloud(path)
            mc = getattr(self._viewer_panel, "measurement_controller", None)
            if mc:
                mc.set_geometry_from_file(path)
        def _on_mesh_loaded(path):
            self._viewer_panel.load_mesh(path)
            mc = getattr(self._viewer_panel, "measurement_controller", None)
            if mc:
                mc.set_geometry_from_file(path)
        self._controller.pointCloudLoaded.connect(_on_point_cloud_loaded)
        self._controller.meshLoaded.connect(_on_mesh_loaded)
        def on_cameras_loaded(geojson):
            self._switch_to_map_if_gps()
            self.map_widget.load_geojson_layer("Cameras", geojson)
        self._controller.camerasLoaded.connect(on_cameras_loaded)
        # Forward map JS console (log/warn/error) to app console panel
        def on_map_js_console(level: int, message: str):
            log_level = "error" if level == 2 else ("warning" if level == 1 else "info")
            self._console_panel.append_log(message, log_level)
        self.map_widget.jsConsoleMessage.connect(on_map_js_console)

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
        if state == "geospatial":
            self._project_panel.set_stage_status("dense", STATUS_DONE)
            self._project_panel.set_stage_status("geospatial", STATUS_RUNNING)
            self._current_stage = "geospatial"
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
        # Auto-load 3D result into viewer (WebODM/Metashape-style)
        if self._project_path:
            path, is_mesh = _get_best_result_path(self._project_path)
            if path:
                if is_mesh:
                    self._viewer_panel.load_mesh(path)
                else:
                    self._viewer_panel.load_point_cloud(path)
                self._viewer_panel.zoom_fit()
                self._statusbar.showMessage("Pipeline finished. 3D model loaded in viewer.")

    def _on_pipeline_error(self, message: str):
        self._statusbar.showMessage("Pipeline error.")
        if self._current_stage:
            self._project_panel.set_stage_status(self._current_stage, STATUS_ERROR)
        self._project_panel.set_running(False)
        self._stop_action.setEnabled(False)
        self._update_run_enabled()
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
        self._run_action.setEnabled(False)
        self._stop_action.setEnabled(True)
        self._worker.start()

    def _on_worker_finished(self):
        self._worker = None
        self._project_panel.set_running(False)
        self._stop_action.setEnabled(False)
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
        h = self._vertical_splitter.size().height()
        if h <= 0:
            h = 400
        if self._vertical_splitter.sizes()[1] > 0:
            # Collapse: give all space to workspace
            self._vertical_splitter.setSizes([h, 0])
            self._toggle_console_action.setChecked(False)
        else:
            # Expand: console max 25% of splitter height
            console_h = min(int(0.25 * h), max(120, h // 4))
            self._vertical_splitter.setSizes([h - console_h, console_h])
            self._console_panel.setMaximumHeight(int(0.25 * h))
            self._toggle_console_action.setChecked(True)
        self._vertical_splitter.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep console at most 25% when visible
        if self._vertical_splitter.sizes()[1] > 0:
            h = self._vertical_splitter.size().height()
            if h > 0:
                self._console_panel.setMaximumHeight(int(0.25 * h))
