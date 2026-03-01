"""Viewer panel — Open3D-based 3D viewer embedded in Qt via winId binding."""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QToolBar,
)
from PySide6.QtGui import QWindow, QPixmap, QAction
from PySide6.QtCore import Qt, QTimer

# Optional: reduce Open3D console noise
try:
    import open3d as o3d
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
except ImportError:
    o3d = None


def _get_o3d_window_handle(window_name: str):
    """Return native window handle (WId) for an Open3D window, or None."""
    if sys.platform == "win32":
        try:
            import win32gui
            hwnd = win32gui.FindWindowEx(0, 0, None, window_name)
            return int(hwnd) if hwnd else None
        except ImportError:
            return None
    if sys.platform.startswith("linux"):
        try:
            import subprocess
            out = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if out.returncode != 0:
                return None
            for line in out.stdout.splitlines():
                if window_name in line:
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        return int(parts[0], 16)
            return None
        except (FileNotFoundError, ValueError):
            return None
    return None


class ViewerPanel(QWidget):
    """Central viewer area: Open3D Visualizer embedded in Qt via winId."""

    _O3D_WINDOW_NAME = "MapFree_O3D_Viewer"
    _DARK_BG = [0.15, 0.15, 0.15]  # RGB 0–1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._o3d_initialized = False
        self._vis = None
        self._container = None
        self._timer = None
        self._fallback_label = None
        self._wireframe_mode = False
        self._viewer_toolbar = self._create_viewer_toolbar()
        self._layout.addWidget(self._viewer_toolbar)
        self._raster_label = QLabel(self)
        self._raster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._raster_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._raster_label.setStyleSheet("background-color: #252525;")
        self._raster_label.setScaledContents(False)
        self._raster_label.hide()
        self._raster_pixmap_path = None
        self._layout.addWidget(self._raster_label)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(400)
        self.setStyleSheet("background-color: #252525;")

    def showEvent(self, event):
        super().showEvent(event)
        if o3d is None:
            if self._fallback_label is None:
                self._show_fallback("Open3D not installed (pip install open3d).")
            return
        if not self._o3d_initialized and self.width() > 0 and self.height() > 0:
            self._init_open3d()

    def _init_open3d(self):
        """Create Open3D visualizer and embed into this widget using winId. Run once."""
        if self._o3d_initialized or o3d is None:
            return
        self._o3d_initialized = True
        w, h = max(320, self.width()), max(240, self.height())
        self._vis = o3d.visualization.Visualizer()
        # Create window off-screen to avoid a visible popup
        ok = self._vis.create_window(
            window_name=self._O3D_WINDOW_NAME,
            width=w,
            height=h,
            left=-10000,
            top=-10000,
            visible=True,
        )
        if not ok:
            self._show_fallback("Open3D window creation failed.")
            return
        # Dark background
        opt = self._vis.get_render_option()
        opt.background_color = self._DARK_BG
        hwnd = _get_o3d_window_handle(self._O3D_WINDOW_NAME)
        if hwnd is not None:
            o3d_window = QWindow.fromWinId(hwnd)
            self._container = QWidget.createWindowContainer(o3d_window, self)
            self._container.setStyleSheet("background-color: #252525;")
            self._layout.addWidget(self._container)
            self._raster_label.lower()
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._render_loop)
            self._timer.start(16)
            self._viewer_toolbar.setEnabled(True)
        else:
            self._vis.destroy_window()
            self._vis = None
            self._show_fallback(
                "Open3D embed requires Windows (pywin32) or Linux (wmctrl)."
            )

    def _create_viewer_toolbar(self) -> QToolBar:
        """Toolbar: Toggle Points/Mesh, Reset Camera, Top View, Side View, Wireframe."""
        bar = QToolBar(self)
        bar.setObjectName("ViewerToolbar")
        bar.setStyleSheet("""
            QToolBar { background-color: #2d2d2d; border: none; padding: 4px; spacing: 4px; }
            QToolButton { color: #e0e0e0; padding: 6px 10px; }
            QToolButton:hover { background-color: #404040; }
            QToolButton:checked { background-color: #3d6fa8; }
        """)
        a_toggle = QAction("Points / Mesh", self)
        a_toggle.setToolTip("Toggle between points and mesh (solid) display")
        a_toggle.triggered.connect(self._on_toggle_points_mesh)
        bar.addAction(a_toggle)
        bar.addSeparator()
        a_reset = QAction("Reset Camera", self)
        a_reset.setToolTip("Reset camera to default view")
        a_reset.triggered.connect(self._on_reset_camera)
        bar.addAction(a_reset)
        a_top = QAction("Top View", self)
        a_top.setToolTip("View from top (XY plane)")
        a_top.triggered.connect(self._on_top_view)
        bar.addAction(a_top)
        a_side = QAction("Side View", self)
        a_side.setToolTip("View from side (XZ plane)")
        a_side.triggered.connect(self._on_side_view)
        bar.addAction(a_side)
        bar.addSeparator()
        a_wire = QAction("Wireframe", self)
        a_wire.setToolTip("Toggle wireframe mode for meshes")
        a_wire.setCheckable(True)
        a_wire.triggered.connect(self._on_wireframe)
        bar.addAction(a_wire)
        self._action_wireframe = a_wire
        bar.setEnabled(False)  # enabled when _vis is active
        return bar

    def _on_toggle_points_mesh(self):
        """Toggle wireframe (points-like edges vs solid mesh)."""
        if self._vis is None:
            return
        try:
            opt = self._vis.get_render_option()
            self._wireframe_mode = not getattr(opt, "mesh_show_wireframe", False)
            opt.mesh_show_wireframe = self._wireframe_mode
            if self._action_wireframe is not None:
                self._action_wireframe.setChecked(self._wireframe_mode)
            self._vis.update_renderer()
        except Exception:
            pass

    def _on_reset_camera(self):
        """Reset camera to fit geometry."""
        if self._vis is None or o3d is None:
            return
        try:
            vc = self._vis.get_view_control()
            vc.set_front([0.25, -0.5, -0.8])
            vc.set_lookat([0, 0, 0])
            vc.set_up([0, 1, 0])
            vc.set_zoom(1.0)
            self._vis.update_renderer()
        except Exception:
            pass

    def _on_top_view(self):
        """Set camera to top view (looking down -Z)."""
        if self._vis is None or o3d is None:
            return
        try:
            vc = self._vis.get_view_control()
            vc.set_front([0, 0, -1])
            vc.set_lookat([0, 0, 0])
            vc.set_up([0, 1, 0])
            self._vis.update_renderer()
        except Exception:
            pass

    def _on_side_view(self):
        """Set camera to side view (looking along Y)."""
        if self._vis is None or o3d is None:
            return
        try:
            vc = self._vis.get_view_control()
            vc.set_front([0, -1, 0])
            vc.set_lookat([0, 0, 0])
            vc.set_up([0, 0, 1])
            self._vis.update_renderer()
        except Exception:
            pass

    def _on_wireframe(self, checked: bool):
        """Toggle wireframe mode from checkable action."""
        if self._vis is None:
            return
        try:
            self._wireframe_mode = bool(checked)
            opt = self._vis.get_render_option()
            opt.mesh_show_wireframe = self._wireframe_mode
            self._vis.update_renderer()
        except Exception:
            pass

    def _show_fallback(self, message: str):
        """Show a placeholder when embedding is not available."""
        if self._fallback_label is not None:
            return
        self._fallback_label = QLabel(message + "\n\n(Viewer)")
        self._fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fallback_label.setStyleSheet("""
            QLabel {
                color: #6a6a6a;
                font-size: 13px;
                background-color: #252525;
                border: 1px dashed #3d3d3d;
                border-radius: 8px;
            }
        """)
        self._fallback_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._layout.addWidget(self._fallback_label)
        self._viewer_toolbar.setEnabled(False)

    def _render_loop(self):
        """Timer callback: poll events and update renderer so embedded window stays responsive."""
        if self._vis is not None:
            try:
                self._vis.poll_events()
                self._vis.update_renderer()
            except Exception:
                pass

    def get_visualizer(self):
        """Return the Open3D Visualizer instance, or None if not initialized or unavailable."""
        return self._vis

    def _show_raster_label(self, file_path: str) -> bool:
        """Display image in QLabel fallback. Returns True on success."""
        path = Path(file_path)
        if not path.exists():
            return False
        pix = QPixmap(str(path))
        if pix.isNull():
            return False
        self._raster_pixmap_path = str(path)
        self._update_raster_pixmap()
        self._raster_label.show()
        if self._container is not None:
            self._container.hide()
        if self._fallback_label is not None:
            self._fallback_label.hide()
        self._viewer_toolbar.setEnabled(False)
        return True

    def _update_raster_pixmap(self):
        """Scale and set pixmap on _raster_label from _raster_pixmap_path."""
        if not self._raster_pixmap_path:
            return
        pix = QPixmap(self._raster_pixmap_path)
        if pix.isNull():
            return
        sz = self._raster_label.size()
        if sz.width() > 0 and sz.height() > 0:
            self._raster_label.setPixmap(
                pix.scaled(
                    sz,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _hide_raster_label(self):
        """Switch back from raster QLabel to 3D or fallback."""
        self._raster_pixmap_path = None
        self._raster_label.hide()
        if self._container is not None:
            self._container.show()
        if self._fallback_label is not None:
            self._fallback_label.show()
        self._viewer_toolbar.setEnabled(self._vis is not None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._raster_pixmap_path and self._raster_label.isVisible():
            self._update_raster_pixmap()

    def _make_textured_quad(self, image_path: str):
        """Create an Open3D TriangleMesh quad with image as texture. Returns mesh or None."""
        if o3d is None:
            return None
        path = Path(image_path)
        if not path.exists():
            return None
        try:
            ext = path.suffix.lower()
            if ext in (".png", ".jpg", ".jpeg"):
                tex_img = o3d.io.read_image(str(path))
            else:
                import numpy as np
                try:
                    from PIL import Image
                    img = Image.open(str(path))
                    if img.mode not in ("RGB", "RGBA"):
                        img = img.convert("RGB")
                    arr = np.asarray(img)
                    if len(arr.shape) == 2:
                        arr = np.stack([arr, arr, arr], axis=-1)
                    tex_img = o3d.geometry.Image(arr)
                except ImportError:
                    import cv2
                    arr = cv2.imread(str(path))
                    if arr is None:
                        return None
                    arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
                    tex_img = o3d.geometry.Image(arr)
            if tex_img is None:
                return None
        except Exception:
            return None
        verts = [
            [-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0],
        ]
        tris = [[0, 1, 2], [0, 2, 3]]
        uvs = [
            [0, 0], [1, 0], [1, 1],
            [0, 0], [1, 1], [0, 1],
        ]
        mesh = o3d.geometry.TriangleMesh()
        mesh.vertices = o3d.utility.Vector3dVector(verts)
        mesh.triangles = o3d.utility.Vector3iVector(tris)
        mesh.triangle_uvs = o3d.utility.Vector2dVector(uvs)
        mesh.textures = [tex_img]
        mesh.compute_vertex_normals()
        return mesh

    def load_raster(self, file_path: str) -> bool:
        """Load a raster image (e.g. orthophoto) as textured quad in Open3D or QPixmap in QLabel."""
        file_path = str(file_path).strip()
        if not file_path or not Path(file_path).exists():
            return False
        if self._vis is not None and o3d is not None:
            quad = self._make_textured_quad(file_path)
            if quad is not None:
                self._hide_raster_label()
                self._vis.clear_geometries()
                self._vis.add_geometry(quad)
                self._vis.update_renderer()
                return True
        return self._show_raster_label(file_path)

    def load_point_cloud(self, file_path: str) -> bool:
        """Load a point cloud (.ply) and display it. Returns True on success."""
        self._hide_raster_label()
        if self._vis is None or o3d is None:
            return False
        file_path = str(file_path).strip()
        if file_path.endswith(".ply"):
            geometry = o3d.io.read_point_cloud(file_path)
        else:
            return False
        self._vis.clear_geometries()
        self._vis.add_geometry(geometry)
        self._vis.update_renderer()
        return True

    def load_mesh(self, file_path: str) -> bool:
        """Load a mesh (.obj) and display it. Returns True on success."""
        self._hide_raster_label()
        if self._vis is None or o3d is None:
            return False
        file_path = str(file_path).strip()
        if file_path.endswith(".obj"):
            geometry = o3d.io.read_triangle_mesh(file_path)
        else:
            return False
        self._vis.clear_geometries()
        self._vis.add_geometry(geometry)
        self._vis.update_renderer()
        return True

    def clear_scene(self) -> None:
        """Remove all geometries from the viewer and hide raster image."""
        self._raster_label.hide()
        if self._container is not None:
            self._container.show()
        if self._fallback_label is not None:
            self._fallback_label.show()
        self._viewer_toolbar.setEnabled(self._vis is not None)
        if self._vis is not None:
            self._vis.clear_geometries()
            self._vis.update_renderer()
