"""
Pipeline: orchestration only.
Flow: _prepare_environment -> _run_sparse -> _run_dense -> _post_process.
Final sparse output: sparse_merged/0/ (chunked) or sparse/0/ (single). After run, also exported
to final_results/ (sparse copy + sparse.ply) via final_results.export_final_results().
Delegates: state (state.py), validation (validation.py), profile (profiles.py), detection (hardware.py).
"""
from pathlib import Path

from . import chunking, hardware
from .config import COMPLETION_STEPS
from .engine import VramWatchdogError
from .events import Event, EventEmitter
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

    def run(self):
        self._hook("pipeline_start")
        self.emit("start", "Pipeline started", 0.0)
        try:
            self._prepare_environment()
            if self._abort:
                return
            if self._project_path is not None:
                log_path = set_log_file_for_project(self._project_path)
                if log_path:
                    self._log.info("Log file: %s", log_path)
            self._run_sparse()
            if not self._abort:
                self._filter_sparse()
            if not self._abort:
                self._run_dense()
            self._post_process()
        except Exception as e:
            self._hook("pipeline_error", error=e)
            self.emit("error", str(e))
            if self._project_path is not None:
                try:
                    save_state(self._project_path, load_state(self._project_path))
                except Exception:
                    pass
            raise

    def _prepare_environment(self):
        """Resolve profile, chunk size, image count; prepare context and chunk list."""
        from mapfree.config import get_config
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
        from mapfree.config import get_config
        cfg = get_config()
        retry_count = int(cfg.get("retry_count", 2))
        vw = cfg.get("vram_watchdog") or {}
        downscale = float(vw.get("downscale_factor", 0.75))

        project_path = self._project_path
        self._hook("step_start", step_name="dense")
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
