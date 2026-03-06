"""
Geospatial pipeline: convert dense point cloud to DTM, DSM, and orthophoto.

Orchestrates georeferencing, classification, rasterization (DTM/DSM), and
orthorectification. Callable from the main MapFree pipeline; no GUI dependency.
"""

from pathlib import Path
from typing import Callable, Optional

from mapfree.utils.dependency_check import check_geospatial_dependencies
from mapfree.geospatial.classification import convert_ply_to_las, classify_ground
from mapfree.geospatial.raster import generate_dsm, generate_dtm
from mapfree.geospatial.orthorectify import generate_orthophoto
from mapfree.geospatial.output_names import DTM_TIF, DSM_TIF, ORTHOPHOTO_TIF
from mapfree.geospatial.pipeline import run_geospatial_pipeline


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

    try:
        if dense_ply_path.exists():
            convert_ply_to_las(dense_ply_path, dense_las)
            classify_ground(dense_las, classified_las)
            generate_dsm(dense_las, dsm_tif, resolution)
            generate_dtm(classified_las, dtm_tif, resolution, epsg=epsg_int)
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
