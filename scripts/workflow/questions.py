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
    question_kind: str
    prompt: str
    required: bool
    assumption_allowed: bool
    evidence_required: bool
    answer_status: str = "missing"
    challenge_round: int = 0
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
        return fp.fingerprint_set(files) if files else f"no_inputs:{contract.stage_id}"

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
            answer_status, challenge_round = self._answer_status(
                root, stage_id, q["question_id"], decision, current_fp
            )
            answered = answer_status == "answered"
            if answered:
                continue
            gaps.append(
                QuestionGap(
                    question_id=q["question_id"],
                    category=q.get("category", ""),
                    question_kind=q.get("category", ""),
                    prompt=q.get("prompt", ""),
                    required=required,
                    assumption_allowed=bool(q.get("assumption_allowed", False)),
                    evidence_required=bool(q.get("evidence_required", False)),
                    answer_status=answer_status,
                    challenge_round=challenge_round,
                    stale=answer_status == "stale",
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
        from workflow.stage_checks import evaluate_stage_checks

        root = Path(run_dir).expanduser().resolve()
        contract = self.registry.contract(stage_id)
        artifact_report = validate_exit(contract, root)
        blocking_qs = self.blocking(root, stage_id)
        stage_checks = evaluate_stage_checks(root, stage_id)

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
        checks.extend(stage_checks.checks)
        valid = artifact_report.valid and not blocking_qs and stage_checks.valid
        return ExitValidation(
            valid=valid,
            checks=checks,
            blocking=[g.question_id for g in blocking_qs] + stage_checks.blocking,
        )

    def _answer_status(
        self,
        root: Path,
        stage_id: str,
        question_id: str,
        decision: dict[str, Any] | None,
        current_input_fingerprint: str,
    ) -> tuple[str, int]:
        attempts = self._attempt_count(root, stage_id, question_id)
        if decision is None:
            return "missing", 0
        if DecisionLog.is_stale(decision, current_input_fingerprint):
            return "stale", min(attempts, 2)
        if self._is_vague_answer(decision.get("answer")):
            if attempts >= 2:
                return "needs_human_judgment", 2
            return "needs_follow_up", max(1, attempts)
        return "answered", min(attempts, 2)

    def _attempt_count(self, root: Path, stage_id: str, question_id: str) -> int:
        attempts = 0
        for record in self.decisions.list(root, stage_id=stage_id):
            if record.get("question_id") == question_id:
                attempts += 1
        return attempts

    def _is_vague_answer(self, answer: Any) -> bool:
        if answer is None:
            return True
        if isinstance(answer, str):
            text = answer.strip().lower()
            if not text:
                return True
            vague_tokens = {
                "tbd", "n/a", "na", "none", "unknown", "ok", "yes", "no",
                "不知道", "不清楚", "待定", "暂定", "都可以", "看情况", "后面再说",
                "再看看", "先这样", "有", "没有", "是", "否", "好的",
            }
            return text in vague_tokens
        if isinstance(answer, (list, tuple, set)):
            return len(answer) == 0
        if isinstance(answer, dict):
            return len(answer) == 0
        return False


__all__ = ["QuestionResolver", "QuestionGap", "ExitValidation"]
