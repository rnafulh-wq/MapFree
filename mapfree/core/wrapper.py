"""
Subprocess guard for engine calls (colmap, openmvs, etc.).
Production hardening: timeout, exit-code validation, bounded retry, per-stage log.
All subprocess calls use an env with LD_LIBRARY_PATH including venv/lib so COLMAP
(and other binaries) find libonnxruntime etc. when PATH is not passed through.
"""
import logging
import os
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Callable

# Prepend to LD_LIBRARY_PATH so COLMAP/model_merger etc. find venv libs (e.g. libonnxruntime.so.1).
VENV_LIB = "/media/pop_mangto/E/dev/MapFree/venv/lib"


def get_process_env(env: dict | None = None) -> dict:
    """Return env dict with VENV_LIB prepended to LD_LIBRARY_PATH. Use for any COLMAP subprocess."""
    base = dict(env if env is not None else os.environ)
    base["LD_LIBRARY_PATH"] = VENV_LIB + ":" + base.get("LD_LIBRARY_PATH", "")
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
    Run command with Popen; stream stdout/stderr (combined) line-by-line to logger, log_file, and/or line_callback.
    If stop_event is set, a watcher thread will terminate the process; no zombie left.
    Returns exit code. Raises subprocess.TimeoutExpired on timeout.
    """
    run_env = get_process_env(env)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=run_env,
    )
    log_fp = open(log_file, "a") if log_file else None
    read_done = threading.Event()

    def read_output():
        try:
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
        except Exception as e:
            with open(log_file, "a") as f:
                f.write(f"\n--- Attempt {attempt}: EXCEPTION ---\n")
                f.write(traceback.format_exc())
            attempt += 1
            if attempt >= max_attempts:
                raise
    return True
