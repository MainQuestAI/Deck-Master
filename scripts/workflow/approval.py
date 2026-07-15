"""Stage Approval Runtime (A4, D7/D8).

Approvals bind a Transition (from/to stage), a Handoff id, the bound output
fingerprint and per-artifact sha256, the actor and the decision. They are
append-only records under ``workflow/approvals/<approval_id>.json``.

Staleness: when the bound handoff's current output fingerprint differs from
the approval's ``artifact_binding.output_fingerprint``, the approval is stale
and no longer satisfies the gate.

Non-bypassable: the ``deck-review->client-export`` transition requires a live
human approval and can neither be preauthorized nor auto-approved (D8).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from skills.manifest import Registry, load_registry
from workflow.handoff import HandoffRuntime
from workflow.policy import (
    FINAL_EXPORT_TRANSITION,
    PreauthorizationRuntime,
    transition_key,
)

SCHEMA_VERSION = "deck_stage_approval.v1"
APPROVALS_DIR = "workflow/approvals"

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
REVOKED = "revoked"
STALE = "stale"

DEFAULT_APPROVAL_TTL = 24 * 3600


class ApprovalError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class ApprovalRuntime:
    def __init__(
        self,
        registry: Registry | None = None,
        *,
        handoff_runtime: HandoffRuntime | None = None,
        preauth_runtime: PreauthorizationRuntime | None = None,
        now: datetime | None = None,
    ) -> None:
        self.registry = registry or load_registry()
        self.handoffs = handoff_runtime or HandoffRuntime(registry=self.registry)
        self.preauth = preauth_runtime or PreauthorizationRuntime(registry=self.registry)
        self._now = now  # if None use real clock

    def _clock(self) -> datetime:
        return self._now or _now()

    # --- paths ---
    def _approvals_dir(self, root: Path) -> Path:
        return root / APPROVALS_DIR

    def _approval_path(self, root: Path, approval_id: str) -> Path:
        return self._approvals_dir(root) / f"{approval_id}.json"

    # --- create / decide ---
    def request(
        self,
        run_dir: str | Path,
        handoff_id: str,
        *,
        run_id: str,
        actor: dict[str, Any] | None = None,
        ttl_seconds: int = DEFAULT_APPROVAL_TTL,
    ) -> dict[str, Any]:
        """Open a pending approval bound to a handoff's current fingerprint."""
        root = Path(run_dir).expanduser().resolve()
        handoff = self.handoffs.inspect(root, handoff_id)
        if handoff.get("status") not in {"awaiting_approval", "accepted"}:
            raise ApprovalError(
                f"handoff {handoff_id} is {handoff.get('status')}; nothing to approve"
            )
        approval_id = f"approval_{uuid.uuid4().hex[:12]}"
        now = self._clock()
        binding = self._binding_for(handoff)
        record = {
            "schema_version": SCHEMA_VERSION,
            "approval_id": approval_id,
            "run_id": run_id,
            "handoff_id": handoff_id,
            "from_stage": handoff.get("from_stage"),
            "to_stage": handoff.get("to_stage"),
            "decision": PENDING,
            "actor": dict(actor or {"id": "unknown", "role": "requester"}),
            "artifact_binding": binding,
            "preauthorization_id": "",
            "created_at": _utc(now),
            "expires_at": _utc(now + timedelta(seconds=ttl_seconds)),
        }
        self._write(root, approval_id, record)
        return record

    def approve(
        self,
        run_dir: str | Path,
        approval_id: str,
        *,
        actor: dict[str, Any],
        preauthorization_id: str = "",
    ) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        record = self._read(root, approval_id)
        self._assert_live(root, record)
        # final export cannot be approved via preauthorization
        if record["to_stage"] == "client_export" and preauthorization_id:
            raise ApprovalError("final client export cannot be approved via preauthorization")
        record["decision"] = APPROVED
        record["actor"] = dict(actor)
        record["decided_at"] = _utc(self._clock())
        if preauthorization_id:
            record["preauthorization_id"] = preauthorization_id
        self._write(root, approval_id, record)
        # accept the underlying handoff
        self.handoffs.accept(root, record["handoff_id"], actor=str(actor.get("id") or "approver"))
        if record.get("to_stage") == "client_export":
            from runtime.final_approval import write_final_artifact_approval

            write_final_artifact_approval(root, record)
        return record

    def reject(
        self,
        run_dir: str | Path,
        approval_id: str,
        *,
        actor: dict[str, Any],
        reason: str,
        repair_owner_stage: str = "",
    ) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        record = self._read(root, approval_id)
        self._assert_live(root, record)
        owner = repair_owner_stage or self._default_repair_owner(record)
        record["decision"] = REJECTED
        record["actor"] = dict(actor)
        record["reason"] = reason
        record["repair_owner_stage"] = owner
        record["decided_at"] = _utc(self._clock())
        self._write(root, approval_id, record)
        self.handoffs.reject(
            root,
            record["handoff_id"],
            reason=reason,
            repair_owner_stage=owner,
            actor=str(actor.get("id") or "approver"),
        )
        return record

    def revoke(self, run_dir: str | Path, approval_id: str, *, actor: dict[str, Any], reason: str = "") -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        record = self._read(root, approval_id)
        if record["decision"] not in {APPROVED, PENDING}:
            raise ApprovalError(f"cannot revoke approval in state {record['decision']}")
        record["decision"] = REVOKED
        record["actor"] = dict(actor)
        if reason:
            record["reason"] = reason
        record["decided_at"] = _utc(self._clock())
        self._write(root, approval_id, record)
        if record.get("to_stage") == "client_export":
            from runtime.final_approval import invalidate_final_artifact_approval

            invalidate_final_artifact_approval(root, approval_id)
        return record

    # --- gate query ---
    def is_transition_cleared(
        self,
        run_dir: str | Path,
        from_stage: str,
        *,
        run_id: str,
    ) -> tuple[bool, str]:
        """Return (cleared, reason). For approval-required transitions, cleared
        only when a live, fingerprint-bound approval (or active preauth) exists.
        Final export is never cleared by preauth.
        """
        root = Path(run_dir).expanduser().resolve()
        contract = self.registry.contract(from_stage)
        if not contract.approval_required:
            return True, "automatic transition"
        to_stage = contract.next_stage
        transition = transition_key(from_stage, to_stage)

        # final export: require an APPROVED human approval bound to current fingerprint
        if contract.non_bypassable:
            handoff = self._latest_handoff_for(root, from_stage, to_stage)
            if handoff is None:
                return False, "no handoff for final export"
            approval = self._latest_decision(root, handoff["handoff_id"], decision=APPROVED)
            if approval is None:
                return False, "final export requires explicit human approval"
            if not self._binding_matches(approval, handoff):
                return False, "final export approval is stale (fingerprint changed)"
            return True, "final export approved"

        # other high-impact transitions: approval OR active preauthorization
        handoff = self._latest_handoff_for(root, from_stage, to_stage)
        if handoff is None:
            return False, "no handoff prepared"
        approval = self._latest_decision(root, handoff["handoff_id"], decision=APPROVED)
        if approval is not None and self._binding_matches(approval, handoff):
            return True, "approved"
        # try preauthorization
        preauth = self.preauth.active_for(root, transition)
        if preauth is not None:
            return True, f"preauthorized ({preauth.policy_id})"
        return False, "approval required"

    # --- staleness ---
    def refresh_stale(self, run_dir: str | Path) -> list[str]:
        """Mark approvals stale when the *current* handoff for the same
        transition has a different output fingerprint than the one bound at
        decision time. Upstream change → new handoff → old approval stale.
        Returns the stale approval ids."""
        root = Path(run_dir).expanduser().resolve()
        stale_ids: list[str] = []
        for rec in self.list(root):
            if rec["decision"] not in {APPROVED, PENDING}:
                continue
            from_stage = rec.get("from_stage")
            to_stage = rec.get("to_stage")
            latest = self._latest_handoff_for(root, from_stage, to_stage)
            if latest is None:
                continue
            bound_fp = rec.get("artifact_binding", {}).get("output_fingerprint")
            current_fp = latest.get("output_fingerprint")
            if bound_fp and current_fp and bound_fp != current_fp:
                rec["decision"] = STALE
                rec["decided_at"] = _utc(self._clock())
                self._write(root, rec["approval_id"], rec)
                stale_ids.append(rec["approval_id"])
                try:
                    self.handoffs.mark_stale(root, rec["handoff_id"], reason="output fingerprint changed")
                except Exception:
                    pass
        return stale_ids

    # --- read ---
    def list(self, run_dir: str | Path) -> list[dict[str, Any]]:
        root = Path(run_dir).expanduser().resolve()
        out: list[dict[str, Any]] = []
        d = self._approvals_dir(root)
        if not d.is_dir():
            return out
        for p in sorted(d.glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        out.sort(key=lambda r: r.get("created_at", ""))
        return out

    def inspect(self, run_dir: str | Path, approval_id: str) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        return self._read(root, approval_id)

    # --- internals ---
    def _binding_for(self, handoff: dict[str, Any]) -> dict[str, Any]:
        artifacts = [
            {"path": str(a.get("path")), "sha256": str(a.get("sha256"))}
            for a in handoff.get("output_artifacts", [])
        ]
        return {
            "output_fingerprint": str(handoff.get("output_fingerprint", "")),
            "artifacts": artifacts,
        }

    def _binding_matches(self, approval: dict[str, Any], handoff: dict[str, Any]) -> bool:
        bound = approval.get("artifact_binding", {}).get("output_fingerprint")
        current = handoff.get("output_fingerprint")
        return bool(bound) and bound == current

    def _latest_handoff_for(self, root: Path, from_stage: str, to_stage: str | None) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for h in self.handoffs.list(root):
            if h.get("from_stage") != from_stage:
                continue
            if to_stage is not None and h.get("to_stage") != to_stage:
                continue
            if h.get("status") in {"superseded", "cancelled", "rejected"}:
                continue
            if latest is None or str(h.get("created_at", "")) > str(latest.get("created_at", "")):
                latest = h
        return latest

    def _latest_decision(self, root: Path, handoff_id: str, *, decision: str) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for rec in self.list(root):
            if rec.get("handoff_id") != handoff_id:
                continue
            if rec.get("decision") != decision:
                continue
            # expiry
            exp = _parse_dt(rec.get("expires_at"))
            if exp is not None and self._clock() >= exp:
                continue
            if latest is None or str(rec.get("decided_at") or rec.get("created_at", "")) > str(
                latest.get("decided_at") or latest.get("created_at", "")
            ):
                latest = rec
        return latest

    def _assert_live(self, root: Path, record: dict[str, Any]) -> None:
        if record.get("decision") not in {PENDING}:
            raise ApprovalError(f"approval {record['approval_id']} is {record.get('decision')}, not pending")
        exp = _parse_dt(record.get("expires_at"))
        if exp is not None and self._clock() >= exp:
            raise ApprovalError(f"approval {record['approval_id']} has expired")

    def _default_repair_owner(self, record: dict[str, Any]) -> str:
        frm = record.get("from_stage", "")
        # 03-stage-contract-model.md §8 routing
        if frm in {"deck-producer", "deck-review"}:
            return "deck-producer"
        if frm == "deck-planner":
            return "deck-planner"
        if frm == "deck-sourcing":
            return "deck-sourcing"
        if frm == "deck-builder":
            return "deck-builder"
        return frm

    def _read(self, root: Path, approval_id: str) -> dict[str, Any]:
        p = self._approval_path(root, approval_id)
        if not p.exists():
            raise ApprovalError(f"unknown approval: {approval_id}")
        return json.loads(p.read_text(encoding="utf-8"))

    def _write(self, root: Path, approval_id: str, record: dict[str, Any]) -> None:
        p = self._approval_path(root, approval_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)


__all__ = [
    "ApprovalRuntime",
    "ApprovalError",
    "SCHEMA_VERSION",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "REVOKED",
    "STALE",
]
