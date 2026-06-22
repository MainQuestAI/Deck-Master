from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from delivery.outcome import record_delivery_outcome
from manifest import ManifestError, load_manifest, page_payload
from orchestrate.export_queue import export_queue
from quality.overrides import list_active_overrides
from review.readiness import compute_claim_coverage, compute_deck_readiness, compute_next_actions
from review.workbench import WorkbenchError, execute_review_action
from runtime.events import append_typed_event, read_events
from runtime.render import CANONICAL_RENDER_RESULT, find_render_result
from runtime.run_state import RunStateError, load_request, run_status
from runtime.run_state_resolver import resolve_run_state

APPROVAL_STORE_DIR = "review_workspace"
APPROVAL_STORE_FILE = "approval_tasks.json"

STATUS_LIBRARY: dict[str, dict[str, str]] = {
    "待准备": {
        "definition": "项目已创建，但还没有进入可审状态。",
        "owner": "方案负责人",
        "result": "形成第一版可审页面与预览。",
        "tone": "muted",
    },
    "生成中": {
        "definition": "页面生成或预览构建还在推进。",
        "owner": "内容生成链路",
        "result": "补齐预览与生成结果，回到可审状态。",
        "tone": "warning",
    },
    "待审阅": {
        "definition": "页面已可见，但关键判断还未完成。",
        "owner": "主审人",
        "result": "完成页面级审查与意见记录。",
        "tone": "warning",
    },
    "待补依据": {
        "definition": "核心论点已出现依据缺口，不能直接放行。",
        "owner": "内容负责人",
        "result": "补齐来源与支撑材料，恢复可审状态。",
        "tone": "warning",
    },
    "待审批": {
        "definition": "内容已基本收敛，等待明确拍板。",
        "owner": "审批人",
        "result": "给出批准或驳回结论。",
        "tone": "warning",
    },
    "可交付": {
        "definition": "当前页面、门禁与交付预览已满足交付条件。",
        "owner": "交付把关人",
        "result": "提交审批、确认交付或进入回看。",
        "tone": "success",
    },
    "已交付": {
        "definition": "当前方案项目已完成交付记录，可回看结果。",
        "owner": "交付负责人",
        "result": "沉淀经验并进入复盘。",
        "tone": "success",
    },
    "风险冻结": {
        "definition": "高优先级质量或证据风险阻断了继续推进。",
        "owner": "主审人",
        "result": "先清掉阻断项，再恢复审批或导出。",
        "tone": "danger",
    },
}

BLOCKING_REASON_TRANSLATIONS = {
    "no approved pages": "当前还没有页面进入已批准状态。",
    "pages still need review": "仍有页面待主审处理。",
    "evidence gate is blocked": "证据门禁仍在阻断。",
    "quality gate blocks delivery": "质量门禁仍在阻断导出。",
    "render result is missing": "当前缺少最新渲染结果。",
    "render result is missing after build": "构建已准备，仍缺少最终渲染结果。",
    "build manifest is missing after review and quality gate": "审阅和质量门禁已通过，仍缺少构建清单。",
    "artifact manifest contains invalid artifacts": "构建产物存在无效项，需要重新渲染。",
    "preview manifest is missing": "当前还没有形成可审页面预览。",
}


def _translate_blocking_reason(reason: str) -> str:
    text = str(reason or "").strip()
    if not text:
        return ""
    if text.startswith("generation session status="):
        status = text.split("=", 1)[1].strip() or "unknown"
        status_mapping = {
            "running": "内容生成任务仍在进行中。",
            "pending": "内容生成任务已经排队，等待开始。",
            "dispatched": "内容生成任务已派发，等待 Agent 回传结果。",
            "awaiting_agent_execution": "内容生成任务已派发，等待 Agent 执行。",
            "quality_required": "最新生成结果还缺质量复核。",
            "preview_refreshed": "页面预览已刷新，等待继续判断。",
            "completed": "内容生成已完成，等待导入结果。",
        }
        return status_mapping.get(status, f"内容生成状态仍为 {status}。")
    return BLOCKING_REASON_TRANSLATIONS.get(text, text)

RUNTIME_STAGE_TO_WORKSPACE_STAGE = {
    "needs_request": "待准备",
    "needs_context": "待准备",
    "needs_brief": "待准备",
    "needs_claim_map": "待准备",
    "needs_narrative_plan": "待准备",
    "needs_page_tasks": "待准备",
    "needs_sourcing": "待准备",
    "needs_preview": "待准备",
    "needs_generation_session": "生成中",
    "awaiting_agent_execution": "生成中",
    "generation_running": "生成中",
    "needs_generation_import": "生成中",
    "needs_preview_refresh": "生成中",
    "needs_build": "生成中",
    "needs_render": "生成中",
    "generation_failed": "风险冻结",
    "needs_draft_gate": "风险冻结",
    "needs_evidence": "待补依据",
    "needs_review": "待审阅",
    "ready_for_client_export": "可交付",
    "ready_for_benchmark": "可交付",
    "blocked_workspace": "风险冻结",
}


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_manifest_optional(run_dir: Path) -> dict[str, Any] | None:
    try:
        return load_manifest(run_dir)
    except ManifestError:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _approval_store_path(run_dir: Path) -> Path:
    return run_dir / APPROVAL_STORE_DIR / APPROVAL_STORE_FILE


def _load_approval_tasks(run_dir: Path) -> list[dict[str, Any]]:
    payload = _safe_read_json(_approval_store_path(run_dir)) or {}
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    return [task for task in tasks if isinstance(task, dict)]


def _save_approval_tasks(run_dir: Path, tasks: list[dict[str, Any]]) -> None:
    path = _approval_store_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "deck_workspace_approval.v1", "tasks": tasks}
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _find_pending_approval_task(
    tasks: list[dict[str, Any]],
    *,
    scope_type: str,
    target_id: str,
    subject: str,
    approval_type: str,
) -> dict[str, Any] | None:
    for task in tasks:
        if task.get("status") != "pending":
            continue
        if task.get("scope_type") != scope_type:
            continue
        if str(task.get("target_id") or "") != target_id:
            continue
        if str(task.get("subject") or "") != subject:
            continue
        if str(task.get("approval_type") or "approval") != approval_type:
            continue
        return task
    return None


def _create_approval_task(
    run_dir: Path,
    *,
    scope_type: str,
    target_id: str,
    subject: str,
    reason: str,
    submitted_by: str,
    approval_type: str = "approval",
) -> dict[str, Any]:
    tasks = _load_approval_tasks(run_dir)
    existing = _find_pending_approval_task(
        tasks,
        scope_type=scope_type,
        target_id=target_id,
        subject=subject,
        approval_type=approval_type,
    )
    if existing:
        return existing
    approval_id = f"approval_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    task = {
        "approval_id": approval_id,
        "run_id": run_dir.name,
        "scope_type": scope_type,
        "target_id": target_id,
        "approval_type": approval_type,
        "subject": subject,
        "reason": reason,
        "status": "pending",
        "submitted_by": submitted_by,
        "submitted_at": _utc_now(),
        "decision_notes": "",
    }
    tasks.append(task)
    _save_approval_tasks(run_dir, tasks)
    append_typed_event(
        run_dir,
        "manual_action",
        "workspace.approval.submitted",
        f"{subject} submitted for approval",
        refs=[target_id, approval_id],
        severity="info",
        payload={"scope_type": scope_type, "approval_id": approval_id, "reason": reason},
    )
    return task


def _decide_approval_task(
    run_dir: Path,
    *,
    approval_id: str,
    decision: str,
    actor: str,
    note: str,
) -> dict[str, Any]:
    tasks = _load_approval_tasks(run_dir)
    for task in tasks:
        if task.get("approval_id") != approval_id:
            continue
        if task.get("status") != "pending":
            raise ValueError(f"Approval {approval_id} is not pending.")
        task["status"] = decision
        task["decision_by"] = actor
        task["decision_at"] = _utc_now()
        task["decision_notes"] = note
        _save_approval_tasks(run_dir, tasks)
        append_typed_event(
            run_dir,
            "manual_action",
            f"workspace.approval.{decision}",
            f"{task.get('subject', approval_id)} marked as {decision}",
            refs=[str(task.get("target_id") or ""), approval_id],
            severity="info" if decision == "approved" else "warning",
            payload={"approval_id": approval_id, "note": note},
        )
        return task
    raise ValueError(f"Approval not found: {approval_id}")


def _request_data(run_dir: Path) -> dict[str, Any]:
    try:
        return load_request(run_dir)
    except (ManifestError, RunStateError, ValueError):
        return {}


def _empty_claim_summary() -> dict[str, Any]:
    return {
        "total": 0,
        "covered": 0,
        "evidence_gap": 0,
        "blocked": 0,
        "review_required": 0,
        "uncovered": 0,
        "claims": [],
    }


def _source_label(page: dict[str, Any]) -> str:
    origin = str(page.get("candidate_origin") or page.get("library_source") or page.get("source_type") or "").lower()
    mapping = {
        "ppt_library": "真实库",
        "library_slide": "历史页面",
        "generated": "生成页",
        "placeholder": "占位页",
        "manual": "人工页",
        "fixture": "演示样例",
        "reuse": "历史页面",
        "adapt": "改写页",
    }
    return mapping.get(origin, origin or "未标注")


def _source_decision_label(page: dict[str, Any]) -> str:
    decision = str(page.get("source_decision") or page.get("action_intent") or "").lower()
    mapping = {
        "reuse": "沿用历史页面",
        "adapt": "基于历史页改写",
        "generate": "新生成",
        "manual_placeholder": "人工占位",
        "pending_replacement": "等待替换来源",
        "replace": "待替换",
        "request_evidence": "等待补依据",
    }
    if decision in mapping:
        return mapping[decision]
    source_type = str(page.get("source_type") or "").lower()
    source_type_mapping = {
        "library_slide": "沿用历史页面",
        "generated": "新生成",
        "placeholder": "人工占位",
        "manual": "人工页",
    }
    return source_type_mapping.get(source_type, "待确认")


def _review_label(page: dict[str, Any]) -> tuple[str, str]:
    status = str(page.get("review_status") or page.get("decision") or "needs_review")
    mapping = {
        "approved": ("已批准", "success"),
        "rejected": ("已驳回", "danger"),
        "needs_evidence": ("待补依据", "warning"),
        "needs_review": ("待审阅", "warning"),
        "keep": ("已批准", "success"),
        "replace": ("待替换", "danger"),
    }
    return mapping.get(status, (status or "待处理", "muted"))


def _claim_graph(run_dir: Path) -> dict[str, Any]:
    return _safe_read_json(run_dir / "claim_evidence_graph.json") or {}


def _claim_map(run_dir: Path) -> dict[str, Any]:
    return _safe_read_json(run_dir / "claim_map.json") or {}


def _page_claim_bundle(run_dir: Path, page_id: str) -> dict[str, Any]:
    claim_graph = _claim_graph(run_dir)
    claim_map = _claim_map(run_dir)
    claims = claim_graph.get("claims", [])
    evidence_list = claim_graph.get("evidence", [])
    evidence_by_id = {
        str(item.get("evidence_id")): item
        for item in evidence_list
        if isinstance(item, dict) and item.get("evidence_id")
    }
    page_claims = []
    page_claim_map = None
    for entry in claim_map.get("pages", []):
        if isinstance(entry, dict) and entry.get("page_id") == page_id:
            page_claim_map = entry
            break

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        refs = claim.get("page_refs", [])
        if claim.get("page_id") == page_id or page_id in refs:
            evidence_items = []
            raw_evidence = claim.get("supporting_evidence") or claim.get("evidence") or []
            for evidence_id in raw_evidence:
                item = evidence_by_id.get(str(evidence_id), {})
                evidence_items.append(
                    {
                        "evidence_id": str(evidence_id),
                        "source_ref": str(item.get("source_ref") or item.get("source_id") or ""),
                        "status": str(item.get("publication_status") or "available"),
                        "evidence_type": str(item.get("evidence_type") or ""),
                        "title": str(item.get("title") or item.get("summary") or item.get("source_ref") or evidence_id),
                    }
                )
            page_claims.append(
                {
                    "claim_id": str(claim.get("claim_id") or ""),
                    "statement": str(claim.get("statement") or ""),
                    "evidence": evidence_items,
                    "evidence_count": len(evidence_items),
                }
            )

    uncovered = [claim for claim in page_claims if not claim["evidence_count"]]
    return {
        "core_claim": str((page_claim_map or {}).get("core_claim") or ""),
        "evidence_policy": (page_claim_map or {}).get("evidence_policy"),
        "claims": page_claims,
        "uncovered_claims": len(uncovered),
        "covered_claims": len(page_claims) - len(uncovered),
        "evidence_total": sum(claim["evidence_count"] for claim in page_claims),
    }


def _page_quality_risks(run_dir: Path, page: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for item in page.get("quality", []):
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "P2")
        findings.append(
            {
                "finding_id": str(item.get("finding_id") or item.get("id") or item.get("message") or ""),
                "severity": severity,
                "summary": str(item.get("message") or item.get("repair_instruction") or ""),
                "repair_instruction": str(item.get("repair_instruction") or ""),
                "gate": str(item.get("gate") or "quality"),
                "status": "blocked" if severity in {"P0", "P1"} else "warning",
            }
        )

    if not page.get("asset_exists", True):
        findings.append(
            {
                "finding_id": f"{page.get('page_id', '')}_preview_missing",
                "severity": "P1",
                "summary": str(page.get("asset_error") or "页面预览缺失"),
                "repair_instruction": "补齐预览文件后再审阅。",
                "gate": "preview",
                "status": "blocked",
            }
        )
    return findings


def _delivery_outcome(run_dir: Path) -> dict[str, Any]:
    return _safe_read_json(run_dir / "delivery" / "delivery_outcome.json") or {}


def _resolve_run_relative_path(run_dir: Path, raw_path: str) -> tuple[Path | None, str]:
    value = str(raw_path or "").strip()
    if not value:
        return None, ""
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (run_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()
    root = run_dir.resolve()
    candidate_text = str(candidate)
    root_text = str(root)
    if candidate_text != root_text and not candidate_text.startswith(root_text + "/"):
        return None, value
    try:
        relative = str(candidate.relative_to(root))
    except ValueError:
        relative = value
    return candidate, relative


def build_delivery_preview_payload(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    request = _request_data(root)
    project_title = str(request.get("project_name") or root.name)
    render_result_path, render_result, source = find_render_result(root)
    raw_artifact_path = str((render_result or {}).get("artifact_path") or "")
    artifact_file, artifact_relative_path = _resolve_run_relative_path(root, raw_artifact_path)
    artifact_ready = bool(artifact_file and artifact_file.exists())
    delivery = _delivery_outcome(root)
    render_status_value = str((render_result or {}).get("status") or "")
    raw_artifacts = (render_result or {}).get("artifacts")
    artifact_list = raw_artifacts if isinstance(raw_artifacts, list) else []
    formats = sorted(
        set(str(item.get("kind") or "") for item in artifact_list if isinstance(item, dict) and item.get("kind"))
    )
    editability = sorted(
        set(str(item.get("editability") or "") for item in artifact_list if isinstance(item, dict) and item.get("editability"))
    )

    if not render_result:
        status = "missing_render_result"
        summary = "当前还没有交付级预览产物。"
        detail = "先完成 PPT Master 渲染，形成标准交付预览。"
    elif not raw_artifact_path:
        status = "missing_artifact_path"
        summary = "渲染结果存在，但还没有登记交付产物路径。"
        detail = "检查 render_result.json，补齐 artifact_path。"
    elif not artifact_ready:
        status = "artifact_missing"
        summary = "交付预览文件缺失，当前无法直接回看交付成片。"
        detail = "检查 rendered/index.html 或重新执行交付渲染。"
    else:
        status = "ready"
        summary = "交付级预览已就绪。"
        detail = "可以切换到交付预览查看最终交付形态。"

    if delivery.get("delivered"):
        summary = "已记录交付结果，可回看交付预览与交付说明。"
        if status == "ready":
            detail = "当前已具备交付回看条件。"

    artifact_url = ""
    if artifact_ready:
        artifact_url = f"/delivery-preview/{root.name}?run={root.name}"

    return {
        "schema_version": "deck_master_workspace_delivery_preview.v0.2",
        "run_id": _resolved_run_id(root),
        "project_id": _resolved_run_id(root),
        "project_title": project_title,
        "status": status,
        "render_status": render_status_value or ("present" if render_result else "missing"),
        "render_source": source,
        "render_result_path": str(render_result_path.relative_to(root)) if render_result_path else str(CANONICAL_RENDER_RESULT),
        "artifact_path": artifact_relative_path,
        "artifact_ready": artifact_ready,
        "artifact_url": artifact_url,
        "format": str((render_result or {}).get("format") or "html"),
        "artifact_manifest": str((render_result or {}).get("artifact_manifest") or ""),
        "artifact_count": len(artifact_list),
        "formats": formats,
        "editability": editability,
        "source_fingerprint": str((render_result or {}).get("source_fingerprint") or ""),
        "source_mode": "real" if (render_result or {}).get("schema_version") == "deck_render_result.v2" else source,
        "created_at": str((render_result or {}).get("created_at") or ""),
        "summary": summary,
        "detail": detail,
        "recommended_action": "补齐交付渲染" if status != "ready" else "进入交付预览",
        "delivered": bool(delivery.get("delivered")),
        "delivered_at": str(delivery.get("delivered_at") or ""),
        "delivery_notes": str(delivery.get("notes") or ""),
    }


def _next_step_summary(run_dir: Path) -> dict[str, Any]:
    try:
        return resolve_run_state(run_dir)
    except Exception:
        return {"status": run_status(run_dir)}


def _blocking_reasons(deck_readiness: dict[str, Any], quality_findings: list[dict[str, Any]]) -> list[str]:
    reasons = []
    for reason in deck_readiness.get("deck_readiness", {}).get("blocking_reasons", []):
        if reason:
            reasons.append(_translate_blocking_reason(str(reason)))
    for finding in quality_findings:
        if finding.get("severity") in {"P0", "P1"}:
            reasons.append(str(finding.get("summary") or ""))
    return list(dict.fromkeys(reason for reason in reasons if reason))


def _workspace_stage(
    run_dir: Path,
    *,
    pages: list[dict[str, Any]],
    deck_readiness: dict[str, Any],
    approvals: list[dict[str, Any]],
    delivery: dict[str, Any],
    run_state_summary: dict[str, Any],
) -> dict[str, Any]:
    ready = deck_readiness.get("deck_readiness", {})
    counts = deck_readiness.get("counts", {})
    blocking_quality = bool(counts.get("p0") or counts.get("p1"))
    pending_approvals = [task for task in approvals if task.get("status") == "pending"]
    waiting_evidence = [page for page in pages if str(page.get("review_status")) == "needs_evidence"]
    waiting_review = [page for page in pages if str(page.get("review_status")) in {"", "needs_review"}]
    preview_missing = [page for page in pages if not page.get("asset_exists", True)]
    export_ready = str(ready.get("export") or "") == "ready"
    generation_state = str(ready.get("generation") or "")
    generation_required = bool(ready.get("generation_required"))
    runtime_stage = str(run_state_summary.get("stage") or "")
    blocked_actions = run_state_summary.get("blocked_actions") or []
    runtime_reason = ""
    if isinstance(blocked_actions, list) and blocked_actions:
        runtime_reason = _translate_blocking_reason(str(blocked_actions[0].get("reason") or ""))
    runtime_stage_next_step = {
        "needs_generation_session": "先创建生成会话，准备派发给 Agent。",
        "awaiting_agent_execution": "等待 Agent 执行并回传生成结果。",
        "generation_running": "等待生成任务完成。",
        "needs_generation_import": "导入 Agent 回传的生成结果。",
        "needs_preview_refresh": "用最新生成结果刷新页面预览。",
        "needs_build": "先生成 build manifest，锁定本次构建输入。",
        "needs_render": "执行 build run，补齐 HTML/PDF/PNG/PPTX 产物。",
    }

    if delivery.get("delivered"):
        stage_label = "已交付"
        blocker = "已记录交付结果，可转入复盘。"
        next_step = "查看反馈并沉淀复用经验。"
    elif runtime_stage in runtime_stage_next_step:
        stage_label = "生成中"
        blocker = runtime_reason or "生产链路仍在补齐生成、构建或渲染结果。"
        next_step = runtime_stage_next_step[runtime_stage]
    elif pending_approvals:
        stage_label = "待审批"
        blocker = f"{len(pending_approvals)} 项审批仍待拍板。"
        next_step = "推进审批人给出结论。"
    elif waiting_evidence:
        stage_label = "待补依据"
        blocker = f"{len(waiting_evidence)} 页存在证据缺口。"
        next_step = "补齐来源和证据后再审阅。"
    elif blocking_quality:
        stage_label = "风险冻结"
        blocker = "高优先级质量风险仍在阻断推进。"
        next_step = "先处理 P0/P1 风险，再恢复导出判断。"
    elif export_ready and not waiting_review:
        stage_label = "可交付"
        blocker = "当前内容、门禁与交付链路已满足进入交付的前置条件。"
        next_step = "提交审批、查看交付预览或直接记录交付。"
    elif (
        generation_required
        and generation_state in {"running", "pending", "quality_required", "preview_refreshed", "partial"}
    ) or preview_missing:
        stage_label = "生成中"
        blocker = "生成链路或预览文件还没有完全稳定。"
        next_step = "等待生成完成，或补齐缺失预览。"
    elif not pages:
        stage_label = "待准备"
        blocker = "当前还没有可审页面。"
        next_step = "先完成 planning、sourcing 或 preview 构建。"
    else:
        stage_label = "待审阅"
        blocker = f"{len(waiting_review) or counts.get('needs_review', 0)} 页仍待主审判断。"
        next_step = "优先处理阻断页，再推进批准。"

    definition = STATUS_LIBRARY[stage_label]
    return {
        "code": stage_label,
        "label": stage_label,
        "definition": definition["definition"],
        "blocking_reason": blocker,
        "next_step": next_step,
        "owner": definition["owner"],
        "expected_result": definition["result"],
        "tone": definition["tone"],
    }


def _workspace_stage_without_manifest(run_dir: Path, *, run_state_summary: dict[str, Any]) -> dict[str, Any]:
    runtime_stage = str(run_state_summary.get("stage") or "needs_request")
    stage_label = RUNTIME_STAGE_TO_WORKSPACE_STAGE.get(runtime_stage, "待准备")
    definition = STATUS_LIBRARY[stage_label]
    blocked_actions = run_state_summary.get("blocked_actions") or []
    reason = ""
    if isinstance(blocked_actions, list) and blocked_actions:
        reason = str(blocked_actions[0].get("reason") or "")
    reason = _translate_blocking_reason(reason)
    if not reason:
        reason = "当前还没有形成可审页面。"
    next_step_mapping = {
        "needs_request": "先补齐项目基础信息。",
        "needs_context": "先补齐项目背景与输入资料。",
        "needs_brief": "先补齐方案目标和核心要求。",
        "needs_claim_map": "先整理主论点和页面主张。",
        "needs_narrative_plan": "先补齐方案结构规划。",
        "needs_page_tasks": "先补齐页面任务拆解。",
        "needs_sourcing": "先完成来源决策和页面取材。",
        "needs_preview": "先生成首版页面与预览。",
        "needs_generation_session": "先发起内容生成任务。",
        "awaiting_agent_execution": "等待 Agent 执行并回传生成结果。",
        "generation_running": "等待内容生成完成。",
        "needs_generation_import": "先导入最新生成结果。",
        "needs_preview_refresh": "先刷新最新页面预览。",
        "needs_build": "先准备构建清单。",
        "needs_render": "先补齐最新构建和渲染结果。",
    }
    next_step = next_step_mapping.get(runtime_stage, "继续补齐前置内容。")
    return {
        "code": stage_label,
        "label": stage_label,
        "definition": definition["definition"],
        "blocking_reason": reason,
        "next_step": next_step,
        "owner": definition["owner"],
        "expected_result": definition["result"],
        "tone": definition["tone"],
    }


def _focus_page_id(pages: list[dict[str, Any]]) -> str:
    priorities = [
        ("needs_evidence", None),
        ("needs_review", None),
        ("approved", "blocked"),
        ("approved", None),
    ]
    for review_status, risk_status in priorities:
        for page in pages:
            page_status = str(page.get("review_status") or "")
            if page_status != review_status:
                continue
            if risk_status == "blocked" and not any(
                str(risk.get("severity") or "") in {"P0", "P1"} for risk in page.get("_quality_risks", [])
            ):
                continue
            return str(page.get("page_id") or "")
    return str((pages[0] or {}).get("page_id") or "") if pages else ""


def _build_page_cards(run_dir: Path, manifest_pages: list[dict[str, Any]], approvals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for page in manifest_pages:
        page_data = page_payload(run_dir, page)
        label, tone = _review_label(page_data)
        page_approvals = [
            task for task in approvals
            if task.get("scope_type") == "page" and task.get("target_id") == page_data.get("page_id")
        ]
        quality_risks = _page_quality_risks(run_dir, page_data)
        cards.append(
            {
                "page_id": page_data.get("page_id"),
                "order": page_data.get("order"),
                "title": page_data.get("title") or page_data.get("page_id"),
                "narrative_role": page_data.get("narrative_role", ""),
                "source_label": _source_label(page_data),
                "source_decision_label": _source_decision_label(page_data),
                "review_status": page_data.get("review_status", ""),
                "status_label": label,
                "status_tone": tone,
                "preview_url": page_data.get("preview_url", ""),
                "has_preview": bool(page_data.get("asset_exists")),
                "approval_state": page_approvals[0]["status"] if page_approvals else "none",
                "risk_count": len(quality_risks),
                "blocking_count": sum(1 for item in quality_risks if item.get("severity") in {"P0", "P1"}),
                "_quality_risks": quality_risks,
            }
        )
    return cards


def _resolved_run_id(run_dir: Path) -> str:
    manifest = _load_manifest_optional(run_dir)
    if manifest:
        return str(manifest.get("run_id") or run_dir.name)
    request = _request_data(run_dir)
    return str(request.get("run_id") or run_dir.name)


def _workspace_claim_summary(run_dir: Path) -> dict[str, Any]:
    coverage = compute_claim_coverage(run_dir)
    claims = coverage.get("claims", [])
    by_status: dict[str, int] = {}
    for claim in claims:
        status = str(claim.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "total": len(claims),
        "covered": by_status.get("covered", 0),
        "evidence_gap": by_status.get("evidence_gap", 0),
        "blocked": by_status.get("blocked", 0),
        "review_required": by_status.get("review_required", 0),
        "uncovered": by_status.get("uncovered", 0),
        "claims": claims,
    }


def _activity_items(run_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for event in read_events(run_dir, strict=False):
        timestamp = str(event.get("timestamp") or "")
        items.append(
            {
                "timestamp": timestamp,
                "kind": str(event.get("event_type") or "event"),
                "title": str(event.get("message") or event.get("action") or event.get("step") or "系统事件"),
                "detail": str(event.get("step") or event.get("action") or ""),
                "refs": event.get("refs") or [],
                "severity": str(event.get("severity") or "info"),
            }
        )
    for task in _load_approval_tasks(run_dir):
        items.append(
            {
                "timestamp": str(task.get("submitted_at") or ""),
                "kind": "approval",
                "title": f"提交审批: {task.get('subject', '')}",
                "detail": str(task.get("reason") or ""),
                "refs": [str(task.get("approval_id") or ""), str(task.get("target_id") or "")],
                "severity": "info",
            }
        )
        if task.get("decision_at"):
            items.append(
                {
                    "timestamp": str(task.get("decision_at") or ""),
                    "kind": "approval",
                    "title": f"审批{ '通过' if task.get('status') == 'approved' else '驳回' }: {task.get('subject', '')}",
                    "detail": str(task.get("decision_notes") or ""),
                    "refs": [str(task.get("approval_id") or ""), str(task.get("target_id") or "")],
                    "severity": "info" if task.get("status") == "approved" else "warning",
                }
            )
    delivery = _delivery_outcome(run_dir)
    if delivery:
        items.append(
            {
                "timestamp": str(delivery.get("delivered_at") or ""),
                "kind": "delivery",
                "title": "交付结果已记录",
                "detail": str(delivery.get("notes") or delivery.get("customer_reaction") or ""),
                "refs": ["delivery/delivery_outcome.json"],
                "severity": "info",
            }
        )
    items.sort(key=lambda item: _parse_ts(str(item.get("timestamp") or "")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:30]


def build_workspace_payload(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = _load_manifest_optional(root)
    request = _request_data(root)
    run_state_summary = _next_step_summary(root)
    approvals = _load_approval_tasks(root)
    delivery = _delivery_outcome(root)
    if manifest:
        readiness = compute_deck_readiness(root)
        next_actions = compute_next_actions(root)
        cards = _build_page_cards(root, manifest["pages"], approvals)
        stage = _workspace_stage(
            root,
            pages=cards,
            deck_readiness=readiness,
            approvals=approvals,
            delivery=delivery,
            run_state_summary=run_state_summary,
        )
        claim_summary = _workspace_claim_summary(root)
        queue = export_queue(root, {"approved"}, queue_type="client", allow_quality_override=False)
        metrics = readiness.get("counts", {})
        blocking = _blocking_reasons(readiness, [risk for card in cards for risk in card.get("_quality_risks", [])])
        title = str(manifest.get("title") or request.get("project_name") or root.name)
        updated_at = str(manifest.get("updated_at", ""))
    else:
        readiness = {"counts": {"pages": 0, "approved": 0, "needs_review": 0, "rejected": 0, "p0": 0, "p1": 0}}
        next_actions = {"actions": []}
        cards = []
        stage = _workspace_stage_without_manifest(root, run_state_summary=run_state_summary)
        claim_summary = _empty_claim_summary()
        queue = {"pages": [], "blocked_pages": [], "blocked_count": 0}
        metrics = readiness["counts"]
        blocking = [stage["blocking_reason"]] if stage["blocking_reason"] else []
        title = str(request.get("project_name") or request.get("business_goal") or root.name)
        updated_at = ""

    workspace_name = str(request.get("workspace_id") or request.get("project_name") or title or root.name)
    focus_page_id = _focus_page_id(cards)

    pending_approvals = [task for task in approvals if task.get("status") == "pending"]
    main_risks = []
    for card in cards:
        for risk in card.get("_quality_risks", []):
            if risk.get("severity") in {"P0", "P1"}:
                main_risks.append(
                    {
                        "target_id": card["page_id"],
                        "page_title": card["title"],
                        "severity": risk["severity"],
                        "summary": risk["summary"],
                        "repair_instruction": risk["repair_instruction"],
                    }
                )

    filters = [
        {"id": "all", "label": "全部页面", "count": len(cards)},
        {"id": "blocked", "label": "阻断页", "count": sum(1 for card in cards if card["blocking_count"] > 0)},
        {"id": "needs_review", "label": "待审阅", "count": sum(1 for card in cards if card["review_status"] == "needs_review")},
        {"id": "needs_evidence", "label": "待补依据", "count": sum(1 for card in cards if card["review_status"] == "needs_evidence")},
        {"id": "approved", "label": "已批准", "count": sum(1 for card in cards if card["review_status"] == "approved")},
        {"id": "rejected", "label": "已驳回", "count": sum(1 for card in cards if card["review_status"] == "rejected")},
    ]

    runtime_artifacts = ((run_state_summary.get("readiness") or {}).get("artifacts") or {})
    production_flow = {
        "stage": run_state_summary.get("stage", ""),
        "next_command": run_state_summary.get("next_command", ""),
        "generation": runtime_artifacts.get("generation", {}),
        "build": runtime_artifacts.get("build", {}),
        "render": runtime_artifacts.get("render", {}),
    }

    return {
        "schema_version": "deck_master_workspace.v0.3",
        "run_id": _resolved_run_id(root),
        "project_id": _resolved_run_id(root),
        "workspace_name": workspace_name,
        "workspace_path": str(request.get("workspace") or ""),
        "title": title,
        "project_title": title,
        "updated_at": updated_at,
        "stage": stage,
        "project_stage": stage,
        "status": run_status(root),
        "runtime": production_flow,
        "focus_page_id": focus_page_id,
        "header_metrics": {
            "pages_total": metrics.get("pages", len(cards)),
            "pages_approved": metrics.get("approved", 0),
            "pages_waiting": metrics.get("needs_review", 0),
            "pages_rejected": metrics.get("rejected", 0),
            "p0": metrics.get("p0", 0),
            "p1": metrics.get("p1", 0),
            "pending_approvals": len(pending_approvals),
            "export_ready": len(queue.get("pages", [])),
            "export_blocked": int(queue.get("blocked_count", 0)),
        },
        "health": {
            "label": stage["label"],
            "tone": stage["tone"],
            "blocking_reasons": blocking[:4],
            "next_step": stage["next_step"],
            "owner": stage["owner"],
            "expected_result": stage["expected_result"],
        },
        "queue": {
            "filters": filters,
            "pages": [{k: v for k, v in card.items() if not k.startswith("_")} for card in cards],
        },
        "run_summary": {
            "claim_coverage": claim_summary,
            "export_queue": {
                "ready": len(queue.get("pages", [])),
                "blocked": int(queue.get("blocked_count", 0)),
            },
            "approvals": approvals[:8],
            "main_risks": main_risks[:6],
            "delivery": {
                "delivered": bool(delivery.get("delivered")),
                "delivered_at": delivery.get("delivered_at"),
                "customer_reaction": delivery.get("customer_reaction", ""),
                "notes": delivery.get("notes", ""),
            },
            "delivery_preview": build_delivery_preview_payload(root),
            "production_flow": production_flow,
            "next_actions": next_actions.get("actions", [])[:5],
            "active_overrides": list_active_overrides(root),
        },
    }


def build_workspace_page_payload(run_dir: str | Path, page_id: str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = load_manifest(root)
    page = next((item for item in manifest["pages"] if item.get("page_id") == page_id), None)
    if not page:
        raise ManifestError(f"Unknown page_id: {page_id}")
    payload = page_payload(root, page)
    review_label, review_tone = _review_label(payload)
    claim_bundle = _page_claim_bundle(root, page_id)
    quality_risks = _page_quality_risks(root, payload)
    approvals = [
        task for task in _load_approval_tasks(root)
        if task.get("target_id") in {page_id, root.name}
    ]
    source_reason = (
        payload.get("decision_reason")
        or payload.get("reuse_reason")
        or payload.get("generation_reason")
        or payload.get("notes")
        or ""
    )
    critical_alerts = []
    if not payload.get("asset_exists", True):
        critical_alerts.append({"tone": "danger", "label": "预览缺失", "detail": payload.get("asset_error", "")})
    if payload.get("review_status") == "needs_evidence":
        critical_alerts.append({"tone": "warning", "label": "待补依据", "detail": "当前页仍缺少可用支撑材料。"})
    for risk in quality_risks:
        if risk.get("severity") in {"P0", "P1"}:
            critical_alerts.append({"tone": "danger", "label": risk["severity"], "detail": risk["summary"]})
    if claim_bundle["uncovered_claims"]:
        critical_alerts.append({"tone": "warning", "label": "论点未覆盖", "detail": f"{claim_bundle['uncovered_claims']} 个论点仍无证据。"})

    return {
        "schema_version": "deck_master_workspace_page.v0.2",
        "run_id": _resolved_run_id(root),
        "page": payload,
        "hero": {
            "page_number": payload.get("order"),
            "page_id": payload.get("page_id"),
            "title": payload.get("title") or payload.get("page_id"),
            "role": payload.get("narrative_role", ""),
            "source_label": _source_label(payload),
            "source_decision_label": _source_decision_label(payload),
            "review_label": review_label,
            "review_tone": review_tone,
            "confidence": payload.get("confidence"),
        },
        "summary": {
            "core_claim": claim_bundle["core_claim"],
            "evidence_policy": claim_bundle["evidence_policy"],
            "source_reason": source_reason,
            "critical_alerts": critical_alerts[:4],
            "preview_ready": bool(payload.get("asset_exists")),
        },
        "evidence": {
            "covered_claims": claim_bundle["covered_claims"],
            "uncovered_claims": claim_bundle["uncovered_claims"],
            "evidence_total": claim_bundle["evidence_total"],
            "claims": claim_bundle["claims"],
        },
        "quality": {
            "blocking": any(item["severity"] in {"P0", "P1"} for item in quality_risks),
            "risks": quality_risks,
            "overrides": list_active_overrides(root),
        },
        "approvals": {
            "tasks": approvals,
            "pending_count": sum(1 for task in approvals if task.get("status") == "pending"),
        },
        "notes": payload.get("notes", ""),
        "available_actions": [
            {"id": "approve", "label": "批准页面", "variant": "primary"},
            {"id": "reject", "label": "驳回页面", "variant": "secondary"},
            {"id": "request_evidence", "label": "请求补依据", "variant": "secondary"},
            {"id": "submit_approval", "label": "升级审批", "variant": "secondary"},
            {"id": "add_note", "label": "记录备注", "variant": "ghost"},
        ],
    }


def build_workspace_activity_payload(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    return {
        "schema_version": "deck_master_workspace_activity.v0.2",
        "run_id": _resolved_run_id(root),
        "items": _activity_items(root),
    }


def handle_workspace_page_action(run_dir: str | Path, page_id: str, body: dict[str, Any]) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    action = str(body.get("action") or "").strip()
    actor = str(body.get("actor") or "user").strip()
    note = str(body.get("note") or body.get("reason") or "").strip()
    if not action:
        raise ValueError("action is required.")
    if action == "submit_approval":
        return _create_approval_task(
            root,
            scope_type="page",
            target_id=page_id,
            subject=f"页面 {page_id} 审批",
            reason=note or "页面需要人工拍板。",
            submitted_by=actor,
        )
    if action == "approve_approval":
        return _decide_approval_task(
            root,
            approval_id=str(body.get("approval_id") or ""),
            decision="approved",
            actor=actor,
            note=note,
        )
    if action == "reject_approval":
        return _decide_approval_task(
            root,
            approval_id=str(body.get("approval_id") or ""),
            decision="rejected",
            actor=actor,
            note=note,
        )
    try:
        return execute_review_action(
            root,
            page_id,
            action,
            actor=actor,
            reason=note,
            note=note,
            finding_id=str(body.get("finding_id") or ""),
            severity=str(body.get("severity") or "P1"),
            approver=str(body.get("approver") or ""),
        )
    except WorkbenchError as exc:
        raise ValueError(str(exc)) from exc


def handle_workspace_run_action(run_dir: str | Path, body: dict[str, Any]) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    action = str(body.get("action") or "").strip()
    actor = str(body.get("actor") or "user").strip()
    note = str(body.get("note") or body.get("reason") or "").strip()
    if not action:
        raise ValueError("action is required.")

    if action == "submit_approval":
        return _create_approval_task(
            root,
            scope_type="run",
            target_id=root.name,
            subject="方案项目交付审批",
            reason=note or "当前方案项目已达到交付前置条件，申请人工审批。",
            submitted_by=actor,
        )
    if action == "approve_approval":
        return _decide_approval_task(
            root,
            approval_id=str(body.get("approval_id") or ""),
            decision="approved",
            actor=actor,
            note=note,
        )
    if action == "reject_approval":
        return _decide_approval_task(
            root,
            approval_id=str(body.get("approval_id") or ""),
            decision="rejected",
            actor=actor,
            note=note,
        )
    if action == "mark_delivered":
        delivered = bool(body.get("delivered", True))
        existing_delivery = _delivery_outcome(root)
        if delivered and existing_delivery.get("delivered"):
            return existing_delivery
        return record_delivery_outcome(
            root,
            delivered=delivered,
            advanced_to_next_stage=bool(body.get("advanced_to_next_stage", False)),
            customer_reaction=str(body.get("customer_reaction") or ""),
            notes=note,
        )
    raise ValueError(f"Unsupported workspace action: {action}")
