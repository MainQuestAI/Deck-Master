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
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionEnvelopeError(f"applied marker for action {action_id} is unreadable: {exc}") from exc
    if str(marker.get("status") or "applied") != "applied":
        # a recorded failure must not block a retry of the same action id
        return None
    return marker


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
    current_input_fingerprint: "str | Callable[[], str]",
    targets: dict[str, Path],
    expected_revision: str | None = None,
) -> dict[str, Any]:
    """Commit staged outputs to their live targets — version-guarded, idempotent.

    - stale: the envelope's input fingerprint differs from the current input
      version → the result is rejected (old input cannot overwrite new versions);
    - idempotent: committing the same action_id twice returns the first result;
    - atomic per file: staging copies land next to the target and rename, so
      an interrupted commit leaves the previous version intact.
    """

    root = Path(root).expanduser().resolve()
    # SC-1.1 spec 05 section 5.5: the whole compare-validate-commit-pointer
    # cycle runs under a per-run write lock.
    lock = _acquire_run_lock(root)
    try:
        return _commit_locked(
            root,
            envelope,
            current_input_fingerprint=current_input_fingerprint,
            targets=targets,
            expected_revision=expected_revision,
        )
    finally:
        _release_run_lock(lock)


def _commit_locked(
    root: Path,
    envelope: dict[str, Any],
    *,
    current_input_fingerprint: "str | Callable[[], str]",
    targets: dict[str, Path],
    expected_revision: str | None,
) -> dict[str, Any]:
    # SC-1.1 P1-04: when the caller provides a callable, the fingerprint is
    # recomputed HERE (inside the run lock) — a caller-provided string is
    # never trusted as the current input version.
    if callable(current_input_fingerprint):
        current_input_fingerprint = current_input_fingerprint()
    action_id = str(envelope.get("action_id") or "")
    applied = action_applied(root, action_id)
    if applied:
        return {**applied, "status": "already_applied"}

    _check_action_revision_cas(root, expected_revision)
    _enforce_task_budget(root, envelope)
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

    # SC-1.1 review round 3 (P1-02): activation order is revision snapshot +
    # pointer FIRST, live projections SECOND. Production readers resolve via
    # the committed revision (complete old or complete new, never mixed);
    # fixed paths are compatibility projections with best-effort rollback.
    applied_files: list[str] = []
    for relative, target in targets.items():
        target = Path(target)
        applied_files.append(str(target.relative_to(root)) if target.is_relative_to(root) else str(target))

    parent_revision = read_current_revision(root).get("revision_id", "")
    revision_info = commit_revision_pointer(root, action_id, targets, applied_files, parent_revision=parent_revision)
    revision_id = revision_info["revision_id"]

    _PROJECTION_BACKUP.clear()
    try:
        for relative, target in targets.items():
            source = staging / relative
            target = Path(target)
            _PROJECTION_BACKUP[target] = target.read_bytes() if target.exists() else None
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".action-tmp")
            shutil.copy2(source, tmp)
            tmp.replace(target)
    except Exception:
        _rollback_projections(root)
        raise

    marker = {
        "action_id": action_id,
        "task_id": str(envelope.get("task_id") or ""),
        "scope_pages": list(envelope.get("scope_pages") or []),
        "applied_files": applied_files,
        "revision_id": revision_id,
        "parent_revision_id": revision_info.get("parent_revision_id", ""),
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
            if str(marker.get("task_id") or "") == str(task_id) and str(marker.get("status") or "applied") == "applied":
                # successes count from applied markers; failures are counted
                # solely from the append-only attempt ledger below (no
                # double counting of the overwritten summary marker).
                count += 1
    attempts_root = _actions_root(root) / "attempts"
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
    except (OSError, json.JSONDecodeError):
        return {"revision_id": ""}


def record_action_failure(root: Path | str, *, action_id: str, task_id: str, reason: str) -> dict[str, Any]:
    """Record a failed action attempt — failures consume the task budget."""

    root = Path(root).expanduser().resolve()
    marker = {
        "action_id": str(action_id),
        "task_id": str(task_id),
        "status": "failed",
        "reason": str(reason or ""),
        "recorded_at": _utc_now(),
    }
    # SC-1.1 P1-03: append-only attempt ledger — repeated failures each
    # consume budget; nothing is overwritten.
    attempts_dir = _actions_root(root) / "attempts" / str(action_id)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    (attempts_dir / f"{stamp}.json").write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    marker_path = _actions_root(root) / "applied" / f"{action_id}.json"
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


def _target_run_relative(root: Path, staging_key: str, target: Path) -> str:
    target = Path(target)
    try:
        return str(target.resolve().relative_to(root))
    except ValueError:
        return str(target)


def commit_revision_pointer(
    root: Path,
    action_id: str,
    targets: dict[str, Path],
    applied_files: list[str],
    *,
    parent_revision: str = "",
) -> dict[str, Any]:
    """Write the immutable revision snapshot + atomically swap the pointer."""

    import hashlib
    import shutil as _shutil

    staging = _actions_root(root) / "staging" / action_id
    payload_hash = hashlib.sha256()
    for relative in sorted(targets):
        target = Path(targets[relative])
        try:
            target_rel = str(target.resolve().relative_to(root))
        except ValueError:
            target_rel = str(target)
        # SC-1.1 P1-03: identity binds (target path, content) — the same
        # content written to different pages is a DIFFERENT revision.
        payload_hash.update(target_rel.encode("utf-8"))
        payload_hash.update(hashlib.sha256((staging / relative).read_bytes()).digest())
    revision_id = payload_hash.hexdigest()[:16]
    revisions_dir = root / "build" / "revisions" / revision_id
    if not revisions_dir.exists():
        revisions_dir.mkdir(parents=True)
        for relative in targets:
            # snapshot copies land at the TARGET run-relative path (matching
            # the manifest keys), not the staging key
            destination = revisions_dir / _target_run_relative(root, relative, targets[relative])
            destination.parent.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(staging / relative, destination)
        manifest = {
            "schema_version": "deck_build_revision.v1",
            "revision_id": revision_id,
            "action_id": action_id,
            "parent_revision_id": str(parent_revision),
            "files": {
                _target_run_relative(root, relative, targets[relative]): hashlib.sha256((staging / relative).read_bytes()).hexdigest()
                for relative in targets
            },
            # files NOT touched by this action inherit from the parent chain
            "inherits": [str(applied) for applied in applied_files],
            "committed_at": _utc_now(),
        }
        (revisions_dir / "revision_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pointer = revision_pointer_path(root)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    tmp = pointer.with_suffix(".tmp")
    tmp.write_text(json.dumps({"revision_id": revision_id, "action_id": action_id, "applied_files": applied_files}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(pointer)
    return {"revision_id": revision_id}


def _run_lock_path(root: Path) -> Path:
    return root / "build" / ".action_commit.lock"


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


_PROJECTION_BACKUP: dict[Path, bytes | None] = {}


def _rollback_projections(root: Path) -> None:
    """Restore every live projection touched by a failed commit to its
    pre-commit bytes (SC-1.1 P1-03: never leave mixed versions on disk)."""

    for target, data in list(_PROJECTION_BACKUP.items()):
        if data is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(data)
    _PROJECTION_BACKUP.clear()


def read_revision_state(root: Path | str) -> dict[str, bytes]:
    """Resolve the FULL revision state for readers: current revision files
    overlaid onto the parent chain (files absent from the current revision
    inherit from parents)."""

    root = Path(root).expanduser().resolve()
    current = read_current_revision(root).get("revision_id", "")
    if not current:
        return {}
    revisions_dir = root / "build" / "revisions"
    # SC-1.1 review round 3 (P1-03): walk the parent chain OLDEST-FIRST and
    # let each CHILD overwrite its parents — the current revision's files
    # must win. Files are keyed by final run-relative target paths.
    chain: list[str] = []
    revision_id = current
    hops = 0
    while revision_id and hops < 32:
        manifest_path = revisions_dir / revision_id / "revision_manifest.json"
        if not manifest_path.exists():
            break
        chain.append(revision_id)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        revision_id = str(manifest.get("parent_revision_id") or "")
        hops += 1
    files: dict[str, bytes] = {}
    for revision_id in reversed(chain):  # oldest first, child last (wins)
        rev_dir = revisions_dir / revision_id
        manifest = json.loads((revisions_dir / revision_id / "revision_manifest.json").read_text(encoding="utf-8"))
        for relative in manifest.get("files", {}):
            file_path = rev_dir / relative
            if file_path.exists():
                files[str(relative)] = file_path.read_bytes()
    return files
