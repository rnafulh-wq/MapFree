"""
Profile selection: VRAM/RAM -> profile dict and chunk size.
All values from config (mapfree/config/default.yaml); no hardcoding.
"""
import os

from mapfree.core.config import ENV_CHUNK_SIZE


def _cfg():
    from mapfree.config import get_config
    return get_config()


def get_profiles() -> dict:
    """Profile definitions from config (HIGH, MEDIUM, LOW, CPU_SAFE)."""
    return _cfg().get("profiles", {})


def get_chunk_sizes() -> dict:
    """Chunk sizes per profile from config."""
    return _cfg().get("chunk_sizes", {"HIGH": 400, "MEDIUM": 250, "LOW": 150, "CPU_SAFE": 100})


def get_profile(vram_mb: int) -> dict:
    """Select profile from VRAM (MB). Returns a *copy* of the profile dict from config."""
    profiles = get_profiles()
    if not profiles:
        profiles = {"HIGH": {"profile": "HIGH", "max_image_size": 3200, "max_features": 16384, "matcher": "sequential", "use_gpu": 1},
                    "MEDIUM": {"profile": "MEDIUM", "max_image_size": 2400, "max_features": 8192, "matcher": "sequential", "use_gpu": 1},
                    "LOW": {"profile": "LOW", "max_image_size": 1600, "max_features": 8000, "matcher": "exhaustive", "use_gpu": 1},
                    "CPU_SAFE": {"profile": "CPU_SAFE", "max_image_size": 1600, "max_features": 8000, "matcher": "exhaustive", "use_gpu": 0}}
    if vram_mb >= 4096:
        return dict(profiles.get("HIGH", {}))
    if vram_mb >= 2048:
        return dict(profiles.get("MEDIUM", {}))
    if vram_mb >= 1024:
        return dict(profiles.get("LOW", {}))
    return dict(profiles.get("CPU_SAFE", {}))


def recommend_chunk_size(vram_mb: int, ram_gb: float) -> int:
    """Recommend chunk size from VRAM + RAM (from config chunk_sizes). Applied memory_multiplier."""
    cfg = _cfg()
    sizes = cfg.get("chunk_sizes") or get_chunk_sizes()
    mult = float(cfg.get("memory_multiplier", 1.0))
    if ram_gb <= 0:
        ram_gb = 8.0
    if vram_mb >= 4096 and ram_gb >= 16:
        base = sizes.get("HIGH", 400)
    elif vram_mb >= 2048 and ram_gb >= 8:
        base = sizes.get("MEDIUM", 250)
    elif vram_mb >= 1024 and ram_gb >= 4:
        base = sizes.get("LOW", 150)
    else:
        base = sizes.get("CPU_SAFE", 100)
    return max(1, int(base * mult))


def resolve_chunk_size(override: int | None, vram_mb: int, ram_gb: float) -> int:
    """Resolve chunk size: override > config chunk_size/max_images_per_chunk > ENV > recommendation."""
    if override is not None:
        return max(1, int(override))
    cfg = _cfg()
    config_val = cfg.get("chunk_size")
    if config_val is None:
        config_val = cfg.get("max_images_per_chunk")
    if config_val is not None:
        return max(1, int(config_val))
    env_val = os.environ.get(ENV_CHUNK_SIZE)
    if env_val and env_val.strip():
        try:
            return max(1, int(env_val.strip()))
        except ValueError:
            pass
    return recommend_chunk_size(vram_mb, ram_gb)


# Backward compatibility: lazy module attributes (read from config when accessed)
def __getattr__(name: str):
    if name == "PROFILES":
        return get_profiles()
    if name == "CHUNK_SIZES":
        return get_chunk_sizes()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
