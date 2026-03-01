"""
Geospatial output filenames under project_output/geospatial/.
Single source of truth for consistent naming.
"""

# Raster outputs (originals from generate_dsm, generate_dtm, generate_orthophoto)
DTM_TIF = "dtm.tif"
DSM_TIF = "dsm.tif"
ORTHOPHOTO_TIF = "orthophoto.tif"

# Reprojected (from CRSManager.reproject_raster when EPSG detected)
DTM_EPSG_TIF = "dtm_epsg.tif"
DSM_EPSG_TIF = "dsm_epsg.tif"
ORTHOPHOTO_EPSG_TIF = "orthophoto_epsg.tif"
