"""Backward compatibility: config moved to mapfree.core.config."""

from mapfree.core.config import get_config, load_config, reset_config

__all__ = ["get_config", "load_config", "reset_config"]
