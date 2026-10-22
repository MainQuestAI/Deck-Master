"""Ordinary CI entry for S09's finite, isolated substantive case suite.

The carrier is deliberately outside pytest's automatic filename patterns. This
wrapper executes all 70 cases in one real -I -B interpreter and checks every
JUnit outcome; no production flag guard or substantive case is patched.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = Path(__file__).with_name("rc3_q2_later_300_cases.py").resolve()
TOOL = ROOT / "tools/rc3_campaign/q2_later_300.py"
EXPECTED_CASES = 70


def run_logged(tmp_path, argv):
    """One actual invocation, exclusive logs, no retry or result replacement."""
    env = dict(os.environ)
    # The child must run the entire explicit carrier, independently of a
    # caller's environment filters. Repository conftest/normal plugins remain.
    env["PYTEST_ADDOPTS"] = ""
    started = datetime.now(timezone.utc).isoformat()
    result = None
    stdout, stderr = b"", b""
    execution_error = None
    try:
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, timeout=180)
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        execution_error = {"type": type(exc).__name__, "message": str(exc)}
        raise
    except OSError as exc:
        execution_error = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        (tmp_path / "stdout.txt").open("xb").write(stdout)
        (tmp_path / "stderr.txt").open("xb").write(stderr)
        (tmp_path / "invocation.json").open("x").write(json.dumps({
            "argv": argv, "cwd": str(ROOT), "start_UTC": started,
            "end_UTC": datetime.now(timezone.utc).isoformat(),
            "exit": result.returncode if result is not None else None,
            "execution_error": execution_error,
            "environment_overrides": {"PYTEST_ADDOPTS": ""},
            "parent_flags": {"isolated": sys.flags.isolated, "dont_write_bytecode": sys.flags.dont_write_bytecode},
        }, indent=2) + "\n")
    return result


def test_all_q2_later_300_cases_run_in_an_actual_isolated_interpreter(tmp_path):
    junit = tmp_path / "isolated-cases.xml"
    case_root = tmp_path / "isolated-cases"
    # Keep the active node in captured output if the unchanged deadline fires;
    # durations diagnose completed slow cases without weakening any case checks.
    argv = [sys.executable, "-I", "-B", "-m", "pytest", "-vv", "--durations=20", "-p", "no:cacheprovider",
            "-o", "addopts=", "--basetemp=" + str(case_root), "--junitxml=" + str(junit), str(CASES)]
    result = run_logged(tmp_path, argv)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    outcomes = list(ET.parse(junit).getroot().iter("testcase"))
    identities = {(case.get("classname"), case.get("name")) for case in outcomes}
    assert len(outcomes) == len(identities) == EXPECTED_CASES
    assert all(case.find(tag) is None for case in outcomes for tag in ("failure", "error", "skipped"))
    observed = [json.loads(path.read_bytes()) for path in case_root.rglob("identity.json")]
    assert observed and all(value["isolated"] == value["dont_write_bytecode"] == 1 for value in observed)
    (tmp_path / "execution-summary.json").open("x").write(json.dumps({
        "case_carrier": str(CASES), "expected": EXPECTED_CASES, "executed": len(outcomes),
        "passed": len(outcomes), "failed": 0, "errors": 0, "skipped": 0,
        "actual_runtime_identity_observations": len(observed),
        "case_outcomes": [{"classname": case.get("classname"), "name": case.get("name")} for case in outcomes],
    }, indent=2) + "\n")


@pytest.mark.parametrize("flags", [("-B",), ("-I",)])
def test_real_CLI_requires_both_flags_before_opening_control_or_ledger(tmp_path, flags):
    result = run_logged(tmp_path, [sys.executable, *flags, "-X", "pycache_prefix="+str(tmp_path/"pycache"),
        str(TOOL), "initialize", "--engineering", "--flow", "r04", "--control", str(tmp_path/"absent.json"),
        "--control-sha256", "0"*64])
    assert result.returncode == 2
    assert json.loads(result.stderr)["error"] == "use own absolute Python -I -B"
    assert not (tmp_path/"absent.json").exists()


@pytest.mark.parametrize("option", ["--operation", "--adapter-context", "--scope", "--pool"])
def test_real_CLI_has_no_operation_context_scope_or_pool_override(tmp_path, option):
    result = run_logged(tmp_path, [sys.executable, "-I", "-B", str(TOOL), "initialize", "--engineering",
        "--flow", "r04", "--control", str(tmp_path/"absent.json"), "--control-sha256", "0"*64, option, "unauthorized"])
    assert result.returncode == 2 and b"unrecognized arguments" in result.stderr


def test_companion_and_pinned_helpers_import_without_Runtime(tmp_path):
    code = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('s09',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.helpers(); "
            "assert not any(n=='deck_master' or n.startswith('deck_master.') for n in sys.modules)")
    result = run_logged(tmp_path, [sys.executable, "-I", "-B", "-c", code, str(TOOL)])
    assert result.returncode == 0, result.stderr.decode()
