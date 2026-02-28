"""PySide6 application entry point."""

import sys
from PySide6.QtWidgets import QApplication

from mapfree.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
