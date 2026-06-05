from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OUTCOMES = {"won", "lost", "unknown"}


def load_queue(queue_path: Path) -> dict[str, Any]:
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Queue file not found: {queue_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid queue JSON: {exc.msg}") from exc
    if "run_id" not in queue or "pages" not in queue:
        raise ValueError("Queue must include run_id and pages.")
    if not isinstance(queue["pages"], list):
        raise ValueError("Queue pages must be a list.")
    return queue


def slide_key(page: dict[str, Any]) -> str:
    source_pptx = page.get("source_pptx")
    source_slide_index = page.get("source_slide_index")
    if source_pptx and source_slide_index != "":
        return f"library::{source_pptx}::{source_slide_index}"
    source_project = page.get("source_project")
    if source_project:
        return f"generated::{source_project}::{page['page_id']}"
    return f"page::{page['page_id']}"


def record_deal(
    queue_path: Path,
    log_path: Path,
    deal_id: str,
    outcome: str,
    notes: str = "",
) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError(f"Invalid outcome: {outcome}")
    queue = load_queue(queue_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "deal_id": deal_id,
        "outcome": outcome,
        "notes": notes,
        "run_id": queue["run_id"],
        "title": queue.get("title", ""),
        "pages": [
            {
                "page_id": page["page_id"],
                "order": page["order"],
                "title": page.get("title", page["page_id"]),
                "source_type": page["source_type"],
                "slide_key": slide_key(page),
                "source_pptx": page.get("source_pptx", ""),
                "source_slide_index": page.get("source_slide_index", ""),
                "source_project": page.get("source_project", ""),
                "narrative_role": page.get("narrative_role", ""),
            }
            for page in queue["pages"]
        ],
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def summarize(log_path: Path) -> dict[str, Any]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"uses": 0, "wins": 0, "losses": 0, "unknown": 0, "titles": set(), "source_type": ""}
    )
    if not log_path.exists():
        return {"slides": []}

    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        outcome = record.get("outcome", "unknown")
        for page in record.get("pages", []):
            item = stats[page["slide_key"]]
            item["uses"] += 1
            if outcome == "won":
                item["wins"] += 1
            elif outcome == "lost":
                item["losses"] += 1
            else:
                item["unknown"] += 1
            item["titles"].add(page.get("title", page["page_id"]))
            item["source_type"] = page.get("source_type", "")

    slides = []
    for key, item in stats.items():
        decided = item["wins"] + item["losses"]
        win_rate = item["wins"] / decided if decided else None
        slides.append(
            {
                "slide_key": key,
                "source_type": item["source_type"],
                "titles": sorted(item["titles"]),
                "uses": item["uses"],
                "wins": item["wins"],
                "losses": item["losses"],
                "unknown": item["unknown"],
                "win_rate": win_rate,
            }
        )
    slides.sort(key=lambda item: (item["win_rate"] is None, -(item["win_rate"] or 0), -item["uses"], item["slide_key"]))
    return {"slides": slides}


def main() -> None:
    parser = argparse.ArgumentParser(description="Record and summarize Deck Master slide deal outcomes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="Append one deal outcome record.")
    record_parser.add_argument("queue", help="Queue JSON exported by scripts/orchestrate/export_queue.py")
    record_parser.add_argument("--log", default="feedback/deal_results.jsonl")
    record_parser.add_argument("--deal-id", required=True)
    record_parser.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    record_parser.add_argument("--notes", default="")

    summary_parser = subparsers.add_parser("summary", help="Summarize recorded slide outcomes.")
    summary_parser.add_argument("--log", default="feedback/deal_results.jsonl")

    args = parser.parse_args()
    try:
        if args.command == "record":
            payload = record_deal(Path(args.queue), Path(args.log), args.deal_id, args.outcome, args.notes)
        else:
            payload = summarize(Path(args.log))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
