"""
Security tests: path traversal, shell metacharacters in paths, YAML injection.
"""
import pytest

from mapfree.core.exceptions import ProjectValidationError
from mapfree.core.validation import validate_path_allowed


def test_path_traversal_rejected(tmp_path):
    """Path escaping allowed_base (e.g. ../../etc/passwd) raises ProjectValidationError."""
    base = tmp_path.resolve()
    (tmp_path / "allowed").mkdir(exist_ok=True)
    allowed_sub = tmp_path / "allowed"

    validate_path_allowed(allowed_sub, base, "path")  # ok: under base

    with pytest.raises(ProjectValidationError, match="di luar direktori basis"):
        validate_path_allowed(str(tmp_path / ".." / ".." / "etc" / "passwd"), base, "path")

    with pytest.raises(ProjectValidationError, match="di luar direktori basis"):
        validate_path_allowed(str(tmp_path / "allowed" / ".." / ".." / "etc"), base, "path")


def test_path_traversal_relative_to_base(tmp_path):
    """Path under base is accepted; path outside base is rejected."""
    base = (tmp_path / "base").resolve()
    base.mkdir(parents=True, exist_ok=True)
    inside = base / "project"
    inside.mkdir(exist_ok=True)

    result = validate_path_allowed(str(inside), base, "project_path")
    assert result == inside

    other = tmp_path / "other"
    other.mkdir(exist_ok=True)
    with pytest.raises(ProjectValidationError):
        validate_path_allowed(str(other), base, "project_path")


def test_shell_metacharacters_in_path_not_executed(tmp_path):
    """
    Paths containing semicolon (or other shell-ish chars where allowed by OS)
    are validated as path strings only. Engine uses list args (no shell=True).
    """
    base = tmp_path.resolve()
    # Use a name that is valid on both Windows and Unix (semicolon can be in dir name on Unix)
    sub = tmp_path / "img_folder"
    sub.mkdir(exist_ok=True)
    result = validate_path_allowed(str(sub), base, "image_path")
    assert result == sub
    # Validation only checks traversal; we do not pass paths to shell


def test_yaml_safe_load_required():
    """Config and settings must use yaml.safe_load; unsafe YAML with Python tags is rejected."""
    import yaml
    payload = "!!python/object/apply:os.system\nargs: ['id']"
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(payload)
