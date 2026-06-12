from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_delivery_outcome.v1"

def record_delivery_outcome(
    run_dir: str | Path,
    *,
    delivered: bool = False,
    advanced_to_next_stage: bool = False,
    customer_reaction: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """记录交付结果。"""
    run_dir = Path(run_dir).expanduser().resolve()
    run_id = run_dir.name

    outcome = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "delivered": delivered,
        "delivered_at": datetime.now(timezone.utc).isoformat() if delivered else None,
        "advanced_to_next_stage": advanced_to_next_stage,
        "customer_reaction": customer_reaction,
        "notes": notes,
    }

    # 写 delivery outcome (canonical path)
    delivery_dir = run_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    outcome_path = delivery_dir / "delivery_outcome.json"
    tmp = outcome_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(outcome_path)

    # 写 typed event
    try:
        from runtime.events import append_typed_event
        append_typed_event(
            run_dir, "step_completed", "delivery.outcome.recorded",
            f"Delivery outcome: delivered={delivered}, advanced={advanced_to_next_stage}",
            refs=["delivery/delivery_outcome.json"],
        )
    except Exception:
        pass

    # 反哺 asset feedback（如果有 workspace）
    try:
        request_path = run_dir / "request.json"
        if request_path.exists() and delivered:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            workspace = request.get("workspace", "")
            if workspace:
                from assets.feedback import append_feedback
                # 读取 asset_refs
                refs_path = run_dir / "asset_refs.json"
                if refs_path.exists():
                    refs = json.loads(refs_path.read_text(encoding="utf-8"))
                    for ref in refs.get("asset_refs", []):
                        cid = ref.get("canonical_slide_id", "")
                        if cid:
                            append_feedback(
                                workspace, "delivered", cid,
                                run_id=run_id, page_id=ref.get("beat_id", ""),
                            )
    except Exception:
        pass

    return outcome
