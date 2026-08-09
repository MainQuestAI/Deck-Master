from __future__ import annotations

import re
from typing import Any

from .contracts import ContractError, sha256_json


HARD_FORBIDDEN_CATEGORIES = ("page_number", "slide_counter", "page_id_badge")
HIDDEN_BY_DEFAULT_CATEGORIES = (
    "evidence_marker",
    "source_marker",
    "methodology_label",
    "explanatory_label",
    "caveat_label",
    "placeholder",
    "production_annotation",
)

_LABEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("evidence_marker", re.compile(r"^(?:evidence(?:\s*id)?|证据(?:\s*id)?|证据占位)\s*[:：]?$", re.I)),
    ("source_marker", re.compile(r"^(?:source|来源|口径|日期|date)\s*[:：]?$", re.I)),
    ("methodology_label", re.compile(r"^(?:swot|nbb|scr|so\s*what)\s*[:：/]?$", re.I)),
    ("explanatory_label", re.compile(r"^(?:说明|note|notes|explanation)\s*[:：]?$", re.I)),
    ("caveat_label", re.compile(r"^(?:caveat|注意事项|假设与边界)\s*[:：]?$", re.I)),
    ("placeholder", re.compile(r"^(?:待补充|占位|placeholder|tbd|todo)\s*[:：]?$", re.I)),
    ("production_annotation", re.compile(r"^(?:prompt|wireframe|generation|internal|生产标注)\s*[:：]?$", re.I)),
)


def build_visibility_policy(package: dict[str, Any], *, page_id: str) -> dict[str, Any]:
    requirements = package.get("build_requirements") or {}
    requested = requirements.get("visibility_policy") or {}
    raw_allowed = requested.get("allowed_visible_terms") or []
    allowed: list[dict[str, str]] = []
    for item in raw_allowed:
        if not isinstance(item, dict):
            raise ContractError("visibility_policy.allowed_visible_terms must contain objects")
        term = str(item.get("term") or "").strip()
        content_ref = str(item.get("content_ref") or "").strip()
        approved_by = str(item.get("approved_by") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not all((term, content_ref, approved_by, reason)):
            raise ContractError("each visibility allowlist term requires term, content_ref, approved_by, and reason")
        allowed.append({"term": term, "content_ref": content_ref, "approved_by": approved_by, "reason": reason})
    policy = {
        "version": "high-density-visible-content.v1",
        "page_id": page_id,
        "hard_forbidden": list(HARD_FORBIDDEN_CATEGORIES),
        "hidden_by_default": list(HIDDEN_BY_DEFAULT_CATEGORIES),
        "allowed_visible_terms": allowed,
    }
    policy["visibility_policy_sha256"] = sha256_json(policy)
    return policy


def validate_visibility_policy(policy: dict[str, Any], *, page_id: str) -> None:
    if str(policy.get("page_id") or "") != page_id:
        raise ContractError(f"visibility policy page_id mismatch: {page_id}")
    expected = sha256_json({key: value for key, value in policy.items() if key != "visibility_policy_sha256"})
    if str(policy.get("visibility_policy_sha256") or "") != expected:
        raise ContractError(f"visibility policy hash is stale on {page_id}")
    if list(policy.get("hard_forbidden") or []) != list(HARD_FORBIDDEN_CATEGORIES):
        raise ContractError("visibility policy cannot relax page-number protections")
    allowed = policy.get("allowed_visible_terms") or []
    if not isinstance(allowed, list) or any(not isinstance(item, dict) for item in allowed):
        raise ContractError("visibility policy allowlist is invalid")


def visible_text_violation(policy: dict[str, Any], text: str, *, page_id: str) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    allowed = {str(item.get("term") or "").strip() for item in policy.get("allowed_visible_terms") or [] if isinstance(item, dict)}
    if value in allowed:
        return None
    compact = re.sub(r"\s+", "", value)
    if compact.casefold() == page_id.casefold() or re.fullmatch(r"(?:page|p|页码|第)\s*\d+|\d+\s*/\s*\d+", value, re.I):
        return "page_number"
    for category, pattern in _LABEL_PATTERNS:
        if pattern.fullmatch(value):
            return category
    return None


def assert_visible_text_allowed(policy: dict[str, Any], text: str, *, page_id: str, context: str) -> None:
    violation = visible_text_violation(policy, text, page_id=page_id)
    if violation:
        raise ContractError(f"unapproved visible {violation} in {context}: {text}")


__all__ = [
    "HARD_FORBIDDEN_CATEGORIES",
    "HIDDEN_BY_DEFAULT_CATEGORIES",
    "assert_visible_text_allowed",
    "build_visibility_policy",
    "validate_visibility_policy",
    "visible_text_violation",
]
