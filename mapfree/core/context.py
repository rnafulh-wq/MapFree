import threading
from pathlib import Path

from .event_bus import EventBus
from .project_structure import resolve_project_paths


# Canonical project output layout (each stage writes only into its folder):
#   project_output/
#     sparse/          <- sparse stage (e.g. sparse/0/ for COLMAP)
#     dense/           <- dense stage (fused.ply, etc.)
#     geospatial/      <- geospatial stage (dsm.tif, dtm.tif, orthophoto.tif)
#       dsm.tif
#       dtm.tif
#       orthophoto.tif


class ProjectContext:
    """Single source of truth for a pipeline run: paths, profile, event_bus, progress, state."""

    def __init__(self, project_path, image_path, profile):
        paths = resolve_project_paths(Path(project_path))
        self.project_path = Path(paths.root)
        self.image_path = Path(image_path)
        self.profile = profile

        self.database_path = self.project_path / "database.db"
        self.sparse_path = Path(paths.sparse)
        self.dense_path = Path(paths.dense)
        self.geospatial_path = Path(paths.geospatial)
        self.mesh_path = Path(paths.mesh)
        self.logs_path = Path(paths.logs)
        self.exports_path = Path(paths.exports)
        self.images_path = Path(paths.images)

        self.event_bus = EventBus()
        self.progress = 0.0
        self.state = "idle"
        self.stop_event = threading.Event()

    def prepare(self):
        """Create project directories so each stage writes into its folder."""
        self.project_path.mkdir(parents=True, exist_ok=True)
        for p in (
            self.sparse_path,
            self.dense_path,
            self.geospatial_path,
            getattr(self, "mesh_path", None),
            getattr(self, "logs_path", None),
            getattr(self, "exports_path", None),
            getattr(self, "images_path", None),
        ):
            if p is not None:
                Path(p).mkdir(parents=True, exist_ok=True)
