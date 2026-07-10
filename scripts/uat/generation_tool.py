from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from generation.handback import RESULT_SCHEMA_VERSION, VALID_STATUSES, validate_generation_result
from uat.report import build_check, build_uat_report, write_uat_report


REPORT_NAME = "generation_tool_uat"
TASKS_DIR = "generation_tasks"
RESULTS_DIR = "generation_results"


def run_generation_tool_uat(
    run_dir: Path,
    *,
    tool: str = "ppt-deck-pro-max",
    require_preview: bool = False,
    require_artifact: bool = False,
    sample_limit: int | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Validate generation task/result handback contracts without calling generation tools."""
    run_dir = Path(run_dir).expanduser().resolve()
    checks: list[dict[str, Any]] = []
    recommendations: list[str] = []
    run_id = _run_id(run_dir)

    tasks, task_ids = _load_tasks(run_dir, checks, run_id)
    if sample_limit and sample_limit > 0:
        tasks = tasks[:sample_limit]
        task_ids = set(list(task_ids)[:sample_limit])

    enhanced_task_count = 0
    for index, task in enumerate(tasks):
        ref_id = str(task.get("task_id") or task.get("beat_id") or f"task_{index}")
        _check_task(checks, task, ref_id, run_id)
        if all(task.get(field) for field in ("workspace_refs", "quality_requirements", "expected_outputs")):
            enhanced_task_count += 1

    results = _load_results(run_dir, checks)
    known_task_ids = {str(task.get("task_id", "")) for task in tasks if task.get("task_id")}
    known_task_ids.update(task_ids)

    completed_count = 0
    failed_count = 0
    partial_count = 0
    preview_count = 0
    artifact_count = 0
    for path, result in results:
        status = str(result.get("status", ""))
        completed_count += 1 if status == "completed" else 0
        failed_count += 1 if status == "failed" else 0
        partial_count += 1 if status == "partial" else 0
        preview_count += 1 if result.get("preview_path") else 0
        artifact_count += 1 if result.get("artifact_path") else 0
        _check_result(
            checks,
            run_dir,
            path,
            result,
            run_id=run_id,
            known_task_ids=known_task_ids,
            require_preview=require_preview,
            require_artifact=require_artifact,
        )

    preview_refresh_updated = _check_preview_refresh_readiness(run_dir, checks) if results else 0
    output_denominator = max(completed_count + partial_count, 1)
    metrics = {
        "schema_version": "deck_generation_tool_uat_metrics.v1",
        "task_count": len(tasks),
        "enhanced_task_count": enhanced_task_count,
        "result_count": len(results),
        "completed_count": completed_count,
        "failed_count": failed_count,
        "partial_count": partial_count,
        "preview_refresh_updated": preview_refresh_updated,
        "preview_asset_coverage": round(preview_count / output_denominator, 2),
        "artifact_coverage": round(artifact_count / output_denominator, 2),
    }

    if not tasks:
        recommendations.append("Run create-generation-tasks before generation tool UAT.")
    if not results:
        recommendations.append("Place generation result JSON files under generation_results/ when external generation output is ready.")
    if require_preview and preview_count < completed_count:
        recommendations.append("Completed generation results should include preview_path.")
    if require_artifact and artifact_count < completed_count:
        recommendations.append("Completed generation results should include artifact_path.")

    report = build_uat_report(
        run_dir,
        tool,
        checks,
        metrics,
        recommendations,
        schema_version="deck_generation_tool_uat.v1",
    )
    return write_uat_report(run_dir, REPORT_NAME, report) if write else report


def build_generation_tool_uat_report(
    run_dir: str | Path,
    *,
    tool: str = "ppt-deck-pro-max",
    require_preview: bool = False,
    require_artifact: bool = False,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    return run_generation_tool_uat(
        Path(run_dir),
        tool=tool,
        require_preview=require_preview,
        require_artifact=require_artifact,
        sample_limit=sample_limit,
        write=False,
    )


def write_generation_tool_uat_report(
    run_dir: str | Path,
    *,
    tool: str = "ppt-deck-pro-max",
    require_preview: bool = False,
    require_artifact: bool = False,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    return run_generation_tool_uat(
        Path(run_dir),
        tool=tool,
        require_preview=require_preview,
        require_artifact=require_artifact,
        sample_limit=sample_limit,
        write=True,
    )


def _load_tasks(run_dir: Path, checks: list[dict[str, Any]], run_id: str) -> tuple[list[dict[str, Any]], set[str]]:
    index_path = run_dir / TASKS_DIR / "index.json"
    checks.append(build_check("generation_tasks_index_exists", index_path.exists(), "error", "generation_tasks/index.json missing.", refs=[TASKS_DIR + "/index.json"]))
    if not index_path.exists():
        return [], set()
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        checks.append(build_check("generation_tasks_index_readable", isinstance(index, dict), "error", "generation task index JSON is readable.", refs=[TASKS_DIR + "/index.json"]))
    except json.JSONDecodeError as exc:
        checks.append(build_check("generation_tasks_index_readable", False, "error", f"Bad JSON: {exc.msg}", refs=[TASKS_DIR + "/index.json"]))
        return [], set()
    if not isinstance(index, dict):
        return [], set()

    checks.append(build_check("generation_tasks_index_schema_version", bool(index.get("schema_version")), "warning", "generation task index should include schema_version.", refs=[TASKS_DIR + "/index.json"]))
    if index.get("run_id"):
        checks.append(build_check("generation_tasks_index_run_id", str(index.get("run_id")) == run_id, "error", f"index run_id is {index.get('run_id')}, expected {run_id}.", refs=[TASKS_DIR + "/index.json"]))

    raw_tasks = index.get("tasks")
    raw_task_ids = index.get("task_ids")
    has_tasks = isinstance(raw_tasks, list) and bool(raw_tasks)
    has_task_ids = isinstance(raw_task_ids, list) and bool(raw_task_ids)
    checks.append(build_check("generation_tasks_index_has_tasks", has_tasks or has_task_ids, "error", "generation task index must include tasks[] or task_ids[].", refs=[TASKS_DIR + "/index.json"]))

    tasks: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    embedded_by_id: dict[str, dict[str, Any]] = {}
    if has_tasks:
        for item in raw_tasks:
            if isinstance(item, dict):
                if item.get("task_id"):
                    task_id = str(item["task_id"])
                    task_ids.add(task_id)
                    embedded_by_id[task_id] = item
                else:
                    tasks.append(item)
            elif isinstance(item, str):
                task_ids.add(item)
    if has_task_ids:
        task_ids.update(str(item) for item in raw_task_ids if item)

    for task_id in sorted(task_ids):
        task_path = run_dir / TASKS_DIR / f"{task_id}.json"
        if not task_path.exists():
            embedded = embedded_by_id.get(task_id)
            embedded_complete = bool(embedded and embedded.get("schema_version") and embedded.get("run_id"))
            checks.append(build_check(f"generation_task_file_{task_id}", embedded_complete, "error", f"{task_id}.json missing.", refs=[str(task_path.relative_to(run_dir))]))
            if embedded is not None:
                tasks.append(embedded)
            continue
        checks.append(build_check(f"generation_task_file_{task_id}", True, "error", f"{task_id}.json exists.", refs=[str(task_path.relative_to(run_dir))]))
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append(build_check(f"generation_task_json_{task_id}", False, "error", f"Bad JSON: {exc.msg}", refs=[str(task_path.relative_to(run_dir))]))
            continue
        if isinstance(task, dict):
            tasks.append(task)
    return tasks, task_ids


def _check_task(checks: list[dict[str, Any]], task: dict[str, Any], ref_id: str, run_id: str) -> None:
    ref = f"{TASKS_DIR}/{ref_id}.json"
    checks.append(build_check(f"{ref_id}.schema_version", bool(task.get("schema_version")), "error", f"{ref_id} missing schema_version.", refs=[ref]))
    checks.append(build_check(f"{ref_id}.run_id", bool(task.get("run_id")), "error", f"{ref_id} missing run_id.", refs=[ref]))
    if task.get("run_id"):
        checks.append(build_check(f"{ref_id}.run_id_match", str(task.get("run_id")) == run_id, "error", f"{ref_id} run_id is {task.get('run_id')}, expected {run_id}.", refs=[ref]))
    checks.append(build_check(f"{ref_id}.identity", bool(task.get("task_id") or task.get("beat_id")), "error", f"{ref_id} missing task_id/beat_id.", refs=[ref]))
    for field in ("generation_brief", "workspace_refs", "quality_requirements", "expected_outputs"):
        checks.append(build_check(f"{ref_id}.{field}", bool(task.get(field)), "warning", f"{ref_id} missing {field}.", refs=[ref]))


def _load_results(run_dir: Path, checks: list[dict[str, Any]]) -> list[tuple[Path, dict[str, Any]]]:
    results_dir = run_dir / RESULTS_DIR
    if not results_dir.exists():
        checks.append(build_check("generation_results_optional", True, "info", "generation_results/ not present yet.", refs=[RESULTS_DIR + "/"]))
        return []
    checks.append(build_check("generation_results_exists", True, "warning", "generation_results/ exists.", refs=[RESULTS_DIR + "/"]))
    results: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append(build_check(f"generation_result_{path.stem}_readable", False, "error", f"Bad JSON: {exc.msg}", refs=[str(path.relative_to(run_dir))]))
            continue
        if isinstance(result, dict):
            checks.append(build_check(f"generation_result_{path.stem}_readable", True, "error", "generation result JSON is readable.", refs=[str(path.relative_to(run_dir))]))
            results.append((path, result))
    return results


def _check_result(
    checks: list[dict[str, Any]],
    run_dir: Path,
    path: Path,
    result: dict[str, Any],
    *,
    run_id: str,
    known_task_ids: set[str],
    require_preview: bool,
    require_artifact: bool,
) -> None:
    ref = str(path.relative_to(run_dir))
    validation = validate_generation_result(result, run_dir=run_dir)
    checks.append(build_check(f"{path.stem}.base_contract", validation.get("valid", False), "error", "; ".join(validation.get("errors", [])) or "generation result base contract ok.", refs=[ref]))
    checks.append(build_check(f"{path.stem}.schema_version", result.get("schema_version") == RESULT_SCHEMA_VERSION, "error", f"schema_version must be {RESULT_SCHEMA_VERSION}.", refs=[ref]))
    if result.get("run_id"):
        checks.append(build_check(f"{path.stem}.run_id_match", str(result.get("run_id")) == run_id, "error", f"result run_id is {result.get('run_id')}, expected {run_id}.", refs=[ref]))
    task_id = str(result.get("task_id") or "")
    if task_id:
        checks.append(build_check(f"{path.stem}.task_id_known", task_id in known_task_ids, "error", f"task_id {task_id} must exist in generation tasks.", refs=[ref]))
    status = str(result.get("status") or "")
    checks.append(build_check(f"{path.stem}.status", status in VALID_STATUSES, "error", f"status must be one of {sorted(VALID_STATUSES)}.", refs=[ref]))
    if status == "completed":
        checks.append(build_check(f"{path.stem}.completed_output", bool(result.get("preview_path") or result.get("artifact_path")), "error", "completed result needs preview_path or artifact_path.", refs=[ref]))
    if status == "failed":
        checks.append(build_check(f"{path.stem}.failed_errors", bool(result.get("errors")), "error", "failed result needs errors[].", refs=[ref]))
    _check_run_relative_path(checks, run_dir, result.get("preview_path"), f"{path.stem}.preview_path", "preview_path", require_preview and status == "completed", ref)
    _check_run_relative_path(checks, run_dir, result.get("artifact_path"), f"{path.stem}.artifact_path", "artifact_path", require_artifact and status == "completed", ref)


def _check_run_relative_path(
    checks: list[dict[str, Any]],
    run_dir: Path,
    value: Any,
    check_id: str,
    label: str,
    required: bool,
    ref: str,
) -> None:
    if not value:
        if required:
            checks.append(build_check(f"{check_id}_present", False, "error", f"{label} is required.", refs=[ref]))
        return
    path = Path(str(value))
    run_relative = not path.is_absolute() and ".." not in path.parts
    resolved = (run_dir / path).resolve() if run_relative else None
    if resolved is not None:
        root_text = str(run_dir)
        resolved_text = str(resolved)
        run_relative = resolved_text == root_text or resolved_text.startswith(root_text + os.sep)
    location_check_id = f"{check_id}_run_relative" if run_relative else f"{check_id}_outside_run"
    checks.append(build_check(location_check_id, run_relative, "error", f"{label} must be run-relative and stay inside run_dir.", refs=[ref]))
    if run_relative and resolved is not None:
        exists = resolved.exists()
        checks.append(build_check(f"{check_id}_exists", exists, "error" if required else "warning", f"{label} not found: {value}.", refs=[str(value)]))


def _check_preview_refresh_readiness(run_dir: Path, checks: list[dict[str, Any]]) -> int:
    try:
        from generation.handback import refresh_preview_from_generation

        refresh_available = callable(refresh_preview_from_generation)
    except Exception:
        refresh_available = False
    checks.append(build_check("refresh_preview_from_generation_available", refresh_available, "error", "refresh-preview-from-generation function unavailable."))

    preview_path = run_dir / "preview_manifest.json"
    checks.append(build_check("preview_manifest_exists", preview_path.exists(), "warning", "preview_manifest.json missing.", refs=["preview_manifest.json"]))
    if not preview_path.exists():
        return 0
    try:
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        checks.append(build_check("preview_manifest_readable", False, "error", f"Bad JSON: {exc.msg}", refs=["preview_manifest.json"]))
        return 0
    pages = preview.get("pages", []) if isinstance(preview, dict) else []
    generated_pages = [page for page in pages if isinstance(page, dict) and page.get("source_type") == "generated"]
    checks.append(build_check("generated_pages_source_type", bool(generated_pages), "warning", "No preview pages currently have source_type=generated.", refs=["preview_manifest.json"]))
    if generated_pages:
        checks.append(build_check("generated_pages_generation_status", all(page.get("generation_status") for page in generated_pages), "warning", "generated pages should include generation_status.", refs=["preview_manifest.json"]))
        checks.append(build_check("generated_pages_previous_preview_path", all(page.get("previous_preview_path") for page in generated_pages), "warning", "generated pages should preserve previous_preview_path when replaced.", refs=["preview_manifest.json"]))
    return len(generated_pages)


def _run_id(run_dir: Path) -> str:
    request_path = run_dir / "request.json"
    if request_path.exists():
        try:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            if isinstance(request, dict) and request.get("run_id"):
                return str(request["run_id"])
        except json.JSONDecodeError:
            return run_dir.name
    return run_dir.name
