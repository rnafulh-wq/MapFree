"""
Hardware detection only. Uses stdlib (subprocess).
Fails gracefully if nvidia-smi is not available.
Profile/chunk mapping → profiles.py; output checks → validation.py.
"""
import re
import subprocess


def detect_system_ram_gb() -> float:
    """Return total system RAM in GB. Uses /proc/meminfo on Linux; 0 on failure."""
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    kb = int(parts[1])
                    return kb / (1024.0 * 1024.0)
    except (FileNotFoundError, ValueError):
        pass
    return 0.0


def detect_gpu_vram() -> int:
    """Return total GPU VRAM in MB. Returns 0 if no NVIDIA GPU or nvidia-smi fails."""
    _used, total = get_gpu_vram_usage()
    return total


def get_gpu_vram_usage() -> tuple[int, int]:
    """
    Return (used_mb, total_mb) for GPU 0.
    (0, 0) if no NVIDIA GPU or nvidia-smi fails.
    Used for VRAM watchdog (e.g. used/total > 0.9).
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return (0, 0)
        line = out.stdout.strip().split("\n")[0].strip()
        numbers = re.findall(r"\d+", line)
        if len(numbers) >= 2:
            return (int(numbers[0]), int(numbers[1]))
        if len(numbers) == 1:
            return (0, int(numbers[0]))
        return (0, 0)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return (0, 0)
