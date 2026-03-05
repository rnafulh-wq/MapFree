"""Matplotlib-based point cloud viewer (no OpenGL). Fallback when OpenGL is unavailable."""
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from mapfree.utils.ply_parser import parse_ply_file

logger = logging.getLogger("mapfree.viewer_matplotlib")

_MAX_POINTS_DISPLAY = 50_000


def _subsample(xyz: np.ndarray, colors: Optional[np.ndarray], max_points: int):
    """Subsample to max_points by taking every Nth point. Returns (xyz, colors, total_orig)."""
    n = len(xyz)
    if n <= max_points:
        return xyz, colors, n
    step = max(1, n // max_points)
    idx = np.arange(0, n, step, dtype=np.intp)[:max_points]
    xyz_out = xyz[idx]
    colors_out = colors[idx] if colors is not None else None
    return xyz_out, colors_out, n


class MatplotlibPointCloudViewer(QWidget):
    """Point cloud viewer using matplotlib (mplot3d). No OpenGL required."""

    pointsLoaded = Signal(int)
    loadError = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._xyz: Optional[np.ndarray] = None
        self._colors: Optional[np.ndarray] = None
        self._total_points = 0
        self._displayed_points = 0
        self._ax = None
        self._canvas = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            from mpl_toolkits.mplot3d import Axes3D
        except ImportError:
            lab = QLabel("Matplotlib not installed.\npip install matplotlib")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet("color: #6a6a6a; background: #1e1e1e;")
            layout.addWidget(lab)
            self._status_label = QLabel("No point cloud loaded")
            self._status_label.setStyleSheet("color: #888; padding: 4px;")
            layout.addWidget(self._status_label)
            return

        fig = Figure(facecolor="#1a1a1a", edgecolor="none")
        self._canvas = FigureCanvas(fig)
        self._ax = fig.add_subplot(111, projection="3d")
        self._ax.set_facecolor("#1a1a1a")
        self._ax.xaxis.pane.fill = False
        self._ax.yaxis.pane.fill = False
        self._ax.zaxis.pane.fill = False
        self._ax.xaxis.pane.set_edgecolor("#333")
        self._ax.yaxis.pane.set_edgecolor("#333")
        self._ax.zaxis.pane.set_edgecolor("#333")
        self._ax.tick_params(colors="#888")
        self._ax.xaxis.label.set_color("#888")
        self._ax.yaxis.label.set_color("#888")
        self._ax.zaxis.label.set_color("#888")
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self._canvas)

        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #2a2a2a;")
        tlay = QHBoxLayout(toolbar)
        tlay.setContentsMargins(6, 4, 6, 4)
        tlay.setSpacing(6)

        for label, (elev, azim) in [
            ("Reset View", (30, 45)),
            ("Top View", (90, 0)),
            ("Side View", (0, 90)),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(
                "QPushButton { color: #ddd; background: #3a3a3a; border: 1px solid #555; "
                "border-radius: 4px; padding: 4px 8px; }"
                "QPushButton:hover { background: #4a4a4a; }"
            )
            btn.clicked.connect(lambda checked=False, e=elev, a=azim: self._set_view(e, a))
            tlay.addWidget(btn)
        tlay.addStretch()

        self._status_label = QLabel("No point cloud loaded")
        self._status_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px 8px;")
        tlay.addWidget(self._status_label)
        layout.addWidget(toolbar)

    def _set_view(self, elev: float, azim: float) -> None:
        if self._ax is None:
            return
        self._ax.view_init(elev=elev, azim=azim)
        self._canvas.draw_idle()

    def _reset_camera(self) -> None:
        self._set_view(30, 45)

    def load_ply(self, path: str | Path) -> bool:
        path = Path(path)
        xyz, colors = parse_ply_file(path)
        if xyz is None:
            msg = f"Could not load PLY: {path.name}"
            logger.warning(msg)
            self._set_status(msg)
            self.loadError.emit(msg)
            return False

        xyz_disp, colors_disp, total = _subsample(
            xyz, colors, _MAX_POINTS_DISPLAY
        )
        self._xyz = xyz_disp
        self._colors = colors_disp
        self._total_points = total
        self._displayed_points = len(xyz_disp)

        self._update_plot()
        if total > _MAX_POINTS_DISPLAY:
            self._set_status(
                f"Showing {self._displayed_points:,} points (subsampled from {total:,})"
            )
        else:
            self._set_status(f"Showing {total:,} points")
        self.pointsLoaded.emit(total)
        logger.info("Loaded %d points from '%s' (displaying %d)", total, path, self._displayed_points)
        return True

    def _update_plot(self) -> None:
        if self._ax is None or self._canvas is None or self._xyz is None:
            return
        self._ax.cla()
        self._ax.set_facecolor("#1a1a1a")
        self._ax.tick_params(colors="#888")
        if self._colors is not None and self._colors.shape[1] >= 3:
            c = self._colors[:, :3]
            if c.max() <= 1.0:
                c = (c * 255).astype(np.uint8)
            self._ax.scatter(
                self._xyz[:, 0],
                self._xyz[:, 1],
                self._xyz[:, 2],
                c=c / 255.0,
                s=0.5,
                alpha=0.8,
            )
        else:
            self._ax.scatter(
                self._xyz[:, 0],
                self._xyz[:, 1],
                self._xyz[:, 2],
                c="#3d6fa8",
                s=0.5,
                alpha=0.8,
            )
        self._ax.set_xlabel("X")
        self._ax.set_ylabel("Y")
        self._ax.set_zlabel("Z")
        self._canvas.draw_idle()

    def _set_status(self, message: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(message)

    def clear(self) -> None:
        self._xyz = None
        self._colors = None
        self._total_points = 0
        self._displayed_points = 0
        if self._ax is not None and self._canvas is not None:
            self._ax.cla()
            self._ax.set_facecolor("#1a1a1a")
            self._canvas.draw_idle()
        self._set_status("No point cloud loaded")

    def point_count(self) -> int:
        return self._total_points if self._xyz is not None else 0

    def refresh_points(self, xyz_rgb: np.ndarray) -> None:
        """Update from Nx3 or Nx6 array (for live preview). Subsampled like load_ply."""
        if xyz_rgb.ndim != 2 or xyz_rgb.shape[1] < 3:
            return
        xyz = xyz_rgb[:, :3].astype(np.float32)
        colors = None
        if xyz_rgb.shape[1] >= 6:
            rgb = xyz_rgb[:, 3:6].astype(np.float32)
            if not np.issubdtype(xyz_rgb.dtype, np.floating):
                rgb = rgb / 255.0
            alpha = np.ones((len(xyz), 1), dtype=np.float32)
            colors = np.concatenate([rgb, alpha], axis=1)
        xyz_disp, colors_disp, total = _subsample(
            xyz, colors, _MAX_POINTS_DISPLAY
        )
        self._xyz = xyz_disp
        self._colors = colors_disp
        self._total_points = total
        self._displayed_points = len(xyz_disp)
        self._update_plot()
        self._set_status(f"Showing {self._displayed_points:,} points (subsampled from {total:,})")
