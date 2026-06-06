from __future__ import annotations


BASE_BEATS = [
    ("opener", "开场定位", "说明本方案要解决的业务主题。"),
    ("problem", "业务痛点", "把现状问题压缩成客户能认可的判断。"),
    ("problem", "关键挑战", "解释挑战背后的业务原因和影响。"),
    ("solution", "总体方案", "给出解决路径和能力组合。"),
    ("solution", "能力矩阵", "把能力拆成可落地模块。"),
    ("architecture", "目标架构", "呈现系统、数据和业务流程的关系。"),
    ("solution", "全渠道场景", "说明线上线下协同的业务场景。"),
    ("solution", "库存可视化", "说明库存数据和运营动作如何闭环。"),
    ("solution", "最后一公里配送", "说明履约和配送优化路径。"),
    ("case", "案例与证据", "用案例或历史经验降低客户疑虑。"),
    ("roi", "价值与收益", "说明效率、增长、成本或体验价值。"),
    ("cta", "推进计划", "给出试点、路线图和下一步动作。"),
]


def resolve_page_count(target_pages: str, audience: str = "client") -> int:
    value = str(target_pages or "auto").strip().lower()
    if value == "auto":
        return 12 if audience in {"client", "exec"} else 15
    try:
        count = int(value)
    except ValueError:
        return 12
    if count <= 0:
        return 12
    return count


def density_for(page_count: int) -> str:
    if page_count <= 15:
        return "executive"
    if page_count <= 35:
        return "solution"
    return "chaptered"


def beat_templates(page_count: int) -> list[tuple[str, str, str]]:
    if page_count <= len(BASE_BEATS):
        return BASE_BEATS[:page_count]
    beats = list(BASE_BEATS)
    extra_roles = [
        ("solution", "业务流程拆解", "细化关键业务流程。"),
        ("architecture", "数据流与集成", "补充数据链路和系统集成。"),
        ("solution", "运营机制", "说明组织和流程如何承接。"),
        ("roi", "分阶段收益", "按阶段拆分价值。"),
        ("appendix", "附录与参考", "保留可供深入讨论的补充材料。"),
    ]
    while len(beats) < page_count:
        role, title, goal = extra_roles[(len(beats) - len(BASE_BEATS)) % len(extra_roles)]
        beats.append((role, f"{title} {len(beats) + 1}", goal))
    return beats
