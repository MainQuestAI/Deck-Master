from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TOPIC_KEYWORDS = {
    "全渠道": ["全渠道", "omnichannel", "线上线下"],
    "库存可视化": ["库存", "可视化", "inventory"],
    "最后一公里配送": ["最后一公里", "配送", "物流", "last mile"],
    "客户经营": ["客户经营", "会员", "cdp", "私域"],
    "内容中台": ["内容", "DAM", "CMS", "素材"],
    "AI智能体": ["AI", "智能体", "agent", "AIGC"],
}


def load_brief_text(brief: str = "", brief_file: str | Path | None = None) -> str:
    if brief and brief_file:
        raise ValueError("Use either --brief or --brief-file, not both.")
    if brief_file:
        return Path(brief_file).expanduser().read_text(encoding="utf-8").strip()
    if brief:
        return brief.strip()
    raise ValueError("A brief or brief_file is required.")


def detect_topics(text: str) -> list[str]:
    lowered = text.lower()
    topics: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            topics.append(topic)
    return topics


def infer_project_name(text: str, industry: str = "") -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:48]
    return f"{industry or '通用'}方案"


def build_request(
    *,
    brief: str = "",
    brief_file: str | Path | None = None,
    industry: str = "",
    target_pages: str = "auto",
    audience: str = "client",
    style_preference: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    text = load_brief_text(brief, brief_file)
    parsed: dict[str, Any] = {}
    if text.startswith("{"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                parsed = payload
                text = str(payload.get("brief") or payload.get("business_goal") or text)
        except json.JSONDecodeError:
            parsed = {}

    actual_industry = industry or str(parsed.get("industry") or "")
    topics = parsed.get("must_cover_topics")
    if not isinstance(topics, list) or not topics:
        topics = detect_topics(text)

    request = {
        "run_id": run_id or str(parsed.get("run_id") or ""),
        "project_name": str(parsed.get("project_name") or infer_project_name(text, actual_industry)),
        "industry": actual_industry,
        "audience": audience or str(parsed.get("audience") or "client"),
        "business_goal": str(parsed.get("business_goal") or text),
        "brief": text,
        "must_cover_topics": [str(topic) for topic in topics],
        "source_constraints": parsed.get("source_constraints") if isinstance(parsed.get("source_constraints"), list) else [],
        "target_pages": str(target_pages or parsed.get("target_pages") or "auto"),
        "style_preference": style_preference or str(parsed.get("style_preference") or ""),
    }
    return request
