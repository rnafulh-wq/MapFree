"""
Geospatial pipeline: orchestrate georef, classification, rasterize, orthomosaic.
Pure backend; callable from main mapfree pipeline. No GUI.
"""

from pathlib import Path
from typing import Optional, Callable, Any

import logging

from mapfree.utils.dependency_check import check_geospatial_dependencies
from mapfree.geospatial.georef import georeference
from mapfree.geospatial.classification import classify_point_cloud
from mapfree.geospatial.rasterizer import rasterize
from mapfree.geospatial.orthomosaic import build_orthomosaic

log = logging.getLogger(__name__)


def run_geospatial_pipeline(
    project_path: Path,
    sparse_path: Optional[Path] = None,
    dense_path: Optional[Path] = None,
    image_path: Optional[Path] = None,
    crs: str = "EPSG:4326",
    run_georef: bool = True,
    run_classification: bool = False,
    run_raster: bool = False,
    run_ortho: bool = False,
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """
    Run geospatial steps on project outputs.
    sparse_path/dense_path: typically project_path/sparse_merged/0 or project_path/dense.
    image_path: folder of input images (for orthomosaic).
    on_progress: optional callback (step_name, 0.0..1.0) for progress.
    Returns dict with output paths: georef, classified, raster, ortho.
    """
    check_geospatial_dependencies()

    project_path = Path(project_path)
    if sparse_path is None:
        sparse_path = project_path / "sparse_merged" / "0"
    if not sparse_path.exists():
        sparse_path = project_path / "sparse" / "0"
    if dense_path is None:
        dense_path = project_path / "dense"
    if image_path is None:
        image_path = project_path / "images"

    def _progress(step: str, pct: float):
        if on_progress:
            on_progress(step, pct)
        log.info("%s: %.0f%%", step, pct * 100)

    results = {}

    if run_georef:
        _progress("georeference", 0.0)
        out = georeference(sparse_path, crs=crs)
        results["georef"] = out
        _progress("georeference", 1.0)

    if run_classification and dense_path.exists():
        _progress("classification", 0.0)
        ply = dense_path / "fused.ply"
        if ply.exists():
            results["classified"] = classify_point_cloud(ply)
        _progress("classification", 1.0)

    if run_raster:
        _progress("rasterize", 0.0)
        src = results.get("georef", dense_path if dense_path.exists() else sparse_path)
        src = Path(src) if isinstance(src, Path) else Path(sparse_path)
        ply = src / "fused.ply" if src.is_dir() else src
        if not ply.exists():
            ply = sparse_path / "points3D.ply" if (sparse_path / "points3D.ply").exists() else src
        results["raster"] = rasterize(ply)
        _progress("rasterize", 1.0)

    if run_ortho and image_path.exists():
        _progress("orthomosaic", 0.0)
        dem = results.get("raster") if run_raster else None
        results["ortho"] = build_orthomosaic(
            image_path,
            sparse_path,
            dem_path=Path(dem) if dem else None,
        )
        _progress("orthomosaic", 1.0)

    return results
