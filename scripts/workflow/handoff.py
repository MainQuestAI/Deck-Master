"""Skill Handoff Runtime (A3).

Append-only, auditable stage-transition handoffs. One handoff per file under
``workflow/handoffs/<handoff_id>.json``; ``workflow/current_handoff.json`` is a
*projection* of the most recent accepted/consumed handoff, never the truth
source.

Lifecycle::

    draft -> awaiting_approval / accepted -> consumed

Anomalous::

    rejected / stale / superseded / cancelled

Key invariants (A3 must-implement):

* ``prepare`` refuses when exit validation fails.
* Same output fingerprint is idempotent (returns the existing handoff).
* Upstream change supersedes the prior handoff for the same transition, which
  is retained (never deleted).
* ``current_handoff`` is a projection only.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from skills.manifest import Registry, load_registry
from workflow import fingerprint as fp
from workflow.validator import required_outputs, resolve_artifact_files, validate_exit

SCHEMA_VERSION = "deck_skill_handoff.v1"
HANDOFFS_DIRNAME = "workflow/handoffs"
CURRENT_PROJECTION = "workflow/current_handoff.json"
LOCK_NAME = ".handoff.lock"

DRAFT = "draft"
AWAITING_APPROVAL = "awaiting_approval"
ACCEPTED = "accepted"
CONSUMED = "consumed"
REJECTED = "rejected"
STALE = "stale"
SUPERSEDED = "superseded"
CANCELLED = "cancelled"

ACTIVE_STATES = {ACCEPTED, CONSUMED}


class HandoffError(RuntimeError):
    """Raised on handoff invariant violations."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@contextmanager
def _locked(lock_path: Path) -> Iterator[None]:
    """Best-effort cross-process file lock via fcntl (POSIX)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - non-POSIX
            pass
        yield
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


class HandoffRuntime:
    def __init__(self, registry: Registry | None = None, *, now: datetime | None = None) -> None:
        self.registry = registry or load_registry()
        self._now = now  # if None, use real clock

    def _clock(self) -> datetime:
        return self._now or _now()

    # --- paths ---
    def _handoffs_dir(self, run_dir: Path) -> Path:
        return run_dir / HANDOFFS_DIRNAME

    def _handoff_path(self, run_dir: Path, handoff_id: str) -> Path:
        return self._handoffs_dir(run_dir) / f"{handoff_id}.json"

    def _lock_path(self, run_dir: Path) -> Path:
        return run_dir / HANDOFFS_DIRNAME / LOCK_NAME

    # --- prepare ---
    def prepare(
        self,
        run_dir: str | Path,
        from_stage: str,
        *,
        run_id: str | None = None,
        created_by: str | None = None,
        decisions: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        contract = self.registry.contract(from_stage)
        rid = run_id or root.name
        creator = created_by or from_stage

        # 1. exit validation must pass
        exit_report = validate_exit(contract, root)
        if not exit_report.valid:
            raise HandoffError(
                f"cannot prepare handoff for {from_stage}: exit validation failed; "
                f"missing={exit_report.missing}, invalid={exit_report.invalid}"
            )

        # 2. build artifact refs
        output_refs = self._artifact_refs(contract, root, kind="output")
        input_refs = self._artifact_refs(contract, root, kind="input")
        if not output_refs:
            raise HandoffError(f"cannot prepare handoff for {from_stage}: no output artifacts")

        output_fingerprint = fp.fingerprint_set(
            [root / r["path"] for r in output_refs]
        )
        idempotency_key = f"{rid}:{from_stage}:{output_fingerprint}"

        # 3. idempotency: return existing handoff with the same key
        with _locked(self._lock_path(root)):
            existing = self._find_by_idempotency_key(root, idempotency_key)
            if existing is not None:
                return existing

            # 4. supersede any prior ACTIVE/AWAITING handoff for same transition
            transition = (from_stage, contract.next_stage)
            prior = self._latest_for_transition(root, transition)
            supersedes = ""
            if prior is not None and prior.get("idempotency_key") != idempotency_key:
                self._mutate_status(root, prior["handoff_id"], SUPERSEDED, reason="newer output fingerprint")
                supersedes = prior["handoff_id"]

            approval_policy = {
                "required": bool(contract.approval_required),
                "preauthorizable": bool(contract.preauthorizable),
                "non_bypassable": bool(contract.non_bypassable),
            }
            status = AWAITING_APPROVAL if approval_policy["required"] else ACCEPTED
            handoff_id = self._new_id(from_stage, contract.next_stage or "")

            record: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "handoff_id": handoff_id,
                "run_id": rid,
                "from_stage": from_stage,
                "to_stage": contract.next_stage,
                "status": status,
                "contract_version": self.registry.suite_version,
                "idempotency_key": idempotency_key,
                "input_artifacts": input_refs,
                "output_artifacts": output_refs,
                "output_fingerprint": output_fingerprint,
                "exit_validation": {
                    "valid": True,
                    "checks": [
                        {"check": "required_artifacts", "status": "pass"},
                        {"check": "blocking_questions", "status": "pass"},
                    ],
                },
                "decisions": list(decisions or []),
                "warnings": list(warnings or []),
                "approval_policy": approval_policy,
                "created_by": creator,
                "created_at": _utc_iso(self._clock()),
            }
            if supersedes:
                record["supersedes"] = supersedes
            if status == ACCEPTED:
                record["accepted_by"] = "auto"
                record["accepted_at"] = record["created_at"]

            self._write(root, handoff_id, record)
            self._refresh_current(root)
            return record

    # --- transitions ---
    def accept(self, run_dir: str | Path, handoff_id: str, *, actor: str) -> dict[str, Any]:
        return self._transition(
            run_dir, handoff_id, target=ACCEPTED, allowed_from=(AWAITING_APPROVAL,),
            extra={"accepted_by": actor, "accepted_at": _utc_iso(self._clock())},
        )

    def consume(self, run_dir: str | Path, handoff_id: str) -> dict[str, Any]:
        return self._transition(
            run_dir, handoff_id, target=CONSUMED, allowed_from=(ACCEPTED,),
        )

    def reject(
        self,
        run_dir: str | Path,
        handoff_id: str,
        *,
        reason: str,
        repair_owner_stage: str = "",
        actor: str = "",
    ) -> dict[str, Any]:
        return self._transition(
            run_dir, handoff_id, target=REJECTED, allowed_from=(AWAITING_APPROVAL,),
            extra={
                "rejected_reason": reason,
                "repair_owner_stage": repair_owner_stage or _default_repair_owner(handoff_id),
                "accepted_by": actor,
            },
        )

    def cancel(self, run_dir: str | Path, handoff_id: str, *, reason: str) -> dict[str, Any]:
        return self._transition(
            run_dir, handoff_id, target=CANCELLED, allowed_from=(DRAFT, AWAITING_APPROVAL, ACCEPTED),
            extra={"rejected_reason": reason},
        )

    def mark_stale(self, run_dir: str | Path, handoff_id: str, *, reason: str) -> dict[str, Any]:
        return self._transition(
            run_dir, handoff_id, target=STALE,
            allowed_from=(AWAITING_APPROVAL, ACCEPTED),
            extra={"stale_reason": reason},
        )

    # --- read API ---
    def list(self, run_dir: str | Path) -> list[dict[str, Any]]:
        root = Path(run_dir).expanduser().resolve()
        out: list[dict[str, Any]] = []
        d = self._handoffs_dir(root)
        if not d.is_dir():
            return out
        for p in sorted(d.glob("*.json")):
            if p.name == Path(CURRENT_PROJECTION).name:
                continue
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        out.sort(key=lambda h: h.get("created_at", ""))
        return out

    def inspect(self, run_dir: str | Path, handoff_id: str) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        p = self._handoff_path(root, handoff_id)
        if not p.exists():
            raise HandoffError(f"unknown handoff: {handoff_id}")
        return json.loads(p.read_text(encoding="utf-8"))

    def current(self, run_dir: str | Path) -> dict[str, Any] | None:
        """Projection of the most recent accepted/consumed handoff.

        Always recomputed from the handoffs truth source — the
        ``current_handoff.json`` file is a human/Review-Desk cache, never the
        truth source, so tampering it cannot change what ``current`` returns.
        """
        root = Path(run_dir).expanduser().resolve()
        return self._compute_current(root)

    # --- internals ---
    def _artifact_refs(self, contract, root: Path, *, kind: str) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        if kind == "output":
            outputs = required_outputs(contract)
            for out in outputs:
                for path in resolve_artifact_files(root, out["path_pattern"]):
                    refs.append(self._ref(path, root, out))
        else:
            for pattern in contract.entry.get("required_artifacts", []):
                for path in resolve_artifact_files(root, pattern):
                    refs.append(self._ref(path, root, None))
        return refs

    @staticmethod
    def _ref(path: Path, root: Path, output_def: dict[str, Any] | None) -> dict[str, Any]:
        digest = fp.fingerprint_file(path) or ""
        return {
            "path": str(path.relative_to(root)),
            "sha256": digest,
            "artifact_type": str((output_def or {}).get("artifact_type") or path.stem),
            "schema_version": str((output_def or {}).get("schema_version") or ""),
            "source_fingerprint": digest,
        }

    def _find_by_idempotency_key(self, root: Path, key: str) -> dict[str, Any] | None:
        for h in self.list(root):
            if h.get("idempotency_key") == key and h.get("status") not in {SUPERSEDED, CANCELLED}:
                return h
        return None

    def latest_for_stage(self, run_dir: str | Path, from_stage: str, to_stage: str | None) -> dict[str, Any] | None:
        """Latest non-superseded/cancelled/rejected handoff for a transition."""
        return self._latest_for_transition(run_dir, (from_stage, to_stage))

    def _latest_for_transition(self, root: Path, transition: tuple[str, str | None]) -> dict[str, Any] | None:
        frm, to = transition
        latest: dict[str, Any] | None = None
        for h in self.list(root):
            if h.get("from_stage") != frm:
                continue
            if to is not None and h.get("to_stage") != to:
                continue
            if h.get("status") in {SUPERSEDED, CANCELLED, REJECTED}:
                continue
            if latest is None or str(h.get("created_at", "")) > str(latest.get("created_at", "")):
                latest = h
        return latest

    def _transition(
        self,
        run_dir: str | Path,
        handoff_id: str,
        *,
        target: str,
        allowed_from: tuple[str, ...],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        with _locked(self._lock_path(root)):
            record = self.inspect(root, handoff_id)
            current = record.get("status")
            if current not in allowed_from:
                raise HandoffError(
                    f"cannot move handoff {handoff_id} from {current} to {target}"
                )
            record["status"] = target
            if extra:
                record.update(extra)
            self._write(root, handoff_id, record)
            self._refresh_current(root)
            return record

    def _mutate_status(self, root: Path, handoff_id: str, status: str, *, reason: str = "") -> None:
        record = self.inspect(root, handoff_id)
        record["status"] = status
        if reason:
            record["stale_reason" if status == STALE else "rejected_reason"] = reason
        self._write(root, handoff_id, record)

    def _write(self, root: Path, handoff_id: str, record: dict[str, Any]) -> None:
        path = self._handoff_path(root, handoff_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def _new_id(self, from_stage: str, to_stage: str) -> str:
        suffix = uuid.uuid4().hex[:12]
        to = (to_stage or "end").replace("deck-", "")
        frm = from_stage.replace("deck-", "")
        return f"handoff_{frm}_to_{to}_{suffix}"

    def _refresh_current(self, root: Path) -> None:
        current = self._compute_current(root)
        proj = root / CURRENT_PROJECTION
        proj.parent.mkdir(parents=True, exist_ok=True)
        if current is None:
            if proj.exists():
                proj.write_text("null\n", encoding="utf-8")
            return
        proj.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _compute_current(self, root: Path) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for h in self.list(root):
            if h.get("status") in ACTIVE_STATES:
                if latest is None or str(h.get("created_at", "")) > str(latest.get("created_at", "")):
                    latest = h
        return latest


def _default_repair_owner(handoff_id: str) -> str:
    """Default repair routing derived from the handoff's source stage."""
    if "brief_to_" in handoff_id:
        return "deck-brief"
    if "planner_to_" in handoff_id:
        return "deck-planner"
    if "sourcing_to_" in handoff_id:
        return "deck-sourcing"
    if "producer_to_" in handoff_id:
        return "deck-producer"
    return ""


__all__ = [
    "HandoffRuntime",
    "HandoffError",
    "SCHEMA_VERSION",
]
