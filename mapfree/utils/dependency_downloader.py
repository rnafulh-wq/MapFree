"""
Dependency downloader for MapFree installer: download with progress, retry, and install.
"""
import logging
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mapfree.utils.dependency_resolver import DependencyPackage

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300
RETRY_ATTEMPTS = 3
CHUNK_SIZE = 8192


class DependencyDownloader:
    """
    Download dependency packages with progress tracking, resume, and retry.

    After download, install (zip_extract, exe_silent, choco, apt) and verify
    via the package's verify_command.
    """

    def download(
        self,
        package: DependencyPackage,
        dest_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        """
        Download package to dest_dir; return path to the downloaded file.

        Args:
            package: Package with download_url.
            dest_dir: Directory to save the file.
            progress_callback: Optional (bytes_downloaded, total_bytes) callback.
                total_bytes may be -1 if Content-Length is unknown.

        Returns:
            Path to the downloaded file.

        Raises:
            URLError: If download fails after retries.
            ValueError: If package has no download_url.
        """
        if not (package.download_url or "").strip():
            raise ValueError(f"Package {package.name} has no download_url")
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = package.download_url.rstrip("/").split("/")[-1].split("?")[0]
        if not filename:
            filename = f"{package.name.lower().replace(' ', '_')}.zip"
        out_path = dest_dir / filename
        existing_size = out_path.stat().st_size if out_path.exists() else 0
        last_error = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                return self._do_download(
                    package.download_url,
                    out_path,
                    progress_callback,
                    existing_size,
                )
            except HTTPError as e:
                last_error = e
                if e.code == 404:
                    raise URLError(
                        "URL tidak ditemukan (404). Asset release mungkin berubah. "
                        "Cek: %s" % package.download_url
                    ) from e
                logger.warning("Download attempt %s failed: %s", attempt + 1, e)
            except (URLError, OSError, TimeoutError) as e:
                last_error = e
                logger.warning("Download attempt %s failed: %s", attempt + 1, e)
            if last_error and attempt < RETRY_ATTEMPTS - 1:
                delay = 2 ** attempt
                time.sleep(delay)
        if last_error:
            raise last_error
        raise URLError("Download failed after retries")

    def _do_download(
        self,
        url: str,
        out_path: Path,
        progress_callback: Callable[[int, int], None] | None,
        start_byte: int,
    ) -> Path:
        request = Request(url)
        if start_byte > 0:
            request.add_header("Range", f"bytes={start_byte}-")
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT) as resp:
            total = -1
            cl = resp.headers.get("Content-Length")
            if cl is not None:
                try:
                    total = int(cl) + start_byte
                except ValueError:
                    pass
            # Server may ignore Range and return 200 with full body
            code = getattr(resp, "status", 200)
            if code == 200 and start_byte > 0:
                start_byte = 0
                total = int(cl) if cl else -1
            mode = "ab" if (start_byte > 0 and code == 206) else "wb"
            downloaded = start_byte
            with open(out_path, mode) as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
        return out_path

    def install(self, package: DependencyPackage, downloaded_file: Path) -> bool:
        """
        Install package after download. Dispatches by install_method.

        Args:
            package: Package with install_method and path_to_add.
            downloaded_file: Path to the downloaded file.

        Returns:
            True if install succeeded, False otherwise.
        """
        method = (package.install_method or "").lower()
        dest_dir = downloaded_file.parent
        try:
            if method == "zip_extract":
                return self._install_zip_extract(downloaded_file, dest_dir, package)
            if method == "exe_silent":
                return self._install_exe_silent(downloaded_file)
            if method == "choco":
                return self._install_choco(package)
            if method == "apt":
                return self._install_apt(package)
            logger.warning("Unknown install_method %s for %s", method, package.name)
            return False
        except (OSError, subprocess.SubprocessError, zipfile.BadZipFile) as e:
            logger.exception("Install failed for %s: %s", package.name, e)
            return False

    def _install_zip_extract(self, archive: Path, dest_dir: Path, package: DependencyPackage) -> bool:
        """Extract ZIP to dest_dir; normalize COLMAP so binaries end up in dest_dir/colmap/."""
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest_dir)
        if package.name != "COLMAP":
            return True
        # COLMAP zip may have one top-level dir (e.g. colmap-x64-windows-nocuda) or files at root.
        # path_to_add is deps/colmap, so we need dest_dir/colmap/colmap.exe.
        top_level = [p for p in dest_dir.iterdir() if p != archive and p.name != archive.name]
        if not top_level:
            return True
        target_colmap_dir = dest_dir / "colmap"
        if len(top_level) == 1 and top_level[0].is_dir():
            single = top_level[0]
            if single.name == "colmap":
                return True
            if target_colmap_dir.exists():
                logger.debug("COLMAP dir %s already exists, leaving extract at %s", target_colmap_dir, single)
                return True
            single.rename(target_colmap_dir)
            logger.debug("Renamed COLMAP extract dir %s -> %s", single.name, target_colmap_dir)
            return True
        if target_colmap_dir.exists():
            return True
        target_colmap_dir.mkdir(parents=True)
        for p in top_level:
            if p == archive:
                continue
            dest_item = target_colmap_dir / p.name
            if dest_item.exists():
                continue
            shutil.move(str(p), str(dest_item))
        logger.debug("Moved COLMAP files into %s", target_colmap_dir)
        return True

    def _install_exe_silent(self, exe_path: Path) -> bool:
        """Run .exe with /S /quiet."""
        result = subprocess.run(
            [str(exe_path), "/S", "/quiet"],
            timeout=600,
            capture_output=True,
        )
        return result.returncode == 0

    def _install_choco(self, package: DependencyPackage) -> bool:
        """Run choco install package name -y --no-progress."""
        name = package.install_args[0] if package.install_args else package.name
        result = subprocess.run(
            ["choco", "install", name, "-y", "--no-progress"],
            timeout=600,
            capture_output=True,
        )
        return result.returncode == 0

    def _install_apt(self, package: DependencyPackage) -> bool:
        """Run sudo apt install -y package."""
        name = package.install_args[0] if package.install_args else package.name
        result = subprocess.run(
            ["sudo", "apt", "install", "-y", name],
            timeout=300,
            capture_output=True,
        )
        return result.returncode == 0

    def verify(self, package: DependencyPackage) -> bool:
        """
        Run package verify_command and return True if exit code is 0.

        Does not raise; returns False on failure or missing command.
        """
        cmd_str = (package.verify_command or "").strip()
        if not cmd_str:
            return False
        try:
            result = subprocess.run(
                cmd_str.split(),
                timeout=10,
                capture_output=True,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError) as e:
            logger.debug("Verify failed for %s: %s", package.name, e)
            return False
