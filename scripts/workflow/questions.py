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
    material_answer_available: bool = False
    user_reserved: bool = False


# SC-1 A5/W-05: these decisions are the user's alone — the host Agent may
# draft, recommend, or prepare the question, but never fill the answer.
USER_RESERVED_CATEGORIES = {"delivery"}
AGENT_ANSWER_SOURCES = {"agent", "runtime", "host_agent"}


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
                root, stage_id, q["question_id"], decision, current_fp, question=q
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
                    material_answer_available=bool(self.material_answer_candidates(root, q).get("answer")),
                    user_reserved=str(q.get("category") or "") in USER_RESERVED_CATEGORIES,
                )
            )
        return gaps

    def material_answer_candidates(self, root: Path, question: dict[str, Any]) -> dict[str, Any]:
        """SC-1 A5/W-01: find answers the材料 already contains.

        Scans registered constraint candidates (full-text, including the tail
        region) and source navigation text for keyword overlap with the
        question prompt. The candidate carries its evidence refs so the
        runtime can record a material-sourced answer instead of re-asking the
        user for information the材料 already answers.
        """

        manifest_path = root / "context_manifest.json"
        if not manifest_path.exists():
            return {"answer": "", "evidence_refs": []}
        try:
            import json as _json

            manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):  # type: ignore[attr-defined]
            return {"answer": "", "evidence_refs": []}
        prompt = str(question.get("prompt") or "")
        keywords = [token for token in _extract_keywords(prompt) if len(token) >= 2]
        if not keywords:
            return {"answer": "", "evidence_refs": []}
        best: dict[str, Any] = {"answer": "", "evidence_refs": []}
        for candidate in manifest.get("tail_constraint_candidates", []) or []:
            text = str(candidate.get("text") or "")
            if sum(1 for token in keywords if token in text) >= min(2, len(keywords)):
                best = {
                    "answer": text,
                    "evidence_refs": [f"context_manifest.json#{candidate.get('source_id', '')}"],
                    "region": candidate.get("region", "tail"),
                }
                break
        if not best["answer"]:
            for source in manifest.get("sources", []) or []:
                text = f"{source.get('name', '')} {source.get('summary', '')} {source.get('excerpt', '')}"
                if sum(1 for token in keywords if token in text) >= min(2, len(keywords)):
                    best = {
                        "answer": str(source.get("excerpt") or source.get("summary") or "")[:400],
                        "evidence_refs": [f"context_manifest.json#{source.get('source_id', '')}"],
                        "region": "source",
                    }
                    break
        return best

    def validate_answer_authority(self, question: dict[str, Any], answered_by: str) -> None:
        """SC-1 W-05: the Agent can never fill user-reserved answers."""

        category = str(question.get("category") or "")
        if category in USER_RESERVED_CATEGORIES and str(answered_by or "").strip().lower() in AGENT_ANSWER_SOURCES:
            raise ValueError(
                f"question category '{category}' is reserved for the user; the {answered_by} cannot record this answer"
            )

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
        *, question: dict[str, Any] | None = None,
    ) -> tuple[str, int]:
        attempts = self._attempt_count(root, stage_id, question_id)
        if decision is None:
            return "missing", 0
        if DecisionLog.is_stale(decision, current_input_fingerprint):
            return "stale", min(attempts, 2)
        if self._is_vague_answer(decision.get("answer"), question=question):
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

    def _is_vague_answer(self, answer: Any, *, question: dict[str, Any] | None = None) -> bool:
        if answer is None:
            return True
        if isinstance(answer, str):
            text = answer.strip().lower()
            if not text:
                return True
            # Only a typed boolean or an explicitly yes/no question makes a
            # bare affirmation/negation informative. Open questions retain
            # their follow-up behaviour.
            question = question or {}
            schema = question.get("answer_schema") or {}
            boolean_question = (
                isinstance(schema, dict) and schema.get("type") == "boolean"
            ) or str(question.get("prompt") or "").strip().startswith(("是否", "有无", "有没有"))
            if boolean_question and text in {"yes", "no", "true", "false", "有", "没有", "是", "否"}:
                return False
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


def _extract_keywords(prompt: str) -> list[str]:
    """Latin words + CJK character bigrams, so Chinese prompts match material text."""

    import re

    tokens: list[str] = []
    for word in re.findall(r"[A-Za-z0-9_]+", str(prompt or "")):
        tokens.append(word.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", str(prompt or "")):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


__all__ = ["QuestionResolver", "QuestionGap", "ExitValidation", "USER_RESERVED_CATEGORIES"]
