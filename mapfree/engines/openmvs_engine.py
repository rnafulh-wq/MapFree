"""
OpenMVS engine: runs OpenMVS pipeline (InterfaceCOLMAP -> Densify -> Mesh -> Refine -> Texture).
Expects COLMAP dense output (or sparse + images). All paths derived from context.project_path.
"""
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

from mapfree.core.engine import BaseEngine
from mapfree.core.logger import get_logger
from mapfree.core.wrapper import run_process_streaming

# Default binary names (OpenMVS uses PascalCase on Linux/Windows)
OPENMVS_BINARIES = (
    "InterfaceCOLMAP",
    "DensifyPointCloud",
    "ReconstructMesh",
    "RefineMesh",
    "TextureMesh",
)


def _get_logger(context) -> logging.Logger:
    """Use context.logger if set, else module logger."""
    return getattr(context, "logger", None) or get_logger("openmvs")


def _resolve_binary(name: str) -> str:
    """Resolve OpenMVS executable: env MAPFREE_OPENMVS_BIN_DIR/name, else PATH."""
    bin_dir = os.environ.get("MAPFREE_OPENMVS_BIN_DIR", "").strip()
    if bin_dir:
        p = Path(bin_dir).resolve() / name
        if p.exists():
            return str(p)
    found = shutil.which(name)
    if found:
        return found
    return name


def _run_step(
    context,
    cmd: list,
    step_name: str,
    timeout: int = 7200,
) -> None:
    """Run subprocess with Popen streaming; emit engine_log and stage events via context.event_bus; raise RuntimeError if non-zero exit or timeout."""
    logger = _get_logger(context)
    logger.info("OpenMVS step: %s", step_name)
    bus = getattr(context, "event_bus", None)

    if bus is not None:
        bus.emit("engine_stage_started", {"engine": "openmvs", "stage": step_name})

    def on_line(line: str) -> None:
        if bus is not None:
            bus.emit("engine_log", {"engine": "openmvs", "message": line})

    stop_event = getattr(context, "stop_event", None)
    try:
        returncode = run_process_streaming(
            cmd,
            cwd=context.project_path,
            timeout=timeout,
            logger=logger,
            line_callback=on_line,
            stop_event=stop_event,
        )
        if returncode != 0:
            logger.error("OpenMVS step failed: %s (exit %s)", step_name, returncode)
            if bus is not None:
                bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
            raise RuntimeError(f"OpenMVS {step_name} failed with code {returncode}")
        logger.info("OpenMVS step completed: %s", step_name)
    except subprocess.TimeoutExpired:
        logger.error("OpenMVS step timed out: %s", step_name)
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
        raise RuntimeError(f"OpenMVS {step_name} timed out")
    except (OSError, ValueError) as e:
        logger.error("OpenMVS step error: %s — %s", step_name, e)
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})
        raise RuntimeError(f"OpenMVS {step_name} failed: {e}") from e
    if bus is not None:
        bus.emit("engine_stage_completed", {"engine": "openmvs", "stage": step_name})


class OpenMVSEngine(BaseEngine):
    """
    OpenMVS pipeline engine: import COLMAP scene, densify (resolution-level 2), mesh, refine, texture.
    All paths derived from context.project_path. Use run() to execute the full pipeline.
    BaseEngine methods (feature_extraction, matching, sparse, dense) are not used; call run() instead.
    """

    def __init__(self, context):
        self.context = context
        self._project_path = Path(context.project_path)
        self._openmvs_dir = self._project_path / "openmvs"
        self._sparse_path = Path(context.sparse_path)
        self._dense_path = Path(context.dense_path)
        self._image_path = Path(context.image_path)

    def feature_extraction(self, ctx):
        raise NotImplementedError("OpenMVSEngine uses run() only")

    def matching(self, ctx):
        raise NotImplementedError("OpenMVSEngine uses run() only")

    def sparse(self, ctx):
        raise NotImplementedError("OpenMVSEngine uses run() only")

    def dense(self, ctx, vram_watchdog=False):
        raise NotImplementedError("OpenMVSEngine uses run() only")

    def run(self) -> None:
        """
        Run full OpenMVS pipeline:
        1. Create openmvs directory
        2. InterfaceCOLMAP
        3. DensifyPointCloud (resolution-level 2)
        4. ReconstructMesh
        5. RefineMesh
        6. TextureMesh
        """
        logger = _get_logger(self.context)
        logger.info("OpenMVS pipeline starting (project_path=%s)", self._project_path)

        # 1. Create openmvs directory inside project path
        self._openmvs_dir.mkdir(parents=True, exist_ok=True)
        logger.info("OpenMVS step: create directory — %s", self._openmvs_dir)

        scene_mvs = self._openmvs_dir / "scene.mvs"
        scene_dense_mvs = self._openmvs_dir / "scene_dense.mvs"
        scene_mesh_ply = self._openmvs_dir / "scene_mesh.ply"
        scene_mesh_refine_mvs = self._openmvs_dir / "scene_mesh_refine.mvs"
        scene_textured_mvs = self._openmvs_dir / "scene_textured.mvs"

        # 2. InterfaceCOLMAP
        colmap_input, image_folder = self._colmap_input_and_images()
        interface_bin = _resolve_binary("InterfaceCOLMAP")
        _run_step(
            self.context,
            [
                interface_bin,
                "-i", str(colmap_input),
                "-o", str(scene_mvs),
                "--image-folder", str(image_folder),
            ],
            "InterfaceCOLMAP",
        )
        if not scene_mvs.exists():
            raise RuntimeError("InterfaceCOLMAP did not produce scene.mvs")

        # 3. DensifyPointCloud with resolution-level 2
        densify_bin = _resolve_binary("DensifyPointCloud")
        _run_step(
            self.context,
            [
                densify_bin,
                str(scene_mvs),
                "-o", str(scene_dense_mvs),
                "-w", "2",  # resolution-level 2
            ],
            "DensifyPointCloud",
        )
        if not scene_dense_mvs.exists():
            raise RuntimeError("DensifyPointCloud did not produce scene_dense.mvs")

        # 4. ReconstructMesh
        reconstruct_bin = _resolve_binary("ReconstructMesh")
        _run_step(
            self.context,
            [reconstruct_bin, str(scene_dense_mvs), "-p", str(scene_mesh_ply)],
            "ReconstructMesh",
        )
        if not scene_mesh_ply.exists():
            raise RuntimeError("ReconstructMesh did not produce scene_mesh.ply")

        # 5. RefineMesh (reads rough mesh, writes refined .mvs and often .ply with same stem)
        scene_mesh_refine_ply = self._openmvs_dir / "scene_mesh_refine.ply"
        refine_bin = _resolve_binary("RefineMesh")
        _run_step(
            self.context,
            [
                refine_bin,
                str(scene_dense_mvs),
                "-m", str(scene_mesh_ply),
                "-o", str(scene_mesh_refine_mvs),
            ],
            "RefineMesh",
        )
        if not scene_mesh_refine_mvs.exists():
            raise RuntimeError("RefineMesh did not produce scene_mesh_refine.mvs")
        mesh_for_texture = scene_mesh_refine_ply if scene_mesh_refine_ply.exists() else scene_mesh_ply

        # 6. TextureMesh (input scene .mvs + mesh .ply -> textured .mvs)
        texture_bin = _resolve_binary("TextureMesh")
        _run_step(
            self.context,
            [
                texture_bin,
                str(scene_mesh_refine_mvs),
                "-m", str(mesh_for_texture),
                "-o", str(scene_textured_mvs),
            ],
            "TextureMesh",
        )

        logger.info("OpenMVS pipeline finished. Output: %s", scene_textured_mvs)

    def _colmap_input_and_images(self) -> Tuple[Path, Path]:
        """
        Resolve COLMAP input folder and image folder for InterfaceCOLMAP.
        Prefer dense (undistorted) if present; else sparse + original images.
        """
        dense_images = self._dense_path / "images"
        if self._dense_path.exists() and dense_images.is_dir():
            return self._dense_path, dense_images
        sparse_0 = self._sparse_path / "0"
        sparse_dir = sparse_0 if sparse_0.exists() else self._sparse_path
        if not sparse_dir.exists():
            raise RuntimeError(
                "No COLMAP output found: dense path %s (with images/) or sparse path %s"
                % (self._dense_path, self._sparse_path)
            )
        return sparse_dir, self._image_path
