"""Audited per-task native budget ceilings; actors are local declarations."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from native_pptx.contracts import ContractError, SCHEMA_DIR, read_json
from workflow.actions import (
    ActionEnvelopeError, ActionStaleError, action_applied, check_action_budget, fingerprint_payload,
    revision_input_path, revision_read, validate_identifier,
)

LIMITS_FIELD = "native_task_budget_limits"
AUTHORIZATIONS_FIELD = "native_task_budget_authorizations"
KINDS = {"imagegen", "reconstruct", "svg"}


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{label} must be a string")
    try:
        return validate_identifier(value, label)
    except ActionEnvelopeError as exc:
        raise ContractError(str(exc)) from exc


def _limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 20:
        raise ContractError("native task budget must be an integer between 1 and 20")
    return value


def _policy(request: dict) -> tuple[int, dict, list]:
    default = _limit(request.get("native_max_actions", 3))
    limits = request.get(LIMITS_FIELD, {})
    history = request.get(AUTHORIZATIONS_FIELD, [])
    if not isinstance(limits, dict) or not isinstance(history, list):
        raise ContractError("native task budget policy must contain a limits object and authorization list")
    for task_id, value in limits.items():
        _identifier(task_id, "task_id")
        if not any(task_id.startswith(f"native_{kind}_") for kind in KINDS):
            raise ContractError("native task budget key is not a native task")
        _limit(value)
    if any(not isinstance(record, dict) for record in history):
        raise ContractError("invalid native budget authorization history")
    authorized = {}
    for record in history:
        if (record.get("schema_version") != "deck_native_task_budget_authorization.v1"
                or record.get("actor_authenticated") is not False
                or not isinstance(record.get("changes"), list)):
            raise ContractError("invalid native budget authorization history")
        for change in record["changes"]:
            if not isinstance(change, dict) or not isinstance(change.get("task_id"), str):
                raise ContractError("invalid native budget authorization change")
            authorized[change["task_id"]] = _limit(change.get("max_actions"))
    if any(authorized.get(task_id) != limit for task_id, limit in limits.items()):
        raise ContractError("native task budget limit lacks matching authorization history")
    return default, limits, history


def native_task_budget_limit(request: dict, task_id: str) -> int:
    """Resolve the next dispatch ceiling without altering issued actions."""
    default, limits, _ = _policy(request)
    return limits.get(task_id, default)


def _task(root: Path, task_id: str, approved_ids: set[str]) -> dict:
    from workflow.actions import _safe_path

    _identifier(task_id, "task_id")
    path = _safe_path(root, f"build/native_tasks/{task_id}.json")
    if not path.is_file():
        raise ContractError("budget target must be a Runtime-issued task in this run")
    task = read_json(path)
    page = task.get("page_id")
    kind = task.get("kind")
    if (not isinstance(page, str) or not isinstance(kind, str)
            or page not in approved_ids or kind not in KINDS
            or task_id != f"native_{kind}_{page}"
            or task.get("task_id") != task_id or task.get("run_id") != root.name
            or task.get("scope_pages") != [page]):
        raise ContractError("budget task does not belong to an approved page in this run")
    action = _identifier(task.get("action_id"), "action_id")
    issued = _safe_path(root, f"build/native_tasks/issued/{action}.json")
    if not issued.is_file() or read_json(issued) != task:
        raise ContractError("budget task does not match its immutable issued action")
    _limit((task.get("budget") or {}).get("max_actions"))
    return task


def _snapshot(root: Path, task_ids: list[str]) -> tuple[dict, dict, str]:
    from build.build_route import load_persisted_route
    from build.native_engine import _approved_packages

    with revision_read(root, fresh=True) as revision:
        request = read_json(revision_input_path(root, root / "request.json"))
        if request.get("run_id") != root.name or load_persisted_route(root).get("engine_id") != "deck_native":
            raise ContractError("native task budgets require this run's persisted native route")
        default, limits, _ = _policy(request)
        ids = {p["page_id"] for p in _approved_packages(root)}
        entries = []
        for task_id in task_ids:
            task = _task(root, task_id, ids)
            limit = limits.get(task_id, default)
            usage = check_action_budget(root, task_id, max_actions=limit)
            entries.append({
                "task_id": task_id, "page_id": task["page_id"], "kind": task["kind"],
                "max_actions": limit, "default_max_actions": default,
                "issued_action_id": task["action_id"],
                "issued_max_actions": task["budget"]["max_actions"],
                "used": usage["used"], "remaining": usage["remaining"], "exhausted": usage["exhausted"],
            })
        return request, {"run_id": root.name, "revision_id": revision, "tasks": entries}, revision


def read_native_task_budgets(run_dir: str | Path, *, task_ids: list[str]) -> dict:
    from workflow.actions import _acquire_run_lock, _release_run_lock

    root = Path(run_dir).expanduser().resolve()
    if not isinstance(task_ids, list) or not task_ids:
        raise ContractError("explicit unique native task IDs are required")
    for task_id in task_ids:
        _identifier(task_id, "task_id")
    if len(set(task_ids)) != len(task_ids):
        raise ContractError("explicit unique native task IDs are required")
    lock = _acquire_run_lock(root)
    try:
        return _snapshot(root, sorted(task_ids))[1]
    finally:
        _release_run_lock(lock)


def set_native_task_budgets(
    run_dir: str | Path, *, limits: dict[str, int], expected_revision: str,
    reason: str, actor: dict[str, str],
) -> dict:
    """Set exact task ceilings atomically; never reset use or rewrite tasks."""
    from jsonschema import Draft202012Validator, FormatChecker
    from workflow.actions import create_action_envelope, stage_action_result, commit_action_result

    root = Path(run_dir).expanduser().resolve()
    if not isinstance(limits, dict) or not limits:
        raise ContractError("explicit native task ceilings are required")
    for task_id, value in limits.items():
        _identifier(task_id, "task_id")
        _limit(value)
    limits = dict(sorted(limits.items()))
    if not isinstance(expected_revision, str):
        raise ContractError("explicit source revision is required")
    if expected_revision:
        _identifier(expected_revision, "source revision")
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError("native budget authorization requires a reason")
    if (not isinstance(actor, dict) or actor.get("role") != "user"
            or not isinstance(actor.get("id"), str) or not actor["id"].strip()):
        raise ContractError("explicit locally declared user actor is required; identity is not authenticated")
    reason = reason.strip()
    actor = {"id": actor["id"].strip(), "role": "user"}
    identity = {"source_revision": expected_revision, "requested_limits": limits, "reason": reason, "actor": actor}
    authorization_id = "native_budget_" + fingerprint_payload(identity)[:32]
    request, before, revision = _snapshot(root, list(limits))
    default, current_limits, history = _policy(request)
    for existing in history:
        if existing.get("authorization_id") == authorization_id:
            if any(existing.get(key) != value for key, value in identity.items()):
                raise ContractError("native budget authorization identity conflict")
            receipt = action_applied(root, existing.get("action_id", ""))
            if not receipt:
                raise ContractError("native budget authorization lacks its committed receipt")
            return {"status": "already_applied", "authorization": existing, "receipt": receipt,
                    "current": read_native_task_budgets(root, task_ids=list(limits))}
    if revision != expected_revision:
        raise ActionStaleError("native budget source revision changed; read current budgets again")
    changes = []
    for entry in before["tasks"]:
        target = limits[entry["task_id"]]
        if target < entry["max_actions"]:
            raise ContractError("native budget authorization can only retain or increase the current ceiling")
        if target != entry["max_actions"]:
            changes.append({key: entry[key] for key in ("task_id", "page_id", "kind")})
            changes[-1].update(previous_max_actions=entry["max_actions"], max_actions=target,
                               used_at_authorization=entry["used"])
    if not changes:
        return {"status": "unchanged", "current": read_native_task_budgets(root, task_ids=list(limits))}
    action_id = "native_budget_commit_" + uuid4().hex
    authorization = {
        "schema_version": "deck_native_task_budget_authorization.v1", "run_id": root.name,
        "authorization_id": authorization_id, "action_id": action_id, **identity,
        "actor_authenticated": False, "default_max_actions": default,
        "changes": changes, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    schema = read_json(SCHEMA_DIR / "native-task-budget-authorization.v1.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(authorization)
    changed_limits = {change["task_id"]: change["max_actions"] for change in changes}
    updated = {**request, LIMITS_FIELD: {**current_limits, **changed_limits}, AUTHORIZATIONS_FIELD: [*history, authorization]}
    _policy(updated)
    token = fingerprint_payload({"revision": revision, "request": request, "tasks": before["tasks"]})
    envelope = create_action_envelope(
        action_id=action_id, task_id="native_budget_authorization", permission="runtime",
        scope_pages=sorted({item["page_id"] for item in changes}), input_fingerprint=token,
    )
    stage_action_result(root, envelope, {"request.json": json.dumps(updated, ensure_ascii=False, indent=2) + "\n"})

    def locked_check():
        current_request, now, current_revision = _snapshot(root, list(limits))
        actual = fingerprint_payload({"revision": current_revision, "request": current_request, "tasks": now["tasks"]})
        if actual != token:
            raise ActionStaleError("native budget inputs, issued action or used budget changed; read current budgets again")
        return token

    receipt = commit_action_result(
        root, envelope, expected_revision=expected_revision, current_input_fingerprint=locked_check,
        targets={"request.json": root / "request.json"},
        receipt_data={"native_budget_authorization_id": authorization_id},
    )
    return {"status": "applied", "authorization": authorization, "receipt": receipt,
            "current": read_native_task_budgets(root, task_ids=list(limits))}
