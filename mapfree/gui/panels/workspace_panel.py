"""Workspace tab — tree view of project files (Metashape-style)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt


class WorkspacePanel(QWidget):
    """Tree view of project folder (images, sparse, dense, etc.)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Size"])
        self._tree.setColumnCount(2)
        self._tree.setAlternatingRowColors(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._tree.setColumnWidth(1, 72)
        layout.addWidget(self._tree)

    def set_project_path(self, project_path: str | Path | None) -> None:
        """Populate tree with project folder structure."""
        self._tree.clear()
        if not project_path:
            return
        root = Path(project_path)
        if not root.is_dir():
            return
        root_item = QTreeWidgetItem([root.name, "—"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(root))
        self._tree.addTopLevelItem(root_item)
        for path in sorted(root.iterdir()):
            if path.name.startswith("."):
                continue
            if path.is_dir():
                size_str = "—"
                child = QTreeWidgetItem([path.name + "/", size_str])
            else:
                try:
                    size_str = _fmt_size(path.stat().st_size)
                except OSError:
                    size_str = "—"
                child = QTreeWidgetItem([path.name, size_str])
            child.setData(0, Qt.ItemDataRole.UserRole, str(path))
            root_item.addChild(child)
        root_item.setExpanded(True)


def _fmt_size(n: int) -> str:
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.1f KB" % (n / 1024)
    return "%.1f MB" % (n / (1024 * 1024))
