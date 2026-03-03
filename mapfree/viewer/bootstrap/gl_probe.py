"""
Minimal OpenGL context probe. Intended to be run in a subprocess so that
a segfault does not kill the parent. Exits 0 if GL context is created and
initialized successfully, 1 on error, or process may exit with 139 (SIGSEGV).
"""
import json
import os
import subprocess
import sys
from typing import Any


def _probe(use_software: bool) -> bool:
    """Create Qt app and QOpenGLWidget; return True if successful."""
    if use_software:
        os.environ["QT_OPENGL"] = "software"
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtWidgets import QApplication

    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    widget = QOpenGLWidget()
    widget.show()
    app.processEvents()
    widget.doneCurrent()
    widget.close()
    return True


def safe_probe(timeout: float = 5) -> dict[str, Any] | None:
    """
    Launch gl_probe_runner in a subprocess, capture stdout, parse JSON.
    If subprocess crashes or times out, return None (do not raise).
    Prevents segmentation fault from killing the main app.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mapfree.viewer.bootstrap.gl_probe_runner"],
            env=os.environ.copy(),
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        out = (result.stdout or "").strip()
        if not out:
            return None
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return None


def main() -> int:
    """Run probe. use_software from env GL_PROBE_SOFTWARE=1."""
    use_software = os.environ.get("GL_PROBE_SOFTWARE", "") == "1"
    try:
        ok = _probe(use_software)
        return 0 if ok else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
