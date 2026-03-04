"""Background workers for pipeline execution and export; keep GUI responsive."""

import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from mapfree.application.export_manager import ExportManager

# Default memory warning threshold (MB). Warn user when process RSS exceeds this.
MEMORY_WARN_THRESHOLD_MB = 2048  # 2 GB
MEMORY_CHECK_INTERVAL_SEC = 10.0


class ExportWorker(QThread):
    """
    Runs ExportManager in a background thread so the UI does not block.
    Emits exportSuccess with result (Path or dict) or exportFailed with error message.
    """

    exportSuccess = Signal(object)   # Path or dict from export_all
    exportFailed = Signal(str)

    def __init__(self, project_dir: Path, export_type: str, export_path):
        super().__init__()
        self._project_dir = Path(project_dir)
        self._export_type = export_type  # "dtm", "dsm", "orthophoto", "all"
        self._export_path = Path(export_path) if export_path else None

    def run(self):
        try:
            if self._export_type == "dtm":
                out = ExportManager.export_dtm(self._project_dir, self._export_path)
            elif self._export_type == "dsm":
                out = ExportManager.export_dsm(self._project_dir, self._export_path)
            elif self._export_type == "orthophoto":
                out = ExportManager.export_orthophoto(
                    self._project_dir, self._export_path
                )
            elif self._export_type == "all":
                out = ExportManager.export_all(self._project_dir, self._export_path)
            else:
                self.exportFailed.emit("Unknown export type: %s" % self._export_type)
                return
            self.exportSuccess.emit(out)
        except FileNotFoundError as e:
            self.exportFailed.emit(str(e))
        except Exception as e:
            self.exportFailed.emit("Export failed: %s" % e)


class PipelineWorker(QThread):
    """
    Runs the pipeline in a background thread by delegating to the controller.
    Emits started, then progress/error via controller's event_bus; finished when done.
    UI must never block on this worker.
    """
    started = Signal()
    error = Signal(str)
    # progress/finished come from QtController (progressChanged, pipelineFinished, pipelineError)

    def __init__(self, controller, image_path, project_path, **kwargs):
        super().__init__()
        self._controller = controller
        self._image_path = image_path
        self._project_path = project_path
        self._kwargs = kwargs

    def run(self):
        self.started.emit()
        try:
            self._controller.run_project(
                self._image_path,
                self._project_path,
                **self._kwargs,
            )
            if self._controller.worker_thread is not None:
                self._controller.worker_thread.join()
            from mapfree.core.state import PipelineState
            if self._controller.state == PipelineState.ERROR:
                self.error.emit(getattr(self._controller, "last_error", None) or "Pipeline failed.")
        except Exception as e:
            self.error.emit(str(e))


class MemoryMonitorWorker(QThread):
    """
    Background thread: monitor process RSS via psutil.
    If RSS > threshold_mb, emit memoryHigh(rss_mb, threshold_mb) once per breach.
    Main window should warn user and suggest decimating large meshes.
    """

    memoryHigh = Signal(float, float)  # (rss_mb, threshold_mb)

    def __init__(self, threshold_mb: float = MEMORY_WARN_THRESHOLD_MB, interval_sec: float = MEMORY_CHECK_INTERVAL_SEC):
        super().__init__()
        self._threshold_mb = threshold_mb
        self._interval_sec = interval_sec
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            import psutil
        except ImportError:
            return
        proc = psutil.Process()
        last_emitted = 0.0
        while not self._stopped:
            time.sleep(self._interval_sec)
            if self._stopped:
                break
            try:
                rss_bytes = proc.memory_info().rss
                rss_mb = rss_bytes / (1024 * 1024)
                if rss_mb >= self._threshold_mb:
                    # Throttle: emit at most once per 2*interval
                    now = time.monotonic()
                    if now - last_emitted >= self._interval_sec * 2:
                        self.memoryHigh.emit(rss_mb, self._threshold_mb)
                        last_emitted = now
            except Exception:
                pass


class GeometryLoadWorker(QThread):
    """
    Load PLY geometry (mesh or point cloud) in a background thread so the UI does not freeze.
    Emits progress(0-100) and loadDone(vertices, normals, colors, indices, path, is_point_cloud, num_vertices, num_indices)
    or loadFailed(path). Main thread should call viewer._upload_geometry in response to loadDone.
    """

    progress = Signal(int)  # 0-100
    loadDone = Signal(list, list, list, list, str, bool, int, int)
    loadFailed = Signal(str)

    def __init__(self, file_path: str, is_point_cloud: bool):
        super().__init__()
        self._path = str(file_path)
        self._is_point_cloud = bool(is_point_cloud)

    def run(self):
        from mapfree.viewer.gl_widget import _load_ply, _simplify_for_render

        self.progress.emit(10)
        data = _load_ply(self._path)
        self.progress.emit(40)
        if not data or not data.get("vertices"):
            self.loadFailed.emit(self._path)
            return
        vertices = data["vertices"]
        normals = data.get("normals")
        colors = data.get("colors")
        indices = data.get("indices") if not self._is_point_cloud else None
        if not colors:
            colors = [(0.7, 0.7, 0.7)] * len(vertices)
        if not normals:
            normals = [(0.0, 1.0, 0.0)] * len(vertices)
        self.progress.emit(70)
        vertices, normals, colors, indices = _simplify_for_render(vertices, normals, colors, indices)
        self.progress.emit(95)
        nv = len(vertices)
        ni = len(indices) if indices else 0
        self.loadDone.emit(vertices, normals, colors, indices, self._path, self._is_point_cloud, nv, ni)
        self.progress.emit(100)
