from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from uat.report import build_check, build_uat_report, write_uat_report
from validators.companion_tools import validate_render_result


REPORT_NAME = "render_tool_uat"
RENDER_RESULT_SCHEMA_VERSION = "deck_render_result.v1"
VALID_STATUSES = {"completed", "partial", "failed"}


def run_render_tool_uat(
    run_dir: Path,
    *,
    input_path: Path | None = None,
    artifact_path: Path | None = None,
    tool: str = "ppt-master",
    allow_external: bool = False,
    write: bool = True,
) -> dict[str, Any]:
    """Validate render result or direct artifact readiness without calling a renderer."""
    run_dir = Path(run_dir).expanduser().resolve()
    checks: list[dict[str, Any]] = []
    recommendations: list[str] = []
    run_id = _run_id(run_dir)

    render_result: dict[str, Any] | None = None
    result_artifact: str | Path | None = artifact_path
    page_count: int | None = None

    if input_path is not None:
        render_result = _load_render_result(run_dir, Path(input_path), checks)
        if render_result is not None:
            _check_render_result(checks, run_dir, render_result, run_id=run_id, allow_external=allow_external)
            result_artifact = result_artifact or render_result.get("artifact_path")
            if isinstance(render_result.get("page_count"), int):
                page_count = render_result["page_count"]
            if render_result.get("preview_dir"):
                _check_preview_dir(checks, run_dir, str(render_result["preview_dir"]), allow_external=allow_external)
    elif artifact_path is None:
        checks.append(build_check("render_input_present", False, "error", "input_path or artifact_path is required."))

    artifact_exists = False
    if result_artifact:
        _, artifact_exists = _check_artifact(checks, run_dir, result_artifact, allow_external=allow_external)

    expected_page_count = _expected_page_count(run_dir)
    page_count_delta = None
    if page_count is not None and expected_page_count > 0:
        page_count_delta = page_count - expected_page_count
        checks.append(build_check("page_count_delta", page_count_delta == 0, "warning", f"page_count delta is {page_count_delta}; expected {expected_page_count}."))
    elif expected_page_count > 0:
        checks.append(build_check("page_count_available", False, "warning", "render_result should include page_count."))

    render_gate_status = _check_callable(checks, "render_gate_available", "quality.gate_runner", "evaluate_render_gate")
    delivery_validation_status = _check_callable(checks, "delivery_validation_available", "delivery.validate", "validate_delivery")
    checks.append(
        build_check(
            "final_version_lineage_can_generate",
            artifact_exists and delivery_validation_status == "available",
            "warning",
            "final_version_lineage can be generated when artifact exists and delivery validation is available.",
        )
    )

    metrics = {
        "schema_version": "deck_render_tool_uat_metrics.v1",
        "artifact_exists": artifact_exists,
        "page_count": page_count,
        "expected_page_count": expected_page_count,
        "page_count_delta": page_count_delta,
        "render_gate_status": render_gate_status,
        "delivery_validation_status": delivery_validation_status,
    }

    if not artifact_exists:
        recommendations.append("Provide an existing artifact_path inside run_dir, or allow external artifacts explicitly.")
    if page_count_delta not in (None, 0):
        recommendations.append("Review render output page_count against approved queue before delivery.")
    if render_result is None and input_path is None:
        recommendations.append("Prefer render_result JSON so Deck Master can validate run_id, status, preview_dir, and page_count.")

    report = build_uat_report(
        run_dir,
        tool,
        checks,
        metrics,
        recommendations,
        schema_version="deck_render_tool_uat.v1",
    )
    return write_uat_report(run_dir, REPORT_NAME, report) if write else report


def build_render_tool_uat_report(
    run_dir: str | Path,
    *,
    input_path: str | Path | None = None,
    artifact_path: str | Path | None = None,
    tool: str = "ppt-master",
    allow_external: bool = False,
) -> dict[str, Any]:
    return run_render_tool_uat(
        Path(run_dir),
        input_path=Path(input_path) if input_path is not None else None,
        artifact_path=Path(artifact_path) if artifact_path is not None else None,
        tool=tool,
        allow_external=allow_external,
        write=False,
    )


def write_render_tool_uat_report(
    run_dir: str | Path,
    *,
    input_path: str | Path | None = None,
    artifact_path: str | Path | None = None,
    tool: str = "ppt-master",
    allow_external: bool = False,
) -> dict[str, Any]:
    return run_render_tool_uat(
        Path(run_dir),
        input_path=Path(input_path) if input_path is not None else None,
        artifact_path=Path(artifact_path) if artifact_path is not None else None,
        tool=tool,
        allow_external=allow_external,
        write=True,
    )


def _load_render_result(run_dir: Path, input_path: Path, checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    path = input_path.expanduser()
    if not path.is_absolute():
        path = run_dir / path
    path = path.resolve()
    ref = _ref(run_dir, path)
    checks.append(build_check("render_result_json_exists", path.exists(), "error", "render_result JSON missing.", refs=[ref]))
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        checks.append(build_check("render_result_json_readable", False, "error", f"Bad JSON: {exc.msg}", refs=[ref]))
        return None
    checks.append(build_check("render_result_json_readable", isinstance(payload, dict), "error", "render_result JSON must be an object.", refs=[ref]))
    return payload if isinstance(payload, dict) else None


def _check_render_result(
    checks: list[dict[str, Any]],
    run_dir: Path,
    result: dict[str, Any],
    *,
    run_id: str,
    allow_external: bool,
) -> None:
    validation = validate_render_result(result)
    checks.append(build_check("render_result_base_contract", validation.get("valid", False), "error", "; ".join(validation.get("errors", [])) or "render result base contract ok."))
    checks.append(build_check("render_result_schema_version", result.get("schema_version") == RENDER_RESULT_SCHEMA_VERSION, "error", f"schema_version must be {RENDER_RESULT_SCHEMA_VERSION}."))
    if result.get("run_id"):
        checks.append(build_check("render_result_run_id_match", str(result.get("run_id")) == run_id, "error", f"render result run_id is {result.get('run_id')}, expected {run_id}."))
    status = str(result.get("status") or "")
    checks.append(build_check("render_result_status", status in VALID_STATUSES, "error", f"status must be one of {sorted(VALID_STATUSES)}."))
    if status == "completed":
        checks.append(build_check("render_result_completed_artifact", bool(result.get("artifact_path")), "error", "completed render result needs artifact_path."))
    if status == "failed":
        checks.append(build_check("render_result_failed_errors", bool(result.get("errors")), "error", "failed render result needs errors[]."))
    if result.get("artifact_path"):
        _check_artifact(checks, run_dir, result["artifact_path"], allow_external=allow_external)


def _check_artifact(checks: list[dict[str, Any]], run_dir: Path, value: str | Path, *, allow_external: bool) -> tuple[Path | None, bool]:
    resolved, inside_run = _resolve_path(run_dir, value)
    refs = [str(value)]
    severity = "warning" if allow_external else "error"
    checks.append(build_check("artifact_path_location", bool(resolved and (inside_run or allow_external)), severity, "artifact_path must be inside run_dir unless allow_external is set.", refs=refs))
    if resolved is None:
        return None, False
    exists = resolved.exists()
    checks.append(build_check("artifact_path_exists", exists, "error", "artifact_path missing.", refs=refs))
    return resolved, exists


def _check_preview_dir(checks: list[dict[str, Any]], run_dir: Path, value: str, *, allow_external: bool) -> None:
    resolved, inside_run = _resolve_path(run_dir, value)
    checks.append(build_check("preview_dir_location", bool(resolved and (inside_run or allow_external)), "warning", "preview_dir should be inside run_dir.", refs=[value]))
    if resolved is not None:
        exists = resolved.exists() and resolved.is_dir()
        checks.append(build_check("preview_dir_exists", True, "info", "preview_dir exists." if exists else "preview_dir not present yet.", refs=[value]))


def _resolve_path(run_dir: Path, value: str | Path) -> tuple[Path | None, bool]:
    path = Path(value).expanduser()
    if not path.is_absolute() and ".." in path.parts:
        return None, False
    resolved = path.resolve() if path.is_absolute() else (run_dir / path).resolve()
    root_text = str(run_dir)
    resolved_text = str(resolved)
    return resolved, resolved_text == root_text or resolved_text.startswith(root_text + os.sep)


def _expected_page_count(run_dir: Path) -> int:
    queue = run_dir / "approved_queue.json"
    if not queue.exists():
        queue = run_dir / "export_queue.json"
    if queue.exists():
        try:
            payload = json.loads(queue.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return len(payload)
            if isinstance(payload, dict):
                for key in ("slides", "pages", "items", "queue"):
                    if isinstance(payload.get(key), list):
                        return len(payload[key])
        except json.JSONDecodeError:
            pass
    preview = run_dir / "preview_manifest.json"
    if not preview.exists():
        return 0
    try:
        payload = json.loads(preview.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    pages = payload.get("pages", []) if isinstance(payload, dict) else []
    return sum(1 for page in pages if isinstance(page, dict) and (page.get("decision") == "approved" or page.get("review_status") == "approved"))


def _check_callable(checks: list[dict[str, Any]], check_id: str, module_name: str, function_name: str) -> str:
    try:
        module = __import__(module_name, fromlist=[function_name])
        available = callable(getattr(module, function_name, None))
    except Exception:
        available = False
    checks.append(build_check(check_id, available, "warning", f"{function_name} unavailable."))
    return "available" if available else "unavailable"


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


def _ref(run_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)
