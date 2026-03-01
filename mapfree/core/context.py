import threading
from pathlib import Path

from .event_bus import EventBus


class ProjectContext:
    """Single source of truth for a pipeline run: paths, profile, event_bus, progress, state."""

    def __init__(self, project_path, image_path, profile):
        self.project_path = Path(project_path)
        self.image_path = Path(image_path)
        self.profile = profile

        self.database_path = self.project_path / "database.db"
        self.sparse_path = self.project_path / "sparse"
        self.dense_path = self.project_path / "dense"
        self.geospatial_path = self.project_path / "geospatial"

        self.event_bus = EventBus()
        self.progress = 0.0
        self.state = "idle"
        self.stop_event = threading.Event()

    def prepare(self):
        """Create project_output structure: sparse/, dense/, geospatial/ (dtm.tif, dtm_epsg.tif, dsm.tif, dsm_epsg.tif, orthophoto.tif, orthophoto_epsg.tif)."""
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.sparse_path.mkdir(parents=True, exist_ok=True)
        self.dense_path.mkdir(parents=True, exist_ok=True)
        self.geospatial_path.mkdir(parents=True, exist_ok=True)
