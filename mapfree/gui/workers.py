"""Background workers for pipeline execution; keep GUI responsive."""

from PySide6.QtCore import QThread


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
