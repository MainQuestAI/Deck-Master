"""Decision Log (B1).

Append-only decision records under ``workflow/decision_log.jsonl``. Each
answer is bound to the ``input_fingerprint`` of the stage's input artifacts at
the time it was recorded, so an upstream change makes the answer stale and
re-surfaces the question as a gap.

This is the fact source referenced by :mod:`workflow.questions`; the workflow
state resolver and handoff ``blocking_questions`` check consume it to decide
whether a stage may exit.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_decision_record.v1"
LOG_PATH = "workflow/decision_log.jsonl"

SOURCE_USER = "user"
SOURCE_DOC = "approved_document"
SOURCE_ASSUMPTION = "agent_assumption"
SOURCE_POLICY = "system_policy"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class DecisionLog:
    def __init__(self, *, now: datetime | None = None) -> None:
        self._now = now  # if None, real clock

    def _clock(self) -> datetime:
        return self._now or _now()

    def _log_path(self, root: Path) -> Path:
        return root / LOG_PATH

    # --- write ---
    def record(
        self,
        run_dir: str | Path,
        *,
        run_id: str,
        stage_id: str,
        question_id: str,
        answer: Any,
        actor: dict[str, Any],
        required: bool,
        assumption_allowed: bool = False,
        input_fingerprint: str = "",
        source_type: str = SOURCE_USER,
        evidence_refs: list[str] | None = None,
        category: str = "",
    ) -> dict[str, Any]:
        root = Path(run_dir).expanduser().resolve()
        decision = {
            "schema_version": SCHEMA_VERSION,
            "decision_id": f"decision_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "stage_id": stage_id,
            "question_id": question_id,
            "category": category,
            "answer": answer,
            "actor": dict(actor),
            "source_type": source_type,
            "required": bool(required),
            "assumption_allowed": bool(assumption_allowed),
            "evidence_refs": list(evidence_refs or []),
            "input_fingerprint": str(input_fingerprint),
            "created_at": _utc(self._clock()),
        }
        root.joinpath("workflow").mkdir(parents=True, exist_ok=True)
        with self._log_path(root).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(decision, ensure_ascii=False) + "\n")
        return decision

    # --- read ---
    def list(self, run_dir: str | Path, *, stage_id: str | None = None) -> list[dict[str, Any]]:
        root = Path(run_dir).expanduser().resolve()
        path = self._log_path(root)
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if stage_id is not None and rec.get("stage_id") != stage_id:
                continue
            out.append(rec)
        return out

    def latest(
        self, run_dir: str | Path, stage_id: str, question_id: str
    ) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for rec in self.list(run_dir, stage_id=stage_id):
            if rec.get("question_id") != question_id:
                continue
            if latest is None or str(rec.get("created_at", "")) > str(latest.get("created_at", "")):
                latest = rec
        return latest

    @staticmethod
    def is_stale(decision: dict[str, Any], current_input_fingerprint: str) -> bool:
        bound = str(decision.get("input_fingerprint", ""))
        if not bound:
            return True
        return bound != str(current_input_fingerprint)


__all__ = [
    "DecisionLog",
    "SCHEMA_VERSION",
    "SOURCE_USER",
    "SOURCE_DOC",
    "SOURCE_ASSUMPTION",
    "SOURCE_POLICY",
]
