"""Backward compatibility: profiles moved to mapfree.core.profiles."""
from mapfree.core.profiles import PROFILES

# MX150_PROFILE for backward compat
from mapfree.core.profiles.mx150 import MX150_PROFILE

__all__ = ["PROFILES", "MX150_PROFILE"]
