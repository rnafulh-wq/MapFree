"""Project History Panel — shows the 10 most recently opened projects.

History is persisted to ``~/.mapfree/recent_projects.json``.

Schema (per entry)::

    {
        "path": "/absolute/path/to/project",
        "name": "project_name",
        "last_opened": "2026-03-04T12:00:00+00:00",
        "status": "completed" | "in_progress" | "failed",
        "thumbnail": null
    }

Signals:
    resumeRequested (str): Emitted with project path when "Resume" is clicked.
    openOutputRequested (str): Emitted with project path when "Buka Output" is clicked.
"""
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("mapfree.project_history")

_HISTORY_FILE = Path.home() / ".mapfree" / "recent_projects.json"
_MAX_HISTORY = 10

_STATUS_COLORS = {
    "completed":   "#2d8a4e",
    "in_progress": "#b87a20",
    "failed":      "#a03030",
}
_STATUS_LABELS = {
    "completed":   "Selesai",
    "in_progress": "Dalam Progress",
    "failed":      "Gagal",
}


def load_history() -> list[dict]:
    """Load project history from ``~/.mapfree/recent_projects.json``."""
    try:
        if _HISTORY_FILE.is_file():
            return json.loads(_HISTORY_FILE.read_text(encoding="utf-8")) or []
    except Exception as exc:
        logger.debug("Could not load project history: %s", exc)
    return []


def save_history(entries: list[dict]) -> None:
    """Persist project history entries to disk."""
    try:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_FILE.write_text(
            json.dumps(entries[:_MAX_HISTORY], indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Could not save project history: %s", exc)


def add_project(path: str, status: str = "in_progress") -> None:
    """Add or update a project entry in the history.

    Args:
        path: Absolute path to the project directory.
        status: ``"completed"``, ``"in_progress"``, or ``"failed"``.
    """
    path = str(Path(path).resolve())
    entries = load_history()
    # Remove existing entry for same path
    entries = [e for e in entries if e.get("path") != path]
    entries.insert(0, {
        "path": path,
        "name": Path(path).name,
        "last_opened": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "thumbnail": None,
    })
    save_history(entries[:_MAX_HISTORY])


def update_status(path: str, status: str) -> None:
    """Update the status of an existing history entry.

    Args:
        path: Absolute project path.
        status: New status string.
    """
    path = str(Path(path).resolve())
    entries = load_history()
    for e in entries:
        if e.get("path") == path:
            e["status"] = status
            break
    save_history(entries)


class _HistoryItemWidget(QWidget):
    """Custom list-item widget with name, path, status badge, and action button."""

    def __init__(self, entry: dict, parent=None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Text area
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name = self._entry.get("name", "Unknown")
        path = self._entry.get("path", "")
        status = self._entry.get("status", "unknown")
        last_opened = self._entry.get("last_opened", "")

        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold; color: #eee; font-size: 12px;")
        text_col.addWidget(name_label)

        path_label = QLabel(path)
        path_label.setStyleSheet("color: #777; font-size: 10px;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_col.addWidget(path_label)

        try:
            dt = datetime.fromisoformat(last_opened)
            date_str = dt.strftime("%d %b %Y %H:%M")
        except Exception:
            date_str = last_opened or ""

        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #555; font-size: 10px;")
        text_col.addWidget(date_label)

        layout.addLayout(text_col, stretch=1)

        # Status badge
        color = _STATUS_COLORS.get(status, "#666")
        status_label_text = _STATUS_LABELS.get(status, status.capitalize())
        badge = QLabel(status_label_text)
        badge.setStyleSheet(
            f"color: {color}; background: {color}22; border: 1px solid {color}44;"
            "  border-radius: 3px; padding: 2px 6px; font-size: 10px;"
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge)

        # Action button
        if status == "in_progress":
            btn = QPushButton("Resume")
            btn.setStyleSheet(
                "QPushButton { background: #2d6fa8; color: #fff; border: none;"
                "  border-radius: 3px; padding: 4px 10px; font-size: 11px; }"
                "QPushButton:hover { background: #3d8fc8; }"
            )
        else:
            btn = QPushButton("Buka Output")
            btn.setStyleSheet(
                "QPushButton { background: #3a3a3a; color: #ddd; border: 1px solid #555;"
                "  border-radius: 3px; padding: 4px 10px; font-size: 11px; }"
                "QPushButton:hover { background: #4a4a4a; }"
            )
        btn.setFixedWidth(90)
        btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(btn)

    def _on_action_clicked(self) -> None:
        panel = self._find_panel()
        if panel is None:
            return
        path = self._entry.get("path", "")
        if self._entry.get("status") == "in_progress":
            panel.resumeRequested.emit(path)
        else:
            panel.openOutputRequested.emit(path)

    def _find_panel(self) -> Optional["ProjectHistoryPanel"]:
        w = self.parent()
        while w is not None:
            if isinstance(w, ProjectHistoryPanel):
                return w
            w = w.parent()
        return None


class ProjectHistoryPanel(QWidget):
    """Widget displaying the 10 most recent MapFree projects.

    Signals:
        resumeRequested (str): Project path when user clicks "Resume".
        openOutputRequested (str): Project path when user clicks "Buka Output".
    """

    resumeRequested: Signal = Signal(str)
    openOutputRequested: Signal = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  Project Terakhir")
        header.setStyleSheet(
            "background: #2d2d2d; color: #aaa; font-size: 11px; padding: 6px 8px;"
        )
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: #252525; border: none; }"
            "QListWidget::item { border-bottom: 1px solid #333; }"
            "QListWidget::item:selected { background: #303030; }"
        )
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)

    def refresh(self) -> None:
        """Reload history from disk and repopulate the list."""
        self._list.clear()
        entries = load_history()
        for entry in entries:
            item = QListWidgetItem(self._list)
            widget = _HistoryItemWidget(entry, self)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _on_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        row = self._list.row(item)
        entries = load_history()
        if row >= len(entries):
            return
        entry = entries[row]
        path = entry.get("path", "")

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #2d2d2d; color: #ddd; border: 1px solid #444; }"
            "QMenu::item:selected { background: #3a3a3a; }"
        )
        remove_action = menu.addAction("Hapus dari history")
        open_action = menu.addAction("Buka di File Explorer")

        action = menu.exec(self._list.mapToGlobal(pos))
        if action == remove_action:
            entries.pop(row)
            save_history(entries)
            self.refresh()
        elif action == open_action:
            _open_in_explorer(path)


def _open_in_explorer(path: str) -> None:
    """Open *path* in the system file manager."""
    try:
        p = Path(path)
        target = str(p if p.is_dir() else p.parent)
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except Exception as exc:
        logger.warning("Could not open file explorer: %s", exc)
