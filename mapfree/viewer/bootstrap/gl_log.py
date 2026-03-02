"""
Bootstrap logging to ~/.config/mapfree/gl_bootstrap.log.
All errors logged silently; no stacktrace shown to user.
"""
import logging
import os
from pathlib import Path
from typing import Any

_LOG_PATH = Path(os.path.expanduser("~/.config/mapfree/gl_bootstrap.log"))
_LOGGER: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    _LOGGER = logging.getLogger("mapfree.viewer.bootstrap")
    _LOGGER.setLevel(logging.DEBUG)
    _LOGGER.handlers.clear()
    _LOGGER.propagate = False
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        _LOGGER.addHandler(handler)
    except Exception:
        pass
    return _LOGGER


def _log(level: int, msg: str) -> None:
    try:
        _get_logger().log(level, msg)
    except Exception:
        pass


def log_probe_result(probe_result: dict[str, Any] | None) -> None:
    """Log probe outcome (probe_ok, error, exit_code, software, from_cache)."""
    if probe_result is None:
        _log(logging.INFO, "probe_result: none")
        return
    ok = probe_result.get("probe_ok", False)
    err = probe_result.get("error")
    code = probe_result.get("exit_code")
    soft = probe_result.get("software")
    from_cache = probe_result.get("from_cache")
    force_gl = probe_result.get("force_gl")
    parts = [f"probe_ok={ok}"]
    if from_cache:
        parts.append("from_cache")
    if force_gl:
        parts.append(f"force_gl={force_gl}")
    if soft is not None:
        parts.append(f"software={soft}")
    if code is not None:
        parts.append(f"exit_code={code}")
    if err:
        parts.append(f"error={err}")
    _log(logging.INFO, "probe_result: " + " ".join(parts))


def log_capabilities(capabilities: dict[str, Any] | None) -> None:
    """Log vendor, renderer, version from capabilities."""
    if not capabilities:
        _log(logging.INFO, "capabilities: none")
        return
    vendor = capabilities.get("GL_VENDOR") or "(unknown)"
    renderer = capabilities.get("GL_RENDERER") or "(unknown)"
    version = capabilities.get("GL_VERSION") or "(unknown)"
    _log(logging.INFO, f"vendor: {vendor}")
    _log(logging.INFO, f"renderer: {renderer}")
    _log(logging.INFO, f"version: {version}")


def log_selected_profile(profile_summary: str) -> None:
    """Log selected OpenGL profile (e.g. '3.3 Core' or '2.1 Compatibility')."""
    _log(logging.INFO, f"selected_profile: {profile_summary}")


def log_backend(backend: str) -> None:
    """Log selected backend (hardware / software / placeholder)."""
    _log(logging.INFO, f"backend: {backend}")


def log_fallback(event: str) -> None:
    """Log a fallback event (e.g. context failed, downgrade)."""
    _log(logging.INFO, f"fallback: {event}")


def log_disable(event: str) -> None:
    """Log a disable event (3D viewer disabled)."""
    _log(logging.INFO, f"disable: {event}")


def log_error(msg: str) -> None:
    """Log an error silently (no stacktrace)."""
    _log(logging.ERROR, f"error: {msg}")
