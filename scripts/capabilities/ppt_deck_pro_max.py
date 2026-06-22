from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _tasks(task_dir: Path) -> list[dict[str, Any]]:
    index_path = task_dir / "index.json"
    if not index_path.exists():
        return []
    index = _read_json(index_path)
    raw_tasks = index.get("tasks")
    if isinstance(raw_tasks, list):
        return [task for task in raw_tasks if isinstance(task, dict)]
    task_ids = index.get("task_ids")
    if not isinstance(task_ids, list):
        return []
    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        path = task_dir / f"{task_id}.json"
        if path.exists():
            payload = _read_json(path)
            if isinstance(payload, dict):
                tasks.append(payload)
    return tasks


def generate(args: argparse.Namespace) -> int:
    task_dir = Path(args.task_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    run_dir = task_dir.parent
    request_path = run_dir / "request.json"
    run_mode = "production"
    if request_path.exists():
        request = _read_json(request_path)
        run_mode = str(request.get("run_mode") or "production").strip().lower()
    if run_mode not in {"fixture", "dev"}:
        print(
            "Bundled PPT Deck Pro Max adapter is fixture-only. "
            "Use Deck Master Agent dispatch for production generation.",
            file=sys.stderr,
        )
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = run_dir / "generated_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    for task in _tasks(task_dir):
        task_id = str(task.get("task_id") or task.get("beat_id") or "task")
        beat_id = str(task.get("beat_id") or task.get("page_id") or task_id)
        page_dir = assets_dir / beat_id
        page_dir.mkdir(parents=True, exist_ok=True)
        artifact = page_dir / "slide.pptx"
        preview = page_dir / "preview.png"
        artifact.write_bytes(b"deck-master bundled generation placeholder\n")
        preview.write_bytes(b"deck-master bundled generation preview\n")
        result = {
            "schema_version": "deck_generation_result.v1",
            "run_id": args.run_id,
            "session_id": args.session_id,
            "tool": "ppt-deck-pro-max",
            "task_id": task_id,
            "beat_id": beat_id,
            "status": "completed",
            "artifact_path": str(artifact.relative_to(run_dir)),
            "preview_path": str(preview.relative_to(run_dir)),
            "errors": [],
        }
        (output_dir / f"{task_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deck Master bundled PPT Deck Pro Max adapter.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_generate = sub.add_parser("generate")
    p_generate.add_argument("--task-dir", required=True)
    p_generate.add_argument("--output-dir", required=True)
    p_generate.add_argument("--run-id", required=True)
    p_generate.add_argument("--session-id", required=True)
    p_generate.set_defaults(func=generate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
