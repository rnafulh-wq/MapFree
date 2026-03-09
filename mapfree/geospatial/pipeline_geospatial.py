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
from mapfree.geospatial.georef import georeference_point_cloud, find_fused_ply
from mapfree.geospatial.raster import generate_dsm, generate_dtm
from mapfree.geospatial.orthorectify import generate_orthophoto, prepare_georeferenced_vrts
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

    try:
        from mapfree.core.project_structure import resolve_project_paths
        paths = resolve_project_paths(project_path)
        geo_dir = Path(paths.geospatial)
        images_dir = Path(paths.images)
        search_root = paths.dense.parent
    except Exception:
        geo_dir = project_path / "geospatial"
        images_dir = project_path / "images"
        search_root = project_path

    if not dense_ply_path.exists():
        found = find_fused_ply(search_root)
        if found is not None:
            dense_ply_path = found
        else:
            raise RuntimeError(
                "Geospatial: fused.ply tidak ditemukan di %s" % search_root
            )
    check_geospatial_dependencies()

    from mapfree.core.config import get_geospatial_config
    geo_cfg = get_geospatial_config()
    resolution = float(geo_cfg.get("resolution", 0.05))
    target_epsg = geo_cfg.get("target_epsg")
    try:
        epsg_int = int(target_epsg) if target_epsg is not None else None
    except (TypeError, ValueError):
        epsg_int = None

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
                sparse_dir = None
                for candidate in (
                    project_path / "sparse_merged" / "0",
                    project_path / "01_sparse" / "0",
                ):
                    if (candidate / "images.bin").is_file():
                        sparse_dir = candidate
                        break
                try:
                    georeference_point_cloud(
                        dense_ply_path,
                        dense_las,
                        gps_center,
                        database_path=database_path,
                        sparse_dir=sparse_dir,
                        gps_list=gps_list,
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
            log.info("generate_dsm: output path %s", dsm_tif)
            generate_dsm(dense_las, dsm_tif, resolution)
            log.info(
                "generate_dsm done: %s exists=%s size=%d",
                dsm_tif, dsm_tif.exists(), dsm_tif.stat().st_size if dsm_tif.exists() else 0,
            )
            if not dsm_tif.exists() or dsm_tif.stat().st_size == 0:
                raise RuntimeError("Geospatial: DSM .tif tidak valid setelah generate_dsm: %s" % dsm_tif)
            MIN_DSM_BYTES = 10_000
            if dsm_tif.stat().st_size < MIN_DSM_BYTES:
                log.warning(
                    "DSM.tif terlalu kecil (%d bytes), kemungkinan gagal. Cek PDAL pipeline output.",
                    dsm_tif.stat().st_size,
                )
            log.info("DSM .tif valid: %s (%.1f MB)", dsm_tif, dsm_tif.stat().st_size / (1024 * 1024))
            if epsg_int is None and gps_list:
                from mapfree.geospatial.georef import get_utm_epsg_from_gps
                epsg_int = get_utm_epsg_from_gps(
                    float(gps_list[0]["lat"]), float(gps_list[0]["lon"])
                )
                log.info("Auto-detected EPSG from GPS for DTM: %s", epsg_int)
            generate_dtm(classified_las, dtm_tif, resolution, epsg=epsg_int)
            if not dtm_tif.exists() or dtm_tif.stat().st_size == 0:
                raise RuntimeError("Geospatial: DTM .tif tidak valid setelah generate_dtm: %s" % dtm_tif)
            log.info("DTM .tif valid: %s (%.1f MB)", dtm_tif, dtm_tif.stat().st_size / (1024 * 1024))
            _emit("dtm_done")
            if images_dir.is_dir() and dtm_tif.exists():
                vrts_dir = geo_dir / "ortho_vrts"
                prepared = prepare_georeferenced_vrts(
                    images_dir, dtm_tif, vrts_dir
                )
                if prepared is not None:
                    ortho_dir = prepared
                    log.info("Orthophoto dari VRT (EXIF GPS): %s", ortho_dir)
                else:
                    ortho_dir = images_dir
                    log.debug(
                        "Tidak ada VRT dari EXIF, coba ortho dari folder gambar: %s",
                        ortho_dir,
                    )
                try:
                    generate_orthophoto(ortho_dir, dtm_tif, ortho_tif)
                except Exception as e:
                    log.warning(
                        "Orthophoto tidak dihasilkan: %s. Lanjut tanpa orthophoto.",
                        e,
                    )
            _emit("orthophoto_done")
    except Exception as e:
        raise RuntimeError("Geospatial stage failed: %s" % e) from e


__all__ = [
    "run_geospatial",
    "run_geospatial_pipeline",
]
