"""
Standalone 3D viewer window — run in a separate process so a segfault does not close MapFree.
Usage: python -m mapfree.viewer.standalone [project_path]
"""
import os
import sys

# Force software OpenGL before any Qt/GL load
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QMessageBox
from PySide6.QtCore import Qt

from mapfree.viewer.gl_widget import ViewerWidget, set_default_opengl_format


def _best_result_path(project_path: Path):
    """Return (path_str, is_mesh) for best PLY to load, or (None, False)."""
    proj = Path(project_path)
    openmvs = proj / "openmvs"
    for name in ("scene_mesh_refine.ply", "scene_mesh.ply"):
        p = openmvs / name
        if p.exists() and p.stat().st_size > 0:
            return str(p), True
    fused = proj / "dense" / "fused.ply"
    if fused.exists() and fused.stat().st_size >= 1024:
        return str(fused), False
    final = proj / "final_results"
    for name in ("dense.ply", "sparse.ply"):
        p = final / name
        if p.exists():
            if name == "dense.ply" and p.stat().st_size < 1024:
                continue
            return str(p), False  # both are point clouds
    return None, False


def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    app = QApplication(sys.argv)
    app.setApplicationName("MapFree 3D Viewer")
    set_default_opengl_format()
    viewer = ViewerWidget()
    window = QMainWindow()
    window.setWindowTitle("MapFree 3D Viewer")
    window.setCentralWidget(viewer)
    window.resize(900, 700)

    # Load project result if path given
    if project_path:
        path, is_mesh = _best_result_path(Path(project_path))
        if path:
            if is_mesh:
                viewer.load_mesh(path)
            else:
                viewer.load_point_cloud(path)
            viewer.zoom_fit()

    # Toolbar: Load / Open project folder
    toolbar = window.addToolBar("File")
    def on_load_ply():
        path, _ = QFileDialog.getOpenFileName(window, "Load PLY", "", "PLY (*.ply);;All (*)")
        if path:
            if viewer.load_point_cloud(path) or viewer.load_mesh(path):
                viewer.zoom_fit()
    def on_open_project():
        folder = QFileDialog.getExistingDirectory(window, "Open project folder", "")
        if folder:
            path, is_mesh = _best_result_path(Path(folder))
            if path:
                if is_mesh:
                    viewer.load_mesh(path)
                else:
                    viewer.load_point_cloud(path)
                viewer.zoom_fit()
            else:
                QMessageBox.information(window, "3D Viewer", "No PLY found in this project.")
    toolbar.addAction("Load PLY…", on_load_ply)
    toolbar.addAction("Open project folder…", on_open_project)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
