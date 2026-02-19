from mapfree.core.context import ProjectContext
from mapfree.core.engine import create_engine
from mapfree.core.pipeline import Pipeline


class MapFreeController:

    def __init__(self, profile=None, engine_type="colmap"):
        self.profile = profile
        self.engine_type = engine_type

    def run_project(self, image_path, project_path, on_event=None, chunk_size=None, force_profile=None, event_emitter=None, quality=None):
        profile = self.profile if self.profile is not None else {}
        ctx = ProjectContext(project_path, image_path, profile)
        engine = create_engine(self.engine_type)
        pipeline = Pipeline(
            engine, ctx, on_event,
            chunk_size=chunk_size,
            force_profile=force_profile,
            event_emitter=event_emitter,
            quality=quality,
        )
        pipeline.run()
