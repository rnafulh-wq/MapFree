"""Project panel — urutan: 1 Nama job, 2 Import foto, 3 Penyimpanan, 4 Kualitas, lalu Run."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QTreeWidget,
    QTreeWidgetItem,
    QSizePolicy,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont

# Display names and order for pipeline stages (sparse → dense → geospatial → post_process)
STAGE_ITEMS = [
    ("feature_extraction", "Feature Extraction"),
    ("matching", "Matching"),
    ("sparse", "Sparse Reconstruction"),
    ("dense", "Dense Reconstruction"),
    ("geospatial", "Geospatial (DTM / Orthophoto)"),
    ("post_process", "Post-Process"),
]

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"

QUALITY_OPTIONS = ["High", "Medium", "Low"]

MATCHER_OPTIONS = [
    ("Auto (Recommended)", "auto"),
    ("Spatial (GPS-based)", "spatial"),
    ("Sequential", "sequential"),
    ("Exhaustive", "exhaustive"),
    ("Vocab Tree", "vocab_tree"),
]


class ProjectPanel(QWidget):
    """
    Panel dengan urutan: 1 Nama job, 2 Import foto, 3 Penyimpanan, 4 Kualitas.
    Tombol Run hanya aktif jika keempat langkah sudah diisi.
    """

    startRequested = Signal()
    stopRequested = Signal()
    importPhotosRequested = Signal()
    outputFolderRequested = Signal()
    stepsChanged = Signal()
    imageListChanged = Signal(list)  # list of absolute path strings

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- Dataset (group) ---
        project_grp = QGroupBox("Dataset")
        project_grp.setObjectName("datasetGroup")
        pl = QVBoxLayout(project_grp)
        pl.setContentsMargins(8, 10, 8, 8)
        pl.setSpacing(4)

        def field_label(text: str) -> QLabel:
            lb = QLabel(text)
            lb.setProperty("class", "field")
            lb.setMinimumWidth(100)
            return lb

        pl.addWidget(field_label("Job name"))
        self._job_edit = QLineEdit()
        self._job_edit.setPlaceholderText("Project name")
        self._job_edit.textChanged.connect(self._on_steps_changed)
        pl.addWidget(self._job_edit)

        pl.addWidget(field_label("Images"))
        btn_row1 = QHBoxLayout()
        btn_add_photos = QPushButton("Add Photos")
        btn_add_photos.setMinimumHeight(24)
        btn_add_photos.clicked.connect(self._on_add_photos)
        btn_add_folder = QPushButton("Add Folder")
        btn_add_folder.setMinimumHeight(24)
        btn_add_folder.clicked.connect(self._on_add_folder)
        btn_row1.addWidget(btn_add_photos)
        btn_row1.addWidget(btn_add_folder)
        pl.addLayout(btn_row1)
        self._image_count_label = QLabel("0 foto | 0 dengan GPS | 0 tanpa GPS")
        self._image_count_label.setProperty("class", "muted")
        self._image_count_label.setWordWrap(True)
        pl.addWidget(self._image_count_label)
        self._photo_list = QListWidget()
        self._photo_list.setMaximumHeight(120)
        self._photo_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        pl.addWidget(self._photo_list)
        btn_row2 = QHBoxLayout()
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._on_remove_selected)
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._on_clear_all)
        btn_row2.addWidget(btn_remove)
        btn_row2.addWidget(btn_clear)
        pl.addLayout(btn_row2)
        self._image_list_paths: list[str] = []
        self._gps_status: dict[str, bool] = {}
        self._gps_worker = None
        self._last_image_dir = ""

        pl.addWidget(field_label("Output"))
        btn_output = QPushButton("Select folder...")
        btn_output.setMinimumHeight(24)
        btn_output.clicked.connect(self.outputFolderRequested.emit)
        pl.addWidget(btn_output)
        self._output_label = QLabel("—")
        self._output_label.setWordWrap(True)
        self._output_label.setProperty("class", "muted")
        pl.addWidget(self._output_label)

        pl.addWidget(field_label("Quality"))
        self._quality_combo = QComboBox()
        self._quality_combo.addItems(QUALITY_OPTIONS)
        self._quality_combo.setCurrentText("Medium")
        self._quality_combo.currentTextChanged.connect(self._on_steps_changed)
        pl.addWidget(self._quality_combo)

        pl.addWidget(field_label("Matching Method"))
        self._matcher_combo = QComboBox()
        for label, _ in MATCHER_OPTIONS:
            self._matcher_combo.addItem(label)
        self._matcher_combo.setCurrentIndex(0)
        self._matcher_combo.setToolTip(
            "Auto: spatial if ≥80% GPS, exhaustive if <100 photos, vocab tree if >1000, else sequential."
        )
        pl.addWidget(self._matcher_combo)

        layout.addWidget(project_grp)

        # --- Outputs (group) ---
        pipeline_grp = QGroupBox("Outputs")
        pipeline_grp.setObjectName("outputsGroup")
        pipeline_grp.setMinimumHeight(180)
        pl2 = QVBoxLayout(pipeline_grp)
        pl2.setContentsMargins(8, 10, 8, 8)
        pl2.setSpacing(4)

        self._stage_tree = QTreeWidget()
        self._stage_tree.setHeaderLabels(["Stage", "Status"])
        self._stage_tree.setColumnCount(2)
        self._stage_tree.setRootIsDecorated(False)
        self._stage_tree.setAlternatingRowColors(False)
        header = self._stage_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._stage_tree.setColumnWidth(1, 80)
        self._items = {}
        for key, label in STAGE_ITEMS:
            item = QTreeWidgetItem([label, "Pending"])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            self._stage_tree.addTopLevelItem(item)
            self._items[key] = item
        self._running_stage_key = None
        self._running_dot_index = 0
        self._running_timer = QTimer(self)
        self._running_timer.setInterval(400)
        self._running_timer.timeout.connect(self._on_running_animation_tick)
        pl2.addWidget(self._stage_tree)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton("Run")
        self._start_btn.setObjectName("startButton")
        self._start_btn.setMinimumHeight(28)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setMinimumHeight(28)
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self.startRequested.emit)
        self._stop_btn.clicked.connect(self.stopRequested.emit)
        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._stop_btn)
        pl2.addLayout(btn_layout)

        layout.addWidget(pipeline_grp)

        # --- Measurements (group) ---
        meas_grp = QGroupBox("Measurements")
        meas_grp.setObjectName("measurementsGroup")
        ml = QVBoxLayout(meas_grp)
        ml.setContentsMargins(8, 10, 8, 8)
        ml.setSpacing(4)
        self._measurements_label = QLabel("—")
        self._measurements_label.setProperty("class", "muted")
        self._measurements_label.setWordWrap(True)
        self._measurements_label.setToolTip("Measurement count (updated when distance/area is added)")
        ml.addWidget(self._measurements_label)
        layout.addWidget(meas_grp)

        layout.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    IMAGE_FILTER = (
        "Images (*.jpg *.jpeg *.JPG *.JPEG *.png *.PNG *.tif *.tiff *.TIF *.TIFF)"
    )

    def _on_steps_changed(self):
        self.stepsChanged.emit()

    def _on_add_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Pilih Foto",
            self._last_image_dir or "",
            self.IMAGE_FILTER,
        )
        if not files:
            return
        self._last_image_dir = str(Path(files[0]).parent)
        added = [str(Path(f).resolve()) for f in files if Path(f).is_file()]
        for p in added:
            if p not in self._image_list_paths:
                self._image_list_paths.append(p)
        self._refresh_photo_list_and_emit()

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Pilih folder berisi foto", self._last_image_dir or ""
        )
        if not folder:
            return
        self._last_image_dir = folder
        from mapfree.utils.file_utils import list_images
        try:
            paths = list_images(Path(folder))
            for p in paths:
                s = str(p.resolve())
                if s not in self._image_list_paths:
                    self._image_list_paths.append(s)
        except (OSError, TypeError):
            pass
        self._refresh_photo_list_and_emit()

    def _on_remove_selected(self):
        rows = set(i.row() for i in self._photo_list.selectedIndexes())
        for r in sorted(rows, reverse=True):
            if 0 <= r < len(self._image_list_paths):
                self._image_list_paths.pop(r)
        self._refresh_photo_list_and_emit()

    def _on_clear_all(self):
        self._image_list_paths.clear()
        self._gps_status.clear()
        self._refresh_photo_list_and_emit()

    def _refresh_photo_list_and_emit(self):
        self._update_photo_list_ui()
        self._update_counters()
        self.imageListChanged.emit(list(self._image_list_paths))
        self.stepsChanged.emit()
        if self._image_list_paths:
            self._start_gps_worker()

    def _update_photo_list_ui(self):
        self._photo_list.clear()
        for path in self._image_list_paths:
            p = Path(path)
            name = p.name
            size_mb = p.stat().st_size / (1024 * 1024) if p.is_file() else 0
            size_str = "%.1f MB" % size_mb if size_mb >= 1 else "%.0f KB" % (p.stat().st_size / 1024) if p.is_file() else "—"
            has_gps = self._gps_status.get(path)
            gps_str = "✓" if has_gps else "✗"
            item = QListWidgetItem("%s  %s  %s" % (name, gps_str, size_str))
            item.setData(Qt.ItemDataRole.UserRole, path)
            if has_gps is True:
                item.setForeground(QColor("#4CAF50"))
            elif has_gps is False:
                item.setForeground(QColor("#D94F4F"))
            self._photo_list.addItem(item)

    def _update_counters(self):
        n = len(self._image_list_paths)
        with_gps = sum(1 for p in self._image_list_paths if self._gps_status.get(p))
        without = n - with_gps
        self._image_count_label.setText(
            "%d foto | %d dengan GPS | %d tanpa GPS" % (n, with_gps, without)
        )

    def _start_gps_worker(self):
        if self._gps_worker is not None and self._gps_worker.isRunning():
            return
        from mapfree.gui.workers import GpsExtractWorker
        self._gps_worker = GpsExtractWorker(self._image_list_paths)
        self._gps_worker.result.connect(self._on_gps_result)
        self._gps_worker.finished.connect(self._on_gps_finished)
        self._gps_worker.start()

    def _on_gps_result(self, path: str, has_gps: bool):
        key = str(Path(path).resolve())
        self._gps_status[key] = has_gps
        for i in range(self._photo_list.count()):
            item = self._photo_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                gps_str = "✓" if has_gps else "✗"
                text = item.text().rsplit("  ", 2)
                if len(text) >= 2:
                    item.setText("%s  %s  %s" % (text[0], gps_str, text[-1]))
                item.setForeground(QColor("#4CAF50") if has_gps else QColor("#D94F4F"))
                break
        self._update_counters()

    def _on_gps_finished(self):
        self._gps_worker = None

    def get_image_list(self) -> list:
        return list(self._image_list_paths)

    def set_image_list(self, paths: list):
        self._image_list_paths = [str(Path(p).resolve()) for p in paths if Path(p).is_file()]
        self._gps_status.clear()
        self._refresh_photo_list_and_emit()

    def get_job_name(self):
        return self._job_edit.text().strip() if self._job_edit else ""

    def set_job_name(self, name: str):
        if self._job_edit:
            self._job_edit.setText(name or "")

    def set_image_count(self, count: int):
        """Backward compat: set total count when no list (e.g. folder mode or restore)."""
        if not self._image_list_paths:
            self._image_count_label.setText("%d foto | — dengan GPS | — tanpa GPS" % max(0, count))
        self.stepsChanged.emit()

    def set_output_folder(self, path: str):
        self._output_label.setText(path or "—")
        self._output_label.setToolTip(path or "")
        self.stepsChanged.emit()

    def get_quality(self):
        return (self._quality_combo.currentText() or "Medium").lower()

    def get_matcher(self) -> str:
        idx = self._matcher_combo.currentIndex() if self._matcher_combo else 0
        if 0 <= idx < len(MATCHER_OPTIONS):
            return MATCHER_OPTIONS[idx][1]
        return "auto"

    def set_quality(self, quality: str):
        q = quality.capitalize() if quality else "Medium"
        if q in QUALITY_OPTIONS and self._quality_combo:
            self._quality_combo.setCurrentText(q)

    def set_project_info(self, name: str, image_count: int, output_folder: str):
        """Compatibility: set job name, image count, output path in one call."""
        self.set_job_name(name)
        self.set_image_count(image_count)
        self.set_output_folder(output_folder or "—")

    def set_stage_status(self, stage_key: str, status: str):
        item = self._items.get(stage_key)
        if not item:
            return
        font_normal = QFont()
        font_bold = QFont("Arial", 9, QFont.Weight.Bold)
        if status == STATUS_PENDING:
            item.setText(1, "Pending")
            item.setForeground(1, QColor("#9E9E9E"))
            item.setFont(0, font_normal)
        elif status == STATUS_RUNNING:
            item.setText(1, "Running")
            item.setForeground(1, QColor("#FFC107"))
            item.setFont(0, font_bold)
            self._running_stage_key = stage_key
            self._running_dot_index = 0
            if not self._running_timer.isActive():
                self._running_timer.start()
        elif status == STATUS_DONE:
            item.setText(1, "Done")
            item.setForeground(1, QColor("#4CAF50"))
            item.setFont(0, font_normal)
        elif status == STATUS_ERROR:
            item.setText(1, "Error")
            item.setForeground(1, QColor("#F44336"))
            item.setFont(0, font_normal)
        else:
            item.setText(1, status)
            item.setForeground(1, QColor("#E6E6E6"))
            item.setFont(0, font_normal)
        if status != STATUS_RUNNING and stage_key == getattr(self, "_running_stage_key", None):
            self._running_stage_key = None
            if self._running_timer.isActive():
                self._running_timer.stop()

    def _on_running_animation_tick(self):
        """Cycle 'Running' / 'Running.' / 'Running..' / 'Running...' and pulse color."""
        if not self._running_stage_key:
            self._running_timer.stop()
            return
        item = self._items.get(self._running_stage_key)
        if not item:
            self._running_stage_key = None
            self._running_timer.stop()
            return
        self._running_dot_index = (self._running_dot_index + 1) % 4
        dots = "." * self._running_dot_index
        item.setText(1, "Running" + dots)
        # Pulse between #FFC107 and #FFD54F
        color = QColor("#FFD54F" if self._running_dot_index % 2 else "#FFC107")
        item.setForeground(1, color)

    def set_all_pending(self):
        self._running_stage_key = None
        if self._running_timer.isActive():
            self._running_timer.stop()
        for key in self._items:
            self.set_stage_status(key, STATUS_PENDING)

    def set_running(self, running: bool):
        if running:
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
        else:
            self._stop_btn.setEnabled(False)
            # Start enabled state diatur oleh set_run_enabled (dipanggil MainWindow)

    def set_run_enabled(self, enabled: bool):
        """Enable Run only when all 4 steps are done and not running."""
        if not self._stop_btn.isEnabled():
            self._start_btn.setEnabled(enabled)

    def set_measurements_count(self, count: int) -> None:
        """Update Measurements section (e.g. '3 measurements' or '—')."""
        if getattr(self, "_measurements_label", None) is None:
            return
        if count <= 0:
            self._measurements_label.setText("—")
        else:
            self._measurements_label.setText("%d measurement%s" % (count, "s" if count != 1 else ""))

    @property
    def start_button(self):
        return self._start_btn

    @property
    def stop_button(self):
        return self._stop_btn
