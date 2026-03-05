"""Tests for mapfree.utils.dependency_resolver."""
import os
from unittest.mock import patch

import pytest

from mapfree.utils.dependency_resolver import (
    DependencyPackage,
    DependencyResolver,
    COLMAP_VERSION,
    COLMAP_RELEASE_BASE,
    COLMAP_WINDOWS_CUDA_URL,
    COLMAP_WINDOWS_NO_CUDA_URL,
)


def test_dependency_package_dataclass():
    """DependencyPackage has all required fields."""
    p = DependencyPackage(
        name="COLMAP",
        version="3.13.0",
        download_url="https://example.com/colmap.zip",
        install_size_mb=180,
        required=True,
        install_method="zip_extract",
        install_args=[],
        verify_command="colmap -h",
        path_to_add="/opt/colmap",
    )
    assert p.name == "COLMAP"
    assert p.version == "3.13.0"
    assert p.required is True
    assert p.install_method == "zip_extract"
    assert p.path_to_add == "/opt/colmap"


def test_resolver_required_packages_returns_colmap():
    """get_required_packages returns exactly one package (COLMAP)."""
    system_info = {"os": "windows", "recommended_colmap": "no_cuda"}
    resolver = DependencyResolver(system_info)
    required = resolver.get_required_packages()
    assert len(required) == 1
    assert required[0].name == "COLMAP"
    assert required[0].required is True
    assert required[0].install_method == "zip_extract"


def test_get_colmap_download_url_cuda_windows():
    """get_colmap_download_url returns CUDA URL when recommended_colmap is cuda."""
    system_info = {"os": "windows", "recommended_colmap": "cuda"}
    resolver = DependencyResolver(system_info)
    url = resolver.get_colmap_download_url()
    assert "cuda" in url.lower()
    assert url == COLMAP_WINDOWS_CUDA_URL


def test_get_colmap_download_url_no_cuda_windows():
    """get_colmap_download_url returns no-CUDA URL when recommended_colmap is no_cuda."""
    system_info = {"os": "windows", "recommended_colmap": "no_cuda"}
    resolver = DependencyResolver(system_info)
    url = resolver.get_colmap_download_url()
    assert url == COLMAP_WINDOWS_NO_CUDA_URL
    assert COLMAP_VERSION in url


def test_get_colmap_download_url_default_no_cuda():
    """Missing recommended_colmap defaults to no_cuda."""
    system_info = {"os": "windows"}
    resolver = DependencyResolver(system_info)
    url = resolver.get_colmap_download_url()
    assert url == COLMAP_WINDOWS_NO_CUDA_URL


def test_required_package_uses_colmap_url_from_resolver():
    """Required COLMAP package uses URL from get_colmap_download_url."""
    system_info = {"os": "windows", "recommended_colmap": "cuda"}
    resolver = DependencyResolver(system_info)
    required = resolver.get_required_packages()
    assert required[0].download_url == resolver.get_colmap_download_url()
    assert "cuda" in required[0].download_url.lower()


def test_optional_packages_include_openmvs_pdal_gdal():
    """get_optional_packages returns OpenMVS, PDAL, GDAL."""
    system_info = {"os": "windows"}
    resolver = DependencyResolver(system_info)
    optional = resolver.get_optional_packages()
    names = [p.name for p in optional]
    assert "OpenMVS" in names
    assert "PDAL" in names
    assert "GDAL" in names
    assert all(not p.required for p in optional)


def test_optional_packages_openmvs_has_url_on_windows():
    """OpenMVS has non-empty download_url on Windows."""
    system_info = {"os": "windows"}
    resolver = DependencyResolver(system_info)
    optional = resolver.get_optional_packages()
    openmvs = next(p for p in optional if p.name == "OpenMVS")
    assert openmvs.download_url
    assert "openmvs" in openmvs.download_url.lower() or "OpenMVS" in openmvs.download_url


def test_linux_colmap_urls():
    """On Linux, get_colmap_download_url returns linux variant URLs."""
    system_info = {"os": "linux", "recommended_colmap": "cuda"}
    resolver = DependencyResolver(system_info)
    url = resolver.get_colmap_download_url()
    assert "linux" in url.lower()
    assert COLMAP_RELEASE_BASE in url
    system_info["recommended_colmap"] = "no_cuda"
    resolver2 = DependencyResolver(system_info)
    url2 = resolver2.get_colmap_download_url()
    assert "linux" in url2.lower()


def test_required_package_path_to_add_contains_deps_and_colmap():
    """Required COLMAP package has path_to_add containing deps and colmap."""
    system_info = {"os": "windows"}
    resolver = DependencyResolver(system_info)
    required = resolver.get_required_packages()
    path = required[0].path_to_add or ""
    assert "deps" in path
    assert "colmap" in path


@pytest.mark.skipif(os.name != "nt", reason="Windows-only path test")
def test_deps_root_env_override():
    """MAPFREE_DEPS_ROOT overrides default Windows deps root."""
    with patch.dict("os.environ", {"MAPFREE_DEPS_ROOT": "D:\\Custom"}):
        from mapfree.utils.dependency_resolver import _deps_root
        root = _deps_root()
    assert "Custom" in str(root)
    assert "deps" in str(root)
