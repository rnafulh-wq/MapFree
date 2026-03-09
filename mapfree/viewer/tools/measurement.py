"""Measurement tools — distance, area, and height profile in the 3D viewer."""


class MeasurementTool:
    """Tool for measuring distances and points in the viewer."""

    def __init__(self, gl_widget=None):
        pass

    def activate(self) -> None:
        """Activate the measurement tool (e.g. enable click handling)."""
        pass

    def deactivate(self) -> None:
        """Deactivate the measurement tool."""
        pass

    def add_point(self, x: float, y: float) -> None:
        """Add a measurement point from screen coordinates (e.g. from mouse click)."""
        pass

    def clear_points(self) -> None:
        """Clear all measurement points."""
        pass

    def get_distance(self) -> float | None:
        """Return distance between first two points, or None if fewer than two points."""
        pass

    def draw(self) -> None:
        """Draw measurement lines or labels in the viewport."""
        pass


# -----------------------------------------------------------------------------
# New measurement tools (signatures only; no UI yet)
# -----------------------------------------------------------------------------


class DistanceTool:
    """Measure distance between two or more points in the 3D scene."""

    def start_select(self) -> None:
        """Begin a new distance selection (e.g. first point or reset)."""
        pass

    def update_select(self) -> None:
        """Update selection state (e.g. current point while dragging)."""
        pass

    def compute_result(self) -> None:
        """Compute and store the distance result from current selection."""
        pass


class AreaTool:
    """Measure area of a polygon region in the 3D scene."""

    def start_select(self) -> None:
        """Begin a new area selection (e.g. first point or reset)."""
        pass

    def update_select(self) -> None:
        """Update selection state (e.g. current polygon vertices)."""
        pass

    def compute_result(self) -> None:
        """Compute and store the area result from current selection."""
        pass


class HeightProfileTool:
    """Measure height profile along a path in the 3D scene."""

    def start_select(self) -> None:
        """Begin a new height profile selection (e.g. start of path)."""
        pass

    def update_select(self) -> None:
        """Update selection state (e.g. path points)."""
        pass

    def compute_result(self) -> None:
        """Compute and store the height profile result from current selection."""
        pass
