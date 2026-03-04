"""
Map viewer widget: QWebEngineView loading a Leaflet map from map.html.
GeoJSON layers are injected via runJavaScript (addGeoJSONLayer) after loadFinished.
Guard: if QtWebEngine is not available (e.g. PyInstaller without bundle), use placeholder widget.
"""
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import QMessageBox, QWidget, QLabel, QVBoxLayout

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    _WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None
    QWebEnginePage = None
    QWebEngineSettings = None
    _WEBENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)


def _map_html_path() -> Path:
    """Absolute path to map.html; safe for PyInstaller (uses __file__ dir, not cwd)."""
    return (Path(__file__).resolve().parent / "resources" / "map.html").resolve()


class _MapPlaceholder(QWidget):
    """Placeholder when QtWebEngine is not available (e.g. PyInstaller without WebEngine). Same API as MapWidget."""
    cameraPointClicked = Signal(str)
    jsConsoleMessage = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        lab = QLabel("Map (QtWebEngine not available)")
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lab)

    def load_geojson_layer(self, name: str, geojson: dict) -> None:
        pass

    def load_camera_points(self, geojson: dict) -> None:
        pass

    def set_camera_layer_visible(self, visible: bool) -> None:
        pass

    def get_camera_layer_visible(self) -> bool:
        return True

    def toggle_layer(self, name: str) -> None:
        pass

    def set_basemap(self, name: str) -> None:
        pass

    def clear_layers(self) -> None:
        pass


if _WEBENGINE_AVAILABLE:

    class _MapWebEnginePage(QWebEnginePage):
        """
        Custom page that forwards JavaScript console (log, warn, error) to Python
        and logs JS errors.
        """
        jsConsoleMessage = Signal(int, str, int, str)  # level, message, lineNumber, sourceId

        def javaScriptConsoleMessage(self, level, message: str, lineNumber: int, sourceId: str) -> None:
            # PySide6: level is JavaScriptConsoleMessageLevel (enum), use .value for 0/1/2
            if level is None:
                lv = 0
            elif hasattr(level, "value"):
                lv = max(0, min(level.value, 2))
            else:
                lv = max(0, min(int(level), 2))
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
        Map widget: loads local map.html (Leaflet from resources/leaflet/). 100% offline.
        Waits for loadFinished before injecting any JS. Use load_geojson_layer(name, geojson)
        to add GeoJSON layers; clear_layers() to remove all.
        """
        cameraPointClicked = Signal(str)
        jsConsoleMessage = Signal(int, str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._camera_layer_visible = True
            self._map_loaded = False
            self._pending_layers = []
            self._pending_js = []
            self._page = _MapWebEnginePage(self)
            self._page.jsConsoleMessage.connect(self._on_js_console_message)
            self.setPage(self._page)
            settings = self.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
                True,
            )
            try:
                settings.setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                    False,
                )
            except AttributeError:
                pass
            self.loadFinished.connect(self._on_load_finished)
            html_path = _map_html_path()
            if not html_path.exists():
                logger.error("Map HTML not found: %s", html_path)
            self.setUrl(QUrl.fromLocalFile(str(html_path)))

        def _on_js_console_message(self, level: int, message: str, lineNumber: int, sourceId: str) -> None:
            prefix = ("[Map]", "[Map WARN]", "[Map ERROR]")[min(max(level, 0), 2)]
            self.jsConsoleMessage.emit(level, f"{prefix} {message}")

        def _on_load_finished(self, ok: bool) -> None:
            if not ok:
                logger.error("Map page failed to load (check file path: %s).", _map_html_path())
                return
            self._map_loaded = True
            for script in self._pending_js:
                self.page().runJavaScript(script)
            self._pending_js.clear()
            for name, geojson in self._pending_layers:
                self._inject_geojson(name, geojson)
            self._pending_layers.clear()
            self.page().runJavaScript(
                "window.mapReady === true ? 'ok' : 'fail'",
                self._on_map_ready_check,
            )

        def _on_map_ready_check(self, result) -> None:
            if result != "ok":
                logger.error("Map script not ready (window.mapReady !== true).")

        def _run_js(self, script: str) -> None:
            if self._map_loaded:
                self.page().runJavaScript(script)
            else:
                self._pending_js.append(script)

        def _inject_geojson(self, name: str, geojson: dict) -> None:
            self._run_js(
                "addGeoJSONLayer(%s, %s);" % (json.dumps(name), json.dumps(geojson))
            )

        def load_geojson_layer(self, name: str, geojson: dict) -> None:
            if self._map_loaded:
                self._inject_geojson(name, geojson)
            else:
                self._pending_layers.append((name, geojson))

        def load_camera_points(self, geojson: dict) -> None:
            self.load_geojson_layer("Cameras", geojson)

        def set_camera_layer_visible(self, visible: bool) -> None:
            self._camera_layer_visible = bool(visible)
            self._run_set_layer_visibility("Cameras", self._camera_layer_visible)

        def get_camera_layer_visible(self) -> bool:
            return self._camera_layer_visible

        def toggle_layer(self, name: str) -> None:
            if name == "Cameras":
                self._camera_layer_visible = not self._camera_layer_visible
                self._run_set_layer_visibility("Cameras", self._camera_layer_visible)

        def set_basemap(self, name: str) -> None:
            if name not in ("OpenStreetMap", "Satellite"):
                name = "OpenStreetMap"
            self._run_js(f"if (typeof setBaseLayer === 'function') setBaseLayer({json.dumps(name)});")

        def _run_set_layer_visibility(self, name: str, visible: bool) -> None:
            vis = "true" if visible else "false"
            self._run_js(
                "if (typeof setLayerVisibility === 'function') "
                "setLayerVisibility(%s, %s);" % (json.dumps(name), vis)
            )

        def clear_layers(self) -> None:
            self._run_js("if (typeof clearAllLayers === 'function') clearAllLayers();")

else:
    MapWidget = _MapPlaceholder
