"""Qt adapter for MapFreeController: wraps controller and emits Qt signals from event_bus."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from mapfree.application.controller import MapFreeController
from mapfree.core.state import PipelineState
from mapfree.gui.workers import ExportWorker


class QtController(QObject, MapFreeController):
    """
    Wraps MapFreeController and exposes pipeline events as Qt signals.
    Subscribes to context.event_bus when the controller attaches (per run).
    Export methods run ExportManager in a QThread worker; emit exportStarted,
    exportFinished, exportError. Adapter only: no business logic.
    """

    progressChanged = Signal(int)       # 0–100
    stateChanged = Signal(str)          # idle, running, sparse, dense, finished, error
    logReceived = Signal(str)           # single log line
    pipelineFinished = Signal()
    pipelineError = Signal(str)

    exportStarted = Signal()
    exportFinished = Signal(object)     # Path or dict (for export_all)
    exportError = Signal(str)

    denseReady = Signal(str)            # path to fused.ply when dense stage completes (legacy)
    pointCloudLoaded = Signal(str)      # path when point cloud is loaded (e.g. dense fused.ply)
    meshLoaded = Signal(str)            # path when mesh is loaded

    def __init__(self, profile=None, engine_type="colmap"):
        QObject.__init__(self)
        MapFreeController.__init__(self, profile=profile, engine_type=engine_type)
        self._qt_handlers = []
        self._export_worker = None

    def export_dtm(self, project_dir, export_path):
        """Run ExportManager.export_dtm in a worker; emit exportStarted, then exportFinished or exportError."""
        self._start_export(Path(project_dir), "dtm", Path(export_path))

    def export_dsm(self, project_dir, export_path):
        """Run ExportManager.export_dsm in a worker; emit exportStarted, then exportFinished or exportError."""
        self._start_export(Path(project_dir), "dsm", Path(export_path))

    def export_orthophoto(self, project_dir, export_path):
        """Run ExportManager.export_orthophoto in a worker; emit exportStarted, then exportFinished or exportError."""
        self._start_export(Path(project_dir), "orthophoto", Path(export_path))

    def export_all(self, project_dir, export_dir):
        """Run ExportManager.export_all in a worker; emit exportStarted, then exportFinished or exportError."""
        self._start_export(Path(project_dir), "all", Path(export_dir))

    def _start_export(self, project_dir: Path, export_type: str, export_path: Path):
        if self._export_worker is not None and self._export_worker.isRunning():
            self.exportError.emit("Export already in progress.")
            return
        self.exportStarted.emit()
        self._export_worker = ExportWorker(project_dir, export_type, export_path)
        self._export_worker.exportSuccess.connect(self._on_export_success)
        self._export_worker.exportFailed.connect(self._on_export_failed)
        self._export_worker.finished.connect(self._on_export_worker_finished)
        self._export_worker.start()

    def _on_export_success(self, result):
        w = self._export_worker
        self._export_worker = None
        if w is not None:
            w.deleteLater()
        self.exportFinished.emit(result)

    def _on_export_failed(self, message: str):
        w = self._export_worker
        self._export_worker = None
        if w is not None:
            w.deleteLater()
        self.exportError.emit(message)

    def _on_export_worker_finished(self):
        if self._export_worker is not None and not self._export_worker.isRunning():
            self._export_worker = None

    def _subscribe_qt_adapters(self, bus):
        if bus is None:
            return

        def on_pipeline_started(ev, data):
            self.progressChanged.emit(0)
            self.stateChanged.emit(PipelineState.RUNNING.value)

        def on_pipeline_finished(ev, data):
            self.progressChanged.emit(100)
            self.stateChanged.emit(PipelineState.FINISHED.value)
            self.pipelineFinished.emit()

        def on_pipeline_error(ev, data):
            msg = data if isinstance(data, str) else str(data) if data is not None else ""
            self.stateChanged.emit(PipelineState.ERROR.value)
            self.pipelineError.emit(msg)

        def on_progress_updated(ev, data):
            pct = data if isinstance(data, (int, float)) else 0
            if isinstance(pct, float) and 0 <= pct <= 1:
                pct = int(pct * 100)
            else:
                pct = int(pct)
            self.progressChanged.emit(min(100, max(0, pct)))

        def on_stage_started(ev, data):
            stage = data.get("stage") if isinstance(data, dict) else data
            if isinstance(stage, str):
                self.stateChanged.emit(stage)

        def on_stage_completed(ev, data):
            if not isinstance(data, dict):
                return
            if data.get("stage") == "dense" and not data.get("skipped"):
                path = data.get("fused_ply")
                if path:
                    self.denseReady.emit(path)
                    self.pointCloudLoaded.emit(path)
                mesh_path = data.get("mesh_path")
                if mesh_path:
                    self.meshLoaded.emit(mesh_path)

        def on_engine_log(ev, data):
            if not isinstance(data, dict):
                return
            engine = data.get("engine", "")
            message = data.get("message", "")
            line = "[%s] %s" % (engine, message) if engine else message
            self.logReceived.emit(line)

        def on_reprojection_progress(ev, data):
            pct = data if isinstance(data, (int, float)) else 0
            if isinstance(pct, float) and 0 <= pct <= 1:
                pct = int(pct * 100)
            else:
                pct = int(pct)
            self.progressChanged.emit(min(100, max(0, pct)))

        for ev, cb in [
            ("pipeline_started", on_pipeline_started),
            ("pipeline_finished", on_pipeline_finished),
            ("pipeline_error", on_pipeline_error),
            ("progress_updated", on_progress_updated),
            ("stage_started", on_stage_started),
            ("stage_completed", on_stage_completed),
            ("engine_log", on_engine_log),
            ("reprojection_progress", on_reprojection_progress),
        ]:
            bus.subscribe(ev, cb)
            self._qt_handlers.append((bus, ev, cb))

    def _unsubscribe_qt_adapters(self):
        for bus, ev, cb in self._qt_handlers:
            try:
                bus.unsubscribe(ev, cb)
            except Exception:
                pass
        self._qt_handlers.clear()

    def _attach_context(self, ctx):
        bus = getattr(ctx, "event_bus", None)
        self._subscribe_qt_adapters(bus)
        super()._attach_context(ctx)

    def _detach_context(self):
        self._unsubscribe_qt_adapters()
        super()._detach_context()
