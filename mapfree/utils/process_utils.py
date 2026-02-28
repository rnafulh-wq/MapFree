"""Process and subprocess helpers. Production stub."""

import subprocess
from typing import Optional, List, Callable


def run_cmd(
    cmd: List[str],
    cwd: Optional[str] = None,
    timeout: Optional[float] = None,
    line_callback: Optional[Callable[[str], None]] = None,
    env: Optional[dict] = None,
) -> int:
    """Run command; stream lines to line_callback if given. Return exit code."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=env,
    )
    try:
        if line_callback and proc.stdout:
            for line in proc.stdout:
                line_callback(line.rstrip())
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    return proc.returncode or 0
