"""
COLMAP engine: runs colmap via subprocess. Uses profile for parameters.
Pipeline never calls COLMAP directly — only through this engine.
"""
import os
import subprocess
import time
from pathlib import Path

from mapfree.core.engine import BaseEngine, VramWatchdogError


def _get_cfg():
    from mapfree.config import get_config
    return get_config()


def _run(cmd, timeout=3600):
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "4")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode != 0:
        raise RuntimeError("COLMAP failed (exit %d): %s" % (r.returncode, r.stderr or r.stdout or ""))


def _run_with_vram_watchdog(cmd, threshold=None, poll_interval=None, timeout=3600):
    """Run cmd; if GPU VRAM usage > threshold, terminate and raise VramWatchdogError."""
    cfg = _get_cfg()
    vw = cfg.get("vram_watchdog") or {}
    if threshold is None:
        threshold = float(vw.get("threshold", 0.9))
    if poll_interval is None:
        poll_interval = int(vw.get("poll_interval", 5))
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "4")
    try:
        from mapfree.core import hardware
    except ImportError:
        hardware = None
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    deadline = time.monotonic() + timeout if timeout else None
    while True:
        if proc.poll() is not None:
            break
        if deadline is not None and time.monotonic() > deadline:
            proc.terminate()
            proc.wait(timeout=10)
            raise RuntimeError("COLMAP timed out")
        time.sleep(poll_interval)
        if hardware:
            used_mb, total_mb = hardware.get_gpu_vram_usage()
            if total_mb > 0 and (used_mb / total_mb) > threshold:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                raise VramWatchdogError("VRAM usage exceeded %.0f%%, process terminated" % (threshold * 100))
    if proc.returncode != 0:
        raise RuntimeError("COLMAP failed (exit %d): %s" % (proc.returncode, proc.stderr.read() if proc.stderr else ""))


def _profile(ctx, key, default):
    p = getattr(ctx, "profile", None) or {}
    return p.get(key, default)


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
        _run(cmd)

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
        _run(cmd)

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
        _run(cmd)

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
        use_watchdog = vram_watchdog and use_gpu
        run_dense_step = _run_with_vram_watchdog if use_watchdog else _run

        _run([
            "colmap", "image_undistorter",
            "--image_path", str(img_path),
            "--input_path", str(sparse_dir),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP",
        ])
        run_dense_step([
            "colmap", "patch_match_stereo",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.gpu_index", gpu_idx,
            "--PatchMatchStereo.max_image_size", str(max_size),
            "--PatchMatchStereo.cache_size", "8",
            "--PatchMatchStereo.window_step", "2",
            "--PatchMatchStereo.geom_consistency", "0",
        ])
        run_dense_step([
            "colmap", "stereo_fusion",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", str(dense_dir / "fused.ply"),
            "--StereoFusion.max_image_size", str(max_size),
        ])
