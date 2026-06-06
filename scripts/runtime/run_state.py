from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.events import append_event


REQUEST_NAME = "request.json"
NARRATIVE_PLAN_NAME = "narrative_plan.json"
SOURCING_PLAN_NAME = "sourcing_plan.json"
PREVIEW_MANIFEST_NAME = "preview_manifest.json"


class RunStateError(ValueError):
    pass


def slugify(value: str, fallback: str = "deck-run") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-").lower()
    return slug[:80] or fallback


def make_run_id(title: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{stamp}-{slugify(title)}"


def read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunStateError(f"Missing JSON file: {target}") from exc
    except json.JSONDecodeError as exc:
        raise RunStateError(f"Invalid JSON in {target}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise RunStateError(f"JSON file must contain an object: {target}")
    return data


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def ensure_run_dirs(run_dir: str | Path) -> Path:
    root = Path(run_dir).expanduser().resolve()
    for name in ("library_results/by_beat", "generation_tasks", "links", "notes", "placeholders"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def create_run(base_dir: str | Path, request: dict[str, Any], *, run_id: str | None = None, force: bool = False) -> Path:
    title = str(request.get("project_name") or request.get("business_goal") or "Deck Master Run")
    actual_run_id = run_id or str(request.get("run_id") or make_run_id(title))
    request["run_id"] = actual_run_id
    root = Path(base_dir).expanduser().resolve() / actual_run_id
    if root.exists() and any(root.iterdir()) and not force:
        raise RunStateError(f"Run already exists. Use --force to replace: {root}")
    if force and root.exists():
        for child in root.iterdir():
            if child.is_dir() and not child.is_symlink():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()
    ensure_run_dirs(root)
    write_json(root / REQUEST_NAME, request)
    append_event(root, "run.created", target=actual_run_id, payload_ref=REQUEST_NAME)
    return root


def load_request(run_dir: str | Path) -> dict[str, Any]:
    return read_json(Path(run_dir).expanduser().resolve() / REQUEST_NAME)


def write_artifact(run_dir: str | Path, filename: str, payload: dict[str, Any], *, action: str) -> Path:
    root = ensure_run_dirs(run_dir)
    path = write_json(root / filename, payload)
    append_event(root, action, target=filename, payload_ref=filename)
    return path


def run_status(run_dir: str | Path) -> str:
    root = Path(run_dir).expanduser().resolve()
    if (root / PREVIEW_MANIFEST_NAME).exists():
        return "preview_ready"
    if (root / SOURCING_PLAN_NAME).exists():
        return "sourcing_ready"
    if (root / NARRATIVE_PLAN_NAME).exists():
        return "planned"
    if (root / REQUEST_NAME).exists():
        return "request_ready"
    return "pending"
