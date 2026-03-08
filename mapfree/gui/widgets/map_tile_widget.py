"""
OSM tile map viewer using QGraphicsView (no WebEngine, no external browser).
Tiles downloaded via requests, cached under ~/.mapfree/tile_cache/.
GPS photo positions overlaid as QGraphicsEllipseItem; pan and zoom supported.
"""

import logging
import math
from pathlib import Path
from typing import Optional

import requests
from PySide6.QtCore import QThread, Signal, QRectF
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor
from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsTextItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

logger = logging.getLogger(__name__)

TILE_SIZE = 256
OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
CACHE_DIR = Path.home() / ".mapfree" / "tile_cache"

# Zoom limits (OSM typical range)
ZOOM_MIN = 1
ZOOM_MAX = 19


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert WGS84 lat/lon to OSM tile indices (integer) at given zoom."""
    n = 2**zoom
    x = int((lon + 180) / 360 * n)
    y = int(
        (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat)))
         / math.pi)
        / 2
        * n
    )
    return x, y


def lat_lon_to_tile_frac(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Convert WGS84 lat/lon to OSM tile coordinates (float) for pixel placement."""
    n = 2**zoom
    x = (lon + 180) / 360 * n
    y = (
        (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat)))
         / math.pi)
        / 2
        * n
    )
    return x, y


def tile_to_pixel(
    tx: int, ty: int, zoom: int, lat: float, lon: float
) -> tuple[float, float]:
    """Return scene position (top-left) for tile (tx, ty). lat/lon unused (kept for API)."""
    del zoom, lat, lon
    return (float(tx * TILE_SIZE), float(ty * TILE_SIZE))


class TileDownloader(QThread):
    """Download a single OSM tile in background; emit pixmap when ready."""

    tile_ready = Signal(int, int, int, QPixmap)  # z, x, y, pixmap

    def __init__(self, z: int, x: int, y: int) -> None:
        super().__init__()
        self.z, self.x, self.y = z, x, y

    def run(self) -> None:
        cache_path = CACHE_DIR / str(self.z) / str(self.x) / f"{self.y}.png"
        if cache_path.exists():
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                self.tile_ready.emit(self.z, self.x, self.y, pixmap)
            return
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = requests.get(
                OSM_URL.format(z=self.z, x=self.x, y=self.y),
                headers={"User-Agent": "MapFree/1.1"},
                timeout=5,
            )
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
            pixmap = QPixmap()
            if pixmap.loadFromData(resp.content):
                self.tile_ready.emit(self.z, self.x, self.y, pixmap)
        except Exception as e:
            logger.debug("Tile download failed %s/%s/%s: %s", self.z, self.x, self.y, e)


class MapTileWidget(QWidget):
    """
    Map widget: OSM tiles via QGraphicsView, no WebEngine.
    Compatible API with former MapWidget: load_geojson_layer, load_camera_points,
    fit_to_photos, set_basemap, clear_layers, camera layer visibility, jsConsoleMessage.
    """

    cameraPointClicked = Signal(str)
    jsConsoleMessage = Signal(int, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(0, 0)
        self.zoom = 16
        self.center_lat = 0.0
        self.center_lon = 0.0
        self._photo_points: list[tuple[float, float]] = []
        self._camera_layer_visible = True
        self._tile_items: dict[tuple[int, int, int], QGraphicsPixmapItem] = {}
        self._point_items: list[QGraphicsEllipseItem] = []
        self._downloaders: list[TileDownloader] = []
        self._no_connection_item: Optional[QGraphicsTextItem] = None
        self._pending_tiles: int = 0

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setRenderHint(self.view.renderHints() | self.view.RenderHint.SmoothPixmapTransform)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.wheelEvent = self._on_wheel  # type: ignore[method-assign]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self._no_connection_item = QGraphicsTextItem("Tidak ada koneksi internet")
        self._no_connection_item.setDefaultTextColor(QColor(120, 120, 120))
        self._no_connection_item.setZValue(1000)
        self.scene.addItem(self._no_connection_item)
        self._no_connection_item.hide()

    def set_center(self, lat: float, lon: float) -> None:
        """Set map center and reload tiles."""
        self.center_lat = lat
        self.center_lon = lon
        self._load_tiles()

    def set_photo_points(self, points: list[tuple[float, float]]) -> None:
        """Set GPS points (lat, lon) for overlay."""
        self._photo_points = list(points)
        self._draw_points()

    def load_geojson_layer(self, name: str, geojson: dict) -> None:
        """Load a GeoJSON layer; only 'Cameras' is supported (points overlay)."""
        if name != "Cameras":
            return
        points: list[tuple[float, float]] = []
        for f in geojson.get("features") or []:
            geom = f.get("geometry") or {}
            if geom.get("type") != "Point":
                continue
            coords = geom.get("coordinates")
            if not coords or len(coords) < 2:
                continue
            lon_f, lat_f = float(coords[0]), float(coords[1])
            points.append((lat_f, lon_f))
        self.set_photo_points(points)
        if points:
            lat_sum = sum(p[0] for p in points)
            lon_sum = sum(p[1] for p in points)
            self.set_center(lat_sum / len(points), lon_sum / len(points))

    def load_camera_points(self, geojson: dict) -> None:
        """Same as load_geojson_layer('Cameras', geojson)."""
        self.load_geojson_layer("Cameras", geojson)

    def set_camera_layer_visible(self, visible: bool) -> None:
        """Show or hide camera/photo points overlay."""
        self._camera_layer_visible = bool(visible)
        for item in self._point_items:
            item.setVisible(self._camera_layer_visible)

    def get_camera_layer_visible(self) -> bool:
        return self._camera_layer_visible

    def toggle_layer(self, name: str) -> None:
        """Toggle layer visibility; only 'Cameras' is supported."""
        if name == "Cameras":
            self.set_camera_layer_visible(not self._camera_layer_visible)

    def set_basemap(self, name: str) -> None:
        """Ignored for tile widget (OSM only). Kept for API compatibility."""
        del name

    def clear_layers(self) -> None:
        """Clear photo points and optionally reset view."""
        self._photo_points.clear()
        self._draw_points()

    def fit_to_photos(self) -> None:
        """Adjust center and zoom to fit all photo points."""
        if not self._photo_points:
            return
        lats = [p[0] for p in self._photo_points]
        lons = [p[1] for p in self._photo_points]
        lat_min, lat_max = min(lats), max(lats)
        lon_min, lon_max = min(lons), max(lons)
        self.center_lat = (lat_min + lat_max) / 2
        self.center_lon = (lon_min + lon_max) / 2
        # Simple zoom: fit roughly to bbox (could refine with view size)
        span_lat = max(lat_max - lat_min, 0.001)
        span_lon = max(lon_max - lon_min, 0.001)
        span = max(span_lat, span_lon)
        for z in range(ZOOM_MAX, ZOOM_MIN - 1, -1):
            n = 2**z
            if 360.0 / n < span * 2 and 180.0 / n < span * 2:
                self.zoom = z
                break
        self._load_tiles()
        self._draw_points()

    def _load_tiles(self) -> None:
        """Load 5x5 grid of tiles around center in background threads."""
        for d in self._downloaders:
            if d.isRunning():
                d.quit()
                d.wait(500)
        self._downloaders.clear()
        for key in list(self._tile_items):
            item = self._tile_items.pop(key)
            self.scene.removeItem(item)
        cx, cy = lat_lon_to_tile(self.center_lat, self.center_lon, self.zoom)
        self._pending_tiles = 0
        self._no_connection_item.hide()
        half = 2
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                tx, ty = cx + dx, cy + dy
                px, py = tile_to_pixel(tx, ty, self.zoom, self.center_lat, self.center_lon)
                self._pending_tiles += 1
                d = TileDownloader(self.zoom, tx, ty)
                d.tile_ready.connect(self._on_tile_ready)
                self._downloaders.append(d)
                d.start()
        # Scene rect for 5x5 grid
        left = (cx - half) * TILE_SIZE
        top = (cy - half) * TILE_SIZE
        self.scene.setSceneRect(QRectF(left, top, (2 * half + 1) * TILE_SIZE, (2 * half + 1) * TILE_SIZE))
        center_px = (cx + 0.5) * TILE_SIZE
        center_py = (cy + 0.5) * TILE_SIZE
        self.view.centerOn(center_px, center_py)
        # Show placeholder until at least one tile loads
        self._no_connection_item.setPos(left + (2 * half + 1) * TILE_SIZE / 2 - 80, top + (2 * half + 1) * TILE_SIZE / 2 - 12)
        self._no_connection_item.show()

    def _on_tile_ready(self, z: int, x: int, y: int, pixmap: QPixmap) -> None:
        """Add tile pixmap to scene at correct position."""
        self._pending_tiles -= 1
        if pixmap.isNull():
            if self._pending_tiles <= 0 and not self._tile_items:
                self._no_connection_item.show()
                self.jsConsoleMessage.emit(2, "Map: Tidak ada koneksi internet.")
            return
        if (z, x, y) in self._tile_items:
            return
        px, py = tile_to_pixel(x, y, z, self.center_lat, self.center_lon)
        item = QGraphicsPixmapItem(pixmap)
        item.setPos(px, py)
        item.setZValue(-1)
        self.scene.addItem(item)
        self._tile_items[(z, x, y)] = item
        self._no_connection_item.hide()

    def _draw_points(self) -> None:
        """Draw red circles for each photo GPS point."""
        for item in self._point_items:
            self.scene.removeItem(item)
        self._point_items.clear()
        if not self._photo_points or not self._camera_layer_visible:
            return
        radius = 6
        pen = QPen(QColor(200, 50, 50), 2)
        brush = QBrush(QColor(220, 80, 80, 180))
        for lat, lon in self._photo_points:
            tx, ty = lat_lon_to_tile_frac(lat, lon, self.zoom)
            sx = tx * TILE_SIZE
            sy = ty * TILE_SIZE
            ellipse = QGraphicsEllipseItem(sx - radius, sy - radius, radius * 2, radius * 2)
            ellipse.setPen(pen)
            ellipse.setBrush(brush)
            ellipse.setZValue(10)
            ellipse.setVisible(self._camera_layer_visible)
            self.scene.addItem(ellipse)
            self._point_items.append(ellipse)

    def _on_wheel(self, event) -> None:
        """Zoom in/out with scroll wheel."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom = min(ZOOM_MAX, self.zoom + 1)
        else:
            self.zoom = max(ZOOM_MIN, self.zoom - 1)
        self._load_tiles()
        self._draw_points()
        event.accept()
