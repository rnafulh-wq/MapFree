"""Tests for mapfree.core.engine (create_engine, BaseEngine)."""
import pytest

from mapfree.core.engine import BaseEngine, VramWatchdogError, create_engine
from mapfree.core.exceptions import EngineError


def test_create_engine_colmap():
    """create_engine('colmap') returns a ColmapEngine instance."""
    engine = create_engine("colmap")
    assert isinstance(engine, BaseEngine)
    assert hasattr(engine, "feature_extraction")
    assert hasattr(engine, "matching")
    assert hasattr(engine, "sparse")
    assert hasattr(engine, "dense")


def test_create_engine_unknown_raises():
    """create_engine('unknown') raises EngineError."""
    with pytest.raises(EngineError, match="Unknown engine type"):
        create_engine("unknown")


def test_base_engine_feature_extraction_raises():
    """BaseEngine.feature_extraction raises NotImplementedError."""
    class Concrete(BaseEngine):
        def matching(self, ctx): pass
        def sparse(self, ctx): pass
        def dense(self, ctx, vram_watchdog=False): pass
    with pytest.raises(NotImplementedError):
        Concrete().feature_extraction(None)


def test_vram_watchdog_error():
    """VramWatchdogError is a RuntimeError."""
    e = VramWatchdogError("VRAM exceeded")
    assert isinstance(e, RuntimeError)
    assert "VRAM" in str(e)
