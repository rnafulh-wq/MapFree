"""
Tool manager: holds active tool, forwards mouse/key events, triggers overlay draw.
Viewer delegates events here; no computation.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QKeyEvent

from mapfree.gui.interaction.base_tool import BaseTool


def _mouse_event_dict(event: QMouseEvent) -> dict:
    """Convert QMouseEvent to simple dict for tools."""
    pos = event.position() if hasattr(event, "position") else event.pos()
    return {
        "x": pos.x(),
        "y": pos.y(),
        "button": event.button(),
        "buttons": event.buttons(),
        "modifiers": event.modifiers(),
    }


def _key_event_dict(event: QKeyEvent) -> dict:
    """Convert QKeyEvent to simple dict for tools."""
    return {
        "key": event.key(),
        "text": event.text(),
        "modifiers": event.modifiers(),
    }


class ToolManager:
    """
    Manages the active interaction tool. Viewer calls handle_* and draw_overlay.
    Emits active_tool_changed for UI (cursor, status bar) when measurement mode toggles.
    """

    active_tool_changed = Signal(object)  # BaseTool | None

    def __init__(self) -> None:
        self._active_tool: Optional[BaseTool] = None
        self._navigation_tool: Optional[BaseTool] = None

    def set_active_tool(self, tool: Optional[BaseTool]) -> None:
        """Set the active tool. Call deactivate on previous, activate on new. Emit active_tool_changed."""
        if self._active_tool is not None:
            self._active_tool.deactivate()
        self._active_tool = tool
        if self._active_tool is not None:
            self._active_tool.activate()
        self.active_tool_changed.emit(self._active_tool)

    def get_active_tool(self) -> Optional[BaseTool]:
        return self._active_tool

    def set_navigation_tool(self, tool: Optional[BaseTool]) -> None:
        """Optional tool that handles navigation (orbit/pan) when no measurement tool consumes event."""
        self._navigation_tool = tool

    def handle_mouse_event(self, event_type: str, event: QMouseEvent) -> bool:
        """
        Forward mouse event to active tool. Return True if event was consumed (e.g. do not orbit).
        """
        d = _mouse_event_dict(event)
        if self._active_tool is not None:
            if event_type == "press":
                self._active_tool.on_mouse_press(d)
            elif event_type == "move":
                self._active_tool.on_mouse_move(d)
            elif event_type == "release":
                self._active_tool.on_mouse_release(d)
            return True
        if self._navigation_tool is not None:
            if event_type == "press":
                self._navigation_tool.on_mouse_press(d)
            elif event_type == "move":
                self._navigation_tool.on_mouse_move(d)
            elif event_type == "release":
                self._navigation_tool.on_mouse_release(d)
        return False

    def handle_key_event(self, event: QKeyEvent) -> bool:
        """Forward key event to active tool. Return True if consumed."""
        d = _key_event_dict(event)
        if self._active_tool is not None:
            self._active_tool.on_key_press(d)
            return True
        return False

    def draw_overlay(self, context) -> None:
        """Draw active tool overlay (lines, labels). Call after main scene render."""
        if self._active_tool is not None:
            self._active_tool.draw_overlay(context)
