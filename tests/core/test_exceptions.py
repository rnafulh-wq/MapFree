"""Unit tests for mapfree.core.exceptions."""
import pytest

from mapfree.core.exceptions import (
    MapFreeError,
    DependencyMissingError,
    PipelineError,
    ProjectValidationError,
    EngineError,
)


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------

def test_all_errors_inherit_mapfree_error():
    """All custom exceptions must be subclasses of MapFreeError."""
    for cls in (DependencyMissingError, PipelineError, ProjectValidationError, EngineError):
        assert issubclass(cls, MapFreeError), f"{cls.__name__} must inherit MapFreeError"


def test_mapfree_error_inherits_exception():
    """MapFreeError must be a standard Exception subclass."""
    assert issubclass(MapFreeError, Exception)


# ---------------------------------------------------------------------------
# DependencyMissingError
# ---------------------------------------------------------------------------

def test_dependency_missing_error_message_without_hint():
    exc = DependencyMissingError("colmap")
    assert "colmap" in str(exc)
    assert exc.binary_name == "colmap"
    assert exc.install_hint == ""


def test_dependency_missing_error_message_with_hint():
    exc = DependencyMissingError("colmap", "https://colmap.github.io/install.html")
    assert "colmap" in str(exc)
    assert "https://colmap.github.io/install.html" in str(exc)
    assert exc.install_hint == "https://colmap.github.io/install.html"


def test_dependency_missing_error_is_catchable_as_base():
    with pytest.raises(MapFreeError):
        raise DependencyMissingError("colmap")


# ---------------------------------------------------------------------------
# EngineError
# ---------------------------------------------------------------------------

def test_engine_error_message_contains_engine_and_returncode():
    exc = EngineError("COLMAP", "feature_extractor failed", returncode=1)
    msg = str(exc)
    assert "COLMAP" in msg
    assert "feature_extractor failed" in msg
    assert "1" in msg


def test_engine_error_default_returncode():
    exc = EngineError("COLMAP", "something went wrong")
    assert exc.returncode == -1


def test_engine_error_attributes():
    exc = EngineError("OpenMVS", "DensifyPointCloud failed", returncode=255)
    assert exc.engine_name == "OpenMVS"
    assert exc.returncode == 255


def test_engine_error_is_catchable_as_base():
    with pytest.raises(MapFreeError):
        raise EngineError("COLMAP", "test")


# ---------------------------------------------------------------------------
# PipelineError
# ---------------------------------------------------------------------------

def test_pipeline_error_message():
    exc = PipelineError("No images found in /tmp/images")
    assert "No images" in str(exc)


def test_pipeline_error_is_catchable_as_base():
    with pytest.raises(MapFreeError):
        raise PipelineError("stage failed")


# ---------------------------------------------------------------------------
# ProjectValidationError
# ---------------------------------------------------------------------------

def test_project_validation_error_message():
    exc = ProjectValidationError("Invalid sparse model dir: /tmp/sparse")
    assert "sparse" in str(exc)


def test_project_validation_error_is_catchable_as_base():
    with pytest.raises(MapFreeError):
        raise ProjectValidationError("bad config")


# ---------------------------------------------------------------------------
# Catch-all: catching MapFreeError catches all subtypes at once
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc_class,kwargs", [
    (DependencyMissingError, {"binary_name": "colmap"}),
    (PipelineError, {"args": ("test",)}),
    (ProjectValidationError, {"args": ("test",)}),
    (EngineError, {"engine_name": "COLMAP", "message": "test"}),
])
def test_catch_as_mapfree_error(exc_class, kwargs):
    """All subtypes are catchable with a single `except MapFreeError`."""
    args = kwargs.pop("args", ())
    try:
        raise exc_class(*args, **kwargs)
    except MapFreeError:
        pass
    except Exception as e:
        pytest.fail(f"Expected MapFreeError but got {type(e).__name__}: {e}")
