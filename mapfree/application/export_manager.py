"""
Export geospatial products (DTM, DSM, orthophoto) from project to user-chosen paths.
Prefers EPSG-reprojected files; falls back to originals. Preserves metadata via shutil.copy2.
Uses mapfree.geospatial.output_names for consistent filenames.
"""
import shutil
from pathlib import Path

import logging

from mapfree.geospatial.output_names import (
    DTM_TIF,
    DTM_EPSG_TIF,
    DSM_TIF,
    DSM_EPSG_TIF,
    ORTHOPHOTO_TIF,
    ORTHOPHOTO_EPSG_TIF,
)

log = logging.getLogger(__name__)

_GEO = "geospatial"


def _source_path(project_dir: Path, epsg_name: str, orig_name: str) -> Path:
    """Return path to EPSG file if it exists, else original. Does not check existence."""
    geo = Path(project_dir) / _GEO
    epsg_path = geo / epsg_name
    orig_path = geo / orig_name
    if epsg_path.exists():
        return epsg_path
    return orig_path


def _copy_or_raise(source: Path, dest: Path) -> Path:
    """Copy source to dest with shutil.copy2 (preserves metadata). Raise if source missing."""
    if not source.exists():
        raise FileNotFoundError("Export source does not exist: %s" % source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    log.info("Exported: %s -> %s", source.name, dest)
    return dest


class ExportManager:
    """
    Export DTM, DSM, and orthophoto from a project. Prefers EPSG-reprojected files;
    falls back to originals. Uses shutil.copy2 to preserve metadata.
    """

    @staticmethod
    def export_dtm(project_dir: Path, export_path: Path) -> Path:
        """
        Copy DTM to export_path. Prefer geospatial/dtm_epsg.tif; fallback to dtm.tif.
        Raises FileNotFoundError if neither exists.
        """
        project_dir = Path(project_dir)
        export_path = Path(export_path)
        source = _source_path(project_dir, DTM_EPSG_TIF, DTM_TIF)
        return _copy_or_raise(source, export_path)

    @staticmethod
    def export_dsm(project_dir: Path, export_path: Path) -> Path:
        """
        Copy DSM to export_path. Prefer geospatial/dsm_epsg.tif; fallback to dsm.tif.
        Raises FileNotFoundError if neither exists.
        """
        project_dir = Path(project_dir)
        export_path = Path(export_path)
        source = _source_path(project_dir, DSM_EPSG_TIF, DSM_TIF)
        return _copy_or_raise(source, export_path)

    @staticmethod
    def export_orthophoto(project_dir: Path, export_path: Path) -> Path:
        """
        Copy orthophoto to export_path. Prefer geospatial/orthophoto_epsg.tif;
        fallback to orthophoto.tif. Raises FileNotFoundError if neither exists.
        """
        project_dir = Path(project_dir)
        export_path = Path(export_path)
        source = _source_path(project_dir, ORTHOPHOTO_EPSG_TIF, ORTHOPHOTO_TIF)
        return _copy_or_raise(source, export_path)

    @staticmethod
    def export_all(project_dir: Path, export_dir: Path) -> dict[str, Path]:
        """
        Export DTM, DSM, and orthophoto to export_dir. Files are named dtm.tif,
        dsm.tif, orthophoto.tif. Prefer EPSG versions; fallback to originals.
        Returns dict with keys "dtm", "dsm", "orthophoto" and exported paths as values.
        Raises FileNotFoundError if any product is missing.
        """
        project_dir = Path(project_dir)
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        out = {}
        out["dtm"] = ExportManager.export_dtm(project_dir, export_dir / DTM_TIF)
        out["dsm"] = ExportManager.export_dsm(project_dir, export_dir / DSM_TIF)
        out["orthophoto"] = ExportManager.export_orthophoto(
            project_dir, export_dir / ORTHOPHOTO_TIF
        )
        return out
