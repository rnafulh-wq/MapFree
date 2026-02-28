"""Project panel — project info, pipeline stages tree, Start/Stop."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
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


class ProjectPanel(QWidget):
    """Left panel: project name, image count, output folder, pipeline stage tree, Start/Stop."""

    startRequested = Signal()
    stopRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("Project")
        header.setProperty("class", "header")
        layout.addWidget(header)

        self._project_name = QLabel("—")
        self._project_name.setWordWrap(True)
        self._project_name.setProperty("class", "muted")
        layout.addWidget(self._project_name)

        self._image_count = QLabel("Images: 0")
        self._image_count.setProperty("class", "muted")
        layout.addWidget(self._image_count)

        self._output_folder = QLabel("Output: —")
        self._output_folder.setWordWrap(True)
        self._output_folder.setProperty("class", "muted")
        layout.addWidget(self._output_folder)

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
        self._start_btn = QPushButton("Start")
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

    def set_project_info(self, name: str, image_count: int, output_folder: str):
        self._project_name.setText(name or "—")
        self._image_count.setText("Images: %d" % image_count)
        self._output_folder.setText("Output: %s" % (output_folder or "—"))

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
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)

    @property
    def start_button(self):
        return self._start_btn

    @property
    def stop_button(self):
        return self._stop_btn
