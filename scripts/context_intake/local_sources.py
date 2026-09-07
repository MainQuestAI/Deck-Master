from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".json", ".csv", ".tsv"}
HOST_EXTRACT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUMMARY_LIMIT = 260
EXCERPT_LIMIT = 900

# SC-1 B1/I-01: trailing material must reach candidate extraction. These
# deterministic markers surface tail constraints as *candidates* for the
# Agent; they never pretend the Agent reviewed them.
CONSTRAINT_MARKERS = (
    "必须",
    "不得",
    "不能",
    "禁止",
    "需要",
    "要求",
    "deadline",
    "截止",
    "约束",
    "红线",
    "审批",
    "合规",
    "上线",
    "验收",
)
TAIL_WINDOW_CHARS = 4000


def readable_path(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Context file does not exist: {target}")
    if not target.is_file():
        raise ValueError(f"Context path must be a file: {target}")
    if target.suffix.lower() not in TEXT_EXTENSIONS and target.suffix.lower() not in HOST_EXTRACT_EXTENSIONS:
        raise ValueError(f"Context file type not supported for intake: {target}")
    return target


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def summarize_text(text: str, limit: int = 260) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def detect_source_kind(path: Path, text: str) -> str:
    lowered = f"{path.name}\n{text[:1200]}".lower()
    if any(keyword in lowered for keyword in ("会议", "逐字稿", "transcript", "录音")):
        return "meeting_transcript"
    if any(keyword in lowered for keyword in ("方案", "proposal", "deck", "ppt")):
        return "historical_solution"
    if any(keyword in lowered for keyword in ("wiki", "知识库", "notes")):
        return "knowledge_export"
    return "local_document"


def _constraint_candidates(text: str) -> list[dict[str, Any]]:
    """Extract constraint candidate lines from the FULL text, head and tail.

    Candidates are navigation hints for the Agent (fact_kind
    ``analysis_candidate``); they are not confirmed facts.
    """

    candidates: list[dict[str, Any]] = []
    offset = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        start = offset
        offset += len(raw_line) + 1
        if not line or len(line) > 400:
            continue
        if any(marker in line.lower() for marker in CONSTRAINT_MARKERS):
            candidates.append(
                {
                    "text": line,
                    "char_range": [start, start + len(line)],
                    "region": "tail" if start >= max(0, len(text) - TAIL_WINDOW_CHARS) else "body",
                }
            )
    tail_candidates = [item for item in candidates if item["region"] == "tail"]
    body_candidates = [item for item in candidates if item["region"] != "tail"]
    return (tail_candidates + body_candidates)[:40]


def _reading_registration(text: str | None, *, method: str, failure: str | None = None) -> dict[str, Any]:
    """Register read/unread coverage per source (SC-1 §4.2)."""

    if failure or text is None:
        return {
            "method": method,
            "coverage": "failed",
            "read_ranges": [],
            "unread_ranges": [{"description": "entire source"}],
            "failures": [failure or "source could not be read"],
        }
    length = len(text)
    return {
        "method": method,
        "coverage": "full" if length else "empty",
        "read_ranges": [{"start_char": 0, "end_char": length}],
        "unread_ranges": [],
        "failures": [],
    }


def source_record(path: str | Path) -> dict[str, Any]:
    target = readable_path(path)
    suffix = target.suffix.lower()
    text: str | None = None
    failure: str | None = None
    if suffix in TEXT_EXTENSIONS:
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failure = f"text decode failed: {exc}"
    else:
        failure = (
            f"{suffix} source requires host extraction; no full text read yet"
            if suffix in HOST_EXTRACT_EXTENSIONS
            else "unsupported source type"
        )
    digest_source = text if text is not None else target.read_bytes()
    digest = hashlib.sha256(digest_source if isinstance(digest_source, bytes) else digest_source.encode("utf-8")).hexdigest()
    stat = target.stat()
    summary = summarize_text(text or "") if text is not None else ""
    record: dict[str, Any] = {
        "source_id": digest[:16],
        "path": str(target),
        "name": target.name,
        "kind": detect_source_kind(target, text or ""),
        "media_type": "text" if suffix in TEXT_EXTENSIONS else "host_extract",
        "size_bytes": stat.st_size,
        "sha256": digest,
        # Navigation only (SC-1 §4.2): never a semantic summary of the file.
        "summary_role": "navigation_only",
        "summary": summary,
        "excerpt": summarize_text(text or "", limit=EXCERPT_LIMIT) if text is not None else "",
        "reading": _reading_registration(text, method="direct_text", failure=failure),
    }
    if text is not None:
        record["constraint_candidates"] = _constraint_candidates(text)
    return record


def host_extract_task(source: dict[str, Any]) -> dict[str, Any] | None:
    """Build the host extraction handoff for sources the runtime cannot read."""

    if source.get("media_type") != "host_extract":
        return None
    suffix = Path(source["path"]).suffix.lower()
    return {
        "task_id": f"extract_{source['source_id']}",
        "source_id": source["source_id"],
        "path": source["path"],
        "media_type": suffix.lstrip("."),
        "expected_output": {
            "source_id": source["source_id"],
            "pages_or_sections": [
                {
                    "locator": "page/section identifier",
                    "text": "verbatim extracted text",
                }
            ],
            "unread_ranges": [],
            "failures": [],
        },
    }


def build_context_manifest(
    context_files: list[str | Path],
    *,
    workspace: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    if not context_files:
        raise ValueError("At least one --context-file is required.")
    sources = [source_record(path) for path in context_files]
    combined = " ".join(str(source.get("summary", "")) for source in sources)
    unread = [
        {"source_id": source["source_id"], "reasons": source["reading"]["failures"]}
        for source in sources
        if source["reading"]["coverage"] != "full"
    ]
    tail_constraints = [
        {"source_id": source["source_id"], **candidate}
        for source in sources
        for candidate in source.get("constraint_candidates", [])
        if candidate.get("region") == "tail"
    ]
    manifest = {
        "schema_version": "deck_context_manifest.v1",
        "run_id": run_id,
        "workspace": workspace,
        "strategy": "runtime_reference",
        "sources": sources,
        "summary": summarize_text(combined, limit=600),
        "summary_role": "navigation_only",
        "reading_coverage": {
            "sources_total": len(sources),
            "sources_full": sum(1 for source in sources if source["reading"]["coverage"] == "full"),
            "unread_sources": unread,
        },
        "tail_constraint_candidates": tail_constraints,
        "constraints": [
            "Deck Master v1 references local/exported context only.",
            "No realtime Feishu pull, OpenViking dependency, or long-term note storage is performed.",
            "Summaries are navigation-only; full text stays in the user-authorized location.",
        ],
    }
    extract_tasks = [task for task in (host_extract_task(source) for source in sources) if task]
    if extract_tasks:
        manifest["host_extract_tasks"] = extract_tasks
    return manifest
