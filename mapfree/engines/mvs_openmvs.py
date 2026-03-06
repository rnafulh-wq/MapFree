"""
OpenMVS dense reconstruction engine.
Replaces COLMAP dense (image_undistorter, patch_match_stereo, stereo_fusion) with:
  InterfaceCOLMAP -> DensifyPointCloud -> ReconstructMesh -> RefineMesh (optional) -> TextureMesh (optional).
All outputs go to project_path/03_mesh/. For backward compatibility, a PLY is written to dense/fused.ply.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from mapfree.core.logger import get_logger
from mapfree.core.wrapper import (
    EngineExecutionError,
    get_process_env,
    run_process_streaming,
)

OPENMVS_BINARIES = (
    "InterfaceCOLMAP",
    "DensifyPointCloud",
    "ReconstructMesh",
    "RefineMesh",
    "TextureMesh",
)

# Quality: low = lower densify res, no refine; medium = normal densify + refine; high = highest + refine
QUALITY_DENSIFY_LEVEL = {"low": 3, "medium": 2, "high": 0}  # -w N: 0=full, 1=half, 2=quarter, 3=1/8, ...
QUALITY_REFINE = {"low": False, "medium": True, "high": True}
QUALITY_TEXTURE = {"low": False, "medium": True, "high": True}


def _get_logger(context: Any) -> logging.Logger:
    return getattr(context, "logger", None) or get_logger("mvs_openmvs")


def _resolve_binary(name: str) -> Optional[str]:
    """Resolve OpenMVS executable. Returns path or None if not found."""
    bin_dir = os.environ.get("MAPFREE_OPENMVS_BIN_DIR", "").strip()
    if bin_dir:
        p = Path(bin_dir).resolve() / name
        if p.exists():
            return str(p)
    found = shutil.which(name)
    return found


def openmvs_available() -> bool:
    """Return True if InterfaceCOLMAP (and thus OpenMVS) is available."""
    return _resolve_binary("InterfaceCOLMAP") is not None


def _run_step(
    context: Any,
    cmd: list[str],
    step_name: str,
    timeout: int = 7200,
    log_file: Optional[Path] = None,
) -> None:
    """Run subprocess with streaming log; raise RuntimeError on non-zero exit or timeout."""
    logger = _get_logger(context)
    logger.info("OpenMVS step: %s", step_name)
    bus = getattr(context, "event_bus", None)
    if bus is not None:
        bus.emit("engine_stage_started", {"engine": "openmvs", "stage": step_name})

    def on_line(line: str) -> None:
        if bus is not None:
            bus.emit("engine_log", {"engine": "openmvs", "message": line})

    stop_event = getattr(context, "stop_event", None)
    project_path = Path(context.project_path)
    if log_file is None:
        logs_dir = project_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / ("openmvs_%s.log" % step_name.replace(" ", "_"))
    try:
        returncode = run_process_streaming(
            cmd,
            cwd=project_path,
            env=get_process_env(),
            timeout=timeout,
            logger=logger,
            line_callback=on_line,
            stop_event=stop_event,
            log_file=log_file,
        )
        if returncode != 0:
            logger.error("OpenMVS step failed: %s (exit %s)", step_name, returncode)
            if bus is not None:
                bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
            raise RuntimeError("OpenMVS %s failed with code %s" % (step_name, returncode))
        logger.info("OpenMVS step completed: %s", step_name)
    except subprocess.TimeoutExpired as e:
        logger.error("OpenMVS step timed out: %s", step_name)
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
        raise RuntimeError("OpenMVS %s timed out" % step_name) from e
    except EngineExecutionError as e:
        logger.error("OpenMVS step failed: %s — %s", step_name, e)
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
        raise RuntimeError("OpenMVS %s failed: %s" % (step_name, e)) from e
    except Exception as e:
        logger.error("OpenMVS step error: %s — %s", step_name, e)
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
        raise RuntimeError("OpenMVS %s failed: %s" % (step_name, e)) from e
    if bus is not None:
        bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})


class OpenMVSEngine:
    """
    OpenMVS dense pipeline: convert COLMAP -> densify -> mesh -> optional refine -> optional texture.
    Outputs under project_path/mvs/. Writes dense/fused.ply for backward compatibility.
    """

    def __init__(self, context: Any, quality: str = "medium"):
        self.context = context
        self._project_path = Path(context.project_path)
        self._mvs_dir = Path(getattr(context, "mesh_path", None) or (self._project_path / "mvs"))
        self._sparse_path = Path(context.sparse_path)
        self._dense_path = Path(context.dense_path)
        self._image_path = Path(context.image_path)
        self._quality = quality.lower() if quality else "medium"
        if self._quality not in ("low", "medium", "high"):
            self._quality = "medium"

    def _colmap_input_and_images(self) -> tuple[Path, Path]:
        """COLMAP input folder and image folder for InterfaceCOLMAP. Prefer sparse/0."""
        sparse_0 = self._sparse_path / "0"
        sparse_dir = sparse_0 if (sparse_0.exists() and (sparse_0 / "cameras.bin").exists()) else self._sparse_path
        if not sparse_dir.exists() or not (sparse_dir / "cameras.bin").exists():
            raise RuntimeError(
                "No COLMAP sparse output found at %s or %s" % (self._sparse_path, sparse_0)
            )
        return sparse_dir, self._image_path

    def convert_from_colmap(self) -> Path:
        """Run InterfaceCOLMAP; write scene.mvs. Returns path to scene.mvs."""
        self._mvs_dir.mkdir(parents=True, exist_ok=True)
        scene_mvs = self._mvs_dir / "scene.mvs"
        colmap_input, image_folder = self._colmap_input_and_images()
        bin_path = _resolve_binary("InterfaceCOLMAP")
        if not bin_path:
            raise RuntimeError("OpenMVS not found: InterfaceCOLMAP not in PATH or MAPFREE_OPENMVS_BIN_DIR")
        _run_step(
            self.context,
            [
                bin_path,
                "-i", str(colmap_input),
                "-o", str(scene_mvs),
                "--image-folder", str(image_folder),
            ],
            "InterfaceCOLMAP",
        )
        if not scene_mvs.exists():
            raise RuntimeError("InterfaceCOLMAP did not produce scene.mvs")
        return scene_mvs

    def densify_point_cloud(self, scene_mvs: Path) -> Path:
        """Run DensifyPointCloud; write scene_dense.mvs. Quality sets resolution level (-w)."""
        scene_dense_mvs = self._mvs_dir / "scene_dense.mvs"
        level = QUALITY_DENSIFY_LEVEL.get(self._quality, 2)
        bin_path = _resolve_binary("DensifyPointCloud")
        if not bin_path:
            raise RuntimeError("OpenMVS not found: DensifyPointCloud not in PATH or MAPFREE_OPENMVS_BIN_DIR")
        _run_step(
            self.context,
            [
                bin_path,
                str(scene_mvs),
                "-o", str(scene_dense_mvs),
                "-w", str(level),
            ],
            "DensifyPointCloud",
        )
        if not scene_dense_mvs.exists():
            raise RuntimeError("DensifyPointCloud did not produce scene_dense.mvs")
        return scene_dense_mvs

    def reconstruct_mesh(self, scene_dense_mvs: Path) -> Path:
        """Run ReconstructMesh; write scene_mesh.ply."""
        scene_mesh_ply = self._mvs_dir / "scene_mesh.ply"
        bin_path = _resolve_binary("ReconstructMesh")
        if not bin_path:
            raise RuntimeError("OpenMVS not found: ReconstructMesh not in PATH or MAPFREE_OPENMVS_BIN_DIR")
        _run_step(
            self.context,
            [bin_path, str(scene_dense_mvs), "-p", str(scene_mesh_ply)],
            "ReconstructMesh",
        )
        if not scene_mesh_ply.exists():
            raise RuntimeError("ReconstructMesh did not produce scene_mesh.ply")
        return scene_mesh_ply

    def refine_mesh(self, scene_dense_mvs: Path, scene_mesh_ply: Path) -> Optional[Path]:
        """Run RefineMesh if quality allows. Returns path to refined .mvs or None."""
        if not QUALITY_REFINE.get(self._quality, True):
            return None
        scene_mesh_refine_mvs = self._mvs_dir / "scene_mesh_refine.mvs"
        bin_path = _resolve_binary("RefineMesh")
        if not bin_path:
            raise RuntimeError("OpenMVS not found: RefineMesh not in PATH or MAPFREE_OPENMVS_BIN_DIR")
        _run_step(
            self.context,
            [
                bin_path,
                str(scene_dense_mvs),
                "-m", str(scene_mesh_ply),
                "-o", str(scene_mesh_refine_mvs),
            ],
            "RefineMesh",
        )
        if not scene_mesh_refine_mvs.exists():
            raise RuntimeError("RefineMesh did not produce scene_mesh_refine.mvs")
        return scene_mesh_refine_mvs

    def texture_mesh(self, scene_mesh_mvs: Path, mesh_ply: Path) -> Optional[Path]:
        """Run TextureMesh if quality allows. Returns path to scene_textured.mvs or None."""
        if not QUALITY_TEXTURE.get(self._quality, True):
            return None
        scene_textured_mvs = self._mvs_dir / "scene_textured.mvs"
        bin_path = _resolve_binary("TextureMesh")
        if not bin_path:
            raise RuntimeError("OpenMVS not found: TextureMesh not in PATH or MAPFREE_OPENMVS_BIN_DIR")
        _run_step(
            self.context,
            [
                bin_path,
                str(scene_mesh_mvs),
                "-m", str(mesh_ply),
                "-o", str(scene_textured_mvs),
            ],
            "TextureMesh",
        )
        if not scene_textured_mvs.exists():
            raise RuntimeError("TextureMesh did not produce scene_textured.mvs")
        return scene_textured_mvs

    def _copy_to_dense_fused(self, ply_path: Path) -> None:
        """Copy mesh PLY to dense/fused.ply for geospatial and final_results compatibility."""
        self._dense_path.mkdir(parents=True, exist_ok=True)
        fused = self._dense_path / "fused.ply"
        shutil.copy2(ply_path, fused)
        _get_logger(self.context).info("Copied %s -> %s for dense stage compatibility", ply_path, fused)

    def run_dense_pipeline(self) -> None:
        """
        Run full OpenMVS dense pipeline and write dense/fused.ply for backward compatibility.
        """
        logger = _get_logger(self.context)
        logger.info("OpenMVS dense pipeline starting (quality=%s, mvs_dir=%s)", self._quality, self._mvs_dir)

        scene_mvs = self.convert_from_colmap()
        scene_dense_mvs = self.densify_point_cloud(scene_mvs)
        scene_mesh_ply = self.reconstruct_mesh(scene_dense_mvs)

        mesh_ply = scene_mesh_ply
        scene_mesh_mvs = None
        refine_mvs = self.refine_mesh(scene_dense_mvs, scene_mesh_ply)
        if refine_mvs is not None:
            scene_mesh_mvs = refine_mvs
            refine_ply = self._mvs_dir / "scene_mesh_refine.ply"
            mesh_ply = refine_ply if refine_ply.exists() else scene_mesh_ply

        if QUALITY_TEXTURE.get(self._quality, True):
            # TextureMesh needs scene .mvs that contains the mesh (refined or dense)
            scene_for_texture = scene_mesh_mvs if scene_mesh_mvs is not None else scene_dense_mvs
            self.texture_mesh(scene_for_texture, mesh_ply)

        self._copy_to_dense_fused(mesh_ply)
        logger.info("OpenMVS dense pipeline finished. Output: %s", self._mvs_dir)
