"""
Custom exception hierarchy for MapFree.

Usage:
    from mapfree.core.exceptions import DependencyMissingError, EngineError, PipelineError

All exceptions inherit from MapFreeError so callers can catch the base class.
"""


class MapFreeError(Exception):
    """Base exception for all MapFree errors."""
    pass


class DependencyMissingError(MapFreeError):
    """External binary dependency not found on PATH or configured location.

    Args:
        binary_name: Name of the missing binary (e.g. ``"colmap"``).
        install_hint: Short install instruction shown to the user.

    Example::

        raise DependencyMissingError("colmap", "https://colmap.github.io/install.html")
    """

    def __init__(self, binary_name: str, install_hint: str = "") -> None:
        self.binary_name = binary_name
        self.install_hint = install_hint
        msg = f"Binary '{binary_name}' tidak ditemukan di PATH atau lokasi yang dikonfigurasi."
        if install_hint:
            msg += f" Cara install: {install_hint}"
        super().__init__(msg)


class PipelineError(MapFreeError):
    """Error raised during pipeline stage execution.

    Raised when a pipeline stage cannot proceed (e.g. missing inputs,
    internal logic failure). Does **not** cover external engine failures
    — use :class:`EngineError` for those.
    """
    pass


class ProjectValidationError(MapFreeError):
    """Project configuration or input data is invalid.

    Raised during validation before the pipeline starts (e.g. missing
    image folder, invalid output path, conflicting config values).
    """
    pass


class EngineError(MapFreeError):
    """Error from an external engine (COLMAP, OpenMVS, etc.).

    Args:
        engine_name: Short name of the engine (e.g. ``"COLMAP"``).
        message: Human-readable failure description.
        returncode: Subprocess exit code, or -1 if not applicable.

    Example::

        raise EngineError("COLMAP", "feature_extractor failed", returncode=1)
    """

    def __init__(self, engine_name: str, message: str, returncode: int = -1) -> None:
        self.engine_name = engine_name
        self.returncode = returncode
        super().__init__(f"[{engine_name}] {message} (returncode={returncode})")


__all__ = [
    "MapFreeError",
    "DependencyMissingError",
    "PipelineError",
    "ProjectValidationError",
    "EngineError",
]
