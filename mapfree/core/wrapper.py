"""
Subprocess guard for engine calls (colmap, openmvs, etc.).
Production hardening: timeout, exit-code validation, bounded retry, per-stage log.
"""
import subprocess
import time
import traceback
from pathlib import Path


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
) -> bool:
    """
    Run command with timeout, retries, and per-stage log.
    Retries on both non-zero exit and timeout (up to retry attempts).
    """
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{stage_name}.log"
    run_cwd = Path(cwd) if cwd is not None else workspace

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
