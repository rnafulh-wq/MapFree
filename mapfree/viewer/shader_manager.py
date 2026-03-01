"""Shader manager — compile and manage OpenGL shaders (point cloud, colored mesh, directional light, camera)."""

from typing import Any

from PySide6.QtGui import QMatrix4x4, QVector3D
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram


# -----------------------------------------------------------------------------
# Mesh: colored mesh + directional light + camera position
# -----------------------------------------------------------------------------

MESH_VERTEX_GLSL = """#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
layout(location = 2) in vec3 aNormal;
out vec3 vColor;
out vec3 vNormal;
out vec3 vFragPos;
uniform mat4 uProjection;
uniform mat4 uView;
uniform mat4 uModel;
void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    gl_Position = uProjection * uView * worldPos;
    vFragPos = worldPos.xyz;
    vColor = aColor;
    vNormal = mat3(transpose(inverse(uModel))) * aNormal;
}
"""

MESH_FRAGMENT_GLSL = """#version 330 core
in vec3 vColor;
in vec3 vNormal;
in vec3 vFragPos;
out vec4 FragColor;
uniform vec3 uCameraPosition;
uniform vec3 uLightDir;
uniform vec3 uAmbientColor;
uniform vec3 uDiffuseColor;
void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(-uLightDir);
    float diff = max(dot(N, L), 0.0);
    vec3 ambient = uAmbientColor * vColor;
    vec3 diffuse = uDiffuseColor * diff * vColor;
    FragColor = vec4(ambient + diffuse, 1.0);
}
"""

# -----------------------------------------------------------------------------
# Point cloud
# -----------------------------------------------------------------------------

POINT_VERTEX_GLSL = """#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
out vec3 vColor;
uniform mat4 uProjection;
uniform mat4 uView;
uniform mat4 uModel;
uniform vec3 uCameraPosition;
void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    gl_PointSize = 2.0;
    vColor = aColor;
}
"""

POINT_FRAGMENT_GLSL = """#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
"""


# -----------------------------------------------------------------------------
# ShaderManager
# -----------------------------------------------------------------------------

class ShaderManager:
    """Compile, link, and manage shader programs: point cloud and colored mesh with directional light and camera."""

    def __init__(self) -> None:
        self._program_mesh: QOpenGLShaderProgram | None = None
        self._program_point_cloud: QOpenGLShaderProgram | None = None
        self._initialized = False

    def init(self, context: Any = None) -> bool:
        """Compile and link shaders. Requires a current OpenGL context. Return True on success."""
        if self._initialized:
            return True
        ok = self._compile_mesh_program() and self._compile_point_cloud_program()
        self._initialized = ok
        return ok

    def _compile_mesh_program(self) -> bool:
        prog = QOpenGLShaderProgram()
        if not prog.addShaderFromSourceCode(QOpenGLShader.Vertex, MESH_VERTEX_GLSL):
            return False
        if not prog.addShaderFromSourceCode(QOpenGLShader.Fragment, MESH_FRAGMENT_GLSL):
            return False
        if not prog.link():
            return False
        self._program_mesh = prog
        return True

    def _compile_point_cloud_program(self) -> bool:
        prog = QOpenGLShaderProgram()
        if not prog.addShaderFromSourceCode(QOpenGLShader.Vertex, POINT_VERTEX_GLSL):
            return False
        if not prog.addShaderFromSourceCode(QOpenGLShader.Fragment, POINT_FRAGMENT_GLSL):
            return False
        if not prog.link():
            return False
        self._program_point_cloud = prog
        return True

    def mesh_program(self) -> QOpenGLShaderProgram | None:
        """Return the shader program used for colored mesh rendering (directional light, camera)."""
        return self._program_mesh

    def point_cloud_program(self) -> QOpenGLShaderProgram | None:
        """Return the shader program used for point cloud rendering."""
        return self._program_point_cloud

    def set_uniform_mat4(self, program: QOpenGLShaderProgram | None, name: str, matrix: QMatrix4x4) -> None:
        """Set a mat4 uniform by name. Program should be bound."""
        if program is not None and program.isLinked():
            program.setUniformValue(name, matrix)

    def set_uniform_vec3(self, program: QOpenGLShaderProgram | None, name: str, x: float, y: float, z: float) -> None:
        """Set a vec3 uniform by name. Program should be bound."""
        if program is not None and program.isLinked():
            program.setUniformValue(name, QVector3D(x, y, z))

    def set_mesh_light_and_camera(
        self,
        camera_position: tuple[float, float, float],
        light_dir: tuple[float, float, float],
        ambient: tuple[float, float, float] = (0.4, 0.4, 0.4),
        diffuse: tuple[float, float, float] = (0.6, 0.6, 0.6),
    ) -> None:
        """Set mesh program uniforms for directional light and camera (call with mesh program bound)."""
        prog = self._program_mesh
        if prog is None or not prog.isLinked():
            return
        prog.setUniformValue("uCameraPosition", QVector3D(*camera_position))
        prog.setUniformValue("uLightDir", QVector3D(*light_dir))
        prog.setUniformValue("uAmbientColor", QVector3D(*ambient))
        prog.setUniformValue("uDiffuseColor", QVector3D(*diffuse))

    def set_point_cloud_camera(self, camera_position: tuple[float, float, float]) -> None:
        """Set point cloud program camera uniform (call with point cloud program bound)."""
        prog = self._program_point_cloud
        if prog is None or not prog.isLinked():
            return
        prog.setUniformValue("uCameraPosition", QVector3D(*camera_position))

    def release(self) -> None:
        """Release shader resources and clear stored programs."""
        if self._program_mesh is not None:
            self._program_mesh.release()
            self._program_mesh = None
        if self._program_point_cloud is not None:
            self._program_point_cloud.release()
            self._program_point_cloud = None
        self._initialized = False
