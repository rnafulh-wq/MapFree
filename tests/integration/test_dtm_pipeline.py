"""
Integration tests for DTM pipeline: PLY -> LAS -> SMRF -> writers.gdal -> dtm.tif -> validate_dtm.
Requires: pdal, gdal (writers.gdal path only; no gdal_grid for LAS).
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
POINT_CLOUD_PLY = FIXTURES / "point_cloud.ply"


def _pdal_available():
    import subprocess
    try:
        r = subprocess.run(["pdal", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _gdal_available():
    try:
        from osgeo import gdal  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _pdal_available(), reason="PDAL not available")
@pytest.mark.skipif(not _gdal_available(), reason="GDAL not available")
def test_dtm_pipeline_ply_to_las_to_dtm(tmp_path):
    """PLY -> LAS -> classify_ground -> generate_dtm (PDAL writers.gdal) -> validate_dtm."""
    import sys
    sys.path.insert(0, str(ROOT))
    from mapfree.geospatial.classification import convert_ply_to_las, classify_ground
    from mapfree.geospatial.raster import generate_dtm, validate_dtm

    if not POINT_CLOUD_PLY.exists():
        pytest.skip("fixture point_cloud.ply not found")
    las_all = tmp_path / "all.las"
    las_ground = tmp_path / "ground.las"
    dtm_tif = tmp_path / "dtm.tif"

    convert_ply_to_las(POINT_CLOUD_PLY, las_all)
    assert las_all.exists()
    classify_ground(las_all, las_ground)
    assert las_ground.exists()

    resolution = 0.5
    out = generate_dtm(las_ground, dtm_tif, resolution, epsg=32648)
    assert out == dtm_tif
    assert dtm_tif.exists()

    v = validate_dtm(dtm_tif)
    assert v.get("valid") is True, v.get("message", v)
    assert v.get("crs_exists") is True
    assert v.get("pixel_size_positive") is True
    assert v.get("not_all_nodata") is True
    assert v.get("bbox_sane") is True


@pytest.mark.skipif(not _pdal_available(), reason="PDAL not available")
def test_estimate_resolution(tmp_path):
    """estimate_resolution returns value in [min_res, max_res] from point density."""
    import sys
    sys.path.insert(0, str(ROOT))
    from mapfree.geospatial.classification import convert_ply_to_las
    from mapfree.geospatial.raster import estimate_resolution

    if not POINT_CLOUD_PLY.exists():
        pytest.skip("fixture point_cloud.ply not found")
    las = tmp_path / "in.las"
    convert_ply_to_las(POINT_CLOUD_PLY, las)
    res = estimate_resolution(las, min_resolution=0.01, max_resolution=2.0)
    assert 0.01 <= res <= 2.0


@pytest.mark.skipif(not _gdal_available(), reason="GDAL not available")
def test_validate_dtm_rejects_missing_file():
    """validate_dtm raises for missing path."""
    import sys
    sys.path.insert(0, str(ROOT))
    from mapfree.geospatial.raster import validate_dtm

    with pytest.raises(RuntimeError, match="does not exist"):
        validate_dtm(Path("/nonexistent/dtm.tif"))
