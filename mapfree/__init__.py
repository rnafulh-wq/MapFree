"""MapFree — modular photogrammetry pipeline engine."""

__version__ = "0.1.0"

from mapfree.application.controller import MapFreeController
from mapfree.core.events import Event, EventEmitter
from mapfree.core.pipeline import Pipeline
from mapfree.core.context import ProjectContext
from mapfree.core.engine import create_engine

__all__ = [
    "__version__",
    "MapFreeController",
    "Event",
    "EventEmitter",
    "Pipeline",
    "ProjectContext",
    "create_engine",
]
