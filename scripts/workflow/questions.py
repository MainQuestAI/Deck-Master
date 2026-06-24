"""Forcing Questions resolver (B1).

Surfaces only the *current gap* for a stage: required questions that have no
fresh (non-stale) answer. A required, unanswered question is *blocking* and
must fail exit validation (D1: interview depth enforced by runtime, not by
Agent discipline).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skills.manifest import Registry, StageContract, load_registry
from workflow import fingerprint as fp
from workflow.decisions import DecisionLog
from workflow.validator import required_outputs, resolve_artifact_files


@dataclass
class QuestionGap:
    question_id: str
    category: str
    prompt: str
    required: bool
    assumption_allowed: bool
    evidence_required: bool
    stale: bool = False
    trigger: str = ""


@dataclass
class ExitValidation:
    valid: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)


class QuestionResolver:
    def __init__(
        self,
        registry: Registry | None = None,
        *,
        decision_log: DecisionLog | None = None,
    ) -> None:
        self.registry = registry or load_registry()
        self.decisions = decision_log or DecisionLog()

    # --- input fingerprint for a stage ---
    def input_fingerprint(self, contract: StageContract, root: Path) -> str:
        files: list[Path] = []
        for pattern in contract.entry.get("required_artifacts", []):
            files.extend(resolve_artifact_files(root, pattern))
        return fp.fingerprint_set(files) if files else ""

    # --- gap questions ---
    def gaps(
        self,
        run_dir: str | Path,
        stage_id: str,
        *,
        include_optional: bool = False,
    ) -> list[QuestionGap]:
        root = Path(run_dir).expanduser().resolve()
        contract = self.registry.contract(stage_id)
        current_fp = self.input_fingerprint(contract, root)
        gaps: list[QuestionGap] = []
        for q in contract.forcing_questions:
            required = bool(q.get("required"))
            if not required and not include_optional:
                continue
            decision = self.decisions.latest(root, stage_id, q["question_id"])
            answered = decision is not None and not DecisionLog.is_stale(decision, current_fp)
            if answered:
                continue
            gaps.append(
                QuestionGap(
                    question_id=q["question_id"],
                    category=q.get("category", ""),
                    prompt=q.get("prompt", ""),
                    required=required,
                    assumption_allowed=bool(q.get("assumption_allowed", False)),
                    evidence_required=bool(q.get("evidence_required", False)),
                    stale=decision is not None,  # had an answer but it went stale
                    trigger=q.get("trigger", ""),
                )
            )
        return gaps

    def blocking(self, run_dir: str | Path, stage_id: str) -> list[QuestionGap]:
        return [g for g in self.gaps(run_dir, stage_id) if g.required]

    # --- exit validation incl. blocking questions ---
    def exit_validation(
        self,
        run_dir: str | Path,
        stage_id: str,
    ) -> ExitValidation:
        from workflow.validator import validate_exit

        root = Path(run_dir).expanduser().resolve()
        contract = self.registry.contract(stage_id)
        artifact_report = validate_exit(contract, root)
        blocking_qs = self.blocking(root, stage_id)

        checks: list[dict[str, Any]] = [
            {
                "check": "required_artifacts",
                "status": "pass" if artifact_report.valid else "fail",
                "missing": artifact_report.missing,
            },
            {
                "check": "blocking_questions",
                "status": "pass" if not blocking_qs else "fail",
                "open": [g.question_id for g in blocking_qs],
            },
        ]
        valid = artifact_report.valid and not blocking_qs
        return ExitValidation(
            valid=valid,
            checks=checks,
            blocking=[g.question_id for g in blocking_qs],
        )


__all__ = ["QuestionResolver", "QuestionGap", "ExitValidation"]
