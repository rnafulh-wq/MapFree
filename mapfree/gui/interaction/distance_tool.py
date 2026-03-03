"""Distance tool: two clicks -> measure_distance; overlay line + label."""
from typing import Any, List, Optional

from mapfree.gui.interaction.base_tool import BaseTool


class DistanceTool(BaseTool):
    def __init__(self, controller) -> None:
        super().__init__()
        self._controller = controller
        self._points: List[List[float]] = []
        self._last_result: Optional[dict] = None

    def on_mouse_press(self, event: dict) -> None:
        if event.get("button") != 1:
            return
        hit = self._controller.ray_pick(event.get("x", 0), event.get("y", 0))
        if not hit:
            return
        self._points.append(hit["point"])
        if len(self._points) == 2:
            self._last_result = self._controller.measure_distance(
                self._points[0], self._points[1]
            )
            self._points = []

    def on_mouse_move(self, event: dict) -> None:
        pass

    def on_mouse_release(self, event: dict) -> None:
        pass

    def on_key_press(self, event: dict) -> None:
        pass

    def draw_overlay(self, context: Any) -> None:
        if self._points:
            if hasattr(context, "draw_overlay_line_segments"):
                p = self._points[0]
                context.draw_overlay_line_segments([(p, p)], (1.0, 0.8, 0.0))
            return
        if not self._last_result:
            return
        p1 = self._last_result.get("p1")
        p2 = self._last_result.get("p2")
        if p1 and p2 and hasattr(context, "draw_overlay_line_segments"):
            context.draw_overlay_line_segments([(p1, p2)], (0.2, 0.9, 0.3))
        if p1 and p2 and hasattr(context, "draw_overlay_label"):
            mid = [
                (p1[0] + p2[0]) / 2,
                (p1[1] + p2[1]) / 2,
                (p1[2] + p2[2]) / 2,
            ]
            v = self._last_result.get("value")
            u = self._last_result.get("unit", "")
            context.draw_overlay_label(mid, f"{v:.3f} {u}")
