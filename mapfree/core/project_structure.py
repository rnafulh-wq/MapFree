"""Project structure helpers (Metashape-style).

Creates and resolves a consistent output folder layout for a project:

  <output_dir>/<project_name>/
    <project_name>.mapfree
    images/
    01_sparse/
    02_dense/
    03_mesh/
    04_geospatial/
    05_exports/
    logs/

This module is in core so pipeline and GUI can agree on paths without
cross-layer imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_VERSION = "1.1.1"


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved project paths.

    Attributes:
        root: Project root folder.
        project_file: `<name>.mapfree` JSON file.
        images: Project-local images folder (pipeline input).
        sparse: Sparse output folder (COLMAP).
        dense: Dense output folder (fused.ply, etc.).
        mesh: Mesh/OpenMVS output folder.
        geospatial: Geospatial outputs (DTM/DSM/orthophoto).
        exports: User exports folder.
        logs: Logs folder.
    """

    root: Path
    project_file: Path
    images: Path
    sparse: Path
    dense: Path
    mesh: Path
    geospatial: Path
    exports: Path
    logs: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "root": self.root,
            "project_file": self.project_file,
            "images": self.images,
            "sparse": self.sparse,
            "dense": self.dense,
            "mesh": self.mesh,
            "geospatial": self.geospatial,
            "exports": self.exports,
            "logs": self.logs,
        }


def _default_paths(root: Path, project_name: str) -> ProjectPaths:
    root = Path(root)
    return ProjectPaths(
        root=root,
        project_file=root / f"{project_name}.mapfree",
        images=root / "images",
        sparse=root / "01_sparse",
        dense=root / "02_dense",
        mesh=root / "03_mesh",
        geospatial=root / "04_geospatial",
        exports=root / "05_exports",
        logs=root / "logs",
    )


def _load_project_file(project_file: Path) -> Optional[dict[str, Any]]:
    if not Path(project_file).is_file():
        return None
    try:
        raw = json.loads(Path(project_file).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def resolve_project_paths(project_root: Path | str) -> ProjectPaths:
    """Resolve project paths from `<name>.mapfree` if present, else infer.

    This is intentionally tolerant: if a project was created before v1.1.1,
    it falls back to legacy folders (sparse/, dense/, geospatial/).
    """
    root = Path(project_root)
    project_name = root.name
    candidate = root / f"{project_name}.mapfree"
    data = _load_project_file(candidate)

    # Prefer explicit paths from project file when available.
    if data and isinstance(data.get("paths"), dict):
        paths_raw: Dict[str, Any] = data["paths"]  # type: ignore[assignment]

        def _p(key: str, fallback: Path) -> Path:
            v = paths_raw.get(key)
            if v and str(v).strip():
                return Path(str(v))
            return fallback

        defaults = _default_paths(root, project_name)
        return ProjectPaths(
            root=_p("root", defaults.root),
            project_file=candidate,
            images=_p("images", defaults.images),
            sparse=_p("sparse", defaults.sparse),
            dense=_p("dense", defaults.dense),
            mesh=_p("mesh", defaults.mesh),
            geospatial=_p("geospatial", defaults.geospatial),
            exports=_p("exports", defaults.exports),
            logs=_p("logs", defaults.logs),
        )

    # If new folders exist, use them; else fallback to legacy.
    defaults = _default_paths(root, project_name)
    if defaults.sparse.exists() or defaults.dense.exists() or defaults.geospatial.exists():
        return defaults

    # Legacy layout
    return ProjectPaths(
        root=root,
        project_file=candidate,
        images=root / "images",
        sparse=root / "sparse",
        dense=root / "dense",
        mesh=root / "mvs",
        geospatial=root / "geospatial",
        exports=root / "exports",
        logs=root / "logs",
    )


def create_project_structure(output_dir: Path | str, project_name: str) -> ProjectPaths:
    """Create project folder structure under output_dir/project_name.

    Idempotent: creates missing folders; does not overwrite existing `.mapfree` file.
    Returns resolved paths.
    """
    project_name = (project_name or "").strip()
    if not project_name:
        raise ValueError("project_name is required")
    root = Path(output_dir) / project_name
    paths = _default_paths(root, project_name)
    root.mkdir(parents=True, exist_ok=True)
    for p in (paths.images, paths.sparse, paths.dense, paths.mesh, paths.geospatial, paths.exports, paths.logs):
        p.mkdir(parents=True, exist_ok=True)

    if not paths.project_file.exists():
        data = {
            "version": PROJECT_VERSION,
            "name": project_name,
            "created": datetime.now(timezone.utc).isoformat(),
            "paths": {k: str(v) for k, v in paths.as_dict().items() if k != "project_file"},
        }
        paths.project_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return paths
