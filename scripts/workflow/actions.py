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
import re
import os
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Callable
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
    return _safe_path(root, "workflow/actions")


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
    validate_identifier(action_id, "action_id")
    validate_identifier(task_id, "task_id")
    for page in scope_pages:
        validate_identifier(page, "page_id")
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
    return _safe_path(root, f"workflow/actions/applied/{action_id}.json")


def validate_identifier(value: str, label: str = "identifier") -> str:
    value = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", value):
        raise ActionEnvelopeError(f"unsafe {label}: {value!r}")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute() or ".." in raw.parts or not relative or relative == ".":
        raise ActionEnvelopeError(f"path escapes run: {relative}")
    result = root / raw
    if not result.resolve().is_relative_to(root.resolve()):
        raise ActionEnvelopeError(f"symlink escapes run: {relative}")
    return result


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".write-", delete=False, encoding="utf-8") as handle:
        tmp = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _manifest(root: Path, revision: str) -> dict:
    validate_identifier(revision, "revision_id")
    try:
        value = json.loads(_safe_path(root, f"build/revisions/{revision}/revision_manifest.json").read_text())
    except (OSError, ValueError) as exc:
        raise ActionEnvelopeError(f"unreadable revision {revision}: {exc}") from exc
    return value


def action_applied(root: Path | str, action_id: str) -> dict[str, Any] | None:
    root = Path(root).expanduser().resolve()
    validate_identifier(action_id, "action_id")
    revision = read_current_revision(root).get("revision_id", "")
    if revision:
        receipt = _manifest(root, revision).get("receipts", {}).get(action_id)
        if receipt:
            return receipt
    path = _applied_marker(root, action_id)
    if not path.exists():
        return None
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionEnvelopeError(f"applied marker for action {action_id} is unreadable: {exc}") from exc
    return marker if marker.get("status", "applied") == "applied" else None


def _validate_envelope(root: Path, envelope: dict) -> str:
    action = validate_identifier(envelope.get("action_id"), "action_id")
    validate_identifier(envelope.get("task_id"), "task_id")
    if not envelope.get("scope_pages"):
        raise ActionEnvelopeError("action must declare page scope")
    for page in envelope["scope_pages"]:
        validate_identifier(page, "page_id")
    if envelope.get("run_id", root.name) != root.name:
        raise ActionEnvelopeError("action run identity mismatch")
    if envelope.get("permission") not in {"agent", "migration", "runtime", "user"}:
        raise ActionEnvelopeError("unknown action permission")
    if envelope.get("status") in {"cancelled", "superseded"} or (_actions_root(root) / "cancelled" / f"{action}.json").exists():
        raise ActionStaleError("action is cancelled or superseded")
    return action


def stage_action_result(root: Path | str, envelope: dict[str, Any], result_files: dict[str, str | bytes]) -> Path:
    root = Path(root).expanduser().resolve()
    action = _validate_envelope(root, envelope)
    staging = _safe_path(root, f"workflow/actions/staging/{action}")
    for relative in result_files:
        _safe_path(staging, relative)
    lock = _acquire_run_lock(root)
    try:
        if staging.exists():
            previous = json.loads((staging / "envelope.json").read_text())
            if previous != envelope or any(not (staging / rel).exists() or (staging / rel).read_bytes() != (data.encode() if isinstance(data, str) else data) for rel, data in result_files.items()):
                raise ActionEnvelopeError("action staging conflicts with an existing result")
            return staging
        staging.mkdir(parents=True)
        for relative, data in result_files.items():
            target = _safe_path(staging, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        _atomic_json(staging / "envelope.json", envelope)
        return staging
    finally:
        _release_run_lock(lock)


def _validate_target(root: Path, target: Path, envelope: dict) -> str:
    if ".." in Path(target).parts:
        raise ActionEnvelopeError("target contains traversal")
    target = Path(target).resolve()
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError as exc:
        raise ActionEnvelopeError(f"target outside run: {target}") from exc
    _safe_path(root, relative)
    if envelope.get("permission") == "agent":
        if relative.startswith(("approvals/", "workflow/", "sources/", "build/revisions/")) or relative in {"request.json", "build/route.json", "build/current_revision.json"}:
            raise ActionEnvelopeError("agent output cannot modify runtime policy or approval")
        for prefix in ("page_packages/", "high_density_build/svg/", "high_density_build/page_scenes/", "high_density_build/content_locks/", "high_density_build/blueprints/"):
            if relative.startswith(prefix):
                name = Path(relative).name
                if not any(name == page + ext for page in envelope["scope_pages"] for ext in (".json", ".svg", ".png", ".jpg", ".jpeg", ".scene.json", ".content_lock.json", ".blueprint.json")):
                    raise ActionEnvelopeError("target page is outside action scope")
    return relative


def commit_action_result(root: Path | str, envelope: dict[str, Any], *, current_input_fingerprint: str | Callable[[], str], targets: dict[str, Path], expected_revision: str | None = None, receipt_data: dict | None = None) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    _validate_envelope(root, envelope)
    for target in targets.values():
        _validate_target(root, target, envelope)
    lock = _acquire_run_lock(root)
    try:
        return _commit_locked(root, envelope, current_input_fingerprint=current_input_fingerprint, targets=targets, expected_revision=expected_revision, receipt_data=receipt_data)
    finally:
        _release_run_lock(lock)


def _commit_locked(root: Path, envelope: dict, *, current_input_fingerprint, targets: dict[str, Path], expected_revision: str | None, receipt_data: dict | None = None) -> dict:
    action = _validate_envelope(root, envelope)
    staging = _safe_path(root, f"workflow/actions/staging/{action}")
    applied = action_applied(root, action)
    if applied:
        if applied.get("input_fingerprint") != envelope.get("input_fingerprint") or applied.get("task_id") != envelope.get("task_id"):
            raise ActionEnvelopeError("action already applied with different input identity")
        if staging.exists() and applied.get("output_hashes"):
            for relative, target in targets.items():
                key = _validate_target(root, target, envelope)
                source = _safe_path(staging, relative)
                if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != applied["output_hashes"].get(key):
                    raise ActionEnvelopeError("action already applied with different output")
        return {**applied, "status": "already_applied"}
    _check_action_revision_cas(root, expected_revision)
    _enforce_task_budget(root, envelope)
    current = current_input_fingerprint() if callable(current_input_fingerprint) else current_input_fingerprint
    if envelope.get("input_fingerprint") != current:
        raise ActionStaleError("action input fingerprint is stale; refresh the task")
    if not staging.is_dir():
        raise ActionEnvelopeError(f"no staged result for action {action}")
    staged_envelope = json.loads((staging / "envelope.json").read_text())
    if staged_envelope != envelope:
        raise ActionEnvelopeError("staged envelope identity mismatch")
    files = {}
    for relative, target in targets.items():
        source = _safe_path(staging, relative)
        if not source.is_file():
            raise ActionEnvelopeError(f"staged file missing for action {action}: {relative}")
        files[_validate_target(root, target, envelope)] = source.read_bytes()
    parent = read_current_revision(root).get("revision_id", "")
    state = read_revision_state(root) if parent else _baseline_state(root)
    state.update(files)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(state.items())}
    revision = fingerprint_payload({"parent": parent, "action": action, "files": hashes})[:32]
    marker = {**(receipt_data or {}), "action_id": action, "task_id": envelope["task_id"], "scope_pages": envelope["scope_pages"], "applied_files": list(files), "revision_id": revision, "parent_revision_id": parent, "input_fingerprint": current, "output_hashes": {name: hashes[name] for name in files}, "committed_at": _utc_now(), "status": "applied"}
    receipts = dict(_manifest(root, parent).get("receipts", {})) if parent else {}
    receipts[action] = marker
    manifest = {"schema_version": "deck_build_revision.v2", "revision_id": revision, "parent_revision_id": parent, "files": hashes, "receipts": receipts, "full_snapshot": True, "committed_at": _utc_now()}
    directory = root / "build/revisions"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=directory) as temp:
        temp_root = Path(temp)
        for relative, data in state.items():
            path = _safe_path(temp_root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        _atomic_json(temp_root / "revision_manifest.json", manifest)
        destination = directory / revision
        if destination.exists():
            if _manifest(root, revision) != manifest:
                raise ActionEnvelopeError("revision identity conflict")
        else:
            # directory rename exposes only complete snapshots
            os.rename(temp_root, destination)
    _atomic_json(revision_pointer_path(root), {"revision_id": revision, "action_id": action, "applied_files": list(files)})
    # Commit point passed. Readers and replay use the durable snapshot receipt.
    backup = {}
    try:
        for relative, data in files.items():
            target = _safe_path(root, relative)
            backup[target] = target.read_bytes() if target.exists() else None
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".action-tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        _atomic_json(_applied_marker(root, action), marker)
    except Exception:
        for target, data in backup.items():
            if data is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(data)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    return marker


def _baseline_state(root: Path) -> dict[str, bytes]:
    state = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("build/revisions/", "build/migrations/", "workflow/actions/")) or rel in {"build/current_revision.json", "build/.action_commit.lock"} or path.is_dir():
            continue
        if path.is_symlink():
            raise ActionEnvelopeError(f"snapshot input is a symlink: {rel}")
        if path.is_file():
            state[rel] = path.read_bytes()
    return state


def check_action_budget(root: Path | str, task_id: str, *, max_actions: int) -> dict[str, Any]:
    """Count committed actions for a task; exhausting the budget blocks."""

    root = Path(root).expanduser().resolve()
    applied_dir = _safe_path(root, "workflow/actions/applied")
    successes = set()
    revision = read_current_revision(root).get("revision_id", "")
    if revision:
        successes.update(action for action, receipt in _manifest(root, revision).get("receipts", {}).items() if receipt.get("task_id") == task_id)
    if applied_dir.is_dir():
        for path in applied_dir.glob("*.json"):
            try:
                marker = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(marker.get("task_id") or "") == str(task_id) and str(marker.get("status") or "applied") == "applied":
                # successes count from applied markers; failures are counted
                # solely from the append-only attempt ledger below (no
                # double counting of the overwritten summary marker).
                successes.add(str(marker.get("action_id") or path.stem))
    count = len(successes)
    attempts_root = _safe_path(root, "workflow/actions/attempts")
    if attempts_root.is_dir():
        for attempt_dir in attempts_root.iterdir():
            if not attempt_dir.is_dir():
                continue
            for attempt_file in attempt_dir.glob("*.json"):
                try:
                    entry = json.loads(attempt_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if str(entry.get("task_id") or "") == str(task_id):
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


def revision_pointer_path(root: Path) -> Path:
    return root / "build" / "current_revision.json"


def read_current_revision(root: Path | str) -> dict[str, Any]:
    path = revision_pointer_path(Path(root).expanduser().resolve())
    if not path.exists():
        return {"revision_id": ""}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionEnvelopeError("current revision pointer is unreadable") from exc


def record_action_failure(root: Path | str, *, action_id: str, task_id: str, reason: str) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    _actions_root(root)
    lock = _acquire_run_lock(root)
    try:
        return _record_action_failure_locked(root, action_id=action_id, task_id=task_id, reason=reason)
    finally:
        _release_run_lock(lock)


def _record_action_failure_locked(root: Path | str, *, action_id: str, task_id: str, reason: str) -> dict[str, Any]:
    """Record a failed action attempt — failures consume the task budget."""

    root = Path(root).expanduser().resolve()
    validate_identifier(action_id, "action_id")
    validate_identifier(task_id, "task_id")
    applied = action_applied(root, action_id)
    if applied:
        return applied
    marker = {
        "action_id": str(action_id),
        "task_id": str(task_id),
        "status": "failed",
        "reason": str(reason or ""),
        "recorded_at": _utc_now(),
    }
    # SC-1.1 P1-03: append-only attempt ledger — repeated failures each
    # consume budget; nothing is overwritten.
    attempts_dir = _safe_path(root, f"workflow/actions/attempts/{action_id}")
    attempts_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    (attempts_dir / f"{stamp}.json").write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    marker_path = _safe_path(root, f"workflow/actions/applied/{action_id}.json")
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return marker


def _check_action_revision_cas(root: Path, expected_revision: str | None) -> None:
    if expected_revision is None:
        return
    current = read_current_revision(root).get("revision_id", "")
    if str(expected_revision) != current:
        raise ActionStaleError(
            f"expected revision {expected_revision!r} but the current committed revision is {current!r}; "
            "the action was produced against a superseded revision"
        )


def _run_lock_path(root: Path) -> Path:
    return _safe_path(root, "build/.action_commit.lock")


def _acquire_run_lock(root: Path):
    lock_path = _run_lock_path(root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    held = False
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        held = True
    except ImportError:  # pragma: no cover - non-POSIX best-effort fallback
        pass
    handle._deck_lock_held = held  # type: ignore[attr-defined]
    return handle


def _release_run_lock(handle) -> None:
    try:
        import fcntl

        if getattr(handle, "_deck_lock_held", False):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _enforce_task_budget(root: Path, envelope: dict[str, Any]) -> None:
    """SC-1.1 P1-03: the commit path enforces the task budget (committed
    attempts AND failures both count); exhaustion blocks the commit."""

    budget = envelope.get("budget") if isinstance(envelope.get("budget"), dict) else {}
    max_actions = budget.get("max_actions")
    if not max_actions:
        return
    usage = check_action_budget(root, str(envelope.get("task_id") or ""), max_actions=int(max_actions))
    if usage["exhausted"]:
        raise ActionBudgetExhaustedError(
            f"task {envelope.get('task_id')!r} budget exhausted "
            f"({usage['used']}/{usage['max_actions']} attempts including failures); the commit is blocked"
        )


def read_revision_state(root: Path | str, revision: str | None = None) -> dict[str, bytes]:
    root = Path(root).expanduser().resolve()
    current = read_current_revision(root).get("revision_id", "") if revision is None else revision
    if not current:
        return {}
    chain, seen = [], set()
    while current:
        if current in seen:
            raise ActionEnvelopeError("revision parent cycle")
        seen.add(current)
        manifest = _manifest(root, current)
        chain.append((current, manifest))
        if manifest.get("full_snapshot"):
            break
        current = manifest.get("parent_revision_id", "")
    files = {}
    for revision_id, manifest in reversed(chain):
        for relative, expected in manifest.get("files", {}).items():
            data = _safe_path(root / "build/revisions" / revision_id, relative).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ActionEnvelopeError(f"revision file hash mismatch: {relative}")
            files[relative] = data
    return files


_READ_REVISION: ContextVar[dict] = ContextVar("deck_revision", default={})


@contextmanager
def revision_read(root: Path | str):
    root = Path(root).expanduser().resolve()
    active = _READ_REVISION.get()
    if str(root) in active:
        yield active[str(root)]
        return
    revision = read_current_revision(root).get("revision_id", "")
    token = _READ_REVISION.set({**active, str(root): revision})
    try:
        yield revision
    finally:
        _READ_REVISION.reset(token)


def revision_input_path(root: Path | str, path: Path | str) -> Path:
    root = Path(root).expanduser().resolve()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    relative = path.resolve().relative_to(root).as_posix()
    revision = _READ_REVISION.get().get(str(root))
    if revision is None or not revision:
        return _safe_path(root, relative)
    return _safe_path(root / "build/revisions" / revision, relative)


def active_input_path(path: Path) -> Path:
    """Read-only loader hook; only redirects within an explicitly pinned scope."""
    for root in _READ_REVISION.get():
        if path.resolve().is_relative_to(Path(root)):
            relative = path.resolve().relative_to(Path(root)).as_posix()
            inputs = ("page_packages", "assets", "high_density_build/svg", "high_density_build/content_locks", "high_density_build/page_scenes", "high_density_build/blueprints")
            if relative in {"request.json", "narrative_plan.json", "solution_model.json", "diagram_views.json", "style_lock.json", "context_manifest.json", "page_tasks.json"} or any(relative == prefix or relative.startswith(prefix + "/") for prefix in inputs):
                return revision_input_path(root, path)
    return path


def recover_projections(root: Path | str) -> dict:
    root = Path(root).expanduser().resolve()
    lock = _acquire_run_lock(root)
    try:
        revision = read_current_revision(root).get("revision_id", "")
        for relative, data in read_revision_state(root).items():
            target = _safe_path(root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".recover-tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        if revision:
            for action, receipt in _manifest(root, revision).get("receipts", {}).items():
                _atomic_json(_applied_marker(root, validate_identifier(action)), receipt)
        return {"status": "recovered", "revision_id": revision}
    finally:
        _release_run_lock(lock)


def restore_revision(root: Path | str, *, expected_revision: str, revision_id: str) -> dict:
    root = Path(root).expanduser().resolve()
    lock = _acquire_run_lock(root)
    try:
        _check_action_revision_cas(root, expected_revision)
        if revision_id:
            read_revision_state(root, revision_id)  # verify complete content before activation
        _atomic_json(revision_pointer_path(root), {"revision_id": revision_id})
        return {"status": "restored", "revision_id": revision_id}
    finally:
        _release_run_lock(lock)
