"""
Measurement session persistence: store results and metadata, export/load JSON.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


def _serialize_for_json(obj: Any) -> Any:
    """Convert numpy types and arrays to JSON-serializable form."""
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_json(x) for x in obj]
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class MeasurementSession:
    """
    Store measurement results and metadata; export to / load from JSON.
    Structure: project, crs, timestamp, measurements (list of result dicts).
    """

    def __init__(
        self,
        project: str = "",
        crs: str = "",
    ) -> None:
        self.project: str = str(project)
        self.crs: str = str(crs).strip()
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.measurements: List[Dict[str, Any]] = []

    def add_measurement(self, result: Dict[str, Any]) -> None:
        """Append a measurement result (structured dict) to the session."""
        self.measurements.append(dict(result))

    def set_metadata(self, project: Optional[str] = None, crs: Optional[str] = None) -> None:
        """Update project and/or CRS."""
        if project is not None:
            self.project = str(project)
        if crs is not None:
            self.crs = str(crs).strip()
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Return session as a plain dict (JSON-serializable)."""
        return {
            "project": self.project,
            "crs": self.crs,
            "timestamp": self.timestamp,
            "measurements": _serialize_for_json(self.measurements),
        }

    def export_json(self, path: Union[str, Path]) -> None:
        """
        Write session to a JSON file.

        Raises:
            IOError: On write failure.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: Union[str, Path]) -> "MeasurementSession":
        """
        Load session from a JSON file.

        Returns:
            MeasurementSession with loaded data.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If JSON is invalid or missing required keys.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError("Session file not found: %s" % path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Session JSON must be an object")
        session = cls(
            project=data.get("project", ""),
            crs=data.get("crs", ""),
        )
        session.timestamp = data.get("timestamp", session.timestamp)
        session.measurements = list(data.get("measurements", []))
        return session


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = MeasurementSession(project="test", crs="EPSG:32648")
    s.add_measurement({"value": 10.5, "unit": "meter", "method": "distance"})
    s.add_measurement({"value": 2.3, "unit": "meter^2", "method": "area"})
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    s.export_json(path)
    s2 = MeasurementSession.load_json(path)
    assert s2.project == s.project and len(s2.measurements) == 2
    Path(path).unlink()
    logger.info("MeasurementSession manual test passed.")
