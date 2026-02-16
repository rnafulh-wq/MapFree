"""
COLMAP engine: runs colmap via subprocess wrapper.
Pipeline never calls COLMAP directly — only through this engine.
"""
import os
from pathlib import Path

from mapfree.core.engine import BaseEngine
from mapfree.core.wrapper import EngineExecutionError, run_command

os.environ.setdefault("OMP_NUM_THREADS", "4")


def _get_cfg():
    from mapfree.config import get_config
    return get_config()


def _profile(ctx, key, default):
    p = getattr(ctx, "profile", None) or {}
    return p.get(key, default)


def _run_stage(ctx, command, stage_name, timeout=3600):
    workspace = Path(ctx.project_path)
    try:
        run_command(
            command,
            workspace=workspace,
            stage_name=stage_name,
            timeout=timeout,
            retry=2,
            cwd=workspace,
        )
    except EngineExecutionError as e:
        raise RuntimeError(f"Engine failed: {e}") from e


class ColmapEngine(BaseEngine):
    def feature_extraction(self, ctx):
        db = Path(ctx.database_path)
        img_path = Path(ctx.image_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        max_size = min(_profile(ctx, "max_image_size", 2000), 1600)
        max_features = min(_profile(ctx, "max_features", 8192), 8000)
        use_gpu = _profile(ctx, "use_gpu", 1)
        cmd = [
            "colmap", "feature_extractor",
            "--database_path", str(db),
            "--image_path", str(img_path),
            "--ImageReader.single_camera", "1",
            "--ImageReader.camera_model", "OPENCV",
            "--SiftExtraction.max_image_size", str(max_size),
            "--SiftExtraction.max_num_features", str(max_features),
            "--SiftExtraction.use_gpu", str(1 if use_gpu else 0),
        ]
        _run_stage(ctx, cmd, "feature_extraction")

    def matching(self, ctx):
        db = Path(ctx.database_path)
        matcher = _profile(ctx, "matcher", "exhaustive")
        use_gpu = _profile(ctx, "use_gpu", 1)
        cmd_name = "sequential_matcher" if matcher == "sequential" else "exhaustive_matcher"
        cmd = [
            "colmap", cmd_name,
            "--database_path", str(db),
            "--SiftMatching.use_gpu", str(1 if use_gpu else 0),
        ]
        _run_stage(ctx, cmd, "matching")

    def sparse(self, ctx):
        cfg = _get_cfg()
        colmap_cfg = cfg.get("colmap") or {}
        ba_global = int(colmap_cfg.get("mapper_ba_global_max_iter", 30))
        ba_local = int(colmap_cfg.get("mapper_ba_local_max_iter", 20))
        db = Path(ctx.database_path)
        img_path = Path(ctx.image_path)
        out_sparse = Path(ctx.sparse_path)
        out_sparse.mkdir(parents=True, exist_ok=True)
        cmd = [
            "colmap", "mapper",
            "--database_path", str(db),
            "--image_path", str(img_path),
            "--output_path", str(out_sparse),
            "--Mapper.ba_global_max_num_iterations", str(ba_global),
            "--Mapper.ba_local_max_num_iterations", str(ba_local),
        ]
        _run_stage(ctx, cmd, "sparse")

    def dense(self, ctx, vram_watchdog=False):
        sparse_dir = Path(ctx.sparse_path)
        if (sparse_dir / "0" / "cameras.bin").exists():
            sparse_dir = sparse_dir / "0"
        img_path = Path(ctx.image_path)
        dense_dir = Path(ctx.dense_path)
        dense_dir.mkdir(parents=True, exist_ok=True)
        max_size = min(_profile(ctx, "max_image_size", 800), 1600)
        use_gpu = _profile(ctx, "use_gpu", 1)
        gpu_idx = "0" if use_gpu else "-1"

        _run_stage(ctx, [
            "colmap", "image_undistorter",
            "--image_path", str(img_path),
            "--input_path", str(sparse_dir),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP",
        ], "dense")

        _run_stage(ctx, [
            "colmap", "patch_match_stereo",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.gpu_index", gpu_idx,
            "--PatchMatchStereo.max_image_size", str(max_size),
            "--PatchMatchStereo.cache_size", "8",
            "--PatchMatchStereo.window_step", "2",
            "--PatchMatchStereo.geom_consistency", "0",
        ], "dense")

        _run_stage(ctx, [
            "colmap", "stereo_fusion",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", str(dense_dir / "fused.ply"),
            "--StereoFusion.max_image_size", str(max_size),
        ], "dense")
