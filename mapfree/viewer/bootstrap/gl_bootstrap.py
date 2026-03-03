"""
Main entry: run probe (optional), select backend, apply environment.
Call bootstrap() before creating any QApplication or QOpenGLWidget.

GLBootstrap: run safe_probe(), choose surface format, cache in ~/.config/mapfree/gl_profile.json.
On next startup read cache and skip probe unless cache missing. Apply QSurfaceFormat.setDefaultFormat().
"""
import json
import os
from pathlib import Path
from typing import Any

from mapfree.viewer.bootstrap.gl_log import (
    log_backend,
    log_capabilities,
    log_disable,
    log_error,
    log_probe_result,
    log_selected_profile,
)
from mapfree.viewer.bootstrap.gl_probe_runner import run_probe
from mapfree.viewer.bootstrap.gl_selector import (
    choose_surface_format,
    format_from_force_version,
    format_profile_summary,
    select_backend,
)

_BACKEND: str | None = None

_CACHE_PATH = Path(os.path.expanduser("~/.config/mapfree/gl_profile.json"))


def _load_cache() -> dict[str, Any] | None:
    """Load gl_profile.json. Return None on missing or error."""
    try:
        if not _CACHE_PATH.exists():
            return None
        text = _CACHE_PATH.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        if not data.get("GL_VERSION") and not data.get("GL_VENDOR"):
            return None
        return data
    except Exception:
        return None


def _save_cache(capabilities: dict[str, Any]) -> None:
    """Write capabilities to gl_profile.json. No-op on error."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(capabilities, indent=2), encoding="utf-8")
    except Exception:
        pass


class GLBootstrap:
    """
    Run safe_probe(); choose best surface format; cache in ~/.config/mapfree/gl_profile.json.
    On next startup read cache and skip probe unless cache missing.
    Apply QSurfaceFormat.setDefaultFormat(). Never raise.
    """

    def __init__(self, probe_timeout: float = 5.0):
        self._probe_timeout = probe_timeout
        self._enabled: bool = False

    def initialize_opengl(self) -> bool:
        """
        Load cache or run safe_probe(); choose format; apply setDefaultFormat(); optionally save cache.
        MAPFREE_FORCE_GL overrides: "4.1" | "3.3" | "3.0" | "2.1" → use that format; "disable" → disable 3D.
        Returns True if 3D should be enabled, False if 3D must be disabled. Never raises.
        """
        try:
            from PySide6.QtGui import QSurfaceFormat
        except Exception as e:
            log_error(str(e))
            return False

        force = (os.environ.get("MAPFREE_FORCE_GL") or "").strip().lower()
        if force == "disable":
            log_probe_result({"probe_ok": False, "error": "MAPFREE_FORCE_GL=disable"})
            log_disable("MAPFREE_FORCE_GL=disable")
            self._enabled = False
            return False
        if force:
            fmt = format_from_force_version(force)
            if fmt is not None:
                log_probe_result({"probe_ok": True, "force_gl": force})
                log_selected_profile(format_profile_summary(fmt) + " (forced)")
                try:
                    QSurfaceFormat.setDefaultFormat(fmt)
                    self._enabled = True
                    return True
                except Exception as e:
                    log_error(str(e))
                    log_disable("MAPFREE_FORCE_GL format apply failed")
                    self._enabled = False
                    return False
            # invalid value: fall through to normal detection

        capabilities: dict[str, Any] | None = None

        # 1. Try cache first (skip probe unless cache missing)
        cached = _load_cache()
        if cached is not None:
            capabilities = cached
            log_probe_result({"probe_ok": True, "from_cache": True})

        if capabilities is None:
            # 2. Run safe_probe()
            try:
                from mapfree.viewer.bootstrap.gl_probe import safe_probe
                capabilities = safe_probe(timeout=self._probe_timeout)
            except Exception as e:
                log_error(str(e))
                capabilities = None
            if capabilities is None:
                log_probe_result({"probe_ok": False, "error": "no capabilities"})
                log_disable("probe failed or missing capabilities")
                self._enabled = False
                return False
            log_probe_result({"probe_ok": True})

            # 3. Save cache for next startup
            _save_cache(capabilities)

        log_capabilities(capabilities)
        # 4. Choose best surface format and apply
        try:
            fmt = choose_surface_format(capabilities)
            log_selected_profile(format_profile_summary(fmt))
            QSurfaceFormat.setDefaultFormat(fmt)
            self._enabled = True
            return True
        except Exception as e:
            log_error(str(e))
            log_disable("format apply failed")
            self._enabled = False
            return False


def initialize_opengl(probe_timeout: float = 5.0) -> bool:
    """
    Run GLBootstrap and apply default format. Returns True if 3D should be enabled, False otherwise.
    Never raises; all errors handled internally.
    """
    try:
        b = GLBootstrap(probe_timeout=probe_timeout)
        return b.initialize_opengl()
    except Exception:
        return False


def bootstrap(
    run_probe_subprocess: bool = True,
    probe_timeout: float = 5.0,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Adaptive OpenGL initialization. Call once at startup, before Qt/GL.

    If run_probe_subprocess is True, runs gl_probe in a subprocess (software GL)
    to see if OpenGL context can be created without segfault. Then selects
    backend and sets os.environ so that subsequent Qt/GL use the chosen path.

    Returns:
        dict with:
          - backend: "hardware" | "software" | "placeholder"
          - probe_ok: bool
          - probe_error: str | None
    """
    global _BACKEND
    env = env or os.environ
    probe_result = None
    probe_ok = False
    probe_error = None

    if run_probe_subprocess:
        probe_result = run_probe(timeout=probe_timeout, use_software=True)
        log_probe_result(probe_result)
        probe_ok = probe_result.get("probe_ok", False)
        probe_error = probe_result.get("error")
    else:
        probe_result = None

    backend = select_backend(probe_result, env)
    log_backend(backend)

    if backend == "software":
        os.environ["QT_OPENGL"] = "software"
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    elif backend == "hardware":
        os.environ.pop("QT_OPENGL", None)
        os.environ.pop("LIBGL_ALWAYS_SOFTWARE", None)
    # placeholder: no env change; caller will use GLFallbackWidget

    _BACKEND = backend
    return {
        "backend": backend,
        "probe_ok": probe_ok,
        "probe_error": probe_error,
    }


def get_backend() -> str | None:
    """Return the backend set by last bootstrap() call, or None."""
    return _BACKEND
