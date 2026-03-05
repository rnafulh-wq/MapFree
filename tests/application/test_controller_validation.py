"""Tests for MapFreeController path validation (ProjectValidationError)."""
from pathlib import Path
from unittest.mock import patch

import pytest

from mapfree.application.controller import MapFreeController
from mapfree.core.exceptions import ProjectValidationError


def test_run_project_rejects_path_outside_home():
    """run_project raises ProjectValidationError when path is outside allowed base (home)."""
    home = Path.home().resolve()
    outside = home.parent / "mapfree_test_outside_home_xyz"
    controller = MapFreeController()
    with pytest.raises(ProjectValidationError):
        controller.run_project(
            image_path=str(outside),
            project_path=str(outside),
        )


def test_run_project_accepts_path_under_home(tmp_path):
    """run_project accepts paths under home (does not raise before starting thread)."""
    home = Path.home().resolve()
    if not tmp_path.resolve().is_relative_to(home):
        pytest.skip("tmp_path not under home on this system")
    img = tmp_path / "images"
    proj = tmp_path / "project"
    img.mkdir(exist_ok=True)
    proj.mkdir(exist_ok=True)
    (img / "a.jpg").write_bytes(b"\xff\xd8\xff")
    controller = MapFreeController()
    # Should not raise ProjectValidationError; worker may fail later for other reasons
    controller.run_project(image_path=str(img), project_path=str(proj))
    if controller.worker_thread is not None:
        controller.worker_thread.join(timeout=2)
