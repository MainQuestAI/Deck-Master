from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "deck_final_artifact_approval.v1"
APPROVAL_PATH = Path("final_artifact_approval.json")
FINAL_READINESS_PATH = Path("delivery") / "final_readiness.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_final_artifact_approval(
    run_dir: str | Path,
    approval: dict[str, Any],
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    readiness = _read_json(root / FINAL_READINESS_PATH)
    final_artifact = readiness.get("final_artifact") if isinstance(readiness.get("final_artifact"), dict) else {}
    artifact_path = str(final_artifact.get("path") or "").strip()
    artifact_hash = str(final_artifact.get("hash") or "").strip()
    actor = approval.get("actor") if isinstance(approval.get("actor"), dict) else {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(approval.get("run_id") or root.name),
        "run_dir_name": root.name,
        "approval_id": str(approval.get("approval_id") or ""),
        "handoff_id": str(approval.get("handoff_id") or ""),
        "decision": str(approval.get("decision") or ""),
        "approver": {
            "id": str(actor.get("id") or ""),
            "role": str(actor.get("role") or ""),
        },
        "approved_at": str(approval.get("decided_at") or ""),
        "final_artifact": {"path": artifact_path, "sha256": artifact_hash},
        "readiness": {
            "path": str(FINAL_READINESS_PATH),
            "computed_at": str(readiness.get("computed_at") or ""),
            "ready": bool(readiness.get("ready")),
        },
        "workflow_binding": approval.get("artifact_binding") if isinstance(approval.get("artifact_binding"), dict) else {},
    }
    output = root / APPROVAL_PATH
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def final_approval_clearance(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    payload = _read_json(root / APPROVAL_PATH)
    if not payload:
        return {"ready": False, "reason": "Final artifact approval is missing.", "path": str(APPROVAL_PATH)}
    if payload.get("schema_version") != SCHEMA_VERSION:
        return {"ready": False, "reason": "Final artifact approval schema is invalid.", "path": str(APPROVAL_PATH)}
    if payload.get("decision") != "approved":
        return {"ready": False, "reason": "Final artifact approval is not approved.", "path": str(APPROVAL_PATH)}
    approval_id = str(payload.get("approval_id") or "").strip()
    workflow_approval = _read_json(root / "workflow" / "approvals" / f"{approval_id}.json")
    if not workflow_approval or workflow_approval.get("decision") != "approved":
        return {"ready": False, "reason": "Final artifact approval has no live workflow approval.", "path": str(APPROVAL_PATH)}
    if workflow_approval.get("handoff_id") != payload.get("handoff_id") or workflow_approval.get("to_stage") != "client_export":
        return {"ready": False, "reason": "Final artifact approval workflow binding is invalid.", "path": str(APPROVAL_PATH)}
    if str(payload.get("run_id") or "") not in {root.name, str(_read_json(root / "request.json").get("run_id") or root.name)}:
        return {"ready": False, "reason": "Final artifact approval belongs to a different run.", "path": str(APPROVAL_PATH)}
    approver = payload.get("approver") if isinstance(payload.get("approver"), dict) else {}
    if not str(approver.get("id") or "").strip() or not str(payload.get("approved_at") or "").strip():
        return {"ready": False, "reason": "Final artifact approval has no approver or approval time.", "path": str(APPROVAL_PATH)}
    artifact = payload.get("final_artifact") if isinstance(payload.get("final_artifact"), dict) else {}
    rel = str(artifact.get("path") or "").strip()
    expected_hash = str(artifact.get("sha256") or "").strip()
    if not rel or not expected_hash:
        return {"ready": False, "reason": "Final artifact approval has no artifact binding.", "path": str(APPROVAL_PATH)}
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return {"ready": False, "reason": "Final artifact approval path is outside the run directory.", "path": str(APPROVAL_PATH)}
    if not candidate.is_file():
        return {"ready": False, "reason": "Approved final artifact is missing.", "path": str(APPROVAL_PATH)}
    if _sha256(candidate) != expected_hash:
        return {"ready": False, "reason": "Final artifact approval is stale because the artifact changed.", "path": str(APPROVAL_PATH)}
    readiness = _read_json(root / FINAL_READINESS_PATH)
    current = readiness.get("final_artifact") if isinstance(readiness.get("final_artifact"), dict) else {}
    if not readiness.get("ready") or str(current.get("path") or "") != rel or str(current.get("hash") or "") != expected_hash:
        return {"ready": False, "reason": "Final artifact approval no longer matches final readiness.", "path": str(APPROVAL_PATH)}
    return {"ready": True, "reason": "", "path": str(APPROVAL_PATH), "approval": payload}


def invalidate_final_artifact_approval(run_dir: str | Path, approval_id: str) -> None:
    root = Path(run_dir).expanduser().resolve()
    payload = _read_json(root / APPROVAL_PATH)
    if str(payload.get("approval_id") or "") == approval_id:
        (root / APPROVAL_PATH).unlink(missing_ok=True)
