from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PREVIEW_DIR = Path(__file__).resolve().parents[1] / "preview"
sys.path.insert(0, str(PREVIEW_DIR))

from manifest import DECISIONS, load_manifest


def _get_page_findings(run_dir: Path, page_id: str) -> list[dict[str, Any]]:
    """从 quality_reports/ 获取页面相关 findings。"""
    findings: list[dict[str, Any]] = []
    quality_dir = run_dir / "quality_reports"
    if not quality_dir.exists():
        return findings

    for gate_file in sorted(quality_dir.glob("*_gate.json")):
        try:
            report = json.loads(gate_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(report, dict):
            continue
        for f in report.get("page_findings", []):
            if isinstance(f, dict) and f.get("page_id") == page_id:
                findings.append(f)
        for f in report.get("findings", []):
            if isinstance(f, dict) and f.get("page_id") == page_id:
                findings.append(f)
    return findings


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

    # 检查 quality reports
    findings = _get_page_findings(run_dir, page_id)

    for f in findings:
        severity = f.get("severity", "")
        if severity == "P0":
            return {
                "blocked": True,
                "reason": (
                    f"P0 quality finding: {f.get('finding_id', '')} - {f.get('message', '')}"
                ),
                "severity": "P0",
                "has_override": False,
            }

    p1_findings = [f for f in findings if f.get("severity") == "P1"]
    if p1_findings and not allow_override:
        return {
            "blocked": True,
            "reason": (
                "P1 quality findings without override: "
                f"{[f.get('finding_id', '') for f in p1_findings]}"
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
        "has_override": allow_override and bool(p1_findings),
    }


def export_queue(
    run_dir: Path,
    decisions: set[str],
    *,
    queue_type: str = "client",
    allow_quality_override: bool = False,
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
