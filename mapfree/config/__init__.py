"""
Load configuration from YAML. No hardcoded run values in Python.
Default: mapfree/config/default.yaml. Override: --config <file> or MAPFREE_CONFIG.
"""
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

_CACHE: dict[str, Any] | None = None
_CONFIG_DIR = Path(__file__).resolve().parent


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base (recursive). base is not mutated."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    if yaml is None:
        raise RuntimeError("PyYAML required for config: pip install PyYAML")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _defaults() -> dict:
    """Built-in defaults (no file)."""
    return {
        "chunk_size": None,
        "max_images_per_chunk": 250,
        "chunk_sizes": {"HIGH": 400, "MEDIUM": 250, "LOW": 150, "CPU_SAFE": 100},
        "memory_multiplier": 1.0,
        "profile_override": None,
        "profiles": {
            "HIGH": {"profile": "HIGH", "max_image_size": 3200, "max_features": 16384, "matcher": "sequential", "use_gpu": 1},
            "MEDIUM": {"profile": "MEDIUM", "max_image_size": 2400, "max_features": 8192, "matcher": "sequential", "use_gpu": 1},
            "LOW": {"profile": "LOW", "max_image_size": 1600, "max_features": 8000, "matcher": "exhaustive", "use_gpu": 1},
            "CPU_SAFE": {"profile": "CPU_SAFE", "max_image_size": 1600, "max_features": 8000, "matcher": "exhaustive", "use_gpu": 0},
        },
        "retry_count": 2,
        "vram_watchdog": {"threshold": 0.9, "poll_interval": 5, "downscale_factor": 0.75},
        "dense_engine": "colmap",
        "colmap": {"mapper_ba_global_max_iter": 30, "mapper_ba_local_max_iter": 20},
    }


def load_config(override_path: str | Path | None = None) -> dict:
    """
    Load config: default.yaml + optional override file + env MAPFREE_CONFIG.
    Returns merged dict. Cached after first call unless override_path is given.
    """
    global _CACHE
    if override_path is not None:
        _CACHE = None

    if _CACHE is not None:
        return _CACHE

    base = _defaults()
    default_file = _CONFIG_DIR / "default.yaml"
    if default_file.exists():
        base = _deep_merge(base, _load_yaml(default_file))

    env_path = os.environ.get("MAPFREE_CONFIG")
    if env_path and Path(env_path).exists():
        base = _deep_merge(base, _load_yaml(Path(env_path)))

    if override_path is not None:
        p = Path(override_path)
        if p.exists():
            base = _deep_merge(base, _load_yaml(p))

    # Allow only colmap | openmvs for dense_engine (env MAPFREE_DENSE_ENGINE overrides)
    dense = os.environ.get("MAPFREE_DENSE_ENGINE", "").strip().lower() or str(base.get("dense_engine") or "colmap").strip().lower()
    if dense not in ("colmap", "openmvs"):
        base["dense_engine"] = "colmap"
    else:
        base["dense_engine"] = dense

    _CACHE = base
    return base


def get_config(override_path: str | Path | None = None) -> dict:
    """Alias for load_config; use for read-only access."""
    return load_config(override_path)


def reset_config() -> None:
    """Clear cache (e.g. for tests)."""
    global _CACHE
    _CACHE = None
