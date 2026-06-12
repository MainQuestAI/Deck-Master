from __future__ import annotations
from pathlib import Path
from typing import Any

from assets.schema import load_asset_graph, save_asset_graph


# 页型 archetype 关键词映射
ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "problem_statement": ["问题", "挑战", "痛点", "problem", "challenge"],
    "solution_overview": ["解决方案", "方案", "解决路径", "solution"],
    "architecture": ["架构", "系统", "技术", "architecture", "system"],
    "case_study": ["案例", "客户", "经验", "case", "story"],
    "roi_value": ["收益", "ROI", "价值", "回报", "效率", "成本"],
    "roadmap": ["路线图", "计划", "里程碑", "roadmap", "timeline"],
    "team_capability": ["团队", "能力", "资质", "team", "capability"],
    "opener": ["封面", "标题", "cover", "title"],
    "closing": ["总结", "下一步", "联系", "summary", "next step"],
}


def tag_archetypes(
    workspace_dir: str | Path,
) -> dict[str, Any]:
    """为 workspace 中的 asset 打 archetype 标签。

    基于 title 和 metadata.role 中的关键词匹配。
    """
    workspace_dir = Path(workspace_dir).expanduser().resolve()
    graph = load_asset_graph(workspace_dir)
    assets = graph.get("assets", [])

    tagged_count = 0
    for asset in assets:
        title = (asset.get("title", "") or "").lower()
        metadata = asset.get("metadata", {})
        role = str(metadata.get("role", "")).lower()

        archetypes: list[str] = []

        # 从 role 匹配
        for archetype, keywords in ARCHETYPE_KEYWORDS.items():
            if role and any(kw.lower() in role for kw in keywords):
                archetypes.append(archetype)

        # 从 title 匹配（补充 role 未命中的）
        for archetype, keywords in ARCHETYPE_KEYWORDS.items():
            if archetype not in archetypes:
                if any(kw.lower() in title for kw in keywords):
                    archetypes.append(archetype)

        if archetypes:
            asset["archetypes"] = archetypes
            tagged_count += 1
        elif "archetypes" not in asset:
            asset["archetypes"] = []

    if assets:
        save_asset_graph(workspace_dir, graph)

    return {
        "workspace_dir": str(workspace_dir),
        "total_assets": len(assets),
        "tagged_count": tagged_count,
    }
