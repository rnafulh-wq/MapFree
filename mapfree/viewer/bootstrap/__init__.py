"""
Adaptive OpenGL initialization for the MapFree viewer.

Use bootstrap() at startup to probe GL, select backend (hardware / software / placeholder),
and apply environment. Then create ViewerWidget only when backend is not "placeholder".
"""

from mapfree.viewer.bootstrap.gl_bootstrap import GLBootstrap, bootstrap, get_backend, initialize_opengl
from mapfree.viewer.bootstrap.gl_fallback import GLFallbackManager, GLFallbackWidget
from mapfree.viewer.bootstrap.gl_probe import safe_probe
from mapfree.viewer.bootstrap.gl_probe_runner import run_probe
from mapfree.viewer.bootstrap.gl_selector import choose_surface_format, select_backend

__all__ = [
    "bootstrap",
    "choose_surface_format",
    "get_backend",
    "GLBootstrap",
    "GLFallbackManager",
    "GLFallbackWidget",
    "initialize_opengl",
    "run_probe",
    "safe_probe",
    "select_backend",
]
