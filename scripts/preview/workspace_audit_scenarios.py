from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_RUN_DIR = ROOT / "examples" / "preview-run"
FIXTURE_PROJECT_TITLE = "零售客户全渠道转型方案"

SCENARIOS = [
    {"id": "run-init-wait-preview", "state": "run-init-wait-preview", "label": "前期准备"},
    {"id": "generation-running", "state": "generation-running", "label": "内容生成中"},
    {"id": "needs-review", "state": "needs-review", "label": "待审阅方案"},
    {"id": "needs-evidence", "state": "needs-evidence", "label": "待补依据方案"},
    {"id": "pending-approval", "state": "pending-approval", "label": "待审批方案"},
    {"id": "export-ready", "state": "export-ready", "label": "可交付方案"},
    {"id": "delivered-review", "state": "delivered-review", "label": "已交付回看"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _base_request(run_id: str, project_title: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "project_name": project_title,
        "run_mode": "fixture",
        "industry": "retail",
        "audience": "client",
    }


def _base_context() -> dict[str, Any]:
    return {
        "schema_version": "deck_context_manifest.v1",
        "sources": [
            {"source_id": "ctx_001", "kind": "meeting", "title": "零售客户需求纪要"},
        ],
    }


def _base_brief(project_title: str) -> dict[str, Any]:
    return {
        "business_goal": f"{project_title}，聚焦全渠道、库存可视化和履约效率。",
        "core_points": ["全渠道一致体验", "库存可视化", "配送履约优化"],
        "audience": "CXO",
    }


def _base_claim_map() -> dict[str, Any]:
    return {
        "claims": [
            {"claim_id": "claim_001", "claim": "库存可见性是转型基础"},
            {"claim_id": "claim_002", "claim": "目标架构要支撑渠道与履约协同"},
            {"claim_id": "claim_003", "claim": "最终建议需要明确决策门槛"},
        ],
        "pages": [
            {"page_id": "page_001", "core_claim": "库存可见性是转型基础", "evidence_policy": "at_least_one"},
            {"page_id": "page_002", "core_claim": "目标架构要支撑渠道与履约协同", "evidence_policy": "at_least_one"},
            {"page_id": "page_003", "core_claim": "最终建议需要明确决策门槛", "evidence_policy": "at_least_one"},
        ],
    }


def _base_narrative_plan() -> dict[str, Any]:
    return {
        "beats": [
            {"beat_id": "page_001", "title": "现状与问题界定", "role": "问题界定"},
            {"beat_id": "page_002", "title": "目标方案结构", "role": "方案结构"},
            {"beat_id": "page_003", "title": "交付结论与决策", "role": "结论审批"},
        ]
    }


def _base_page_tasks() -> dict[str, Any]:
    return {
        "tasks": [
            {
                "beat_id": "page_001",
                "source_decision": "reuse",
                "planning": {"core_claim": "库存可见性是转型基础", "decision_intent": "reuse"},
            },
            {
                "beat_id": "page_002",
                "source_decision": "generate",
                "planning": {"core_claim": "目标架构要支撑渠道与履约协同", "decision_intent": "generate"},
            },
            {
                "beat_id": "page_003",
                "source_decision": "manual_placeholder",
                "planning": {"core_claim": "最终建议需要明确决策门槛", "decision_intent": "manual_placeholder"},
            },
        ]
    }


def _base_sourcing_plan() -> dict[str, Any]:
    return {
        "decisions": [
            {"beat_id": "page_001", "source_decision": "reuse"},
            {"beat_id": "page_002", "source_decision": "generate"},
            {"beat_id": "page_003", "source_decision": "manual_placeholder"},
        ]
    }


def _preview_pages(state: str) -> list[dict[str, Any]]:
    pages = [
        {
            "page_id": "page_001",
            "order": 1,
            "title": "现状与问题界定",
            "source_type": "library_slide",
            "preview_path": "links/page_001.svg",
            "source_pptx": "/audit/history-retail-deck.pptx",
            "source_slide_index": 12,
            "narrative_role": "问题界定",
            "reuse_reason": "沿用历史页面，问题界定结构基本匹配。",
            "confidence": 0.83,
            "decision": "needs_review",
            "review_status": "needs_review",
            "notes": "",
        },
        {
            "page_id": "page_002",
            "order": 2,
            "title": "目标方案结构",
            "source_type": "generated",
            "preview_path": "links/page_002.svg",
            "source_project": "/audit/deck-pro-max-project",
            "narrative_role": "方案结构",
            "generation_reason": "结构页需要结合当前需求重新生成。",
            "confidence": 0.76,
            "decision": "approved",
            "review_status": "approved",
            "notes": "结构通过，待最终拍板。",
        },
        {
            "page_id": "page_003",
            "order": 3,
            "title": "交付结论与决策",
            "source_type": "placeholder",
            "preview_path": "links/page_003.svg",
            "narrative_role": "结论审批",
            "reuse_reason": "结论页仍需结合客户优先级重写。",
            "decision": "rejected",
            "review_status": "rejected",
            "notes": "结论支撑不足。",
        },
    ]

    if state == "needs-review":
        return pages
    if state == "needs-evidence":
        pages[0]["decision"] = "needs_review"
        pages[0]["review_status"] = "needs_evidence"
        pages[0]["action_intent"] = "request_evidence"
        pages[0]["notes"] = "请补客户库存周转与缺货率数据。"
        pages[2]["decision"] = "approved"
        pages[2]["review_status"] = "approved"
        return pages
    if state in {"pending-approval", "export-ready", "delivered-review"}:
        for page in pages:
            page["decision"] = "approved"
            page["review_status"] = "approved"
            if page["page_id"] == "page_003":
                page["source_type"] = "generated"
                page["confidence"] = 0.79
        return pages
    return pages


def _claim_graph(state: str) -> dict[str, Any]:
    graph = {
        "claims": [
            {
                "claim_id": "claim_001",
                "statement": "库存可见性是转型基础",
                "page_refs": ["page_001"],
                "supporting_evidence": ["evidence_001"],
            },
            {
                "claim_id": "claim_002",
                "statement": "目标架构要支撑渠道与履约协同",
                "page_refs": ["page_002"],
                "supporting_evidence": ["evidence_002"],
            },
            {
                "claim_id": "claim_003",
                "statement": "最终建议需要明确决策门槛",
                "page_refs": ["page_003"],
                "supporting_evidence": ["evidence_003"],
            },
        ],
        "evidence": [
            {"evidence_id": "evidence_001", "source_ref": "src_001", "publication_status": "safe_to_use", "title": "库存周转访谈"},
            {"evidence_id": "evidence_002", "source_ref": "src_002", "publication_status": "safe_to_use", "title": "目标架构设计说明"},
            {"evidence_id": "evidence_003", "source_ref": "src_003", "publication_status": "safe_to_use", "title": "决策门槛建议"},
        ],
        "gaps": [],
    }
    if state == "needs-evidence":
        graph["claims"][0]["supporting_evidence"] = []
        graph["gaps"] = [{"gap_id": "gap_001", "claim_id": "claim_001", "description": "缺少客户库存现状数据支撑"}]
    return graph


def _quality_gate(state: str) -> dict[str, Any]:
    if state == "needs-evidence":
        return {
            "schema_version": "deck_quality_report.v1",
            "gate": "draft",
            "status": "rework_required",
            "blocks_delivery": True,
            "summary": {"p0_count": 0, "p1_count": 1, "p2_count": 0},
            "findings": [
                {
                    "finding_id": "finding_evidence_gap",
                    "severity": "P1",
                    "page_id": "page_001",
                    "message": "主论点缺少客户现状证据。",
                    "repair_instruction": "补充客户库存周转和缺货率数据。",
                }
            ],
            "page_findings": [
                {
                    "finding_id": "finding_evidence_gap",
                    "severity": "P1",
                    "page_id": "page_001",
                    "message": "主论点缺少客户现状证据。",
                    "repair_instruction": "补充客户库存周转和缺货率数据。",
                }
            ],
        }
    return {
        "schema_version": "deck_quality_report.v1",
        "gate": "draft",
        "status": "pass",
        "blocks_delivery": False,
        "summary": {"p0_count": 0, "p1_count": 0, "p2_count": 0},
        "findings": [],
        "page_findings": [],
    }


def _approval_tasks(run_id: str, state: str) -> list[dict[str, Any]]:
    if state != "pending-approval":
        return []
    return [
        {
            "approval_id": f"approval_{run_id}_run",
            "run_id": run_id,
            "scope_type": "run",
            "target_id": run_id,
            "approval_type": "approval",
            "subject": "方案交付审批",
            "reason": "所有页面已通过主审，等待负责人拍板。",
            "status": "pending",
            "submitted_by": "owner",
            "submitted_at": _now(),
            "decision_notes": "",
        }
    ]


def _delivery_outcome(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": "deck_delivery_outcome.v1",
        "run_id": run_id,
        "delivered": True,
        "delivered_at": _now(),
        "advanced_to_next_stage": True,
        "customer_reaction": "客户认可整体结构，进入下一轮细化。",
        "notes": "交付完成，可进入复盘。",
    }


def _generation_session(state: str) -> dict[str, Any] | None:
    if state == "generation-running":
        return {
            "run_id": state,
            "status": "running",
            "tool": "ppt-deck-pro-max",
            "created_at": _now(),
        }
    return None


def _generation_task_index() -> dict[str, Any]:
    return {
        "tasks": [
            {"task_id": "gen_001", "beat_id": "page_002", "status": "pending"},
        ]
    }


def _copy_preview_links(run_dir: Path) -> None:
    target = run_dir / "links"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SAMPLE_RUN_DIR / "links", target)


def _seed_delivery_preview(run_dir: Path, project_title: str, scenario_state: str) -> None:
    rendered_dir = run_dir / "rendered"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>{project_title} - 交付预览</title>
    <style>
      body {{
        margin: 0;
        padding: 32px;
        font-family: "PingFang SC", -apple-system, sans-serif;
        background: #f4f1ea;
        color: #111827;
      }}
      .deck {{
        max-width: 1280px;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 20px;
        padding: 32px;
        box-shadow: 0 24px 80px rgba(15, 23, 42, 0.12);
      }}
      .eyebrow {{
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #6b7280;
      }}
      h1 {{
        margin: 12px 0 10px;
        font-size: 40px;
        line-height: 1.02;
      }}
      p {{
        margin: 0;
        color: #4b5563;
        line-height: 1.6;
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
        margin-top: 24px;
      }}
      .card {{
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 18px;
        background: #fafaf9;
      }}
      .card strong {{
        display: block;
        margin-bottom: 8px;
        font-size: 18px;
      }}
    </style>
  </head>
  <body>
    <main class="deck">
      <span class="eyebrow">delivery preview</span>
      <h1>{project_title}</h1>
      <p>{'当前已进入交付回看阶段，可结合交付记录复盘。' if scenario_state == 'delivered-review' else '当前内容已满足交付条件，可进入最终交付确认。'}</p>
      <section class="grid">
        <article class="card">
          <strong>现状与问题界定</strong>
          <p>库存可见性是转型基础，形成共识问题定义。</p>
        </article>
        <article class="card">
          <strong>目标方案结构</strong>
          <p>目标架构支撑渠道与履约协同，形成实施主线。</p>
        </article>
        <article class="card">
          <strong>交付结论与决策</strong>
          <p>明确客户下一步决策门槛和推进建议。</p>
        </article>
      </section>
    </main>
  </body>
</html>
"""
    (rendered_dir / "index.html").write_text(html, encoding="utf-8")
    _write_json(
        run_dir / "render_results" / "render_result.json",
        {
            "schema_version": "deck_render_result.v1",
            "run_id": run_dir.name,
            "tool": "ppt-master",
            "status": "completed",
            "format": "html",
            "artifact_path": "rendered/index.html",
            "created_at": _now(),
        },
    )
    _write_json(
        run_dir / "delivery" / "final_readiness.json",
        {
            "schema_version": "deck_final_readiness.v1",
            "run_id": run_dir.name,
            "ready": True,
            "status": "ready",
            "blockers": [],
        },
    )


def _seed_common_artifacts(run_dir: Path, project_title: str) -> None:
    run_id = run_dir.name
    _write_json(run_dir / "request.json", _base_request(run_id, project_title))
    _write_json(run_dir / "context_manifest.json", _base_context())
    _write_json(run_dir / "deck_brief.json", _base_brief(project_title))
    _write_json(run_dir / "claim_map.json", _base_claim_map())
    _write_json(run_dir / "narrative_plan.json", _base_narrative_plan())
    _write_json(run_dir / "page_tasks.json", _base_page_tasks())
    _write_json(run_dir / "sourcing_plan.json", _base_sourcing_plan())
    (run_dir / "quality_reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "generation_tasks").mkdir(parents=True, exist_ok=True)


def generate_workspace_audit_runs(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    report = {
        "schema_version": "deck_master_workspace_audit_runs.v1",
        "generated_at": _now(),
        "root": str(root),
        "empty_state": {"label": "无项目空态", "url_query": ""},
        "runs": [],
    }

    for scenario in SCENARIOS:
        run_id = scenario["id"]
        scenario_state = scenario["state"]
        title = scenario["label"]
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        _seed_common_artifacts(run_dir, FIXTURE_PROJECT_TITLE)

        if scenario_state == "run-init-wait-preview":
            pass
        elif scenario_state == "generation-running":
            _write_json(run_dir / "generation_tasks" / "index.json", _generation_task_index())
            session = _generation_session("generation-running")
            if session:
                _write_json(run_dir / "generation_session.json", session)
        else:
            _copy_preview_links(run_dir)
            _write_json(
                run_dir / "preview_manifest.json",
                {
                    "run_id": run_id,
                    "title": FIXTURE_PROJECT_TITLE,
                    "status": "draft",
                    "updated_at": _now(),
                    "pages": _preview_pages(scenario_state),
                },
            )
            _write_json(run_dir / "claim_evidence_graph.json", _claim_graph(scenario_state))
            _write_json(run_dir / "quality_reports" / "draft_gate.json", _quality_gate(scenario_state))

            tasks = _approval_tasks(run_id, scenario_state)
            if tasks:
                _write_json(
                    run_dir / "review_workspace" / "approval_tasks.json",
                    {
                        "schema_version": "deck_workspace_approval.v1",
                        "tasks": tasks,
                    },
                )
            if scenario_state in {"export-ready", "delivered-review"}:
                _seed_delivery_preview(run_dir, FIXTURE_PROJECT_TITLE, scenario_state)
            if scenario_state == "delivered-review":
                _write_json(run_dir / "delivery" / "delivery_outcome.json", _delivery_outcome(run_id))

        report["runs"].append(
            {
                "run_id": run_id,
                "scenario_state": scenario_state,
                "label": scenario["label"],
                "run_dir": str(run_dir),
                "url_query": f"?run={run_id}",
            }
        )

    _write_json(root / "audit_runs_manifest.json", report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成方案工作台截图审计所需的样例项目。")
    parser.add_argument("output_root", help="Output directory for generated runs")
    args = parser.parse_args()
    manifest = generate_workspace_audit_runs(args.output_root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
