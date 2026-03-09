"""Progress panel — progress bar, current stage label, ETA, Lihat Log."""

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
)


class ProgressPanel(QWidget):
    """Bottom status: current stage label, progress bar, ETA, Lihat Log button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

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

        self._log_path: Path | None = None
        self._log_btn = QPushButton("Lihat Log")
        self._log_btn.setProperty("class", "muted")
        self._log_btn.clicked.connect(self._open_log)
        layout.addWidget(self._log_btn)

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

    def set_log_path(self, path: Path | str | None) -> None:
        """Set path to log file for 'Lihat Log' button."""
        self._log_path = Path(path) if path else None
        self._log_btn.setEnabled(self._log_path is not None)

    def _open_log(self) -> None:
        if not self._log_path:
            return
        if not self._log_path.is_file():
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(self._log_path))  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(
                    ["xdg-open", str(self._log_path)] if sys.platform != "darwin"
                    else ["open", str(self._log_path)]
                )
        except Exception:
            pass
