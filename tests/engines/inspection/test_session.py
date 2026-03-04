"""Tests for mapfree.engines.inspection.session.MeasurementSession."""
import json
import numpy as np
import pytest

from mapfree.engines.inspection.session import MeasurementSession, _serialize_for_json


class TestSerializeForJson:
    def test_plain_dict(self):
        out = _serialize_for_json({"a": 1, "b": "x"})
        assert out == {"a": 1, "b": "x"}

    def test_list(self):
        out = _serialize_for_json([1, 2, 3])
        assert out == [1, 2, 3]

    def test_numpy_float(self):
        out = _serialize_for_json(np.float64(3.14))
        assert isinstance(out, float)
        assert out == pytest.approx(3.14)

    def test_numpy_int(self):
        out = _serialize_for_json(np.int32(42))
        assert isinstance(out, int)
        assert out == 42

    def test_numpy_array(self):
        out = _serialize_for_json(np.array([1.0, 2.0]))
        assert out == [1.0, 2.0]

    def test_nested(self):
        out = _serialize_for_json({"arr": np.array([1, 2]), "val": np.float64(0.5)})
        assert out == {"arr": [1, 2], "val": 0.5}


class TestMeasurementSession:
    def test_default_creation(self):
        s = MeasurementSession()
        assert s.project == ""
        assert s.crs == ""
        assert s.measurements == []

    def test_creation_with_args(self):
        s = MeasurementSession(project="proj1", crs="EPSG:32648")
        assert s.project == "proj1"
        assert s.crs == "EPSG:32648"

    def test_add_measurement(self):
        s = MeasurementSession()
        s.add_measurement({"value": 5.0, "unit": "meter", "method": "distance"})
        assert len(s.measurements) == 1
        assert s.measurements[0]["value"] == 5.0

    def test_add_multiple_measurements(self):
        s = MeasurementSession()
        s.add_measurement({"value": 1.0})
        s.add_measurement({"value": 2.0})
        assert len(s.measurements) == 2

    def test_set_metadata(self):
        s = MeasurementSession()
        s.set_metadata(project="new_project", crs="EPSG:4326")
        assert s.project == "new_project"
        assert s.crs == "EPSG:4326"

    def test_to_dict(self):
        s = MeasurementSession(project="p", crs="EPSG:32648")
        s.add_measurement({"value": 10.0, "unit": "m"})
        d = s.to_dict()
        assert d["project"] == "p"
        assert d["crs"] == "EPSG:32648"
        assert len(d["measurements"]) == 1
        assert "timestamp" in d

    def test_export_and_load_json(self, tmp_path):
        s = MeasurementSession(project="test", crs="EPSG:32648")
        s.add_measurement({"value": 10.5, "unit": "meter", "method": "distance"})
        path = tmp_path / "session.json"
        s.export_json(path)
        assert path.exists()
        s2 = MeasurementSession.load_json(path)
        assert s2.project == "test"
        assert s2.crs == "EPSG:32648"
        assert len(s2.measurements) == 1
        assert s2.measurements[0]["value"] == pytest.approx(10.5)

    def test_load_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            MeasurementSession.load_json(tmp_path / "missing.json")

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("[not, a, dict]")
        with pytest.raises(ValueError):
            MeasurementSession.load_json(path)

    def test_numpy_values_serialized(self, tmp_path):
        """Numpy values in measurements should survive JSON round-trip."""
        s = MeasurementSession()
        s.add_measurement({"value": np.float64(3.14), "arr": np.array([1.0, 2.0])})
        path = tmp_path / "session.json"
        s.export_json(path)
        data = json.loads(path.read_text())
        assert data["measurements"][0]["value"] == pytest.approx(3.14)
        assert data["measurements"][0]["arr"] == [1.0, 2.0]
