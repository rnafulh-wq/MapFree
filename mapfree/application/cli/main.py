"""
CLI entry point. Usage: mapfree run <image_folder> --output <project>
Automatic: hardware detection, profile, chunking, merge, dense. No manual flags required.
Use --open-results to open output folder and orthophoto/DTM after completion (like WebODM/Metashape).
"""
import os
# Force software OpenGL before any Qt/GL is loaded so mapfree gui opens without segfault on Linux
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from mapfree.application.controller import MapFreeController
from mapfree.core.config import load_config
from mapfree.core.events import Event
from mapfree.core.logger import setup_logging
from mapfree.core.state import PipelineState
from mapfree.geospatial.output_names import (
    DTM_EPSG_TIF,
    DTM_TIF,
    ORTHOPHOTO_EPSG_TIF,
    ORTHOPHOTO_TIF,
)

logger = logging.getLogger(__name__)

_GEO = "geospatial"


def _open_results(project_path: Path) -> None:
    """Open output folder in file manager and orthophoto/DTM in default app if present."""
    project_path = Path(project_path).resolve()
    geo_dir = project_path / _GEO
    if sys.platform == "linux":
        try:
            subprocess.Popen(["xdg-open", str(project_path)], start_new_session=True)
        except FileNotFoundError:
            logger.warning("xdg-open not found; cannot open output folder")
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(project_path)], start_new_session=True)
    elif sys.platform == "win32":
        os.startfile(project_path)
    else:
        logger.info("Output: %s", project_path)
        return

    for name, epsg_name in [(ORTHOPHOTO_TIF, ORTHOPHOTO_EPSG_TIF), (DTM_TIF, DTM_EPSG_TIF)]:
        for fname in (epsg_name, name):
            path = geo_dir / fname
            if path.exists():
                try:
                    if sys.platform == "linux":
                        subprocess.Popen(["xdg-open", str(path)], start_new_session=True)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(path)], start_new_session=True)
                    elif sys.platform == "win32":
                        os.startfile(str(path))
                except Exception as e:
                    logger.warning("Could not open %s: %s", path.name, e)
                break


def _emit_event(e: Event) -> None:
    if e.type == "step":
        msg = e.message or ""
        pct = (" [%d%%]" % int(e.progress * 100)) if e.progress is not None else ""
        logger.info("%s%s", msg, pct)
    elif e.type == "complete":
        logger.info("DONE: %s", e.message)
    elif e.type == "error":
        logger.error("ERROR: %s", e.message)
        sys.exit(1)
    else:
        if e.message:
            logger.info("%s", e.message)


def main() -> None:
    parser = argparse.ArgumentParser(prog="mapfree", description="MapFree — automatic photogrammetry pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("gui", help="Open MapFree GUI (desktop application)")
    run_parser = subparsers.add_parser("run", help="Run full pipeline on image folder")
    run_parser.add_argument("image_folder", type=str, help="Path to folder of images")
    run_parser.add_argument("--output", "-o", required=True, type=str, help="Output project directory")
    run_parser.add_argument("--quality", "-q", type=str, choices=["high", "medium", "low"], default=None,
                            help="Metashape-style quality: high=full res, medium=÷2, low=÷4 (default: prompt if interactive)")
    run_parser.add_argument("--chunk-size", type=int, default=None, help="Max images per chunk (default: from config default.yaml)")
    run_parser.add_argument("--force-profile", type=str, choices=["LOW", "MEDIUM", "HIGH", "CPU_SAFE"], default=None, help="Override auto profile selection")
    run_parser.add_argument("--log-level", type=str, default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level (default: INFO or MAPFREE_LOG_LEVEL)")
    run_parser.add_argument("--log-dir", type=str, default=None, help="Directory for mapfree.log (default: MAPFREE_LOG_DIR or console only)")
    run_parser.add_argument("--config", "-c", type=str, default=None, help="Path to YAML config (default: mapfree/core/config/default.yaml + MAPFREE_CONFIG)")
    run_parser.add_argument("--open-results", action="store_true", help="After pipeline completes, open output folder and orthophoto/DTM in default apps (like WebODM/Metashape)")
    args = parser.parse_args()

    if args.command == "gui":
        from mapfree.app import main as app_main
        app_main()
        return

    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    load_config(override_path=args.config)

    image_folder = Path(args.image_folder).resolve()
    project_path = Path(args.output).resolve()
    if not image_folder.is_dir():
        logger.error("image_folder is not a directory: %s", image_folder)
        sys.exit(1)

    level = getattr(logging, args.log_level) if args.log_level else None
    setup_logging(level=level, log_dir=args.log_dir)

    quality = args.quality
    if quality is None and sys.stdin.isatty():
        logger.info(
            "Select quality (Metashape-style smart scaling): "
            "1=High, 2=Medium, 3=Low"
        )
        try:
            raw = input("Choice [1-3] (default 2): ").strip() or "2"
            quality = {"1": "high", "2": "medium", "3": "low"}.get(raw, "medium")
        except (EOFError, KeyboardInterrupt):
            quality = "medium"
    if quality is None:
        from mapfree.core.config import recommend_quality_from_hardware
        quality = recommend_quality_from_hardware()

    controller = MapFreeController(profile=None)
    controller.run_project(
        str(image_folder),
        str(project_path),
        on_event=_emit_event,
        chunk_size=args.chunk_size,
        force_profile=args.force_profile,
        quality=quality,
    )
    if controller.worker_thread is not None:
        controller.worker_thread.join()
    if controller.state == PipelineState.ERROR:
        sys.exit(1)
    if getattr(args, "open_results", False):
        _open_results(project_path)


if __name__ == "__main__":
    main()
