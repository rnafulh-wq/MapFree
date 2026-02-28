import logging
import threading
from collections import deque

from mapfree.core.context import ProjectContext
from mapfree.core.engine import create_engine
from mapfree.core.pipeline import Pipeline
from mapfree.core.state import PipelineState

logger = logging.getLogger(__name__)

LOG_BUFFER_MAX = 200


class MapFreeController:
    """
    Starts the pipeline in a worker thread and updates state only from context.event_bus events.
    Does not control the engine directly; only runs the thread and listens.
    """

    def __init__(self, profile=None, engine_type="colmap"):
        self.profile = profile
        self.engine_type = engine_type
        self.worker_thread = None
        self.state = PipelineState.IDLE
        self.progress = 0.0
        self.logs = deque(maxlen=LOG_BUFFER_MAX)
        self._lock = threading.Lock()
        self._event_handlers = []
        self._current_bus = None

    def _attach_context(self, ctx):
        """Subscribe to context.event_bus; update controller and context from events only (no direct engine access)."""
        bus = getattr(ctx, "event_bus", None)
        if bus is None:
            return
        self._current_bus = bus

        def on_pipeline_started(_, data):
            with self._lock:
                self.state = PipelineState.RUNNING
                self.progress = 0.0
            ctx.state = PipelineState.RUNNING
            ctx.progress = 0.0

        def on_pipeline_finished(_, data):
            with self._lock:
                self.state = PipelineState.FINISHED
                self.progress = 1.0
            ctx.state = PipelineState.FINISHED
            ctx.progress = 1.0

        def on_pipeline_error(_, data):
            with self._lock:
                self.state = PipelineState.ERROR
            ctx.state = PipelineState.ERROR

        def on_progress_updated(_, data):
            pct = data if isinstance(data, (int, float)) else 0
            val = (pct / 100.0) if pct > 1 else float(pct)
            with self._lock:
                self.progress = val
            ctx.progress = val

        def on_stage_started(_, data):
            stage = data.get("stage") if isinstance(data, dict) else data
            if stage == "sparse":
                ctx.state = PipelineState.SPARSE
            elif stage == "dense":
                ctx.state = PipelineState.DENSE

        def on_engine_log(_, data):
            if not isinstance(data, dict):
                return
            with self._lock:
                self.logs.append({"engine": data.get("engine", ""), "message": data.get("message", "")})

        for ev, cb in [
            ("pipeline_started", on_pipeline_started),
            ("pipeline_finished", on_pipeline_finished),
            ("pipeline_error", on_pipeline_error),
            ("progress_updated", on_progress_updated),
            ("stage_started", on_stage_started),
            ("engine_log", on_engine_log),
        ]:
            bus.subscribe(ev, cb)
            self._event_handlers.append((bus, ev, cb))

    def _detach_context(self):
        """Unsubscribe all handlers registered by _attach_context."""
        for bus, ev, cb in self._event_handlers:
            try:
                bus.unsubscribe(ev, cb)
            except Exception:
                pass
        self._event_handlers.clear()
        self._current_bus = None

    def _run_worker(
        self,
        image_path,
        project_path,
        on_event=None,
        chunk_size=None,
        force_profile=None,
        event_emitter=None,
        quality=None,
    ):
        try:
            profile = self.profile if self.profile is not None else {}
            ctx = ProjectContext(project_path, image_path, profile)
            self._attach_context(ctx)
            engine = create_engine(self.engine_type)
            pipeline = Pipeline(
                engine,
                ctx,
                on_event,
                chunk_size=chunk_size,
                force_profile=force_profile,
                event_emitter=event_emitter,
                quality=quality,
            )
            pipeline.run()
        except Exception as e:
            with self._lock:
                self.state = PipelineState.ERROR
            logger.exception("Pipeline failed: %s", e)
        finally:
            self._detach_context()

    def get_logs(self):
        """Return a copy of the last up to 200 engine log entries (each {'engine': str, 'message': str})."""
        with self._lock:
            return list(self.logs)

    def stop_project(self):
        """Emit pipeline_stop_requested so pipeline terminates subprocess; then set state to IDLE."""
        bus = getattr(self, "_current_bus", None)
        if bus is not None:
            bus.emit("pipeline_stop_requested", None)
        with self._lock:
            self.state = PipelineState.IDLE

    def run_project(self, image_path, project_path, on_event=None, chunk_size=None, force_profile=None, event_emitter=None, quality=None):
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return
        self.worker_thread = threading.Thread(
            target=self._run_worker,
            kwargs={
                "image_path": image_path,
                "project_path": project_path,
                "on_event": on_event,
                "chunk_size": chunk_size,
                "force_profile": force_profile,
                "event_emitter": event_emitter,
                "quality": quality,
            },
            daemon=True,
        )
        self.worker_thread.start()
