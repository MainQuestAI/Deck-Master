"""Checks for scripts/install.sh: dry-run plan and skill-link refusal."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "install.sh"


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


def test_dry_run_prints_install_plan(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    skill = tmp_path / "skills" / "deck"
    result = _run(
        [
            "--dry-run",
            "--prefix",
            str(prefix),
            "--skill-dir",
            str(skill),
        ]
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert "cargo install" in output
    assert "--path" in output
    assert str(REPO / "rust") in output
    assert "uv venv --python 3.12 --seed" in output or "python3.12 -m venv" in output
    assert str(prefix / "share" / "deck" / "venv") in output
    assert "run build" in output
    assert "npm test" not in output
    assert "ln -s" in output
    assert str(REPO / "deck-skill") in output
    assert f"deck-bin={prefix / 'bin' / 'deck'}" in output
    assert not prefix.exists()
    assert not skill.exists()


def test_existing_file_at_skill_dir_errors_without_writing(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    skill = tmp_path / "skills" / "deck"
    skill.parent.mkdir()
    skill.write_text("other skill", encoding="utf-8")
    result = _run(
        [
            "--prefix",
            str(prefix),
            "--skill-dir",
            str(skill),
        ]
    )
    assert result.returncode == 2
    assert "已存在" in result.stderr
    assert skill.read_text(encoding="utf-8") == "other skill"
    assert not prefix.exists()


def test_skill_link_to_another_target_errors(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    other = tmp_path / "other-skill"
    other.mkdir()
    skill = tmp_path / "skills" / "deck"
    skill.parent.mkdir()
    os.symlink(other, skill)
    result = _run(
        [
            "--prefix",
            str(prefix),
            "--skill-dir",
            str(skill),
        ]
    )
    assert result.returncode == 2
    assert "已存在且指向其他位置" in result.stderr
    assert "不要删除它指向的目录" in result.stderr
    assert Path(os.readlink(skill)) == other
    assert not prefix.exists()


def test_matching_skill_link_is_kept(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    skill = tmp_path / "skills" / "deck"
    skill.parent.mkdir()
    os.symlink(REPO / "deck-skill", skill)
    result = _run(
        [
            "--dry-run",
            "--prefix",
            str(prefix),
            "--skill-dir",
            str(skill),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert "skill-link=already" in result.stdout
    assert "ln -s" not in result.stdout
    assert Path(os.readlink(skill)) == REPO / "deck-skill"


def test_script_is_executable() -> None:
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR


def test_skill_flags_are_mutually_exclusive(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    result = _run(
        [
            "--dry-run",
            "--prefix",
            str(prefix),
            "--skill-dir",
            str(tmp_path / "one" / "deck"),
            "--skills-root",
            str(tmp_path / "roles"),
        ]
    )
    assert result.returncode == 2
    assert "不能同时使用" in result.stderr
    assert not prefix.exists()
    assert not (tmp_path / "roles").exists()


def test_default_dry_run_installs_only_compatibility_entry(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = _run(["--dry-run", "--prefix", str(tmp_path / "prefix")], env={"HOME": str(home)})
    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert "skill-mode=compat" in output
    assert f"skill-dir={home / '.codex' / 'skills' / 'deck'}" in output
    assert "skill-entry=deck-master" not in output
    assert "deck-master.md" not in output
    assert not (home / ".codex").exists()


def test_skills_root_dry_run_plans_five_entries(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    result = _run(
        [
            "--dry-run",
            "--prefix",
            str(tmp_path / "prefix"),
            "--skills-root",
            str(root),
        ]
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert "skill-mode=roles" in output
    assert "skill-link=create" in output
    for role in ("deck-master", "deck-content", "deck-design", "deck-review"):
        assert f"skill-entry={role} action=create" in output
        assert f"{REPO / 'deck-skill' / (role + '.md')}" in output
    assert str(REPO / "deck-skill" / "references") in output
    assert str(REPO / "deck-skill" / "assets") in output
    assert not root.exists()


def test_skills_root_refuses_foreign_symlink_without_writing(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    foreign = tmp_path / "old-content"
    foreign.mkdir()
    occupied = root / "deck-content"
    occupied.parent.mkdir()
    os.symlink(foreign, occupied)
    result = _run(
        ["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)]
    )
    assert result.returncode == 2
    assert str(occupied) in result.stderr
    assert str(foreign) in result.stderr
    assert Path(os.readlink(occupied)) == foreign
    assert not (root / "deck").exists()
    assert not (root / "deck-master").exists()
    assert not (tmp_path / "prefix").exists()


def test_skills_root_refuses_plain_directory_without_writing(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    occupied = root / "deck-review"
    occupied.mkdir(parents=True)
    marker = occupied / "SKILL.md"
    marker.write_text("old line", encoding="utf-8")
    result = _run(
        ["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)]
    )
    assert result.returncode == 2
    assert str(occupied) in result.stderr
    assert marker.read_text(encoding="utf-8") == "old line"
    assert not (root / "deck-design").exists()
    assert not (tmp_path / "prefix").exists()


def test_skills_root_does_not_repair_partial_role_directory(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    role = root / "deck-design"
    role.mkdir(parents=True)
    other = tmp_path / "other-assets"
    other.mkdir()
    os.symlink(REPO / "deck-skill" / "deck-design.md", role / "SKILL.md")
    os.symlink(REPO / "deck-skill" / "references", role / "references")
    os.symlink(other, role / "assets")
    result = _run(
        ["--prefix", str(tmp_path / "prefix"), "--skills-root", str(root)]
    )
    assert result.returncode == 2
    assert str(role) in result.stderr
    assert Path(os.readlink(role / "assets")) == other
    assert Path(os.readlink(role / "SKILL.md")) == REPO / "deck-skill" / "deck-design.md"
    assert not (root / "deck").exists()


def test_matching_role_links_are_kept(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    os.symlink(REPO / "deck-skill", root / "deck")
    note = "keep me"
    for role in ("deck-master", "deck-content", "deck-design", "deck-review"):
        directory = root / role
        directory.mkdir()
        os.symlink(REPO / "deck-skill" / f"{role}.md", directory / "SKILL.md")
        os.symlink(REPO / "deck-skill" / "references", directory / "references")
        os.symlink(REPO / "deck-skill" / "assets", directory / "assets")
        (directory / "NOTES").write_text(note, encoding="utf-8")
    result = _run(
        [
            "--dry-run",
            "--prefix",
            str(tmp_path / "prefix"),
            "--skills-root",
            str(root),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert "skill-link=already" in result.stdout
    assert "action=keep" in result.stdout
    assert "ln -s" not in result.stdout
    assert (root / "deck-content" / "NOTES").read_text(encoding="utf-8") == note


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


def _stub_env(tmp_path: Path, home: Path | None = None) -> dict[str, str]:
    env = {"PATH": f"{_stub_tools(tmp_path)}:{os.environ['PATH']}"}
    if home is not None:
        env["HOME"] = str(home)
    return env


def test_relative_links_to_this_source_are_already_installed(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    root.mkdir()
    os.symlink(os.path.relpath(REPO / "deck-skill", root), root / "deck")
    role = root / "deck-content"
    role.mkdir()
    os.symlink(os.path.relpath(REPO / "deck-skill" / "deck-content.md", role), role / "SKILL.md")
    os.symlink(os.path.relpath(REPO / "deck-skill" / "references", role), role / "references")
    os.symlink(os.path.relpath(REPO / "deck-skill" / "assets", role), role / "assets")
    before = {
        name: os.readlink(role / name) for name in ("SKILL.md", "references", "assets")
    }
    result = _run(
        [
            "--dry-run",
            "--prefix",
            str(tmp_path / "prefix"),
            "--skills-root",
            str(root),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert "skill-link=already" in result.stdout
    assert "skill-entry=deck-content action=keep" in result.stdout
    assert {name: os.readlink(role / name) for name in before} == before


def test_stub_install_creates_role_links_and_repeat_keeps_extra_files(tmp_path: Path) -> None:
    root = tmp_path / "roles"
    prefix = tmp_path / "prefix"
    env = _stub_env(tmp_path)
    first = _run(["--prefix", str(prefix), "--skills-root", str(root)], env=env)
    assert first.returncode == 0, first.stderr
    deck = root / "deck"
    assert deck.is_symlink()
    assert Path(os.readlink(deck)) == REPO / "deck-skill"
    for role in ("deck-master", "deck-content", "deck-design", "deck-review"):
        directory = root / role
        assert Path(os.readlink(directory / "SKILL.md")) == REPO / "deck-skill" / f"{role}.md"
        assert Path(os.readlink(directory / "references")) == REPO / "deck-skill" / "references"
        assert Path(os.readlink(directory / "assets")) == REPO / "deck-skill" / "assets"
    note = root / "deck-master" / "NOTES"
    note.write_text("author note", encoding="utf-8")
    second = _run(["--prefix", str(prefix), "--skills-root", str(root)], env=env)
    assert second.returncode == 0, second.stderr
    assert note.read_text(encoding="utf-8") == "author note"
    assert "ln -s" not in second.stdout
    other = tmp_path / "elsewhere"
    other.mkdir()
    reading = root / "deck-content" / "references" / "source-reading.md"
    design = root / "deck-design" / "references" / "content-to-visual.md"
    semantic = root / "deck-design" / "assets" / "design" / "semantic-layout-examples.md"
    routes = root / "deck-master" / "assets" / "master" / "routing-examples.json"
    patterns = root / "deck-content" / "references" / "narrative-patterns.md"
    template = root / "deck-content" / "assets" / "content" / "templates" / "page-draft.md"
    review = root / "deck-review" / "references" / "method-review.md"
    calibration = root / "deck-review" / "assets" / "review" / "calibration-cases.json"
    opened = subprocess.run(
        [
            "python3",
            "-c",
                "import pathlib,sys\n"
                "missing=[item for item in sys.argv[1:] if not pathlib.Path(item).is_file()]\n"
                "print('\\n'.join(missing))\n"
                "raise SystemExit(1 if missing else 0)",
            str(reading),
            str(design),
            str(semantic),
            str(routes),
            str(patterns),
            str(template),
            str(review),
            str(calibration),
        ],
        cwd=other,
        text=True,
        capture_output=True,
        check=False,
    )
    assert opened.returncode == 0, opened.stderr


def test_stub_skill_dir_does_not_create_role_entries(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    deck = skills / "deck"
    result = _run(
        ["--prefix", str(tmp_path / "prefix"), "--skill-dir", str(deck)],
        env=_stub_env(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert Path(os.readlink(deck)) == REPO / "deck-skill"
    assert not (skills / "deck-content").exists()


def test_stub_default_install_skips_role_entries(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = _run(
        ["--prefix", str(tmp_path / "prefix")],
        env=_stub_env(tmp_path, home),
    )
    assert result.returncode == 0, result.stderr
    deck = home / ".codex" / "skills" / "deck"
    assert Path(os.readlink(deck)) == REPO / "deck-skill"
    assert not (home / ".codex" / "skills" / "deck-master").exists()
