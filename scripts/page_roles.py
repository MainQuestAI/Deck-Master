"""Canonical page-role normalization shared by preview, build, and quality."""

from __future__ import annotations

from typing import Any


CANONICAL_PAGE_ROLES = frozenset(
    {
        "cover",
        "section",
        "section_divider",
        "divider",
        "toc",
        "agenda",
        "visual",
        "visual_divider",
        "image",
        "image_page",
        "dense_narrative",
        "content",
        "framework",
        "architecture",
        "comparison",
        "data_story",
        "process",
        "table",
    }
)

NARRATIVE_ROLE_ALIASES = {
    "opener": "cover",
    "section_intro": "section",
    "section_handoff": "section_divider",
    "case": "content",
    "roi": "data_story",
}


def normalize_page_role(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def page_role_with_warning(value: Any, *, default: str = "content") -> tuple[str, str]:
    raw = normalize_page_role(value)
    if not raw:
        return normalize_page_role(default), ""
    if raw in CANONICAL_PAGE_ROLES:
        return raw, ""
    mapped = NARRATIVE_ROLE_ALIASES.get(raw)
    if mapped:
        return mapped, f"narrative_role '{raw}' migrated to page_role '{mapped}'"
    fallback = normalize_page_role(default)
    return fallback, f"unknown narrative_role '{raw}' defaulted to page_role '{fallback}'"


def canonical_page_role(value: Any, *, default: str = "content") -> str:
    return page_role_with_warning(value, default=default)[0]


STRUCTURAL_PAGE_ROLES = frozenset(
    {
        "cover",
        "section",
        "section_divider",
        "divider",
        "toc",
        "agenda",
        "visual",
        "visual_divider",
        "image",
        "image_page",
    }
)


def is_structural_page_role(value: Any) -> bool:
    return canonical_page_role(value, default="") in STRUCTURAL_PAGE_ROLES


__all__ = [
    "CANONICAL_PAGE_ROLES",
    "NARRATIVE_ROLE_ALIASES",
    "STRUCTURAL_PAGE_ROLES",
    "canonical_page_role",
    "is_structural_page_role",
    "normalize_page_role",
    "page_role_with_warning",
]
