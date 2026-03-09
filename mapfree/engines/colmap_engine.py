"""
COLMAP engine: runs colmap via subprocess wrapper.
Pipeline never calls COLMAP directly — only through this engine.
Uses mapfree.utils.colmap_finder.find_colmap_executable() for discovery.
"""
import logging
import os
import shutil
import sys
from pathlib import Path

from mapfree.core.engine import BaseEngine
from mapfree.core.exceptions import DependencyMissingError, EngineError
from mapfree.core.wrapper import EngineExecutionError, run_command
from mapfree.core.config import IMAGE_EXTENSIONS
from mapfree.utils.exif_order import write_image_list_for_colmap
from mapfree.utils.colmap_finder import find_colmap_executable

log = logging.getLogger(__name__)

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


def resolve_colmap_executable() -> str:
    """
    Resolve COLMAP executable via find_colmap_executable().
    Returns absolute path. Raises DependencyMissingError if not found.
    """
    path = find_colmap_executable()
    if path:
        log.debug("COLMAP resolved: %s", path)
        return path
    env_set = bool(os.environ.get("MAPFREE_COLMAP", "").strip() or os.environ.get("MAPFREE_COLMAP_PATH", "").strip())
    if env_set:
        raise DependencyMissingError(
            "colmap",
            "MAPFREE_COLMAP/MAPFREE_COLMAP_PATH is set but path not found. "
            "See: https://colmap.github.io/install.html",
        )
    log.warning("COLMAP not found (env, config, registry, extra dirs, PATH)")
    raise DependencyMissingError(
        "colmap",
        "Konfigurasi MAPFREE_COLMAP atau colmap_path di Settings. "
        "Install: https://colmap.github.io/install.html atau scripts/install_colmap_windows.md",
    )


def get_colmap_bin() -> str:
    """Return absolute path to COLMAP executable. Raises RuntimeError if not found."""
    return resolve_colmap_executable()


def verify_colmap_installation() -> bool:
    """
    Run COLMAP -h and return True if it succeeds.
    Use at GUI startup to warn if COLMAP is not configured.
    On Windows, .bat is run via cmd /c so shell=False works.
    """
    try:
        colmap_bin = resolve_colmap_executable()
    except RuntimeError:
        return False
    try:
        import subprocess
        cmd = [colmap_bin, "-h"]
        if sys.platform == "win32" and colmap_bin.lower().endswith(".bat"):
            cmd = ["cmd", "/c", colmap_bin, "-h"]
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(
            cmd,
            capture_output=True,
            timeout=15,
            shell=False,
            creationflags=creationflags,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_colmap_version() -> tuple[int, int]:
    """
    Return (major, minor) from `colmap --version` (e.g. (3, 9)).
    Use for version-aware argument building. On parse failure returns (0, 0).
    """
    import re
    import subprocess
    try:
        bin_path = resolve_colmap_executable()
        cmd = [bin_path, "--version"]
        if sys.platform == "win32" and bin_path.lower().endswith(".bat"):
            cmd = ["cmd", "/c", bin_path, "--version"]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creationflags,
        )
        if out.returncode != 0:
            return (0, 0)
        # e.g. "COLMAP 3.9.1 - Structure-from-Motion..."
        m = re.search(r"COLMAP\s+(\d+)\.(\d+)", (out.stdout or out.stderr or ""))
        if m:
            return (int(m.group(1)), int(m.group(2)))
    except Exception:
        pass
    return (0, 0)


def _get_cfg():
    from mapfree.core.config import get_config
    return get_config()


def _profile(ctx, key, default):
    p = getattr(ctx, "profile", None) or {}
    return p.get(key, default)


def _run_stage(ctx, command, stage_name, timeout=3600):
    workspace = Path(ctx.project_path).resolve()
    logger = getattr(ctx, "logger", None)
    bus = getattr(ctx, "event_bus", None)

    # Ensure every argument is str (paths with spaces safe when passed as list to subprocess)
    command = [str(x) for x in command]
    # Windows: .bat must be run via cmd /c (shell=False)
    if sys.platform == "win32" and command and command[0].lower().endswith(".bat"):
        command = ["cmd", "/c", command[0]] + command[1:]

    log.info("COLMAP executable: %s", command[0] if command else "—")
    log.info("COLMAP command: %s", " ".join(command))

    if bus is not None:
        bus.emit("engine_stage_started", {"engine": "colmap", "stage": stage_name})

    def on_line(line: str) -> None:
        if bus is not None:
            bus.emit("engine_log", {"engine": "colmap", "message": line})

    def heartbeat() -> None:
        if bus is not None:
            bus.emit("engine_log", {"engine": "colmap", "message": "[heartbeat] %s running…" % stage_name})

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
            heartbeat_callback=heartbeat,
        )
    except EngineExecutionError as e:
        stage_log = workspace / "logs" / f"{stage_name}.log"
        if stage_log.exists():
            try:
                with open(stage_log, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                tail = lines[-100:] if len(lines) > 100 else lines
                log.error(
                    "COLMAP %s failed. Last lines of %s:\n%s",
                    stage_name,
                    stage_log,
                    "".join(tail).strip() or "(empty)",
                )
            except OSError:
                log.warning("Could not read COLMAP log: %s", stage_log)
        if bus is not None:
            bus.emit("engine_stage_completed", {"engine": "colmap", "stage": stage_name})
        raise EngineError("COLMAP", str(e), returncode=getattr(e, "returncode", -1)) from e
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


def find_best_sparse_model(sparse_dir: Path) -> Path:
    """
    Return the subfolder of sparse_dir whose points3D.bin is largest (most 3D points).

    COLMAP mapper may produce multiple models (0, 1, 2, …); the largest by
    points3D.bin file size contains the most registered images and should be
    used for dense reconstruction. Falls back to sparse_dir/0 when no valid
    subfolder is found.
    """
    sparse_dir = Path(sparse_dir)
    best: Path | None = None
    best_size = -1
    try:
        for sub in sorted(sparse_dir.iterdir()):
            if not sub.is_dir():
                continue
            pts = sub / "points3D.bin"
            if pts.exists() and pts.stat().st_size > best_size:
                best_size = pts.stat().st_size
                best = sub
    except OSError:
        pass
    if best is not None:
        log.info("find_best_sparse_model: selected %s (points3D.bin %d bytes)", best, best_size)
        return best
    fallback = sparse_dir / "0"
    log.debug("find_best_sparse_model: no valid model found under %s, falling back to %s", sparse_dir, fallback)
    return fallback


def _emit_sparse_checkpoint(ctx, sparse_dir: Path) -> None:
    """Emit 'sparse_checkpoint' event with the points3D.bin path of the best model."""
    bus = getattr(ctx, "event_bus", None)
    if bus is None:
        return
    best = find_best_sparse_model(sparse_dir)
    candidates = [
        best / "points3D.bin",
        sparse_dir / "points3D.bin",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            bus.emit("sparse_checkpoint", {"path": str(candidate)})
            return


def _count_images(image_dir: Path) -> int:
    """Return number of image files in directory (by extension)."""
    if not image_dir.is_dir():
        return 0
    return sum(
        1 for p in image_dir.iterdir()
        if p.is_file() and p.suffix in IMAGE_EXTENSIONS
    )


class ColmapEngine(BaseEngine):
    def feature_extraction(self, ctx):
        from mapfree.utils.hardware import get_hardware_profile
        image_dir = Path(ctx.image_path).resolve()
        database_path = Path(ctx.database_path).resolve()
        project_path = Path(ctx.project_path).resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)

        if not image_dir.is_dir():
            raise EngineError(
                "COLMAP",
                "image_path is not a directory or does not exist: %s" % image_dir,
            )
        n_images = _count_images(image_dir)
        if n_images == 0:
            raise EngineError(
                "COLMAP",
                "No image files found in %s (extensions: %s)" % (image_dir, IMAGE_EXTENSIONS),
            )
        if not database_path.parent.exists():
            raise EngineError(
                "COLMAP",
                "database_path parent directory does not exist: %s" % database_path.parent,
            )

        use_gpu = _profile(ctx, "use_gpu", 1)
        if get_hardware_profile().vram_mb < 1000:
            use_gpu = 0
        list_output = project_path / "image_list.txt"
        list_path = write_image_list_for_colmap(
            image_dir,
            list_output,
            IMAGE_EXTENSIONS,
        )
        if list_path is None:
            raise EngineError(
                "COLMAP",
                "Could not create image list for %s (no images or write failed)" % image_dir,
            )

        # Exact args from verified manual test (no extra options)
        cmd = [
            str(get_colmap_bin()), "feature_extractor",
            "--database_path", str(database_path),
            "--image_path", str(image_dir),
            "--ImageReader.single_camera", "1",
            "--ImageReader.camera_model", "OPENCV",
            "--SiftExtraction.max_num_features", "4096",
            "--FeatureExtraction.use_gpu", str(int(use_gpu)),
            "--FeatureExtraction.num_threads", "-1",
            "--image_list_path", str(list_path.resolve()),
        ]
        log.info(
            "COLMAP feature_extractor: image_path=%s database_path=%s n_images=%d",
            image_dir, database_path, n_images,
        )
        _run_stage(ctx, cmd, "feature_extraction")

    def matching(self, ctx):
        from mapfree.utils.hardware import get_hardware_profile
        db = Path(ctx.database_path).resolve()
        db.parent.mkdir(parents=True, exist_ok=True)
        if not db.is_file():
            raise EngineError(
                "COLMAP",
                "Database not found after feature extraction: %s" % db,
            )
        matcher = _profile(ctx, "matcher", "spatial")
        vram_mb = get_hardware_profile().vram_mb
        use_gpu = _profile(ctx, "use_gpu", 1)
        if vram_mb < 1000:
            use_gpu = 0
        log.info("GPU mode: use_gpu=%s, VRAM=%sMB", use_gpu, vram_mb)
        # COLMAP 3.8+ uses SiftMatching.use_gpu (FeatureMatching.* removed)
        cmd_names = {
            "sequential": "sequential_matcher",
            "exhaustive": "exhaustive_matcher",
            "spatial": "spatial_matcher",
            "vocab_tree": "vocab_tree_matcher",
        }
        cmd_name = cmd_names.get(matcher, "spatial_matcher")
        colmap_exe = str(get_colmap_bin())
        cmd = [
            colmap_exe, cmd_name,
            "--database_path", str(db),
            "--FeatureMatching.use_gpu", str(int(use_gpu)),
            "--FeatureMatching.num_threads", "-1",
        ]
        if cmd_name == "spatial_matcher":
            cmd.extend(["--SpatialMatching.max_num_neighbors", "50"])
        _run_stage(ctx, cmd, "matching")

    def sparse(self, ctx):
        cfg = _get_cfg()
        colmap_cfg = cfg.get("colmap") or {}
        ba_global = int(colmap_cfg.get("mapper_ba_global_max_iter", 50))
        ba_local = int(colmap_cfg.get("mapper_ba_local_max_iter", 25))
        db = Path(ctx.database_path).resolve()
        img_path = Path(ctx.image_path).resolve()
        out_sparse = Path(ctx.sparse_path).resolve()
        if not db.is_file():
            raise EngineError(
                "COLMAP",
                "Database not found for mapper: %s (run feature_extraction and matching first)" % db,
            )
        if not img_path.is_dir():
            raise EngineError(
                "COLMAP",
                "Image path for mapper is not a directory: %s" % img_path,
            )
        out_sparse.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(get_colmap_bin()), "mapper",
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
        # Emit sparse_checkpoint so live-preview can reload the point cloud
        _emit_sparse_checkpoint(ctx, out_sparse)

    def point_filtering(self, ctx):
        """Filter sparse points by reprojection error and track length."""
        sparse_root = Path(ctx.sparse_path).resolve()
        # If ctx.sparse_path is already a model subfolder (e.g. .../01_sparse/0), use parent
        if sparse_root.name in ("0", "1", "2") and (sparse_root / "cameras.bin").exists():
            sparse_root = sparse_root.parent
        best = find_best_sparse_model(sparse_root)
        sparse_dir = best if (best / "cameras.bin").exists() else sparse_root / "0"
        parent = sparse_dir.parent
        out_reproj = parent / "0_filtered"
        out_reproj.mkdir(parents=True, exist_ok=True)
        cmd_reproj = [
            str(get_colmap_bin()), "point_filtering",
            "--input_path", str(sparse_dir),
            "--output_path", str(out_reproj),
            "--PointFiltering.filter_type", "reprojection_error",
            "--PointFiltering.max_reprojection_error", "1.5",
        ]
        _run_stage(ctx, cmd_reproj, "point_filtering_reproj")
        out_track = parent / "0_filtered2"
        out_track.mkdir(parents=True, exist_ok=True)
        cmd_track = [
            str(get_colmap_bin()), "point_filtering",
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
        # image_undistorter --image_path must be original photo folder (ctx.image_dir),
        # not project output/images, so COLMAP finds the same images as in the sparse DB
        image_dir_raw = getattr(ctx, "image_dir", None) or getattr(ctx, "image_path", None)
        if not image_dir_raw:
            raise EngineError(
                "COLMAP",
                "Dense: ctx.image_dir / image_path not set (folder foto asli).",
            )
        image_dir = Path(image_dir_raw).resolve()
        if not image_dir.exists():
            raise EngineError(
                "COLMAP",
                "Folder foto tidak ditemukan: %s" % image_dir,
            )
        output_dir = Path(ctx.project_path).resolve()
        # Prefer sparse_merged (post-merge), then sparse; always pick largest model
        sparse_root = output_dir / "sparse_merged"
        if not sparse_root.exists() or not any(sparse_root.iterdir()):
            sparse_root = output_dir / "sparse"
        if not sparse_root.exists() or not any(sparse_root.iterdir()):
            sparse_root = Path(ctx.sparse_path).resolve()
        # Ensure we pass the dir that contains 0, 1, 2... not a model subfolder (avoid .../0/0)
        if sparse_root.name in ("0", "1", "2") and (sparse_root / "cameras.bin").exists():
            sparse_root = sparse_root.parent
        sparse_input = find_best_sparse_model(sparse_root)
        if not (sparse_input / "cameras.bin").exists():
            raise EngineError(
                "COLMAP",
                "Sparse model tidak ditemukan: %s" % sparse_input,
            )
        log.info("Dense image_path: %s", image_dir)
        log.info("Dense sparse_input: %s", sparse_input)
        dense_dir = Path(ctx.dense_path).resolve()
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

        # Metashape-style quality: resolution and photo count limit for dense (avoids Not Responding on large models).
        quality = str(_profile(ctx, "quality", "medium")).lower()
        downscale = _profile(ctx, "downscale", 1)
        base_size = 3200 if patch_match_max_size == -1 else patch_match_max_size
        patch_match_max_size = max(256, base_size // downscale)
        undistorter_max_size = patch_match_max_size
        geom_consistency = "1"
        fusion_min_num_pixels = "5"
        num_iterations = 5  # default; overridden for low
        if quality == "low":
            undistorter_max_size = min(undistorter_max_size, 800)
            patch_match_max_size = 800
            geom_consistency = "0"
            fusion_min_num_pixels = "3"
            num_samples = 7
            num_iterations = 3
        # medium/high: num_samples and num_iterations from VRAM block above
        # Note: COLMAP image_undistorter has no --max_num_images; limit via max_image_size only.

        _run_stage(ctx, [
            str(get_colmap_bin()), "image_undistorter",
            "--image_path", str(image_dir),
            "--input_path", str(sparse_input),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP",
            "--max_image_size", str(undistorter_max_size),
        ], "dense")

        _run_stage(ctx, [
            str(get_colmap_bin()), "patch_match_stereo",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.gpu_index", gpu_idx,
            "--PatchMatchStereo.max_image_size", str(patch_match_max_size),
            "--PatchMatchStereo.cache_size", str(cache_size),
            "--PatchMatchStereo.window_step", "1",
            "--PatchMatchStereo.geom_consistency", geom_consistency,
            "--PatchMatchStereo.num_iterations", str(num_iterations),
            "--PatchMatchStereo.num_samples", str(num_samples),
        ], "dense")

        # When geom_consistency=0, patch_match only writes photometric depth;
        # stereo_fusion must use the same input_type or it finds no inputs → 0 points.
        fusion_input_type = "geometric" if geom_consistency == "1" else "photometric"
        _run_stage(ctx, [
            str(get_colmap_bin()), "stereo_fusion",
            "--workspace_path", str(dense_dir),
            "--workspace_format", "COLMAP",
            "--input_type", fusion_input_type,
            "--output_path", str(dense_dir / "fused.ply"),
            "--StereoFusion.max_image_size", str(patch_match_max_size),
            "--StereoFusion.check_num_images", "3",
            "--StereoFusion.min_num_pixels", fusion_min_num_pixels,
        ], "dense")
