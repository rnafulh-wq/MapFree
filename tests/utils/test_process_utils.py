"""Tests for mapfree.utils.process_utils."""
import subprocess
import pytest

from mapfree.utils.process_utils import run_cmd


class TestRunCmd:
    def test_successful_command(self):
        rc = run_cmd(["python", "-c", "pass"])
        assert rc == 0

    def test_failing_command(self):
        rc = run_cmd(["python", "-c", "import sys; sys.exit(3)"])
        assert rc == 3

    def test_line_callback_receives_output(self):
        lines = []
        run_cmd(["python", "-c", "print('hello'); print('world')"], line_callback=lines.append)
        assert any("hello" in ln for ln in lines)
        assert any("world" in ln for ln in lines)

    def test_timeout_raises(self):
        with pytest.raises(subprocess.TimeoutExpired):
            run_cmd(["python", "-c", "import time; time.sleep(3)"], timeout=0.3)

    def test_cwd_parameter(self, tmp_path):
        rc = run_cmd(["python", "-c", "pass"], cwd=str(tmp_path))
        assert rc == 0

    def test_env_parameter(self):
        import os
        env = dict(os.environ)
        env["TEST_VAR_MAPFREE"] = "hello"
        lines = []
        run_cmd(
            ["python", "-c", "import os; print(os.environ.get('TEST_VAR_MAPFREE', ''))"],
            env=env,
            line_callback=lines.append,
        )
        assert any("hello" in ln for ln in lines)
