# Pick tool: single click -> ray_pick via controller
from typing import Any, Optional

from mapfree.gui.interaction.base_tool import BaseTool


class PickTool(BaseTool):
    def __init__(self, controller) -> None:
        super().__init__()
        self._controller = controller
        self._last_hit: Optional[dict] = None

    def on_mouse_press(self, event: dict) -> None:
        if event.get("button") != 1:
            return
        hit = self._controller.ray_pick(event.get("x", 0), event.get("y", 0))
        self._last_hit = hit

    def on_mouse_move(self, event: dict) -> None:
        pass

    def on_mouse_release(self, event: dict) -> None:
        pass

    def on_key_press(self, event: dict) -> None:
        pass

    def draw_overlay(self, context: Any) -> None:
        if not self._last_hit or not self._last_hit.get("point"):
            return
        if hasattr(context, "draw_overlay_point"):
            context.draw_overlay_point(
                self._last_hit["point"],
                self._last_hit.get("result", {}).get("value"),
            )
