"""Keep the public first-run material and its documented paths usable."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "examples/first-run"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")


@pytest.mark.parametrize("relative", [
    "README.md", "zh/material.md", "zh/brief.md", "en/material.md", "en/brief.md",
])
def test_first_run_files_are_readable_and_substantial(relative: str) -> None:
    path = SAMPLE / relative
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert text.strip()


@pytest.mark.parametrize("name", ["README.md", "README.zh-CN.md"])
def test_readme_example_paths_exist(name: str) -> None:
    text = (REPO / name).read_text(encoding="utf-8")
    assert "examples/first-run" in text
    assert "deck serve" in text
    paths = re.findall(r"\bexamples/[^\s`<>\[\]()\"'#，。,;:!?]+", text)
    for relative in paths:
        assert (REPO / relative).exists(), f"{name} -> {relative}"


def test_sample_readme_local_links_resolve() -> None:
    text = (SAMPLE / "README.md").read_text(encoding="utf-8")
    for raw in LINK.findall(text):
        if raw.startswith(("https://", "http://", "mailto:")):
            continue
        relative = raw.split("#", 1)[0]
        if relative:
            assert (SAMPLE / relative).exists(), raw
