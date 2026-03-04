"""Tests for mapfree.utils.hardware."""
from unittest.mock import patch, MagicMock
import pytest

from mapfree.utils.hardware import (
    HardwareProfile,
    detect_ram_gb,
    get_vram_usage,
    get_hardware_profile,
)


class TestHardwareProfile:
    def test_creation(self):
        hp = HardwareProfile(ram_gb=16.0, vram_mb=4096)
        assert hp.ram_gb == 16.0
        assert hp.vram_mb == 4096

    def test_vram_gb(self):
        hp = HardwareProfile(ram_gb=8.0, vram_mb=2048)
        assert hp.vram_gb == pytest.approx(2.0)

    def test_zero_vram(self):
        hp = HardwareProfile(ram_gb=8.0, vram_mb=0)
        assert hp.vram_gb == 0.0


class TestDetectRamGb:
    def test_returns_float(self):
        ram = detect_ram_gb()
        assert isinstance(ram, float)
        assert ram >= 0.0

    def test_fallback_on_psutil_error(self, monkeypatch):
        import mapfree.utils.hardware as hw_mod
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.side_effect = Exception("error")
        monkeypatch.setattr(hw_mod, "psutil", mock_psutil)
        # Should not raise; returns 0.0 or proc/meminfo fallback
        ram = detect_ram_gb()
        assert isinstance(ram, float)

    def test_no_psutil_fallback(self, monkeypatch):
        import mapfree.utils.hardware as hw_mod
        monkeypatch.setattr(hw_mod, "psutil", None)
        ram = detect_ram_gb()
        assert isinstance(ram, float)


class TestGetVramUsage:
    def test_returns_tuple_int_int(self):
        used, total = get_vram_usage()
        assert isinstance(used, int)
        assert isinstance(total, int)
        assert used >= 0 and total >= 0

    def test_no_nvidia_smi_returns_zero(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            used, total = get_vram_usage()
        assert (used, total) == (0, 0)

    def test_timeout_returns_zero(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 5)):
            used, total = get_vram_usage()
        assert (used, total) == (0, 0)

    def test_nonzero_exit_returns_zero(self):
        mock = MagicMock()
        mock.returncode = 1
        mock.stdout = ""
        with patch("subprocess.run", return_value=mock):
            used, total = get_vram_usage()
        assert (used, total) == (0, 0)

    def test_valid_output_parsed(self):
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = "1024, 4096\n"
        with patch("subprocess.run", return_value=mock):
            used, total = get_vram_usage()
        assert used == 1024
        assert total == 4096


class TestGetHardwareProfile:
    def test_returns_hardware_profile(self):
        profile = get_hardware_profile()
        assert isinstance(profile, HardwareProfile)
        assert profile.ram_gb >= 0.0
        assert profile.vram_mb >= 0
