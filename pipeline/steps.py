"""Pipeline step definitions and completion checks."""

from pathlib import Path

# Locked order; do not change without updating architecture.
PIPELINE_STEPS = [
    "init",
    "feature_extractor",
    "matcher",
    "mapper",
    "image_undistorter",
    "patch_match_stereo",
    "export",
]

DONE_FILE = ".done_{step}"


def done_file(project_path: Path, step: str) -> Path:
    """Path to sentinel file marking step as completed."""
    return Path(project_path) / DONE_FILE.format(step=step)


def step_completed(step: str, project_path: Path, dirs: dict) -> bool:
    """
    Return True if this step has already produced expected outputs (for resume).
    Uses .done_<step> sentinel files written after each step.
    """
    if step == "init":
        return done_file(project_path, "init").exists()

    return done_file(project_path, step).exists()
