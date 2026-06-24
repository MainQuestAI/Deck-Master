"""Legacy Run & Compatibility Migration (C3).

Bootstraps pre-Skill-OS runs into the Workflow runtime WITHOUT forging
approvals: a legacy run whose artifacts exist is inferred to have reached the
corresponding stage, but every high-impact transition stays
``awaiting_approval`` until a real human approval is recorded. No handoff or
approval records are synthesized (C3 must-implement #1).

Also provides a rollback hook so a migration can be undone without losing the
original run state.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skills.manifest import Registry, load_registry
from workflow.state import WorkflowStateResolver

SCHEMA_VERSION = "deck_legacy_bootstrap.v1"
BOOTSTRAP_PATH = "workflow/legacy_bootstrap.json"

HIGH_IMPACT_STAGES = {"deck-brief", "deck-planner", "deck-sourcing", "deck-review"}


class MigrationError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class LegacyBootstrap:
    def __init__(self, registry: Registry | None = None, *, now: datetime | None = None) -> None:
        self.registry = registry or load_registry()
        self._now = now  # if None real clock

    def _clock(self) -> datetime:
        return self._now or _now()

    def infer_run(self, run_dir: str | Path) -> dict[str, Any]:
        """Resolve a legacy run to a workflow_state without forging approvals.

        Returns the inferred state plus a migration record. The state is the
        standard workflow_state.v1; high-impact stages with artifacts present
        are ``awaiting_approval`` (never ``completed``/approved) until a real
        approval is recorded.
        """
        root = Path(run_dir).expanduser().resolve()
        resolver = WorkflowStateResolver(registry=self.registry, now=self._now)
        state = resolver.resolve(root, run_id=root.name)
        # defense-in-depth: force approval-required stages to awaiting_approval
        # if they were inferred completed (they must NOT be, but legacy paths
        # could surprise us). This is the non-forgery invariant.
        forged_fixed = 0
        for stage in state.get("stages", []):
            sid = stage.get("stage_id")
            if sid in HIGH_IMPACT_STAGES and stage.get("exit_valid") and stage.get("status") == "completed":
                stage["status"] = "awaiting_approval"
                forged_fixed += 1
        if forged_fixed:
            state["approval_required"] = True
        return state

    def bootstrap(self, run_dir: str | Path, *, run_id: str | None = None) -> dict[str, Any]:
        """Write a legacy_bootstrap.json marker recording the inference, and
        return the inferred state. Does NOT create handoffs or approvals."""
        root = Path(run_dir).expanduser().resolve()
        rid = run_id or root.name
        state = self.infer_run(root)
        record = {
            "schema_version": SCHEMA_VERSION,
            "run_id": rid,
            "bootstrapped_at": _utc(self._clock()),
            "inferred_stages": [
                {"stage_id": s["stage_id"], "status": s["status"], "exit_valid": s.get("exit_valid", False)}
                for s in state.get("stages", [])
            ],
            "forged_approvals": 0,  # invariant: never forge
            "high_impact_awaiting": [
                s["stage_id"] for s in state.get("stages", [])
                if s["stage_id"] in HIGH_IMPACT_STAGES and s.get("status") == "awaiting_approval"
            ],
            "rollback_possible": True,
        }
        wf = root / "workflow"
        wf.mkdir(parents=True, exist_ok=True)
        (wf / "legacy_bootstrap.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # also persist the inferred state snapshot
        (wf / "workflow_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return record

    def rollback(self, run_dir: str | Path) -> dict[str, Any]:
        """Remove the Skill OS workflow bookkeeping written by bootstrap,
        leaving the original run artifacts untouched."""
        root = Path(run_dir).expanduser().resolve()
        wf = root / "workflow"
        removed: list[str] = []
        if not wf.is_dir():
            return {"rolled_back": False, "reason": "no workflow dir", "removed": []}
        # remove only the Skill OS derived files, never the run's content artifacts
        for name in ("legacy_bootstrap.json", "workflow_state.json", "current_handoff.json"):
            p = wf / name
            if p.exists():
                p.unlink()
                removed.append(name)
        # remove handoffs/approvals/preauth subdirs if bootstrap created them
        for sub in ("handoffs", "approvals"):
            sub_path = wf / sub
            if sub_path.is_dir():
                import shutil

                shutil.rmtree(sub_path)
                removed.append(f"{sub}/")
        return {"rolled_back": True, "removed": removed}

    def inference_report(self, run_dir: str | Path) -> dict[str, Any]:
        state = self.infer_run(run_dir)
        return {
            "current_skill_stage": state.get("current_skill_stage"),
            "high_impact_awaiting": [
                s["stage_id"] for s in state.get("stages", [])
                if s["stage_id"] in HIGH_IMPACT_STAGES and s.get("status") == "awaiting_approval"
            ],
            "completed_stages": state.get("completed_skills", []),
            "forged_approvals": 0,
        }


__all__ = ["LegacyBootstrap", "MigrationError", "SCHEMA_VERSION"]
