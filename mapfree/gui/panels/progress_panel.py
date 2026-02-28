"""Progress panel — progress bar, current stage label, ETA (future)."""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
)


class ProgressPanel(QWidget):
    """Bottom status: current stage label, progress bar, ETA placeholder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        self._stage_label = QLabel("Idle")
        self._stage_label.setMinimumWidth(160)
        self._stage_label.setProperty("class", "muted")
        layout.addWidget(self._stage_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setMinimumWidth(240)
        self._progress.setFormat("%p%")
        layout.addWidget(self._progress, 1)

        self._eta_label = QLabel("")
        self._eta_label.setProperty("class", "muted")
        self._eta_label.setMinimumWidth(80)
        layout.addWidget(self._eta_label)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def update_progress(self, value: int):
        """Set progress bar 0–100. Thread-safe when used as slot."""
        self._progress.setValue(min(100, max(0, value)))

    def update_state(self, state: str):
        """Set current stage / state label. Thread-safe when used as slot."""
        self._stage_label.setText(state if state else "Idle")

    def set_eta(self, text: str):
        """Set ETA text (future improvement)."""
        self._eta_label.setText(text or "")
