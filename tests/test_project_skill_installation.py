"""Project skill discovery and ownership using real links and release files."""
from pathlib import Path
import os
import shlex
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deck_master
from skills import installer


@pytest.fixture
def central(tmp_path, monkeypatch):
    root = tmp_path / "central"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(installer, "INSTALL_LOG_DIR", root)
    monkeypatch.setattr(installer, "INSTALLED_SKILL_DIR", root / "current/skills/deck-master")
    monkeypatch.setattr(installer, "DEFAULT_AGENT_SKILL_DIRS", {"codex": str(tmp_path / "global/skills")})
    installer.build_release_tree(root / "current")
    return root


def invoke(*argv):
    args = deck_master.build_parser().parse_args(list(argv))
    return args.func(args)


def test_project_install_discovery_isolation_and_uninstall(central, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    result = invoke("suite-install", "--target", "codex", "--scope", "project", "--project-root", str(project), "--links-only", "--include-optional")
    assert result["status"] == "installed"
    assert not result["release_install"]["activated"]
    directory = project / ".agents/skills"
    assert len(list(directory.iterdir())) == 18
    assert not (directory / "ppt-master").exists()
    assert not (tmp_path / "global").exists()
    nested = project / "slides"
    nested.mkdir()
    monkeypatch.chdir(nested)
    # Runtime consumers use the same resolver, even without explicit CLI flags.
    status = installer.inspect_suite_status(targets=["codex"])
    assert status["full_suite_ready"]
    assert status["installations"]["codex"]["scope"] == "project"
    compat = next(s for s in status["skills"] if s["skill"] == "ppt-master")
    assert compat["source_type"] == "bundled_compatibility"
    assert compat["public_entry"] == "deck-builder"
    log = central / installer.INSTALL_LOG_NAME
    original_log = log.read_bytes()
    assert invoke("validate-skill", "--target", "codex")["valid"]
    assert log.read_bytes() == original_log
    monkeypatch.chdir(tmp_path)
    assert not invoke("validate-skill", "--target", "codex")["valid"]
    assert invoke("suite-status", "--target", "codex", "--project-root", str(project))["full_suite_ready"]
    # Foreign content and unrelated skills must survive suite removal.
    external = directory / "ppt-master"
    external.mkdir()
    marker = external / "SKILL.md"
    marker.write_text("independent production package")
    other = directory / "other"
    other.mkdir()
    result = invoke("uninstall-skill", "--target", "codex", "--suite", "--scope", "project", "--project-root", str(project))
    assert result["status"] == "uninstalled"
    assert marker.read_text() == "independent production package"
    assert set(p.name for p in directory.iterdir()) == {"ppt-master", "other"}
    assert (central / "current/skills/deck-master/SKILL.md").exists()


def test_project_links_survive_central_activation_and_rollback(central, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    invoke("suite-install", "--project-root", str(project), "--links-only")
    entry = project / ".agents/skills/deck-master"
    original = (entry / "SKILL.md").read_bytes()
    # Managed releases require 3.12 even when preview tests run on 3.11.
    # Use an actual supported runtime and record its observed version.
    runtime_python = sys.executable
    runtime_version = installer._probe_python_version(runtime_python)
    if not installer._is_python_312(runtime_version):
        runtime_python, runtime_version = installer._resolve_runtime_python()
        # Preserve a configured venv entrypoint; resolving its symlink loses
        # its dependencies when this test runs under a 3.11 interpreter.
        runtime_python = os.environ.get("DECK_MASTER_PYTHON") or runtime_python
    release = central / "current"
    python = release / installer.RELEASE_PYTHON_RELATIVE
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text(f'#!/bin/sh\nexec {shlex.quote(runtime_python)} "$@"\n')
    python.chmod(0o755)
    installer._record_release_runtime(release, runtime_version)
    stage = central / "staging/new"
    installer.build_release_tree(stage)
    python = stage / installer.RELEASE_PYTHON_RELATIVE
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text(f'#!/bin/sh\nexec {shlex.quote(runtime_python)} "$@"\n')
    python.chmod(0o755)
    # An auxiliary marker demonstrates that every link follows activation.
    (stage / "upgrade-marker").write_text("new")
    installer._record_release_runtime(stage, runtime_version)
    verification = installer.verify_release_tree(stage, run_smoke=False)
    assert verification["valid"], verification
    installer._activate_staged_release(stage)
    assert entry.resolve() == central / "current/skills/deck-master"
    assert (entry.parents[0] / "deck-builder/SKILL.md").exists()
    assert (central / "current/upgrade-marker").exists()
    result = installer.rollback_release_tree()
    assert result["status"] == "rolled_back"
    assert (entry / "SKILL.md").read_bytes() == original
    assert not (central / "current/upgrade-marker").exists()


def test_explicit_global_scope_and_foreign_link_preservation(central, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    invoke("suite-install", "--project-root", str(project), "--links-only")
    monkeypatch.chdir(project)
    result = invoke("suite-install", "--scope", "global", "--links-only")
    assert result["status"] == "installed"
    assert invoke("validate-skill", "--target", "codex", "--scope", "global")["scope"] == "global"
    link = project / ".agents/skills/deck-brief"
    link.unlink()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    link.symlink_to(foreign)
    result = invoke("uninstall-skill", "--target", "codex", "--suite")
    assert result["status"] == "blocked"
    assert link.resolve() == foreign
    assert (tmp_path / "global/skills/deck-master").is_symlink()


def test_scope_validation_before_install(central, tmp_path):
    with pytest.raises(installer.SkillInstallError, match="requires target codex"):
        invoke("suite-install", "--scope", "project", "--target", "claude-code", "--links-only")
    with pytest.raises(installer.SkillInstallError, match="not both"):
        invoke("suite-install", "--scope", "project", "--agent-skill-dir", str(tmp_path), "--links-only")
