"""Tests for mapfree.geospatial.geojson_builder."""
import pytest

from mapfree.geospatial.geojson_builder import build_geojson_points


class TestBuildGeojsonPoints:
    def test_empty_input(self):
        result = build_geojson_points([])
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []

    def test_single_point(self):
        pts = [{"lat": 13.7, "lon": 100.5, "filename": "img.jpg"}]
        result = build_geojson_points(pts)
        assert len(result["features"]) == 1
        f = result["features"][0]
        assert f["type"] == "Feature"
        assert f["geometry"]["type"] == "Point"
        assert f["geometry"]["coordinates"] == [100.5, 13.7]
        assert f["properties"]["filename"] == "img.jpg"

    def test_multiple_points(self):
        pts = [
            {"lat": 10.0, "lon": 100.0},
            {"lat": 11.0, "lon": 101.0},
            {"lat": 12.0, "lon": 102.0},
        ]
        result = build_geojson_points(pts)
        assert len(result["features"]) == 3

    def test_skip_missing_lat_lon(self):
        pts = [
            {"lat": 13.7, "lon": 100.5},
            {"lat": 14.0},  # missing lon
            {"lon": 101.0},  # missing lat
            {},  # missing both
        ]
        result = build_geojson_points(pts)
        assert len(result["features"]) == 1

    def test_altitude_included(self):
        pts = [{"lat": 13.0, "lon": 100.0, "alt": 50.0}]
        result = build_geojson_points(pts)
        assert result["features"][0]["properties"]["altitude"] == pytest.approx(50.0)

    def test_altitude_via_altitude_key(self):
        pts = [{"lat": 13.0, "lon": 100.0, "altitude": 100.5}]
        result = build_geojson_points(pts)
        assert result["features"][0]["properties"]["altitude"] == pytest.approx(100.5)

    def test_invalid_altitude_skipped(self):
        pts = [{"lat": 13.0, "lon": 100.0, "alt": "bad"}]
        result = build_geojson_points(pts)
        assert "altitude" not in result["features"][0]["properties"]

    def test_timestamp_included(self):
        pts = [{"lat": 13.0, "lon": 100.0, "timestamp": "2024-01-01T10:00:00"}]
        result = build_geojson_points(pts)
        assert result["features"][0]["properties"]["timestamp"] == "2024-01-01T10:00:00"

    def test_null_timestamp_skipped(self):
        pts = [{"lat": 13.0, "lon": 100.0, "timestamp": None}]
        result = build_geojson_points(pts)
        assert "timestamp" not in result["features"][0]["properties"]

    def test_invalid_lat_lon_skipped(self):
        pts = [{"lat": "bad", "lon": 100.0}]
        result = build_geojson_points(pts)
        assert len(result["features"]) == 0

    def test_feature_collection_type(self):
        result = build_geojson_points([{"lat": 10.0, "lon": 100.0}])
        assert result["type"] == "FeatureCollection"
