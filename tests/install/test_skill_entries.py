"""Role entries stay independently addressable and share one method tree."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "deck-skill"
ROLES = ("deck-master", "deck-content", "deck-design", "deck-review")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")


def _local_links(text: str) -> list[str]:
    found = []
    for raw in LINK.findall(text):
        if raw.startswith(("http://", "https://", "mailto:")):
            continue
        path = raw.split("#", 1)[0]
        if path:
            found.append(path)
    return found


def _frontmatter_name(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing name in {path}")


def test_source_has_one_skill_manifest_and_unique_names() -> None:
    manifests = [path for path in SOURCE.rglob("SKILL.md")]
    assert manifests == [SOURCE / "SKILL.md"]
    names = [_frontmatter_name(SOURCE / "SKILL.md")]
    names.extend(_frontmatter_name(SOURCE / f"{role}.md") for role in ROLES)
    assert names == ["deck", *ROLES]


def test_role_entries_call_rust_deck() -> None:
    for role in ROLES:
        text = (SOURCE / f"{role}.md").read_text(encoding="utf-8")
        assert "`deck`" in text
        assert "deck_master" not in text
        assert "python -m deck_master" not in text
        for link in _local_links(text):
            assert link.startswith(("references/", "assets/"))


def test_shared_links_resolve_from_source_and_from_role_directory(tmp_path: Path) -> None:
    install = tmp_path / "skills"
    for role in ROLES:
        directory = install / role
        directory.mkdir(parents=True)
        os.symlink(SOURCE / f"{role}.md", directory / "SKILL.md")
        os.symlink(SOURCE / "references", directory / "references")
        os.symlink(SOURCE / "assets", directory / "assets")
        source_text = (SOURCE / f"{role}.md").read_text(encoding="utf-8")
        for link in _local_links(source_text):
            from_source = (SOURCE / link).resolve()
            from_install = (directory / link).resolve()
            assert from_source.is_file() or from_source.is_dir()
            assert from_install == from_source


def test_method_markdown_links_resolve() -> None:
    for path in SOURCE.rglob("*.md"):
        for link in _local_links(path.read_text(encoding="utf-8")):
            target = (path.parent / link).resolve()
            assert target.is_file() or target.is_dir(), f"{path} -> {link}"


@pytest.mark.parametrize("relative", ["deck-content.md", "references/page-writing.md"])
def test_title_policy_preserves_page_roles(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    paragraphs = re.split(r"\n\s*\n", text)
    for role in ("说明", "教学"):
        policies = [paragraph for paragraph in paragraphs if re.search(rf"{role}(?:页|页面)", paragraph)]
        assert any(
            re.search(r"(?:不(?:强制|要求|必)|无[需须]).{0,30}(?:结论|判断).{0,8}标题", policy)
            and re.search(r"(?:不(?:强制|要求|必)|无[需须]).{0,40}(?:商业\s*)?CTA", policy)
            for policy in policies
        ), f"{relative}: {role} pages need title and CTA exceptions"
    assert re.search(r"判断页.{0,30}判断句", text)
    assert re.search(r"查阅页.{0,30}查阅职责", text)
