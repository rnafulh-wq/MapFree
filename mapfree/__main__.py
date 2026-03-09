"""
Windows production entry point for MapFree GUI.

- python -m mapfree         -> GUI
- mapfree                   -> GUI (console script)
- mapfree run ...           -> CLI pipeline (delegated)
- No sys.exit() during import; only under if __name__ == "__main__" or from main().
- Global exception hook: log to logs/mapfree_error.log, show QMessageBox when Qt is up.
- QApplication is created only once (in app.main()).
"""

import sys
from pathlib import Path


def _log_error_to_file(exc_type, exc_value, exc_tb) -> None:
    """Append traceback to logs/mapfree_error.log (create dir if needed)."""
    import traceback
    try:
        # Use cwd so it works from any launch dir and when frozen
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "mapfree_error.log"
        lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n---\n")
            f.writelines(lines)
    except Exception:
        pass


def _install_exception_hook() -> None:
    """Install global exception hook: log to file, show dialog if Qt up, then re-raise."""
    _original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        import traceback
        # 1. Log to file first (no Qt dependency)
        _log_error_to_file(exc_type, exc_value, exc_tb)
        # 2. stderr
        traceback.print_exception(exc_type, exc_value, exc_tb)
        # 3. Show dialog on Windows so user sees the error (no silent crash)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance()
            if app is not None:
                msg = "".join(traceback.format_exception_only(exc_type, exc_value))
                QMessageBox.critical(
                    None,
                    "MapFree Error",
                    "An unexpected error occurred:\n\n%s\n\nSee logs/mapfree_error.log and console for details."
                    % (msg.strip() or str(exc_value)),
                )
        except Exception:
            pass
        _original(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def main() -> int:
    """
    Entry point for console script and python -m mapfree.
    - If argv[1] == 'run', delegate to CLI (never returns).
    - Otherwise launch GUI and return exit code.
    """
    # Delegate CLI when invoked as: mapfree run ...
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        from mapfree.application.cli.main import main as cli_main
        cli_main()  # sys.exit() inside
        return 0

    _install_exception_hook()
    from mapfree.app import main as app_main
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
