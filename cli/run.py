"""Command-line entry point for MapFree pipeline."""

import argparse
import sys
from pathlib import Path

# Allow running as python -m cli.run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.colmap_runner import (
    build_feature_extractor_args,
    build_image_undistorter_args,
    build_mapper_args,
    build_matcher_args,
    build_patch_match_stereo_args,
    build_stereo_fusion_args,
    run_colmap,
)
from pipeline.exceptions import ColmapError, ConfigError, MapFreeError, ValidationError
from pipeline.logger import get_logger, setup_logging
from pipeline.project import (
    create_project,
    link_images_to_project,
    setup_project_dirs,
    validate_image_input,
)
from pipeline.steps import PIPELINE_STEPS, done_file, step_completed
from pipeline.exporter import ensure_dense_ply_copy


def load_config(config_name: str) -> dict:
    """Load YAML config from config/<name>.yaml."""
    import yaml
    config_dir = Path(__file__).resolve().parent.parent / "config"
    path = config_dir / f"{config_name}.yaml"
    if not path.exists():
        raise ConfigError(f"Config not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f) or {}


def run_pipeline(
    image_path: Path,
    project_name: str,
    projects_root: Path,
    config: dict,
    dry_run: bool = False,
    resume: bool = False,
) -> None:
    """Run full pipeline: init, COLMAP steps, export."""
    log = get_logger("run")
    project_path = create_project(projects_root, project_name)
    dirs = setup_project_dirs(project_path)
    num_threads = config.get("system", {}).get("num_threads", 4)

    for step in PIPELINE_STEPS:
        if step_completed(step, project_path, dirs) and resume:
            log.info("Resume: skip step %s (already done)", step)
            continue

        if step == "init":
            images = validate_image_input(image_path)
            link_images_to_project(images, dirs["images"])
            done_file(project_path, "init").touch()
            log.info("Init: linked %d images", len(images))
            continue

        if step == "feature_extractor":
            cmd = build_feature_extractor_args(project_path, dirs["images"], config)
            run_colmap(cmd, dry_run=dry_run, num_threads=num_threads)
            done_file(project_path, step).touch()
            continue

        if step == "matcher":
            cmd = build_matcher_args(project_path, config)
            run_colmap(cmd, dry_run=dry_run, num_threads=num_threads)
            done_file(project_path, step).touch()
            continue

        if step == "mapper":
            cmd = build_mapper_args(project_path, config)
            run_colmap(cmd, dry_run=dry_run, num_threads=num_threads)
            done_file(project_path, step).touch()
            continue

        if step == "image_undistorter":
            cmd = build_image_undistorter_args(project_path)
            run_colmap(cmd, dry_run=dry_run, num_threads=num_threads)
            done_file(project_path, step).touch()
            continue

        if step == "patch_match_stereo":
            cmd = build_patch_match_stereo_args(project_path, config)
            run_colmap(cmd, dry_run=dry_run, num_threads=num_threads)
            cmd_fusion = build_stereo_fusion_args(project_path, config)
            run_colmap(cmd_fusion, dry_run=dry_run, num_threads=num_threads)
            done_file(project_path, step).touch()
            continue

        if step == "export":
            ensure_dense_ply_copy(project_path)
            done_file(project_path, step).touch()
            log.info("Export: dense PLY at %s", dirs["dense"] / "fused.ply")
            continue

    log.info("Pipeline finished: %s", project_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MapFree: lightweight photogrammetry pipeline for drone imagery."
    )
    parser.add_argument(
        "image_path",
        type=Path,
        help="Directory containing drone images (JPG/RAW with EXIF)",
    )
    parser.add_argument(
        "--project",
        "-p",
        default="default",
        help="Project name (folder under projects/)",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="mx150",
        choices=["default", "mx150"],
        help="Config preset (default: mx150 for 2GB VRAM)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print COLMAP commands without executing",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip steps that are already completed",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=None,
        help="Root directory for projects (default: <repo>/projects)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    projects_root = args.projects_dir or (repo_root / "projects")
    log_dir = repo_root / "logs"
    setup_logging(log_file=log_dir / "mapfree.log")

    try:
        config = load_config(args.config)
        run_pipeline(
            args.image_path,
            args.project,
            projects_root,
            config,
            dry_run=args.dry_run,
            resume=args.resume,
        )
        return 0
    except MapFreeError as e:
        get_logger("run").error("%s", e)
        return 1
    except Exception as e:
        get_logger("run").exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
