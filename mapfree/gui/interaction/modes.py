"""
Interaction modes (enum-like). Switchable via ToolManager.
"""
from enum import Enum


class InteractionMode(Enum):
    """CAD-like interaction modes for the viewer."""

    NAVIGATION = "navigation"
    DISTANCE = "distance"
    AREA = "area"
    PROFILE = "profile"
    PICK = "pick"
