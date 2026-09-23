"""Read-only check that a proposed PPTX handoff belongs to the current run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .editing import check_summary
from .store import Store


def check_handoff(project_dir, *, file_path, purpose="review"):
    if purpose not in ("review", "delivery"):
        raise ValueError("purpose must be review or delivery")
    candidate = Path(file_path).expanduser().resolve()
    if not candidate.is_file() or candidate.suffix.lower() != ".pptx":
        raise ValueError("file must be an existing PPTX")

    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    output_ref = (document.get("outputs") or {}).get("pptx")
    expected_hash = None
    if output_ref:
        expected_hash = store.read_object_json(output_ref)["file"]["sha256"]
    actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()

    gaps = []
    if not output_ref:
        gaps.append("missing_current_pptx")
    if actual_hash != expected_hash:
        gaps.append("candidate_not_current_output")
    for entry in document.get("pages") or []:
        for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
            if not entry.get(slot):
                gaps.append(f"{entry['page_id']}:missing_{slot}")

    pending = []
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if task.get("status") in ("awaiting_host", "running"):
            pending.append({"task_id": task["task_id"], "kind": task["kind"], "status": task["status"]})
    if pending:
        gaps.append("pending_host_tasks")

    report_ref = (document.get("outputs") or {}).get("render_report")
    report_status = None
    if report_ref:
        report = json.loads(store.read_object_bytes(store.read_object_json(report_ref)["file"]))
        report_status = report.get("status")
    if report_status != "pass":
        gaps.append("render_report_not_pass")

    review_status = check_summary(store, document)["status"] if output_ref else "not_evaluated"
    if purpose == "delivery" and review_status != "pass":
        gaps.append("required_review_not_pass")

    return {
        "status": "verified" if not gaps else "blocked",
        "project_id": document["project_id"],
        "revision_id": document["revision_id"],
        "purpose": purpose,
        "file": str(candidate),
        "file_sha256": actual_hash,
        "current_pptx_sha256": expected_hash,
        "page_count": len(document.get("pages") or []),
        "render_report_status": report_status or "not_evaluated",
        "review_status": review_status,
        "pending_tasks": pending,
        "gaps": gaps,
        "evidence_level": "engineering",
        "next_action": None if not gaps else "continue_current_project",
    }
