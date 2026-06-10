from __future__ import annotations

from pathlib import Path
from typing import Any

from quality.gate_runner import evaluate_draft_gate, markdown_report, write_gate_report


def severity_for_flags(flags: list[str]) -> str:
    if any(flag in {"missing_core_claim", "evidence_gap"} for flag in flags):
        return "P1"
    return "P2"


def evaluate_draft(
    deck_brief: dict[str, Any],
    claim_map: dict[str, Any],
    page_tasks: dict[str, Any],
) -> dict[str, Any]:
    return evaluate_draft_gate(deck_brief, claim_map, page_tasks)


def write_draft_gate_report(run_dir: str | Path, report: dict[str, Any]) -> dict[str, str]:
    return write_gate_report(run_dir, "draft", report)
