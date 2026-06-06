from __future__ import annotations

from typing import Any

from planning.page_budget import beat_templates, density_for, resolve_page_count


def identify_gaps(request: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if not request.get("industry"):
        gaps.append({"field": "industry", "message": "缺少明确行业，检索会按跨行业方案处理。"})
    if not request.get("must_cover_topics"):
        gaps.append({"field": "must_cover_topics", "message": "缺少必须覆盖主题，页面规划会采用通用方案结构。"})
    if "案例" not in str(request.get("brief", "")) and "case" not in str(request.get("brief", "")).lower():
        gaps.append({"field": "case_evidence", "message": "缺少可引用案例，案例页需要人工确认或生成占位。"})
    return gaps


def topic_hint(request: dict[str, Any], fallback: str) -> str:
    topics = request.get("must_cover_topics") or []
    if isinstance(topics, list) and topics:
        return "、".join(str(topic) for topic in topics)
    return fallback


def build_reuse_query(request: dict[str, Any], role: str, title: str) -> str:
    industry = request.get("industry") or "跨行业"
    topics = topic_hint(request, title)
    return f"{industry} {topics} {role} {title}"


def plan_narrative(request: dict[str, Any]) -> dict[str, Any]:
    page_count = resolve_page_count(str(request.get("target_pages") or "auto"), str(request.get("audience") or "client"))
    density = density_for(page_count)
    gaps = identify_gaps(request)
    beats = []
    for index, (role, title, goal) in enumerate(beat_templates(page_count), start=1):
        beat_id = f"beat_{index:02d}_{role}"
        evidence_need = "历史方案页或通用方法论"
        if role == "case":
            evidence_need = "可引用客户案例或相似项目经验"
        elif role == "roi":
            evidence_need = "收益指标、效率提升或成本优化依据"
        elif role == "architecture":
            evidence_need = "目标架构、系统关系或数据流证据"
        beats.append(
            {
                "beat_id": beat_id,
                "order": index,
                "page_title": title,
                "role": role,
                "brief": f"{goal} 需求背景：{request.get('business_goal', '')}",
                "content_goal": goal,
                "evidence_need": evidence_need,
                "visual_need": "历史页截图、架构图、能力矩阵或生成型页面",
                "density": density,
                "reuse_query": build_reuse_query(request, role, title),
                "generation_brief": f"生成一页{title}，用于{request.get('project_name', 'Deck')}。{goal}",
                "approval_required": role in {"case", "roi", "architecture"},
            }
        )
    return {
        "run_id": request.get("run_id", ""),
        "title": request.get("project_name", "Deck Master Run"),
        "target_pages": page_count,
        "density": density,
        "industry": request.get("industry", ""),
        "audience": request.get("audience", "client"),
        "roles": [beat["role"] for beat in beats],
        "gaps": gaps,
        "beats": beats,
    }
