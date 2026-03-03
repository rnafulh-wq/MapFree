"""PySide6 application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from mapfree.gui.main_window import MainWindow
from mapfree.viewer.bootstrap.gl_bootstrap import GLBootstrap


def main():
    gl_enabled = GLBootstrap().initialize_opengl()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow(gl_enabled=gl_enabled)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
