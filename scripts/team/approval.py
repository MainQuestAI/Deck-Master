from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def team_dir(workspace_dir: str | Path) -> Path:
    return Path(workspace_dir) / "team"


def submit_approval(
    workspace_dir: str | Path,
    run_id: str,
    submitted_by: str,
    *,
    notes: str = "",
) -> dict[str, Any]:
    """提交 final export 审批。"""
    d = team_dir(workspace_dir)
    d.mkdir(parents=True, exist_ok=True)

    approval_id = f"approval_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    request = {
        "approval_id": approval_id,
        "run_id": run_id,
        "submitted_by": submitted_by,
        "submitted_at": utc_now(),
        "status": "pending",
        "notes": notes,
    }

    # 追加到 JSONL
    path = d / "approval_requests.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(request, ensure_ascii=False) + "\n")

    # 更新 approval_flows.json
    flows = _load_flows(d)
    flows[approval_id] = request
    _save_flows(d, flows)

    _append_audit(workspace_dir, "approval.submitted", submitted_by, {"approval_id": approval_id, "run_id": run_id})
    return request


def approve(
    workspace_dir: str | Path,
    approval_id: str,
    approver: str,
    *,
    notes: str = "",
) -> dict[str, Any]:
    """批准审批。"""
    d = team_dir(workspace_dir)
    flows = _load_flows(d)

    if approval_id not in flows:
        raise ValueError(f"Approval not found: {approval_id}")

    flow = flows[approval_id]
    if flow["status"] != "pending":
        raise ValueError(f"Approval {approval_id} is not pending (status: {flow['status']})")

    flow["status"] = "approved"
    flow["approved_by"] = approver
    flow["approved_at"] = utc_now()
    flow["approval_notes"] = notes
    _save_flows(d, flows)

    _append_audit(workspace_dir, "approval.approved", approver, {"approval_id": approval_id})
    return flow


def reject(
    workspace_dir: str | Path,
    approval_id: str,
    rejecter: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    """拒绝审批。"""
    d = team_dir(workspace_dir)
    flows = _load_flows(d)

    if approval_id not in flows:
        raise ValueError(f"Approval not found: {approval_id}")

    flow = flows[approval_id]
    flow["status"] = "rejected"
    flow["rejected_by"] = rejecter
    flow["rejected_at"] = utc_now()
    flow["rejection_reason"] = reason
    _save_flows(d, flows)

    _append_audit(workspace_dir, "approval.rejected", rejecter, {"approval_id": approval_id, "reason": reason})
    return flow


def is_approved(workspace_dir: str | Path, run_id: str) -> bool:
    """检查 run 是否已通过审批。"""
    d = team_dir(workspace_dir)
    flows = _load_flows(d)
    return any(
        f.get("run_id") == run_id and f.get("status") == "approved"
        for f in flows.values()
    )


def list_approvals(workspace_dir: str | Path) -> list[dict[str, Any]]:
    d = team_dir(workspace_dir)
    flows = _load_flows(d)
    return list(flows.values())


def _load_flows(d: Path) -> dict:
    path = d / "approval_flows.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_flows(d: Path, flows: dict) -> None:
    path = d / "approval_flows.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(flows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_audit(workspace_dir: str | Path, action: str, user_id: str, data: dict) -> None:
    d = team_dir(workspace_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "audit_log.jsonl"
    entry = {"timestamp": utc_now(), "action": action, "user_id": user_id, **data}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
