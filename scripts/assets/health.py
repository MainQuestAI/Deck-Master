from __future__ import annotations
from pathlib import Path
from typing import Any
import json

from assets.schema import load_asset_graph, save_asset_graph
from assets.feedback import read_feedback, get_asset_feedback_summary


HEALTH_FLAGS = {
    "missing_screenshot",
    "low_approval_rate",
    "high_rejection_rate",
    "stale_asset",
    "confidential_risk",
    "orphan_asset",
}


def evaluate_asset_health(
    workspace_dir: str | Path,
    *,
    runs_dir: str | Path | None = None,
) -> dict[str, Any]:
    """评估 workspace 中所有 asset 的健康状态。

    产物：assets/asset_health_report.json

    健康规则：
    - missing_screenshot: 无截图
    - low_approval_rate: approval rate < 0.5（有 3+ feedback 时）
    - high_rejection_rate: rejection count > approval count
    - stale_asset: 没有在任何近期 run 中使用
    - confidential_risk: publication_status 为 needs_redaction 或 internal_only
    - orphan_asset: 未被任何 run 引用
    """
    workspace_dir = Path(workspace_dir).expanduser().resolve()
    graph = load_asset_graph(workspace_dir)
    assets = graph.get("assets", [])
    feedback_list = read_feedback(workspace_dir)

    # 收集所有被引用的 asset IDs
    referenced_ids: set[str] = set()
    for f in feedback_list:
        cid = f.get("canonical_slide_id", "")
        if cid:
            referenced_ids.add(cid)

    # 如果提供了 runs_dir，扫描 run 中的 asset_refs
    if runs_dir:
        runs_path = Path(runs_dir).expanduser().resolve()
        if runs_path.exists():
            for run_dir in runs_path.iterdir():
                if run_dir.is_dir():
                    refs_path = run_dir / "asset_refs.json"
                    if refs_path.exists():
                        try:
                            refs = json.loads(refs_path.read_text(encoding="utf-8"))
                            for ref in refs.get("asset_refs", []):
                                cid = ref.get("canonical_slide_id", "")
                                if cid:
                                    referenced_ids.add(cid)
                        except json.JSONDecodeError:
                            pass

    health_results: list[dict[str, Any]] = []
    for asset in assets:
        cid = asset.get("canonical_slide_id", "")
        flags: list[str] = list(asset.get("health_flags", []))

        # 检查 missing_screenshot
        if not asset.get("screenshot_available", False):
            if "missing_screenshot" not in flags:
                flags.append("missing_screenshot")

        # 检查 feedback
        summary = get_asset_feedback_summary(workspace_dir, cid)
        total = summary.get("total_events", 0)
        approval_count = summary.get("approval_count", 0)
        rejection_count = summary.get("rejection_count", 0)

        if total >= 3:
            approval_rate = approval_count / total
            if approval_rate < 0.5:
                if "low_approval_rate" not in flags:
                    flags.append("low_approval_rate")

        if rejection_count > approval_count and total >= 2:
            if "high_rejection_rate" not in flags:
                flags.append("high_rejection_rate")

        # 检查 confidential_risk
        pub_status = asset.get("publication_status", "")
        if pub_status in ("needs_redaction", "internal_only"):
            if "confidential_risk" not in flags:
                flags.append("confidential_risk")

        # 检查 orphan
        if cid not in referenced_ids:
            if "orphan_asset" not in flags:
                flags.append("orphan_asset")

        # 更新 asset 的 health_flags
        asset["health_flags"] = flags

        health_results.append({
            "canonical_slide_id": cid,
            "title": asset.get("title", ""),
            "health_flags": flags,
            "approval_count": approval_count,
            "rejection_count": rejection_count,
            "total_feedback": total,
            "screenshot_available": asset.get("screenshot_available", False),
        })

    # 保存更新后的 graph
    if assets:
        save_asset_graph(workspace_dir, graph)

    report: dict[str, Any] = {
        "schema_version": "deck_asset_health.v1",
        "workspace_dir": str(workspace_dir),
        "total_assets": len(assets),
        "healthy_count": sum(1 for r in health_results if not r["health_flags"]),
        "flagged_count": sum(1 for r in health_results if r["health_flags"]),
        "assets": health_results,
        "summary": {
            "missing_screenshot": sum(1 for r in health_results if "missing_screenshot" in r["health_flags"]),
            "low_approval_rate": sum(1 for r in health_results if "low_approval_rate" in r["health_flags"]),
            "high_rejection_rate": sum(1 for r in health_results if "high_rejection_rate" in r["health_flags"]),
            "orphan_asset": sum(1 for r in health_results if "orphan_asset" in r["health_flags"]),
            "confidential_risk": sum(1 for r in health_results if "confidential_risk" in r["health_flags"]),
        },
    }

    # 写报告
    report_path = workspace_dir / "assets" / "asset_health_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = report_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(report_path)

    return report
