# Area tool: multiple clicks, Enter -> measure_area_polygon_3d; polygon overlay
from typing import Any, List, Optional

from mapfree.gui.interaction.base_tool import BaseTool

QT_KEY_RETURN = 0x01000004
QT_KEY_ENTER = 0x01000005


class AreaTool(BaseTool):
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

    def on_mouse_move(self, event: dict) -> None:
        pass

    def on_mouse_release(self, event: dict) -> None:
        pass

    def on_key_press(self, event: dict) -> None:
        if event.get("key") in (QT_KEY_RETURN, QT_KEY_ENTER) and len(self._points) >= 3:
            self._last_result = self._controller.measure_area_polygon_3d(self._points)
            self._points = []

    def draw_overlay(self, context: Any) -> None:
        pts = self._points or (
            self._last_result.get("points", []) if self._last_result else []
        )
        if len(pts) < 2:
            return
        if hasattr(context, "draw_overlay_polygon"):
            context.draw_overlay_polygon(pts, (0.2, 0.6, 0.9))
        if self._last_result and hasattr(context, "draw_overlay_label"):
            n = len(pts)
            cx = sum(p[0] for p in pts) / n
            cy = sum(p[1] for p in pts) / n
            cz = sum(p[2] for p in pts) / n
            v = self._last_result.get("value")
            u = self._last_result.get("unit", "")
            context.draw_overlay_label([cx, cy, cz], f"{v:.3f} {u}")
