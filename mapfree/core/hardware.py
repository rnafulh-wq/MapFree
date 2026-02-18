"""
Hardware detection: delegates to mapfree.utils.hardware (psutil + nvidia-smi).
Re-exports for backward compatibility. Profile/chunk mapping → profiles.py.
"""
from mapfree.utils import hardware as _hw

HardwareProfile = _hw.HardwareProfile
get_hardware_profile = _hw.get_hardware_profile


def detect_system_ram_gb() -> float:
    """Return total system RAM in GB. Uses psutil if available, else /proc/meminfo."""
    return _hw.detect_ram_gb()


def detect_gpu_vram() -> int:
    """Return total GPU VRAM in MB. Returns 0 if no NVIDIA GPU or nvidia-smi fails."""
    return _hw.detect_vram_mb()


def get_gpu_vram_usage() -> tuple[int, int]:
    """Return (used_mb, total_mb) for GPU 0. (0, 0) if nvidia-smi fails."""
    return _hw.get_vram_usage()
