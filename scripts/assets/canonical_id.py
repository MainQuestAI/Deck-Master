from __future__ import annotations
from typing import Any
from assets.schema import compute_canonical_slide_id


def normalize_title(title: str) -> str:
    """标准化标题用于 ID 计算。"""
    return " ".join(title.split()).lower().strip()


def candidate_to_canonical_id(candidate: dict[str, Any]) -> str:
    """从 library candidate 计算 canonical slide ID。"""
    return compute_canonical_slide_id(
        file_sha256=candidate.get("file_sha256", ""),
        page_number=candidate.get("page_number", candidate.get("slide_index", 0)),
        normalized_title=normalize_title(candidate.get("title", candidate.get("page_title", ""))),
        fallback_source_ref=candidate.get("source_pptx", candidate.get("source_project", "")),
        fallback_text_summary=candidate.get("text_summary", candidate.get("excerpt", "")),
    )
