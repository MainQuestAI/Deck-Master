"""Checks for scripts/install.sh: dry-run plan and skill-link refusal."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "install.sh"
ROLES = ("deck-master", "deck-content", "deck-design", "deck-review")
SOURCE = REPO / "deck-skill"


def _run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=str(REPO),
        text=True,
        capture_output=True,
        env=merged,
        check=False,
    )


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def _assert_roles(root: Path) -> None:
    assert not (root / "deck").is_symlink()
    assert not (root / "deck").exists()
    for role in ROLES:
        directory = root / role
        assert directory.is_symlink() and directory.is_dir()
        target = Path(os.readlink(directory))
        assert target.parts[-3:] == ("current", "deck-skill", role)
        installation = directory.resolve().parent.parent
        assert installation.parent.name == "installations"
        assert (directory / "SKILL.md").is_file()
        assert not (directory / "SKILL.md").is_symlink()
        assert (directory / "SKILL.md").read_bytes() == (SOURCE / role / "SKILL.md").read_bytes()
        for name in ("references", "assets"):
            assert (directory / name).resolve() == installation / "deck-skill" / name



def _wrapper(root: Path, role: str, *, new_target: bool = False, relative: bool = False) -> Path:
    directory = root / role
    directory.mkdir(parents=True)
    targets = {
        "SKILL.md": SOURCE / role / "SKILL.md" if new_target else SOURCE / f"{role}.md",
        "references": SOURCE / "references",
        "assets": SOURCE / "assets",
    }
    for name, target in targets.items():
        directory.joinpath(name).symlink_to(os.path.relpath(target, directory) if relative else target)
    return directory


def _stub_tools(tmp_path: Path) -> Path:
    # These doubles exercise sequencing and failures, not real package provenance.
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    (bin_dir / "npm").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "cargo").write_text("""#!/bin/sh
while [ "$1" != "--root" ]; do shift; done
mkdir -p "$2/bin"
printf '%s\\n' '#!/bin/sh' 'exit 0' > "$2/bin/deck"
chmod +x "$2/bin/deck"
""")
    (bin_dir / "uv").write_text(f"""#!{sys.executable}
import pathlib, sys
if sys.argv[1:3] == ['python', 'find']:
    print({sys.executable!r})
    raise SystemExit(0)
dest = pathlib.Path(sys.argv[-1]) / 'bin'
dest.mkdir(parents=True)
(dest / 'python').write_text('#!/bin/sh\\nif [ "$DECK_TEST_FAIL" = pip ] && [ "$1" = -m ]; then exit 17; fi\\nif [ "$DECK_TEST_FAIL" = validate ] && [ "$1" = -c ]; then exit 17; fi\\nexit 0\\n')
(dest / 'python').chmod(0o755)
""")
    for name in ("npm", "cargo", "uv"):
        (bin_dir / name).chmod(0o755)
    return bin_dir


def _stub_env(tmp_path: Path) -> dict[str, str]:
    return {"PATH": f"{_stub_tools(tmp_path)}:{os.environ['PATH']}"}


def test_default_dry_run_prints_four_entry_plan_without_writing(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    root = tmp_path / "home" / ".codex" / "skills"
    result = _run(["--dry-run", "--prefix", str(prefix)])
    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert "cargo install" in output and str(REPO / "rust") in output
    assert "uv venv --python 3.12 --seed" in output or "python3.12 -m venv" in output
    assert str(prefix / "share/deck/installations") in output and "/share/deck/venv" in output
    assert "run build" in output
    assert f"deck-bin={prefix / 'bin/deck'}" in output
    assert f"skills-root={root}" in output
    assert "skill-entry=deck action=absent" in output
    for role in ROLES:
        assert f"skill-entry={role} action=create" in output
        assert f"ln -s {prefix / 'share/deck/current/deck-skill' / role} {root / role}" in output
    assert not prefix.exists() and not root.exists()


def test_script_is_executable() -> None:
    assert SCRIPT.stat().st_mode & stat.S_IXUSR


def test_removed_skill_dir_fails_without_writing(tmp_path: Path) -> None:
    result = _run(["--skill-dir", str(tmp_path / "deck")])
    assert result.returncode == 2
    assert "--skill-dir" in result.stderr and "已取消" in result.stderr
    assert not (tmp_path / "deck").exists()


@pytest.mark.parametrize("custom_root", [False, True])
def test_install_and_repeat_keep_whole_directory_links(tmp_path: Path, custom_root: bool) -> None:
    root = tmp_path / "roles" if custom_root else tmp_path / "home/.codex/skills"
    args = ["--prefix", str(tmp_path / "prefix")]
    if custom_root:
        args += ["--skills-root", str(root) + "///"]
    env = _stub_env(tmp_path)
    first = _run(args, env=env)
    assert first.returncode == 0, first.stderr
    _assert_roles(root)
    before = {role: (root / role).lstat().st_ino for role in ROLES}
    plan = _run([*args, "--dry-run"], env=env)
    assert plan.returncode == 0, plan.stderr
    for role in ROLES:
        assert f"skill-entry={role} action=keep" in plan.stdout
    assert "ln -s" not in plan.stdout
    second = _run(args, env=env)
    assert second.returncode == 0, second.stderr
    assert before == {role: (root / role).lstat().st_ino for role in ROLES}
    _assert_roles(root)


def test_source_managed_deck_removed_on_reinstall(tmp_path: Path) -> None:
    root = tmp_path / "home/.codex/skills"
    env = _stub_env(tmp_path)
    args = ["--prefix", str(tmp_path / "prefix")]
    assert _run(args, env=env).returncode == 0
    (root / "deck").symlink_to(os.path.relpath(SOURCE, root))
    plan = _run([*args, "--dry-run"], env=env)
    assert plan.returncode == 0, plan.stderr
    assert "skill-entry=deck action=remove" in plan.stdout
    assert f"rm -- {root / 'deck'}" in plan.stdout
    assert (root / "deck").is_symlink()
    result = _run(args, env=env)
    assert result.returncode == 0, result.stderr
    assert SOURCE.is_dir()
    _assert_roles(root)


@pytest.mark.parametrize("new_target", [False, True])
@pytest.mark.parametrize("relative", [False, True])
def test_old_wrappers_upgrade(tmp_path: Path, new_target: bool, relative: bool) -> None:
    root = tmp_path / "roles"
    for role in ROLES:
        _wrapper(root, role, new_target=new_target, relative=relative)
    (root / "deck").symlink_to(SOURCE)
    args = ["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)]
    env = _stub_env(tmp_path)
    plan = _run([*args, "--dry-run"], env=env)
    assert plan.returncode == 0, plan.stderr
    assert "action=upgrade" in plan.stdout
    assert not (root / "deck-content").is_symlink()
    result = _run(args, env=env)
    assert result.returncode == 0, result.stderr
    _assert_roles(root)


@pytest.mark.parametrize("occupancy", ["file", "directory", "symlink", "dangling", "extra", "hidden", "partial"])
def test_conflict_leaves_all_paths_untouched(tmp_path: Path, occupancy: str) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    deck = root / "deck"
    deck.symlink_to(SOURCE)
    wrapper = _wrapper(root, "deck-master")
    occupied = root / "deck-review"
    foreign = tmp_path / "old-python-line"
    if occupancy == "file":
        occupied.write_text("author file")
    elif occupancy == "directory":
        occupied.mkdir()
    elif occupancy in ("symlink", "dangling"):
        if occupancy == "symlink":
            foreign.mkdir()
        occupied.symlink_to(foreign)
    else:
        _wrapper(root, "deck-review")
        if occupancy == "partial":
            (occupied / "assets").unlink()
            (occupied / "assets").symlink_to(foreign)
        else:
            (occupied / (".notes" if occupancy == "hidden" else "NOTES")).write_text("author note")
    before = {str(p): (os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
              for p in root.rglob("*")}
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)], env=_stub_env(tmp_path))
    assert result.returncode == 2
    assert str(occupied) in result.stderr
    if occupancy in ("symlink", "dangling", "partial"):
        assert str(foreign) in result.stderr
    assert deck.is_symlink() and not wrapper.is_symlink()
    after = {str(p): (os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
             for p in root.rglob("*")}
    assert before == after
    assert not (tmp_path / "prefix").exists()


@pytest.mark.parametrize("occupancy", ["file", "directory", "symlink", "dangling"])
def test_unmanaged_deck_warns_and_preserves_entry(tmp_path: Path, occupancy: str) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    deck = root / "deck"
    foreign = tmp_path / "foreign"
    if occupancy == "file":
        deck.write_text("other skill")
    elif occupancy == "directory":
        deck.mkdir()
        (deck / "NOTES").write_text("author note")
    else:
        if occupancy == "symlink":
            foreign.mkdir()
        deck.symlink_to(foreign)
    before = deck.lstat().st_ino
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)], env=_stub_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert str(deck) in result.stderr and "抢触发" in result.stderr
    assert deck.lstat().st_ino == before
    for role in ROLES:
        assert (root / role).is_symlink()


def test_relative_source_links_migrate_to_the_installed_component_group(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    for role in ROLES:
        (root / role).symlink_to(os.path.relpath(SOURCE / role, root))
    result = _run(["--dry-run", "--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)])
    assert result.returncode == 0, result.stderr
    for role in ROLES:
        assert f"skill-entry={role} action=replace" in result.stdout
    assert "ln -s" in result.stdout


@pytest.mark.parametrize("stage", ["npm", "cargo", "venv", "pip", "validate"])
def test_preparation_failure_keeps_current_and_all_entries(tmp_path: Path, stage: str) -> None:
    prefix = tmp_path / "prefix"
    root = tmp_path / "roles"
    env = _stub_env(tmp_path)
    args = ["--prefix", str(prefix), "--skills-root", str(root)]
    assert _run(args, env=env).returncode == 0
    current = prefix / "share/deck/current"
    target = current.readlink()
    entry = (prefix / "bin/deck").read_bytes()
    links = {role: (root / role).readlink() for role in ROLES}
    bin_dir = tmp_path / "stub-bin"
    if stage in ("npm", "cargo"):
        (bin_dir / stage).write_text("#!/bin/sh\nexit 17\n")
    elif stage == "venv":
        path = bin_dir / "uv"
        path.write_text(path.read_text().replace("dest = pathlib.Path", "raise SystemExit(17)\ndest = pathlib.Path"))
    else:
        env["DECK_TEST_FAIL"] = stage
    result = _run(args, env=env)
    assert result.returncode != 0
    assert ("validate" if stage == "validate" else "prepare") in result.stderr
    assert current.readlink() == target
    assert (prefix / "bin/deck").read_bytes() == entry
    assert {role: (root / role).readlink() for role in ROLES} == links


def test_unknown_binary_is_not_executed_or_replaced(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    entry = prefix / "bin/deck"
    entry.parent.mkdir(parents=True)
    marker = tmp_path / "executed"
    source = f"#!/bin/sh\ntouch '{marker}'\n"
    entry.write_text(source)
    entry.chmod(0o755)
    result = _run(["--prefix", str(prefix), "--skills-root", str(tmp_path / "roles")], env=_stub_env(tmp_path))
    assert result.returncode == 2
    assert entry.read_text() == source
    assert not marker.exists()


def _owned_legacy_source(tmp_path: Path, prefix: Path) -> Path:
    import json
    import shutil
    source = tmp_path / "legacy-source"
    (source / "rust/target/release").mkdir(parents=True)
    (source / "rust/Cargo.toml").write_text('[package]\nname="deck"\n')
    (source / "rust/target/release/deck").write_bytes((prefix / "bin/deck").read_bytes())
    (source / "deck-tools").mkdir()
    (source / "deck-tools/pyproject.toml").write_text('[project]\nname="deck-tools"\n')
    shutil.copytree(SOURCE, source / "deck-skill", symlinks=True)
    (prefix / ".crates2.json").write_text(json.dumps({"installs": {f"deck 1.1.2 (path+file://{source / 'rust'})": {"bins": ["deck"]}}}))
    return source


def test_cargo_owned_binary_and_source_links_migrate_without_touching_old_venv(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    entry = prefix / "bin/deck"
    entry.parent.mkdir(parents=True)
    entry.write_text("owned old binary")
    legacy = _owned_legacy_source(tmp_path, prefix)
    old_venv = prefix / "share/deck/venv"
    old_venv.mkdir(parents=True)
    (old_venv / "author-path").write_text("keep old environment")
    roles = tmp_path / "roles"
    roles.mkdir()
    for role in ROLES:
        (roles / role).symlink_to(legacy / "deck-skill" / role)
    env = _stub_env(tmp_path)
    args = ["--prefix", str(prefix), "--skills-root", str(roles)]
    result = _run(args, env=env)
    assert result.returncode == 0, result.stderr
    assert (old_venv / "author-path").read_text() == "keep old environment"
    assert entry.read_text().startswith("#!/usr/bin/env bash")
    _assert_roles(roles)
    assert _run(args, env=env).returncode == 0


def test_interrupted_first_migration_reports_stage_and_can_retry(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    entry = prefix / "bin/deck"
    entry.parent.mkdir(parents=True)
    entry.write_text("owned old binary")
    _owned_legacy_source(tmp_path, prefix)
    root = tmp_path / "roles"
    root.mkdir()
    for role in ROLES:
        (root / role).symlink_to(SOURCE / role)
    env = _stub_env(tmp_path)
    args = ["--prefix", str(prefix), "--skills-root", str(root)]
    cargo = tmp_path / "stub-bin/cargo"
    original_cargo = cargo.read_text()
    cargo.write_text(original_cargo + f'\nchmod 555 "{entry.parent}"\n')
    try:
        failed = _run(args, env=env)
    finally:
        entry.parent.chmod(0o755)
        cargo.write_text(original_cargo)
    assert failed.returncode != 0
    assert "install-entries" in failed.stderr
    assert entry.read_text() == "owned old binary"
    assert (prefix / "share/deck/current").is_symlink()
    assert _run(args, env=env).returncode == 0
    _assert_roles(root)



def test_stale_cargo_record_does_not_authorize_replacing_foreign_binary(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    entry = prefix / "bin/deck"
    entry.parent.mkdir(parents=True)
    entry.write_text("managed old binary")
    _owned_legacy_source(tmp_path, prefix)
    entry.write_text("foreign replacement")
    result = _run(["--prefix", str(prefix), "--skills-root", str(tmp_path / "roles")], env=_stub_env(tmp_path))
    assert result.returncode == 2
    assert entry.read_text() == "foreign replacement"


def _interrupt_entry(tmp_path: Path, root: Path, point: str) -> Path:
    tool = "ln" if point == "role-link" else "rm" if point == "wrapper-links" else "rmdir"
    real = shutil.which(tool)
    assert real is not None
    target = root / ("deck-content" if point == "role-link" else "deck-master")
    failure = tmp_path / "stub-bin" / tool
    if point == "wrapper-links":
        operation = f'"{real}" -- "{target}/SKILL.md"\nexit 17'
        match = target / "SKILL.md"
    else:
        operation = "exit 17"
        match = target
    failure.write_text(f'''#!/bin/sh
for arg do
  if [ "$arg" = "{match}" ]; then
    {operation}
  fi
done
exec "{real}" "$@"
''')
    failure.chmod(0o755)
    return failure


@pytest.mark.parametrize("point", ["role-link", "wrapper-links", "wrapper-directory"])
def test_entry_migration_retry_after_destructive_step(tmp_path: Path, point: str) -> None:
    prefix = tmp_path / "prefix"
    entry = prefix / "bin/deck"
    entry.parent.mkdir(parents=True)
    entry.write_text("owned old binary")
    legacy = _owned_legacy_source(tmp_path, prefix)
    old_venv = prefix / "share/deck/venv"
    old_venv.mkdir(parents=True)
    (old_venv / "author-path").write_text("keep old environment")
    root = tmp_path / "roles"
    root.mkdir()
    if point == "role-link":
        for role in ROLES:
            (root / role).symlink_to(legacy / "deck-skill" / role)
    else:
        for role in ROLES:
            _wrapper(root, role)
    env = _stub_env(tmp_path)
    args = ["--prefix", str(prefix), "--skills-root", str(root)]
    failure = _interrupt_entry(tmp_path, root, point)
    interrupted = _run(args, env=env)
    assert interrupted.returncode == 17, interrupted.stderr
    assert entry.read_text().startswith("#!/usr/bin/env bash")
    if point == "role-link":
        assert (root / "deck-master").readlink() == prefix / "share/deck/current/deck-skill/deck-master"
        assert not (root / "deck-content").exists()
    else:
        wrapper = root / "deck-master"
        assert wrapper.is_dir() and not wrapper.is_symlink()
        assert {path.name for path in wrapper.iterdir()} == (
            {"references", "assets"} if point == "wrapper-links" else set()
        )
    failure.unlink()
    retry = _run(args, env=env)
    assert retry.returncode == 0, retry.stderr
    _assert_roles(root)
    assert (old_venv / "author-path").read_text() == "keep old environment"
    assert (legacy / "rust/target/release/deck").read_text() == "owned old binary"
    assert "install-entries" in interrupted.stderr
    assert not list((prefix / "share/deck/entry-migrations").glob("*.json"))


@pytest.mark.parametrize("mutation", ["extra", "hidden", "retarget", "file", "directory"])
def test_migration_receipt_does_not_authorize_changed_wrapper(tmp_path: Path, mutation: str) -> None:
    root = tmp_path / "roles"
    for role in ROLES:
        _wrapper(root, role)
    prefix = tmp_path / "prefix"
    env = _stub_env(tmp_path)
    args = ["--prefix", str(prefix), "--skills-root", str(root)]
    failure = _interrupt_entry(tmp_path, root, "wrapper-links")
    assert _run(args, env=env).returncode == 17
    failure.unlink()
    wrapper = root / "deck-master"
    if mutation in ("extra", "hidden"):
        (wrapper / (".notes" if mutation == "hidden" else "NOTES")).write_text("author note")
    elif mutation == "retarget":
        (wrapper / "assets").unlink()
        (wrapper / "assets").symlink_to(tmp_path / "foreign")
    elif mutation == "file":
        (wrapper / "assets").unlink()
        (wrapper / "assets").write_text("author asset")
    else:
        wrapper.rename(root / "preserved-wrapper")
        wrapper.mkdir()
    before = {str(p): os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None
              for p in root.rglob("*")}
    current = (prefix / "share/deck/current").readlink()
    retry = _run(args, env=env)
    assert retry.returncode == 2, retry.stderr
    assert str(wrapper) in retry.stderr
    assert not wrapper.is_symlink()
    assert before == {str(p): os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None
                      for p in root.rglob("*")}
    assert (prefix / "share/deck/current").readlink() == current


def test_migration_receipt_does_not_authorize_retargeted_cross_checkout_link(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    entry = prefix / "bin/deck"
    entry.parent.mkdir(parents=True)
    entry.write_text("owned old binary")
    legacy = _owned_legacy_source(tmp_path, prefix)
    root = tmp_path / "roles"
    root.mkdir()
    for role in ROLES:
        (root / role).symlink_to(legacy / "deck-skill" / role)
    env = _stub_env(tmp_path)
    args = ["--prefix", str(prefix), "--skills-root", str(root)]
    failure = _interrupt_entry(tmp_path, root, "role-link")
    assert _run(args, env=env).returncode == 17
    failure.unlink()
    changed = root / "deck-design"
    changed.unlink()
    changed.symlink_to(tmp_path / "foreign")
    retry = _run(args, env=env)
    assert retry.returncode == 2, retry.stderr
    assert changed.readlink() == tmp_path / "foreign"
    assert not (root / "deck-content").is_symlink()
