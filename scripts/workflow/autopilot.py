"""Workflow Autopilot v2 (B5).

A contract-aware, approval-aware, evidence-first workflow executor. It does
NOT replace the stage skills (it does not produce artifacts) — it drives the
stage ladder via the Handoff/Approval runtime, stopping at every high-impact
approval and ALWAYS at final client export.

Unified step algorithm::

    resolve state -> decide transition policy ->
    if stop condition: record evidence, stop
    else: prepare handoff (auto-accept or preauth) -> consume -> record evidence

Mode policies (07-approval-autopilot-policy.md §1):

* interactive   – stop at every high-impact approval
* preauthorized – auto-advance only for transitions covered by a live preauth
* quick         – fixture/dev; auto-advance non-export transitions
* repair        – only the finding's owner stage; re-approve on direction change
* review-only   – never run upstream production; only quality/review/readiness
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from skills.manifest import Registry, load_registry
from workflow.approval import ApprovalRuntime
from workflow.handoff import HandoffRuntime
from workflow.policy import (
    FINAL_EXPORT_TRANSITION,
    PreauthorizationRuntime,
    transition_key,
)
from workflow.questions import QuestionResolver
from workflow.state import WorkflowStateResolver

MODE_INTERACTIVE = "interactive"
MODE_PREAUTHORIZED = "preauthorized"
MODE_QUICK = "quick"
MODE_REPAIR = "repair"
MODE_REVIEW_ONLY = "review-only"
ALL_MODES = (MODE_INTERACTIVE, MODE_PREAUTHORIZED, MODE_QUICK, MODE_REPAIR, MODE_REVIEW_ONLY)

# Stages whose transition is "high-impact" (approval-required).
HIGH_IMPACT_STAGES = {"deck-brief", "deck-planner", "deck-sourcing", "deck-review"}

# Stages review-only mode may touch (downstream only).
REVIEW_ONLY_ALLOWED = {"deck-quality", "deck-review"}


@dataclass
class StepEvidence:
    step: int
    stage_before: str
    stage_after: str
    action: str
    handoff_id: str = ""
    approval_decision: str = ""
    preauthorization_id: str = ""
    stop_reason: str = ""
    validation_refs: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0


@dataclass
class AutopilotResult:
    mode: str
    steps: list[StepEvidence]
    stop_reason: str
    final_stage: str
    started_at: str
    ended_at: str


class AutopilotV2:
    def __init__(
        self,
        registry: Registry | None = None,
        *,
        now: datetime | None = None,
    ) -> None:
        self.registry = registry or load_registry()
        self._now = now  # if None, real clock
        self.handoffs = HandoffRuntime(registry=self.registry, now=now)
        self.approvals = ApprovalRuntime(registry=self.registry, handoff_runtime=self.handoffs, now=now)
        self.preauth = PreauthorizationRuntime(registry=self.registry, now=now)
        self.questions = QuestionResolver(registry=self.registry)
        self.state = WorkflowStateResolver(registry=self.registry, now=now, handoff_runtime=self.handoffs)

    def _clock(self) -> datetime:
        return self._now or datetime.now(timezone.utc)

    def run(
        self,
        run_dir: str | Path,
        *,
        mode: str,
        max_steps: int = 8,
        run_id: str | None = None,
        repair_owner_stage: str = "",
    ) -> AutopilotResult:
        if mode not in ALL_MODES:
            raise ValueError(f"unknown autopilot mode: {mode}")
        root = Path(run_dir).expanduser().resolve()
        rid = run_id or root.name
        started = self._clock()
        steps: list[StepEvidence] = []
        stop_reason = ""

        for step_num in range(1, max_steps + 1):
            step_start = self._clock()
            state = self.state.resolve(root, run_id=rid)
            current = state.get("current_skill_stage", "")
            if not current:
                stop_reason = "workflow_complete"
                steps.append(self._evidence(step_num, current, current, "noop", stop_reason=stop_reason, start=step_start))
                break

            contract = self.registry.contract(current)
            nxt = contract.next_stage
            transition = transition_key(current, nxt)

            # --- stop conditions (07 §4) ---
            # 1. final export always stops (never auto-export)
            if nxt == "client_export" or transition == FINAL_EXPORT_TRANSITION:
                stop_reason = "final_export_requires_approval"
                steps.append(self._evidence(step_num, current, current, "stop_export", stop_reason=stop_reason, start=step_start))
                break

            # 2. review-only mode blocks upstream production
            if mode == MODE_REVIEW_ONLY and current not in REVIEW_ONLY_ALLOWED:
                stop_reason = "review_only_blocked_upstream"
                steps.append(self._evidence(step_num, current, current, "stop", stop_reason=stop_reason, start=step_start))
                break

            # 3. repair mode: only act on the owner stage
            if mode == MODE_REPAIR and repair_owner_stage and current != repair_owner_stage:
                stop_reason = "repair_owner_stage_mismatch"
                steps.append(self._evidence(step_num, current, current, "stop", stop_reason=stop_reason, start=step_start))
                break

            # 4. exit validation (artifacts + blocking questions)
            exit_val = self.questions.exit_validation(root, current)
            if not exit_val.valid:
                if exit_val.blocking:
                    stop_reason = "blocking_questions"
                else:
                    stop_reason = "missing_artifacts"
                steps.append(self._evidence(
                    step_num, current, current, "stop",
                    stop_reason=stop_reason, start=step_start,
                    validation_refs={"checks": exit_val.checks},
                ))
                break

            approval_required = contract.approval_required and current in HIGH_IMPACT_STAGES

            # 5. decide whether to auto-advance or stop for approval
            cleared, clearance_reason = self._clearance(mode, current, transition, root, rid)
            if approval_required and not cleared:
                # prepare handoff (awaiting_approval) so the gate is concrete
                handoff = self.handoffs.prepare(root, current, run_id=rid)
                stop_reason = "approval_required"
                steps.append(self._evidence(
                    step_num, current, current, "prepare_handoff",
                    handoff_id=handoff.get("handoff_id", ""),
                    approval_decision="pending", stop_reason=stop_reason, start=step_start,
                ))
                break

            # 6. auto-advance: prepare handoff (auto-accepted or preauth), consume
            handoff = self.handoffs.prepare(root, current, run_id=rid)
            hid = handoff.get("handoff_id", "")
            if handoff.get("status") == "awaiting_approval":
                # preauth-cleared: accept via the approval runtime using the preauth
                req = self.approvals.request(root, hid, run_id=rid)
                self.approvals.approve(
                    root, req["approval_id"],
                    actor={"id": "autopilot", "role": mode},
                    preauthorization_id=clearance_reason if "preauth" in clearance_reason else "",
                )
            # consume to mark transition complete
            try:
                self.handoffs.consume(root, hid)
            except Exception:
                pass

            new_state = self.state.resolve(root, run_id=rid)
            stage_after = new_state.get("current_skill_stage", current)
            steps.append(self._evidence(
                step_num, current, stage_after, "advance",
                handoff_id=hid,
                approval_decision="cleared" if approval_required else "not_required",
                preauthorization_id=clearance_reason if "preauth" in clearance_reason else "",
                start=step_start,
            ))

            if stage_after == current:
                stop_reason = "no_stage_advance"
                break

        else:
            stop_reason = "max_steps_reached"

        ended = self._clock()
        final_state = self.state.resolve(root, run_id=rid)
        return AutopilotResult(
            mode=mode,
            steps=steps,
            stop_reason=stop_reason or "max_steps_reached",
            final_stage=final_state.get("current_skill_stage", ""),
            started_at=started.isoformat(),
            ended_at=ended.isoformat(),
        )

    # --- clearance ---
    def _clearance(
        self,
        mode: str,
        current: str,
        transition: str,
        root: Path,
        run_id: str,
    ) -> tuple[bool, str]:
        """Return (cleared, reason). `cleared` means autopilot may auto-advance
        an approval-required transition without a fresh human approval."""
        if mode == MODE_INTERACTIVE:
            return False, "interactive_requires_approval"
        if mode == MODE_QUICK:
            return True, "quick_mode_auto"
        if mode == MODE_REVIEW_ONLY:
            return False, "review_only"
        if mode == MODE_REPAIR:
            # repair re-approves on direction change; assume not cleared unless
            # caller signals the owner stage is being re-run deterministically
            return False, "repair_requires_approval"
        if mode == MODE_PREAUTHORIZED:
            preauth = self.preauth.active_for(root, transition)
            if preauth is not None:
                return True, f"preauth:{preauth.policy_id}"
            return False, "no_active_preauth"
        return False, "unknown_mode"

    def _evidence(
        self,
        step: int,
        before: str,
        after: str,
        action: str,
        *,
        handoff_id: str = "",
        approval_decision: str = "",
        preauthorization_id: str = "",
        stop_reason: str = "",
        validation_refs: dict[str, Any] | None = None,
        start: datetime,
    ) -> StepEvidence:
        elapsed = int((self._clock() - start).total_seconds() * 1000)
        return StepEvidence(
            step=step,
            stage_before=before,
            stage_after=after,
            action=action,
            handoff_id=handoff_id,
            approval_decision=approval_decision,
            preauthorization_id=preauthorization_id,
            stop_reason=stop_reason,
            validation_refs=validation_refs or {},
            elapsed_ms=elapsed,
        )


__all__ = [
    "AutopilotV2",
    "AutopilotResult",
    "StepEvidence",
    "ALL_MODES",
    "MODE_INTERACTIVE",
    "MODE_PREAUTHORIZED",
    "MODE_QUICK",
    "MODE_REPAIR",
    "MODE_REVIEW_ONLY",
]
