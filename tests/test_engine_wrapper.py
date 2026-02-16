"""
Quick test: subprocess wrapper (run_command, EngineExecutionError).
Run: python3 tests/test_engine_wrapper.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapfree.core.wrapper import run_command, EngineExecutionError

PASS = 0
FAIL = 0


def report(name, ok, detail=""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print(" Engine Wrapper — run_command / EngineExecutionError")
print("=" * 60)

with tempfile.TemporaryDirectory() as tmp:
    workspace = Path(tmp)

    # 1. Success: trivial command
    try:
        ok = run_command(
            ["true"],
            workspace=workspace,
            stage_name="test_ok",
            timeout=10,
            retry=0,
            cwd=workspace,
        )
        report("run_command(true) returns True", ok is True)
    except Exception as e:
        report("run_command(true) no exception", False, str(e))

    # 2. Log file created
    log_file = workspace / "logs" / "test_ok.log"
    report("log file created", log_file.exists())
    if log_file.exists():
        content = log_file.read_text()
        report("log contains attempt line", "Attempt" in content or "---" in content)

    # 3. Failure: non-zero exit raises after retries
    try:
        run_command(
            ["false"],
            workspace=workspace,
            stage_name="test_fail",
            timeout=10,
            retry=1,
            cwd=workspace,
        )
        report("run_command(false) raises EngineExecutionError", False, "no exception")
    except EngineExecutionError as e:
        report("run_command(false) raises EngineExecutionError", True)
        report("error message mentions stage", "test_fail" in str(e) or "failed" in str(e).lower())
    except Exception as e:
        report("run_command(false) raises EngineExecutionError", False, type(e).__name__)

print("=" * 60)
print(f" TOTAL: {PASS} PASS, {FAIL} FAIL")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
