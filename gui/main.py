"""
Flask web UI for MapFree.
- Run as desktop app (pywebview): python -m gui.main
- Run as server only: flask --app gui.main run
"""
import atexit
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
from flask import Flask, Response, request, render_template

# Template folder: gui/templates (relative to package)
GUI_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GUI_DIR.parent
TEMPLATES = GUI_DIR / "templates"
CONFIG_JSON = GUI_DIR / "config.json"
CORE_SCRIPT = PROJECT_ROOT / "core" / "mapfree_core.sh"

# Console log queue for SSE (stdout from mapping process)
_console_queue = queue.Queue()
# Processing status (CPU/RAM/progress) for /api/processing/status
_processing_status = {"running": False, "cpu": 0, "ram_mb": 0, "progress": 0, "elapsed_sec": 0, "paused": False}
_processing_lock = threading.Lock()
_process_start_time = None
_current_process = None  # subprocess.Popen for Cancel/Pause

app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=None)


def _load_config_json():
    """Load hardware config from gui/config.json."""
    if not CONFIG_JSON.exists():
        return {"gpu_enabled": True, "gpu_id": 0, "cpu_threads": 4, "primary_device": "gpu"}
    try:
        with open(CONFIG_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"gpu_enabled": True, "gpu_id": 0, "cpu_threads": 4, "primary_device": "gpu"}


def _save_config_json(data):
    """Save hardware config to gui/config.json."""
    with open(CONFIG_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_core_with_config(image_folder: str, output_folder: str, quality: str = "medium"):
    """
    Run MapFree pipeline with parameters from config.json.
    Passes --quality so CLI does not block on stdin prompt.
    """
    config = _load_config_json()
    cmd = [
        sys.executable, "-m", "mapfree.cli", "run",
        str(image_folder), "--output", str(output_folder),
        "--quality", (quality or "medium"),
    ]
    if not config.get("gpu_enabled", True):
        cmd.extend(["--force-profile", "CPU_SAFE"])
    return subprocess.Popen(
        cmd,
        env=None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(PROJECT_ROOT),
        start_new_session=True,
    )


def _stdout_reader(process: subprocess.Popen):
    """Daemon thread: read process stdout line by line and put into _console_queue."""
    try:
        for line in iter(process.stdout.readline, ""):
            line = (line or "").rstrip()
            if line:
                _console_queue.put({"msg": line, "level": "info"})
    except (ValueError, BrokenPipeError):
        pass
    finally:
        if process.stdout:
            try:
                process.stdout.close()
            except OSError:
                pass


def _status_poller(process: subprocess.Popen):
    """Daemon thread: update _processing_status (CPU, RAM, elapsed) every second until process exits."""
    global _process_start_time, _current_process
    try:
        while process.poll() is None:
            with _processing_lock:
                try:
                    _processing_status["cpu"] = round(psutil.cpu_percent(interval=None) or 0, 1)
                    _processing_status["ram_mb"] = round(psutil.virtual_memory().used / (1024 * 1024), 1)
                    if _process_start_time:
                        _processing_status["elapsed_sec"] = int(time.time() - _process_start_time)
                except Exception:
                    pass
            time.sleep(1)
    finally:
        with _processing_lock:
            _processing_status["running"] = False
            _processing_status["paused"] = False
        if _current_process is process:
            _current_process = None


def start_mapping_process(image_folder: str, output_folder: str, quality: str = "medium"):
    """
    Start the mapping pipeline (core/mapfree_core.sh or Python CLI), stream stdout to
    console queue, and update CPU/RAM status. Passes --quality so CLI does not block on prompt.
    Returns immediately; process runs in background.
    """
    global _process_start_time, _current_process
    image_folder = (image_folder or "").strip()
    output_folder = (output_folder or "").strip()
    quality = (quality or "medium").strip().lower()
    if quality not in ("high", "medium", "low"):
        quality = "medium"
    if not image_folder or not output_folder:
        _console_queue.put({"msg": "Image folder and output folder are required.", "level": "error"})
        return
    with _processing_lock:
        if _processing_status["running"]:
            _console_queue.put({"msg": "A process is already running.", "level": "warn"})
            return
        _processing_status["running"] = True
        _processing_status["paused"] = False
        _processing_status["cpu"] = 0
        _processing_status["ram_mb"] = 0
        _processing_status["progress"] = 0
        _processing_status["elapsed_sec"] = 0
    _process_start_time = time.time()
    _current_process = None
    _console_queue.put({"msg": "Starting mapping process (quality=%s): %s -> %s" % (quality, image_folder, output_folder), "level": "info"})
    env = dict(__import__("os").environ)
    env["IMAGE_FOLDER"] = image_folder
    env["OUTPUT_FOLDER"] = output_folder
    env["QUALITY"] = quality
    try:
        if CORE_SCRIPT.exists():
            process = subprocess.Popen(
                ["/bin/bash", str(CORE_SCRIPT)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(PROJECT_ROOT),
                env=env,
                start_new_session=True,
            )
        else:
            process = run_core_with_config(image_folder, output_folder, quality)
    except Exception as e:
        with _processing_lock:
            _processing_status["running"] = False
        _console_queue.put({"msg": "Failed to start process: %s" % e, "level": "error"})
        return
    _current_process = process
    t1 = threading.Thread(target=_stdout_reader, args=(process,), daemon=True)
    t2 = threading.Thread(target=_status_poller, args=(process,), daemon=True)
    t1.start()
    t2.start()


def _kill_mapping_process(proc, force: bool = False):
    """Terminate process and its whole group (so bash + python child both exit)."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if hasattr(os, "killpg") and hasattr(signal, "SIGTERM"):
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL if force else signal.SIGTERM)
            except (OSError, ProcessLookupError):
                proc.terminate()
        else:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    except (OSError, ProcessLookupError, ValueError):
        pass


def _terminate_background_process():
    """Called on app exit (atexit): ensure mapping process is stopped when MapFree closes."""
    global _current_process
    with _processing_lock:
        proc = _current_process
        _current_process = None
        _processing_status["running"] = False
        _processing_status["paused"] = False
    _kill_mapping_process(proc, force=True)


atexit.register(_terminate_background_process)


def stop_mapping_process():
    """Terminate the running mapping process (Cancel)."""
    global _current_process
    with _processing_lock:
        proc = _current_process
        _current_process = None
    if proc is not None and proc.poll() is None:
        try:
            _kill_mapping_process(proc, force=False)
            try:
                _console_queue.put({"msg": "Process cancelled by user.", "level": "warn"})
            except Exception:
                pass
        except Exception as e:
            try:
                _console_queue.put({"msg": "Cancel failed: %s" % e, "level": "error"})
            except Exception:
                pass
    with _processing_lock:
        _processing_status["running"] = False
        _processing_status["paused"] = False


def pause_mapping_process():
    """Pause the running process (SIGSTOP, Unix only)."""
    global _current_process
    with _processing_lock:
        proc = _current_process
        if proc is not None and proc.poll() is None:
            _processing_status["paused"] = True
    if proc is not None and proc.poll() is None:
        try:
            import os
            import signal
            os.kill(proc.pid, signal.SIGSTOP)
            _console_queue.put({"msg": "Process paused.", "level": "info"})
        except (AttributeError, OSError, ValueError):
            _processing_status["paused"] = False
            _console_queue.put({"msg": "Pause not supported on this system.", "level": "warn"})


def resume_mapping_process():
    """Resume a paused process (SIGCONT, Unix only)."""
    global _current_process
    with _processing_lock:
        proc = _current_process
        if proc is not None and proc.poll() is None:
            _processing_status["paused"] = False
    if proc is not None and proc.poll() is None:
        try:
            import os
            import signal
            os.kill(proc.pid, signal.SIGCONT)
            _console_queue.put({"msg": "Process resumed.", "level": "info"})
        except (AttributeError, OSError, ValueError):
            _console_queue.put({"msg": "Resume failed.", "level": "warn"})


@app.route("/")
def dashboard():
    """Tampilan awal: dashboard modular (extends base.html)."""
    return render_template("dashboard.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/gcp")
def gcp():
    return render_template("gcp.html")


@app.route("/export")
def export_view():
    return render_template("export_view.html")


@app.route("/processing")
def processing():
    return render_template("processing.html")


@app.route("/gallery")
def gallery():
    return render_template("gallery.html")


@app.route("/project/new")
def project_new():
    return render_template("project_new.html")


@app.route("/map")
def map_view():
    return render_template("map_view.html")


@app.route("/quality-report")
def quality_report():
    return render_template("quality_report.html")


@app.route("/select-crs")
def select_crs():
    return render_template("select_crs.html")


@app.route("/point-cloud-classification")
def point_cloud_classification():
    return render_template("point_cloud_classification.html")


def _get_hardware_recommendation():
    """Return vram_mb, ram_gb, recommended_quality from mapfree hardware + config. Safe if mapfree missing."""
    try:
        from mapfree.utils.hardware import get_hardware_profile
        from mapfree.core.config import recommend_quality_from_hardware
        h = get_hardware_profile()
        quality = recommend_quality_from_hardware(h.vram_mb, h.ram_gb)
        return {"vram_mb": h.vram_mb, "ram_gb": round(h.ram_gb, 2), "recommended_quality": quality}
    except Exception:
        return {"vram_mb": 0, "ram_gb": 0, "recommended_quality": "medium"}


@app.route("/api/hardware/recommend")
def api_hardware_recommend():
    """Return hardware-based quality recommendation (VRAM/RAM) for smart scaling."""
    return _get_hardware_recommendation()


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """GET: return hardware config from config.json. POST: save config from UI."""
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        allowed = {"gpu_enabled", "gpu_id", "cpu_threads", "primary_device"}
        config = _load_config_json()
        for k in allowed:
            if k in data:
                config[k] = data[k]
        _save_config_json(config)
        return {"ok": True}
    return _load_config_json()


@app.route("/api/console/stream")
def console_stream():
    """Server-Sent Events: stream log lines from _console_queue (stdout of mapping process)."""
    def generate():
        yield "data: {\"msg\":\"Console stream connected.\",\"level\":\"info\"}\n\n"
        while True:
            try:
                item = _console_queue.get(timeout=2)
                yield "data: %s\n\n" % json.dumps(item)
            except queue.Empty:
                yield ": keepalive\n\n"
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/processing/status")
def api_processing_status():
    """Return current CPU/RAM/running state for the processing page."""
    with _processing_lock:
        return dict(_processing_status)


@app.route("/api/processing/start", methods=["POST"])
def api_processing_start():
    """Start mapping process from JSON body (for browser mode when pywebview not available)."""
    data = request.get_json(force=True, silent=True) or {}
    image_folder = (data.get("image_folder") or "").strip()
    output_folder = (data.get("output_folder") or "").strip()
    quality = (data.get("quality") or "medium").strip().lower()
    if quality not in ("high", "medium", "low"):
        quality = "medium"
    start_mapping_process(image_folder, output_folder, quality)
    return {"ok": True}


@app.route("/api/processing/stop", methods=["POST"])
def api_processing_stop():
    """Cancel the running mapping process."""
    stop_mapping_process()
    return {"ok": True}


@app.route("/api/processing/pause", methods=["POST"])
def api_processing_pause():
    """Pause the running process (Unix: SIGSTOP)."""
    pause_mapping_process()
    return {"ok": True}


@app.route("/api/processing/resume", methods=["POST"])
def api_processing_resume():
    """Resume a paused process (Unix: SIGCONT)."""
    resume_mapping_process()
    return {"ok": True}


def _run_flask():
    app.run(host="127.0.0.1", port=5000, use_reloader=False, debug=False)


if __name__ == "__main__":
    import webbrowser

    try:
        import webview
        WebViewException = webview.WebViewException
    except ImportError:
        webview = None
        WebViewException = Exception

    # Jalankan Flask di thread agar webview/browser bisa load http://127.0.0.1:5000/
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    time.sleep(1.2)

    def _open_in_browser():
        print(
            "PyWebView: native window unavailable. Opening in browser.\n"
            "For native window on Linux (GTK):\n"
            "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1\n"
            "  pip install pywebview[gtk]"
        )
        webbrowser.open("http://127.0.0.1:5000/")
        flask_thread.join()

    if webview is None:
        _open_in_browser()
    else:
        try:
            window = webview.create_window(
                "MapFree",
                "http://127.0.0.1:5000/",
                width=1400,
                height=900,
                frameless=False,
                resizable=True,
            )

            def select_folder():
                # Gunakan window yang sama (bukan active_window) agar dialog tetap jalan setelah navigasi
                try:
                    result = window.create_file_dialog(webview.FOLDER_DIALOG)
                    if result:
                        return result[0]
                except Exception as e:
                    # Agar JS Promise reject dan error bisa ditampilkan
                    raise RuntimeError(str(e))
                return None

            window.expose(select_folder, start_mapping_process, stop_mapping_process, pause_mapping_process, resume_mapping_process)
            webview.start()
        except WebViewException:
            _open_in_browser()
        except Exception as e:
            if "QT" in str(e) or "GTK" in str(e) or "gi" in str(e):
                _open_in_browser()
            else:
                raise
