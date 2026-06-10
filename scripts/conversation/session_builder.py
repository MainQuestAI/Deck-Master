from __future__ import annotations

from typing import Any


GUIDED_QUESTIONS = [
    {
        "question_id": "audience_goal",
        "prompt": "这份 Deck 面向谁？他们看完后需要做什么决定？",
        "purpose": "锁定受众、决策场景和表达深度。",
    },
    {
        "question_id": "core_claim",
        "prompt": "如果只能让对方记住一个判断，这个判断是什么？",
        "purpose": "逼出主论点，避免页面变成材料堆叠。",
    },
    {
        "question_id": "evidence",
        "prompt": "哪些案例、截图、数据或客户原话可以证明这个判断？",
        "purpose": "建立论证和论据，不只输出观点。",
    },
    {
        "question_id": "reuse_assets",
        "prompt": "哪些历史方案页、业务模型或框架值得复用？",
        "purpose": "把历史资产接入本次 Deck。",
    },
    {
        "question_id": "cut_line",
        "prompt": "哪些内容应该删掉或放进附录？",
        "purpose": "让有限页数承载最关键的信息。",
    },
]


def build_conversation_session(request: dict[str, Any], context_manifest: dict[str, Any]) -> dict[str, Any]:
    context_summary = str(context_manifest.get("summary") or "")
    business_goal = str(request.get("business_goal") or context_summary)
    locked_decisions = {
        "audience": request.get("audience", "client"),
        "business_goal": business_goal,
        "context_strategy": "runtime_reference",
        "first_output": "reviewable_deck_draft",
    }
    if request.get("industry"):
        locked_decisions["industry"] = request["industry"]
    if request.get("must_cover_topics"):
        locked_decisions["must_cover_topics"] = request["must_cover_topics"]
    return {
        "run_id": request.get("run_id", ""),
        "mode": "guided_deck_conversation",
        "status": "draft",
        "context_refs": [source.get("source_id") for source in context_manifest.get("sources", [])],
        "locked_decisions": locked_decisions,
        "questions": GUIDED_QUESTIONS,
        "answers": [],
        "notes": [
            "首版记录 AI 引导问题和已锁定判断；实际多轮交互可后续接入。",
            "Deck Master 不保存长期思考库，只保存本次 run 的审查轨迹。",
        ],
    }
