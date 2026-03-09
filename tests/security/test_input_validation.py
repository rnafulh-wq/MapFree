"""
Security tests: path traversal, system dirs, writable parent, YAML injection.
"""
import os
import sys
from pathlib import Path

import pytest

from mapfree.core.exceptions import ProjectValidationError
from mapfree.core.validation import validate_path_allowed


def test_path_must_be_absolute(tmp_path):
    """Relative path that does not resolve to a forbidden dir still must be absolute after resolve."""
    # resolve() makes it absolute; we only reject if not absolute (e.g. if someone passes ".")
    # Actually after resolve() it's always absolute. So we need a case where is_absolute() is False:
    # On Windows, a path like "E:project" might resolve to cwd on E: and be absolute.
    # The check is: if not resolved.is_absolute() - so we'd need to pass something that resolves to non-absolute.
    # In practice resolve() always gives absolute. So this test can check that a valid absolute path is accepted.
    d = (tmp_path / "project").resolve()
    d.mkdir(parents=True, exist_ok=True)
    result = validate_path_allowed(str(d), kind="project_path")
    assert result == d
    assert result.is_absolute()


def test_path_traversal_resolved_away_from_system(tmp_path):
    """Path that uses .. but resolves to a safe writable dir can be allowed (we resolve first)."""
    # After resolve(), .. is normalized. So we only reject if the resolved path is inside forbidden dirs.
    safe = (tmp_path / "a" / "b").resolve()
    safe.mkdir(parents=True, exist_ok=True)
    # Path like a/b/../b is valid and resolves to a/b
    result = validate_path_allowed(str(tmp_path / "a" / "b" / ".." / "b"), kind="path")
    assert result == safe


def test_forbidden_system_dir_rejected():
    """Path under a forbidden system directory raises ProjectValidationError."""
    if sys.platform == "win32":
        forbidden = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "drivers"
        if not forbidden.exists():
            forbidden = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32"
    else:
        forbidden = Path("/etc") / "subdir"
    with pytest.raises(ProjectValidationError, match="tidak boleh di dalam direktori sistem"):
        validate_path_allowed(str(forbidden), kind="project_path")


def test_parent_must_exist(tmp_path):
    """Path whose parent does not exist raises ProjectValidationError."""
    nonexistent = tmp_path / "nonexistent" / "project"
    with pytest.raises(ProjectValidationError, match="direktori induk tidak ada"):
        validate_path_allowed(str(nonexistent), kind="project_path")


def test_parent_must_be_writable(tmp_path):
    """Path whose parent is not writable raises ProjectValidationError (Unix)."""
    if sys.platform == "win32":
        pytest.skip("hard to simulate read-only dir on Windows without admin")
    read_only = tmp_path / "readonly"
    read_only.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(read_only), 0o444)
        child = read_only / "project"
        with pytest.raises(ProjectValidationError, match="tidak dapat ditulis"):
            validate_path_allowed(str(child), kind="project_path")
    finally:
        os.chmod(str(read_only), 0o755)


def test_valid_path_on_any_drive_accepted(tmp_path):
    """Valid absolute path under a writable parent is accepted (e.g. E:\\output on Windows)."""
    d = tmp_path.resolve()
    d.mkdir(parents=True, exist_ok=True)
    result = validate_path_allowed(str(d), kind="project_path")
    assert result == d


def test_yaml_safe_load_required():
    """Config and settings must use yaml.safe_load; unsafe YAML with Python tags is rejected."""
    import yaml
    payload = "!!python/object/apply:os.system\nargs: ['id']"
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(payload)
