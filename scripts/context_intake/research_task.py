"""SC-1 B2: gap-driven research task construction and result ingestion.

``deck_research_task.v1`` objects are operational task projections (spec 02
§2.3): they never become a second fact store. Research results flow back
through the same Context Pack / context_manifest channel, carrying
``research_meta`` (task_id, status, summary, open questions) and full source
provenance. Spec 04 §4.6/§4.7: without a real query/reading log a task can
never be marked ``executed``; queries must be redacted before leaving the
machine.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESEARCH_TASK_SCHEMA_VERSION = "deck_research_task.v1"
RESEARCH_STATUSES = {"pending", "executed", "inconclusive", "capability_unavailable"}
DEFAULT_MAX_ROUNDS = 2
DEFAULT_MAX_SOURCES = 6
_REDACT_PATTERNS = (
    re.compile(r"(?<![\w])/(?:Users|home|private|var|etc)/[^\s\"']+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\\\[^\s\"']+"),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redaction_problems(public_query_context: list[str], *, workspace: str = "") -> list[str]:
    """Return redaction violations in the query context that would leave the machine."""

    problems: list[str] = []
    for index, item in enumerate(public_query_context or []):
        text = str(item or "")
        if not text.strip():
            continue
        for pattern in _REDACT_PATTERNS:
            match = pattern.search(text)
            if match:
                problems.append(f"public_query_context[{index}] leaks a local path/email-like token: {match.group(0)[:40]}…")
        if workspace:
            workspace_name = Path(workspace).name
            if workspace_name and workspace_name in text:
                problems.append(f"public_query_context[{index}] references the private workspace name")
    return problems


def build_research_task(
    *,
    question: str,
    affects: list[str],
    source_priority: list[str] | None = None,
    public_query_context: list[str] | None = None,
    freshness_requirement: str = "",
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    max_sources: int = DEFAULT_MAX_SOURCES,
    cost_budget: str = "",
    workspace: str = "",
) -> dict[str, Any]:
    if not str(question or "").strip():
        raise ValueError("research task requires a concrete question")
    if not affects:
        raise ValueError("research task must record which claims/decisions it affects")
    problems = redaction_problems(public_query_context or [], workspace=workspace)
    if problems:
        raise ValueError("unredacted query context: " + "; ".join(problems))
    if max_rounds > DEFAULT_MAX_ROUNDS:
        raise ValueError(f"max_rounds defaults to {DEFAULT_MAX_ROUNDS}; raising it requires an explicit authorized budget")
    return {
        "schema_version": RESEARCH_TASK_SCHEMA_VERSION,
        "task_id": "",
        "question": str(question).strip(),
        "affects": [str(item) for item in affects],
        "source_priority": [str(item) for item in (source_priority or [])],
        "public_query_context": [str(item) for item in (public_query_context or [])],
        "freshness_requirement": str(freshness_requirement or ""),
        "budget": {"max_rounds": int(max_rounds), "max_sources": int(max_sources), "cost_budget": str(cost_budget or "")},
        "terminal_conditions": [
            "direct evidence found for the affected claims",
            "budget exhausted",
            "capability_unavailable",
        ],
        "status": "pending",
        "created_at": _utc_now(),
    }


def validate_research_result(result: dict[str, Any]) -> list[str]:
    """Fail-closed validation: executed requires a real query/reading log."""

    errors: list[str] = []
    status = str(result.get("status") or "").strip().lower()
    if status not in RESEARCH_STATUSES:
        errors.append(f"research status must be one of {sorted(RESEARCH_STATUSES)}")
        return errors
    log = result.get("query_log") if isinstance(result.get("query_log"), list) else []
    if status == "executed" and not log:
        errors.append("research result cannot be executed without a query/reading log")
    if status in {"inconclusive", "executed"}:
        sources = result.get("sources") if isinstance(result.get("sources"), list) else []
        if status == "executed" and not sources:
            errors.append("executed research must record consulted sources")
    return errors


def ingest_research_result(context_manifest: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Merge a validated research result into the context manifest.

    New sources carry provenance (url, accessed_at, excerpt sha256,
    applicability bounds) and fact_kind ``externally_verified_candidate`` —
    the Agent review decides whether it becomes externally_verified.
    """

    errors = validate_research_result(result)
    if errors:
        raise ValueError("invalid research result: " + "; ".join(errors))
    manifest = dict(context_manifest)
    sources = [dict(item) for item in manifest.get("sources", []) if isinstance(item, dict)]
    task_id = str(result.get("task_id") or "")
    for entry in result.get("sources") or []:
        if not isinstance(entry, dict):
            continue
        excerpt = str(entry.get("excerpt") or "")
        source = {
            "source_id": str(entry.get("source_id") or hashlib.sha256(f"{task_id}:{entry.get('url','')}".encode("utf-8")).hexdigest()[:16]),
            "path": "",
            "name": str(entry.get("title") or "research source"),
            "kind": "research",
            "media_type": "web",
            "size_bytes": 0,
            "sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "summary_role": "navigation_only",
            "summary": excerpt[:200],
            "excerpt": excerpt,
            "reading": {
                "method": "host_web_research",
                "coverage": "full" if excerpt else "failed",
                "read_ranges": [],
                "unread_ranges": [] if excerpt else [{"description": "no content captured"}],
                "failures": [] if excerpt else ["no content captured"],
            },
            "provenance": {
                "task_id": task_id,
                "url": str(entry.get("url") or ""),
                "title": str(entry.get("title") or ""),
                "published_at": str(entry.get("published_at") or "unknown"),
                "accessed_at": str(entry.get("accessed_at") or _utc_now()),
                "applicability_bounds": [str(item) for item in (entry.get("applicability_bounds") or [])],
                "fact_kind": "externally_verified_candidate",
            },
        }
        if not any(existing.get("source_id") == source["source_id"] for existing in sources):
            sources.append(source)
    manifest["sources"] = sources
    research_meta_list = [dict(item) for item in manifest.get("research_meta", []) if isinstance(item, dict)]
    research_meta_list.append(
        {
            "task_id": task_id,
            "question": str(result.get("question") or ""),
            "status": str(result.get("status") or ""),
            "result_summary": str(result.get("result_summary") or ""),
            "counter_evidence": [str(item) for item in (result.get("counter_evidence") or [])],
            "open_questions": [str(item) for item in (result.get("open_questions") or [])],
            "recorded_at": _utc_now(),
        }
    )
    manifest["research_meta"] = research_meta_list
    return manifest
