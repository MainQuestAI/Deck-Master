"""Ordinary CI entry for S08's finite, isolated substantive case suite.

The carrier is deliberately outside pytest's automatic filename patterns. This
wrapper executes all 53 cases in one real -I -B interpreter and checks every
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
CASES = Path(__file__).with_name("rc3_supplied_p5_fidelity_cases.py").resolve()
TOOL = ROOT / "tools/rc3_campaign/supplied_p5_fidelity.py"
EXPECTED_CASES = 53


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
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, timeout=120)
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


def test_all_supplied_p5_fidelity_cases_run_in_an_actual_isolated_interpreter(tmp_path):
    junit = tmp_path / "isolated-cases.xml"
    case_root = tmp_path / "isolated-cases"
    argv = [sys.executable, "-I", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
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


@pytest.mark.parametrize("flags", [("-B",), ("-I",)], ids=["without-isolation", "without-bytecode-guard"])
def test_real_cli_refuses_missing_required_python_flags(tmp_path, flags):
    argv = [sys.executable, *flags, "-X", "pycache_prefix=" + str(tmp_path/"pycache"), str(TOOL), "prepare",
            "--engineering-only", "--run", str(tmp_path/"absent-run"),
            "--admission", str(tmp_path/"absent-admission.json"), "--admission-sha256", "0"*64]
    result = run_logged(tmp_path, argv)
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status":"refused_or_unknown", "error_type":"Error",
        "error":"use own absolute Python -I -B", "automatic_retry":False}
    assert not (tmp_path/"absent-run").exists()


@pytest.mark.parametrize("option", ["--scope", "--operation", "--adapter-context", "--review-receipt-selector"])
def test_real_cli_has_no_arbitrary_override_parameter(tmp_path, option):
    result = run_logged(tmp_path, [sys.executable,"-I","-B",str(TOOL),"prepare","--engineering-only",
        "--run",str(tmp_path/"absent-run"),"--admission",str(tmp_path/"absent.json"),
        "--admission-sha256","0"*64,option,"unauthorized"])
    assert result.returncode == 2 and b"unrecognized arguments" in result.stderr
    assert not (tmp_path/"absent-run").exists()


def test_standalone_companion_and_pinned_helpers_import_no_DeckMaster_Runtime(tmp_path):
    code = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('s08',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.helpers(); "
            "assert not any(n=='deck_master' or n.startswith('deck_master.') for n in sys.modules)")
    result = run_logged(tmp_path,[sys.executable,"-I","-B","-c",code,str(TOOL)])
    assert result.returncode == 0, result.stderr.decode()
