"""
Subprocess guard for engine calls (colmap, openmvs, etc.).
Production hardening: timeout, exit-code validation, bounded retry, per-stage log.
All subprocess calls use an env with LD_LIBRARY_PATH including venv/lib so COLMAP
(and other binaries) find libonnxruntime etc. when PATH is not passed through.
"""
import os
import subprocess
import time
import traceback
from pathlib import Path

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


def run_command(
    command: list,
    workspace: Path,
    stage_name: str,
    timeout: int = 7200,
    retry: int = 2,
    cwd: Path | None = None,
    env: dict | None = None,
) -> bool:
    """
    Run command with timeout, retries, and per-stage log.
    Retries on both non-zero exit and timeout (up to retry attempts).
    Always passes an env with LD_LIBRARY_PATH including venv/lib (so COLMAP finds shared libs).
    """
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{stage_name}.log"
    run_cwd = Path(cwd) if cwd is not None else workspace
    run_env = get_process_env(env)

    attempt = 0
    max_attempts = retry + 1

    while attempt < max_attempts:
        try:
            start = time.time()
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                text=True,
                cwd=run_cwd,
                env=run_env,
            )
            duration = time.time() - start

            with open(log_file, "a") as f:
                f.write(f"\n--- Attempt {attempt} ({duration:.1f}s) ---\n")
                if result.stdout:
                    f.write(result.stdout)
                if result.stderr:
                    f.write(result.stderr)

            if result.returncode != 0:
                with open(log_file, "a") as f:
                    f.write(f"\nExit code: {result.returncode}\n")
                attempt += 1
                if attempt >= max_attempts:
                    raise EngineExecutionError(
                        f"{stage_name} failed with code {result.returncode}"
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
