"""Checks for scripts/install.sh: dry-run plan and skill-link refusal."""

from __future__ import annotations

import os
import stat
import subprocess
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
        assert Path(os.readlink(directory)) == SOURCE / role
        assert (directory / "SKILL.md").is_file()
        assert not (directory / "SKILL.md").is_symlink()
        for name in ("references", "assets"):
            assert (directory / name).resolve() == SOURCE / name


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
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    (bin_dir / "npm").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (bin_dir / "cargo").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (bin_dir / "uv").write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "dest=",
                "prev=",
                'for arg in "$@"; do',
                '  if [ "$prev" = "--seed" ]; then',
                "    dest=$arg",
                "  fi",
                "  prev=$arg",
                "done",
                'mkdir -p "$dest/bin"',
                "printf '%s\\n' '#!/bin/sh' 'exit 0' > \"$dest/bin/python\"",
                'chmod +x "$dest/bin/python"',
                "exit 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
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
    assert str(prefix / "share/deck/venv") in output
    assert "run build" in output
    assert f"deck-bin={prefix / 'bin/deck'}" in output
    assert f"skills-root={root}" in output
    assert "skill-entry=deck action=absent" in output
    for role in ROLES:
        assert f"skill-entry={role} action=create" in output
        assert f"ln -s {SOURCE / role} {root / role}" in output
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


def test_relative_whole_directory_links_are_kept(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    for role in ROLES:
        (root / role).symlink_to(os.path.relpath(SOURCE / role, root))
    result = _run(["--dry-run", "--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)])
    assert result.returncode == 0, result.stderr
    for role in ROLES:
        assert f"skill-entry={role} action=keep" in result.stdout
    assert "ln -s" not in result.stdout
