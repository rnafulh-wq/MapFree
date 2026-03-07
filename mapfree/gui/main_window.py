"""Main application window — Blender/Metashape-style layout and dark theme."""

import os
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QStatusBar,
    QMessageBox,
    QApplication,
    QFileDialog,
    QLabel,
    QComboBox,
    QPushButton,
    QStyle,
)
from PySide6.QtCore import Qt, QTimer

from mapfree.gui.panels import (
    ProjectPanel,
    ConsolePanel,
    ProgressPanel,
    STATUS_RUNNING,
    STATUS_DONE,
    STATUS_ERROR,
)
from mapfree.gui.panels.viewer_panel import ViewerPanel
from mapfree.gui.panels.project_history_panel import (
    ProjectHistoryPanel,
    add_project as add_project_to_history,
    update_status as update_project_history_status,
)
from mapfree.gui.map_widget import MapWidget
from mapfree.gui.qt_controller import QtController
from mapfree.gui.workers import PipelineWorker, MemoryMonitorWorker
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
    Priority: mesh/ or mvs/ mesh > dense fused.ply > final_results/dense.ply > final_results/sparse.ply.
    """
    proj = Path(project_path)
    try:
        from mapfree.core.project_structure import resolve_project_paths
        paths = resolve_project_paths(proj)
        mesh_dir = paths.mesh
        dense_dir = paths.dense
    except Exception:
        mesh_dir = proj / "mvs"
        dense_dir = proj / "dense"
    for mvs_dir in (mesh_dir, proj / "mvs", proj / "openmvs"):
        if not mvs_dir.exists():
            continue
        for name in ("scene_mesh_refine.ply", "scene_mesh.ply"):
            p = mvs_dir / name
            if p.exists() and p.stat().st_size > 0:
                return str(p), True
    fused = dense_dir / "fused.ply"
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
        self._start_memory_monitor()
        QTimer.singleShot(500, self._check_colmap_installation)
        QTimer.singleShot(700, self._check_trial_expired)

    def _check_trial_expired(self) -> None:
        """If trial is expired, show license dialog non-blocking."""
        try:
            from mapfree.application.license_manager import (
                LicenseStatus,
                _get_trial_status,
            )
            if _get_trial_status() == LicenseStatus.TRIAL_EXPIRED:
                self._on_license()
        except Exception:
            pass

    def _check_colmap_installation(self):
        """Check dependencies at startup; skip dialog if setup already complete and recent."""
        try:
            from mapfree.application.setup_state import (
                should_skip_dependency_dialog,
                save_setup_state,
            )
            from mapfree.utils.dependency_check import check_all_dependencies
            from mapfree.gui.dialogs.dependency_dialog import DependencyDialog

            if should_skip_dependency_dialog():
                return
            # Re-check if file was older than 7 days
            results = check_all_dependencies()
            if should_skip_dependency_dialog(recheck_results=results):
                save_setup_state(results)
                return
            missing_critical = [
                name for name, s in results.items() if s.critical and not s.available
            ]
            if missing_critical:
                dlg = DependencyDialog(results, parent=self)
                dlg.exec()
        except Exception:
            try:
                from mapfree.engines.colmap_engine import verify_colmap_installation
                if not verify_colmap_installation():
                    QMessageBox.warning(
                        self,
                        "COLMAP Not Configured",
                        "COLMAP executable not found. Please configure in Settings.",
                    )
            except Exception:
                pass

    def _on_settings(self) -> None:
        """Open the Settings dialog."""
        from mapfree.gui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(parent=self)
        dlg.exec()

    def _on_license(self) -> None:
        """Open the License Activation dialog."""
        from mapfree.gui.dialogs.license_dialog import LicenseDialog
        dlg = LicenseDialog(parent=self)
        dlg.exec()

    def _on_check_deps(self) -> None:
        """Show dependency status dialog (manual refresh)."""
        from mapfree.utils.dependency_check import check_all_dependencies, invalidate_cache
        from mapfree.gui.dialogs.dependency_dialog import DependencyDialog
        invalidate_cache()
        results = check_all_dependencies()
        dlg = DependencyDialog(results, parent=self)
        dlg.exec()

    def _start_memory_monitor(self):
        """Start background memory monitor; warn user when RSS > threshold and suggest decimation."""
        try:
            import psutil  # noqa: F401
        except ImportError:
            return
        self._memory_monitor = MemoryMonitorWorker(threshold_mb=2048.0, interval_sec=10.0)
        self._memory_monitor.memoryHigh.connect(self._on_memory_high)
        self._memory_monitor.start()

    def _on_memory_high(self, rss_mb: float, threshold_mb: float):
        """Warn user and suggest decimating large meshes when process memory is high."""
        QMessageBox.warning(
            self,
            "High Memory Usage",
            "Process memory is high (%.0f MB, threshold %.0f MB).\n\n"
            "Consider decimating large meshes (View → Load mesh with fewer vertices, or use a LOD export) to reduce memory usage."
            % (rss_mb, threshold_mb),
        )

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
        view_menu.addSeparator()
        self._measure_distance_action = view_menu.addAction("Measure &Distance", self._on_toggle_measure_distance)
        self._measure_distance_action.setCheckable(True)

        edit_menu.addSeparator()
        edit_menu.addAction("&Settings…", self._on_settings)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About")
        help_menu.addSeparator()
        help_menu.addAction("Aktivasi &Lisensi…", self._on_license)
        help_menu.addAction("Cek &Dependencies…", self._on_check_deps)

    def _setup_toolbar(self):
        self._toolbar = QToolBar("Main")
        self._toolbar.setMovable(False)
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
        self._status_project = QLabel("Project: —")
        self._status_project.setStyleSheet("color: #A0A2A6; font-size: 11px;")
        self._statusbar.addPermanentWidget(self._status_project)
        self._status_crs = QLabel("CRS: —")
        self._status_fps = QLabel("FPS: —")
        self._status_mem = QLabel("Mem: —")
        self._status_cpu = QLabel("CPU: —")
        self._status_colmap = QLabel("COLMAP: —")
        self._status_mode = QLabel("Mode: Navigation")
        for w in (self._status_crs, self._status_fps, self._status_mem,
                  self._status_cpu, self._status_colmap, self._status_mode):
            w.setStyleSheet("color: #A0A2A6; font-size: 11px;")
            w.setMinimumWidth(72)
        self._statusbar.addPermanentWidget(self._status_crs)
        self._statusbar.addPermanentWidget(self._status_fps)
        self._statusbar.addPermanentWidget(self._status_mem)
        self._statusbar.addPermanentWidget(self._status_cpu)
        self._statusbar.addPermanentWidget(self._status_colmap)
        self._statusbar.addPermanentWidget(self._status_mode)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status_widgets)
        self._status_timer.start(2000)

    def _update_status_widgets(self) -> None:
        """Update status bar: project name, memory, CPU, COLMAP."""
        if hasattr(self, "_status_project") and self._status_project is not None:
            if self._project_path:
                self._status_project.setText("Project: %s" % self._project_path.name)
            else:
                self._status_project.setText("Project: —")
        if hasattr(self, "_status_mem") and self._status_mem is not None:
            try:
                import psutil
                proc = psutil.Process()
                rss_mb = proc.memory_info().rss / (1024 * 1024)
                self._status_mem.setText("Mem: %.0f MB" % rss_mb)
            except Exception:
                self._status_mem.setText("Mem: —")
        if hasattr(self, "_status_cpu") and self._status_cpu is not None:
            try:
                import psutil
                pct = psutil.cpu_percent(interval=None)
                self._status_cpu.setText("CPU: %d%%" % int(pct))
            except Exception:
                self._status_cpu.setText("CPU: —")
        if hasattr(self, "_status_colmap") and self._status_colmap is not None:
            cache = getattr(self, "_colmap_status_cache", None)
            cache_time = getattr(self, "_colmap_status_time", 0)
            now = time.monotonic()
            if cache is None or (now - cache_time) > 30:
                try:
                    from mapfree.engines.colmap_engine import resolve_colmap_executable
                    resolve_colmap_executable()
                    self._colmap_status_cache = True
                except Exception:
                    self._colmap_status_cache = False
                self._colmap_status_time = now
            if self._colmap_status_cache:
                self._status_colmap.setText("COLMAP: ✓ Ditemukan")
                self._status_colmap.setStyleSheet("color: #4CAF50; font-size: 11px;")
            else:
                self._status_colmap.setText("COLMAP: ✗ Tidak ada")
                self._status_colmap.setStyleSheet("color: #e74c3c; font-size: 11px;")

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
        self._map_container = self._create_map_container()

        self._workspace = QStackedWidget()
        self._workspace.addWidget(self._viewer_panel)   # index 0 = 3D
        self._workspace.addWidget(self._map_container)  # index 1 = Map
        self._workspace.setCurrentIndex(0)  # default 3D until GPS available
        tm = getattr(self._viewer_panel, "tool_manager", None)
        if tm is not None:
            tm.active_tool_changed.connect(self._on_measurement_tool_changed)
        mc = getattr(self._viewer_panel, "measurement_controller", None)
        if mc is not None:
            mc.resultAdded.connect(self._on_measurement_result_added)
        if hasattr(self._viewer_panel, "progressChanged"):
            self._viewer_panel.progressChanged.connect(self._progress_panel.update_progress)
        if hasattr(self._viewer_panel, "mesh_loaded"):
            self._viewer_panel.mesh_loaded.connect(self._on_viewer_mesh_loaded)
        if hasattr(self._viewer_panel, "geometry_load_failed"):
            self._viewer_panel.geometry_load_failed.connect(self._on_viewer_geometry_load_failed)

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        # Left sidebar: min 220px, max 320px, default 260px; user can resize
        left_widget = QWidget()
        left_widget.setMinimumWidth(220)
        left_widget.setMaximumWidth(320)
        left_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.addWidget(self._project_panel)
        self._history_panel = ProjectHistoryPanel(self)
        self._history_panel.resumeRequested.connect(self._on_history_resume)
        self._history_panel.openOutputRequested.connect(self._on_history_open_output)
        left_splitter.addWidget(self._history_panel)
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 0)
        left_splitter.setSizes([400, 180])
        left_layout.addWidget(left_splitter)
        horizontal.addWidget(left_widget)
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
        horizontal.setSizes([260, 900])

        main_layout.addWidget(horizontal)
        main_layout.addWidget(self._progress_panel)

        self.setCentralWidget(central)

    def _create_map_container(self) -> QWidget:
        """Map tab: toolbar (basemap, Fit to Photos) + info label + map widget."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Basemap:"))
        self._basemap_combo = QComboBox()
        self._basemap_combo.addItems(["OSM", "Satellite", "None"])
        self._basemap_combo.setCurrentText("OSM")
        self._basemap_combo.currentTextChanged.connect(self._on_basemap_changed)
        bar.addWidget(self._basemap_combo)
        fit_btn = QPushButton("Fit to Photos")
        fit_btn.clicked.connect(lambda: self.map_widget.fit_to_photos())
        bar.addWidget(fit_btn)
        bar.addStretch()
        self._map_photo_info = QLabel("GPS: — / —")
        self._map_photo_info.setStyleSheet("color: #A0A2A6; font-size: 11px;")
        bar.addWidget(self._map_photo_info)
        layout.addLayout(bar)
        layout.addWidget(self.map_widget)
        return container

    def _on_basemap_changed(self, text: str) -> None:
        name = "OpenStreetMap" if text == "OSM" else ("Satellite" if text == "Satellite" else "None")
        self.map_widget.set_basemap(name)

    def _set_map_photo_info(self, gps_count: int, total: int) -> None:
        """Update map tab info: GPS: gps_count / total."""
        if getattr(self, "_map_photo_info", None) is None:
            return
        if total is None or total < 0:
            self._map_photo_info.setText("GPS: %d / —" % gps_count)
        else:
            self._map_photo_info.setText("GPS: %d / %d" % (gps_count, total))

    def _create_viewer_widget(self):
        if not self._gl_enabled:
            return _viewer_disabled_widget(self)
        if os.environ.get("MAPFREE_NO_OPENGL") == "1":
            return ViewerPanel(self)
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
        viewer.tool_manager = tool_manager
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

    def _on_history_resume(self, project_path: str) -> None:
        """Open project from history (Resume)."""
        if not project_path or not Path(project_path).is_dir():
            return
        self._project_path = Path(project_path)
        images_sub = self._project_path / "images"
        try:
            from mapfree.core.state import load_state
            state = load_state(project_path)
            saved_images = state.get("images")
            if isinstance(saved_images, list) and saved_images:
                self._project_panel.set_image_list(saved_images)
        except Exception:
            pass
        if images_sub.is_dir():
            self._image_path = images_sub
        self._project_panel.set_job_name(self._project_path.name)
        self._refresh_project_panel()
        self._update_run_enabled()
        path, is_mesh = _get_best_result_path(self._project_path)
        if path:
            if is_mesh:
                self._viewer_panel.load_mesh(str(path))
            else:
                self._viewer_panel.load_point_cloud(str(path))
        self._statusbar.showMessage("Opened: %s" % project_path)
        if hasattr(self, "_history_panel") and self._history_panel is not None:
            self._history_panel.refresh()

    def _on_history_open_output(self, project_path: str) -> None:
        """Open project output folder in file explorer."""
        if not project_path:
            return
        p = Path(project_path)
        target = str(p) if p.is_dir() else str(p.parent)
        try:
            if sys.platform == "win32":
                os.startfile(target)  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(
                    ["xdg-open", target] if sys.platform != "darwin" else ["open", target]
                )
        except Exception:
            pass

    def _connect_project_panel(self):
        self._project_panel.startRequested.connect(self._start_pipeline)
        self._project_panel.stopRequested.connect(self._on_stop_requested)
        self._project_panel.outputFolderRequested.connect(self._on_set_output_folder)
        self._project_panel.stepsChanged.connect(self._update_run_enabled)
        self._project_panel.imageListChanged.connect(self._on_image_list_changed)
        self._update_run_enabled()

    def _on_image_list_changed(self, paths: list):
        """Photo list changed in panel (Add/Remove/Clear). Update run eligibility."""
        self._update_run_enabled()
        if paths:
            try:
                from mapfree.geospatial.exif_reader import extract_gps_from_paths
                from mapfree.geospatial.geojson_builder import build_geojson_points
                pts = extract_gps_from_paths([Path(p) for p in paths])
                if pts:
                    geojson = build_geojson_points(pts)
                    self._controller.camerasLoaded.emit(geojson)
                    self._set_map_photo_info(len(pts), len(paths))
                    self._switch_to_map_if_gps()
                    self.map_widget.load_geojson_layer("Cameras", geojson)
                else:
                    self._set_map_photo_info(0, len(paths))
            except Exception:
                pass

    def _can_run(self):
        """Semua 4 langkah: nama job, foto (list atau folder), penyimpanan, kualitas."""
        job = self._project_panel.get_job_name()
        has_images = self._project_panel.get_image_list() or self._image_path
        return bool(job and has_images and self._project_path)

    def _update_run_enabled(self):
        self._project_panel.set_run_enabled(self._can_run())
        can_run = self._can_run() and (self._worker is None or not self._worker.isRunning())
        self._run_action.setEnabled(can_run)

    def _refresh_project_panel(self):
        if self._image_path:
            try:
                image_count = len(list_images(Path(self._image_path)))
                self._project_panel.set_image_count(image_count)
            except (OSError, TypeError):
                self._project_panel.set_image_count(0)
        self._project_panel.set_output_folder(
            str(self._project_path) if self._project_path else ""
        )

    def _on_new_job(self):
        """Reset: kosongkan nama job, foto, penyimpanan. Run dinonaktifkan sampai 4 langkah terisi."""
        self._image_path = None
        self._project_path = None
        self._project_panel.set_job_name("")
        self._project_panel.set_image_list([])
        self._project_panel.set_output_folder("")
        self._update_run_enabled()
        self._statusbar.showMessage("New job. Isi 1–4: nama, import foto, penyimpanan, kualitas.")

    def _get_image_dir_for_validation(self) -> Path | None:
        """Return the folder containing input photos, or None if not set."""
        if self._image_path and Path(self._image_path).is_dir():
            return Path(self._image_path).resolve()
        img_list = self._project_panel.get_image_list()
        if img_list:
            return Path(img_list[0]).resolve().parent
        return None

    def _on_set_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Pilih folder output (parent)",
            str(self._project_path.parent) if self._project_path else "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        job_name = self._project_panel.get_job_name()
        if not job_name:
            QMessageBox.warning(self, "Output", "Isi dulu Job name sebelum memilih output folder.")
            return
        base_dir = Path(folder)
        project_dir = base_dir / job_name
        image_dir = self._get_image_dir_for_validation()
        if image_dir is not None:
            try:
                out_resolved = project_dir.resolve()
                img_resolved = image_dir.resolve()
                if out_resolved != img_resolved and out_resolved.is_relative_to(img_resolved):
                    QMessageBox.warning(
                        self,
                        "Output folder",
                        "Output folder tidak boleh berada di dalam folder foto.",
                    )
                    return
            except (ValueError, OSError):
                pass
        if project_dir.exists():
            try:
                has_files = any(project_dir.iterdir())
            except OSError:
                has_files = True
            if has_files:
                resp = QMessageBox.question(
                    self,
                    "Project sudah ada",
                    "Folder project sudah ada:\n\n%s\n\nLanjutkan dan pakai folder ini?"
                    % str(project_dir),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return
        try:
            from mapfree.core.project_structure import create_project_structure
            paths = create_project_structure(base_dir, job_name)
            self._project_path = Path(paths.root)
        except Exception as e:
            QMessageBox.critical(self, "Output", "Gagal membuat project structure: %s" % e)
            return
        self._refresh_project_panel()
        self._update_run_enabled()
        self._statusbar.showMessage("Output: %s" % str(self._project_path))

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

    def _on_viewer_mesh_loaded(self, path: str, vertex_count: int):
        """When viewer finishes loading mesh/point cloud: idle progress, CRS, measurement geometry, status."""
        self._progress_panel.update_state("idle")
        self._progress_panel.update_progress(0)
        self._update_status_crs()
        mc = getattr(self._viewer_panel, "measurement_controller", None)
        if mc:
            mc.set_geometry_from_file(path)
        self._statusbar.showMessage("Loaded: %s" % path)

    def _on_viewer_geometry_load_failed(self, path: str):
        """When async geometry load fails: idle progress, status message."""
        self._progress_panel.update_state("idle")
        self._progress_panel.update_progress(0)
        self._statusbar.showMessage("Failed to load: %s" % path)

    def _on_load_point_cloud(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Point Cloud",
            str(self._project_path) if self._project_path else "",
            "PLY files (*.ply);;LAS files (*.las);;All files (*)",
        )
        if path:
            if getattr(self._viewer_panel, "load_point_cloud_async", None):
                self._progress_panel.update_state("Loading point cloud…")
                self._progress_panel.update_progress(0)
                if self._viewer_panel.load_point_cloud_async(path):
                    pass  # result via mesh_loaded / geometry_load_failed
                else:
                    self._progress_panel.update_state("idle")
                    self._statusbar.showMessage("Load already in progress.")
            else:
                if self._viewer_panel.load_point_cloud(path):
                    self._update_status_crs()
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
            if getattr(self._viewer_panel, "load_mesh_async", None):
                self._progress_panel.update_state("Loading mesh…")
                self._progress_panel.update_progress(0)
                if self._viewer_panel.load_mesh_async(path):
                    pass  # result via mesh_loaded / geometry_load_failed
                else:
                    self._progress_panel.update_state("idle")
                    self._statusbar.showMessage("Load already in progress.")
            elif self._viewer_panel.load_mesh(path):
                self._update_status_crs()
                mc = getattr(self._viewer_panel, "measurement_controller", None)
                if mc:
                    mc.set_geometry_from_file(path)
                self._statusbar.showMessage("Loaded mesh: %s" % path)
            else:
                self._statusbar.showMessage("Failed to load mesh.")

    def _on_clear_view(self):
        self._viewer_panel.clear_scene()
        self._project_panel.set_measurements_count(0)
        self._statusbar.showMessage("View cleared.")

    def _on_zoom_fit(self):
        self._viewer_panel.zoom_fit()
        self._statusbar.showMessage("Zoom fit.")

    def _on_toggle_axes(self):
        self._viewer_panel.toggle_axes()
        self._statusbar.showMessage("Axes toggled.")

    def _on_view_mode_changed(self, index: int):
        self._workspace.setCurrentIndex(index)

    def _on_toggle_measure_distance(self):
        tm = getattr(self._viewer_panel, "tool_manager", None)
        mc = getattr(self._viewer_panel, "measurement_controller", None)
        if tm is None or mc is None:
            self._measure_distance_action.setChecked(False)
            return
        if self._measure_distance_action.isChecked():
            from mapfree.gui.interaction import DistanceTool
            tm.set_active_tool(DistanceTool(mc))
        else:
            tm.set_active_tool(None)

    def _update_status_crs(self) -> None:
        """Set status bar CRS from measurement engine if available."""
        if not hasattr(self, "_status_crs") or self._status_crs is None:
            return
        mc = getattr(self._viewer_panel, "measurement_controller", None)
        if mc is None or not hasattr(mc, "engine"):
            self._status_crs.setText("CRS: —")
            return
        try:
            crs = mc.engine.crs_manager.get_crs()
            self._status_crs.setText("CRS: %s" % (crs or "—"))
        except Exception:
            self._status_crs.setText("CRS: —")

    def _on_measurement_result_added(self, _result_dict) -> None:
        """Update project panel Measurements count when a measurement is added."""
        mc = getattr(self._viewer_panel, "measurement_controller", None)
        if mc is not None and hasattr(mc, "session"):
            count = len(getattr(mc.session, "measurements", []))
            self._project_panel.set_measurements_count(count)

    def _on_measurement_tool_changed(self, tool) -> None:
        """When Distance tool is active: crosshair cursor, status message, and Mode widget."""
        from mapfree.gui.interaction.distance_tool import DistanceTool
        if isinstance(tool, DistanceTool):
            self._statusbar.showMessage("Distance Mode Active — Ctrl+click to add points, ESC to cancel")
            if hasattr(self, "_status_mode") and self._status_mode is not None:
                self._status_mode.setText("Mode: Distance")
            if hasattr(self._viewer_panel, "setCursor"):
                self._viewer_panel.setCursor(Qt.CursorShape.CrossCursor)
            if hasattr(self._measure_distance_action, "setChecked"):
                self._measure_distance_action.setChecked(True)
        else:
            self._statusbar.showMessage("Ready")
            if hasattr(self, "_status_mode") and self._status_mode is not None:
                self._status_mode.setText("Mode: Navigation")
            if hasattr(self._viewer_panel, "setCursor"):
                self._viewer_panel.setCursor(Qt.CursorShape.ArrowCursor)
            if hasattr(self, "_measure_distance_action") and self._measure_distance_action is not None:
                self._measure_distance_action.setChecked(False)

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
        add_project_to_history(str(self._project_path), "completed")
        if hasattr(self, "_history_panel") and self._history_panel is not None:
            self._history_panel.refresh()
        images_sub = self._project_path / "images"
        try:
            from mapfree.core.state import load_state
            state = load_state(project_folder)
            saved_images = state.get("images")
            if isinstance(saved_images, list) and saved_images:
                self._project_panel.set_image_list(saved_images)
        except Exception:
            pass
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
            n_total = n
            if len(points) > 0:
                geojson = build_geojson_points(points)
                self._controller.camerasLoaded.emit(geojson)
                self._set_map_photo_info(len(points), n_total)
                self._switch_to_map_if_gps()
                self.map_widget.load_geojson_layer("Cameras", geojson)
            else:
                self._set_map_photo_info(0, n_total)
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

        def _on_sparse_checkpoint(pts_bin_path: str):
            """Live preview: load points3D.bin and refresh point cloud viewer."""
            if not pts_bin_path:
                return
            try:
                from mapfree.utils.colmap_io import read_points3d_bin
                import numpy as np
                xyz_rgb = read_points3d_bin(pts_bin_path)
                if xyz_rgb is not None and len(xyz_rgb) > 0:
                    # Viewer expects RGB in [0,1] when float; colmap_io returns [0,255]
                    arr = xyz_rgb.astype(np.float32)
                    arr[:, 3:6] /= 255.0
                    pc = self._viewer_panel.get_visualizer()
                    pc.refresh_points(arr)
            except Exception:
                pass  # Don't block pipeline on preview failure

        self._controller.sparseCheckpoint.connect(_on_sparse_checkpoint)

        def on_cameras_loaded(geojson):
            n_gps = len(geojson.get("features", [])) if isinstance(geojson, dict) else 0
            n_tot = None
            if self._image_path:
                try:
                    n_tot = len(list_images(self._image_path))
                except (OSError, TypeError):
                    pass
            self._set_map_photo_info(n_gps, n_tot)
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
        if self._project_path:
            update_project_history_status(str(self._project_path), "completed")
            if hasattr(self, "_history_panel") and self._history_panel is not None:
                self._history_panel.refresh()
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
        if self._project_path:
            update_project_history_status(str(self._project_path), "failed")
            if hasattr(self, "_history_panel") and self._history_panel is not None:
                self._history_panel.refresh()
        if self._current_stage:
            self._project_panel.set_stage_status(self._current_stage, STATUS_ERROR)
        self._project_panel.set_running(False)
        self._stop_action.setEnabled(False)
        self._update_run_enabled()
        self._console_panel.append_log("Pipeline error: %s" % (message or "An error occurred."), "error")
        self._vertical_splitter.setSizes([400, 200])
        self._toggle_console_action.setChecked(True)
        if self._console_panel.parent():
            self._console_panel.setVisible(True)

    def _on_stop_requested(self):
        self._controller.stop_project()

    def _start_pipeline(self):
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._can_run():
            miss = []
            if not self._project_panel.get_job_name():
                miss.append("1. Nama job")
            if not self._project_panel.get_image_list() and not self._image_path:
                miss.append("2. Import foto")
            if not self._project_path:
                miss.append("3. Penyimpanan job")
            QMessageBox.warning(
                self,
                "Run Pipeline",
                "Lengkapi dulu:\n" + "\n".join(miss or ["Semua langkah 1–4."]),
            )
            return
        project_path = str(self._project_path)
        image_list = self._project_panel.get_image_list()
        if image_list:
            from mapfree.utils.image_list_utils import copy_or_link_images
            from mapfree.core.state import load_state, save_state
            images_dir = Path(project_path) / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            copy_or_link_images([Path(p) for p in image_list], images_dir)
            self._image_path = images_dir
            state = load_state(project_path)
            state["images"] = image_list
            save_state(project_path, state)
        image_path = str(self._image_path)
        add_project_to_history(project_path, "in_progress")
        if hasattr(self, "_history_panel") and self._history_panel is not None:
            self._history_panel.refresh()
        quality = self._project_panel.get_quality()
        matcher = self._project_panel.get_matcher()
        self._project_panel.set_running(True)
        self._project_panel.set_all_pending()
        self._progress_panel.set_log_path(Path(project_path) / "logs" / "mapfree.log")
        self._worker = PipelineWorker(
            self._controller,
            image_path,
            project_path,
            quality=quality,
            matcher=matcher,
        )
        self._worker.started.connect(lambda: self._progress_panel.update_state("running"))
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_pipeline_error)
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
        mon = getattr(self, "_memory_monitor", None)
        if mon is not None and mon.isRunning():
            mon.stop()
            mon.wait(2000)
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
