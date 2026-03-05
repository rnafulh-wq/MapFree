"""Settings dialog with Paths, Hardware, and Pipeline tabs.

Settings are persisted to ``~/.mapfree/config.yaml`` via
:func:`~mapfree.gui.dialogs.settings_dialog.load_settings` and
:func:`~mapfree.gui.dialogs.settings_dialog.save_settings`.

Typical usage::

    dlg = SettingsDialog(parent=main_window)
    if dlg.exec():
        dlg.apply()   # save to disk
"""
import logging

import yaml
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from pathlib import Path

log = logging.getLogger("mapfree.settings_dialog")

_CONFIG_PATH = Path.home() / ".mapfree" / "config.yaml"

_DEFAULTS: dict = {
    "paths": {
        "colmap_bin": "",
        "openmvs_bin_dir": "",
        "default_output_dir": str(Path.home() / "MapFreeProjects"),
    },
    "hardware": {
        "profile": "auto",
        "max_ram_gb": 8,
        "gpu_index": 0,
    },
    "pipeline": {
        "enable_geospatial": False,
        "auto_chunking": True,
        "max_chunk_size": 200,
    },
}


def load_settings() -> dict:
    """Load settings from ``~/.mapfree/config.yaml``.

    Returns:
        Merged dict with defaults filled in for any missing keys.
    """
    data = _deep_copy(_DEFAULTS)
    try:
        if _CONFIG_PATH.is_file():
            loaded = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
            _deep_merge(data, loaded)
    except Exception as exc:
        log.warning("Could not load settings: %s", exc)
    return data


def save_settings(settings: dict) -> None:
    """Persist *settings* to ``~/.mapfree/config.yaml``.

    Args:
        settings: Dict with the same structure as :func:`load_settings`.
    """
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(yaml.safe_dump(settings, default_flow_style=False),
                                encoding="utf-8")
    except Exception as exc:
        log.warning("Could not save settings: %s", exc)


class SettingsDialog(QDialog):
    """Application settings dialog with three tabs.

    Tabs:

    * **Paths** — COLMAP binary, OpenMVS binary dir, default output dir.
    * **Hardware** — hardware profile, max RAM, GPU selection.
    * **Pipeline** — geospatial toggle, auto-chunking, chunk size.

    Calling :meth:`apply` persists the current UI state to disk.

    Example::

        dlg = SettingsDialog(parent=main_window)
        if dlg.exec():
            dlg.apply()
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings — MapFree")
        self.setMinimumSize(560, 420)
        self.setStyleSheet(
            "QDialog { background: #2b2b2b; color: #ddd; }"
            "QLabel { color: #ddd; }"
            "QTabWidget::pane { border: 1px solid #3a3a3a; background: #252525; }"
            "QTabBar::tab { background: #2d2d2d; color: #aaa; padding: 6px 16px; }"
            "QTabBar::tab:selected { color: #fff; border-bottom: 2px solid #3d6fa8; }"
            "QLineEdit, QComboBox, QSpinBox { background: #1e1e1e; color: #ddd;"
            "  border: 1px solid #555; border-radius: 3px; padding: 4px 8px; }"
            "QCheckBox { color: #ddd; }"
            "QPushButton { background: #3a3a3a; color: #ddd; border: 1px solid #555;"
            "  border-radius: 3px; padding: 5px 12px; }"
            "QPushButton:hover { background: #4a4a4a; }"
            "QGroupBox { color: #aaa; border: 1px solid #3a3a3a; border-radius: 4px;"
            "  margin-top: 8px; padding-top: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; padding: 0 6px; }"
        )
        self._settings = load_settings()
        self._build_ui()
        self._load_into_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 12)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_paths_tab(), "Paths")
        self._tabs.addTab(self._build_hardware_tab(), "Hardware")
        self._tabs.addTab(self._build_pipeline_tab(), "Pipeline")

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _build_paths_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        # COLMAP binary
        colmap_row = QHBoxLayout()
        self._colmap_bin = QLineEdit()
        self._colmap_bin.setPlaceholderText("e.g. C:/tools/COLMAP/COLMAP.bat")
        colmap_row.addWidget(self._colmap_bin)
        colmap_browse = QPushButton("Browse…")
        colmap_browse.setFixedWidth(80)
        colmap_browse.clicked.connect(
            lambda: self._browse_file(self._colmap_bin, "COLMAP Executable", "All (*)")
        )
        colmap_row.addWidget(colmap_browse)
        form.addRow("COLMAP binary:", colmap_row)

        # OpenMVS binary dir
        mvs_row = QHBoxLayout()
        self._openmvs_dir = QLineEdit()
        self._openmvs_dir.setPlaceholderText("Directory containing DensifyPointCloud")
        mvs_row.addWidget(self._openmvs_dir)
        mvs_browse = QPushButton("Browse…")
        mvs_browse.setFixedWidth(80)
        mvs_browse.clicked.connect(
            lambda: self._browse_dir(self._openmvs_dir, "OpenMVS Binary Directory")
        )
        mvs_row.addWidget(mvs_browse)
        form.addRow("OpenMVS dir:", mvs_row)

        # Default output directory
        out_row = QHBoxLayout()
        self._output_dir = QLineEdit()
        out_row.addWidget(self._output_dir)
        out_browse = QPushButton("Browse…")
        out_browse.setFixedWidth(80)
        out_browse.clicked.connect(
            lambda: self._browse_dir(self._output_dir, "Default Output Directory")
        )
        out_row.addWidget(out_browse)
        form.addRow("Output dir:", out_row)

        return w

    def _build_hardware_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._hw_profile = QComboBox()
        for label in ["Auto-detect", "Low (≤4 GB VRAM)", "Medium (4–8 GB)", "High (>8 GB)"]:
            self._hw_profile.addItem(label)
        form.addRow("Hardware profile:", self._hw_profile)

        ram_row = QHBoxLayout()
        self._max_ram = QSlider(Qt.Orientation.Horizontal)
        self._max_ram.setRange(2, 64)
        self._max_ram.setTickInterval(2)
        self._max_ram.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._ram_label = QLabel("8 GB")
        self._ram_label.setFixedWidth(40)
        self._max_ram.valueChanged.connect(lambda v: self._ram_label.setText(f"{v} GB"))
        ram_row.addWidget(self._max_ram)
        ram_row.addWidget(self._ram_label)
        form.addRow("Max RAM:", ram_row)

        self._gpu_index = QSpinBox()
        self._gpu_index.setRange(0, 7)
        self._gpu_index.setSuffix("  (GPU index)")
        form.addRow("GPU:", self._gpu_index)

        return w

    def _build_pipeline_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        self._geospatial_cb = QCheckBox("Aktifkan geospatial stages (PDAL/GDAL)")
        form.addRow("", self._geospatial_cb)

        self._auto_chunk_cb = QCheckBox("Chunking otomatis untuk dataset besar")
        form.addRow("", self._auto_chunk_cb)

        self._chunk_size = QSpinBox()
        self._chunk_size.setRange(20, 2000)
        self._chunk_size.setSingleStep(10)
        self._chunk_size.setSuffix("  images/chunk")
        form.addRow("Max chunk size:", self._chunk_size)

        return w

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_into_ui(self) -> None:
        p = self._settings.get("paths", {})
        self._colmap_bin.setText(p.get("colmap_bin", ""))
        self._openmvs_dir.setText(p.get("openmvs_bin_dir", ""))
        self._output_dir.setText(p.get("default_output_dir", ""))

        hw = self._settings.get("hardware", {})
        profile_map = {"auto": 0, "low": 1, "medium": 2, "high": 3}
        self._hw_profile.setCurrentIndex(profile_map.get(hw.get("profile", "auto"), 0))
        self._max_ram.setValue(int(hw.get("max_ram_gb", 8)))
        self._gpu_index.setValue(int(hw.get("gpu_index", 0)))

        pl = self._settings.get("pipeline", {})
        self._geospatial_cb.setChecked(bool(pl.get("enable_geospatial", False)))
        self._auto_chunk_cb.setChecked(bool(pl.get("auto_chunking", True)))
        self._chunk_size.setValue(int(pl.get("max_chunk_size", 200)))

    def _collect_from_ui(self) -> dict:
        profile_map = {0: "auto", 1: "low", 2: "medium", 3: "high"}
        return {
            "paths": {
                "colmap_bin": self._colmap_bin.text().strip(),
                "openmvs_bin_dir": self._openmvs_dir.text().strip(),
                "default_output_dir": self._output_dir.text().strip(),
            },
            "hardware": {
                "profile": profile_map.get(self._hw_profile.currentIndex(), "auto"),
                "max_ram_gb": self._max_ram.value(),
                "gpu_index": self._gpu_index.value(),
            },
            "pipeline": {
                "enable_geospatial": self._geospatial_cb.isChecked(),
                "auto_chunking": self._auto_chunk_cb.isChecked(),
                "max_chunk_size": self._chunk_size.value(),
            },
        }

    def apply(self) -> None:
        """Collect current UI state and save to ``~/.mapfree/config.yaml``."""
        self._settings = self._collect_from_ui()
        save_settings(self._settings)

    def get_settings(self) -> dict:
        """Return current in-memory settings dict."""
        return self._collect_from_ui()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        self.apply()
        self.accept()

    def _browse_file(self, line_edit: QLineEdit, title: str, filters: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", filters)
        if path:
            line_edit.setText(path)

    def _browse_dir(self, line_edit: QLineEdit, title: str) -> None:
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            line_edit.setText(path)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _deep_copy(d: dict) -> dict:
    import copy
    return copy.deepcopy(d)


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
