from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
PREVIEW_DIR = SCRIPTS_DIR / "preview"
QUALITY_DIR = SCRIPTS_DIR / "quality"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PREVIEW_DIR))
sys.path.insert(0, str(QUALITY_DIR))

from manifest import DECISIONS, load_manifest
from overrides import has_active_override
from runtime.final_readiness import final_readiness_clearance
from runtime.final_approval import final_approval_clearance

DRAFT_GATE_FILES = {"draft_gate.json", "draft_v2_gate.json"}
BLOCKING_STATUSES = {"rework_required"}


def _load_gate_reports(run_dir: Path) -> list[dict[str, Any]]:
    """Load valid quality gate reports for export policy checks."""
    reports: list[dict[str, Any]] = []
    quality_dir = run_dir / "quality_reports"
    if not quality_dir.exists():
        return reports

    for gate_file in sorted(quality_dir.glob("*_gate.json")):
        try:
            report = json.loads(gate_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(report, dict):
            continue
        report = dict(report)
        report["_gate_name"] = str(report.get("gate") or gate_file.stem.removesuffix("_gate"))
        report["_report_file"] = gate_file.name
        reports.append(report)
    return reports


def _has_draft_gate_report(reports: list[dict[str, Any]]) -> bool:
    return any(report.get("_report_file") in DRAFT_GATE_FILES for report in reports)


def _report_blocks_delivery(report: dict[str, Any]) -> bool:
    return bool(report.get("blocks_delivery")) or str(report.get("status", "")).lower() in BLOCKING_STATUSES


def _client_customer_visible_safety_block(final_readiness: dict[str, Any]) -> str:
    readiness = final_readiness.get("readiness") if isinstance(final_readiness.get("readiness"), dict) else {}
    safety = readiness.get("customer_visible_safety") if isinstance(readiness.get("customer_visible_safety"), dict) else {}
    if safety and not safety.get("path"):
        return "客户可见内容安全检查尚未完成。"
    return ""


def _finding_id(finding: dict[str, Any]) -> str:
    return str(
        finding.get("finding_id")
        or finding.get("id")
        or finding.get("code")
        or finding.get("message")
        or "unknown_finding"
    )


def _report_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in ("findings", "page_findings"):
        for finding in report.get(key, []):
            if isinstance(finding, dict):
                item = dict(finding)
                item["_gate_name"] = report.get("_gate_name", "")
                findings.append(item)
    return findings


def _get_blocking_findings(run_dir: Path, page_id: str) -> list[dict[str, Any]]:
    """Collect page-level and run-level blocking findings for a page."""
    findings: list[dict[str, Any]] = []

    for report in _load_gate_reports(run_dir):
        report_blocks = _report_blocks_delivery(report)
        report_findings = _report_findings(report)
        matched = False

        for finding in report_findings:
            severity = str(finding.get("severity", "")).upper()
            if severity not in {"P0", "P1"}:
                continue
            finding_page_id = finding.get("page_id")
            if finding_page_id == page_id:
                findings.append(finding)
                matched = True
            elif report_blocks:
                findings.append(finding)

        if report_blocks and not matched and not report_findings:
            findings.append(
                {
                    "severity": "P1",
                    "finding_id": f"{report.get('_gate_name', 'quality')}_gate_blocking",
                    "message": f"{report.get('_gate_name', 'quality')} gate blocks delivery.",
                    "_gate_name": report.get("_gate_name", ""),
                }
            )
    return findings


def has_client_export_quality_clearance(
    run_dir: Path,
    *,
    allow_quality_override: bool = False,
) -> dict[str, Any]:
    """Return run-level quality clearance used by UI and export."""
    reports = _load_gate_reports(run_dir)
    if not _has_draft_gate_report(reports):
        return {
            "ready": False,
            "reason": "Missing draft gate report: needs_draft_gate.",
            "blocking_findings": [],
        }

    blocking_findings: list[dict[str, Any]] = []
    for report in reports:
        if not _report_blocks_delivery(report):
            continue
        report_findings = [
            finding
            for finding in _report_findings(report)
            if str(finding.get("severity", "")).upper() in {"P0", "P1"}
        ]
        if report_findings:
            blocking_findings.extend(report_findings)
        else:
            blocking_findings.append(
                {
                    "severity": "P1",
                    "finding_id": f"{report.get('_gate_name', 'quality')}_gate_blocking",
                    "message": f"{report.get('_gate_name', 'quality')} gate blocks delivery.",
                    "_gate_name": report.get("_gate_name", ""),
                }
            )

    p0_findings = [finding for finding in blocking_findings if str(finding.get("severity", "")).upper() == "P0"]
    if p0_findings:
        return {
            "ready": False,
            "reason": f"P0 quality findings block client export: {[_finding_id(f) for f in p0_findings]}",
            "blocking_findings": blocking_findings,
        }

    p1_findings = [finding for finding in blocking_findings if str(finding.get("severity", "")).upper() == "P1"]
    if p1_findings:
        missing_overrides = [
            finding
            for finding in p1_findings
            if not allow_quality_override or not has_active_override(run_dir, _finding_id(finding))
        ]
        if missing_overrides:
            return {
                "ready": False,
                "reason": f"P1 quality findings require active overrides: {[_finding_id(f) for f in missing_overrides]}",
                "blocking_findings": blocking_findings,
            }

    return {"ready": True, "reason": "", "blocking_findings": blocking_findings}


def check_page_quality_blocking(
    run_dir: Path,
    page: dict[str, Any],
    *,
    queue_type: str,
    allow_override: bool,
) -> dict[str, Any]:
    """检查单个页面是否被 quality blocking。

    返回：
    {
        "blocked": bool,
        "reason": str,
        "severity": str,  # "P0", "P1", ""
        "has_override": bool,
    }
    """
    if queue_type == "internal":
        return {"blocked": False, "reason": "", "severity": "", "has_override": False}

    page_id = page.get("page_id", "")

    # 检查 review_status（新字段优先，回退到 decision）
    review_status = page.get("review_status", "")
    if not review_status:
        decision = page.get("decision", "needs_review")
        if decision == "approved":
            review_status = "approved"
        elif decision == "rejected":
            review_status = "rejected"
        else:
            review_status = "needs_review"

    if review_status != "approved":
        return {
            "blocked": True,
            "reason": f"Page review_status is '{review_status}', not approved.",
            "severity": "",
            "has_override": False,
        }

    reports = _load_gate_reports(run_dir)
    if not _has_draft_gate_report(reports):
        return {
            "blocked": True,
            "reason": "Missing draft gate report: needs_draft_gate.",
            "severity": "",
            "has_override": False,
        }

    findings = _get_blocking_findings(run_dir, page_id)

    for f in findings:
        severity = str(f.get("severity", "")).upper()
        if severity == "P0":
            return {
                "blocked": True,
                "reason": (
                    f"P0 quality finding: {_finding_id(f)} - {f.get('message', '')}"
                ),
                "severity": "P0",
                "has_override": False,
            }

    # P0-1: P1 finding 必须逐条有 active override（target_id == finding_id）
    p1_findings = [f for f in findings if str(f.get("severity", "")).upper() == "P1"]
    p1_without_override = [
        f for f in p1_findings
        if not allow_override or not has_active_override(run_dir, _finding_id(f))
    ]
    if p1_without_override:
        return {
            "blocked": True,
            "reason": (
                "P1 quality findings without active override: "
                f"{[_finding_id(f) for f in p1_without_override]}"
            ),
            "severity": "P1",
            "has_override": False,
        }

    # 检查 manual_placeholder action_intent
    action_intent = page.get("action_intent", "")
    if action_intent == "manual_placeholder":
        return {
            "blocked": True,
            "reason": (
                "Page has manual_placeholder action_intent, only allowed in internal queue."
            ),
            "severity": "",
            "has_override": False,
        }

    return {
        "blocked": False,
        "reason": "",
        "severity": "",
        "has_override": bool(p1_findings),  # P1 已逐条验证有 active override 才放行
    }


def export_queue(
    run_dir: Path,
    decisions: set[str],
    *,
    queue_type: str = "client",
    allow_quality_override: bool = False,
    enforce_final_readiness: bool = True,
) -> dict[str, Any]:
    """导出审查后的页面队列。

    queue_type="client" 时执行 quality blocking：
    - review_status 必须为 approved 才能进入 client export
    - P0 finding 一律阻断
    - P1 finding 需要 active override（allow_quality_override=True 时放行）
    - 找不到 quality report 时默认 needs_quality_review，不进 client queue

    queue_type="internal" 时保留所有匹配 decision 的页面。
    """
    invalid = decisions - DECISIONS
    if invalid:
        raise ValueError(f"Invalid decisions: {', '.join(sorted(invalid))}")

    manifest = load_manifest(run_dir)
    pages: list[dict[str, Any]] = []
    blocked_pages: list[dict[str, Any]] = []
    final_readiness = final_readiness_clearance(run_dir)
    final_approval = final_approval_clearance(run_dir)
    final_readiness_blocks_client = (
        queue_type == "client"
        and enforce_final_readiness
        and not bool(final_readiness.get("ready"))
    )
    final_approval_blocks_client = (
        queue_type == "client"
        and enforce_final_readiness
        and not bool(final_approval.get("ready"))
    )
    final_safety_block_reason = (
        _client_customer_visible_safety_block(final_readiness)
        if queue_type == "client" and enforce_final_readiness
        else ""
    )

    for page in manifest["pages"]:
        if page["decision"] not in decisions:
            continue

        blocking = check_page_quality_blocking(
            run_dir,
            page,
            queue_type=queue_type,
            allow_override=allow_quality_override,
        )

        page_entry: dict[str, Any] = {
            "page_id": page["page_id"],
            "order": page["order"],
            "title": page.get("title", page["page_id"]),
            "source_type": page["source_type"],
            "decision": page["decision"],
            "preview_path": page["preview_path"],
            "source_preview_asset": page.get("source_preview_asset", ""),
            "source_pptx": page.get("source_pptx", ""),
            "source_slide_index": page.get("source_slide_index", ""),
            "source_project": page.get("source_project", ""),
            "narrative_role": page.get("narrative_role", ""),
            "notes": page.get("notes", ""),
        }

        if blocking["blocked"]:
            page_entry["quality_blocked"] = True
            page_entry["quality_block_reason"] = blocking["reason"]
            blocked_pages.append(page_entry)
        elif final_readiness_blocks_client or final_approval_blocks_client or final_safety_block_reason:
            page_entry["quality_blocked"] = True
            page_entry["final_readiness_blocked"] = True
            page_entry["quality_block_reason"] = (
                final_safety_block_reason
                or str(final_readiness.get("reason") or "")
                or str(final_approval.get("reason") or "Final approval is blocked.")
            )
            page_entry["final_readiness_reason"] = page_entry["quality_block_reason"]
            blocked_pages.append(page_entry)
        else:
            if blocking.get("has_override"):
                page_entry["quality_override_active"] = True
            pages.append(page_entry)

    return {
        "run_id": manifest["run_id"],
        "title": manifest["title"],
        "source_manifest": str((run_dir / "preview_manifest.json").resolve()),
        "decisions": sorted(decisions),
        "queue_type": queue_type,
        "final_readiness": {
            "ready": bool(final_readiness.get("ready")),
            "status": str(final_readiness.get("status") or ""),
            "reason": str(final_readiness.get("reason") or ""),
            "path": str(final_readiness.get("path") or ""),
            "enforced": bool(queue_type == "client" and enforce_final_readiness),
            "degraded": bool(queue_type == "internal" and not final_readiness.get("ready")),
        },
        "final_approval": {
            "ready": bool(final_approval.get("ready")),
            "reason": str(final_approval.get("reason") or ""),
            "path": str(final_approval.get("path") or ""),
            "enforced": bool(queue_type == "client" and enforce_final_readiness),
        },
        "pages": pages,
        "blocked_pages": blocked_pages,
        "blocked_count": len(blocked_pages),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the reviewed page queue for the next Deck step.")
    parser.add_argument("run_dir", help="Directory containing preview_manifest.json")
    parser.add_argument("--output", help="Write JSON to this path instead of stdout")
    parser.add_argument(
        "--decision",
        action="append",
        dest="decisions",
        default=["approved"],
        help="Decision to include. Repeat for multiple decisions.",
    )
    parser.add_argument(
        "--queue-type",
        choices=["client", "internal"],
        default="client",
        help="Queue type. 'client' applies quality blocking; 'internal' keeps all matched pages.",
    )
    parser.add_argument(
        "--allow-quality-override",
        action="store_true",
        help="Allow P1 findings to pass client queue with an explicit override flag.",
    )
    args = parser.parse_args()

    try:
        payload = export_queue(
            Path(args.run_dir).expanduser().resolve(),
            set(args.decisions),
            queue_type=args.queue_type,
            allow_quality_override=args.allow_quality_override,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).expanduser().resolve().write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
