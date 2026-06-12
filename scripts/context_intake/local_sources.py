from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".json", ".csv", ".tsv"}


def readable_path(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Context file does not exist: {target}")
    if not target.is_file():
        raise ValueError(f"Context path must be a file: {target}")
    if target.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError(f"Context file must be text-like for v1: {target}")
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


def source_record(path: str | Path) -> dict[str, Any]:
    target = readable_path(path)
    text = target.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    stat = target.stat()
    return {
        "source_id": digest[:16],
        "path": str(target),
        "name": target.name,
        "kind": detect_source_kind(target, text),
        "size_bytes": stat.st_size,
        "sha256": digest,
        "summary": summarize_text(text),
        "excerpt": summarize_text(text, limit=900),
    }


def build_context_manifest(context_files: list[str | Path], *, workspace: str = "", run_id: str = "") -> dict[str, Any]:
    if not context_files:
        raise ValueError("At least one --context-file is required.")
    sources = [source_record(path) for path in context_files]
    combined = " ".join(str(source.get("summary", "")) for source in sources)
    return {
        "schema_version": "deck_context_manifest.v1",
        "run_id": run_id,
        "workspace": workspace,
        "strategy": "runtime_reference",
        "sources": sources,
        "summary": summarize_text(combined, limit=600),
        "constraints": [
            "Deck Master v1 references local/exported context only.",
            "No realtime Feishu pull, OpenViking dependency, or long-term note storage is performed.",
        ],
    }
