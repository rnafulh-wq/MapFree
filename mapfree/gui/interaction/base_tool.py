"""
Abstract base tool. No computation; only event and overlay hooks.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseTool(ABC):
    """
    Base class for interaction tools. Subclasses implement event handlers and overlay.
    No geometry computation here; delegate to controller/engine.
    """

    def on_mouse_press(self, event: dict) -> None:
        """Called when mouse button is pressed. event: {x, y, button, modifiers}."""
        pass

    def on_mouse_move(self, event: dict) -> None:
        """Called when mouse moves. event: {x, y, button, modifiers}."""
        pass

    def on_mouse_release(self, event: dict) -> None:
        """Called when mouse button is released. event: {x, y, button, modifiers}."""
        pass

    def on_key_press(self, event: dict) -> None:
        """Called when key is pressed. event: {key, modifiers}."""
        pass

    def draw_overlay(self, context: Any) -> None:
        """
        Draw tool overlay (lines, points, text). Called after main scene render.
        context: object with GL access and camera (e.g. viewer widget).
        No heavy shaders; simple GL line/point drawing.
        """
        pass

    def activate(self) -> None:
        """Called when tool becomes active."""
        pass

    def deactivate(self) -> None:
        """Called when tool is deactivated."""
        pass
