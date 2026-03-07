"""
Subprocess guard for engine calls (colmap, openmvs, etc.).
Production hardening: timeout, exit-code validation, bounded retry, per-stage log.
All subprocess calls use an env with LD_LIBRARY_PATH including venv/lib so COLMAP
(and other binaries) find libonnxruntime etc. when PATH is not passed through.
"""
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable


def get_process_env(env: dict | None = None) -> dict:
    """Return env dict. On non-Windows, optionally prepend LD_LIBRARY_PATH from MAPFREE_VENV_LIB if set."""
    base = dict(env if env is not None else os.environ)
    if sys.platform != "win32":
        venv_lib = os.environ.get("MAPFREE_VENV_LIB", "").strip()
        if venv_lib and Path(venv_lib).is_dir():
            base["LD_LIBRARY_PATH"] = venv_lib + os.pathsep + base.get("LD_LIBRARY_PATH", "")
    return base


class EngineExecutionError(Exception):
    """Raised when a subprocess stage fails after retries or times out."""

    pass


def run_process_streaming(
    command: list,
    *,
    cwd: Path | str | None = None,
    env: dict | None = None,
    timeout: int | None = None,
    logger: logging.Logger | None = None,
    log_file: Path | None = None,
    line_callback: Callable[[str], None] | None = None,
    stop_event: threading.Event | None = None,
) -> int:
    """
    Run command with Popen (shell=False, list args). Stream stdout/stderr to logger/log_file/line_callback.
    If stop_event is set, a watcher thread will terminate the process.
    Returns exit code. Raises EngineExecutionError on spawn failure (e.g. executable not found).
    """
    # Ensure list of str (paths with spaces safe; no Path objects)
    command = [str(c) for c in command]
    if logger:
        logger.info("Running: %s", " ".join(command))
    if log_file:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as f:
                f.write("\n--- CMD ---\n%s\n" % " ".join(command))
        except Exception:
            pass

    run_env = get_process_env(env)
    run_cwd = str(Path(cwd).resolve()) if cwd else None
    log_fp = None
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=run_cwd,
            env=run_env,
            shell=False,
        )
    except FileNotFoundError as e:
        msg = (
            "COLMAP executable not found. Please configure path in Settings or set MAPFREE_COLMAP. "
            "Details: %s" % (e,)
        )
        if logger:
            logger.error(msg)
        if log_file:
            try:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a") as f:
                    f.write("\n--- SPAWN FAILED ---\n%s\n" % msg)
            except Exception:
                pass
        raise EngineExecutionError(msg) from e
    except OSError as e:
        msg = "Subprocess failed to start: %s" % (e,)
        if logger:
            logger.error(msg)
        if log_file:
            try:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "a") as f:
                    f.write("\n--- SPAWN FAILED ---\n%s\n" % msg)
            except Exception:
                pass
        raise EngineExecutionError(msg) from e
    if log_file:
        try:
            log_fp = open(log_file, "a")
        except Exception:
            log_fp = None
    read_done = threading.Event()

    def read_output():
        try:
            if proc.stdout is None:
                return
            for line in proc.stdout:
                line = line.rstrip()
                if logger is not None:
                    logger.info(line)
                if log_fp is not None:
                    log_fp.write(line + "\n")
                    log_fp.flush()
                if line_callback is not None:
                    try:
                        line_callback(line)
                    except Exception:
                        pass
        finally:
            if log_fp is not None:
                log_fp.close()
            read_done.set()

    def watcher():
        while proc.poll() is None:
            if stop_event is not None and stop_event.wait(timeout=0.5):
                try:
                    proc.kill()
                except (OSError, ProcessLookupError):
                    pass
                break

    t = threading.Thread(target=read_output, daemon=True)
    t.start()
    if stop_event is not None:
        w = threading.Thread(target=watcher, daemon=True)
        w.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        read_done.wait(timeout=5)
    return proc.returncode


def run_command(
    command: list,
    workspace: Path,
    stage_name: str,
    timeout: int = 7200,
    retry: int = 2,
    cwd: Path | None = None,
    env: dict | None = None,
    logger: logging.Logger | None = None,
    line_callback: Callable[[str], None] | None = None,
    stop_event: threading.Event | None = None,
) -> bool:
    """
    Run command with timeout, retries, and per-stage log. Streams output to log file and optional logger.
    Retries on both non-zero exit and timeout (up to retry attempts).
    Always passes an env with LD_LIBRARY_PATH including venv/lib (so COLMAP finds shared libs).
    """
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{stage_name}.log"
    run_cwd = Path(cwd) if cwd is not None else workspace

    attempt = 0
    max_attempts = retry + 1

    while attempt < max_attempts:
        try:
            with open(log_file, "a") as f:
                f.write(f"\n--- Attempt {attempt} ---\n")
            start = time.time()
            returncode = run_process_streaming(
                command,
                cwd=run_cwd,
                env=env,
                timeout=timeout,
                logger=logger,
                log_file=log_file,
                line_callback=line_callback,
                stop_event=stop_event,
            )
            duration = time.time() - start

            with open(log_file, "a") as f:
                f.write(f"--- Completed in {duration:.1f}s (exit {returncode}) ---\n")

            if returncode != 0:
                with open(log_file, "a") as f:
                    f.write(f"\nExit code: {returncode}\n")
                attempt += 1
                if attempt >= max_attempts:
                    raise EngineExecutionError(
                        f"{stage_name} failed with code {returncode}"
                    )
                continue
            return True

        except subprocess.TimeoutExpired:
            with open(log_file, "a") as f:
                f.write(f"\n--- Attempt {attempt}: TIMEOUT (>{timeout}s) ---\n")
            attempt += 1
            if attempt >= max_attempts:
                raise EngineExecutionError(
                    f"{stage_name} timed out after {max_attempts} attempts"
                )

        except EngineExecutionError:
            raise
        except Exception:
            with open(log_file, "a") as f:
                f.write(f"\n--- Attempt {attempt}: EXCEPTION ---\n")
                f.write(traceback.format_exc())
            attempt += 1
            if attempt >= max_attempts:
                raise
    return True
