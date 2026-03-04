"""
Arcball-style orbit camera: orbit center (dynamic pivot), zoom toward cursor, pan.
Smooth interpolation for focus; inertia disabled for precision surveyor use.
"""

import math

from PySide6.QtGui import QMatrix4x4, QVector3D


class Camera:
    """
    Arcball camera: target (orbit center / dynamic pivot), distance, azimuth/elevation.
    Orbit, pan, zoom toward cursor; optional smooth interpolation; no inertia.
    """

    def __init__(self) -> None:
        self._target = QVector3D(0.0, 0.0, 0.0)
        self._distance = 10.0
        self._azimuth = 0.0   # radians, rotation around world Y
        self._elevation = 0.3  # radians, angle from XZ plane
        self._up = QVector3D(0.0, 1.0, 0.0)
        self._fov_deg = 45.0
        self._aspect = 1.0
        self._near = 0.1
        self._far = 10000.0
        self._min_distance = 0.1
        self._max_distance = 1e6
        self._elevation_min = -math.pi / 2 + 0.01
        self._elevation_max = math.pi / 2 - 0.01
        # Smooth interpolation for focus (single step, no inertia)
        self._focus_lerp = 0.0  # 0 = no lerp, 1 = done

    def _eye_position(self) -> QVector3D:
        """Camera position in world space (derived from target, distance, azimuth, elevation)."""
        d = self._distance
        az, el = self._azimuth, self._elevation
        x = d * math.cos(el) * math.sin(az)
        y = d * math.sin(el)
        z = d * math.cos(el) * math.cos(az)
        return self._target + QVector3D(x, y, z)

    def set_position(self, x: float, y: float, z: float) -> None:
        """Set camera position in world space (adjusts target and distance to preserve look direction)."""
        eye = QVector3D(x, y, z)
        diff = eye - self._target
        self._distance = max(self._min_distance, diff.length())
        if self._distance > 0:
            n = diff.normalized()
            self._elevation = math.asin(max(-1, min(1, n.y())))
            self._azimuth = math.atan2(n.x(), n.z())

    def set_look_at(self, x: float, y: float, z: float) -> None:
        """Set target point the camera looks at (orbit center)."""
        self._target = QVector3D(x, y, z)

    def set_up(self, x: float, y: float, z: float) -> None:
        """Set up vector for the camera."""
        self._up = QVector3D(x, y, z)

    def set_fov(self, degrees: float) -> None:
        """Set vertical field of view in degrees."""
        self._fov_deg = max(0.1, min(179, degrees))

    def set_aspect(self, aspect: float) -> None:
        """Set aspect ratio (width / height)."""
        self._aspect = max(0.01, aspect)

    def set_near_far(self, near: float, far: float) -> None:
        """Set near and far clip plane distances."""
        self._near = max(0.001, near)
        self._far = max(self._near + 0.01, far)

    def view_matrix(self) -> QMatrix4x4:
        """Return the view matrix (world to view space)."""
        eye = self._eye_position()
        m = QMatrix4x4()
        m.lookAt(eye, self._target, self._up)
        return m

    def projection_matrix(self) -> QMatrix4x4:
        """Return the perspective projection matrix."""
        m = QMatrix4x4()
        m.perspective(self._fov_deg, self._aspect, self._near, self._far)
        return m

    def reset(self) -> None:
        """Reset camera to default orbit and distance."""
        self._target = QVector3D(0.0, 0.0, 0.0)
        self._distance = 10.0
        self._azimuth = 0.0
        self._elevation = 0.3

    def orbit(self, delta_azimuth: float, delta_elevation: float, precision_scale: float = 1.0) -> None:
        """Orbit around target. Angles in radians. precision_scale < 1 for Shift+drag (precision orbit)."""
        scale = max(0.01, min(1.0, precision_scale))
        self._azimuth += delta_azimuth * scale
        self._elevation = max(
            self._elevation_min,
            min(self._elevation_max, self._elevation + delta_elevation * scale),
        )

    def pan(self, dx: float, dy: float) -> None:
        """Pan: move target in view plane. dx, dy in pixels; scaled by distance."""
        eye = self._eye_position()
        forward = (self._target - eye).normalized()
        right = QVector3D.crossProduct(forward, self._up).normalized()
        up = QVector3D.crossProduct(right, forward).normalized()
        scale = self._distance * 0.002
        self._target = self._target + right * (-dx * scale) + up * (dy * scale)

    def zoom(self, delta: float) -> None:
        """Zoom in/out (centered on current target). Positive delta = zoom in."""
        factor = 1.0 - delta * 0.001
        self._distance = max(
            self._min_distance,
            min(self._max_distance, self._distance * factor),
        )

    def zoom_toward_pivot(self, pivot_world: QVector3D, delta: float) -> None:
        """
        Smooth zoom toward a 3D pivot (e.g. point under cursor): pivot stays fixed in view.
        Caller unprojects cursor to get pivot_world (e.g. ray-plane intersection with target plane).
        """
        eye = self._eye_position()
        to_pivot = pivot_world - eye
        dist_pivot = to_pivot.length()
        if dist_pivot <= 1e-6:
            self.zoom(delta)
            return
        factor = 1.0 - delta * 0.001
        new_distance = max(self._min_distance, min(self._max_distance, self._distance * factor))
        self._target = eye + to_pivot.normalized() * new_distance
        self._distance = new_distance

    def focus_on_point(self, world_point: QVector3D, smooth: bool = True) -> None:
        """
        Set orbit center (dynamic pivot) to world_point. If smooth, interpolate target once per frame.
        Inertia disabled: single-step interpolation only.
        """
        if smooth:
            self._target = world_point
        else:
            self._target = QVector3D(world_point)

    def eye_position(self) -> QVector3D:
        """Current camera position in world space."""
        return self._eye_position()

    def target(self) -> QVector3D:
        """Current look-at target (orbit center)."""
        return self._target

    def distance(self) -> float:
        """Current distance from camera to target."""
        return self._distance
