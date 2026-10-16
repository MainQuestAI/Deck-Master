"""Ordinary CI really executes S12's own-wheel isolated engineering chain."""
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from rc3_s12_evidence import logged_command, publish_workspace, save

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/rc3_campaign/m02_image_transition.py"
PROBE = Path(__file__).with_name("rc3_m02_image_installed_probe.py")
SCENARIOS = {"positive", "unknown", "bad-callback", "grant-lost-ack", "grant-durable", "role-overrun"}


def output_root(tmp_path, label):
    configured = os.environ.get("RC3_S12_EVIDENCE_ROOT")
    path = (Path(configured) if configured else tmp_path / "evidence") / (label + "-" + uuid.uuid4().hex)
    path.mkdir(parents=True, exist_ok=False)
    return path


def checked(root, name, argv, *, env=None):
    result = logged_command(root, name, argv, cwd=ROOT, env=env)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    return result


def test_real_own_wheel_six_scenarios_run_in_isolated_interpreter(tmp_path):
    """One serial Runtime child, all six scenarios and substantive checks.

    No Source Runtime borrow, skipped case, resampling or production guard
    patch. Successful ordinary working fixtures are temporary; full command,
    SDK/identity/error/public-workspace evidence is retained separately.
    """
    out = output_root(tmp_path, "own-wheel")
    wheels = tmp_path / "wheels"; wheels.mkdir()
    prefix = tmp_path / "own-prefix"
    working = tmp_path / "neutral-projects"
    env = dict(os.environ)
    env["PYTEST_ADDOPTS"] = ""
    save(out / "parent-identity.json", {"python": sys.executable, "parent_isolated": sys.flags.isolated,
        "parent_dont_write_bytecode": sys.dont_write_bytecode, "github_sha": os.environ.get("GITHUB_SHA"),
        "environment_overrides": {"PYTEST_ADDOPTS": ""}, "temporary_successful_working_fixtures": str(working)})
    try:
        checked(out, "wheel", [sys.executable, "-B", "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
            "--no-cache-dir", "--wheel-dir", str(wheels), str(ROOT)], env=env)
        candidates = list(wheels.glob("deck_master-*.whl"))
        assert len(candidates) == 1
        wheel = candidates[0]
        shutil.copyfile(wheel, out / wheel.name)
        checked(out, "venv", [sys.executable, "-I", "-B", "-m", "venv", "--system-site-packages", str(prefix)], env=env)
        python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        checked(out, "install", [str(python), "-I", "-B", "-m", "pip", "install", "--ignore-installed", "--no-deps",
            "--no-compile", "--disable-pip-version-check", str(wheel)], env=env)
        checked(out, "actual-own-wheel-probe", [str(python), "-I", "-B", str(PROBE), "--wheel", str(wheel),
            "--working", str(working), "--evidence", str(out / "probe")], env=env)
        result = json.loads((out / "probe/result.json").read_bytes())
        assert result["status"] == "ENGINEERING_ONLY"
        observed = result["scenarios"]
        assert len(observed) == len(SCENARIOS) and {r["scenario"] for r in observed} == SCENARIOS
        assert all(r["status"] == "executed" and r["function_observations"] > 0 for r in observed)
        assert result["checks"] and all(r["pass"] is True for r in result["checks"])
        assert result["new_S11_full_export_or_formal_M02"] is False and result["managed_candidate"] is False
        save(out / "execution-summary.json", {"actual_scenarios": len(observed), "actual_checks": len(result["checks"]),
            "function_observations": result["function_observations"], "skipped": 0, "resampled": 0,
            "actual_child_flags": ["-I", "-B"], "complete_result": str(out / "probe/result.json")})
    finally:
        # This also preserves partial projects if the child was killed before
        # its finally. The original IG key root is pruned before enumeration.
        manifest = publish_workspace(working, out / "probe/neutral-workspaces")
        save(out / "workspace-manifest-from-parent.json", manifest)


@pytest.mark.parametrize("flags", [("-B",), ("-I",)])
def test_real_cli_requires_both_flags_before_opening_any_epoch(tmp_path, flags):
    out = output_root(tmp_path, "flags")
    result = logged_command(out, "actual-cli", [sys.executable, *flags, "-X", "pycache_prefix=" + str(tmp_path / "pycache"),
        str(TOOL), "initialize", "--root", str(tmp_path / "absent"), "--registration", str(tmp_path / "absent.json")], cwd=ROOT)
    assert result.returncode == 2
    assert json.loads(result.stderr)["error"] == "use own absolute Python -I -B"
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("option", ["--operation", "--adapter-context", "--scope", "--provider", "--key", "--receipt", "--epoch", "--store"])
def test_cli_cannot_choose_operation_trust_scope_key_or_receipt(tmp_path, option):
    out = output_root(tmp_path, "unsupported-option")
    result = logged_command(out, "actual-cli", [sys.executable, "-I", "-B", str(TOOL), "status",
        "--root", str(tmp_path / "absent"), option, "caller-controlled"], cwd=ROOT)
    assert result.returncode == 2 and b"unrecognized arguments" in result.stderr
    assert not (tmp_path / "absent").exists()


def test_companion_import_reads_no_Runtime(tmp_path):
    out = output_root(tmp_path, "import")
    code = ("import importlib.util,sys; s=importlib.util.spec_from_file_location('s12',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
            "assert not any(n=='deck_master' or n.startswith('deck_master.') for n in sys.modules)")
    checked(out, "actual-import", [sys.executable, "-I", "-B", "-c", code, str(TOOL)])

