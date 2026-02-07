class Pipeline:

    def __init__(self, engine, context, on_event=None):
        self.engine = engine
        self.ctx = context
        self.on_event = on_event or (lambda e: None)

    def emit(self, type_, message=None, progress=None):
        from .events import Event
        self.on_event(Event(type_, message, progress))

    def run(self):
        self.emit("start", "Pipeline started", 0.0)

        try:
            self.emit("step", "Feature Extraction", 0.2)
            self.engine.feature_extraction(self.ctx)

            self.emit("step", "Matching", 0.4)
            self.engine.matching(self.ctx)

            self.emit("step", "Sparse Reconstruction", 0.6)
            self.engine.sparse(self.ctx)

            self.emit("step", "Dense Reconstruction", 0.8)
            self.engine.dense(self.ctx)

            self.emit("complete", "Pipeline finished", 1.0)

        except Exception as e:
            self.emit("error", str(e))
            raise
