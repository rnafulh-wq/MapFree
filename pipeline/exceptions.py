"""MapFree pipeline exceptions."""


class MapFreeError(Exception):
    """Base exception for MapFree."""


class ConfigError(MapFreeError):
    """Invalid or missing configuration."""


class ProjectError(MapFreeError):
    """Project setup or path error."""


class ValidationError(MapFreeError):
    """Input validation failed (e.g. no images, bad paths)."""


class ColmapError(MapFreeError):
    """COLMAP command failed."""
