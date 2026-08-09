from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contracts import ContractError, assert_valid, read_json, run_relative, safe_run_path, sha256_file, utc_now, write_json


TARGET_PAGE_IDS = ("P06", "P30", "P46", "P49", "P50", "P60")
SOURCE_INDEX_RELATIVE = "docs/qa/high-density-builder-v2/phase-4-73-page-external-mvp-index.json"


class IconExternalAcceptanceError(ContractError):
    pass


def _find_blueprint(root: Path, page_id: str) -> Path | None:
    for candidate in (
        root / "high_density_build" / "blueprints" / f"{page_id}.normalized.png",
        root / "high_density_build" / "blueprints" / f"{page_id}.png",
        root / "high_density_build" / "blueprints" / f"{page_id}.jpg",
    ):
        if candidate.is_file():
            return candidate
    return None


def _required_artifacts(root: Path, page_id: str) -> dict[str, Path | None]:
    return {
        "source_blueprint": _find_blueprint(root, page_id),
        "native_svg": root / "high_density_build" / "svg" / f"{page_id}.svg",
        "svg_to_pptx_metrics": root / "high_density_build" / "reviews" / f"{page_id}.svg_vs_pptx.metrics.json",
        "pptx": root / "high_density_build" / "pptx" / "deck_high_density.pptx",
        "readback": root / "high_density_build" / "readback" / "readback_report.json",
    }


def _artifact_ref(root: Path, path: Path) -> dict[str, str]:
    return {"path": run_relative(root, path), "sha256": sha256_file(path)}


def _page_evidence(root: Path, page_id: str, readback: dict[str, Any]) -> dict[str, Any]:
    artifacts = _required_artifacts(root, page_id)
    missing = [name for name, path in artifacts.items() if path is None or not path.is_file()]
    if missing:
        return {
            "page_id": page_id,
            "status": "blocked",
            "artifacts": {},
            "object_check_count": 0,
            "unresolved_icon_count": 0,
            "blockers": [f"missing local artifact: {name}" for name in missing],
        }

    metrics_path = artifacts["svg_to_pptx_metrics"]
    assert metrics_path is not None
    metrics = read_json(metrics_path)
    blockers: list[str] = []
    if str(metrics.get("comparison", {}).get("kind") or "") != "svg_vs_pptx":
        blockers.append("metrics are not an SVG-to-PPTX comparison")
    if str(metrics.get("status") or "") != "pass":
        blockers.append("SVG-to-PPTX metrics did not pass")
    object_checks = [item for item in metrics.get("object_checks") or [] if isinstance(item, dict)]
    failed_objects = [str(item.get("visual_id") or "<unknown>") for item in object_checks if item.get("status") != "pass"]
    if failed_objects:
        blockers.append(f"local visual object checks failed: {', '.join(failed_objects)}")
    for item in object_checks:
        for field in ("source_crop_path", "svg_crop_path", "pptx_crop_path"):
            value = str(item.get(field) or "")
            if not value:
                blockers.append(f"{item.get('visual_id') or '<unknown>'} is missing {field}")
                continue
            try:
                crop = safe_run_path(root, value)
            except ContractError:
                blockers.append(f"{item.get('visual_id') or '<unknown>'} has an unsafe {field}")
                continue
            if not crop.is_file():
                blockers.append(f"{item.get('visual_id') or '<unknown>'} crop is missing: {field}")

    page_readback = next((item for item in readback.get("pages") or [] if str(item.get("page_id") or "") == page_id), None)
    if str(readback.get("status") or "") != "pass":
        blockers.append("PPTX readback report did not pass")
    if page_readback is None:
        blockers.append("PPTX readback has no page entry")
    elif page_readback.get("geometry_mismatches") or page_readback.get("missing_elements"):
        blockers.append("PPTX readback has missing elements or geometry mismatches")

    refs = {name: _artifact_ref(root, path) for name, path in artifacts.items() if path is not None}
    unresolved_count = sum(
        1
        for finding in metrics.get("findings") or []
        if "unresolved_icon" in json.dumps(finding, ensure_ascii=False)
    )
    if unresolved_count:
        blockers.append(f"unresolved_icon findings: {unresolved_count}")
    return {
        "page_id": page_id,
        "status": "pass" if not blockers else "failed",
        "artifacts": refs,
        "object_check_count": len(object_checks),
        "unresolved_icon_count": unresolved_count,
        "blockers": blockers,
    }


def build_icon_external_acceptance(
    run_dir: str | Path,
    *,
    output: str | Path | None = None,
    source_index: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    source_path = Path(source_index).expanduser().resolve() if source_index else Path(__file__).resolve().parents[2] / SOURCE_INDEX_RELATIVE
    if not source_path.is_file():
        raise IconExternalAcceptanceError(f"missing 73-page source index: {source_path}")
    readback_path = root / "high_density_build" / "readback" / "readback_report.json"
    readback = read_json(readback_path) if readback_path.is_file() else {}
    pages = [_page_evidence(root, page_id, readback) for page_id in TARGET_PAGE_IDS]
    blockers = [f"{page['page_id']}: {blocker}" for page in pages for blocker in page.get("blockers") or []]
    if any(page["status"] == "blocked" for page in pages):
        status = "blocked_missing_local_benchmark_artifacts"
    elif blockers:
        status = "failed"
    else:
        status = "pass"
    evidence = {
        "schema_version": "deck_high_density_icon_external_acceptance.v1",
        "source_index": {"path": SOURCE_INDEX_RELATIVE if source_index is None else source_path.name, "sha256": sha256_file(source_path)},
        "target_page_ids": list(TARGET_PAGE_IDS),
        "status": status,
        "raw_artifacts_included": False,
        "pages": pages,
        "blockers": blockers,
        "created_at": utc_now(),
    }
    assert_valid("icon_external_acceptance", evidence)
    if output is not None:
        write_json(Path(output).expanduser().resolve(), evidence)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate six-page external high-density SVG-to-PPTX icon evidence.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-index", type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = build_icon_external_acceptance(args.run_dir, output=args.output, source_index=args.source_index)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
