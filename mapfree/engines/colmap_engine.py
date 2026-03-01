"""
COLMAP engine: runs colmap via subprocess wrapper.
Pipeline never calls COLMAP directly — only through this engine.
Colmap binary: MAPFREE_COLMAP_BIN env, or config colmap.colmap_bin, else PATH, else venv fallback.
"""
import os
import shutil
from pathlib import Path

from mapfree.core.engine import BaseEngine
from mapfree.core.wrapper import EngineExecutionError, run_command
from mapfree.core.config import IMAGE_EXTENSIONS
from mapfree.utils.exif_order import write_image_list_for_colmap

os.environ.setdefault("OMP_NUM_THREADS", "4")

# DJI sensor width (mm) for focal length in pixels: focal_px = (width_px * focal_mm) / sensor_mm
DJI_SENSOR_WIDTH_MM = {
    "FC6310": 13.2,
    "FC220": 6.3,
    "FC3170": 6.4,   # Mavic Air 2
    "FC3582": 9.6,
    "FC2403": 13.2,
    "DEFAULT_DJI": 6.3,
}

# Absolute path fallback when PATH is not passed to subprocess (avoids "No such file or directory").
COLMAP_VENV_BIN = "/media/pop_mangto/E/dev/MapFree/venv/bin/colmap"


def _get_cfg():
    from mapfree.core.config import get_config
    return get_config()


def get_colmap_bin() -> str:
    """Resolve colmap executable: env MAPFREE_COLMAP_BIN > config colmap.colmap_bin > which colmap > venv fallback > 'colmap'."""
    env_bin = os.environ.get("MAPFREE_COLMAP_BIN", "").strip()
    if env_bin:
        return os.path.abspath(env_bin) if os.path.sep in env_bin else env_bin
    cfg = _get_cfg()
    cfg_bin = (cfg.get("colmap") or {}).get("colmap_bin")
    if cfg_bin:
        p = str(cfg_bin).strip()
        return os.path.abspath(p) if os.path.sep in p else p
    found = shutil.which("colmap")
    if found and os.path.sep in found:
        return os.path.abspath(found)
    if os.path.isfile(COLMAP_VENV_BIN) and os.access(COLMAP_VENV_BIN, os.X_OK):
        return COLMAP_VENV_BIN
    return found or "colmap"


def _profile(ctx, key, default):
    p = getattr(ctx, "profile", None) or {}
    return p.get(key, default)


def _run_stage(ctx, command, stage_name, timeout=3600):
    workspace = Path(ctx.project_path)
    logger = getattr(ctx, "logger", None)
    bus = getattr(ctx, "event_bus", None)

    if bus is not None:
        bus.emit("engine_stage_started", {"engine": "colmap", "stage": stage_name})

    def on_line(line: str) -> None:
        if bus is not None:
            bus.emit("engine_log", {"engine": "colmap", "message": line})

    stop_event = getattr(ctx, "stop_event", None)
    try:
        run_command(
            command,
            workspace=workspace,
            stage_name=stage_name,
            timeout=timeout,
            retry=2,
            cwd=workspace,
            logger=logger,
            line_callback=on_line,
            stop_event=stop_event,
        )
    except EngineExecutionError as e:
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "colmap", "stage": stage_name})
        raise RuntimeError(f"Engine failed: {e}") from e
    if bus is not None:
        bus.emit("engine_stage_completed", {"engine": "colmap", "stage": stage_name})


def _get_dji_opencv_params(image_path: Path) -> str | None:
    """
    If the first image has DJI EXIF, return OPENCV camera params string:
    fx,fy,cx,cy,k1,k2,p1,p2 (focal in pixels, principal point, distortion zeros).
    Otherwise return None.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    img_path = Path(image_path)
    if not img_path.is_dir():
        return None
    first = None
    for p in sorted(img_path.iterdir()):
        if p.is_file() and p.suffix in IMAGE_EXTENSIONS:
            first = p
            break
    if not first or not first.is_file():
        return None
    try:
        with Image.open(first) as im:
            exif = im.getexif() if hasattr(im, "getexif") else None
            if not exif:
                return None
            make = (exif.get(271) or "").strip().upper()
            if "DJI" not in make:
                return None
            model = (exif.get(272) or "").strip()
            lens = (exif.get(42036) or "").strip()  # LensModel
            width_px = im.width
            height_px = im.height
            focal_mm = exif.get(33434)  # EXIF FocalLength (rational, mm)
            if focal_mm is None:
                return None
            if hasattr(focal_mm, "numerator") and getattr(focal_mm, "denominator", 1):
                focal_mm = float(focal_mm.numerator) / float(focal_mm.denominator or 1)
            else:
                focal_mm = float(focal_mm)
    except Exception:
        return None
    sensor_mm = DJI_SENSOR_WIDTH_MM.get("DEFAULT_DJI", 6.3)
    for code in DJI_SENSOR_WIDTH_MM:
        if code == "DEFAULT_DJI":
            continue
        if code in model or code in lens:
            sensor_mm = DJI_SENSOR_WIDTH_MM[code]
            break
    focal_px = (width_px * focal_mm) / sensor_mm
    cx = width_px / 2.0
    cy = height_px / 2.0
    return f"{focal_px},{focal_px},{cx},{cy},0,0,0,0"


class ColmapEngine(BaseEngine):
    def feature_extraction(self, ctx):
        from mapfree.utils.hardware import get_hardware_profile
        db = Path(ctx.database_path)
        img_path = Path(ctx.image_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        # Use profile values; on low VRAM (<2.5GB) avoid GPU OOM: use CPU + cap size
        vram_mb = get_hardware_profile().vram_mb
        low_vram = vram_mb < 2500
        max_size = _profile(ctx, "max_image_size", 2000)
        max_features = _profile(ctx, "max_features", 8192)
        use_gpu = _profile(ctx, "use_gpu", 1)
        if low_vram:
            max_size = min(max_size, 1600)
            use_gpu = 0  # SIFT GPU OOM on 2GB; use CPU for feature extraction
        # Metashape-style quality: apply downscale to feature extraction
        downscale = _profile(ctx, "downscale", 1)
        max_size = max(256, max_size // downscale)
        cfg = _get_cfg()
        colmap_cfg = cfg.get("colmap") or {}
        num_threads = colmap_cfg.get("num_threads", -1)
        # Order images by EXIF: GPS (lat, lon) then datetime for sequential matcher
        list_path = write_image_list_for_colmap(
            img_path,
            Path(ctx.project_path) / "image_list.txt",
            IMAGE_EXTENSIONS,
        )
        cmd = [
            get_colmap_bin(), "feature_extractor",
            "--database_path", str(db),
            "--image_path", str(img_path),
            "--ImageReader.single_camera", "1",
            "--ImageReader.camera_model", "OPENCV",
            "--FeatureExtraction.max_image_size", str(max_size),
            "--FeatureExtraction.num_threads", str(num_threads),
            "--SiftExtraction.max_num_features", str(max_features),
            "--FeatureExtraction.use_gpu", str(1 if use_gpu else 0),
        ]
        if list_path is not None:
            cmd.extend(["--image_list_path", str(list_path)])
        dji_params = _get_dji_opencv_params(img_path)
        if dji_params is not None:
            cmd.extend(["--ImageReader.camera_params", dji_params])
        _run_stage(ctx, cmd, "feature_extraction")

    def matching(self, ctx):
        from mapfree.utils.hardware import get_hardware_profile
        db = Path(ctx.database_path)
        matcher = _profile(ctx, "matcher", "exhaustive")
        use_gpu = _profile(ctx, "use_gpu", 1)
        if get_hardware_profile().vram_mb < 2500:
            use_gpu = 0  # avoid GPU OOM on 2GB during matching
        cmd_name = "sequential_matcher" if matcher == "sequential" else "exhaustive_matcher"
        cmd = [
            get_colmap_bin(), cmd_name,
            "--database_path", str(db),
            "--FeatureMatching.use_gpu", str(1 if use_gpu else 0),
        ]
        _run_stage(ctx, cmd, "matching")

    def sparse(self, ctx):
        cfg = _get_cfg()
        colmap_cfg = cfg.get("colmap") or {}
        ba_global = int(colmap_cfg.get("mapper_ba_global_max_iter", 50))
        ba_local = int(colmap_cfg.get("mapper_ba_local_max_iter", 25))
        db = Path(ctx.database_path)
        img_path = Path(ctx.image_path)
        out_sparse = Path(ctx.sparse_path)
        out_sparse.mkdir(parents=True, exist_ok=True)
        cmd = [
            get_colmap_bin(), "mapper",
            "--database_path", str(db),
            "--image_path", str(img_path),
            "--output_path", str(out_sparse),
            "--Mapper.ba_global_max_num_iterations", str(ba_global),
            "--Mapper.ba_local_max_num_iterations", str(ba_local),
            "--Mapper.ba_refine_focal_length", "1",
            "--Mapper.ba_refine_extra_params", "1",
            "--Mapper.ba_refine_principal_point", "1",
        ]
        _run_stage(ctx, cmd, "sparse")

    def point_filtering(self, ctx):
        """Filter sparse points by reprojection error and track length."""
        sparse_dir = Path(ctx.sparse_path)
        if (sparse_dir / "0" / "cameras.bin").exists():
            sparse_dir = sparse_dir / "0"
        parent = sparse_dir.parent
        out_reproj = parent / "0_filtered"
        out_reproj.mkdir(parents=True, exist_ok=True)
        cmd_reproj = [
            get_colmap_bin(), "point_filtering",
            "--input_path", str(sparse_dir),
            "--output_path", str(out_reproj),
            "--PointFiltering.filter_type", "reprojection_error",
            "--PointFiltering.max_reprojection_error", "1.5",
        ]
        _run_stage(ctx, cmd_reproj, "point_filtering_reproj")
        out_track = parent / "0_filtered2"
        out_track.mkdir(parents=True, exist_ok=True)
        cmd_track = [
            get_colmap_bin(), "point_filtering",
            "--input_path", str(out_reproj),
            "--output_path", str(out_track),
            "--PointFiltering.filter_type", "track_length",
            "--PointFiltering.min_track_length", "3",
        ]
        _run_stage(ctx, cmd_track, "point_filtering_track")
        for f in ("cameras.bin", "images.bin", "points3D.bin"):
            src = out_track / f
            if src.exists():
                shutil.copy2(src, sparse_dir / f)
        shutil.rmtree(out_reproj, ignore_errors=True)
        shutil.rmtree(out_track, ignore_errors=True)

    def dense(self, ctx, vram_watchdog=False):
        from mapfree.utils.hardware import get_hardware_profile
        sparse_dir = Path(ctx.sparse_path)
        if (sparse_dir / "0" / "cameras.bin").exists():
            sparse_dir = sparse_dir / "0"
        img_path = Path(ctx.image_path)
        dense_dir = Path(ctx.dense_path)
        dense_dir.mkdir(parents=True, exist_ok=True)
        use_gpu = _profile(ctx, "use_gpu", 1)
        gpu_idx = "0" if use_gpu else "-1"
        # Smart scaling by VRAM: <2.5GB -> 1600, <4.5GB -> 2500, >=6GB -> full (-1)
        vram_gb = get_hardware_profile().vram_gb
        if vram_gb < 2.5:
            patch_match_max_size = 1600
            cache_size = 1
            num_samples = 10
        elif vram_gb < 4.5:
            patch_match_max_size = 2500
            cache_size = 1
            num_samples = 10
        else:
            patch_match_max_size = -1
            cache_size = 8
            num_samples = 15

        # Metashape-style quality: apply downscale to dense
        downscale = _profile(ctx, "downscale", 1)
        base_size = 3200 if patch_match_max_size == -1 else patch_match_max_size
        patch_match_max_size = max(256, base_size // downscale)

        _run_stage(ctx, [
            get_colmap_bin(), "image_undistorter",
            "--image_path", str(img_path),
            "--input_path", str(sparse_dir),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP",
        ], "dense")

        _run_stage(ctx, [
            get_colmap_bin(), "patch_match_stereo",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.gpu_index", gpu_idx,
            "--PatchMatchStereo.max_image_size", str(patch_match_max_size),
            "--PatchMatchStereo.cache_size", str(cache_size),
            "--PatchMatchStereo.window_step", "1",
            "--PatchMatchStereo.geom_consistency", "1",
            "--PatchMatchStereo.num_iterations", "5",
            "--PatchMatchStereo.num_samples", str(num_samples),
        ], "dense")

        _run_stage(ctx, [
            get_colmap_bin(), "stereo_fusion",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", str(dense_dir / "fused.ply"),
            "--StereoFusion.max_image_size", str(patch_match_max_size),
            "--StereoFusion.check_num_images", "3",
        ], "dense")
