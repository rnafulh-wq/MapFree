"""PySide6 application entry point."""

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from mapfree.utils.path_manager import PathManager
from mapfree.utils.tile_cache import cleanup_old_tiles

PathManager.inject_to_env()

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mapfree.gui.main_window import MainWindow  # noqa: E402
from mapfree.gui.dialogs.first_run_wizard import (  # noqa: E402
    FirstRunWizard,
    should_show_first_run_wizard,
)
from mapfree.application.setup_state import (  # noqa: E402
    should_skip_dependency_dialog,
    save_setup_state,
)
from mapfree.viewer.bootstrap.gl_bootstrap import GLBootstrap  # noqa: E402

_log = logging.getLogger(__name__)

ICON_TASKBAR = "MapFree_logo_taskbar.png"


def _find_icon_path() -> Path | None:
    """Resolve path to taskbar icon: repo assets/ or PyInstaller bundle."""
    if getattr(sys, "_MEIPASS", None):
        p = Path(sys._MEIPASS) / "assets" / ICON_TASKBAR
    else:
        # From source: repo root = parent of mapfree package
        base = Path(__file__).resolve().parent.parent
        p = base / "assets" / ICON_TASKBAR
    return p if p.is_file() else None


def _log_startup_colmap() -> None:
    """Log PATH prefix and COLMAP executable + version at startup."""
    from mapfree.utils.colmap_finder import find_colmap_executable
    path = find_colmap_executable()
    env_path = os.environ.get("PATH", "")
    prefix = env_path[:250] + "..." if len(env_path) > 250 else env_path
    _log.info("PATH (prefix): %s", prefix)
    _log.info("COLMAP executable: %s", path or "not found")
    if path:
        try:
            cmd = [path, "--version"]
            if sys.platform == "win32" and path.lower().endswith(".bat"):
                cmd = ["cmd", "/c", path, "--version"]
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = (r.stdout or r.stderr or "").strip()
            version_line = out.splitlines()[0] if out else "—"
            _log.info("COLMAP version: %s", version_line)
        except Exception as e:
            _log.debug("COLMAP version check failed: %s", e)


def main() -> int:
    """Launch the MapFree GUI. Creates QApplication only if one does not exist.
    Shows first-run setup wizard when ~/.mapfree/setup_complete.json is missing.
    Dependency check runs after PathManager.inject_to_env() so COLMAP is found;
    setup_complete.json skip logic runs before main window to avoid dialog flash."""
    _log_startup_colmap()
    gl_enabled = GLBootstrap().initialize_opengl()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    icon_path = _find_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        _log.debug("App icon not found: assets/%s", ICON_TASKBAR)

    if should_show_first_run_wizard():
        wizard = FirstRunWizard()
        wizard.exec()

    # Run dependency check before main window so PATH is already set and
    # setup_complete.json is respected (skip dialog when completed + colmap.found).
    if not should_skip_dependency_dialog():
        from mapfree.utils.dependency_check import check_all_dependencies
        from mapfree.gui.dialogs.dependency_dialog import DependencyDialog
        results = check_all_dependencies()
        if should_skip_dependency_dialog(recheck_results=results):
            save_setup_state(results)
        else:
            dlg = DependencyDialog(results, parent=None)
            dlg.exec()

    window = MainWindow(gl_enabled=gl_enabled)
    if icon_path is not None:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    # Clean global tile cache (files older than 30 days) in background
    threading.Thread(target=lambda: cleanup_old_tiles(30), daemon=True).start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
