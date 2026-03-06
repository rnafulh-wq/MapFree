"""PySide6 application entry point."""

import logging
import os
import subprocess
import sys

from mapfree.utils.path_manager import PathManager

PathManager.inject_to_env()

from PySide6.QtWidgets import QApplication  # noqa: E402

from mapfree.gui.main_window import MainWindow  # noqa: E402
from mapfree.gui.dialogs.first_run_wizard import (  # noqa: E402
    FirstRunWizard,
    should_show_first_run_wizard,
)
from mapfree.viewer.bootstrap.gl_bootstrap import GLBootstrap  # noqa: E402

_log = logging.getLogger(__name__)


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
    Returns the exit code (for the caller to pass to sys.exit())."""
    _log_startup_colmap()
    gl_enabled = GLBootstrap().initialize_opengl()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    if should_show_first_run_wizard():
        wizard = FirstRunWizard()
        wizard.exec()

    window = MainWindow(gl_enabled=gl_enabled)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
