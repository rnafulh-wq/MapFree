"""MapFree 3D viewer package — QOpenGLWidget-based viewer."""

from mapfree.viewer.gl_widget import GLWidget, ViewerWidget, set_default_opengl_format
from mapfree.viewer.camera import Camera
from mapfree.viewer.scene import Scene
from mapfree.viewer.geometry_loader import GeometryLoader
from mapfree.viewer.shader_manager import ShaderManager

__all__ = [
    "GLWidget",
    "ViewerWidget",
    "set_default_opengl_format",
    "Camera",
    "Scene",
    "GeometryLoader",
    "ShaderManager",
]
