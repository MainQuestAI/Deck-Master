from __future__ import annotations

from pathlib import Path
from typing import Any

from metrics.run_metrics import summarize_run_metrics
from orchestrate.export_queue import export_queue
from preview.manifest import load_manifest
from review.readiness import compute_claim_coverage, compute_deck_readiness, compute_next_actions
from uat.report import build_check, build_uat_report, write_uat_report


REQUIRED_ARTIFACTS = [
    "request.json",
    "context_manifest.json",
    "deck_brief.json",
    "claim_map.json",
    "narrative_plan.json",
    "page_tasks.json",
    "sourcing_plan.json",
    "generation_tasks/index.json",
    "preview_manifest.json",
]


def run_real_workflow_smoke(run_dir: Path, *, write: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    recommendations: list[str] = []

    for artifact in REQUIRED_ARTIFACTS:
        checks.append(build_check(f"artifact.{artifact}", (run_dir / artifact).exists(), "error", f"{artifact} missing.", refs=[artifact]))

    draft_gate_exists = (run_dir / "quality_reports" / "draft_gate.json").exists() or (run_dir / "quality_reports" / "draft_v2_gate.json").exists()
    checks.append(build_check("artifact.draft_gate", draft_gate_exists, "error", "draft gate report missing.", refs=["quality_reports/"]))

    checks.append(build_check("agentic.narrative_task_or_result", (run_dir / "advisor_tasks" / "narrative_advice_task.json").exists() or (run_dir / "advisor_results" / "narrative_advice.json").exists(), "warning", "narrative advice task/result missing."))
    quality_reports_dir = run_dir / "quality_reports"
    has_external_quality = (run_dir / "quality_review_tasks").exists() or (
        quality_reports_dir.exists() and any(quality_reports_dir.glob("external_*_gate.json"))
    )
    checks.append(build_check("agentic.quality_review_task_or_result", has_external_quality, "warning", "external quality review task/result missing."))

    phases: dict[str, str] = {}
    try:
        load_manifest(run_dir)
        compute_deck_readiness(run_dir)
        compute_claim_coverage(run_dir)
        compute_next_actions(run_dir)
        export_queue(run_dir, {"approved"}, queue_type="client")
        summarize_run_metrics(run_dir)
        checks.append(build_check("review_export.computable", True, "error", "review/export APIs computable."))
        phases["review_export"] = "pass"
    except Exception as exc:
        checks.append(build_check("review_export.computable", False, "error", f"review/export computation failed: {exc}"))
        phases["review_export"] = "fail"

    uat_dir = run_dir / "uat_reports"
    checks.append(build_check("companion.ppt_library_uat", (uat_dir / "ppt_library_uat.json").exists(), "warning", "ppt_library_uat report missing."))
    checks.append(build_check("companion.generation_tool_uat", (uat_dir / "generation_tool_uat.json").exists(), "warning", "generation_tool_uat report missing."))
    checks.append(build_check("companion.render_tool_uat", (uat_dir / "render_tool_uat.json").exists(), "warning", "render_tool_uat report missing."))

    run_artifact_fail = any(not check.get("passed") and str(check.get("check_id", "")).startswith("artifact.") for check in checks)
    phases["run_artifacts"] = "fail" if run_artifact_fail else "pass"
    agentic_warning = any(not check.get("passed") and str(check.get("check_id", "")).startswith("agentic.") for check in checks)
    phases["agentic_contract"] = "warning" if agentic_warning else "pass"
    companion_warning = any(not check.get("passed") and str(check.get("check_id", "")).startswith("companion.") for check in checks)
    phases["companion_uat"] = "warning" if companion_warning else "pass"

    if agentic_warning:
        recommendations.append("Import external narrative and quality review results before client export.")
    if companion_warning:
        recommendations.append("Run companion UAT commands before benchmark.")

    report = build_uat_report(
        run_dir,
        "real_workflow_smoke",
        checks,
        {"phases": phases},
        recommendations,
        schema_version="deck_real_workflow_smoke.v1",
    )
    report["phases"] = phases
    report["next_actions"] = recommendations
    return write_uat_report(run_dir, "real_workflow_smoke", report) if write else report
