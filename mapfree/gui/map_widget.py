"""
Map viewer widget: QWebEngineView loading a Leaflet map from map.html.
GeoJSON layers are injected via runJavaScript (addGeoJSONLayer) after loadFinished.
"""
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import QMessageBox, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

logger = logging.getLogger(__name__)


def _map_html_path() -> Path:
    """Return absolute path to map.html so file:// URL and resources resolve correctly."""
    return (Path(__file__).resolve().parent / "resources" / "map.html").resolve()


class _MapWebEnginePage(QWebEnginePage):
    """
    Custom page that forwards JavaScript console (log, warn, error) to Python
    and logs JS errors.
    """
    jsConsoleMessage = Signal(int, str, int, str)  # level, message, lineNumber, sourceId

    def javaScriptConsoleMessage(self, level, message: str, lineNumber: int, sourceId: str) -> None:
        # Qt: InfoMessageLevel=0, WarningMessageLevel=1, ErrorMessageLevel=2 (enum or int)
        lv = int(level) if level is not None else 0
        lv = max(0, min(lv, 2))
        level_name = ("INFO", "WARN", "ERROR")[lv]
        line = lineNumber if lineNumber is not None else 0
        source = sourceId or ""
        self.jsConsoleMessage.emit(lv, message, line, source)
        log_line = f"[Map JS {level_name}] {message}"
        if source or line:
            log_line += f" (at {source}:{line})"
        if lv == 2:
            logger.error(log_line)
        elif lv == 1:
            logger.warning(log_line)
        else:
            logger.info(log_line)


class MapWidget(QWebEngineView):
    """
    Map widget: loads local map.html (Leaflet) via absolute path, enables JavaScript.
    Waits for loadFinished before injecting any JS. Use load_geojson_layer(name, geojson)
    to add GeoJSON layers. OSM is the default base layer.
    """
    cameraPointClicked = Signal(str)
    # level (0=info, 1=warn, 2=error), message — connect to console panel to show JS log in Python
    jsConsoleMessage = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_layer_visible = True
        self._map_loaded = False
        self._pending_layers: list[tuple[str, dict]] = []
        self._pending_js: list[str] = []
        self._page = _MapWebEnginePage(self)
        self._page.jsConsoleMessage.connect(self._on_js_console_message)
        self.setPage(self._page)
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        self.loadFinished.connect(self._on_load_finished)
        # Load via absolute path so the document base URL is correct
        html_path = _map_html_path()
        if not html_path.exists():
            logger.error("Map HTML not found: %s", html_path)
        url = QUrl.fromLocalFile(str(html_path))
        self.setUrl(url)

    def _on_js_console_message(self, level: int, message: str, lineNumber: int, sourceId: str) -> None:
        """Forward JS console to Python logging and emit for app console panel."""
        prefix = ("[Map]", "[Map WARN]", "[Map ERROR]")[min(max(level, 0), 2)]
        self.jsConsoleMessage.emit(level, f"{prefix} {message}")

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.warning("Map page failed to load (check file path and network for Leaflet CDN).")
            self._warn_no_network()
            return
        self._map_loaded = True
        # Run any JS that was queued before load (e.g. setBaseLayer, setLayerVisibility)
        for script in self._pending_js:
            self.page().runJavaScript(script)
        self._pending_js.clear()
        # Inject pending GeoJSON layers
        for name, geojson in self._pending_layers:
            self._inject_geojson(name, geojson)
        self._pending_layers.clear()
        # Verify Leaflet loaded (e.g. internet was available for CDN)
        self.page().runJavaScript(
            "typeof L !== 'undefined' && typeof map !== 'undefined' ? 'ok' : 'fail'",
            self._on_map_ready_check,
        )

    def _on_map_ready_check(self, result) -> None:
        if result == "fail":
            logger.warning("Leaflet or map object not available; CDN may be unreachable.")
            self._warn_no_network()

    def _warn_no_network(self) -> None:
        """Show a one-time warning when map/network is unavailable."""
        w = self.window()
        if isinstance(w, QWidget):
            QMessageBox.warning(
                w,
                "Map",
                "Map could not load. Check your internet connection (Leaflet is loaded from CDN). "
                "OpenStreetMap tiles also require network access.",
            )

    def _run_js(self, script: str) -> None:
        """Run script only after loadFinished; otherwise queue it."""
        if self._map_loaded:
            self.page().runJavaScript(script)
        else:
            self._pending_js.append(script)

    def _inject_geojson(self, name: str, geojson: dict) -> None:
        script = f"addGeoJSONLayer({json.dumps(name)}, {json.dumps(geojson)});"
        self._run_js(script)

    def load_geojson_layer(self, name: str, geojson: dict) -> None:
        """
        Inject GeoJSON into a Leaflet layer by name.
        Waits for the map to load before injecting; otherwise queues and runs after load.
        """
        if self._map_loaded:
            self._inject_geojson(name, geojson)
        else:
            self._pending_layers.append((name, geojson))

    def load_camera_points(self, geojson: dict) -> None:
        """Convenience: add GeoJSON as the 'Cameras' layer (keeps main_window API)."""
        self.load_geojson_layer("Cameras", geojson)

    def set_camera_layer_visible(self, visible: bool) -> None:
        """Show or hide the Cameras layer."""
        self._camera_layer_visible = bool(visible)
        self._run_set_layer_visibility("Cameras", self._camera_layer_visible)

    def get_camera_layer_visible(self) -> bool:
        return self._camera_layer_visible

    def toggle_layer(self, name: str) -> None:
        """Toggle visibility of a layer by name."""
        if name == "Cameras":
            self._camera_layer_visible = not self._camera_layer_visible
            self._run_set_layer_visibility("Cameras", self._camera_layer_visible)

    def set_basemap(self, name: str) -> None:
        """Switch base layer to 'OpenStreetMap' or 'Satellite' via runJavaScript (after load)."""
        if name not in ("OpenStreetMap", "Satellite"):
            name = "OpenStreetMap"
        self._run_js(
            f"if (typeof setBaseLayer === 'function') setBaseLayer({json.dumps(name)});"
        )

    def _run_set_layer_visibility(self, name: str, visible: bool) -> None:
        name_escaped = json.dumps(name)
        vis = "true" if visible else "false"
        script = (
            f"if (typeof setLayerVisibility === 'function') "
            f"setLayerVisibility({name_escaped}, {vis});"
        )
        self._run_js(script)
