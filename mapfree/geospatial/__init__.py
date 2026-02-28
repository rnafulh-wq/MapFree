"""
Geospatial backend: georeferencing, classification, rasterization, orthomosaic.
No GUI dependency; callable from main pipeline.
"""

from mapfree.geospatial.georef import (
    georeference,
    convert_ply_to_las,
    EVENT_STAGE_STARTED,
    EVENT_STAGE_COMPLETED,
)
from mapfree.geospatial.classification import classify_point_cloud, classify_ground
from mapfree.geospatial.rasterizer import rasterize, generate_dsm, generate_dtm
from mapfree.geospatial.orthomosaic import build_orthomosaic, generate_orthophoto
from mapfree.geospatial.pipeline import run_geospatial_pipeline

__all__ = [
    "georeference",
    "convert_ply_to_las",
    "EVENT_STAGE_STARTED",
    "EVENT_STAGE_COMPLETED",
    "classify_point_cloud",
    "classify_ground",
    "rasterize",
    "generate_dsm",
    "generate_dtm",
    "build_orthomosaic",
    "generate_orthophoto",
    "run_geospatial_pipeline",
]
