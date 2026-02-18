"""
Pipeline and engine constants. No profile logic (see profiles.py).
Step registry, image extensions, env names, COLMAP/VRAM limits.
"""
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

# COLMAP / VRAM watchdog values moved to mapfree/config/default.yaml
