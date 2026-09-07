"""SC-1 C2: stage action envelopes — idempotent, version-guarded, budgeted.

Stage-level agent actions (generation results, repairs, imports) travel in an
envelope that fixes the input version they were produced against and the
pages they are allowed to touch. The runtime applies results through
staging + commit so an interrupted multi-file action keeps the previous
version, a late result for a superseded input can never overwrite the new
version, replaying the same action id is a no-op, and an exhausted budget
blocks instead of silently continuing.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENVELOPE_SCHEMA_VERSION = "deck_stage_action.v1"


class ActionEnvelopeError(RuntimeError):
    pass


class ActionStaleError(ActionEnvelopeError):
    """The result was produced against an input version that is no longer current."""


class ActionBudgetExhaustedError(ActionEnvelopeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _actions_root(root: Path) -> Path:
    return root / "workflow" / "actions"


def fingerprint_payload(payload: dict[str, Any] | list[Any] | str) -> str:
    if isinstance(payload, str):
        blob = payload.encode("utf-8")
    else:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def create_action_envelope(
    *,
    action_id: str,
    task_id: str,
    scope_pages: list[str],
    permission: str = "agent",
    input_fingerprint: str,
    budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not str(action_id or "").strip():
        raise ValueError("action_id is required")
    if not scope_pages:
        raise ValueError("an action envelope must declare its page scope; unscoped actions are not accepted")
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "action_id": str(action_id),
        "task_id": str(task_id or ""),
        "scope_pages": [str(page) for page in scope_pages],
        "permission": str(permission),
        "input_fingerprint": str(input_fingerprint),
        "budget": dict(budget or {}),
        "created_at": _utc_now(),
    }


def _applied_marker(root: Path, action_id: str) -> Path:
    return _actions_root(root) / "applied" / f"{action_id}.json"


def action_applied(root: Path | str, action_id: str) -> dict[str, Any] | None:
    path = _applied_marker(Path(root).expanduser().resolve(), str(action_id))
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"action_id": action_id, "status": "applied_marker_unreadable"}


def stage_action_result(
    root: Path | str,
    envelope: dict[str, Any],
    result_files: dict[str, str],
) -> Path:
    """Write action outputs into a staging directory (never the live paths)."""

    root = Path(root).expanduser().resolve()
    action_id = str(envelope.get("action_id") or "")
    staging = _actions_root(root) / "staging" / action_id
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for relative, content in result_files.items():
        target = staging / relative
        if not str(relative).strip() or ".." in Path(relative).parts or Path(relative).is_absolute():
            raise ActionEnvelopeError(f"staging path escapes the action staging dir: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (staging / "envelope.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return staging


def commit_action_result(
    root: Path | str,
    envelope: dict[str, Any],
    *,
    current_input_fingerprint: str,
    targets: dict[str, Path],
) -> dict[str, Any]:
    """Commit staged outputs to their live targets — version-guarded, idempotent.

    - stale: the envelope's input fingerprint differs from the current input
      version → the result is rejected (old input cannot overwrite new versions);
    - idempotent: committing the same action_id twice returns the first result;
    - atomic per file: staging copies land next to the target and rename, so
      an interrupted commit leaves the previous version intact.
    """

    root = Path(root).expanduser().resolve()
    action_id = str(envelope.get("action_id") or "")
    applied = action_applied(root, action_id)
    if applied:
        return {**applied, "status": "already_applied"}

    if str(envelope.get("input_fingerprint") or "") != str(current_input_fingerprint or ""):
        raise ActionStaleError(
            f"action {action_id} was produced against input {envelope.get('input_fingerprint')!r} "
            f"but the current input is {current_input_fingerprint!r}; refresh the task instead of overwriting"
        )

    staging = _actions_root(root) / "staging" / action_id
    if not staging.is_dir():
        raise ActionEnvelopeError(f"no staged result for action {action_id}; stage before commit")

    # Validate every declared target first: an interrupted or partial staging
    # must keep the previous live versions untouched (all-or-nothing).
    for relative in targets:
        if not (staging / relative).is_file():
            raise ActionEnvelopeError(f"staged file missing for action {action_id}: {relative}")

    applied_files: list[str] = []
    for relative, target in targets.items():
        source = staging / relative
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".action-tmp")
        shutil.copy2(source, tmp)
        tmp.replace(target)
        applied_files.append(str(target.relative_to(root)) if target.is_relative_to(root) else str(target))

    marker = {
        "action_id": action_id,
        "task_id": str(envelope.get("task_id") or ""),
        "scope_pages": list(envelope.get("scope_pages") or []),
        "applied_files": applied_files,
        "committed_at": _utc_now(),
        "input_fingerprint": str(envelope.get("input_fingerprint") or ""),
        "status": "applied",
    }
    marker_path = _applied_marker(root, action_id)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(staging, ignore_errors=True)
    return marker


def check_action_budget(root: Path | str, task_id: str, *, max_actions: int) -> dict[str, Any]:
    """Count committed actions for a task; exhausting the budget blocks."""

    root = Path(root).expanduser().resolve()
    applied_dir = _actions_root(root) / "applied"
    count = 0
    if applied_dir.is_dir():
        for path in applied_dir.glob("*.json"):
            try:
                marker = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(marker.get("task_id") or "") == str(task_id):
                count += 1
    remaining = max(0, max(1, int(max_actions)) - count)
    return {
        "task_id": str(task_id),
        "used": count,
        "max_actions": int(max_actions),
        "remaining": remaining,
        "exhausted": remaining <= 0,
    }


def record_targeted_repair(
    root: Path | str,
    *,
    repair_id: str,
    finding_ids: list[str],
    scope_pages: list[str],
    reason: str = "",
) -> dict[str, Any]:
    """Register a targeted repair: only declared pages/finding ids are in
    scope; affected reviews must re-run before the result can be current."""

    if not finding_ids:
        raise ValueError("a targeted repair must name the findings it repairs")
    root = Path(root).expanduser().resolve()
    repair = {
        "schema_version": "deck_targeted_repair.v1",
        "repair_id": str(repair_id),
        "finding_ids": [str(item) for item in finding_ids],
        "scope_pages": [str(item) for item in scope_pages],
        "reason": str(reason or ""),
        "requires_rereview": {
            "scope": "affected_only",
            "note": "re-review covers only the repaired pages and their dependents; the rest of the approval stands",
        },
        "created_at": _utc_now(),
        "status": "open",
    }
    repairs_dir = root / "workflow" / "repairs"
    repairs_dir.mkdir(parents=True, exist_ok=True)
    (repairs_dir / f"{repair_id}.json").write_text(json.dumps(repair, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return repair
