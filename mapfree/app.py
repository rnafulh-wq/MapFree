"""PySide6 application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from mapfree.gui.main_window import MainWindow
from mapfree.viewer.bootstrap.gl_bootstrap import GLBootstrap


def main() -> int:
    """Launch the MapFree GUI. Creates QApplication only if one does not exist.
    Returns the exit code (for the caller to pass to sys.exit())."""
    gl_enabled = GLBootstrap().initialize_opengl()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow(gl_enabled=gl_enabled)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
