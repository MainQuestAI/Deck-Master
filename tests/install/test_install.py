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
    assert "ln -s" in output
    assert str(REPO / "deck-skill") in output
    assert not prefix.exists()
    assert not skill.exists()


def test_existing_file_at_skill_dir_errors_without_writing(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    skill = tmp_path / "skills" / "deck"
    skill.parent.mkdir()
    skill.write_text("other skill", encoding="utf-8")
    result = _run(
        [
            "--dry-run",
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
            "--dry-run",
            "--prefix",
            str(prefix),
            "--skill-dir",
            str(skill),
        ]
    )
    assert result.returncode == 2
    assert "其他位置" in result.stderr
    assert Path(os.readlink(skill)) == other


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
