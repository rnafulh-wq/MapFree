"""PySide6 application entry point."""

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


def main() -> int:
    """Launch the MapFree GUI. Creates QApplication only if one does not exist.
    Shows first-run setup wizard when ~/.mapfree/setup_complete.json is missing.
    Returns the exit code (for the caller to pass to sys.exit())."""
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
