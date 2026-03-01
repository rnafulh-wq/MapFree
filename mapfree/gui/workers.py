"""Background workers for pipeline execution and export; keep GUI responsive."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from mapfree.application.export_manager import ExportManager


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
    The controller starts its own internal thread; this thread blocks until
    that thread completes, so the GUI can treat this worker as the long-running
    unit and stay responsive.
    """

    def __init__(self, controller, image_path, project_path, **kwargs):
        super().__init__()
        self._controller = controller
        self._image_path = image_path
        self._project_path = project_path
        self._kwargs = kwargs

    def run(self):
        self._controller.run_project(
            self._image_path,
            self._project_path,
            **self._kwargs,
        )
        if self._controller.worker_thread is not None:
            self._controller.worker_thread.join()
