"""
Hardware detection for installer: OS, CPU, RAM, GPU, and recommended profiles.
Runs before MapFree is installed to choose COLMAP/OpenMVS variants.
"""
import logging
import os
import re
import subprocess
import sys
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

from mapfree.utils.hardware import detect_ram_gb

logger = logging.getLogger(__name__)

# Profile and variant literals
OS_NAMES = ("windows", "linux", "macos")
PROFILES = ("high", "medium", "low", "cpu_only")
COLMAP_VARIANTS = ("cuda", "no_cuda")
OPENMVS_VARIANTS = ("cuda", "opencl", "cpu")
GPU_VENDORS = ("nvidia", "amd", "intel", "unknown")


def _get_os_and_version() -> tuple[str, str]:
    """Return (os, os_version) with os in OS_NAMES."""
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["wmic", "os", "get", "Caption", "/value"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if out.returncode == 0 and out.stdout:
                m = re.search(r"Caption=(.+)", out.stdout)
                if m:
                    return ("windows", m.group(1).strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
            logger.debug("wmic os failed: %s", e)
        try:
            import platform as plat
            return ("windows", plat.platform(terse=True) or "Windows")
        except Exception:
            return ("windows", "Windows")
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                return ("macos", f"macOS {out.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        return ("macos", "macOS")
    # Linux
    try:
        with open("/etc/os-release", "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        name = ""
        version = ""
        for line in content.splitlines():
            if line.startswith("PRETTY_NAME="):
                val = line.split("=", 1)[1].strip().strip('"')
                return ("linux", val)
            if line.startswith("NAME="):
                name = line.split("=", 1)[1].strip().strip('"')
            if line.startswith("VERSION_ID="):
                version = line.split("=", 1)[1].strip().strip('"')
        if name or version:
            return ("linux", f"{name} {version}".strip() or "Linux")
    except OSError:
        pass
    return ("linux", "Linux")


def _get_cpu_info() -> dict[str, Any]:
    """Return dict with name, cores, arch (x64 or arm64)."""
    import platform as plat
    name = plat.processor() or plat.machine() or "Unknown CPU"
    if not name or name == plat.machine():
        # Fallback: uname
        try:
            name = os.uname().machine if hasattr(os, "uname") else plat.machine()
        except OSError:
            name = plat.machine() or "Unknown"
    cores = os.cpu_count()
    if cores is None and psutil is not None:
        try:
            cores = psutil.cpu_count()
        except Exception:
            cores = 1
    if cores is None:
        cores = 1
    machine = plat.machine().lower()
    if "aarch64" in machine or "arm64" in machine or "armv8" in machine:
        arch = "arm64"
    else:
        arch = "x64"
    return {"name": name.strip() or "Unknown CPU", "cores": int(cores), "arch": arch}


def _parse_vram_bytes(value: Any) -> int:
    """Parse AdapterRAM (bytes) or string to MB. Windows wmic returns bytes."""
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, value // (1024 * 1024))
    s = str(value).strip()
    if not s or s == "":
        return 0
    try:
        n = int(re.sub(r"[^\d]", "", s) or "0")
        if "kb" in s.lower() or "k" == s[-1:].lower():
            return n // 1024
        if "gb" in s.lower() or "g" == s[-1:].lower():
            return n * 1024
        return n // (1024 * 1024)
    except (ValueError, TypeError):
        return 0


def _vendor_from_name(name: str) -> str:
    """Infer vendor from GPU name."""
    n = (name or "").lower()
    if "nvidia" in n:
        return "nvidia"
    if "amd" in n or "radeon" in n:
        return "amd"
    if "intel" in n:
        return "intel"
    return "unknown"


def _detect_gpu_windows() -> list[dict[str, Any]]:
    """Detect GPUs on Windows via wmic and optionally nvidia-smi for CUDA."""
    gpus: list[dict[str, Any]] = []
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        out = subprocess.run(
            [
                "wmic",
                "path",
                "win32_VideoController",
                "get",
                "Name,AdapterRAM",
                "/format:csv",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=creationflags,
        )
        if out.returncode != 0 or not out.stdout.strip():
            raise ValueError("wmic returned no output")
        lines = [ln.strip() for ln in out.stdout.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            raise ValueError("wmic csv too short")
        header = [h.strip() for h in lines[0].split(",")]
        name_idx = next((i for i, h in enumerate(header) if "name" in h.lower()), 0)
        ram_idx = next((i for i, h in enumerate(header) if "adapterram" in h.lower()), 1)
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",", maxsplit=max(name_idx, ram_idx) + 1)]
            name = parts[name_idx] if name_idx < len(parts) else "Unknown"
            ram_val = parts[ram_idx] if ram_idx < len(parts) else None
            vram_mb = _parse_vram_bytes(ram_val)
            vendor = _vendor_from_name(name)
            gpus.append({
                "name": name or "Unknown",
                "vendor": vendor,
                "vram_mb": vram_mb,
                "cuda_capable": False,
                "cuda_version": None,
                "opencl_capable": vendor in ("amd", "intel") or vendor == "unknown",
            })
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("wmic VideoController failed: %s", e)
    # Enrich with nvidia-smi for NVIDIA: CUDA, VRAM
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creationflags,
        )
        if out.returncode == 0 and out.stdout.strip():
            cuda_version = _get_cuda_version_from_nvidia_smi(creationflags)
            nvidia_lines = out.stdout.strip().split("\n")
            nvidia_indices = [i for i, g in enumerate(gpus) if _vendor_from_name(g["name"]) == "nvidia"]
            for idx, line in enumerate(nvidia_lines):
                parts = [p.strip() for p in line.split(",", 2)]
                gname = parts[0] if parts else "NVIDIA GPU"
                vram_s = parts[1] if len(parts) > 1 else "0"
                vram_mb = int(re.sub(r"[^\d]", "", vram_s) or "0")
                if idx < len(nvidia_indices):
                    gpus[nvidia_indices[idx]]["vram_mb"] = vram_mb
                    gpus[nvidia_indices[idx]]["cuda_capable"] = cuda_version is not None
                    gpus[nvidia_indices[idx]]["cuda_version"] = cuda_version
                else:
                    gpus.append({
                        "name": gname,
                        "vendor": "nvidia",
                        "vram_mb": vram_mb,
                        "cuda_capable": cuda_version is not None,
                        "cuda_version": cuda_version,
                        "opencl_capable": True,
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return gpus


def _get_cuda_version_from_nvidia_smi(creationflags: int = 0) -> str | None:
    """Run nvidia-smi and parse CUDA Version: X.Y from output."""
    try:
        out = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creationflags,
        )
        if out.returncode != 0:
            return None
        m = re.search(r"CUDA Version:\s*(\d+\.\d+)", (out.stdout or "") + (out.stderr or ""))
        return m.group(1) if m else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def _detect_gpu_linux() -> list[dict[str, Any]]:
    """Detect GPUs on Linux via nvidia-smi and lspci."""
    gpus: list[dict[str, Any]] = []
    cuda_version = None
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            cuda_version = _get_cuda_version_from_nvidia_smi(0)
            for line in out.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",", 1)]
                gname = parts[0] if parts else "NVIDIA GPU"
                vram_s = parts[1] if len(parts) > 1 else "0"
                vram_mb = int(re.sub(r"[^\d]", "", vram_s) or "0")
                gpus.append({
                    "name": gname,
                    "vendor": "nvidia",
                    "vram_mb": vram_mb,
                    "cuda_capable": cuda_version is not None,
                    "cuda_version": cuda_version,
                    "opencl_capable": True,
                })
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    if not gpus:
        try:
            out = subprocess.run(
                ["lspci", "-vmm"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout:
                blocks = []
                current = {}
                for line in out.stdout.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if k == "Slot":
                            if current:
                                blocks.append(current)
                            current = {}
                        current[k] = v
                if current:
                    blocks.append(current)
                for blk in blocks:
                    if "VGA" not in (blk.get("Class") or ""):
                        continue
                    name = blk.get("Device") or "Unknown GPU"
                    vendor = _vendor_from_name(name)
                    if "Vendor" in blk:
                        v = blk["Vendor"]
                        if "NVIDIA" in v:
                            vendor = "nvidia"
                        elif "AMD" in v or "ATI" in v:
                            vendor = "amd"
                        elif "Intel" in v:
                            vendor = "intel"
                    gpus.append({
                        "name": name,
                        "vendor": vendor,
                        "vram_mb": 0,
                        "cuda_capable": False,
                        "cuda_version": None,
                        "opencl_capable": vendor in ("amd", "intel"),
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
    if not gpus:
        try:
            out = subprocess.run(
                ["sh", "-c", "glxinfo 2>/dev/null | grep -i 'OpenGL renderer'"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                name = out.stdout.strip().split(":", 1)[-1].strip()
                if name:
                    gpus.append({
                        "name": name,
                        "vendor": _vendor_from_name(name),
                        "vram_mb": 0,
                        "cuda_capable": False,
                        "cuda_version": None,
                        "opencl_capable": True,
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
    return gpus


def _detect_gpu_macos() -> list[dict[str, Any]]:
    """Detect GPU on macOS (Apple Silicon or Intel)."""
    gpus: list[dict[str, Any]] = []
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if out.returncode != 0 or not out.stdout:
            return gpus
        import json
        data = json.loads(out.stdout)
        for item in data.get("SPDisplaysDataType", []):
            name = item.get("_name") or item.get("sppci_model", "Apple GPU")
            vram = item.get("sppci_vram") or "0"
            vram_mb = int(re.sub(r"[^\d]", "", str(vram)) or "0")
            if "MB" in str(vram).upper():
                pass
            elif "GB" in str(vram).upper():
                vram_mb = vram_mb * 1024
            gpus.append({
                "name": name,
                "vendor": "intel" if "Intel" in name else "unknown",
                "vram_mb": vram_mb,
                "cuda_capable": False,
                "cuda_version": None,
                "opencl_capable": True,
            })
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, Exception):
        pass
    if not gpus:
        gpus.append({
            "name": "Apple GPU",
            "vendor": "unknown",
            "vram_mb": 0,
            "cuda_capable": False,
            "cuda_version": None,
            "opencl_capable": True,
        })
    return gpus


def _detect_gpus(os_name: str) -> list[dict[str, Any]]:
    """Dispatch GPU detection by OS."""
    if os_name == "windows":
        return _detect_gpu_windows()
    if os_name == "linux":
        return _detect_gpu_linux()
    if os_name == "macos":
        return _detect_gpu_macos()
    return []


def _compute_recommendations(info: dict[str, Any]) -> None:
    """Set recommended_profile, recommended_colmap, recommended_openmvs on info."""
    gpus = info.get("gpu") or []
    has_nvidia_cuda = any(
        g.get("vendor") == "nvidia" and g.get("cuda_capable") for g in gpus
    )
    best_vram = max((g.get("vram_mb") or 0 for g in gpus), default=0)
    has_any_gpu = len(gpus) > 0
    has_amd_intel = any(g.get("vendor") in ("amd", "intel") for g in gpus)

    if not has_any_gpu:
        info["recommended_profile"] = "cpu_only"
        info["recommended_colmap"] = "no_cuda"
        info["recommended_openmvs"] = "cpu"
        return
    if has_nvidia_cuda and best_vram >= 8 * 1024:
        info["recommended_profile"] = "high"
        info["recommended_colmap"] = "cuda"
        info["recommended_openmvs"] = "cuda"
        return
    if (has_nvidia_cuda and 4 * 1024 <= best_vram < 8 * 1024) or has_amd_intel:
        info["recommended_profile"] = "medium"
        info["recommended_colmap"] = "cuda" if has_nvidia_cuda else "no_cuda"
        info["recommended_openmvs"] = "cuda" if has_nvidia_cuda else "opencl"
        return
    if best_vram < 4 * 1024:
        info["recommended_profile"] = "low"
    else:
        info["recommended_profile"] = "medium"
    info["recommended_colmap"] = "cuda" if has_nvidia_cuda else "no_cuda"
    info["recommended_openmvs"] = "cuda" if has_nvidia_cuda else "opencl"
    if info["recommended_openmvs"] == "opencl" and not has_amd_intel:
        info["recommended_openmvs"] = "cpu"


def detect_system() -> dict[str, Any]:
    """
    Detect OS, CPU, RAM, GPU and compute recommended profile and variants.

    Returns a dict with: os, os_version, cpu, ram_gb, gpu,
    recommended_profile, recommended_colmap, recommended_openmvs.
    Suitable for running before MapFree is installed (installer use).
    """
    os_name, os_version = _get_os_and_version()
    cpu = _get_cpu_info()
    ram_gb = detect_ram_gb()
    gpu = _detect_gpus(os_name)
    info: dict[str, Any] = {
        "os": os_name,
        "os_version": os_version,
        "cpu": cpu,
        "ram_gb": round(ram_gb, 2),
        "gpu": gpu,
    }
    _compute_recommendations(info)
    return info
