"""
Abstract engine interface. Pipeline only interacts with BaseEngine.
Use create_engine() to get a concrete implementation without knowing engine details.
"""


class VramWatchdogError(RuntimeError):
    """Raised when VRAM watchdog terminates a dense step (usage > threshold)."""
    pass


class BaseEngine:
    """Abstract interface for photogrammetry engines (COLMAP, OpenMVS, etc.)."""

    def feature_extraction(self, ctx):
        raise NotImplementedError

    def matching(self, ctx):
        raise NotImplementedError

    def sparse(self, ctx):
        raise NotImplementedError

    def dense(self, ctx, vram_watchdog=False):
        raise NotImplementedError


def create_engine(engine_type: str = "colmap") -> BaseEngine:
    """
    Factory: create engine by type name.
    Pipeline and controller should use this instead of importing engine classes directly.
    """
    if engine_type == "colmap":
        from mapfree.engines.colmap_engine import ColmapEngine
        return ColmapEngine()
    raise ValueError(f"Unknown engine type: {engine_type}")
