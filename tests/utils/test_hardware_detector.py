"""Tests for mapfree.utils.hardware_detector."""
from unittest.mock import patch

from mapfree.utils.hardware_detector import detect_system


REQUIRED_KEYS = (
    "os",
    "os_version",
    "cpu",
    "ram_gb",
    "gpu",
    "recommended_profile",
    "recommended_colmap",
    "recommended_openmvs",
)


def test_detect_system_returns_required_keys():
    """detect_system() returns a dict with all required top-level keys."""
    result = detect_system()
    assert isinstance(result, dict)
    for key in REQUIRED_KEYS:
        assert key in result, f"Missing key: {key}"


def test_cpu_info_populated():
    """CPU info has name, cores, and arch (x64 or arm64)."""
    result = detect_system()
    cpu = result["cpu"]
    assert isinstance(cpu, dict)
    assert "name" in cpu
    assert "cores" in cpu
    assert "arch" in cpu
    assert isinstance(cpu["name"], str)
    assert isinstance(cpu["cores"], int)
    assert cpu["cores"] >= 1
    assert cpu["arch"] in ("x64", "arm64")


def test_recommended_profile_cpu_only_when_no_gpu():
    """When no GPU is detected, recommended_profile is cpu_only and colmap is no_cuda."""
    with patch("mapfree.utils.hardware_detector._detect_gpus", return_value=[]):
        with patch("mapfree.utils.hardware_detector.detect_ram_gb", return_value=16.0):
            result = detect_system()
    assert result["recommended_profile"] == "cpu_only"
    assert result["recommended_colmap"] == "no_cuda"
    assert result["recommended_openmvs"] == "cpu"
    assert result["gpu"] == []


def test_recommended_colmap_cuda_when_nvidia_available():
    """When NVIDIA GPU with CUDA is present, recommended_colmap is cuda."""
    fake_gpu = [
        {
            "name": "NVIDIA GeForce RTX 3060",
            "vendor": "nvidia",
            "vram_mb": 12 * 1024,
            "cuda_capable": True,
            "cuda_version": "12.1",
            "opencl_capable": True,
        },
    ]
    with patch("mapfree.utils.hardware_detector._get_os_and_version", return_value=("windows", "Windows 11")):
        with patch("mapfree.utils.hardware_detector._get_cpu_info", return_value={"name": "Intel", "cores": 8, "arch": "x64"}):
            with patch("mapfree.utils.hardware_detector.detect_ram_gb", return_value=32.0):
                with patch("mapfree.utils.hardware_detector._detect_gpus", return_value=fake_gpu):
                    result = detect_system()
    assert result["recommended_colmap"] == "cuda"
    assert result["recommended_profile"] == "high"
    assert result["recommended_openmvs"] == "cuda"


def test_os_and_version_present():
    """Result has os in (windows, linux, macos) and non-empty os_version."""
    result = detect_system()
    assert result["os"] in ("windows", "linux", "macos")
    assert isinstance(result["os_version"], str)
    assert len(result["os_version"]) > 0


def test_ram_gb_non_negative():
    """ram_gb is a non-negative float."""
    result = detect_system()
    assert isinstance(result["ram_gb"], (int, float))
    assert result["ram_gb"] >= 0


def test_gpu_list_and_shape():
    """gpu is a list; each entry has name, vendor, vram_mb, cuda_capable, etc."""
    result = detect_system()
    assert isinstance(result["gpu"], list)
    for g in result["gpu"]:
        assert "name" in g
        assert "vendor" in g
        assert "vram_mb" in g
        assert "cuda_capable" in g
        assert "cuda_version" in g
        assert "opencl_capable" in g
        assert g["vendor"] in ("nvidia", "amd", "intel", "unknown")


def test_recommended_profile_values():
    """recommended_profile is one of high, medium, low, cpu_only."""
    result = detect_system()
    assert result["recommended_profile"] in ("high", "medium", "low", "cpu_only")


def test_recommended_colmap_values():
    """recommended_colmap is cuda or no_cuda."""
    result = detect_system()
    assert result["recommended_colmap"] in ("cuda", "no_cuda")


def test_recommended_openmvs_values():
    """recommended_openmvs is cuda, opencl, or cpu."""
    result = detect_system()
    assert result["recommended_openmvs"] in ("cuda", "opencl", "cpu")
