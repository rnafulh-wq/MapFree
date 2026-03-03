"""Console panel — live log with monospace, auto-scroll, color coding."""

import html
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QGroupBox,
    QSizePolicy,
)
from PySide6.QtGui import QFont


# Log level colors (dark theme)
LEVEL_COLORS = {
    "info": "#e0e0e0",
    "warning": "#d4a84b",
    "error": "#e74c3c",
}


class ConsolePanel(QWidget):
    """Bottom-right panel: read-only log, monospace, auto-scroll, INFO/WARNING/ERROR colors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        grp = QGroupBox("Console")
        grp.setObjectName("consoleGroup")
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(6, 8, 6, 6)
        gl.setSpacing(0)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Pipeline output…")
        self._log.setMinimumHeight(80)
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._log.setFont(font)
        self._log.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px 6px;
                font-family: Consolas, Monospace;
            }
        """)
        gl.addWidget(self._log)
        layout.addWidget(grp)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setMinimumHeight(0)

    def append_log(self, text: str, level: str = "info"):
        """Append a line with color. level: info (white), warning (yellow), error (red). Thread-safe when used as slot."""
        if not text:
            return
        color = LEVEL_COLORS.get(level.lower(), LEVEL_COLORS["info"])
        escaped = html.escape(text)
        line = '<span style="color:%s">%s</span>' % (color, escaped)
        self._log.append(line)
        scrollbar = self._log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_plain(self, text: str):
        """Append as plain text (no level). Uses info color. For backward compatibility."""
        self.append_log(text, "info")

    def clear_log(self):
        self._log.clear()
