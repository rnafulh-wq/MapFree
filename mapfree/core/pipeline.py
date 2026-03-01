"""
Pipeline: orchestration only.
Flow: _prepare_environment -> _run_sparse -> _run_dense -> _run_geospatial_stages -> _post_process.
Project output structure:
  sparse/
  dense/
  geospatial/
    dtm.tif, dtm_epsg.tif
    dsm.tif, dsm_epsg.tif
    orthophoto.tif, orthophoto_epsg.tif
Final sparse output: sparse_merged/0/ (chunked) or sparse/0/ (single). After run, also exported
to final_results/ (sparse copy + sparse.ply) via final_results.export_final_results().
Delegates: state (state.py), validation (validation.py), profile (profiles.py), detection (hardware.py).
"""
from pathlib import Path

from . import chunking, hardware
from .config import COMPLETION_STEPS
from .engine import VramWatchdogError
from .events import Event
from .profiles import get_profile
from .state import (
    load_state,
    save_state,
    mark_step_done,
    is_step_done,
    is_chunk_mapping_done,
    is_chunk_step_done,
    mark_chunk_step_done,
    reset_state,
)
from .validation import sparse_valid, dense_valid
from .logger import get_logger, get_chunk_logger, set_log_file_for_project
from . import final_results as final_results_module
from .config import QUALITY_PRESETS


class Pipeline:
    def __init__(self, engine, context, on_event=None, chunk_size=None, force_profile=None, event_emitter=None, quality=None):
        self.engine = engine
        self.ctx = context
        self.on_event = on_event or (lambda e: None)
        self.chunk_size = chunk_size
        self.force_profile = force_profile
        self.event_emitter = event_emitter
        self.quality = quality if quality in QUALITY_PRESETS else "medium"
        self._project_path = None
        self._image_path = None
        self._profile = None
        self._chunk_folders = []
        self._use_chunking = False
        self._abort = False
        self._log = get_logger("pipeline")

    def emit(self, type_, message=None, progress=None):
        self.on_event(Event(type_, message, progress))

    def _hook(self, event_name: str, **payload):
        if self.event_emitter is not None:
            self.event_emitter.emit(event_name, **payload)

    def _bus(self, event_name: str, data=None):
        """Emit via context.event_bus only. No direct GUI/controller state modification."""
        if getattr(self.ctx, "event_bus", None) is not None:
            self.ctx.event_bus.emit(event_name, data)

    def run(self):
        ctx = self.ctx
        bus = getattr(ctx, "event_bus", None)
        if getattr(ctx, "stop_event", None) is not None:
            ctx.stop_event.clear()
        self._stop_requested = False

        def on_stop_requested(_, data):
            self._stop_requested = True
            if getattr(ctx, "stop_event", None) is not None:
                ctx.stop_event.set()

        if bus is not None:
            bus.subscribe("pipeline_stop_requested", on_stop_requested)

        self._hook("pipeline_start")
        self.emit("start", "Pipeline started", 0.0)
        self._bus("pipeline_started")
        try:
            self._prepare_environment()
            if self._abort:
                return
            self._bus("progress_updated", 10)
            if self._project_path is not None:
                log_path = set_log_file_for_project(self._project_path)
                if log_path:
                    self._log.info("Log file: %s", log_path)
            self._bus("stage_started", {"stage": "sparse"})
            self._run_sparse()
            if not self._abort:
                self._filter_sparse()
            if not self._abort:
                self._bus("stage_completed", {"stage": "sparse"})
                self._bus("progress_updated", 40)
                self._bus("stage_started", {"stage": "dense"})
                self._run_dense()
                fused_ply = Path(self.ctx.dense_path) / "fused.ply"
                self._bus("stage_completed", {"stage": "dense", "fused_ply": str(fused_ply)})
                self._bus("progress_updated", 80)
                if self._config_enable_geospatial():
                    self._run_geospatial_stages()
                else:
                    self._log.info("Geospatial stages disabled by config (enable_geospatial=false)")
            self._bus("stage_started", {"stage": "post_process"})
            self._post_process()
            self._bus("stage_completed", {"stage": "post_process"})
            self._bus("pipeline_finished")
        except Exception as e:
            if getattr(self, "_stop_requested", False):
                self._bus("pipeline_error", "Stopped by user")
                self._hook("pipeline_error", error=e)
                self.emit("error", "Stopped by user")
            else:
                self._bus("pipeline_error", str(e))
                self._hook("pipeline_error", error=e)
                self.emit("error", str(e))
            self._log.exception("Pipeline failed: %s", e)
            raise
        finally:
            if bus is not None:
                bus.unsubscribe("pipeline_stop_requested", on_stop_requested)
            if self._project_path is not None:
                try:
                    save_state(self._project_path, load_state(self._project_path))
                except Exception:
                    pass

    def _prepare_environment(self):
        """Resolve profile, chunk size, image count; prepare context and chunk list."""
        from mapfree.core.config import get_config
        cfg = get_config()

        self._project_path = Path(self.ctx.project_path)

        hw = hardware.get_hardware_profile()
        self._log.info(
            "Hardware: RAM %.2f GB, VRAM %d MB",
            hw.ram_gb,
            hw.vram_mb,
        )
        self.emit("step", "Detected VRAM: %d MB" % hw.vram_mb, 0.02)
        force = self.force_profile or cfg.get("profile_override")
        if force:
            profile = get_profile(
                4096 if force == "HIGH" else
                2048 if force == "MEDIUM" else
                1024 if force == "LOW" else 0
            )
            profile["profile"] = force
        else:
            profile = get_profile(hw.vram_mb)
        self._profile = profile
        self.ctx.profile = profile
        downscale = QUALITY_PRESETS.get(self.quality, 1)
        self.ctx.profile["quality"] = self.quality
        self.ctx.profile["downscale"] = downscale
        self.emit("step", "Selected profile: %s" % profile["profile"], 0.05)
        self.emit("step", "Quality: %s (downscale %d)" % (self.quality.upper(), downscale), 0.05)

        self.chunk_size = chunking.resolve_chunk_size(self.chunk_size)

        self._image_path = Path(self.ctx.image_path)
        n_images = chunking.count_images(self._image_path)
        self.emit("step", "Image count: %d" % n_images, 0.06)
        if n_images == 0:
            self.emit("error", "No images found in %s" % self._image_path)
            self._abort = True
            return

        self.ctx.prepare()
        self._chunk_folders = chunking.split_dataset(self._image_path, self._project_path, self.chunk_size)
        self._use_chunking = (
            len(self._chunk_folders) > 1
            or (len(self._chunk_folders) == 1 and self._chunk_folders[0] != self._image_path)
        )
        self.emit("step", "Chunking enabled: %s" % ("YES" if self._use_chunking else "NO"), 0.07)
        self.emit("step", "Total chunks: %d" % len(self._chunk_folders), 0.08)

    def _run_sparse(self):
        if self._use_chunking and self._chunk_folders and self._chunk_folders[0] != self._image_path:
            self._run_chunked_sparse()
        else:
            self._run_single_sparse()

    def _filter_sparse(self):
        """Sparse point filtering bypassed: COLMAP point_filtering binary incompatible (SIGABRT)."""
        self._log.info("Skipping sparse point filtering due to binary incompatibility")
        self.emit("step", "Skipping filtering due to binary incompatibility", 0.55)

    def _run_dense(self):
        from mapfree.core.config import get_config
        cfg = get_config()
        dense_engine = str(cfg.get("dense_engine") or "colmap").strip().lower()
        retry_count = int(cfg.get("retry_count", 2))
        vw = cfg.get("vram_watchdog") or {}
        downscale = float(vw.get("downscale_factor", 0.75))

        project_path = self._project_path
        self._hook("step_start", step_name="dense")

        if dense_engine == "openmvs":
            openmvs_output = project_path / "openmvs" / "scene_textured.mvs"
            if openmvs_output.exists():
                self.emit("step", "[RESUME] Skipping dense (OpenMVS)", None)
            else:
                self.emit("step", "[RUNNING] OpenMVS pipeline", 0.6)
                from mapfree.engines.openmvs_engine import OpenMVSEngine
                openmvs_ctx = self.ctx
                if getattr(openmvs_ctx, "logger", None) is None:
                    openmvs_ctx.logger = self._log
                OpenMVSEngine(openmvs_ctx).run()
                mark_step_done(project_path, "dense")
                self.emit("step", "[DONE] OpenMVS pipeline", None)
        else:
            if is_step_done(project_path, "dense") and dense_valid(self.ctx.dense_path):
                self.emit("step", "[RESUME] Skipping dense", None)
            else:
                self.emit("step", "[RUNNING] dense reconstruction", 0.6)
                Path(self.ctx.dense_path).mkdir(parents=True, exist_ok=True)
                use_gpu = self.ctx.profile.get("use_gpu", 1)
                vram_mb = hardware.detect_gpu_vram()
                enable_watchdog = bool(use_gpu and vram_mb > 0)
                for attempt in range(retry_count + 1):
                    try:
                        self.engine.dense(self.ctx, vram_watchdog=enable_watchdog)
                        break
                    except VramWatchdogError:
                        if attempt < retry_count:
                            current = self.ctx.profile.get("max_image_size") or 800
                            new_size = max(100, int(current * downscale))
                            self.ctx.profile["max_image_size"] = new_size
                            self.emit("step", "VRAM exceeded, retrying dense with max_image_size=%d" % new_size, None)
                        else:
                            raise
                if dense_valid(self.ctx.dense_path):
                    mark_step_done(project_path, "dense")
                self.emit("step", "[DONE] dense reconstruction", None)
            fused_ply = Path(self.ctx.dense_path) / "fused.ply"
            if fused_ply.exists() and fused_ply.stat().st_size < 1024:
                self._log.warning(
                    "Dense fusion produced an empty model, possibly due to VRAM limits (fused.ply %d bytes)",
                    fused_ply.stat().st_size,
                )
        self._hook("step_end", step_name="dense")

    def _post_process(self):
        """Export final sparse to final_results/ (copy + PLY), then clear state if done; emit complete."""
        project_path = self._project_path
        sparse_dir = Path(self.ctx.sparse_path)
        if sparse_valid(sparse_dir):
            try:
                final_dir = final_results_module.export_final_results(project_path, sparse_dir)
                self._log.info(
                    "Final sparse model exported to %s (sparse copy + %s)",
                    final_dir,
                    final_results_module.SPARSE_PLY_NAME,
                )
                self.emit(
                    "step",
                    "Final sparse exported to %s" % (final_dir / final_results_module.SPARSE_PLY_NAME),
                    None,
                )
            except Exception as e:
                self._log.warning("Could not export final results: %s", e)
                self.emit("step", "Final results export skipped: %s" % e, None)
        state = load_state(project_path)
        if all(state.get(s, False) for s in COMPLETION_STEPS):
            reset_state(project_path)
            self.emit("step", "[RESUME] State file removed (all steps complete)", None)
        self._hook("pipeline_complete")
        self.emit("complete", "Pipeline finished", 1.0)

    def _config_enable_geospatial(self) -> bool:
        """True if config.enable_geospatial is True."""
        from mapfree.core.config import get_config
        cfg = get_config()
        return bool(cfg.get("enable_geospatial", True))

    def _run_geospatial_stages(self):
        """Run geospatial stages after dense: convert to LAS, ground classification, DSM, DTM, orthophoto."""
        from mapfree.core.config import get_config
        from mapfree.utils.dependency_check import check_geospatial_dependencies
        from mapfree.geospatial.georef import convert_ply_to_las
        from mapfree.geospatial.classification import classify_ground
        from mapfree.geospatial.rasterizer import generate_dsm, generate_dtm
        from mapfree.geospatial.orthomosaic import generate_orthophoto
        from mapfree.geospatial.output_names import (
            DTM_TIF,
            DTM_EPSG_TIF,
            DSM_TIF,
            DSM_EPSG_TIF,
            ORTHOPHOTO_TIF,
            ORTHOPHOTO_EPSG_TIF,
        )

        try:
            check_geospatial_dependencies()
        except RuntimeError as e:
            self._log.warning("Skipping geospatial stages: %s", e)
            return

        cfg = get_config()
        resolution = float(cfg.get("dtm_resolution", 0.05))

        project_path = Path(self._project_path)
        dense_path = Path(self.ctx.dense_path)
        image_path = self._image_path or project_path / "images"
        geo_dir = Path(self.ctx.geospatial_path)
        geo_dir.mkdir(parents=True, exist_ok=True)

        dense_las = geo_dir / "dense.las"
        classified_las = geo_dir / "classified.las"
        dsm_tif = geo_dir / DSM_TIF
        dtm_tif = geo_dir / DTM_TIF
        ortho_tif = geo_dir / ORTHOPHOTO_TIF

        # 1. Convert to LAS
        stage = "geospatial_convert_las"
        self._bus("stage_started", {"stage": stage})
        self._bus("progress_updated", 81)
        fused_ply = dense_path / "fused.ply"
        if not fused_ply.exists():
            self._log.warning("Skipping %s: dependency missing (fused.ply not found)", stage)
            self._bus("stage_completed", {"stage": stage, "skipped": True})
        else:
            try:
                convert_ply_to_las(fused_ply, dense_las, event_bus=None)
                self._bus("stage_completed", {"stage": stage})
            except Exception as e:
                self._log.warning("Skipping %s: %s", stage, e)
                self._bus("stage_completed", {"stage": stage, "skipped": True})

        # 2. Ground Classification
        stage = "geospatial_ground_classification"
        self._bus("stage_started", {"stage": stage})
        self._bus("progress_updated", 82)
        if not dense_las.exists():
            self._log.warning("Skipping %s: dependency missing (dense.las not found)", stage)
            self._bus("stage_completed", {"stage": stage, "skipped": True})
        else:
            try:
                classify_ground(dense_las, classified_las)
                self._bus("stage_completed", {"stage": stage})
            except Exception as e:
                self._log.warning("Skipping %s: %s", stage, e)
                self._bus("stage_completed", {"stage": stage, "skipped": True})

        # 3. DSM Generation
        stage = "geospatial_dsm"
        self._bus("stage_started", {"stage": stage})
        self._bus("progress_updated", 83)
        if not dense_las.exists():
            self._log.warning("Skipping %s: dependency missing (dense.las not found)", stage)
            self._bus("stage_completed", {"stage": stage, "skipped": True})
        else:
            try:
                generate_dsm(dense_las, dsm_tif, resolution=resolution)
                self._bus("stage_completed", {"stage": stage})
            except Exception as e:
                self._log.warning("Skipping %s: %s", stage, e)
                self._bus("stage_completed", {"stage": stage, "skipped": True})

        # 4. DTM Generation
        stage = "geospatial_dtm"
        self._bus("stage_started", {"stage": stage})
        self._bus("progress_updated", 84)
        if not classified_las.exists():
            self._log.warning("Skipping %s: dependency missing (classified.las not found)", stage)
            self._bus("stage_completed", {"stage": stage, "skipped": True})
        else:
            try:
                generate_dtm(classified_las, dtm_tif, resolution=resolution)
                self._bus("stage_completed", {"stage": stage})
            except Exception as e:
                self._log.warning("Skipping %s: %s", stage, e)
                self._bus("stage_completed", {"stage": stage, "skipped": True})

        # 5. Orthophoto Generation (skip only if georeference missing)
        stage = "geospatial_orthophoto"
        self._bus("stage_started", {"stage": stage})
        self._bus("progress_updated", 85)
        if not dtm_tif.exists():
            self._log.warning("Skipping %s: dependency missing (dtm.tif not found)", stage)
            self._bus("stage_completed", {"stage": stage, "skipped": True})
        else:
            try:
                generate_orthophoto(image_path, dtm_tif, ortho_tif)
                self._bus("stage_completed", {"stage": stage})
            except RuntimeError as e:
                if "georeferenced" in str(e).lower():
                    self._log.warning("Skipping %s: orthophoto requires georeferenced dataset.", stage)
                    self._bus("stage_completed", {"stage": stage, "skipped": True})
                else:
                    raise
            except Exception as e:
                self._log.warning("Skipping %s: %s", stage, e)
                self._bus("stage_completed", {"stage": stage, "skipped": True})

        # After DTM + DSM + Orthophoto: detect CRS and optionally reproject to EPSG
        self._run_geospatial_crs_reproject(geo_dir, image_path, dtm_tif, dsm_tif, ortho_tif)

    def _run_geospatial_crs_reproject(self, geo_dir, image_path, dtm_tif, dsm_tif, ortho_tif):
        """
        After geospatial stages: use config.target_epsg if set; else if auto_detect_epsg
        detect CRS from images; else skip. Then reproject dtm/dsm/orthophoto to *_epsg.tif.
        """
        from mapfree.core.config import get_config
        from mapfree.geospatial.crs_manager import CRSManager

        cfg = get_config()
        target_epsg = cfg.get("target_epsg")
        auto_detect_epsg = bool(cfg.get("auto_detect_epsg", True))

        if target_epsg is not None:
            try:
                epsg = int(target_epsg)
            except (TypeError, ValueError):
                self._log.warning("config.target_epsg invalid (%s); skipping reprojection.", target_epsg)
                self._bus("crs_missing", {"message": "target_epsg invalid; reprojection skipped."})
                return
            self._log.info("Using config.target_epsg: %d", epsg)
            self._bus("crs_detected", {"epsg": epsg, "source": "config"})
        elif auto_detect_epsg:
            epsg = CRSManager.detect_crs_from_images(image_path)
            if epsg is None:
                self._log.warning("No GPS in images; skipping CRS reprojection.")
                self._bus("crs_missing", {"message": "No GPS in images; reprojection skipped."})
                return
            self._bus("crs_detected", {"epsg": epsg, "source": "auto"})
        else:
            self._log.info("CRS reprojection disabled (auto_detect_epsg=false, target_epsg not set).")
            self._bus("crs_missing", {"message": "Reprojection disabled by config."})
            return

        dtm_epsg = geo_dir / DTM_EPSG_TIF
        dsm_epsg = geo_dir / DSM_EPSG_TIF
        ortho_epsg = geo_dir / ORTHOPHOTO_EPSG_TIF

        event_bus = getattr(self.ctx, "event_bus", None)
        try:
            if dtm_tif.exists():
                CRSManager.reproject_raster(dtm_tif, dtm_epsg, epsg, event_bus=event_bus)
            if dsm_tif.exists():
                CRSManager.reproject_raster(dsm_tif, dsm_epsg, epsg, event_bus=event_bus)
            if ortho_tif.exists():
                CRSManager.reproject_raster(ortho_tif, ortho_epsg, epsg, event_bus=event_bus)
            self._bus("reprojection_completed", {
                "epsg": epsg,
                "dtm_epsg": str(dtm_epsg),
                "dsm_epsg": str(dsm_epsg),
                "orthophoto_epsg": str(ortho_epsg),
            })
            self._log.info(
                "CRS reprojection completed: EPSG:%d -> %s, %s, %s",
                epsg, DTM_EPSG_TIF, DSM_EPSG_TIF, ORTHOPHOTO_EPSG_TIF,
            )
        except Exception as e:
            self._log.warning("CRS reprojection failed: %s", e)
            self._bus("reprojection_completed", {"epsg": epsg, "error": str(e)})

    # ------------------------------------------------------------------
    # Sparse: chunked
    # ------------------------------------------------------------------

    def _run_chunked_sparse(self):
        project_path = self._project_path
        image_path = self._image_path
        chunk_folders = self._chunk_folders
        profile = self._profile

        self._hook("step_start", step_name="feature_extraction")
        self._log.info("Sparse phase (chunked): %d chunks", len(chunk_folders))
        merged_sparse_dir = project_path / "sparse_merged" / "0"
        sparse_phase_done = (
            is_step_done(project_path, "feature_extraction")
            and is_step_done(project_path, "matching")
            and is_step_done(project_path, "sparse")
            and sparse_valid(merged_sparse_dir)
        )
        if sparse_phase_done:
            self.emit("step", "[RESUME] Skipping feature_extraction", None)
            self.emit("step", "[RESUME] Skipping matching", None)
            self.emit("step", "[RESUME] Skipping sparse", None)
            chunks_dir = project_path / "chunks"
            sparse_dirs = []
            for d in sorted(chunks_dir.iterdir()):
                if d.is_dir():
                    sp = d / "sparse" / "0"
                    if sparse_valid(sp):
                        sparse_dirs.append(sp)
            if sparse_dirs:
                merged = chunking.merge_sparse_models(project_path, sparse_dirs)
                self.ctx.sparse_path = str(merged)
            self.ctx.image_path = str(image_path)
            self.ctx.dense_path = str(project_path / "dense")
            self._hook("step_end", step_name="sparse")
        else:
            sparse_dirs = []
            for i, chunk_path in enumerate(chunk_folders):
                chunk_name = chunk_path.name
                sp0 = chunk_path / "sparse" / "0"
                if is_chunk_mapping_done(project_path, chunk_name) and sparse_valid(sp0):
                    self.emit("step", "[RESUME] Skipping chunk %s (mapping done)" % chunk_name, None)
                    sparse_dirs.append(sp0)
                    continue
                chunk_ctx = type(self.ctx)(chunk_path, chunk_path, profile)
                chunk_ctx.prepare()
                chunk_log = get_chunk_logger(self._log, chunk_name)
                if not is_chunk_step_done(project_path, chunk_name, "feature_extraction"):
                    chunk_log.info("Feature extraction %d/%d", i + 1, len(chunk_folders))
                    self.emit("step", "[RUNNING] Chunk %d/%d: feature extraction" % (i + 1, len(chunk_folders)),
                              0.1 + 0.25 * i / max(len(chunk_folders), 1))
                    self.engine.feature_extraction(chunk_ctx)
                    mark_chunk_step_done(project_path, chunk_name, "feature_extraction")
                else:
                    chunk_log.debug("Feature extraction already done")
                    self.emit("step", "[RESUME] Chunk %s: feature_extraction done" % chunk_name, None)
                if not is_chunk_step_done(project_path, chunk_name, "matching"):
                    chunk_log.info("Matching %d/%d", i + 1, len(chunk_folders))
                    self.emit("step", "Chunk %d/%d: matching" % (i + 1, len(chunk_folders)), None)
                    self.engine.matching(chunk_ctx)
                    mark_chunk_step_done(project_path, chunk_name, "matching")
                else:
                    chunk_log.debug("Matching already done")
                    self.emit("step", "[RESUME] Chunk %s: matching done" % chunk_name, None)
                if not is_chunk_step_done(project_path, chunk_name, "mapping"):
                    chunk_log.info("Mapper %d/%d", i + 1, len(chunk_folders))
                    self.emit("step", "Chunk %d/%d: mapper" % (i + 1, len(chunk_folders)), None)
                    self.engine.sparse(chunk_ctx)
                    sp = Path(chunk_ctx.sparse_path) / "0"
                    if sp.exists():
                        sparse_dirs.append(sp)
                    else:
                        sparse_dirs.append(Path(chunk_ctx.sparse_path))
                    chunk_sparse_dir = sp if sp.exists() else Path(chunk_ctx.sparse_path)
                    if sparse_valid(chunk_sparse_dir):
                        mark_chunk_step_done(project_path, chunk_name, "mapping")
                else:
                    sparse_dirs.append(sp0 if sp0.exists() else (chunk_path / "sparse"))
            self.emit("step", "Merging sparse models", 0.45)
            merged = chunking.merge_sparse_models(project_path, sparse_dirs)
            self.ctx.sparse_path = str(merged)
            self._log.info("Final sparse output: %s (also exported to final_results/ after pipeline)", merged)
            self.ctx.image_path = str(image_path)
            self.ctx.dense_path = str(project_path / "dense")
            if sparse_valid(Path(merged)):
                mark_step_done(project_path, "feature_extraction")
                mark_step_done(project_path, "matching")
                mark_step_done(project_path, "sparse")
            self._hook("step_end", step_name="sparse")

    # ------------------------------------------------------------------
    # Sparse: single
    # ------------------------------------------------------------------

    def _run_single_sparse(self):
        project_path = self._project_path
        image_path = self._image_path

        self._hook("step_start", step_name="feature_extraction")
        if is_step_done(project_path, "feature_extraction"):
            self.emit("step", "[RESUME] Skipping feature_extraction", None)
        else:
            self.emit("step", "[RUNNING] feature_extraction", 0.2)
            self.engine.feature_extraction(self.ctx)
            mark_step_done(project_path, "feature_extraction")
        self._hook("step_end", step_name="feature_extraction")

        self._hook("step_start", step_name="matching")
        if is_step_done(project_path, "matching"):
            self.emit("step", "[RESUME] Skipping matching", None)
        else:
            self.emit("step", "[RUNNING] matching", 0.4)
            self.engine.matching(self.ctx)
            mark_step_done(project_path, "matching")
        self._hook("step_end", step_name="matching")

        self._hook("step_start", step_name="sparse")
        sparse_dir = Path(self.ctx.sparse_path) / "0"
        if not sparse_dir.exists():
            sparse_dir = Path(self.ctx.sparse_path)
        if is_step_done(project_path, "sparse") and sparse_valid(sparse_dir):
            self.emit("step", "[RESUME] Skipping sparse", None)
        else:
            self.emit("step", "[RUNNING] sparse reconstruction", 0.5)
            self.engine.sparse(self.ctx)
            sparse_dir_after = Path(self.ctx.sparse_path) / "0"
            if not sparse_dir_after.exists():
                sparse_dir_after = Path(self.ctx.sparse_path)
            if sparse_valid(sparse_dir_after):
                mark_step_done(project_path, "sparse")
        self._hook("step_end", step_name="sparse")

        self.ctx.sparse_path = str(Path(self.ctx.sparse_path) / "0") \
            if (Path(self.ctx.sparse_path) / "0").exists() else str(self.ctx.sparse_path)
        self.ctx.image_path = str(image_path)
        self.ctx.dense_path = str(project_path / "dense")
