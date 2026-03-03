"""
Measurement & Inspection Engine — headless core for mesh/point-cloud measurements.
Stage 1: geometry, picking, CRS, measurement engine.
Stage 2: volume, profile, KDTree, SimpleBVH.
Stage 3: TIN volume, surface deviation, CRS transform, session, parallel. No UI, no OpenGL.
"""
from mapfree.engines.inspection.models import Point3D, MeasurementResult
from mapfree.engines.inspection.geometry_utils import (
    distance_3d,
    distance_2d,
    polyline_length,
    polygon_area_2d,
    polygon_area_3d,
)
from mapfree.engines.inspection.crs_manager import CRSManager
from mapfree.engines.inspection.picking import (
    ray_triangle_intersect,
    ray_mesh_intersect,
)
from mapfree.engines.inspection.measurement_engine import MeasurementEngine
from mapfree.engines.inspection.volume import VolumeEngine
from mapfree.engines.inspection.profile import ProfileEngine
from mapfree.engines.inspection.spatial_index import KDTreeWrapper, SimpleBVH
from mapfree.engines.inspection.tin_volume import TINVolumeEngine
from mapfree.engines.inspection.deviation import SurfaceDeviationEngine
from mapfree.engines.inspection.session import MeasurementSession
from mapfree.engines.inspection.parallel import ParallelExecutor
try:
    from mapfree.engines.inspection.crs_transform import CRSTransformer
except RuntimeError:
    CRSTransformer = None

__all__ = [
    "Point3D",
    "MeasurementResult",
    "distance_3d",
    "distance_2d",
    "polyline_length",
    "polygon_area_2d",
    "polygon_area_3d",
    "CRSManager",
    "ray_triangle_intersect",
    "ray_mesh_intersect",
    "MeasurementEngine",
    "VolumeEngine",
    "ProfileEngine",
    "KDTreeWrapper",
    "SimpleBVH",
    "TINVolumeEngine",
    "SurfaceDeviationEngine",
    "MeasurementSession",
    "ParallelExecutor",
    "CRSTransformer",
]
