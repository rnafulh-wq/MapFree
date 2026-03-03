"""
Integration tests for orthophoto pipeline: finalize_orthophoto (reproject, tiling, compression, overviews, validation).
Requires: gdalwarp, gdal_translate, gdaladdo, gdalinfo.
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _gdal_available():
    try:
        from osgeo import gdal
        return True
    except ImportError:
        return False


def _create_small_geotiff(path: Path, epsg: int = 32648):
    """Create a minimal GeoTIFF with CRS and geotransform for testing finalize_orthophoto."""
    try:
        from osgeo import gdal
    except ImportError:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    drv = gdal.GetDriverByName("GTiff")
    if not drv:
        return False
    ds = drv.Create(str(path), 10, 10, 1, gdal.GDT_Float32, options=["COMPRESS=LZW"])
    if not ds:
        return False
    ds.SetGeoTransform([100.0, 1.0, 0.0, 200.0, 0.0, -1.0])
    from osgeo import osr
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).Fill(1.0)
    ds.GetRasterBand(1).SetNoDataValue(-9999.0)
    ds.FlushCache()
    ds = None
    return path.exists()


@pytest.mark.skipif(not _gdal_available(), reason="GDAL not available")
def test_finalize_orthophoto_reproject_and_validate(tmp_path):
    """finalize_orthophoto: gdalwarp -> gdal_translate (tiling, compression) -> gdaladdo -> validate."""
    import sys
    sys.path.insert(0, str(ROOT))
    from mapfree.geospatial.orthorectify import finalize_orthophoto
    from mapfree.geospatial.raster import validate_dtm

    src = tmp_path / "ortho_src.tif"
    if not _create_small_geotiff(src, epsg=32648):
        pytest.skip("Could not create test GeoTIFF")
    out = tmp_path / "ortho_epsg4326.tif"
    result = finalize_orthophoto(src, 4326, output_path=out)
    assert result == out
    assert out.exists()
    v = validate_dtm(out)
    assert v.get("crs_exists") is True
    assert v.get("pixel_size_positive") is True
    assert v.get("bbox_sane") is True


@pytest.mark.skipif(not _gdal_available(), reason="GDAL not available")
def test_finalize_orthophoto_missing_file_raises():
    """finalize_orthophoto raises for missing path."""
    import sys
    sys.path.insert(0, str(ROOT))
    from mapfree.geospatial.orthorectify import finalize_orthophoto

    with pytest.raises(RuntimeError, match="does not exist"):
        finalize_orthophoto(Path("/nonexistent/ortho.tif"), 4326)
