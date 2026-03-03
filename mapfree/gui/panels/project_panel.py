"""Project panel — urutan: 1 Nama job, 2 Import foto, 3 Penyimpanan, 4 Kualitas, lalu Run."""

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
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
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
        btn_import = QPushButton("Select folder...")
        btn_import.setMinimumHeight(24)
        btn_import.clicked.connect(self.importPhotosRequested.emit)
        pl.addWidget(btn_import)
        self._image_count_label = QLabel("0 images")
        self._image_count_label.setProperty("class", "muted")
        pl.addWidget(self._image_count_label)

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

        layout.addWidget(project_grp)

        # --- Outputs (group) ---
        pipeline_grp = QGroupBox("Outputs")
        pipeline_grp.setObjectName("outputsGroup")
        pl2 = QVBoxLayout(pipeline_grp)
        pl2.setContentsMargins(8, 10, 8, 8)
        pl2.setSpacing(4)

        self._stage_tree = QTreeWidget()
        self._stage_tree.setHeaderLabels(["Stage", "Status"])
        self._stage_tree.setColumnCount(2)
        self._stage_tree.setColumnWidth(0, 160)
        self._stage_tree.setRootIsDecorated(False)
        self._stage_tree.setAlternatingRowColors(False)
        self._items = {}
        for key, label in STAGE_ITEMS:
            item = QTreeWidgetItem([label, "Pending"])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            self._stage_tree.addTopLevelItem(item)
            self._items[key] = item
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

    def _on_steps_changed(self):
        self.stepsChanged.emit()

    def get_job_name(self):
        return self._job_edit.text().strip() if self._job_edit else ""

    def set_job_name(self, name: str):
        if self._job_edit:
            self._job_edit.setText(name or "")

    def set_image_count(self, count: int):
        self._image_count_label.setText("%d images" % max(0, count))
        self.stepsChanged.emit()

    def set_output_folder(self, path: str):
        self._output_label.setText(path or "—")
        self._output_label.setToolTip(path or "")
        self.stepsChanged.emit()

    def get_quality(self):
        return (self._quality_combo.currentText() or "Medium").lower()

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
        if status == STATUS_PENDING:
            item.setText(1, "Pending")
            item.setForeground(1, QColor("#A0A2A6"))
        elif status == STATUS_RUNNING:
            item.setText(1, "Running")
            item.setForeground(1, QColor("#2F6FED"))
        elif status == STATUS_DONE:
            item.setText(1, "Done")
            item.setForeground(1, QColor("#4CAF50"))
        elif status == STATUS_ERROR:
            item.setText(1, "Error")
            item.setForeground(1, QColor("#D94F4F"))
        else:
            item.setText(1, status)
            item.setForeground(1, QColor("#E6E6E6"))

    def set_all_pending(self):
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
