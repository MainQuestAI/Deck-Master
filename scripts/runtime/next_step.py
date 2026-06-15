from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.setup_status import setup_status
from runtime.run_state import (
    REQUEST_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    CLAIM_MAP_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    SOURCING_PLAN_NAME,
    PREVIEW_MANIFEST_NAME,
)


SCHEMA_VERSION = "deck_next_step.v1"
DRAFT_GATE_FILES = ("draft_v2_gate.json", "draft_gate.json")
BLOCKING_STATUSES = {"rework_required"}

# 状态优先级（从最缺到最完整）
STEP_CHECKS: list[tuple[str, str, str]] = [
    # (artifact_name, status_if_missing, next_command_template)
    (REQUEST_NAME, "needs_request", "python3 scripts/deck_master.py start-conversation --runs-dir {runs_dir} --run-id {run_id} ..."),
    (CONTEXT_MANIFEST_NAME, "needs_context", "python3 scripts/deck_master.py start-conversation --runs-dir {runs_dir} --run-id {run_id} ..."),
    (DECK_BRIEF_NAME, "needs_brief", "python3 scripts/deck_master.py build-brief --runs-dir {runs_dir} --run-id {run_id}"),
    (CLAIM_MAP_NAME, "needs_claim_map", "python3 scripts/deck_master.py build-claim-map --runs-dir {runs_dir} --run-id {run_id}"),
    (NARRATIVE_PLAN_NAME, "needs_narrative_plan", "python3 scripts/deck_master.py plan --runs-dir {runs_dir} --run-id {run_id} ..."),
    (PAGE_TASKS_NAME, "needs_page_tasks", "（narrative plan 完成后自动生成 page tasks）"),
    (SOURCING_PLAN_NAME, "needs_sourcing", "python3 scripts/deck_master.py decide-sourcing --runs-dir {runs_dir} --run-id {run_id}"),
    (PREVIEW_MANIFEST_NAME, "needs_preview", "python3 scripts/deck_master.py build-preview --runs-dir {runs_dir} --run-id {run_id}"),
]


def _read_draft_gate(root: Path) -> dict[str, Any] | None:
    quality_dir = root / "quality_reports"
    for filename in DRAFT_GATE_FILES:
        path = quality_dir / filename
        if not path.exists():
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "status": "invalid",
                "blocks_delivery": True,
                "blocking_issue": f"Invalid quality report JSON: {filename}",
            }
        if isinstance(report, dict):
            report["_report_file"] = filename
            return report
    return None


def _draft_gate_blocks(report: dict[str, Any]) -> bool:
    status = str(report.get("status", "")).lower()
    return bool(report.get("blocks_delivery")) or status in BLOCKING_STATUSES


def _with_setup_hint(result: dict[str, Any], workspace: str | None = None) -> dict[str, Any]:
    setup = setup_status(workspace=workspace, write_event=False)
    result["setup_status"] = setup.get("status", "")
    result["setup_next_command"] = setup.get("next_command", "")
    if setup.get("status") != "ready":
        result.setdefault("blocking_issues", []).append(
            f"Setup status is {setup.get('status')}. Run: {setup.get('next_command')}"
        )
    return result


def resolve_next_step(run_dir: str | Path) -> dict[str, Any]:
    """分析 run 目录，返回下一步操作建议。"""
    root = Path(run_dir).expanduser().resolve()
    run_id = root.name

    # 尝试从 request.json 获取 run_id
    request_path = root / REQUEST_NAME
    if request_path.exists():
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            run_id = request.get("run_id", run_id)
            workspace = str(request.get("workspace") or "") or None
        except (json.JSONDecodeError, KeyError):
            workspace = None
    else:
        workspace = None

    runs_dir = str(root.parent)
    missing_artifacts: list[str] = []
    blocking_issues: list[str] = []

    for artifact_name, status, command_template in STEP_CHECKS:
        if not (root / artifact_name).exists():
            missing_artifacts.append(artifact_name)
            next_command = command_template.format(runs_dir=runs_dir, run_id=run_id)
            return _with_setup_hint({
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "status": status,
                "next_command": next_command,
                "missing_artifacts": missing_artifacts,
                "blocking_issues": blocking_issues,
            }, workspace)

    draft_gate = _read_draft_gate(root)
    if draft_gate is None:
        return _with_setup_hint({
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "needs_draft_gate",
            "next_command": f"python3 scripts/deck_master.py quality-gate draft --runs-dir {runs_dir} --run-id {run_id}",
            "missing_artifacts": [],
            "blocking_issues": [],
        }, workspace)

    if _draft_gate_blocks(draft_gate):
        return _with_setup_hint({
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "needs_quality_review",
            "next_command": f"python3 scripts/deck_master.py quality-gate {str(draft_gate.get('_report_file', 'draft_gate.json')).removesuffix('_gate.json')} --runs-dir {runs_dir} --run-id {run_id}",
            "missing_artifacts": [],
            "blocking_issues": [draft_gate.get("blocking_issue") or "Draft gate blocks client export."],
        }, workspace)

    # 检查是否有 approved 页面可 export
    try:
        manifest_path = root / PREVIEW_MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = manifest.get("pages", [])
        approved_pages = [p for p in pages if isinstance(p, dict) and p.get("decision") == "approved"]
        if approved_pages:
            return _with_setup_hint({
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "status": "ready_to_export",
                "next_command": f"python3 scripts/deck_master.py export --runs-dir {runs_dir} --run-id {run_id}",
                "missing_artifacts": [],
                "blocking_issues": [],
                "approved_pages": len(approved_pages),
            }, workspace)
        review_pages = [
            p
            for p in pages
            if isinstance(p, dict) and p.get("decision") in {"needs_review", "keep", "replace", "pending"}
        ]
        if review_pages:
            return _with_setup_hint({
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "status": "needs_page_review",
                "next_command": f"python3 scripts/preview/server.py --runs-dir {runs_dir} --run-id {run_id}",
                "missing_artifacts": [],
                "blocking_issues": [],
                "pending_pages": len(review_pages),
            }, workspace)
    except (json.JSONDecodeError, FileNotFoundError):
        pass

    return _with_setup_hint({
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "complete",
        "next_command": "",
        "missing_artifacts": [],
        "blocking_issues": [],
    }, workspace)
