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

# COLMAP / VRAM watchdog values moved to mapfree/config/default.yaml
