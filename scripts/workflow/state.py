"""Workflow State Resolver (A2).

Derives a ``deck_workflow_state.v1`` snapshot for a run directory from the
Stage Contract registry, on-disk artifacts, and (optionally) the fine-grained
runtime stage produced by ``scripts/runtime/run_state_resolver.py``.

Design notes:

* Artifact-derived: stage completion is decided by contract exit artifacts,
  not by handoff/approval facts (those land in A3/A4). When exit artifacts are
  present but the transition is approval-required, the stage is reported as
  ``awaiting_approval``.
* Stale propagation: a stage is ``stale`` when any of its
  ``staleness_dependencies`` was modified after its own outputs.
* Deterministic & rebuildable: given identical on-disk state, two resolutions
  of the same run yield byte-identical snapshots (apart from ``generated_at``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from skills.manifest import PRODUCTION_STAGE_IDS, Registry, load_registry
from workflow import fingerprint as fp
from workflow.validator import (
    EntryReport,
    ExitReport,
    required_outputs,
    resolve_artifact_files,
    validate_entry,
    validate_exit,
)

SCHEMA_VERSION = "deck_workflow_state.v1"
RESOLVER_VERSION = "skill-os.state.v1"

# Status values (per 03-stage-contract-model.md §1).
NOT_STARTED = "not_started"
ENTRY_BLOCKED = "entry_blocked"
READY = "ready"
IN_PROGRESS = "in_progress"
AWAITING_QUESTIONS = "awaiting_questions"
AWAITING_APPROVAL = "awaiting_approval"
COMPLETED = "completed"
STALE = "stale"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass
class StageState:
    stage_id: str
    status: str = NOT_STARTED
    entry_valid: bool = False
    exit_valid: bool = False
    handoff_id: str = ""
    approval_status: str = ""
    missing_artifacts: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    output_fingerprint: str = ""
    stale: bool = False


RuntimeStageFn = Callable[[Path], str | None]


class WorkflowStateResolver:
    """Builds a workflow_state.v1 snapshot for a run directory."""

    def __init__(
        self,
        registry: Registry | None = None,
        *,
        runtime_stage_fn: RuntimeStageFn | None = None,
        now: datetime | None = None,
    ) -> None:
        self.registry = registry or load_registry()
        self._runtime_stage_fn = runtime_stage_fn
        self._now = now or datetime.now(timezone.utc)

    # --- public API ---
    def resolve(self, run_dir: str | Path, run_id: str | None = None) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        rid = run_id or root.name
        stages = self._resolve_stages(root)
        completed = [s.stage_id for s in stages if s.status == COMPLETED]
        stale_skills = [s.stage_id for s in stages if s.status == STALE]
        current = self._current_skill_stage(stages)
        runtime_stage = self._runtime_stage(root)
        next_skill, approval_required, approval_status = self._next(current, stages)
        missing = _collect(stages, lambda s: s.missing_artifacts)
        invalid = _collect(stages, lambda s: getattr(_exit(self.registry, s.stage_id, root), "invalid", []))
        stale_artifacts = self._stale_artifacts(root, stages)

        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": rid,
            "current_skill_stage": current,
            "runtime_stage": runtime_stage,
            "stages": [self._stage_dict(s) for s in stages],
            "completed_skills": completed,
            "stale_skills": stale_skills,
            "required_next_skill": next_skill if approval_required else "",
            "recommended_next_skill": next_skill,
            "approval_required": approval_required,
            "approval_status": approval_status,
            "current_handoff": None,  # populated by handoff runtime (A3)
            "missing_artifacts": missing,
            "invalid_artifacts": invalid,
            "stale_artifacts": stale_artifacts,
            "allowed_actions": self._allowed_actions(current, stages),
            "blocked_actions": self._blocked_actions(current, stages),
            "source_fingerprint": self._source_fingerprint(stages),
            "resolver_version": RESOLVER_VERSION,
            "generated_at": self._now.isoformat(),
            "legacy_inferred": False,
        }
        return state

    def write_snapshot(self, run_dir: str | Path, run_id: str | None = None) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        state = self.resolve(root, run_id=run_id)
        wf_dir = root / "workflow"
        wf_dir.mkdir(parents=True, exist_ok=True)
        (wf_dir / "workflow_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return state

    # --- internals ---
    def _resolve_stages(self, root: Path) -> list[StageState]:
        out: list[StageState] = []
        prev_status = COMPLETED  # deck-init has no required previous stage
        for stage_id in PRODUCTION_STAGE_IDS:
            contract = self.registry.contract(stage_id)
            # a stage may enter only if its predecessor reached COMPLETED
            previous_completed = prev_status == COMPLETED
            entry = validate_entry(contract, root, previous_completed=previous_completed)
            exit_report = validate_exit(contract, root)
            state = StageState(
                stage_id=stage_id,
                entry_valid=entry.valid,
                exit_valid=exit_report.valid,
                missing_artifacts=list(dict.fromkeys(entry.missing + exit_report.missing)),
                blockers=list(entry.blockers + exit_report.blockers),
            )

            # output fingerprint (deterministic)
            outputs = resolve_files_for_outputs(contract, root)
            state.output_fingerprint = fp.fingerprint_set(outputs) if outputs else ""

            # staleness: upstream dependency changed after own outputs
            state.stale = self._is_stale(contract, root, outputs)

            # status
            if state.stale and exit_report.valid:
                state.status = STALE
            elif exit_report.valid:
                if contract.approval_required and stage_id in {
                    "deck-brief",
                    "deck-planner",
                    "deck-sourcing",
                    "deck-review",
                }:
                    state.status = AWAITING_APPROVAL
                else:
                    state.status = COMPLETED
            elif entry.valid:
                # entry ok but not all outputs → in progress (or ready if nothing yet)
                state.status = IN_PROGRESS if outputs else READY
            else:
                # cannot enter: if upstream already produced something but the
                # gate is not passed, it is entry_blocked; otherwise not_started.
                if prev_status == NOT_STARTED:
                    state.status = NOT_STARTED
                else:
                    state.status = ENTRY_BLOCKED

            prev_status = state.status
            out.append(state)
        return out

    def _is_stale(self, contract, root: Path, outputs: list[Path]) -> bool:
        if not outputs:
            return False
        own_outputs = {p.resolve() for p in outputs}
        dep_files: list[Path] = []
        for d in contract.staleness_dependencies:
            resolved = _resolve_dependency(root, d)
            if not resolved:
                continue
            for p in resolved:
                # exclude this stage's own output files: a stage is stale only
                # when an *upstream* dependency changed after its outputs.
                if p.resolve() in own_outputs:
                    continue
                dep_files.append(p)
        if not dep_files:
            return False
        dep_latest = fp.latest_mtime(dep_files)
        out_earliest = fp.earliest_mtime(outputs)
        if dep_latest is None or out_earliest is None:
            return False
        return dep_latest > out_earliest

    def _stale_artifacts(self, root: Path, stages: list[StageState]) -> list[str]:
        out: list[str] = []
        for s in stages:
            if s.status == STALE:
                contract = self.registry.contract(s.stage_id)
                out.extend(contract.staleness_dependencies)
        return sorted(set(out))

    def _current_skill_stage(self, stages: list[StageState]) -> str:
        for s in stages:
            if s.status not in {COMPLETED}:
                return s.stage_id
        return stages[-1].stage_id if stages else ""

    def _next(
        self, current: str, stages: list[StageState]
    ) -> tuple[str, bool, str]:
        if not current:
            return "", False, ""
        contract = self.registry.contract(current)
        nxt = contract.next_stage
        approval_required = contract.approval_required
        # if current stage already completed its artifacts but awaits approval,
        # the recommended next skill is still the transition target
        status = next((s.status for s in stages if s.stage_id == current), "")
        if status in {AWAITING_APPROVAL, STALE}:
            approval_status = status
        elif approval_required:
            approval_status = "pending"
        else:
            approval_status = "not_required" if not approval_required else "pending"
        # next skill is the *next stage's* skill (or export gate for review)
        if nxt:
            return nxt, approval_required, approval_status
        return "", approval_required, approval_status

    def _allowed_actions(self, current: str, stages: list[StageState]) -> list[str]:
        status = next((s.status for s in stages if s.stage_id == current), NOT_STARTED)
        allowed: list[str] = []
        if status in {READY, IN_PROGRESS}:
            allowed.append(f"run:{current}")
        if status == AWAITING_APPROVAL:
            allowed.extend(["approve", "reject"])
        if status == COMPLETED:
            allowed.append("advance")
        return sorted(set(allowed))

    def _blocked_actions(self, current: str, stages: list[StageState]) -> list[dict[str, Any]]:
        blocked: list[dict[str, Any]] = []
        for s in stages:
            if s.status == ENTRY_BLOCKED and s.missing_artifacts:
                blocked.append(
                    {
                        "action": f"enter:{s.stage_id}",
                        "reason": "missing artifacts: " + ", ".join(s.missing_artifacts),
                    }
                )
            if s.status == AWAITING_APPROVAL:
                blocked.append({"action": f"advance:{s.stage_id}", "reason": "approval required"})
            if s.status == STALE:
                blocked.append({"action": f"advance:{s.stage_id}", "reason": "upstream changed"})
        return blocked

    def _runtime_stage(self, root: Path) -> str:
        if self._runtime_stage_fn is None:
            return ""
        try:
            value = self._runtime_stage_fn(root)
        except Exception:
            return ""
        return str(value or "")

    def _source_fingerprint(self, stages: list[StageState]) -> str:
        payload = [
            {
                "stage_id": s.stage_id,
                "status": s.status,
                "entry_valid": s.entry_valid,
                "exit_valid": s.exit_valid,
                "output_fingerprint": s.output_fingerprint,
                "missing": s.missing_artifacts,
            }
            for s in stages
        ]
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _stage_dict(self, s: StageState) -> dict[str, Any]:
        d: dict[str, Any] = {
            "stage_id": s.stage_id,
            "status": s.status,
            "entry_valid": s.entry_valid,
            "exit_valid": s.exit_valid,
            "handoff_id": s.handoff_id,
            "approval_status": s.approval_status,
            "missing_artifacts": s.missing_artifacts,
            "blockers": s.blockers,
            "output_fingerprint": s.output_fingerprint,
            "stale": s.stale,
        }
        return d


# --- module-level helpers ---


def resolve_files_for_outputs(contract, root: Path) -> list[Path]:
    files: list[Path] = []
    for out in required_outputs(contract):
        files.extend(resolve_artifact_files(root, out["path_pattern"]))
    return files


def _exit(registry: Registry, stage_id: str, root: Path) -> ExitReport:
    return validate_exit(registry.contract(stage_id), root)


def _resolve_dependency(root: Path, dep: str) -> list[Path] | None:
    """Resolve a staleness_dependency (filename / glob / dir) to files."""
    dep = dep.strip()
    if dep.endswith("/"):
        directory = root / dep.rstrip("/")
        if directory.is_dir():
            return [p for p in directory.rglob("*") if p.is_file()]
        return None
    if "*" in dep or "?" in dep:
        return [p for p in root.glob(dep) if p.is_file()]
    # may reference workflow/decision_log.jsonl etc.
    candidate = root / dep
    if candidate.is_file():
        return [candidate]
    if candidate.is_dir():
        return [p for p in candidate.rglob("*") if p.is_file()]
    return None


def _flatten(groups: list[list[Path]]) -> list[Path]:
    out: list[Path] = []
    for g in groups:
        out.extend(g)
    return out


def _collect(stages: list[StageState], selector) -> list[str]:
    out: list[str] = []
    for s in stages:
        out.extend(selector(s) or [])
    return sorted(set(out))


def resolve_workflow_state(
    run_dir: str | Path,
    *,
    run_id: str | None = None,
    registry: Registry | None = None,
    runtime_stage_fn: RuntimeStageFn | None = None,
) -> dict[str, Any]:
    """Convenience: resolve a workflow_state snapshot without instantiating."""
    return WorkflowStateResolver(registry=registry, runtime_stage_fn=runtime_stage_fn).resolve(
        run_dir, run_id=run_id
    )


__all__ = [
    "WorkflowStateResolver",
    "resolve_workflow_state",
    "StageState",
    "SCHEMA_VERSION",
]
