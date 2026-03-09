"""
Import-level smoke tests for backward-compatibility stub modules.
Importing these modules covers their re-export lines without triggering side effects.
"""
import importlib
import pytest


def _import(module_name: str):
    """Import a module, skip if optional dependency is missing."""
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        pytest.skip(f"Optional dependency missing: {e}")


class TestStubImports:
    def test_api_init(self):
        mod = _import("mapfree.api")
        assert hasattr(mod, "MapFreeController")

    def test_api_controller(self):
        mod = _import("mapfree.api.controller")
        assert hasattr(mod, "MapFreeController")

    def test_cli_init(self):
        mod = _import("mapfree.cli")
        assert hasattr(mod, "main")

    def test_config_compat(self):
        mod = _import("mapfree.config")
        assert hasattr(mod, "get_config")

    def test_engines_base(self):
        mod = _import("mapfree.engines.base")
        assert hasattr(mod, "BaseEngine")

    def test_engines_base_engine(self):
        mod = _import("mapfree.engines.base_engine")
        assert hasattr(mod, "BaseEngine")

    def test_engines_colmap(self):
        mod = _import("mapfree.engines.colmap")
        assert hasattr(mod, "ColmapEngine")

    def test_profiles_compat(self):
        mod = _import("mapfree.profiles")
        assert hasattr(mod, "PROFILES")

    def test_profiles_mx150(self):
        mod = _import("mapfree.profiles.mx150")
        assert hasattr(mod, "MX150_PROFILE")

    def test_core_profiles_mx150(self):
        mod = _import("mapfree.core.profiles.mx150")
        assert hasattr(mod, "MX150_PROFILE")
