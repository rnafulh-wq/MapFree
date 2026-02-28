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
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

# Display names and order for pipeline stages
STAGE_ITEMS = [
    ("feature_extraction", "Feature Extraction"),
    ("matching", "Matching"),
    ("sparse", "Sparse Reconstruction"),
    ("dense", "Dense Reconstruction"),
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
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("Pengaturan Job")
        header.setProperty("class", "header")
        layout.addWidget(header)

        # 1. Nama job
        layout.addWidget(QLabel("1. Nama job"))
        self._job_edit = QLineEdit()
        self._job_edit.setPlaceholderText("Masukkan nama job")
        self._job_edit.textChanged.connect(self._on_steps_changed)
        layout.addWidget(self._job_edit)

        # 2. Import foto
        layout.addWidget(QLabel("2. Import foto"))
        btn_import = QPushButton("Pilih folder foto...")
        btn_import.clicked.connect(self.importPhotosRequested.emit)
        layout.addWidget(btn_import)
        self._image_count_label = QLabel("Foto: 0")
        self._image_count_label.setProperty("class", "muted")
        layout.addWidget(self._image_count_label)

        # 3. Penyimpanan
        layout.addWidget(QLabel("3. Penyimpanan job"))
        btn_output = QPushButton("Pilih folder penyimpanan...")
        btn_output.clicked.connect(self.outputFolderRequested.emit)
        layout.addWidget(btn_output)
        self._output_label = QLabel("—")
        self._output_label.setWordWrap(True)
        self._output_label.setProperty("class", "muted")
        layout.addWidget(self._output_label)

        # 4. Kualitas
        layout.addWidget(QLabel("4. Kualitas pengolahan"))
        self._quality_combo = QComboBox()
        self._quality_combo.addItems(QUALITY_OPTIONS)
        self._quality_combo.setCurrentText("Medium")
        self._quality_combo.currentTextChanged.connect(self._on_steps_changed)
        layout.addWidget(self._quality_combo)

        stage_header = QLabel("Pipeline Stages")
        stage_header.setProperty("class", "header")
        layout.addWidget(stage_header)

        self._stage_tree = QTreeWidget()
        self._stage_tree.setHeaderLabels(["Stage", "Status"])
        self._stage_tree.setColumnCount(2)
        self._stage_tree.setColumnWidth(0, 180)
        self._stage_tree.setRootIsDecorated(False)
        self._stage_tree.setAlternatingRowColors(False)
        self._items = {}
        for key, label in STAGE_ITEMS:
            item = QTreeWidgetItem([label, "Pending"])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            self._stage_tree.addTopLevelItem(item)
            self._items[key] = item
        layout.addWidget(self._stage_tree)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton("Run")
        self._start_btn.setObjectName("startButton")
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("stopButton")
        self._stop_btn.setEnabled(False)
        self._start_btn.clicked.connect(self.startRequested.emit)
        self._stop_btn.clicked.connect(self.stopRequested.emit)
        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._stop_btn)
        layout.addLayout(btn_layout)

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
        self._image_count_label.setText("Foto: %d" % max(0, count))
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
            item.setForeground(1, QColor("#8a8a8a"))
        elif status == STATUS_RUNNING:
            item.setText(1, "Running")
            item.setForeground(1, QColor("#5b9bd5"))
        elif status == STATUS_DONE:
            item.setText(1, "Done")
            item.setForeground(1, QColor("#70ad47"))
        elif status == STATUS_ERROR:
            item.setText(1, "Error")
            item.setForeground(1, QColor("#e74c3c"))
        else:
            item.setText(1, status)
            item.setForeground(1, QColor("#e0e0e0"))

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

    @property
    def start_button(self):
        return self._start_btn

    @property
    def stop_button(self):
        return self._stop_btn
