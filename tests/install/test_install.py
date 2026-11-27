"""Checks for scripts/install.sh: dry-run, single-pointer upgrade, conflict refusal, and post-install doctor."""

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


def _stub_tools(tmp_path: Path) -> Path:
    # These doubles exercise sequencing and failures, not real package provenance.
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    (bin_dir / "npm").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "cargo").write_text("""#!/bin/sh
while [ "$1" != "--root" ]; do shift; done
mkdir -p "$2/bin"
cat <<'DECK' > "$2/bin/deck"
#!/bin/sh
if [ "$1" = doctor ]; then
  if [ "$DECK_TEST_DOCTOR_FAIL" = 1 ]; then
    echo '{"status":"needs_tool","checks":[{"name":"soffice","available":false}]}'
    exit 3
  fi
  echo '{"status":"ready","checks":[{"name":"python","available":true}]}'
  exit 0
fi
exit 0
DECK
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
    assert f"dry-run: {prefix / 'bin/deck'} doctor" in output
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
def test_install_and_repeat_upgrade_switch_current_and_run_doctor(tmp_path: Path, custom_root: bool) -> None:
    root = tmp_path / "roles" if custom_root else tmp_path / "home/.codex/skills"
    prefix = tmp_path / "prefix"
    args = ["--prefix", str(prefix)]
    if custom_root:
        args += ["--skills-root", str(root) + "///"]
    env = _stub_env(tmp_path)
    first = _run(args, env=env)
    assert first.returncode == 0, first.stderr
    assert '"status":"ready"' in first.stdout
    _assert_roles(root)
    first_target = (prefix / "share/deck/current").readlink()
    before = {role: (root / role).lstat().st_ino for role in ROLES}
    plan = _run([*args, "--dry-run"], env=env)
    assert plan.returncode == 0, plan.stderr
    for role in ROLES:
        assert f"skill-entry={role} action=keep" in plan.stdout
    assert "ln -s" not in plan.stdout
    second = _run(args, env=env)
    assert second.returncode == 0, second.stderr
    assert (prefix / "share/deck/current").readlink() != first_target
    assert before == {role: (root / role).lstat().st_ino for role in ROLES}
    _assert_roles(root)


def test_post_install_doctor_missing_tool_warns_without_failing(tmp_path: Path) -> None:
    env = _stub_env(tmp_path)
    env["DECK_TEST_DOCTOR_FAIL"] = "1"
    root = tmp_path / "roles"
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)], env=env)
    assert result.returncode == 0, result.stderr
    assert '"status":"needs_tool"' in result.stdout
    assert "警告" in result.stderr and "deck doctor" in result.stderr
    _assert_roles(root)


@pytest.mark.parametrize("occupancy", ["file", "directory", "symlink", "dangling"])
def test_conflict_leaves_all_paths_untouched(tmp_path: Path, occupancy: str) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    occupied = root / "deck-review"
    foreign = tmp_path / "foreign-skill"
    if occupancy == "file":
        occupied.write_text("author file")
    elif occupancy == "directory":
        occupied.mkdir()
        (occupied / "NOTES").write_text("author note")
    else:
        if occupancy == "symlink":
            foreign.mkdir()
        occupied.symlink_to(foreign)
    before = {
        str(p): (os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
        for p in root.rglob("*")
    }
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)], env=_stub_env(tmp_path))
    assert result.returncode == 2
    assert str(occupied) in result.stderr
    if occupancy in ("symlink", "dangling"):
        assert str(foreign) in result.stderr
    after = {
        str(p): (os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
        for p in root.rglob("*")
    }
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
    assert result.returncode == 17, result.stderr
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
    assert str(entry) in result.stderr
    assert entry.read_text() == source
    assert not marker.exists()


def _uv_missing_python(tmp_path: Path, *, failure: str = "") -> Path:
    tool = tmp_path / "stub-bin/uv"
    builder = tool.with_name("uv-builder")
    tool.rename(builder)
    downloaded = tmp_path / "downloaded-python"
    tool.write_text(f'''#!{sys.executable}
import os, pathlib, sys
downloaded = pathlib.Path({str(downloaded)!r})
if sys.argv[1:3] == ['python', 'find']:
    if not downloaded.exists() or {failure == 'find'!r}:
        raise SystemExit(2)
    print({sys.executable!r})
elif sys.argv[1:3] == ['python', 'install']:
    if {failure == 'install'!r}:
        raise SystemExit(17)
    downloaded.write_text('3.12')
else:
    os.execv({str(builder)!r}, [{str(builder)!r}, *sys.argv[1:]])
''')
    tool.chmod(0o755)
    return downloaded


def test_uv_installs_missing_python_before_installing_components(tmp_path: Path) -> None:
    env = _stub_env(tmp_path)
    downloaded = _uv_missing_python(tmp_path)
    root = tmp_path / "roles"
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)], env=env)
    assert result.returncode == 0, result.stderr
    assert downloaded.read_text() == "3.12"
    _assert_roles(root)


def test_dry_run_with_missing_python_never_downloads_or_writes(tmp_path: Path) -> None:
    env = _stub_env(tmp_path)
    downloaded = _uv_missing_python(tmp_path)
    prefix = tmp_path / "prefix"
    root = tmp_path / "roles"
    result = _run(["--dry-run", "--prefix", str(prefix), "--skills-root", str(root)], env=env)
    assert result.returncode == 3, result.stderr
    assert "3.12" in result.stderr and "--dry-run" in result.stderr
    assert "uv python install 3.12" in result.stderr
    assert not downloaded.exists() and not prefix.exists() and not root.exists()


@pytest.mark.parametrize("failure", ["install", "find"])
def test_python_preparation_failure_reports_phase_without_installing_entries(tmp_path: Path, failure: str) -> None:
    env = _stub_env(tmp_path)
    _uv_missing_python(tmp_path, failure=failure)
    prefix = tmp_path / "prefix"
    root = tmp_path / "roles"
    result = _run(["--prefix", str(prefix), "--skills-root", str(root)], env=env)
    assert result.returncode == (17 if failure == "install" else 3), result.stderr
    assert "prepare-python" in result.stderr
    assert not prefix.exists() and not root.exists()


def test_install_without_uv_uses_python312(tmp_path: Path) -> None:
    env = _stub_env(tmp_path)
    bin_dir = tmp_path / "stub-bin"
    builder = bin_dir / "venv-builder"
    (bin_dir / "uv").rename(builder)
    python = bin_dir / "python3.12"
    python.write_text(f'''#!{sys.executable}
import os, sys
if sys.argv[1:3] == ['-m', 'venv']:
    os.execv({str(builder)!r}, [{str(builder)!r}, 'venv', sys.argv[-1]])
os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])
''')
    python.chmod(0o755)
    for name in ("bash", "dirname", "date", "readlink", "cat", "cmp", "mkdir", "cp", "mktemp", "env", "rm", "rmdir", "ln", "chmod"):
        executable = shutil.which(name)
        assert executable is not None
        (bin_dir / name).symlink_to(executable)
    env["PATH"] = str(bin_dir)
    root = tmp_path / "roles"
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)], env=env)
    assert result.returncode == 0, result.stderr
    _assert_roles(root)


@pytest.mark.parametrize("nested", [False, True])
def test_command_substitution_failure_reports_phase_once(tmp_path: Path, nested: bool) -> None:
    env = _stub_env(tmp_path)
    failure = tmp_path / "stub-bin/mktemp"
    failure.write_text("#!/bin/sh\nexit 17\n")
    failure.chmod(0o755)
    if nested:
        startup = tmp_path / "bash-startup"
        startup.write_text('mktemp() { local result; result=$(command mktemp "$@"); printf "%s\\n" "$result"; }\n')
        env["BASH_ENV"] = str(startup)
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(tmp_path / "roles")], env=env)
    assert result.returncode == 17, result.stderr
    assert result.stderr.count("阶段失败") == 1, result.stderr
    assert "validate" in result.stderr


def test_python312_named_shim_with_wrong_version_is_rejected(tmp_path: Path) -> None:
    env = _stub_env(tmp_path)
    bin_dir = tmp_path / "stub-bin"
    (bin_dir / "uv").unlink()
    python = bin_dir / "python3.12"
    python.write_text(f'''#!{sys.executable}
import sys
sys.version_info = (3, 13, 0)
exec(sys.argv[2])
''')
    python.chmod(0o755)
    for name in ("bash", "dirname", "date"):
        (bin_dir / name).symlink_to(shutil.which(name))
    env["PATH"] = str(bin_dir)
    prefix = tmp_path / "prefix"
    result = _run(["--prefix", str(prefix)], env=env)
    assert result.returncode == 3, result.stderr
    assert "prepare-python" in result.stderr and "Python 3.12" in result.stderr
    assert not prefix.exists()


def test_nondefault_prefix_names_its_binary_when_an_older_deck_is_first(tmp_path: Path) -> None:
    old_bin = tmp_path / "old-bin"
    old_bin.mkdir()
    old_deck = old_bin / "deck"
    old_deck.write_text("#!/bin/sh\necho old\n")
    old_deck.chmod(0o755)
    env = _stub_env(tmp_path)
    env["PATH"] = f"{old_bin}:{env['PATH']}"
    prefix = tmp_path / "prefix"
    root = tmp_path / "roles"
    result = _run(["--prefix", str(prefix), "--skills-root", str(root)], env=env)
    assert result.returncode == 0, result.stderr
    binary = str(prefix / "bin/deck")
    installed = (root / "deck-master" / "references" / "commands.md").read_text()
    assert binary in installed
    assert "<prefix>/bin/deck" not in installed
    assert "<prefix>/bin/deck" in (SOURCE / "references/commands.md").read_text()
    assert str(old_deck) in result.stdout
    assert binary in result.stdout
    source_path = (SOURCE / "references/commands.md").resolve()
    assert (root / "deck-master" / "references" / "commands.md").resolve() != source_path

    ahead = tmp_path / "ahead"
    ahead_root = tmp_path / "ahead-roles"
    ahead_env = dict(env)
    ahead_env["PATH"] = f"{ahead / 'bin'}:{env['PATH']}"
    ahead_result = _run(["--prefix", str(ahead), "--skills-root", str(ahead_root)], env=ahead_env)
    assert ahead_result.returncode == 0, ahead_result.stderr
    ahead_binary = str(ahead / "bin/deck")
    ahead_text = (ahead_root / "deck-content" / "references" / "commands.md").read_text()
    assert ahead_binary in ahead_text
    assert "<prefix>/bin/deck" not in ahead_text
    assert str(old_deck) not in ahead_result.stdout
    assert ahead_binary in ahead_result.stdout

    default = tmp_path / "home" / ".local"
    default_root = tmp_path / "default-roles"
    default_result = _run(["--prefix", str(default), "--skills-root", str(default_root)], env=env)
    assert default_result.returncode == 0, default_result.stderr
    default_text = (default_root / "deck-review" / "references" / "commands.md").read_text()
    assert default_text == (SOURCE / "references/commands.md").read_text()
    assert str(old_deck) in default_result.stdout
    assert str(default / "bin/deck") in default_result.stdout


def test_successful_validation_removes_only_its_temporary_probe(tmp_path: Path) -> None:
    env = _stub_env(tmp_path)
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    sentinel = temporary / "author.txt"
    sentinel.write_text("keep this")
    env["TMPDIR"] = str(temporary)
    result = _run(["--prefix", str(tmp_path / "prefix"), "--skills-root", str(tmp_path / "roles")], env=env)
    assert result.returncode == 0, result.stderr
    assert list(temporary.iterdir()) == [sentinel]
    assert sentinel.read_text() == "keep this"
