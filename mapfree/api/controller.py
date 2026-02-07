from mapfree.core.context import ProjectContext
from mapfree.core.pipeline import Pipeline
from mapfree.engines.colmap_engine import ColmapEngine


class MapFreeController:

    def __init__(self, profile):
        self.profile = profile

    def run_project(self, image_path, project_path, on_event=None):
        ctx = ProjectContext(project_path, image_path, self.profile)
        ctx.prepare()

        engine = ColmapEngine()
        pipeline = Pipeline(engine, ctx, on_event)
        pipeline.run()
