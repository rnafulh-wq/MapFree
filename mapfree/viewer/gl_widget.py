"""
OpenGL widget — GL Viewer Wrapper (Safe Layer).

.. warning:: **EXPERIMENTAL**
    The OpenGL 3D viewer is experimental and may crash or produce visual artefacts depending
    on the host GPU driver and platform (software OpenGL is forced to reduce segfaults).
    It is intentionally run in a separate process so a crash does not affect the main
    MapFree window.  Enable it only if needed:

    - GUI button "Enable 3D viewer"
    - Environment variable ``MAPFREE_OPENGL=1``
    - Disable entirely: ``MAPFREE_NO_OPENGL=1``

Architecture:
  GUI Layer (PySide6) → GL Viewer Wrapper (this widget) → Render Core (decoupled from UI thread).

Viewer responsibilities only:
  - Load mesh / point cloud (PLY)
  - Render geometry
  - Emit signals (e.g. mesh_loaded)

Viewer does NOT: process PDAL, DTM, measurement logic — all in backend engine.
"""

import struct
from pathlib import Path
from typing import Any

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from mapfree.viewer.camera import Camera
from PySide6.QtGui import QSurfaceFormat, QOpenGLContext, QMatrix4x4
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
    QOpenGLVersionFunctionsFactory,
    QOpenGLVersionProfile,
)
from PySide6.QtCore import Qt, QSize, QPoint, QRect, Signal
from PySide6.QtGui import QWheelEvent, QMouseEvent, QKeyEvent
from PySide6.QtGui import QVector3D

# OpenGL constants (not all exposed on QOpenGLFunctions_3_3_Core in PySide6)
GL_COLOR_BUFFER_BIT = 0x00004000
GL_DEPTH_BUFFER_BIT = 0x00000100
GL_DEPTH_TEST = 0x0B71
GL_FLOAT = 0x1406
GL_FALSE = 0
GL_TRUE = 1
GL_TRIANGLES = 0x0004
GL_LINES = 0x0001
GL_LINE_STRIP = 0x0003
GL_POINTS = 0x0000
GL_UNSIGNED_INT = 0x1405
GL_DYNAMIC_DRAW = 0x88E8

# Safe memory: cap vertex count per batch to avoid UI freeze / OOM
MAX_VERTICES_RENDER = 2_000_000
# Before uploading to GPU: if vertex_count > MAX_SAFE_VERTICES, auto_decimate (Mesh Buffer Guard)
MAX_SAFE_VERTICES = 2_000_000
# Above this count we auto-downsample for preview; full resolution only for export
LARGE_MESH_VERTEX_THRESHOLD = 10_000_000

# -----------------------------------------------------------------------------
# PLY loader (custom, no external deps)
# -----------------------------------------------------------------------------

def _simplify_for_render(
    vertices: list,
    normals: list | None,
    colors: list,
    indices: list | None,
    max_vertices: int | None = None,
):
    """
    Auto-downsample for large meshes: when vertex count > max_vertices, subsample to LOD preview.
    Default max_vertices = MAX_VERTICES_RENDER. Used for render LOD and for Mesh Buffer Guard (MAX_SAFE_VERTICES).
    Returns (v, n, c, ind).
    """
    cap = max_vertices if max_vertices is not None else MAX_VERTICES_RENDER
    n = len(vertices)
    if n <= cap:
        return vertices, normals, colors, indices
    # Uniformly sample to at most cap (LOD preview; full res only for export)
    step = max(1, n // cap)
    kept_idx = list(range(0, n, step))[:cap]
    kept_set = set(kept_idx)
    old_to_new = {old: i for i, old in enumerate(kept_idx)}
    new_vertices = [vertices[i] for i in kept_idx]
    new_normals = [normals[i] for i in kept_idx] if normals else None
    new_colors = [colors[i] for i in kept_idx]
    if indices and len(indices) >= 3:
        new_indices = []
        for i in range(0, len(indices), 3):
            a, b, c = indices[i], indices[i + 1], indices[i + 2]
            if a in kept_set and b in kept_set and c in kept_set:
                new_indices.extend([old_to_new[a], old_to_new[b], old_to_new[c]])
        if not new_indices:
            new_indices = None
    else:
        new_indices = None
    return new_vertices, new_normals, new_colors, new_indices


def _load_ply(file_path: str) -> dict[str, Any] | None:
    """
    Load a PLY file. Returns a dict with:
      vertices: list of (x,y,z) floats
      normals: list of (nx,ny,nz) or None
      colors: list of (r,g,b) in 0-1 float or None
      indices: list of int (triangles, 3 per face) or None for point cloud
    """
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".ply":
        return None
    data = path.read_bytes()
    try:
        return _parse_ply(data)
    except Exception:
        return None


def _parse_ply(data: bytes) -> dict[str, Any]:
    """Parse PLY binary or ASCII. Fills vertices, optional normals/colors, optional face indices."""
    text = data.decode("utf-8", errors="replace")
    lines = [s.strip() for s in text.splitlines()]
    if not lines or lines[0].lower() != "ply":
        raise ValueError("Not a PLY file")

    # Parse header
    fmt = "ascii"
    binary_fmt = "little"
    num_vertices = 0
    num_faces = 0
    vertex_props = []  # (name, type_str)
    face_props = []
    i = 1
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith("format "):
            parts = line.split()
            if parts[1].lower() == "ascii":
                fmt = "ascii"
            else:
                fmt = "binary"
                binary_fmt = "little" if (len(parts) > 2 and "little" in line.lower()) else "big"
        elif line.startswith("element vertex "):
            num_vertices = int(line.split()[-1])
        elif line.startswith("element face "):
            num_faces = int(line.split()[-1])
        elif line.startswith("property "):
            parts = line.split()
            if len(parts) >= 3:
                prop_type, prop_name = parts[1], parts[2]
                if "vertex" in lines[i - 2].lower():
                    vertex_props.append((prop_name.lower(), prop_type))
                elif "face" in lines[i - 2].lower():
                    face_props.append((prop_name.lower(), prop_type, parts))
        elif line == "end_header":
            break

    # Build vertex property indices
    v_x = v_y = v_z = v_nx = v_ny = v_nz = v_r = v_g = v_b = -1
    for idx, (name, _) in enumerate(vertex_props):
        if name == "x": v_x = idx
        elif name == "y": v_y = idx
        elif name == "z": v_z = idx
        elif name == "nx": v_nx = idx
        elif name == "ny": v_ny = idx
        elif name == "nz": v_nz = idx
        elif name in ("red", "r"): v_r = idx
        elif name in ("green", "g"): v_g = idx
        elif name in ("blue", "b"): v_b = idx
    if v_x < 0 or v_y < 0 or v_z < 0:
        raise ValueError("PLY missing vertex x,y,z")

    vertices = []
    normals = [] if (v_nx >= 0 and v_ny >= 0 and v_nz >= 0) else None
    colors = [] if (v_r >= 0 and v_g >= 0 and v_b >= 0) else None

    header_end = data.find(b"end_header")
    if header_end < 0:
        header_end = text.find("end_header")
        if header_end >= 0:
            header_end = len(text[:header_end].encode("utf-8"))
        else:
            raise ValueError("No end_header")
    header_end += len(b"end_header")
    # Skip newline after end_header
    while header_end < len(data) and data[header_end:header_end + 1] in (b"\n", b"\r"):
        header_end += 1
    if fmt == "ascii":
        header_end = data.find(b"\n", header_end)
        if header_end >= 0:
            header_end += 1
        ascii_body = data[header_end:].decode("utf-8", errors="replace")
        ascii_lines = [ln.split() for ln in ascii_body.splitlines() if ln.strip()]
        line_idx = 0
        for _ in range(num_vertices):
            if line_idx >= len(ascii_lines):
                break
            tok = ascii_lines[line_idx]
            line_idx += 1
            if len(tok) <= max(v_x, v_y, v_z):
                continue
            x = float(tok[v_x])
            y = float(tok[v_y])
            z = float(tok[v_z])
            vertices.append((x, y, z))
            if normals is not None and len(tok) > v_nz:
                normals.append((float(tok[v_nx]), float(tok[v_ny]), float(tok[v_nz])))
            if colors is not None and len(tok) > v_b:
                r, g, b = float(tok[v_r]), float(tok[v_g]), float(tok[v_b])
                if r > 1 or g > 1 or b > 1:
                    r, g, b = r / 255.0, g / 255.0, b / 255.0
                colors.append((r, g, b))
    else:
        # Binary: assume float for vertex props, read tightly
        vertex_stride = 4 * len(vertex_props)  # assume float32 per property
        offset = header_end
        for _ in range(num_vertices):
            if offset + vertex_stride > len(data):
                break
            # Assume all vertex properties are float
            floats = struct.unpack_from(f"{len(vertex_props)}f", data, offset)
            offset += vertex_stride
            vertices.append((float(floats[v_x]), float(floats[v_y]), float(floats[v_z])))
            if normals is not None:
                normals.append((float(floats[v_nx]), float(floats[v_ny]), float(floats[v_nz])))
            if colors is not None:
                r, g, b = floats[v_r], floats[v_g], floats[v_b]
                if r > 1 or g > 1 or b > 1:
                    r, g, b = r / 255.0, g / 255.0, b / 255.0
                colors.append((r, g, b))

    indices = []
    if num_faces > 0 and fmt == "ascii":
        for _ in range(num_faces):
            if line_idx >= len(ascii_lines):
                break
            tok = ascii_lines[line_idx]
            line_idx += 1
            if len(tok) < 4:
                continue
            n = int(tok[0])
            if n == 3:
                indices.extend([int(tok[1]), int(tok[2]), int(tok[3])])
            elif n == 4:
                indices.extend([int(tok[1]), int(tok[2]), int(tok[3]), int(tok[1]), int(tok[3]), int(tok[4])])
    elif num_faces > 0 and fmt == "binary":
        offset = header_end + num_vertices * vertex_stride
        for _ in range(num_faces):
            if offset >= len(data):
                break
            n = struct.unpack_from("B", data, offset)[0]
            offset += 1
            if n >= 3 and offset + n * 4 <= len(data):
                idxs = struct.unpack_from(f"{n}i", data, offset)
                offset += n * 4
                if n == 3:
                    indices.extend(idxs)
                else:
                    for k in range(1, n - 1):
                        indices.extend([idxs[0], idxs[k], idxs[k + 1]])

    return {
        "vertices": vertices,
        "normals": normals,
        "colors": colors,
        "indices": indices if indices else None,
    }


# -----------------------------------------------------------------------------
# OpenGL surface format (Windows & Linux) — Safe initialization
# -----------------------------------------------------------------------------

def set_default_opengl_format() -> None:
    """
    Set default OpenGL surface format for context creation. Call before creating any GL widget.
    Prefer 3.3 Core, depth 24, 4x MSAA. If context creation or init fails in the widget,
    it falls back to 2.1 compatibility (see ViewerWidget.initializeGL / _fallback_mode).
    """
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    fmt.setStencilBufferSize(8)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)


def _format_fallback_21() -> QSurfaceFormat:
    """Fallback format: OpenGL 2.1 Compatibility when 3.3 Core fails."""
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    fmt.setStencilBufferSize(8)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    return fmt


# -----------------------------------------------------------------------------
# Shaders
# -----------------------------------------------------------------------------

_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
layout(location = 2) in vec3 aNormal;
out vec3 vColor;
out vec3 vNormal;
uniform mat4 uProjection;
uniform mat4 uView;
uniform mat4 uModel;
void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    vColor = aColor;
    vNormal = mat3(transpose(inverse(uModel))) * aNormal;
}
"""

_FRAGMENT_SHADER = """
#version 330 core
in vec3 vColor;
in vec3 vNormal;
out vec4 FragColor;
void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(vec3(0.2, 0.5, 0.8));
    float diff = max(dot(N, L), 0.0);
    vec3 ambient = 0.4 * vColor;
    vec3 diffuse = 0.6 * diff * vColor;
    FragColor = vec4(ambient + diffuse, 1.0);
}
"""

# Fallback when no normals (point cloud)
_VERTEX_SHADER_POINTS = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
out vec3 vColor;
uniform mat4 uProjection;
uniform mat4 uView;
uniform mat4 uModel;
void main() {
    gl_Position = uProjection * uView * uModel * vec4(aPos, 1.0);
    gl_PointSize = 2.0;
    vColor = aColor;
}
"""

_FRAGMENT_SHADER_POINTS = """
#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
"""

# Overlay: lines (position only, uniform color)
_LINE_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uProjection;
uniform mat4 uView;
void main() {
    gl_Position = uProjection * uView * vec4(aPos, 1.0);
}
"""
_LINE_FRAGMENT_SHADER = """
#version 330 core
uniform vec3 uColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(uColor, 1.0);
}
"""


# -----------------------------------------------------------------------------
# ViewerWidget
# -----------------------------------------------------------------------------

class ViewerWidget(QOpenGLWidget):
    """
    GL Viewer Wrapper (Safe Layer): 3D viewport, PLY load, render, signals only.
    No PDAL/DTM/measurement logic — all in backend engine.
    API: load_point_cloud, load_mesh, clear_scene; emits mesh_loaded.
    """

    mesh_loaded = Signal(str, int)  # (path, vertex_count) when mesh/point cloud loaded
    geometry_load_failed = Signal(str)  # path when async load failed
    progressChanged = Signal(int)  # 0-100 during async geometry load (for progress bar)

    def __init__(self, parent=None):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)
        fmt.setStencilBufferSize(8)
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        super().__init__(parent)
        self.setFormat(fmt)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._gl = None  # QOpenGLFunctions_3_3_Core or None when fallback
        self._vao = None
        self._vbo = None
        self._ebo = None
        self._program_mesh = None
        self._program_points = None
        self._num_vertices = 0
        self._num_indices = 0
        self._initialized = False
        self._use_fallback = False  # True when 3.3 Core failed → 2.1 compat path
        self._camera = Camera()
        self._last_mouse = QPoint()
        self._mouse_button = Qt.MouseButton.NoButton
        self._show_axes = False
        self._tool_manager = None
        self._program_line = None
        self._vao_line = None
        self._vbo_line = None
        self._geometry_load_worker = None

    def _glf(self):
        """Return OpenGL functions; must be called with context current."""
        return self._gl

    def initializeGL(self) -> None:
        """Guard against context loss: try init_renderer (3.3 Core), else fallback_mode (2.1 compat)."""
        self.makeCurrent()
        if self._initialized:
            self.doneCurrent()
            return
        try:
            self._init_renderer()
        except Exception as e:
            try:
                self._fallback_mode(e)
            except Exception:
                self._fallback_mode(None)
        self._initialized = True
        self.doneCurrent()

    def _init_renderer(self) -> None:
        """Initialize 3.3 Core: shaders, buffers. Raises on failure."""
        profile = QOpenGLVersionProfile()
        profile.setVersion(3, 3)
        profile.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        ctx = QOpenGLContext.currentContext()
        if not ctx:
            raise RuntimeError("No OpenGL context")
        self._gl = QOpenGLVersionFunctionsFactory.get(profile, ctx)
        if not self._gl or not self._gl.initializeOpenGLFunctions():
            self._gl = None
            raise RuntimeError("OpenGL 3.3 Core not available")
        self._create_shaders()
        self._create_buffers()

    def _fallback_mode(self, exc: Exception | None) -> None:
        """Downgrade to minimal render (2.1 compat): clear only, no geometry. No crash."""
        self._use_fallback = True
        self._gl = None
        self._vao = self._vbo = self._ebo = None
        self._program_mesh = self._program_points = self._program_line = None
        self._vao_line = self._vbo_line = None
        try:
            from PySide6.QtOpenGL import QOpenGLFunctions
            ctx = QOpenGLContext.currentContext()
            if ctx:
                self._gl = QOpenGLFunctions(ctx)
                if self._gl:
                    self._gl.initializeOpenGLFunctions()
        except Exception:
            pass

    def _create_shaders(self) -> None:
        self._program_mesh = QOpenGLShaderProgram()
        self._program_mesh.addShaderFromSourceCode(QOpenGLShader.Vertex, _VERTEX_SHADER)
        self._program_mesh.addShaderFromSourceCode(QOpenGLShader.Fragment, _FRAGMENT_SHADER)
        if not self._program_mesh.link():
            raise RuntimeError("Mesh shader link failed: " + self._program_mesh.log())

        self._program_points = QOpenGLShaderProgram()
        self._program_points.addShaderFromSourceCode(QOpenGLShader.Vertex, _VERTEX_SHADER_POINTS)
        self._program_points.addShaderFromSourceCode(QOpenGLShader.Fragment, _FRAGMENT_SHADER_POINTS)
        if not self._program_points.link():
            raise RuntimeError("Points shader link failed: " + self._program_points.log())

        self._program_line = QOpenGLShaderProgram()
        self._program_line.addShaderFromSourceCode(QOpenGLShader.Vertex, _LINE_VERTEX_SHADER)
        self._program_line.addShaderFromSourceCode(QOpenGLShader.Fragment, _LINE_FRAGMENT_SHADER)
        if not self._program_line.link():
            raise RuntimeError("Line shader link failed: " + self._program_line.log())

    def _create_buffers(self) -> None:
        self._vao = QOpenGLVertexArrayObject()
        self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._ebo = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
        self._vao.create()
        self._vbo.create()
        self._ebo.create()
        self._vao.bind()
        self._vbo.setUsage(QOpenGLBuffer.UsagePattern.DynamicDraw)
        self._ebo.setUsage(QOpenGLBuffer.UsagePattern.DynamicDraw)
        self._vbo.bind()
        self._ebo.bind()
        self._vao.release()
        self._vbo.release()
        self._ebo.release()

        self._vao_line = QOpenGLVertexArrayObject()
        self._vbo_line = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._vao_line.create()
        self._vbo_line.create()
        self._vbo_line.setUsage(QOpenGLBuffer.UsagePattern.DynamicDraw)

    def resizeGL(self, w: int, h: int) -> None:
        self.makeCurrent()
        if w > 0 and h > 0:
            self._camera.set_aspect(w / h)
        if self._gl:
            self._gl.glViewport(0, 0, w, h)
        self.doneCurrent()

    def paintGL(self) -> None:
        self.makeCurrent()
        if not self._gl:
            self.doneCurrent()
            return
        g = self._gl
        g.glClearColor(0.15, 0.15, 0.15, 1.0)
        g.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._use_fallback:
            self.doneCurrent()
            return
        g.glEnable(GL_DEPTH_TEST)

        if self._num_vertices > 0 and self._vao:
            proj = self._camera.projection_matrix()
            view = self._camera.view_matrix()
            eye = self._camera.eye_position()
            model = _identity()
            self._vao.bind()
            if self._num_indices > 0:
                self._program_mesh.bind()
                self._program_mesh.setUniformValue("uProjection", proj)
                self._program_mesh.setUniformValue("uView", view)
                self._program_mesh.setUniformValue("uModel", model)
                self._program_mesh.setUniformValue("uCameraPosition", eye)
                g.glDrawElements(GL_TRIANGLES, self._num_indices, GL_UNSIGNED_INT, None)
            else:
                self._program_points.bind()
                self._program_points.setUniformValue("uProjection", proj)
                self._program_points.setUniformValue("uView", view)
                self._program_points.setUniformValue("uModel", model)
                self._program_points.setUniformValue("uCameraPosition", eye)
                g.glDrawArrays(GL_POINTS, 0, self._num_vertices)
            self._vao.release()
        if self._tool_manager is not None:
            self._tool_manager.draw_overlay(self)
        self.doneCurrent()

    def get_camera_matrices(self) -> dict:
        """Return projection, view, and viewport for ray/overlay. No GL state change."""
        w, h = max(1, self.width()), max(1, self.height())
        return {
            "projection": self._camera.projection_matrix(),
            "view": self._camera.view_matrix(),
            "viewport": (0, 0, w, h),
            "width": w,
            "height": h,
        }

    def compute_ray_from_screen(self, x: float, y: float) -> tuple:
        """
        Compute world-space ray from screen position. Returns (ray_origin, ray_direction) as lists of 3 floats.
        """
        w, h = max(1, self.width()), max(1, self.height())
        view = self._camera.view_matrix()
        proj = self._camera.projection_matrix()
        viewport = QRect(0, 0, w, h)
        wy = h - 1 - y
        near_win = QVector3D(x, wy, 0.0)
        far_win = QVector3D(x, wy, 1.0)
        near_world = near_win.unproject(view, proj, viewport)
        far_world = far_win.unproject(view, proj, viewport)
        dx = far_world.x() - near_world.x()
        dy = far_world.y() - near_world.y()
        dz = far_world.z() - near_world.z()
        L = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
        return (
            [near_world.x(), near_world.y(), near_world.z()],
            [dx / L, dy / L, dz / L],
        )

    def _cursor_to_plane_point(self, x: float, y: float) -> QVector3D | None:
        """Intersect ray at cursor with plane through camera target (for zoom toward cursor)."""
        try:
            ray_origin, ray_dir = self.compute_ray_from_screen(x, y)
            eye = self._camera.eye_position()
            target = self._camera.target()
            n = (target - eye).normalized()
            o = QVector3D(ray_origin[0], ray_origin[1], ray_origin[2])
            d = QVector3D(ray_dir[0], ray_dir[1], ray_dir[2])
            denom = QVector3D.dotProduct(d, n)
            if abs(denom) < 1e-6:
                return None
            t = QVector3D.dotProduct(target - o, n) / denom
            if t < 0:
                return None
            return o + d * t
        except Exception:
            return None

    def set_tool_manager(self, tool_manager) -> None:
        """Set the ToolManager for interaction and overlay. Call from UI layer."""
        self._tool_manager = tool_manager

    def draw_overlay_line_segments(self, segments: list, color: tuple) -> None:
        """Draw line segments in world space. segments: list of ((x,y,z), (x,y,z)); color: (r,g,b) 0-1."""
        if not self._gl or not self._program_line or not self._vao_line:
            return
        g = self._gl
        verts = []
        for a, b in segments:
            verts.extend([a[0], a[1], a[2], b[0], b[1], b[2]])
        if not verts:
            return
        import struct
        data = struct.pack(f"{len(verts)}f", *verts)
        self._vao_line.bind()
        self._vbo_line.bind()
        self._vbo_line.allocate(data, len(data))
        g.glEnableVertexAttribArray(0)
        g.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, 0)
        self._program_line.bind()
        self._program_line.setUniformValue(
            "uProjection", self._camera.projection_matrix()
        )
        self._program_line.setUniformValue("uView", self._camera.view_matrix())
        self._program_line.setUniformValue("uColor", QVector3D(color[0], color[1], color[2]))
        g.glDrawArrays(GL_LINES, 0, len(segments) * 2)
        g.glDisableVertexAttribArray(0)
        self._vbo_line.release()
        self._vao_line.release()
        self._program_line.release()

    def draw_overlay_polygon(self, points: list, color: tuple) -> None:
        """Draw polygon outline as line loop. points: list of (x,y,z)."""
        if len(points) < 2 or not self._gl or not self._program_line:
            return
        segs = [(points[i], points[i + 1]) for i in range(len(points) - 1)]
        segs.append((points[-1], points[0]))
        self.draw_overlay_line_segments(segs, color)

    def draw_overlay_label(self, world_pos: list, text: str) -> None:
        """Minimal: draw a small marker at world position. No text texture; API for future."""
        if not world_pos or len(world_pos) != 3:
            return
        # Draw a short segment as placeholder for label anchor
        p = world_pos
        segs = [([p[0], p[1], p[2]], [p[0], p[1] + 0.05, p[2]])]
        self.draw_overlay_line_segments(segs, (1.0, 1.0, 0.0))

    def draw_overlay_point(self, world_pos: list, value) -> None:
        """Draw a point marker at world position."""
        if not world_pos or len(world_pos) != 3:
            return
        p = world_pos
        segs = [([p[0], p[1], p[2]], [p[0], p[1], p[2]])]
        self.draw_overlay_line_segments(segs, (1.0, 0.5, 0.0))

    def draw_overlay_profile_preview(self, profile_data: dict) -> None:
        """Minimal 2D preview: no complex plotting; optional stub."""
        pass

    def _on_geometry_load_done(
        self,
        vertices: list,
        normals: list,
        colors: list,
        indices: list | None,
        path: str,
        is_point_cloud: bool,
        num_vertices: int,
        num_indices: int,
    ) -> None:
        """Called from main thread when GeometryLoadWorker finishes. Upload to GPU and update."""
        self._geometry_load_worker = None
        self.progressChanged.emit(100)
        if self._use_fallback:
            self._num_vertices = num_vertices
            self._num_indices = num_indices
            self.update()
            self.mesh_loaded.emit(path, num_vertices)
            return
        if indices:
            self._upload_geometry(vertices, normals, colors, indices=indices)
            self._num_indices = num_indices
        else:
            self._upload_geometry(vertices, normals, colors, indices=None)
            self._num_indices = 0
        self._num_vertices = num_vertices
        self.update()
        self.mesh_loaded.emit(path, num_vertices)

    def _on_geometry_load_failed(self, path: str) -> None:
        self._geometry_load_worker = None
        self.progressChanged.emit(0)
        self.geometry_load_failed.emit(path)

    def load_mesh_async(self, file_path: str) -> bool:
        """Start loading a PLY mesh in background thread; progress via progressChanged; result via mesh_loaded/geometry_load_failed. Returns True if worker started."""
        if self._geometry_load_worker is not None and self._geometry_load_worker.isRunning():
            return False
        from mapfree.gui.workers import GeometryLoadWorker

        self._geometry_load_worker = GeometryLoadWorker(str(file_path), is_point_cloud=False)
        self._geometry_load_worker.progress.connect(self.progressChanged.emit)
        self._geometry_load_worker.loadDone.connect(self._on_geometry_load_done)
        self._geometry_load_worker.loadFailed.connect(self._on_geometry_load_failed)
        self._geometry_load_worker.start()
        return True

    def load_point_cloud_async(self, file_path: str) -> bool:
        """Start loading a PLY point cloud in background thread; progress via progressChanged. Returns True if worker started."""
        if self._geometry_load_worker is not None and self._geometry_load_worker.isRunning():
            return False
        from mapfree.gui.workers import GeometryLoadWorker

        self._geometry_load_worker = GeometryLoadWorker(str(file_path), is_point_cloud=True)
        self._geometry_load_worker.progress.connect(self.progressChanged.emit)
        self._geometry_load_worker.loadDone.connect(self._on_geometry_load_done)
        self._geometry_load_worker.loadFailed.connect(self._on_geometry_load_failed)
        self._geometry_load_worker.start()
        return True

    def load_point_cloud(self, file_path: str) -> bool:
        """Load a PLY point cloud (synchronous). Returns True on success. Prefer load_point_cloud_async for large files."""
        data = _load_ply(file_path)
        if data is None or not data["vertices"]:
            return False
        vertices = data["vertices"]
        normals = data.get("normals")
        colors = data.get("colors")
        if not colors:
            colors = [(0.7, 0.7, 0.7)] * len(vertices)
        if not normals:
            normals = [(0.0, 1.0, 0.0)] * len(vertices)
        vertices, normals, colors, _ = _simplify_for_render(vertices, normals, colors, None)
        if not self._use_fallback:
            self._upload_geometry(vertices, normals, colors, indices=None)
        self._num_indices = 0
        self._num_vertices = len(vertices)
        self.update()
        self.mesh_loaded.emit(str(file_path), self._num_vertices)
        return True

    def load_mesh(self, file_path: str) -> bool:
        """Load a PLY mesh (synchronous). Returns True on success. Prefer load_mesh_async for large files."""
        data = _load_ply(file_path)
        if data is None or not data["vertices"]:
            return False
        vertices = data["vertices"]
        normals = data.get("normals")
        colors = data.get("colors")
        indices = data.get("indices")
        if not colors:
            colors = [(0.7, 0.7, 0.7)] * len(vertices)
        if not normals:
            normals = [(0.0, 1.0, 0.0)] * len(vertices)
        vertices, normals, colors, indices = _simplify_for_render(vertices, normals, colors, indices)
        if not self._use_fallback:
            if indices:
                self._upload_geometry(vertices, normals, colors, indices=indices)
                self._num_indices = len(indices)
            else:
                self._upload_geometry(vertices, normals, colors, indices=None)
                self._num_indices = 0
        self._num_vertices = len(vertices)
        self.update()
        self.mesh_loaded.emit(str(file_path), self._num_vertices)
        return True

    def _upload_geometry(
        self,
        vertices: list[tuple[float, float, float]],
        normals: list[tuple[float, float, float]],
        colors: list[tuple[float, float, float]],
        indices: list[int] | None,
    ) -> None:
        """Upload interleaved vertex data (pos, color, normal) and optional EBO. Mesh Buffer Guard: auto-decimate if over MAX_SAFE_VERTICES."""
        import struct
        # Mesh Buffer Guard: before uploading to GPU, cap vertex count to avoid OOM
        if len(vertices) > MAX_SAFE_VERTICES:
            vertices, normals, colors, indices = _simplify_for_render(
                vertices, normals, colors, indices, max_vertices=MAX_SAFE_VERTICES
            )
        buf = []
        for i in range(len(vertices)):
            buf.append(vertices[i][0])
            buf.append(vertices[i][1])
            buf.append(vertices[i][2])
            buf.append(colors[i][0])
            buf.append(colors[i][1])
            buf.append(colors[i][2])
            buf.append(normals[i][0])
            buf.append(normals[i][1])
            buf.append(normals[i][2])
        data = struct.pack(f"{len(buf)}f", *buf)
        self.makeCurrent()
        self._vao.bind()
        self._vbo.bind()
        self._vbo.allocate(data, len(data))
        # Attribute layout: 0=pos(3), 1=color(3), 2=normal(3); stride 9 floats, 36 bytes
        if not self._gl or not self._vao:
            if self._vao:
                self._vao.release()
            self.doneCurrent()
            return
        g = self._gl
        stride = 9 * 4
        g.glEnableVertexAttribArray(0)
        g.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, 0)
        g.glEnableVertexAttribArray(1)
        g.glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, 3 * 4)
        g.glEnableVertexAttribArray(2)
        g.glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, 6 * 4)
        if indices and self._ebo:
            self._ebo.bind()
            self._ebo.allocate(struct.pack(f"{len(indices)}I", *indices), len(indices) * 4)
        self._vao.release()
        self.doneCurrent()

    def zoom_fit(self) -> None:
        """Reset camera to fit the scene (default orbit and distance)."""
        self._camera.reset()
        self.update()

    def toggle_axes(self) -> None:
        """Toggle visibility of coordinate axes in the viewport."""
        self._show_axes = not getattr(self, "_show_axes", False)
        self.update()

    def clear_scene(self) -> None:
        """Clear geometry and release buffer contents."""
        self._num_vertices = 0
        self._num_indices = 0
        self.makeCurrent()
        if self._gl and self._vao and self._vbo and self._ebo:
            g = self._gl
            self._vao.bind()
            self._vbo.bind()
            g.glDisableVertexAttribArray(0)
            g.glDisableVertexAttribArray(1)
            g.glDisableVertexAttribArray(2)
            self._vbo.allocate(0)
            self._ebo.bind()
            self._ebo.allocate(0)
            self._vao.release()
        self.doneCurrent()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        self._last_mouse = pos
        mods = event.modifiers()
        btn = event.button()
        # Ctrl+click → add measurement point (forward to tool only for press)
        if btn == Qt.MouseButton.LeftButton and (mods & Qt.KeyboardModifier.ControlModifier):
            if self._tool_manager is not None and self._tool_manager.handle_mouse_event("press", event):
                self.update()
            return
        # Middle → pan; Left → orbit (no tool consumption)
        if btn == Qt.MouseButton.MiddleButton or btn == Qt.MouseButton.RightButton:
            self._mouse_button = Qt.MouseButton.MiddleButton
            return
        if btn == Qt.MouseButton.LeftButton:
            self._mouse_button = Qt.MouseButton.LeftButton

    def _pick_for_focus(self, x: float, y: float) -> QVector3D | None:
        """Ray pick for double-click focus; returns world point or None."""
        if self._tool_manager is None:
            return None
        mc = getattr(self, "measurement_controller", None)
        if mc is None:
            return None
        hit = mc.ray_pick(x, y)
        if not hit or "point" not in hit:
            return None
        p = hit["point"]
        return QVector3D(p[0], p[1], p[2])

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()
        # If dragging: orbit (left) or pan (middle). Shift = precision orbit.
        if self._mouse_button != Qt.MouseButton.NoButton:
            precision = 0.25 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1.0
            if self._mouse_button == Qt.MouseButton.LeftButton:
                self._camera.orbit(dx * 0.01, -dy * 0.01, precision_scale=precision)
            elif self._mouse_button == Qt.MouseButton.MiddleButton:
                self._camera.pan(dx, dy)
            self._last_mouse = pos
            self.update()
            return
        # No button: forward move to tool (e.g. dynamic preview line)
        if self._tool_manager is not None:
            self._tool_manager.handle_mouse_event("move", event)
        self._last_mouse = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._mouse_button != Qt.MouseButton.NoButton:
            if self._tool_manager is not None:
                self._tool_manager.handle_mouse_event("release", event)
        self._mouse_button = Qt.MouseButton.NoButton
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click → focus object (set orbit center to hit point)."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            hit = self._pick_for_focus(pos.x(), pos.y())
            if hit is not None:
                self._camera.focus_on_point(hit, smooth=False)
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._tool_manager is not None and self._tool_manager.handle_key_event(event):
                self.update()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        pos = event.position()
        pivot = self._cursor_to_plane_point(pos.x(), pos.y()) if pos else None
        if pivot is not None:
            self._camera.zoom_toward_pivot(pivot, delta)
        else:
            self._camera.zoom_toward_pivot(self._camera.target(), delta)
        self.update()

    def minimumSizeHint(self) -> QSize:
        return QSize(320, 240)

    def sizeHint(self) -> QSize:
        return QSize(640, 480)


def _identity() -> QMatrix4x4:
    """4x4 identity matrix for shader uniforms."""
    m = QMatrix4x4()
    m.setToIdentity()
    return m


# Keep GLWidget as alias for backward compatibility
GLWidget = ViewerWidget
