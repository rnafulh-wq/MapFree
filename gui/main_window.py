from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QLabel,
)
from PySide6.QtCore import QThread, Signal

from mapfree.api.controller import MapFreeController
from mapfree.profiles.mx150 import MX150_PROFILE


class Worker(QThread):
    event_signal = Signal(object)

    def __init__(self, image_path, project_path):
        super().__init__()
        self.image_path = image_path
        self.project_path = project_path

    def run(self):
        controller = MapFreeController(MX150_PROFILE)
        controller.run_project(
            self.image_path,
            self.project_path,
            self.event_signal.emit,
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MapFree")

        self.progress = QProgressBar()
        self.label = QLabel("Ready")
        self.button = QPushButton("Run Demo")

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.button.clicked.connect(self.start_pipeline)

    def start_pipeline(self):
        self.worker = Worker("images", "project_gui")
        self.worker.event_signal.connect(self.handle_event)
        self.worker.start()

    def handle_event(self, event):
        if event.progress is not None:
            self.progress.setValue(int(event.progress * 100))
        if event.message:
            self.label.setText(event.message)
