"""
Hardware detection: RAM (psutil) and VRAM (nvidia-smi).
Returns a HardwareProfile for smart scaling and profile selection.
"""
import re
import subprocess
from dataclasses import dataclass
from typing import Tuple

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


@dataclass
class HardwareProfile:
    """RAM (GB) and VRAM (MB) for pipeline and engine tuning."""

    ram_gb: float
    vram_mb: int

    @property
    def vram_gb(self) -> float:
        return self.vram_mb / 1024.0


def detect_ram_gb() -> float:
    """Return total system RAM in GB. Uses psutil if available, else /proc/meminfo (Linux)."""
    if psutil is not None:
        try:
            return psutil.virtual_memory().total / (1024.0 ** 3)
        except Exception:
            pass
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


def detect_vram_mb() -> int:
    """Return total GPU VRAM in MB via nvidia-smi. 0 if no NVIDIA GPU or failure."""
    used, total = get_vram_usage()
    return total


def get_vram_usage() -> Tuple[int, int]:
    """Return (used_mb, total_mb) for GPU 0. (0, 0) if nvidia-smi fails."""
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
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


def get_hardware_profile() -> HardwareProfile:
    """Detect RAM and VRAM and return a HardwareProfile."""
    return HardwareProfile(ram_gb=detect_ram_gb(), vram_mb=detect_vram_mb())
