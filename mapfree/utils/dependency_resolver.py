"""
Dependency resolver for MapFree installer: selects packages from hardware_detector output.
Returns required (COLMAP) and optional (OpenMVS, PDAL, GDAL) packages with download URLs.
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# COLMAP GitHub Releases (update version as needed; check asset names at release page)
COLMAP_VERSION = "3.13.0"
COLMAP_RELEASE_BASE = (
    f"https://github.com/colmap/colmap/releases/download/{COLMAP_VERSION}"
)
# Windows: pre-built assets from GitHub (3.13+ use colmap-x64-windows-*.zip)
COLMAP_WINDOWS_CUDA_URL = f"{COLMAP_RELEASE_BASE}/colmap-x64-windows-cuda.zip"
COLMAP_WINDOWS_NO_CUDA_URL = f"{COLMAP_RELEASE_BASE}/colmap-x64-windows-nocuda.zip"
# OpenMVS: community pre-built or GitHub releases
OPENMVS_VERSION = "2.2.0"
OPENMVS_WINDOWS_URL = (
    f"https://github.com/cdcseacave/openMVS/releases/download/v{OPENMVS_VERSION}/"
    f"OpenMVS-{OPENMVS_VERSION}-windows.zip"
)


# Default deps root: C:\MapFree\deps (Windows) or ~/.mapfree/deps (Linux/macOS)


def _deps_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("MAPFREE_DEPS_ROOT", "C:\\MapFree")
        return Path(base) / "deps"
    return Path.home() / ".mapfree" / "deps"


@dataclass
class DependencyPackage:
    """
    One dependency package to download and install.

    Attributes:
        name: Display name (e.g. "COLMAP", "OpenMVS").
        version: Version string.
        download_url: URL to download the package.
        install_size_mb: Approximate size in MB.
        required: True if must be installed.
        install_method: One of zip_extract, exe_silent, choco, apt, conda.
        install_args: Arguments for silent install (e.g. [] for zip_extract).
        verify_command: Command to run to verify install (e.g. "colmap -h").
        path_to_add: Path to add to PATH after install, or None.
    """

    name: str
    version: str
    download_url: str
    install_size_mb: int
    required: bool
    install_method: str
    install_args: list[str]
    verify_command: str
    path_to_add: str | None


class DependencyResolver:
    """
    Resolves which dependencies to install based on hardware_detector system info.

    Uses recommended_colmap and recommended_openmvs from system_info to pick
    COLMAP variant (cuda vs no_cuda) and optional packages.
    """

    def __init__(self, system_info: dict[str, Any]) -> None:
        """
        Args:
            system_info: Dict from hardware_detector.detect_system() with keys
                os, recommended_colmap, recommended_openmvs, etc.
        """
        self.system = system_info
        self._deps_root = _deps_root()
        self._os = (system_info.get("os") or "windows").lower()

    def get_required_packages(self) -> list[DependencyPackage]:
        """Return list of packages that must be installed (COLMAP only)."""
        colmap_url = self.get_colmap_download_url()
        colmap_dir = self._deps_root / "colmap"
        verify = "colmap -h" if self._os != "win32" else "colmap.bat -h"
        path_to_add = str(colmap_dir)
        return [
            DependencyPackage(
                name="COLMAP",
                version=COLMAP_VERSION,
                download_url=colmap_url,
                install_size_mb=180,
                required=True,
                install_method="zip_extract",
                install_args=[],
                verify_command=verify,
                path_to_add=path_to_add,
            ),
        ]

    def get_optional_packages(self) -> list[DependencyPackage]:
        """Return list of optional packages (OpenMVS, PDAL, GDAL)."""
        optional: list[DependencyPackage] = []
        # OpenMVS
        openmvs_dir = self._deps_root / "openmvs"
        optional.append(
            DependencyPackage(
                name="OpenMVS",
                version=OPENMVS_VERSION,
                download_url=OPENMVS_WINDOWS_URL if self._os == "windows" else "",
                install_size_mb=85,
                required=False,
                install_method="zip_extract",
                install_args=[],
                verify_command="OpenMVS.exe -h" if self._os == "windows" else "OpenMVS -h",
                path_to_add=str(openmvs_dir),
            ),
        )
        # PDAL (Windows: conda or MSI; Linux: apt)
        optional.append(
            DependencyPackage(
                name="PDAL",
                version="2.6.0",
                download_url="",
                install_size_mb=120,
                required=False,
                install_method="conda" if self._os == "windows" else "apt",
                install_args=["pdal"] if self._os == "windows" else ["pdal"],
                verify_command="pdal --version",
                path_to_add=None,
            ),
        )
        # GDAL
        optional.append(
            DependencyPackage(
                name="GDAL",
                version="3.8.0",
                download_url="",
                install_size_mb=80,
                required=False,
                install_method="conda" if self._os == "windows" else "apt",
                install_args=["gdal"] if self._os == "windows" else ["gdal-bin"],
                verify_command="gdalinfo --version",
                path_to_add=None,
            ),
        )
        return optional

    def get_colmap_download_url(self) -> str:
        """
        Return the COLMAP download URL for the current system.

        Uses recommended_colmap from system_info: "cuda" -> CUDA build,
        "no_cuda" -> CPU-only build. Defaults to no_cuda if key missing.
        """
        variant = (self.system.get("recommended_colmap") or "no_cuda").lower()
        if self._os == "windows":
            return (
                COLMAP_WINDOWS_CUDA_URL
                if variant == "cuda"
                else COLMAP_WINDOWS_NO_CUDA_URL
            )
        # Linux/macOS: often from package manager; placeholder URL for source/script
        if variant == "cuda":
            return f"{COLMAP_RELEASE_BASE}/COLMAP-{COLMAP_VERSION}-linux-cuda.tar.gz"
        return f"{COLMAP_RELEASE_BASE}/COLMAP-{COLMAP_VERSION}-linux.tar.gz"
