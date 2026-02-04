"""COLMAP CLI wrapper. Builds and runs COLMAP commands with config-driven parameters."""

import subprocess
from pathlib import Path

from .exceptions import ColmapError
from .logger import get_logger

logger = get_logger("colmap")


def run_colmap(cmd: list[str], dry_run: bool = False, num_threads: int = 4) -> None:
    """
    Execute a COLMAP command. Log the command; if dry_run, only log and return.
    Raises ColmapError on non-zero exit.
    """
    logger.info("COLMAP: %s", " ".join(cmd))
    if dry_run:
        return
    import os
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(num_threads)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise ColmapError(
            f"COLMAP failed (exit {result.returncode}): {result.stderr or result.stdout}"
        )
    if result.stdout:
        logger.debug("%s", result.stdout[:500])


def build_feature_extractor_args(project_path: Path, image_path: Path, config: dict) -> list[str]:
    """Build COLMAP feature_extractor command args (without 'colmap feature_extractor')."""
    project_path = Path(project_path)
    image_path = Path(image_path)
    db = project_path / "database.db"
    fe_cfg = config.get("feature_extractor", {})
    max_size = fe_cfg.get("max_image_size", 2000)
    gpu = fe_cfg.get("gpu_index", 0)
    args = [
        "colmap", "feature_extractor",
        "--database_path", str(db),
        "--image_path", str(image_path),
        "--ImageReader.single_camera", "0",
        "--ImageReader.camera_model", "OPENCV",
        "--SiftExtraction.max_image_size", str(max_size),
        "--SiftExtraction.gpu_index", str(gpu),
    ]
    return args


def build_matcher_args(project_path: Path, config: dict) -> list[str]:
    """Build COLMAP matcher command args. Uses spatial or sequential from config."""
    project_path = Path(project_path)
    db = project_path / "database.db"
    matcher_cfg = config.get("matcher", {})
    match_type = matcher_cfg.get("type", "spatial")
    gpu = matcher_cfg.get("gpu_index", 0)
    cmd = "sequential_matcher" if match_type == "sequential" else "spatial_matcher"
    args = ["colmap", cmd, "--database_path", str(db), "--SiftMatching.gpu_index", str(gpu)]
    return args


def build_mapper_args(project_path: Path, config: dict) -> list[str]:
    """Build COLMAP mapper command args."""
    project_path = Path(project_path)
    db = project_path / "database.db"
    sparse = project_path / "sparse"
    mapper_cfg = config.get("mapper", {})
    ba_iter = mapper_cfg.get("ba_global_max_iterations", 50)
    ba_refine = mapper_cfg.get("ba_global_max_refinements", 5)
    args = [
        "colmap", "mapper",
        "--database_path", str(db),
        "--image_path", str(project_path / "images"),  # mapper expects images in project
        "--output_path", str(sparse),
        "--Mapper.ba_global_max_num_iterations", str(ba_iter),
        "--Mapper.ba_global_max_refinements", str(ba_refine),
    ]
    return args


def build_image_undistorter_args(project_path: Path) -> list[str]:
    """Build COLMAP image_undistorter command args."""
    project_path = Path(project_path)
    sparse0 = project_path / "sparse" / "0"
    image_path = project_path / "images"
    dense = project_path / "dense"
    args = [
        "colmap", "image_undistorter",
        "--image_path", str(image_path),
        "--input_path", str(sparse0),
        "--output_path", str(dense),
        "--output_type", "COLMAP",
    ]
    return args


def build_patch_match_stereo_args(project_path: Path, config: dict) -> list[str]:
    """Build COLMAP patch_match_stereo command args."""
    project_path = Path(project_path)
    dense = project_path / "dense"
    pm_cfg = config.get("patch_match_stereo", {})
    max_size = pm_cfg.get("max_image_size", 1600)
    gpu = pm_cfg.get("gpu_index", 0)
    args = [
        "colmap", "patch_match_stereo",
        "--workspace_path", str(dense),
        "--workspace_format", "COLMAP",
        "--PatchMatchStereo.max_image_size", str(max_size),
        "--PatchMatchStereo.gpu_index", str(gpu),
    ]
    return args


def build_stereo_fusion_args(project_path: Path) -> list[str]:
    """Build COLMAP stereo_fusion command args (merge depth maps into dense point cloud)."""
    project_path = Path(project_path)
    dense = project_path / "dense"
    args = [
        "colmap", "stereo_fusion",
        "--workspace_path", str(dense),
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", str(dense / "fused.ply"),
    ]
    return args
