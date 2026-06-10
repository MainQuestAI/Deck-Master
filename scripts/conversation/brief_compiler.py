from __future__ import annotations

import re
from typing import Any


def split_sentences(text: str, limit: int = 5) -> list[str]:
    parts = [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]
    return parts[:limit]


def infer_core_points(request: dict[str, Any], context_manifest: dict[str, Any], conversation: dict[str, Any]) -> list[str]:
    topics = request.get("must_cover_topics") if isinstance(request.get("must_cover_topics"), list) else []
    points = [str(topic) for topic in topics if str(topic).strip()]
    summary = str(context_manifest.get("summary") or request.get("business_goal") or "")
    for sentence in split_sentences(summary):
        if sentence not in points:
            points.append(sentence)
    if not points:
        points.append(str(conversation.get("locked_decisions", {}).get("business_goal") or "明确客户问题并给出解决方案"))
    return points[:8]


def compile_deck_brief(request: dict[str, Any], context_manifest: dict[str, Any], conversation: dict[str, Any]) -> dict[str, Any]:
    locked = conversation.get("locked_decisions", {}) if isinstance(conversation.get("locked_decisions"), dict) else {}
    core_points = infer_core_points(request, context_manifest, conversation)
    return {
        "run_id": request.get("run_id", ""),
        "project_name": request.get("project_name", "Deck Master Run"),
        "audience": locked.get("audience") or request.get("audience", "client"),
        "industry": locked.get("industry") or request.get("industry", ""),
        "business_goal": locked.get("business_goal") or request.get("business_goal", ""),
        "core_points": core_points,
        "must_cover_topics": request.get("must_cover_topics", []),
        "source_refs": [source.get("source_id") for source in context_manifest.get("sources", [])],
        "style_preference": request.get("style_preference", ""),
        "target_pages": request.get("target_pages", "auto"),
        "boundaries": [
            "输出第一版可审查客户方案 Deck 草案。",
            "优先做论点、论证、论据和证据链，不追求一次性最终 PPTX。",
            "上下文只做运行时引用，不写入长期知识库。",
        ],
    }
