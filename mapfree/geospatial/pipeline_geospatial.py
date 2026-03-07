"""
Geospatial pipeline: convert dense point cloud to DTM, DSM, and orthophoto.

Orchestrates georeferencing, classification, rasterization (DTM/DSM), and
orthorectification. Callable from the main MapFree pipeline; no GUI dependency.

Workflow: fused.ply (PDAL translate) -> dense.las -> classify_ground -> classified.las;
DSM/DTM via PDAL writers.gdal (no direct GDAL on LAS); GDAL only for raster finishing.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from mapfree.utils.dependency_check import check_geospatial_dependencies
from mapfree.geospatial.classification import convert_ply_to_las, classify_ground
from mapfree.geospatial.georef import georeference_point_cloud
from mapfree.geospatial.raster import generate_dsm, generate_dtm
from mapfree.geospatial.orthorectify import generate_orthophoto
from mapfree.geospatial.output_names import DTM_TIF, DSM_TIF, ORTHOPHOTO_TIF
from mapfree.geospatial.pipeline import run_geospatial_pipeline

log = logging.getLogger(__name__)


def run_geospatial(
    project_path: Path | str,
    dense_ply_path: Path | str,
    on_event: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Run geospatial stages: convert PLY to LAS, classify ground, generate DSM/DTM,
    then orthophoto. Emits progress events via on_event:
      "geospatial_started"  at start
      "dtm_done"            after DTM is written
      "orthophoto_done"     after orthophoto is written
    """
    project_path = Path(project_path)
    dense_ply_path = Path(dense_ply_path)
    check_geospatial_dependencies()

    from mapfree.core.config import get_geospatial_config
    geo_cfg = get_geospatial_config()
    resolution = float(geo_cfg.get("resolution", 0.05))
    target_epsg = geo_cfg.get("target_epsg")
    try:
        epsg_int = int(target_epsg) if target_epsg is not None else None
    except (TypeError, ValueError):
        epsg_int = None

    # All geospatial outputs go into project_output/04_geospatial/ (v1.1.1) or legacy geospatial/
    try:
        from mapfree.core.project_structure import resolve_project_paths
        geo_dir = Path(resolve_project_paths(project_path).geospatial)
        images_dir = Path(resolve_project_paths(project_path).images)
    except Exception:
        geo_dir = project_path / "geospatial"
        images_dir = project_path / "images"
    geo_dir.mkdir(parents=True, exist_ok=True)
    dense_las = geo_dir / "dense.las"
    classified_las = geo_dir / "classified.las"
    dsm_tif = geo_dir / DSM_TIF
    dtm_tif = geo_dir / DTM_TIF
    ortho_tif = geo_dir / ORTHOPHOTO_TIF

    def _emit(name: str) -> None:
        if on_event:
            on_event(name)

    _emit("geospatial_started")

    # Validate fused.ply before starting (Step A input)
    if not dense_ply_path.exists():
        raise RuntimeError(
            "Geospatial: fused.ply tidak ditemukan: %s" % dense_ply_path
        )
    ply_size_mb = dense_ply_path.stat().st_size / (1024 * 1024)
    log.info("fused.ply exists: True, size: %.1f MB", ply_size_mb)

    try:
        if dense_ply_path.exists():
            # GPS georeferencing: convert PLY to LAS with UTM CRS so DSM/DTM have correct location
            gps_list = []
            try:
                from mapfree.geospatial.exif_reader import extract_gps_from_images
                gps_list = extract_gps_from_images(str(images_dir))
            except Exception as e:
                log.debug("extract_gps_from_images failed: %s", e)
            if gps_list:
                rec = gps_list[0]
                gps_center = (
                    rec["lat"],
                    rec["lon"],
                    rec.get("alt") if rec.get("alt") is not None else 0.0,
                )
                database_path = Path(project_path) / "database.db"
                if not database_path.exists():
                    database_path = None
                try:
                    georeference_point_cloud(
                        dense_ply_path,
                        dense_las,
                        gps_center,
                        database_path=database_path,
                    )
                except RuntimeError as e:
                    log.warning("Georeferencing failed, falling back to plain convert: %s", e)
                    convert_ply_to_las(dense_ply_path, dense_las)
            else:
                convert_ply_to_las(dense_ply_path, dense_las)
            # Validate dense.las before any GDAL/PDAL raster step (GDAL cannot read LAS directly)
            if not dense_las.exists():
                raise RuntimeError(
                    "Geospatial: dense.las tidak ditemukan: %s" % dense_las
                )
            if dense_las.stat().st_size == 0:
                raise RuntimeError(
                    "Geospatial: dense.las kosong (0 bytes): %s" % dense_las
                )
            las_size_mb = dense_las.stat().st_size / (1024 * 1024)
            log.info("dense.las size: %.1f MB", las_size_mb)
            classify_ground(dense_las, classified_las)
            generate_dsm(dense_las, dsm_tif, resolution)
            if not dsm_tif.exists() or dsm_tif.stat().st_size == 0:
                raise RuntimeError("Geospatial: DSM .tif tidak valid setelah generate_dsm: %s" % dsm_tif)
            log.info("DSM .tif valid: %s (%.1f MB)", dsm_tif, dsm_tif.stat().st_size / (1024 * 1024))
            generate_dtm(classified_las, dtm_tif, resolution, epsg=epsg_int)
            if not dtm_tif.exists() or dtm_tif.stat().st_size == 0:
                raise RuntimeError("Geospatial: DTM .tif tidak valid setelah generate_dtm: %s" % dtm_tif)
            log.info("DTM .tif valid: %s (%.1f MB)", dtm_tif, dtm_tif.stat().st_size / (1024 * 1024))
            _emit("dtm_done")
            if images_dir.is_dir() and dtm_tif.exists():
                try:
                    generate_orthophoto(images_dir, dtm_tif, ortho_tif)
                except RuntimeError:
                    pass
            _emit("orthophoto_done")
    except Exception as e:
        raise RuntimeError("Geospatial stage failed: %s" % e) from e


__all__ = [
    "run_geospatial",
    "run_geospatial_pipeline",
]
