"""Qt adapter for MapFreeController: wraps controller and emits Qt signals from event_bus."""

from PySide6.QtCore import QObject, Signal

from mapfree.application.controller import MapFreeController
from mapfree.core.state import PipelineState


class QtController(QObject, MapFreeController):
    """
    Wraps MapFreeController and exposes pipeline events as Qt signals.
    Subscribes to context.event_bus when the controller attaches (per run).
    Adapter only: no business logic.
    """

    progressChanged = Signal(int)       # 0–100
    stateChanged = Signal(str)          # idle, running, sparse, dense, finished, error
    logReceived = Signal(str)           # single log line
    pipelineFinished = Signal()
    pipelineError = Signal(str)

    def __init__(self, profile=None, engine_type="colmap"):
        QObject.__init__(self)
        MapFreeController.__init__(self, profile=profile, engine_type=engine_type)
        self._qt_handlers = []

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

        def on_engine_log(ev, data):
            if not isinstance(data, dict):
                return
            engine = data.get("engine", "")
            message = data.get("message", "")
            line = "[%s] %s" % (engine, message) if engine else message
            self.logReceived.emit(line)

        for ev, cb in [
            ("pipeline_started", on_pipeline_started),
            ("pipeline_finished", on_pipeline_finished),
            ("pipeline_error", on_pipeline_error),
            ("progress_updated", on_progress_updated),
            ("stage_started", on_stage_started),
            ("engine_log", on_engine_log),
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
