"""Tests for mapfree.utils.hardware_detector."""
from unittest.mock import MagicMock, patch

from mapfree.utils.hardware_detector import (
    detect_system,
    _get_os_and_version,
    _get_cpu_info,
    _parse_vram_bytes,
    _vendor_from_name,
    _detect_gpu_windows,
    _detect_gpu_linux,
    _detect_gpu_macos,
    _get_cuda_version_from_nvidia_smi,
    _detect_gpus,
    _compute_recommendations,
)


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


# ---- _get_os_and_version ----
def test_get_os_and_version_windows_wmic_success():
    """Windows: wmic returns Caption -> (windows, version)."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "Caption=Microsoft Windows 11 Pro\n"
    with patch("sys.platform", "win32"):
        with patch("subprocess.run", return_value=mock_run):
            os_name, os_version = _get_os_and_version()
    assert os_name == "windows"
    assert "Windows" in os_version


def test_get_os_and_version_windows_wmic_fail_platform_fallback():
    """Windows: wmic fails -> platform.platform(terse=True) or 'Windows'."""
    with patch("sys.platform", "win32"):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("platform.platform", return_value="Windows-10-10.0.19041"):
                with patch("mapfree.utils.hardware_detector.sys.platform", "win32"):
                    os_name, os_version = _get_os_and_version()
    assert os_name == "windows"
    assert os_version


def test_get_os_and_version_macos_sw_vers_success():
    """macOS: sw_vers returns version -> (macos, macOS X.Y)."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "14.0\n"
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run", return_value=mock_run):
            os_name, os_version = _get_os_and_version()
    assert os_name == "macos"
    assert "14" in os_version


def test_get_os_and_version_macos_sw_vers_fail():
    """macOS: sw_vers fails -> (macos, macOS)."""
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            os_name, os_version = _get_os_and_version()
    assert os_name == "macos"
    assert os_version == "macOS"


def test_get_os_and_version_linux_os_release_pretty_name():
    """Linux: /etc/os-release has PRETTY_NAME -> (linux, pretty)."""
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value.read.return_value = (
        'PRETTY_NAME="Ubuntu 22.04 LTS"\n'
    )
    with patch("sys.platform", "linux"):
        with patch("builtins.open", mock_open):
            os_name, os_version = _get_os_and_version()
    assert os_name == "linux"
    assert "Ubuntu" in os_version or "22.04" in os_version


def test_get_os_and_version_linux_os_release_name_version():
    """Linux: os-release has NAME and VERSION_ID -> (linux, name version)."""
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value.read.return_value = (
        'NAME="Debian"\nVERSION_ID="11"\n'
    )
    with patch("sys.platform", "linux"):
        with patch("builtins.open", mock_open):
            os_name, os_version = _get_os_and_version()
    assert os_name == "linux"
    assert "Debian" in os_version or "11" in os_version


def test_get_os_and_version_linux_os_release_missing():
    """Linux: open(/etc/os-release) raises -> (linux, Linux)."""
    with patch("sys.platform", "linux"):
        with patch("builtins.open", side_effect=OSError):
            os_name, os_version = _get_os_and_version()
    assert os_name == "linux"
    assert os_version == "Linux"


# ---- _get_cpu_info ----
def test_get_cpu_info_x64():
    """CPU: machine is x86_64 -> arch x64."""
    with patch("platform.processor", return_value="Intel Core i7"):
        with patch("platform.machine", return_value="AMD64"):
            with patch("os.cpu_count", return_value=8):
                cpu = _get_cpu_info()
    assert cpu["arch"] == "x64"
    assert cpu["cores"] == 8
    assert "Intel" in cpu["name"] or cpu["name"]


def test_get_cpu_info_arm64():
    """CPU: machine is aarch64 -> arch arm64."""
    with patch("platform.processor", return_value=""):
        with patch("platform.machine", return_value="aarch64"):
            with patch("os.cpu_count", return_value=4):
                cpu = _get_cpu_info()
    assert cpu["arch"] == "arm64"


def test_get_cpu_info_cores_psutil_fallback():
    """CPU: os.cpu_count None -> use psutil.cpu_count."""
    import mapfree.utils.hardware_detector as hd
    with patch("os.cpu_count", return_value=None):
        with patch.object(hd, "psutil") as mps:
            mps.cpu_count.return_value = 16
            with patch("platform.processor", return_value="CPU"):
                with patch("platform.machine", return_value="x86_64"):
                    cpu = _get_cpu_info()
    assert cpu["cores"] == 16


# ---- _parse_vram_bytes, _vendor_from_name ----
def test_parse_vram_bytes_none():
    """_parse_vram_bytes(None) -> 0."""
    assert _parse_vram_bytes(None) == 0


def test_parse_vram_bytes_int_bytes():
    """_parse_vram_bytes(int bytes) -> MB."""
    assert _parse_vram_bytes(6442450944) == 6144


def test_parse_vram_bytes_string_gb():
    """_parse_vram_bytes('8 GB') -> 8192."""
    assert _parse_vram_bytes("8 GB") == 8192


def test_vendor_from_name_nvidia_amd_intel_unknown():
    """_vendor_from_name infers nvidia, amd, intel, unknown."""
    assert _vendor_from_name("NVIDIA GeForce RTX 3060") == "nvidia"
    assert _vendor_from_name("AMD Radeon RX 6800") == "amd"
    assert _vendor_from_name("Intel UHD 630") == "intel"
    assert _vendor_from_name("Mesa XYZ") == "unknown"


# ---- _detect_gpu_windows ----
def test_detect_gpu_windows_wmic_csv_returns_gpus():
    """Windows: wmic VideoController csv returns at least one GPU."""
    wmic_out = MagicMock()
    wmic_out.returncode = 0
    wmic_out.stdout = "Node,Name,AdapterRAM\n0,NVIDIA GeForce RTX 3060,6442450944\n"
    nvidia_query = MagicMock()
    nvidia_query.returncode = 0
    nvidia_query.stdout = "NVIDIA GeForce RTX 3060, 6144\n"
    nvidia_full = MagicMock()
    nvidia_full.returncode = 0
    nvidia_full.stdout = "CUDA Version: 12.1\n"
    nvidia_full.stderr = ""
    with patch("sys.platform", "win32"):
        with patch("subprocess.run", side_effect=[wmic_out, nvidia_query, nvidia_full]):
            gpus = _detect_gpu_windows()
    assert len(gpus) >= 1
    assert gpus[0]["name"]
    assert gpus[0]["vendor"] == "nvidia"
    assert gpus[0]["vram_mb"] >= 0


def test_detect_gpu_windows_wmic_fail_nvidia_smi_only():
    """Windows: wmic fails, nvidia-smi returns one GPU."""
    nvidia_query = MagicMock()
    nvidia_query.returncode = 0
    nvidia_query.stdout = "NVIDIA GeForce RTX 3060, 6144\n"
    nvidia_full = MagicMock()
    nvidia_full.returncode = 0
    nvidia_full.stdout = "CUDA Version: 12.1\n"
    nvidia_full.stderr = ""
    with patch("sys.platform", "win32"):
        with patch("subprocess.run", side_effect=[FileNotFoundError, nvidia_query, nvidia_full]):
            gpus = _detect_gpu_windows()
    assert len(gpus) == 1
    assert gpus[0]["vendor"] == "nvidia"
    assert gpus[0]["cuda_version"] == "12.1"


def test_get_cuda_version_from_nvidia_smi_parsed():
    """_get_cuda_version_from_nvidia_smi parses CUDA Version from stdout."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "NVIDIA-SMI 525.60  CUDA Version: 12.0\n"
    mock_run.stderr = ""
    with patch("subprocess.run", return_value=mock_run):
        ver = _get_cuda_version_from_nvidia_smi(0)
    assert ver == "12.0"


def test_get_cuda_version_from_nvidia_smi_fail():
    """_get_cuda_version_from_nvidia_smi returns None on failure."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        ver = _get_cuda_version_from_nvidia_smi(0)
    assert ver is None


# ---- _detect_gpu_linux ----
def test_detect_gpu_linux_nvidia_smi_returns_gpu():
    """Linux: nvidia-smi returns name,memory -> one NVIDIA GPU."""
    nvidia_query = MagicMock()
    nvidia_query.returncode = 0
    nvidia_query.stdout = "NVIDIA GeForce GTX 1660, 6144\n"
    nvidia_full = MagicMock()
    nvidia_full.returncode = 0
    nvidia_full.stdout = "CUDA Version: 11.8\n"
    nvidia_full.stderr = ""
    with patch("subprocess.run", side_effect=[nvidia_query, nvidia_full]):
        gpus = _detect_gpu_linux()
    assert len(gpus) == 1
    assert gpus[0]["vendor"] == "nvidia"
    assert gpus[0]["vram_mb"] == 6144


def test_detect_gpu_linux_lspci_vga_fallback():
    """Linux: nvidia-smi fails, lspci -vmm has VGA block -> GPU from lspci."""
    lspci_out = MagicMock()
    lspci_out.returncode = 0
    lspci_out.stdout = (
        "Slot:\t00:02.0\nClass:\tVGA compatible controller\n"
        "Vendor:\tIntel Corporation\nDevice:\tIntel UHD 630\n"
    )
    with patch("subprocess.run", side_effect=[FileNotFoundError, lspci_out]):
        gpus = _detect_gpu_linux()
    assert len(gpus) >= 1
    assert "Intel" in gpus[0]["name"] or gpus[0]["vendor"] == "intel"


def test_detect_gpu_linux_glxinfo_fallback():
    """Linux: nvidia-smi and lspci fail, glxinfo returns renderer -> one GPU."""
    glx_out = MagicMock()
    glx_out.returncode = 0
    glx_out.stdout = "OpenGL renderer string: Mesa Intel(R) UHD Graphics 630\n"
    with patch("subprocess.run", side_effect=[FileNotFoundError, FileNotFoundError, glx_out]):
        gpus = _detect_gpu_linux()
    assert len(gpus) == 1
    assert "Intel" in gpus[0]["name"] or gpus[0]["vendor"] == "intel"


# ---- _detect_gpu_macos ----
def test_detect_gpu_macos_system_profiler_json():
    """macOS: system_profiler SPDisplaysDataType -json returns GPUs."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = '{"SPDisplaysDataType":[{"_name":"Apple M1","sppci_vram":"8 GB"}]}'
    with patch("subprocess.run", return_value=mock_run):
        gpus = _detect_gpu_macos()
    assert len(gpus) >= 1
    assert gpus[0]["vram_mb"] == 8192  # 8 * 1024


def test_detect_gpu_macos_empty_fallback_apple_gpu():
    """macOS: system_profiler returns empty -> fallback Apple GPU."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = '{"SPDisplaysDataType":[]}'
    with patch("subprocess.run", return_value=mock_run):
        gpus = _detect_gpu_macos()
    assert len(gpus) == 1
    assert "Apple" in gpus[0]["name"]


# ---- _detect_gpus dispatch ----
def test_detect_gpus_dispatch_windows_linux_macos():
    """_detect_gpus(win/linux/mac) calls correct detector."""
    with patch("mapfree.utils.hardware_detector._detect_gpu_windows", return_value=[{"name": "W"}]) as mw:
        assert len(_detect_gpus("windows")) == 1
        mw.assert_called_once()
    with patch("mapfree.utils.hardware_detector._detect_gpu_linux", return_value=[{"name": "L"}]) as ml:
        assert len(_detect_gpus("linux")) == 1
        ml.assert_called_once()
    with patch("mapfree.utils.hardware_detector._detect_gpu_macos", return_value=[{"name": "M"}]) as mm:
        assert len(_detect_gpus("macos")) == 1
        mm.assert_called_once()
    assert _detect_gpus("unknown") == []


# ---- _compute_recommendations ----
def test_compute_recommendations_medium_nvidia_4_8gb():
    """recommended_profile medium when Nvidia 4-8GB VRAM with CUDA."""
    info = {
        "gpu": [{
            "vendor": "nvidia",
            "vram_mb": 6 * 1024,
            "cuda_capable": True,
        }],
    }
    _compute_recommendations(info)
    assert info["recommended_profile"] == "medium"
    assert info["recommended_colmap"] == "cuda"


def test_compute_recommendations_low_vram():
    """recommended_profile low when GPU VRAM < 4GB."""
    info = {
        "gpu": [{
            "vendor": "nvidia",
            "vram_mb": 2 * 1024,
            "cuda_capable": True,
        }],
    }
    _compute_recommendations(info)
    assert info["recommended_profile"] == "low"


def test_compute_recommendations_amd_opencl_then_cpu():
    """recommended_openmvs opencl for AMD; if no amd/intel then cpu."""
    info = {
        "gpu": [{"vendor": "amd", "vram_mb": 4096, "cuda_capable": False}],
    }
    _compute_recommendations(info)
    assert info["recommended_openmvs"] == "opencl"
