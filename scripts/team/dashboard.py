from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def generate_team_quality_dashboard(
    workspace_dir: str | Path,
    runs_dir: str | Path,
) -> dict[str, Any]:
    """生成团队质量 dashboard。

    指标：
    - run_count
    - average_draft_gate_score
    - P0/P1 finding count
    - approved_page_rate
    - historical_reuse_rate
    - delivered_deck_count
    - top_failure_modes
    """
    runs_path = Path(runs_dir).expanduser().resolve()

    run_count = 0
    total_draft_score = 0
    draft_score_count = 0
    p0_count = 0
    p1_count = 0
    total_pages = 0
    approved_pages = 0
    reuse_count = 0
    total_decisions = 0
    delivered_count = 0
    failure_modes: dict[str, int] = {}

    if runs_path.exists():
        for run_dir in runs_path.iterdir():
            if not run_dir.is_dir():
                continue
            run_count += 1

            # Draft gate score
            draft_gate = run_dir / "quality_reports" / "draft_gate.json"
            if draft_gate.exists():
                try:
                    report = json.loads(draft_gate.read_text(encoding="utf-8"))
                    scorecard = report.get("scorecard", {})
                    if scorecard:
                        avg = sum(scorecard.values()) / len(scorecard)
                        total_draft_score += avg
                        draft_score_count += 1

                    for f in report.get("findings", []):
                        sev = f.get("severity", "")
                        if sev == "P0":
                            p0_count += 1
                        elif sev == "P1":
                            p1_count += 1

                        dim = f.get("dimension", "unknown")
                        failure_modes[dim] = failure_modes.get(dim, 0) + 1
                except json.JSONDecodeError:
                    pass

            # Preview manifest
            manifest_path = run_dir / "preview_manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    for page in manifest.get("pages", []):
                        total_pages += 1
                        if page.get("decision") == "approved":
                            approved_pages += 1
                except json.JSONDecodeError:
                    pass

            # Sourcing plan reuse rate
            sourcing_path = run_dir / "sourcing_plan.json"
            if sourcing_path.exists():
                try:
                    sourcing = json.loads(sourcing_path.read_text(encoding="utf-8"))
                    for d in sourcing.get("decisions", []):
                        total_decisions += 1
                        if d.get("source_decision") == "reuse":
                            reuse_count += 1
                except json.JSONDecodeError:
                    pass

            # Delivery outcome
            outcome_path = run_dir / "delivery" / "delivery_outcome.json"
            if outcome_path.exists():
                try:
                    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
                    if outcome.get("delivered"):
                        delivered_count += 1
                except json.JSONDecodeError:
                    pass

    top_failures = sorted(failure_modes.items(), key=lambda x: -x[1])[:5]

    dashboard = {
        "schema_version": "deck_team_dashboard.v1",
        "workspace_dir": str(workspace_dir),
        "metrics": {
            "run_count": run_count,
            "average_draft_gate_score": round(total_draft_score / max(draft_score_count, 1), 2),
            "p0_finding_count": p0_count,
            "p1_finding_count": p1_count,
            "approved_page_rate": round(approved_pages / max(total_pages, 1), 2),
            "historical_reuse_rate": round(reuse_count / max(total_decisions, 1), 2),
            "delivered_deck_count": delivered_count,
        },
        "top_failure_modes": [{"dimension": d, "count": c} for d, c in top_failures],
    }

    # 写 dashboard
    dash_dir = Path(workspace_dir) / "dashboards"
    dash_dir.mkdir(parents=True, exist_ok=True)
    path = dash_dir / "team_quality_dashboard.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

    return dashboard


def generate_asset_usage_dashboard(
    workspace_dir: str | Path,
) -> dict[str, Any]:
    """生成资产使用 dashboard。"""
    ws = Path(workspace_dir).expanduser().resolve()

    # 读取 asset graph
    graph_path = ws / "assets" / "asset_graph.json"
    total_assets = 0
    if graph_path.exists():
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            total_assets = len(graph.get("assets", []))
        except json.JSONDecodeError:
            pass

    # 读取 feedback
    feedback_path = ws / "assets" / "asset_feedback.jsonl"
    approval_events = 0
    rejection_events = 0
    delivery_events = 0
    if feedback_path.exists():
        for line in feedback_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                f = json.loads(line)
                et = f.get("event_type", "")
                if et == "preview_approved":
                    approval_events += 1
                elif et == "preview_rejected":
                    rejection_events += 1
                elif et == "delivered":
                    delivery_events += 1
            except json.JSONDecodeError:
                continue

    dashboard = {
        "schema_version": "deck_asset_dashboard.v1",
        "workspace_dir": str(workspace_dir),
        "metrics": {
            "total_assets": total_assets,
            "total_approvals": approval_events,
            "total_rejections": rejection_events,
            "total_deliveries": delivery_events,
        },
    }

    dash_dir = ws / "dashboards"
    dash_dir.mkdir(parents=True, exist_ok=True)
    path = dash_dir / "asset_usage_dashboard.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

    return dashboard
