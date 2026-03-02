"""
Select OpenGL backend from probe result and environment. Returns one of:
  - "hardware" — use real QOpenGLWidget (caller may still set QT_OPENGL=auto)
  - "software" — use real QOpenGLWidget with QT_OPENGL=software applied
  - "placeholder" — use GLFallbackWidget; do not create GL context
"""
import os
import re
from typing import Any

from PySide6.QtGui import QSurfaceFormat


def _parse_gl_version(version_str: str | None) -> tuple[int, int]:
    """Parse GL_VERSION string to (major, minor). Return (0, 0) if unparseable."""
    if not version_str or not isinstance(version_str, str):
        return (0, 0)
    # e.g. "4.5 (Core Profile) Mesa ..." or "3.3.0" or "2.1 Mesa"
    first_token = version_str.strip().split()[0] if version_str else ""
    match = re.match(r"^(\d+)\.(\d+)", first_token)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (0, 0)


_FORCE_VERSIONS = ("4.1", "3.3", "3.0", "2.1")


def format_from_force_version(version: str) -> QSurfaceFormat | None:
    """
    Build QSurfaceFormat for MAPFREE_FORCE_GL. version must be "4.1", "3.3", "3.0", or "2.1".
    Returns None if version is not supported. 4.1 and 3.3 use Core; 3.0 and 2.1 use Compatibility.
    """
    if version not in _FORCE_VERSIONS:
        return None
    core_versions = ("4.1", "3.3")
    use_core = version in core_versions
    major, minor = (int(x) for x in version.split("."))
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setVersion(major, minor)
    fmt.setProfile(
        QSurfaceFormat.OpenGLContextProfile.CoreProfile
        if use_core
        else QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile
    )
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    return fmt


def format_profile_summary(fmt: QSurfaceFormat) -> str:
    """Return a short string for logging, e.g. '3.3 Core' or '2.1 Compatibility'."""
    major = fmt.version().majorVersion()
    minor = fmt.version().minorVersion()
    is_core = fmt.profile() == QSurfaceFormat.OpenGLContextProfile.CoreProfile
    profile = "Core" if is_core else "Compatibility"
    return f"{major}.{minor} {profile}"


def choose_surface_format(capabilities: dict[str, Any]) -> QSurfaceFormat:
    """
    Choose QSurfaceFormat from probe capabilities (GL_VENDOR, GL_RENDERER, GL_VERSION).
    Priority chain: >= 4.1 Core > >= 3.3 Core > >= 3.0 Compatibility > 2.1 Compatibility.
    Overrides: Intel → avoid Core; Mesa in renderer → force 2.1 compat; NVIDIA → prefer compat 3.0.
    Never default to Core unless high confidence.
    """
    if not capabilities:
        capabilities = {}
    vendor = (capabilities.get("GL_VENDOR") or "").lower()
    renderer = (capabilities.get("GL_RENDERER") or "").lower()
    major, minor = _parse_gl_version(capabilities.get("GL_VERSION"))

    # 1. Priority chain from version
    if major >= 4 and minor >= 1:
        use_core, ver_major, ver_minor = True, 4, 1
    elif major >= 3 and minor >= 3:
        use_core, ver_major, ver_minor = True, 3, 3
    elif major >= 3 and minor >= 0:
        use_core, ver_major, ver_minor = False, 3, 0
    else:
        use_core, ver_major, ver_minor = False, 2, 1

    # 2. Overrides: never default to Core unless high confidence
    if "mesa" in renderer or "mesa" in vendor:
        use_core, ver_major, ver_minor = False, 2, 1
    elif "intel" in vendor:
        use_core = False
    elif "nvidia" in vendor:
        use_core = False
        ver_major, ver_minor = 3, 0

    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setVersion(ver_major, ver_minor)
    fmt.setProfile(
        QSurfaceFormat.OpenGLContextProfile.CoreProfile
        if use_core
        else QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile
    )
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    return fmt


def select_backend(
    probe_result: dict[str, Any] | None,
    env: dict[str, str] | None = None,
) -> str:
    """
    Choose backend from probe result and environment overrides.

    Env (read from env or passed dict):
      MAPFREE_NO_OPENGL=1  -> always "placeholder"
      MAPFREE_OPENGL=1     -> try "hardware" or "software" from probe
      Otherwise            -> use probe: if probe_ok with software -> "software",
                              else if probe_ok with hardware -> "hardware",
                              else "placeholder"

    If probe_result is None, we skip probe and use env only:
      MAPFREE_NO_OPENGL=1 -> "placeholder"
      MAPFREE_OPENGL=1    -> "software" (safe default when no probe)
      Otherwise           -> "placeholder" (safe default)
    """
    env = env or os.environ
    if env.get("MAPFREE_NO_OPENGL") == "1":
        return "placeholder"
    if probe_result is None:
        if env.get("MAPFREE_OPENGL") == "1":
            return "software"
        return "placeholder"
    if not probe_result.get("probe_ok"):
        return "placeholder"
    if env.get("MAPFREE_OPENGL") == "1":
        return "software" if probe_result.get("software") else "hardware"
    return "software" if probe_result.get("software") else "hardware"
