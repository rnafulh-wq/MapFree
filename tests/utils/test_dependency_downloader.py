"""Tests for mapfree.utils.dependency_downloader."""
from unittest.mock import MagicMock, patch
import zipfile

from mapfree.utils.dependency_resolver import DependencyPackage
from mapfree.utils.dependency_downloader import DependencyDownloader


def _make_package(
    name="COLMAP",
    download_url="https://example.com/colmap.zip",
    install_method="zip_extract",
    verify_command="colmap -h",
) -> DependencyPackage:
    return DependencyPackage(
        name=name,
        version="3.13.0",
        download_url=download_url,
        install_size_mb=180,
        required=True,
        install_method=install_method,
        install_args=[],
        verify_command=verify_command,
        path_to_add="/opt/colmap",
    )


def test_download_with_mock_server(tmp_path):
    """Download succeeds with mocked urlopen returning bytes."""
    data = b"fake zip content here"
    package = _make_package(download_url="https://example.com/colmap.zip")

    def fake_urlopen(req, timeout=None):
        resp = MagicMock()
        resp.headers = {"Content-Length": str(len(data))}
        resp.status = 200
        chunks = [data, b""]

        def read(size=8192):
            return chunks.pop(0) if chunks else b""
        resp.read = read
        resp.__enter__ = lambda self: self
        resp.__exit__ = lambda self, *a: None
        return resp

    with patch("mapfree.utils.dependency_downloader.urlopen", side_effect=fake_urlopen):
        downloader = DependencyDownloader()
        path = downloader.download(package, tmp_path)
    assert path.exists()
    assert path.read_bytes() == data


def test_progress_callback_called(tmp_path):
    """progress_callback is invoked with (downloaded, total)."""
    data = b"x" * 20000
    package = _make_package()
    progress_calls = []

    def fake_urlopen(req, timeout=None):
        resp = MagicMock()
        resp.headers = {"Content-Length": str(len(data))}
        resp.status = 200
        it = iter([data[:10000], data[10000:]])

        def read(size=8192):
            try:
                return next(it)
            except StopIteration:
                return b""
        resp.read = read
        resp.__enter__ = lambda self: self
        resp.__exit__ = lambda self, *a: None
        return resp

    with patch("mapfree.utils.dependency_downloader.urlopen", side_effect=fake_urlopen):
        downloader = DependencyDownloader()

        def cb(done, total):
            progress_calls.append((done, total))

        downloader.download(package, tmp_path, progress_callback=cb)
    assert len(progress_calls) >= 1
    assert progress_calls[-1][0] == len(data)
    assert progress_calls[-1][1] == len(data)


def test_retry_on_failure(tmp_path):
    """Download retries on failure and raises after exhausting retries."""
    package = _make_package()
    with patch("mapfree.utils.dependency_downloader.urlopen", side_effect=OSError("net")) as m:
        with patch("time.sleep"):
            downloader = DependencyDownloader()
            try:
                downloader.download(package, tmp_path)
            except OSError as e:
                assert "net" in str(e)
            else:
                raise AssertionError("Expected OSError")
    from mapfree.utils.dependency_downloader import RETRY_ATTEMPTS
    assert m.call_count == RETRY_ATTEMPTS


def test_retry_then_success(tmp_path):
    """Download succeeds on second attempt after first failure."""
    package = _make_package()
    data = b"ok"
    resp = MagicMock()
    resp.headers = {"Content-Length": "2"}
    resp.status = 200
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    first_read = [True]

    def read_once(size=8192):
        if first_read[0]:
            first_read[0] = False
            return data
        return b""
    resp.read = read_once

    with patch("mapfree.utils.dependency_downloader.urlopen", side_effect=[OSError("x"), resp]):
        with patch("time.sleep"):
            downloader = DependencyDownloader()
            path = downloader.download(package, tmp_path)
    assert path.read_bytes() == data


def test_verify_success():
    """verify returns True when verify_command exits 0."""
    package = _make_package(verify_command="python -c \"exit(0)\"")
    downloader = DependencyDownloader()
    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        assert downloader.verify(package) is True


def test_verify_failure():
    """verify returns False when verify_command exits non-zero or not found."""
    package = _make_package(verify_command="nonexistent_bin_xyz -h")
    downloader = DependencyDownloader()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert downloader.verify(package) is False

    with patch("subprocess.run", return_value=MagicMock(returncode=1)):
        assert downloader.verify(package) is False


def test_download_no_url_raises(tmp_path):
    """download raises ValueError when package has no download_url."""
    package = _make_package(download_url="")
    downloader = DependencyDownloader()
    try:
        downloader.download(package, tmp_path)
    except ValueError as e:
        assert "download_url" in str(e)
    else:
        raise AssertionError("Expected ValueError")


def test_install_zip_extract(tmp_path):
    """install with zip_extract extracts archive to dest_dir."""
    zip_path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("colmap/colmap.exe", b"fake")
    package = _make_package(install_method="zip_extract")
    downloader = DependencyDownloader()
    ok = downloader.install(package, zip_path)
    assert ok is True
    assert (tmp_path / "colmap" / "colmap.exe").exists()


def test_verify_empty_command_returns_false():
    """verify returns False when verify_command is empty."""
    package = _make_package(verify_command="")
    assert DependencyDownloader().verify(package) is False
