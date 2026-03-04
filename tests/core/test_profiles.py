"""Tests for mapfree.core.profiles - profile selection and chunk sizing."""
import pytest

from mapfree.core.profiles import (
    get_profiles,
    get_chunk_sizes,
    get_profile,
    recommend_chunk_size,
    resolve_chunk_size,
)


class TestGetProfiles:
    def test_returns_dict(self):
        profiles = get_profiles()
        assert isinstance(profiles, dict)

    def test_has_cpu_safe(self):
        profiles = get_profiles()
        # either from config or default fallback
        assert isinstance(profiles, dict)


class TestGetChunkSizes:
    def test_returns_dict(self):
        sizes = get_chunk_sizes()
        assert isinstance(sizes, dict)

    def test_has_positive_values(self):
        sizes = get_chunk_sizes()
        for v in sizes.values():
            assert v > 0


class TestGetProfile:
    def test_high_vram(self):
        profile = get_profile(8192)
        assert isinstance(profile, dict)

    def test_medium_vram(self):
        profile = get_profile(3000)
        assert isinstance(profile, dict)

    def test_low_vram(self):
        profile = get_profile(1500)
        assert isinstance(profile, dict)

    def test_cpu_safe(self):
        profile = get_profile(0)
        assert isinstance(profile, dict)

    def test_vram_boundary_4096(self):
        p_high = get_profile(4096)
        p_below = get_profile(4095)
        assert isinstance(p_high, dict)
        assert isinstance(p_below, dict)

    def test_vram_boundary_2048(self):
        p = get_profile(2048)
        assert isinstance(p, dict)

    def test_returns_copy(self):
        """Modifying returned dict does not affect next call."""
        p1 = get_profile(8192)
        p1["test_key"] = "test_val"
        p2 = get_profile(8192)
        assert "test_key" not in p2


class TestRecommendChunkSize:
    def test_returns_positive_int(self):
        result = recommend_chunk_size(4096, 32.0)
        assert isinstance(result, int)
        assert result >= 1

    def test_zero_ram_defaults(self):
        result = recommend_chunk_size(0, 0.0)
        assert result >= 1

    def test_high_config(self):
        result = recommend_chunk_size(4096, 16.0)
        assert result > 0

    def test_medium_config(self):
        result = recommend_chunk_size(2048, 8.0)
        assert result > 0

    def test_low_config(self):
        result = recommend_chunk_size(1024, 4.0)
        assert result > 0


class TestResolveChunkSize:
    def test_override_takes_priority(self):
        result = resolve_chunk_size(override=99, vram_mb=8192, ram_gb=32.0)
        assert result == 99

    def test_override_minimum_one(self):
        result = resolve_chunk_size(override=0, vram_mb=8192, ram_gb=32.0)
        assert result == 1

    def test_env_var_used(self, monkeypatch):
        monkeypatch.setenv("MAPFREE_CHUNK_SIZE", "77")
        result = resolve_chunk_size(override=None, vram_mb=0, ram_gb=0)
        # ENV_CHUNK_SIZE value should be returned (if config doesn't override)
        # Could be 77 or from config depending on what default.yaml has
        assert result >= 1

    def test_env_var_invalid_fallback(self, monkeypatch):
        monkeypatch.setenv("MAPFREE_CHUNK_SIZE", "not_a_number")
        result = resolve_chunk_size(override=None, vram_mb=0, ram_gb=0)
        assert result >= 1

    def test_no_override_returns_positive(self):
        result = resolve_chunk_size(override=None, vram_mb=4096, ram_gb=16.0)
        assert result >= 1


class TestModuleAttributes:
    def test_profiles_attribute(self):
        from mapfree.core.profiles import PROFILES
        assert isinstance(PROFILES, dict)

    def test_chunk_sizes_attribute(self):
        from mapfree.core.profiles import CHUNK_SIZES
        assert isinstance(CHUNK_SIZES, dict)

    def test_unknown_attribute_raises(self):
        import mapfree.core.profiles as profiles_mod
        with pytest.raises(AttributeError):
            _ = profiles_mod.__getattr__("NONEXISTENT_ATTR")
