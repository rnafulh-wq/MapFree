"""Project workspace handling: create folders, validate inputs."""

import shutil
from pathlib import Path

from .exceptions import ProjectError, ValidationError
from .utils import find_images


def create_project(root: Path, project_name: str) -> Path:
    """Create project directory under root. Return project path."""
    root = Path(root)
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def setup_project_dirs(project_path: Path) -> dict[str, Path]:
    """Create standard subdirs: images, sparse, dense, logs. Return paths dict."""
    project_path = Path(project_path)
    dirs = {
        "project": project_path,
        "images": project_path / "images",
        "sparse": project_path / "sparse",
        "dense": project_path / "dense",
        "logs": project_path / "logs",
    }
    for key in ("images", "sparse", "dense", "logs"):
        dirs[key].mkdir(parents=True, exist_ok=True)
    return dirs


def validate_image_input(image_path: Path, min_images: int = 3) -> list[Path]:
    """
    Validate that image_path is a directory with enough images.
    Returns list of image paths. Raises ValidationError if invalid.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise ValidationError(f"Input path does not exist: {image_path}")
    if not image_path.is_dir():
        raise ValidationError(f"Input path is not a directory: {image_path}")

    images = find_images(image_path)
    if len(images) < min_images:
        raise ValidationError(
            f"Not enough images in {image_path}: found {len(images)}, need at least {min_images}"
        )
    return images


def link_images_to_project(image_paths: list[Path], project_images_dir: Path) -> None:
    """Symlink (or copy if symlink fails) image_paths into project/images."""
    project_images_dir = Path(project_images_dir)
    project_images_dir.mkdir(parents=True, exist_ok=True)
    for src in image_paths:
        dst = project_images_dir / src.name
        if dst.exists():
            continue
        try:
            dst.symlink_to(src.resolve())
        except OSError:
            shutil.copy2(src, dst)
