"""
Measurement controller: bridge UI (viewer/tools) <-> MeasurementEngine.
Converts screen coords to ray, calls engine.ray_pick/measure_*, stores session, emits results.
No heavy computation; all measurement logic stays in engine.
"""
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from PySide6.QtCore import QObject, Signal

from mapfree.engines.inspection.measurement_engine import MeasurementEngine
from mapfree.engines.inspection.session import MeasurementSession
from mapfree.engines.inspection.models import MeasurementResult

logger = logging.getLogger(__name__)


def _result_to_dict(r: MeasurementResult) -> dict:
    """Convert MeasurementResult to session-storable dict."""
    return {
        "value": r.value,
        "unit": r.unit,
        "precision": r.precision,
        "crs": r.crs,
        "method": r.method,
    }


class MeasurementController(QObject):
    """
    Holds MeasurementEngine and MeasurementSession. Provides:
    - Ray from screen (via viewer callback)
    - ray_pick, measure_distance, measure_area_polygon_3d, extract_profile
    - Session save/load
    Emits resultAdded for UI updates.
    """

    resultAdded = Signal(dict)  # measurement result dict (e.g. for overlay/list)

    def __init__(
        self,
        engine: MeasurementEngine,
        get_ray_from_screen: Optional[Callable[[float, float], Tuple[List[float], List[float]]]] = None,
    ) -> None:
        super().__init__()
        self._engine = engine
        self._get_ray = get_ray_from_screen
        self._session = MeasurementSession(project="", crs=engine.crs_manager.get_crs())

    @property
    def engine(self) -> MeasurementEngine:
        return self._engine

    @property
    def session(self) -> MeasurementSession:
        return self._session

    def set_ray_callback(self, get_ray_from_screen: Callable[[float, float], Tuple[List[float], List[float]]]) -> None:
        """Set the viewer callback to compute world ray from screen x, y."""
        self._get_ray = get_ray_from_screen

    def ray_pick(self, screen_x: float, screen_y: float) -> Optional[Dict[str, Any]]:
        """
        Cast ray from screen position; return hit info or None.
        Returns dict with keys: point (list [x,y,z]), distance, result (measurement dict).
        """
        if self._get_ray is None:
            logger.warning("No ray callback set for measurement controller")
            return None
        try:
            ray_origin, ray_direction = self._get_ray(screen_x, screen_y)
        except Exception as e:
            logger.debug("Ray computation failed: %s", e)
            return None
        try:
            res = self._engine.ray_pick(ray_origin, ray_direction)
        except Exception as e:
            logger.debug("ray_pick failed: %s", e)
            return None
        if res is None:
            return None
        import math
        dx, dy, dz = ray_direction[0], ray_direction[1], ray_direction[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        t = res.value / L
        hit = [
            ray_origin[0] + t * dx,
            ray_origin[1] + t * dy,
            ray_origin[2] + t * dz,
        ]
        out = {
            "point": hit,
            "distance": res.value,
            "result": _result_to_dict(res),
        }
        return out

    def measure_distance(self, p1: Union[list, tuple], p2: Union[list, tuple]) -> Optional[dict]:
        """Measure distance between two 3D points; store in session and emit."""
        try:
            res = self._engine.measure_distance(p1, p2)
        except Exception as e:
            logger.warning("measure_distance failed: %s", e)
            return None
        d = _result_to_dict(res)
        d["p1"] = list(p1)
        d["p2"] = list(p2)
        self._session.add_measurement(d)
        self.resultAdded.emit(d)
        return d

    def measure_area_polygon_3d(self, points: Union[list, List[list]]) -> Optional[dict]:
        """Measure area of 3D polygon; store in session and emit."""
        try:
            res = self._engine.measure_area_polygon_3d(points)
        except Exception as e:
            logger.warning("measure_area_polygon_3d failed: %s", e)
            return None
        d = _result_to_dict(res)
        d["points"] = [list(p) for p in points]
        self._session.add_measurement(d)
        self.resultAdded.emit(d)
        return d

    def extract_profile(
        self,
        line_points: Union[list, List[list]],
        sampling_distance: float = 0.5,
    ) -> Optional[Dict[str, Any]]:
        """Extract profile along polyline; store in session and emit. Returns profile dict from engine."""
        try:
            profile = self._engine.extract_profile(line_points, sampling_distance)
        except Exception as e:
            logger.warning("extract_profile failed: %s", e)
            return None
        # Store minimal summary in session; full profile in returned dict
        summary = {
            "method": "extract_profile",
            "value": profile.get("value"),
            "unit": profile.get("unit", ""),
            "points_count": len(line_points),
            "sampling_distance": sampling_distance,
        }
        self._session.add_measurement(summary)
        self.resultAdded.emit(summary)
        return profile

    def save_measurements(self, path: Union[str, Path]) -> None:
        """Persist current session to JSON file. No UI dialog."""
        path = Path(path)
        self._session.set_metadata(crs=self._engine.crs_manager.get_crs())
        self._session.export_json(path)
        logger.info("Saved %d measurements to %s", len(self._session.measurements), path)

    def load_measurements(self, path: Union[str, Path]) -> None:
        """Load session from JSON; replace current session. No UI dialog."""
        path = Path(path)
        self._session = MeasurementSession.load_json(path)
        logger.info("Loaded %d measurements from %s", len(self._session.measurements), path)

    def set_geometry_from_file(self, path: Union[str, Path]) -> bool:
        """Load PLY and set engine mesh or point cloud. Call when viewer loads a PLY."""
        try:
            from mapfree.viewer.geometry_loader import load_ply
            data = load_ply(str(path))
            if not data:
                return False
            positions = data["positions"]
            indices = data.get("indices")
            if indices is not None and len(indices) >= 3:
                nf = len(indices) // 3
                faces = np.array(indices, dtype=np.intp).reshape(nf, 3)
                self._engine.set_mesh(positions, faces)
            else:
                self._engine.set_point_cloud(positions)
            return True
        except Exception as e:
            logger.warning("set_geometry_from_file failed: %s", e)
            return False
