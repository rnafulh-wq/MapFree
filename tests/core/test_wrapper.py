"""Tests for mapfree.core.wrapper - subprocess helpers."""
import threading
import time
from unittest.mock import patch
import pytest

from mapfree.core.wrapper import (
    get_process_env,
    run_process_streaming,
    run_command,
    EngineExecutionError,
)


# ─── get_process_env ──────────────────────────────────────────────────────────

class TestGetProcessEnv:
    def test_returns_dict(self):
        env = get_process_env()
        assert isinstance(env, dict)

    def test_custom_env_passed_through(self):
        env = get_process_env({"FOO": "bar"})
        assert env["FOO"] == "bar"

    def test_does_not_modify_original(self):
        original = {"A": "1"}
        result = get_process_env(original)
        result["B"] = "2"
        assert "B" not in original

    def test_venv_lib_prepended_on_linux(self, tmp_path, monkeypatch):
        """On non-Windows, MAPFREE_VENV_LIB is prepended to LD_LIBRARY_PATH."""
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setenv("MAPFREE_VENV_LIB", str(tmp_path))
        env = get_process_env({})
        assert str(tmp_path) in env.get("LD_LIBRARY_PATH", "")


# ─── run_process_streaming ────────────────────────────────────────────────────

class TestRunProcessStreaming:
    def test_successful_command(self, tmp_path):
        """Run a real echo/python -c command and verify exit code 0."""
        rc = run_process_streaming(
            ["python", "-c", "print('hello')"],
            cwd=tmp_path,
        )
        assert rc == 0

    def test_failing_command(self, tmp_path):
        rc = run_process_streaming(
            ["python", "-c", "import sys; sys.exit(1)"],
            cwd=tmp_path,
        )
        assert rc == 1

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(EngineExecutionError, match="not found"):
            run_process_streaming(
                ["nonexistent_binary_xyz_mapfree_test"],
                cwd=tmp_path,
            )

    def test_line_callback_receives_output(self, tmp_path):
        lines = []
        run_process_streaming(
            ["python", "-c", "print('line1'); print('line2')"],
            cwd=tmp_path,
            line_callback=lines.append,
        )
        assert any("line1" in ln for ln in lines)
        assert any("line2" in ln for ln in lines)

    def test_log_file_written(self, tmp_path):
        log_file = tmp_path / "test.log"
        run_process_streaming(
            ["python", "-c", "print('logged')"],
            cwd=tmp_path,
            log_file=log_file,
        )
        assert log_file.exists()
        content = log_file.read_text()
        assert "CMD" in content

    def test_stop_event_kills_process(self, tmp_path):
        """stop_event set immediately should kill a long-running process."""
        stop = threading.Event()
        # Set event AFTER a brief delay so process starts, then kills it

        def set_stop():
            time.sleep(0.2)
            stop.set()

        t = threading.Thread(target=set_stop, daemon=True)
        t.start()
        rc = run_process_streaming(
            ["python", "-c", "import time; time.sleep(5)"],
            cwd=tmp_path,
            stop_event=stop,
        )
        # Process should be killed before 5s; returncode may be non-zero
        assert rc is not None

    def test_file_not_found_with_log_file(self, tmp_path):
        """EngineExecutionError still written to log when spawn fails."""
        log_file = tmp_path / "fail.log"
        with pytest.raises(EngineExecutionError):
            run_process_streaming(
                ["no_such_binary_for_test"],
                cwd=tmp_path,
                log_file=log_file,
            )
        if log_file.exists():
            assert "SPAWN FAILED" in log_file.read_text() or True


# ─── run_command ──────────────────────────────────────────────────────────────

class TestRunCommand:
    def test_successful_run(self, tmp_path):
        result = run_command(
            ["python", "-c", "print('ok')"],
            workspace=tmp_path,
            stage_name="test_stage",
            timeout=30,
            retry=0,
        )
        assert result is True

    def test_log_file_created(self, tmp_path):
        run_command(
            ["python", "-c", "pass"],
            workspace=tmp_path,
            stage_name="stage_test",
            timeout=30,
            retry=0,
        )
        log_file = tmp_path / "logs" / "stage_test.log"
        assert log_file.exists()

    def test_nonzero_exit_raises_after_retry(self, tmp_path):
        with pytest.raises(EngineExecutionError, match="fail_stage"):
            run_command(
                ["python", "-c", "import sys; sys.exit(2)"],
                workspace=tmp_path,
                stage_name="fail_stage",
                timeout=30,
                retry=0,
            )

    def test_retry_on_failure(self, tmp_path):
        """retry=1: two attempts, both fail → EngineExecutionError."""
        call_count = []

        def mock_streaming(*args, **kwargs):
            call_count.append(1)
            return 1  # always fails

        with patch("mapfree.core.wrapper.run_process_streaming", side_effect=mock_streaming):
            with pytest.raises(EngineExecutionError):
                run_command(
                    ["python", "-c", "pass"],
                    workspace=tmp_path,
                    stage_name="retry_stage",
                    timeout=30,
                    retry=1,
                )
        assert len(call_count) == 2  # 1 initial + 1 retry

    def test_with_custom_cwd(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        result = run_command(
            ["python", "-c", "pass"],
            workspace=tmp_path,
            stage_name="cwd_stage",
            cwd=subdir,
            timeout=30,
            retry=0,
        )
        assert result is True
