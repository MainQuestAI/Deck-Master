from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delivery.validate import validate_delivery
from runtime.render import find_render_result
from runtime.run_state import PREVIEW_MANIFEST_NAME, read_json
from runtime.run_state_resolver import resolve_run_state

SCHEMA_VERSION = "deck_final_readiness.v1"
FINAL_READINESS_PATH = Path("delivery") / "final_readiness.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return ""


def _resolve_artifact(root: Path, artifact_path: str | Path | None, render_result: dict[str, Any]) -> tuple[Path | None, str]:
    raw = str(artifact_path or render_result.get("artifact_path") or "").strip()
    if not raw:
        return None, ""
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.expanduser().resolve()
    rel = _run_relative(root, candidate)
    if not rel:
        return candidate, ""
    return candidate, rel


def _approved_page_count(root: Path) -> int:
    preview = _safe_read_json(root / PREVIEW_MANIFEST_NAME)
    pages = preview.get("pages")
    if not isinstance(pages, list):
        return 0
    approved = 0
    for page in pages:
        if not isinstance(page, dict):
            continue
        decision = str(page.get("decision") or page.get("review_status") or "").strip().lower()
        review_status = str(page.get("review_status") or "").strip().lower()
        if decision == "approved" or review_status == "approved":
            approved += 1
    return approved


def _render_page_count(render_result: dict[str, Any]) -> int:
    try:
        return int(render_result.get("page_count") or 0)
    except (TypeError, ValueError):
        return 0


def _add_blocker(blockers: list[dict[str, str]], code: str, message: str, *, severity: str = "P0") -> None:
    if any(item.get("code") == code for item in blockers):
        return
    blockers.append({"code": code, "severity": severity, "message": message})


def _run_state_not_ready_message(stage: str) -> str:
    stage_messages = {
        "needs_request": "项目请求还未创建，不能进入最终交付。",
        "needs_context": "项目背景与输入资料还未补齐，不能进入最终交付。",
        "needs_brief": "方案简报还未生成，不能进入最终交付。",
        "needs_claim_map": "论点与依据关系还未建立，不能进入最终交付。",
        "needs_narrative_plan": "叙事方案还未生成，不能进入最终交付。",
        "needs_page_tasks": "页面任务还未生成，不能进入最终交付。",
        "needs_sourcing": "页面来源方案还未确认，不能进入最终交付。",
        "needs_preview": "页面预览还未生成，不能进入最终交付。",
        "needs_generation_session": "内容生成会话还未创建，不能进入最终交付。",
        "awaiting_agent_execution": "内容生成已派发，仍在等待 Agent 回传结果。",
        "generation_running": "内容生成仍在进行中，不能进入最终交付。",
        "needs_generation_import": "Agent 生成结果还未导入，不能进入最终交付。",
        "needs_preview_refresh": "最新生成结果还未刷新到预览，不能进入最终交付。",
        "needs_draft_gate": "草稿质量门禁还未通过，不能进入最终交付。",
        "needs_build": "构建清单还未生成，不能进入最终交付。",
        "needs_render": "最终渲染产物还未生成，不能进入最终交付。",
        "needs_review": "页面审阅还未完成，不能进入最终交付。",
        "blocked_workspace": "项目工作区存在阻断项，不能进入最终交付。",
    }
    return stage_messages.get(stage, f"当前运行阶段还未达到最终交付条件：{stage or 'unknown'}。")


def _quality_gate_summary(root: Path) -> list[dict[str, Any]]:
    quality_dir = root / "quality_reports"
    if not quality_dir.is_dir():
        return []
    gates: list[dict[str, Any]] = []
    for path in sorted(quality_dir.glob("*_gate.json")):
        report = _safe_read_json(path)
        if not report:
            gates.append({"gate": path.stem.replace("_gate", ""), "status": "parse_failed", "blocks_delivery": True})
            continue
        gates.append(
            {
                "gate": str(report.get("gate") or path.stem.replace("_gate", "")),
                "status": str(report.get("status") or ""),
                "blocks_delivery": bool(report.get("blocks_delivery")),
                "findings": len(report.get("findings", [])) if isinstance(report.get("findings"), list) else 0,
                "page_findings": len(report.get("page_findings", [])) if isinstance(report.get("page_findings"), list) else 0,
            }
        )
    return gates


def compute_final_readiness(
    run_dir: str | Path,
    *,
    artifact_path: str | Path | None = None,
    expected_page_count: int | None = None,
    write: bool = True,
    run_mode: str | None = None,
    dev_allow_unsetup: bool = False,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    run_state = resolve_run_state(root, run_mode=run_mode, dev_allow_unsetup=dev_allow_unsetup)
    run_id = str(run_state.get("run_id") or root.name)
    render_result_path, render_result, render_source = find_render_result(root)
    render_result = render_result or {}
    artifact, artifact_rel = _resolve_artifact(root, artifact_path, render_result)
    approved_pages = expected_page_count if expected_page_count is not None else _approved_page_count(root)
    render_pages = _render_page_count(render_result)
    blockers: list[dict[str, str]] = []
    warnings: list[str] = []

    stage = str(run_state.get("stage") or "")
    if stage not in {"ready_for_client_export", "ready_for_benchmark"}:
        _add_blocker(blockers, "final_run_state_not_ready", _run_state_not_ready_message(stage))

    if not render_result:
        _add_blocker(blockers, "final_render_missing", "Render result is missing.")
    elif str(render_result.get("status") or "").lower() != "completed":
        _add_blocker(blockers, "final_render_not_completed", "Render result is not completed.")

    if not artifact_rel:
        _add_blocker(blockers, "final_artifact_path_unsafe", "Final artifact path is missing or outside the run directory.")

    delivery_validation: dict[str, Any] = {}
    if artifact and artifact_rel:
        delivery_validation = validate_delivery(root, artifact, expected_page_count=int(approved_pages or 0))
        if delivery_validation.get("blocks_delivery"):
            _add_blocker(blockers, "final_delivery_validation_blocked", "Delivery validation blocks final readiness.")
    else:
        _add_blocker(blockers, "final_artifact_missing", "Final artifact is missing.")

    lineage = _safe_read_json(root / "delivery" / "final_version_lineage.json")
    if not lineage:
        _add_blocker(blockers, "final_lineage_missing", "Final version lineage is missing.")
    elif lineage.get("schema_version") != "deck_final_version_lineage.v1":
        _add_blocker(blockers, "final_lineage_invalid", "Final version lineage schema is invalid.")

    if approved_pages and render_pages and approved_pages != render_pages:
        _add_blocker(
            blockers,
            "final_page_count_mismatch",
            f"Approved page count {approved_pages} differs from render page count {render_pages}.",
            severity="P1",
        )

    quality_gates = _quality_gate_summary(root)
    if not quality_gates:
        _add_blocker(blockers, "final_quality_gate_missing", "Quality gate report is missing.", severity="P1")
    for gate in quality_gates:
        if gate.get("blocks_delivery") or str(gate.get("status") or "").lower() in {"rework_required", "failed", "blocked"}:
            _add_blocker(
                blockers,
                "final_quality_gate_blocked",
                f"Quality gate {gate.get('gate') or 'unknown'} blocks delivery.",
                severity="P1",
            )

    artifact_validation = (delivery_validation.get("lineage") or {}).get("artifact_validation") or {}
    artifact_manifest_validation = (delivery_validation.get("lineage") or {}).get("artifact_manifest_validation") or {}
    if artifact_validation and not artifact_validation.get("valid"):
        _add_blocker(blockers, "final_artifact_invalid", "Final artifact validation failed.")
    if artifact_manifest_validation and not artifact_manifest_validation.get("valid"):
        _add_blocker(blockers, "final_artifact_manifest_invalid", "Build artifact manifest validation failed.")

    ready = not blockers
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_dir": str(root),
        "run_mode": str(run_state.get("run_mode") or ""),
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "computed_at": _utc_now(),
        "final_artifact": {
            "path": artifact_rel,
            "absolute_path": str(artifact) if artifact else "",
            "hash": str(delivery_validation.get("artifact_hash") or ""),
            "exists": bool(artifact and artifact.exists()),
        },
        "page_counts": {
            "approved": int(approved_pages or 0),
            "rendered": render_pages,
            "delivery_validation": (delivery_validation.get("lineage") or {}).get("page_count"),
        },
        "run_state": {
            "stage": stage,
            "next_command": str(run_state.get("next_command") or ""),
            "blocked_actions": run_state.get("blocked_actions") or [],
        },
        "render": {
            "source": render_source,
            "result_path": str(render_result_path.relative_to(root)) if render_result else "",
            "status": str(render_result.get("status") or ""),
            "source_fingerprint": str(render_result.get("source_fingerprint") or ""),
            "artifact_manifest": str(render_result.get("artifact_manifest") or ""),
        },
        "delivery_validation": {
            "status": str(delivery_validation.get("status") or ""),
            "blocks_delivery": bool(delivery_validation.get("blocks_delivery")),
            "finding_count": len(delivery_validation.get("findings", [])) if isinstance(delivery_validation.get("findings"), list) else 0,
        },
        "lineage": {
            "path": "delivery/final_version_lineage.json" if lineage else "",
            "schema_version": str(lineage.get("schema_version") or ""),
            "artifact_hash": str(lineage.get("artifact_hash") or ""),
            "source_fingerprint": str(lineage.get("source_fingerprint") or ""),
        },
        "quality_gates": quality_gates,
        "blockers": blockers,
        "warnings": warnings,
    }

    if write:
        output_path = root / FINAL_READINESS_PATH
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(output_path)

    return payload


def read_final_readiness(run_dir: str | Path) -> dict[str, Any]:
    return _safe_read_json(Path(run_dir).expanduser().resolve() / FINAL_READINESS_PATH)


def final_readiness_clearance(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    path = root / FINAL_READINESS_PATH
    payload = _safe_read_json(path)
    if not payload:
        return {
            "ready": False,
            "status": "missing",
            "reason": "Final readiness is missing.",
            "path": str(FINAL_READINESS_PATH),
            "readiness": {},
            "blockers": [{"code": "final_readiness_missing", "severity": "P0", "message": "Final readiness is missing."}],
        }

    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    ready = bool(payload.get("ready")) and str(payload.get("status") or "") == "ready"
    reason = ""
    if not ready:
        for blocker in blockers:
            if isinstance(blocker, dict) and blocker.get("message"):
                reason = str(blocker.get("message"))
                break
        if not reason:
            reason = "Final readiness is blocked."
    return {
        "ready": ready,
        "status": str(payload.get("status") or "blocked"),
        "reason": reason,
        "path": str(FINAL_READINESS_PATH),
        "readiness": payload,
        "blockers": blockers,
    }
