"""PATH management for MapFree-managed dependencies.

Registers binary paths in ~/.mapfree/deps_registry.json and injects
them into os.environ['PATH'] at startup so COLMAP/OpenMVS/PDAL/GDAL
installed by the first-run wizard are found without user PATH setup.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REGISTRY_FILE = Path.home() / ".mapfree" / "deps_registry.json"


class PathManager:
    """Manage dependency binary paths and inject them into process PATH."""

    DEPS_DIR_WINDOWS = Path(
        os.environ.get("PROGRAMFILES", "C:/Program Files")
    ) / "MapFree" / "deps"
    DEPS_DIR_LINUX = Path.home() / ".mapfree" / "deps"

    @classmethod
    def get_deps_dir(cls) -> Path:
        """Return the directory for MapFree-managed deps for the current OS."""
        if os.name == "nt":
            return cls.DEPS_DIR_WINDOWS
        return cls.DEPS_DIR_LINUX

    @classmethod
    def _registry_path(cls) -> Path:
        """Path to deps_registry.json."""
        return _REGISTRY_FILE

    @classmethod
    def _load_registry(cls) -> dict[str, str]:
        """Load registry from disk. Returns dict name -> bin_path string."""
        p = cls._registry_path()
        if not p.is_file():
            return {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Could not load deps registry: %s", e)
            return {}

    @classmethod
    def _save_registry(cls, data: dict[str, str]) -> None:
        """Save registry to disk."""
        p = cls._registry_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.warning("Could not save deps registry: %s", e)

    @classmethod
    def register_dep(cls, name: str, bin_path: Path) -> None:
        """Register a dependency binary path in ~/.mapfree/deps_registry.json."""
        path_str = str(bin_path.resolve())
        reg = cls._load_registry()
        reg[name] = path_str
        cls._save_registry(reg)
        logger.debug("Registered dep %s -> %s", name, path_str)

    @classmethod
    def get_dep_path(cls, name: str) -> Optional[Path]:
        """Return the registered path for a dependency, or None if not registered."""
        reg = cls._load_registry()
        raw = reg.get(name)
        if not raw:
            return None
        p = Path(raw)
        return p if p.exists() else None

    @classmethod
    def inject_to_env(cls) -> None:
        """Prepend all registered dependency directories to os.environ['PATH'].

        Call this at the very start of app.py and cli/main.py so that
        dependency_check and engine subprocesses see MapFree-installed deps.
        """
        reg = cls._load_registry()
        if not reg:
            return
        paths_to_prepend: list[str] = []
        seen: set[str] = set()
        for _name, bin_path_str in reg.items():
            try:
                p = Path(bin_path_str)
                if p.is_file():
                    parent = str(p.parent)
                else:
                    parent = bin_path_str
                if parent and parent not in seen:
                    seen.add(parent)
                    paths_to_prepend.append(parent)
            except (TypeError, ValueError):
                continue
        if not paths_to_prepend:
            return
        sep = os.pathsep
        current = os.environ.get("PATH", "")
        new_prefix = sep.join(paths_to_prepend)
        os.environ["PATH"] = new_prefix + sep + current
        logger.debug("Injected %d dep path(s) into PATH", len(paths_to_prepend))

    @classmethod
    def add_to_system_path_windows(cls, path: str) -> bool:
        """Append path to the system PATH in Windows registry (requires admin).

        Edits HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment.
        Returns True on success, False on failure or non-Windows.
        """
        if os.name != "nt":
            return False
        try:
            import winreg
        except ImportError:
            logger.debug("winreg not available")
            return False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0,
                winreg.KEY_READ | winreg.KEY_SET_VALUE,
            )
        except OSError as e:
            logger.warning("Could not open Environment key (admin?): %s", e)
            return False
        try:
            try:
                current, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current = ""
            if path in (current or "").split(os.pathsep):
                return True
            new_path = (current or "").rstrip(os.pathsep) + os.pathsep + path
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            return True
        except OSError as e:
            logger.warning("Could not set system PATH: %s", e)
            return False
        finally:
            winreg.CloseKey(key)
