"""
Build GeoJSON from camera/GPS points (e.g. from exif_reader).
"""


def build_geojson_points(camera_points: list[dict]) -> dict:
    """
    Build a GeoJSON FeatureCollection from a list of point dicts.

    Each item in camera_points should have at least:
      - lat: float
      - lon: float
      - filename: str (optional; included in properties)
      - alt / altitude: optional; included in properties as "altitude"

    Returns a dict conforming to GeoJSON FeatureCollection:
      - type: "FeatureCollection"
      - features: list of Feature dicts with Point geometry and properties
    """
    features = []
    for pt in camera_points:
        lon = pt.get("lon")
        lat = pt.get("lat")
        if lon is None or lat is None:
            continue
        try:
            lon_f = float(lon)
            lat_f = float(lat)
        except (TypeError, ValueError):
            continue
        props = {}
        if "filename" in pt:
            props["filename"] = pt["filename"]
        alt = pt.get("alt", pt.get("altitude"))
        if alt is not None:
            try:
                props["altitude"] = float(alt)
            except (TypeError, ValueError):
                pass
        if "timestamp" in pt and pt["timestamp"] is not None:
            props["timestamp"] = pt["timestamp"]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon_f, lat_f],
            },
            "properties": props,
        })
    return {
        "type": "FeatureCollection",
        "features": features,
    }
