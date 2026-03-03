"""
Run the OpenGL probe in a subprocess so that segfault (exit 139) or timeout
does not affect the caller. Returns a result dict for the selector.

When run as a standalone script (python -m mapfree.viewer.bootstrap.gl_probe_runner):
creates minimal QApplication + QOpenGLWidget, collects GL_* info in initializeGL,
prints JSON to stdout, exits within 3 seconds. No imports from main MapFree app.
"""
import json
import os
import subprocess
import sys
import time
from ctypes import CFUNCTYPE, c_uint, c_void_p, string_at
from typing import Any

# OpenGL enums for glGetString (no external GL dependency)
GL_VENDOR = 0x1F00
GL_RENDERER = 0x1F01
GL_VERSION = 0x1F02
GL_SHADING_LANGUAGE_VERSION = 0x8B8C


def _gl_info_from_context():
    """Read GL_VENDOR, GL_RENDERER, GL_VERSION, GL_SHADING_LANGUAGE_VERSION via current context."""
    from PySide6.QtGui import QOpenGLContext

    ctx = QOpenGLContext.currentContext()
    if not ctx:
        return None
    addr = ctx.getProcAddress("glGetString")
    if not addr:
        return None
    ftype = CFUNCTYPE(c_void_p, c_uint)
    gl_get_string = ftype(addr)

    def get_str(enum: int) -> str | None:
        p = gl_get_string(enum)
        if not p:
            return None
        try:
            return string_at(p).decode("utf-8", errors="replace")
        except Exception:
            return None

    return {
        "GL_VENDOR": get_str(GL_VENDOR),
        "GL_RENDERER": get_str(GL_RENDERER),
        "GL_VERSION": get_str(GL_VERSION),
        "GL_SHADING_LANGUAGE_VERSION": get_str(GL_SHADING_LANGUAGE_VERSION),
    }


def _run_standalone_gl_info_script(use_software: bool = True, max_wait: float = 2.0) -> int:
    """
    Standalone script: minimal QApplication + QOpenGLWidget, collect GL info in initializeGL,
    print JSON to stdout, exit 0. Exit non-zero on failure or timeout. Total runtime target ≤ 3s.
    No imports from main MapFree app; only PySide6 and stdlib.
    """
    if use_software:
        os.environ["QT_OPENGL"] = "software"
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")

    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtWidgets import QApplication

    info_holder: list[dict[str, str | None] | None] = []  # single-element container

    class MinimalGLWidget(QOpenGLWidget):
        def initializeGL(self):
            try:
                info_holder.append(_gl_info_from_context())
            except Exception:
                info_holder.append(None)

    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    widget = MinimalGLWidget()
    widget.show()
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline and not info_holder:
        app.processEvents()
        time.sleep(0.02)
    widget.close()
    app.processEvents()

    if not info_holder or info_holder[0] is None:
        return 1
    out = json.dumps(info_holder[0], indent=2)
    print(out, flush=True)
    return 0


def run_probe(
    timeout: float = 5.0,
    use_software: bool = True,
) -> dict[str, Any]:
    """
    Run gl_probe in a subprocess. Safe from segfault: if the child crashes,
    we get a non-zero exit and report probe_ok=False.

    Returns:
        dict with:
          - probe_ok: bool — True if process exited 0
          - software: bool — whether software GL was requested
          - exit_code: int | None
          - error: str | None — "timeout" | "segfault" | "error" | None
    """
    env = os.environ.copy()
    env["GL_PROBE_SOFTWARE"] = "1" if use_software else "0"
    cmd = [sys.executable, "-m", "mapfree.viewer.bootstrap.gl_probe"]
    try:
        result = subprocess.run(
            cmd,
            env=env,
            timeout=timeout,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        return {
            "probe_ok": False,
            "software": use_software,
            "exit_code": None,
            "error": "timeout",
        }
    exit_code = result.returncode
    if exit_code == 0:
        return {
            "probe_ok": True,
            "software": use_software,
            "exit_code": 0,
            "error": None,
        }
    if exit_code in (-11, 139, 134):
        return {
            "probe_ok": False,
            "software": use_software,
            "exit_code": exit_code,
            "error": "segfault",
        }
    return {
        "probe_ok": False,
        "software": use_software,
        "exit_code": exit_code,
        "error": "error",
    }


if __name__ == "__main__":
    use_software = os.environ.get("GL_PROBE_SOFTWARE", "1") == "1"
    sys.exit(_run_standalone_gl_info_script(use_software=use_software, max_wait=2.0))
