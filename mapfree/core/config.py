"""
Pipeline and engine constants. No profile logic (see profiles.py).
Step registry, image extensions, env names, COLMAP/VRAM limits.
"""
from typing import Optional
# ---------------------------------------------------------------------------
# Step registry — single source of truth (plugin-friendly)
# ---------------------------------------------------------------------------
PIPELINE_STEPS = [
    "feature_extraction",
    "matching",
    "sparse",
    "dense",
    "mesh",
]

CHUNK_STEPS = ("feature_extraction", "matching", "mapping")
COMPLETION_STEPS = ("feature_extraction", "matching", "sparse", "dense")

# ---------------------------------------------------------------------------
# Image extensions
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

# ---------------------------------------------------------------------------
# Env var names
# ---------------------------------------------------------------------------
ENV_CHUNK_SIZE = "MAPFREE_CHUNK_SIZE"
ENV_LOG_LEVEL = "MAPFREE_LOG_LEVEL"
ENV_LOG_DIR = "MAPFREE_LOG_DIR"

# ---------------------------------------------------------------------------
# Quality presets (Metashape-style): single downscale for feature + dense
# ---------------------------------------------------------------------------
QUALITY_PRESETS = {
    "high": 1,    # full resolution (still VRAM-limited)
    "medium": 2,  # image size ÷ 2
    "low": 4,     # image size ÷ 4
}

# VRAM thresholds (MB) for auto quality recommendation (aligned with colmap_engine dense logic)
VRAM_MB_HIGH = 6144   # >= 6 GB: high quality
VRAM_MB_MEDIUM = 2560  # >= 2.5 GB: medium quality; below -> low


def recommend_quality_from_hardware(vram_mb: Optional[int] = None, ram_gb: Optional[float] = None) -> str:
    """
    Recommend smart-scaling quality from VRAM (and optionally RAM).
    Uses VRAM thresholds aligned with COLMAP dense stage (patch_match max_size).
    Returns "high" | "medium" | "low".
    """
    if vram_mb is None or ram_gb is None:
        from mapfree.utils.hardware import get_hardware_profile
        h = get_hardware_profile()
        if vram_mb is None:
            vram_mb = h.vram_mb
        if ram_gb is None:
            ram_gb = h.ram_gb
    if vram_mb >= VRAM_MB_HIGH:
        return "high"
    if vram_mb >= VRAM_MB_MEDIUM:
        return "medium"
    return "low"


# COLMAP / VRAM watchdog values moved to mapfree/config/default.yaml
