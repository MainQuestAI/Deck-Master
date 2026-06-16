from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from planning.page_tasks import build_page_tasks
from runtime.events import append_event
from runtime.next_step import resolve_next_step
from runtime.run_state import REQUEST_NAME
from runtime.run_state import (
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    SOURCING_PLAN_NAME,
    RunStateError,
    ensure_run_dirs,
    load_request,
    read_json,
    write_json,
)
from runtime.run_state_resolver import resolve_run_state
from validators.companion_tools import validate_render_result


SCHEMA_VERSION = "deck_orchestration_check.v1"
PLAN_IMPORT_SCHEMA = "deck_plan_import.v1"
REQUIRED_SEQUENCE = [
    REQUEST_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    CLAIM_MAP_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    SOURCING_PLAN_NAME,
    PREVIEW_MANIFEST_NAME,
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _quality_reports(root: Path) -> list[str]:
    quality_dir = root / "quality_reports"
    if not quality_dir.is_dir():
        return []
    return sorted(path.name for path in quality_dir.glob("*_gate.json"))


def orchestration_check(
    run_dir: str | Path,
    *,
    cli_workspace: str | None = None,
    run_mode: str | None = None,
    dev_allow_unsetup: bool = False,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    state = resolve_run_state(
        root,
        cli_workspace=cli_workspace,
        run_mode=run_mode,
        dev_allow_unsetup=dev_allow_unsetup,
    )
    run_id = str(state.get("run_id") or root.name)

    stage = str(state.get("stage") or "")
    reasons = [entry.get("reason", "") for entry in state.get("blocked_actions", []) if entry.get("reason")]
    if stage in {"ready_for_client_export", "ready_for_benchmark"}:
        status = "ready_for_external_production"
    elif stage == "needs_draft_gate":
        status = "needs_quality_gate"
    elif stage == "blocked_workspace":
        status = "blocked"
    else:
        status = "blocked"

    missing = [name for name in REQUIRED_SEQUENCE if not (root / name).exists()]
    if status == "blocked":
        for name in REQUIRED_SEQUENCE:
            if name == PREVIEW_MANIFEST_NAME and state.get("stage") == "needs_preview" and name not in missing:
                continue
    quality = _quality_reports(root)
    allowed = {
        "external_generation_allowed": status == "ready_for_external_production",
        "external_review_allowed": status in {"ready_for_external_production", "blocked"},
        "client_export_allowed": status == "ready_for_external_production",
        "benchmark_rc_allowed": state.get("stage") == "ready_for_benchmark",
    }
    next_step = resolve_next_step(
        root,
        cli_workspace=cli_workspace,
        run_mode=run_mode,
        dev_allow_unsetup=dev_allow_unsetup,
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_dir": str(root),
        "status": status,
        "missing_artifacts": missing,
        "quality_reports": quality,
        "next_command": next_step.get("next_command", ""),
        "next_step_status": next_step.get("status", ""),
        "allow_external_production": status == "ready_for_external_production",
        "policy": allowed,
        "reasons": reasons,
    }
    append_event(
        root,
        "orchestration.checked",
        target=run_id,
        payload_ref="",
        data={
            "status": status,
            "missing_artifacts": missing,
            "allow_external_production": status == "ready_for_external_production",
        },
    )
    return result


def import_plan(run_dir: str | Path, input_path: str | Path, *, source: str) -> dict[str, Any]:
    if source not in {"human", "agent"}:
        raise RunStateError("--source must be 'human' or 'agent'.")

    root = ensure_run_dirs(run_dir)
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise RunStateError(f"Plan input not found: {input_file}")

    request = load_request(root)
    run_id = str(request.get("run_id") or root.name)
    title = str(request.get("project_name") or request.get("business_goal") or run_id)

    if input_file.suffix.lower() == ".json":
        narrative_plan, page_tasks = _load_json_plan(input_file, run_id=run_id, title=title)
    else:
        narrative_plan, page_tasks = _load_markdown_plan(input_file, run_id=run_id, title=title)

    backup_dir = root / "overrides" / f"plan_{_utc_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in (NARRATIVE_PLAN_NAME, PAGE_TASKS_NAME):
        current = root / name
        if current.exists():
            shutil.copy2(current, backup_dir / name)

    write_json(root / NARRATIVE_PLAN_NAME, narrative_plan)
    write_json(root / PAGE_TASKS_NAME, page_tasks)
    append_event(
        root,
        "plan.override.imported",
        target=run_id,
        payload_ref=str(input_file),
        data={
            "source": source,
            "input": str(input_file),
            "backup_dir": str(backup_dir),
            "beats": len(narrative_plan.get("beats", [])),
            "tasks": len(page_tasks.get("tasks", [])),
        },
    )
    return {
        "schema_version": PLAN_IMPORT_SCHEMA,
        "status": "imported",
        "run_id": run_id,
        "run_dir": str(root),
        "source": source,
        "input": str(input_file),
        "backup_dir": str(backup_dir),
        "beats": len(narrative_plan.get("beats", [])),
        "tasks": len(page_tasks.get("tasks", [])),
    }


def import_render_result(run_dir: str | Path, input_path: str | Path) -> dict[str, Any]:
    root = ensure_run_dirs(run_dir)
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise RunStateError(f"Render result not found: {input_file}")
    result = read_json(input_file)
    validation = validate_render_result(result)
    if not validation["valid"]:
        raise RunStateError("Invalid render result: " + "; ".join(validation["errors"]))
    request = load_request(root)
    run_id = str(request.get("run_id") or root.name)
    if str(result.get("run_id") or "") != run_id:
        raise RunStateError(f"render result run_id mismatch: got {result.get('run_id')}, expected {run_id}.")

    results_dir = root / "external_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    target = results_dir / "render_result.json"
    write_json(target, result)
    preview_updated = _update_preview_from_render_result(root, result)
    append_event(
        root,
        "external_result.imported",
        target=run_id,
        payload_ref=str(target.relative_to(root)),
        data={
            "tool": result.get("tool", "ppt-master"),
            "status": result.get("status", ""),
            "artifact_path": result.get("artifact_path", ""),
            "preview_dir": result.get("preview_dir", ""),
            "preview_manifest_updated": preview_updated,
        },
    )
    return {
        "status": "imported",
        "run_id": run_id,
        "result": str(target),
        "artifact_path": result.get("artifact_path", ""),
        "preview_dir": result.get("preview_dir", ""),
        "preview_manifest_updated": preview_updated,
    }


def _update_preview_from_render_result(root: Path, result: dict[str, Any]) -> bool:
    preview_path = root / PREVIEW_MANIFEST_NAME
    if not preview_path.exists():
        return False
    preview = read_json(preview_path)
    preview["render_status"] = result.get("status", "")
    preview["final_artifact_path"] = result.get("artifact_path", "")
    preview["final_preview_dir"] = result.get("preview_dir", "")
    preview["external_render_result"] = "external_results/render_result.json"
    if result.get("page_count") is not None:
        preview["render_page_count"] = result.get("page_count")

    page_updates = result.get("page_previews", [])
    if isinstance(page_updates, list):
        for update in page_updates:
            if not isinstance(update, dict):
                continue
            key = str(update.get("page_id") or update.get("beat_id") or "")
            new_preview = str(update.get("preview_path") or "")
            if not key or not new_preview:
                continue
            preview_ref = Path(new_preview)
            if preview_ref.is_absolute() or ".." in preview_ref.parts:
                raise RunStateError(f"render preview_path must be run-relative: {new_preview}")
            for page in preview.get("pages", []):
                if not isinstance(page, dict):
                    continue
                if key in {str(page.get("page_id") or ""), str(page.get("beat_id") or "")}:
                    previous = page.get("preview_path", "")
                    if previous and previous != new_preview:
                        page["previous_preview_path"] = previous
                    page["preview_path"] = new_preview
                    page["render_status"] = result.get("status", "")
                    break

    write_json(preview_path, preview)
    return True


def _load_json_plan(input_file: Path, *, run_id: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = read_json(input_file)
    narrative_plan = payload.get("narrative_plan", payload)
    if not isinstance(narrative_plan, dict) or not isinstance(narrative_plan.get("beats"), list):
        raise RunStateError("JSON plan must contain narrative_plan.beats or beats.")
    narrative_plan["run_id"] = run_id
    narrative_plan.setdefault("title", title)

    page_tasks = payload.get("page_tasks")
    if not isinstance(page_tasks, dict):
        page_tasks = build_page_tasks(narrative_plan, {"run_id": run_id, "claims": []})
    page_tasks["run_id"] = run_id
    return narrative_plan, page_tasks


def _load_markdown_plan(input_file: Path, *, run_id: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]:
    text = input_file.read_text(encoding="utf-8")
    headings = _extract_page_headings(text)
    if not headings:
        raise RunStateError("Markdown plan must contain page headings like '## 01 ...'.")

    beats: list[dict[str, Any]] = []
    for index, heading in enumerate(headings, start=1):
        role = _infer_role(index, len(headings), heading)
        beat_id = f"beat_{index:02d}_{role}"
        beats.append(
            {
                "beat_id": beat_id,
                "role": role,
                "title": heading,
                "generation_brief": f"根据人工校准规划生成页面：{heading}",
                "reuse_query": heading,
            }
        )

    narrative_plan = {
        "run_id": run_id,
        "title": title,
        "target_pages": len(beats),
        "audience": "client",
        "industry": "",
        "density": "high",
        "roles": [beat["role"] for beat in beats],
        "beats": beats,
        "gaps": [],
    }
    return narrative_plan, build_page_tasks(narrative_plan, {"run_id": run_id, "claims": []})


def _extract_page_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("## "):
            continue
        label = stripped[3:].strip()
        if re.match(r"^(第?\s*)?\d{1,2}[\.、｜|:\s-]", label) or "页" in label[:8]:
            headings.append(label)
    return headings


def _infer_role(index: int, total: int, title: str) -> str:
    value = title.lower()
    if index == 1:
        return "opener"
    if index == total:
        return "cta"
    if any(token in title for token in ("背景", "问题", "挑战", "监管")):
        return "problem"
    if any(token in title for token in ("架构", "底座", "系统", "流程")):
        return "architecture"
    if any(token in title for token in ("价值", "收益", "验收")):
        return "roi"
    if "case" in value or "案例" in title:
        return "case"
    return "solution"
