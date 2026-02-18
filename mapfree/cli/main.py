"""
CLI entry point. Usage: mapfree run <image_folder> --output <project>
Automatic: hardware detection, profile, chunking, merge, dense. No manual flags required.
"""
import argparse
import logging
import sys
from pathlib import Path

from mapfree.api.controller import MapFreeController
from mapfree.config import load_config
from mapfree.core.events import Event
from mapfree.core.logger import setup_logging


def _print_event(e: Event) -> None:
    if e.type == "step":
        msg = e.message or ""
        pct = (" [%d%%]" % int(e.progress * 100)) if e.progress is not None else ""
        print(msg + pct)
    elif e.type == "complete":
        print("DONE:", e.message)
    elif e.type == "error":
        print("ERROR:", e.message)
        sys.exit(1)
    else:
        if e.message:
            print(e.message)


def main() -> None:
    parser = argparse.ArgumentParser(prog="mapfree", description="MapFree — automatic photogrammetry pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run full pipeline on image folder")
    run_parser.add_argument("image_folder", type=str, help="Path to folder of images")
    run_parser.add_argument("--output", "-o", required=True, type=str, help="Output project directory")
    run_parser.add_argument("--quality", "-q", type=str, choices=["high", "medium", "low"], default=None,
                            help="Metashape-style quality: high=full res, medium=÷2, low=÷4 (default: prompt if interactive)")
    run_parser.add_argument("--chunk-size", type=int, default=None, help="Max images per chunk (default: from config default.yaml)")
    run_parser.add_argument("--force-profile", type=str, choices=["LOW", "MEDIUM", "HIGH", "CPU_SAFE"], default=None, help="Override auto profile selection")
    run_parser.add_argument("--log-level", type=str, default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level (default: INFO or MAPFREE_LOG_LEVEL)")
    run_parser.add_argument("--log-dir", type=str, default=None, help="Directory for mapfree.log (default: MAPFREE_LOG_DIR or console only)")
    run_parser.add_argument("--config", "-c", type=str, default=None, help="Path to YAML config (default: mapfree/config/default.yaml + MAPFREE_CONFIG)")
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    # Load config first so profile/chunk/retry come from YAML (and --config override)
    load_config(override_path=args.config)

    image_folder = Path(args.image_folder).resolve()
    project_path = Path(args.output).resolve()
    if not image_folder.is_dir():
        print("ERROR: image_folder is not a directory: %s" % image_folder)
        sys.exit(1)

    level = getattr(logging, args.log_level) if args.log_level else None
    setup_logging(level=level, log_dir=args.log_dir)

    quality = args.quality
    if quality is None and sys.stdin.isatty():
        print("Select quality (Metashape-style smart scaling):")
        print("  1 = High   (full resolution, VRAM-limited)")
        print("  2 = Medium (image size ÷ 2)")
        print("  3 = Low    (image size ÷ 4)")
        try:
            raw = input("Choice [1-3] (default 2): ").strip() or "2"
            quality = {"1": "high", "2": "medium", "3": "low"}.get(raw, "medium")
        except (EOFError, KeyboardInterrupt):
            quality = "medium"
    if quality is None:
        quality = "medium"

    controller = MapFreeController(profile=None)
    controller.run_project(
        str(image_folder),
        str(project_path),
        on_event=_print_event,
        chunk_size=args.chunk_size,
        force_profile=args.force_profile,
        quality=quality,
    )


if __name__ == "__main__":
    main()
