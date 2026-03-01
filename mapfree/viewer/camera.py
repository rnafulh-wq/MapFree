"""Camera — orbit, zoom, pan; view and projection matrices for the 3D viewer."""

import math

from PySide6.QtGui import QMatrix4x4, QVector3D


class Camera:
    """Orbit camera: target point, distance, rotation (Euler azimuth/elevation). Orbit, zoom, pan."""

    def __init__(self) -> None:
        self._target = QVector3D(0.0, 0.0, 0.0)
        self._distance = 10.0
        self._azimuth = 0.0   # radians, rotation around world Y
        self._elevation = 0.3 # radians, angle from XZ plane
        self._up = QVector3D(0.0, 1.0, 0.0)
        self._fov_deg = 45.0
        self._aspect = 1.0
        self._near = 0.1
        self._far = 10000.0
        self._min_distance = 0.1
        self._max_distance = 1e6
        self._elevation_min = -math.pi / 2 + 0.01
        self._elevation_max = math.pi / 2 - 0.01

    def _eye_position(self) -> QVector3D:
        """Camera position in world space (derived from target, distance, azimuth, elevation)."""
        d = self._distance
        az, el = self._azimuth, self._elevation
        # Direction from target to eye: Y-up, azimuth in XZ
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
        """Set target point the camera looks at."""
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

    def orbit(self, delta_azimuth: float, delta_elevation: float) -> None:
        """Orbit camera around target. Angles in radians (e.g. from mouse delta)."""
        self._azimuth += delta_azimuth
        self._elevation = max(self._elevation_min, min(self._elevation_max, self._elevation + delta_elevation))

    def pan(self, dx: float, dy: float) -> None:
        """Pan: move target (and view) in view plane. dx, dy in pixel-like units; scale by distance for consistency."""
        eye = self._eye_position()
        forward = (self._target - eye).normalized()
        right = QVector3D.crossProduct(forward, self._up).normalized()
        up = QVector3D.crossProduct(right, forward).normalized()
        scale = self._distance * 0.002
        self._target = self._target + right * (-dx * scale) + up * (dy * scale)

    def zoom(self, delta: float) -> None:
        """Zoom in/out. Positive delta = zoom in (decrease distance)."""
        factor = 1.0 - delta * 0.001
        self._distance = max(self._min_distance, min(self._max_distance, self._distance * factor))

    def eye_position(self) -> QVector3D:
        """Current camera position in world space."""
        return self._eye_position()

    def target(self) -> QVector3D:
        """Current look-at target."""
        return self._target

    def distance(self) -> float:
        """Current distance from camera to target."""
        return self._distance
