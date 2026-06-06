from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.events import append_event


TASK_DECISIONS = {"generate", "adapt"}


def task_for_decision(decision: dict[str, Any], index: int) -> dict[str, Any]:
    selected = decision.get("selected_candidate") if isinstance(decision.get("selected_candidate"), dict) else None
    return {
        "task_id": f"generation_{index:02d}_{decision.get('beat_id')}",
        "beat_id": decision.get("beat_id"),
        "page_title": decision.get("page_title"),
        "source_decision": decision.get("source_decision"),
        "generation_brief": decision.get("generation_brief", ""),
        "reference_slide": selected,
        "visual_need": decision.get("visual_need", ""),
        "evidence_need": decision.get("evidence_need", ""),
        "style_constraints": "Follow the deck-level style and preserve any selected reference slide structure.",
        "status": "pending",
    }


def create_generation_tasks(sourcing_plan: dict[str, Any], run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    tasks_dir = root / "generation_tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        task_for_decision(decision, index)
        for index, decision in enumerate(sourcing_plan.get("decisions", []), start=1)
        if isinstance(decision, dict) and decision.get("source_decision") in TASK_DECISIONS
    ]
    for task in tasks:
        (tasks_dir / f"{task['task_id']}.json").write_text(
            json.dumps(task, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    payload = {
        "run_id": sourcing_plan.get("run_id", ""),
        "deck_pro_max_project": str((root / "deck_pro_max_project").resolve()),
        "tasks": tasks,
    }
    (root / "deck_pro_max_project").mkdir(parents=True, exist_ok=True)
    (tasks_dir / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_event(root, "generation.tasks.created", payload_ref="generation_tasks/index.json", data={"tasks": len(tasks)})
    return payload
