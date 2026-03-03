"""
Profile tool: draw polyline, finalize (Enter) -> controller.extract_profile(line_points).
Store profile dataset; minimal 2D overlay preview. No computation in tool.
"""
from typing import TYPE_CHECKING, Any, List, Optional

from mapfree.gui.interaction.base_tool import BaseTool

if TYPE_CHECKING:
    from mapfree.gui.controllers.measurement_controller import MeasurementController

QT_KEY_RETURN = 0x01000004
QT_KEY_ENTER = 0x01000005

# Default sampling for profile
DEFAULT_SAMPLING_DISTANCE = 0.5


class ProfileTool(BaseTool):
    """Polyline by clicks; Enter finalizes and calls extract_profile; minimal 2D preview overlay."""

    def __init__(self, controller: "MeasurementController") -> None:
        super().__init__()
        self._controller = controller
        self._points: List[List[float]] = []
        self._profile_data: Optional[dict] = None  # engine result: distances, elevations, points

    def on_mouse_press(self, event: dict) -> None:
        if event.get("button") != 1:
            return
        x, y = event.get("x", 0), event.get("y", 0)
        hit = self._controller.ray_pick(x, y)
        if hit is None:
            return
        self._points.append(hit["point"])

    def on_mouse_move(self, event: dict) -> None:
        pass

    def on_mouse_release(self, event: dict) -> None:
        pass

    def on_key_press(self, event: dict) -> None:
        key = event.get("key")
        if key in (QT_KEY_RETURN, QT_KEY_ENTER) and len(self._points) >= 2:
            self._profile_data = self._controller.extract_profile(
                self._points, DEFAULT_SAMPLING_DISTANCE
            )
            # Keep points for overlay; profile_data has the sampled result

    def draw_overlay(self, context: Any) -> None:
        pts = self._points
        if len(pts) < 2:
            return
        if hasattr(context, "draw_overlay_line_segments"):
            segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
            context.draw_overlay_line_segments(segs, (0.9, 0.5, 0.2))
        # Minimal 2D preview: if we have profile_data, draw a simple elevation strip in overlay
        if self._profile_data and hasattr(context, "draw_overlay_profile_preview"):
            context.draw_overlay_profile_preview(self._profile_data)
