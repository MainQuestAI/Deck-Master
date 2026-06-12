from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_NAME = "preview_manifest.json"
SOURCE_TYPES = {"library_slide", "generated", "placeholder", "manual"}
DECISIONS = {"needs_review", "keep", "replace", "approved", "rejected"}
REVIEW_STATUSES = {"needs_review", "needs_evidence", "approved", "rejected"}
ACTION_INTENTS = {"none", "reuse", "adapt", "generate", "manual_placeholder", "replace", "request_evidence"}
SOURCE_DECISIONS = {"reuse", "adapt", "generate", "manual_placeholder", "pending_replacement"}
REQUIRED_PAGE_FIELDS = {
    "page_id",
    "order",
    "source_type",
    "preview_path",
    "narrative_role",
    "decision",
}

# Legacy decision → (review_status, action_intent)
LEGACY_TO_REVIEW: dict[str, tuple[str, str]] = {
    "approved": ("approved", "none"),
    "rejected": ("rejected", "none"),
    "needs_review": ("needs_review", "none"),
    "keep": ("approved", "reuse"),
    "replace": ("needs_review", "replace"),
}

# (review_status, action_intent) → legacy decision
REVIEW_TO_LEGACY: dict[tuple[str, str], str] = {
    ("approved", "reuse"): "keep",
    ("approved", "adapt"): "approved",
    ("approved", "generate"): "approved",
    ("approved", "none"): "approved",
    ("rejected", "none"): "rejected",
    ("needs_review", "replace"): "replace",
    ("needs_review", "none"): "needs_review",
    ("needs_evidence", "request_evidence"): "needs_review",
    ("needs_evidence", "none"): "needs_review",
}


class ManifestError(ValueError):
    pass


def migrate_page_to_review_status(page: dict) -> dict:
    """为旧 page 补充 review_status/action_intent。

    如果已有 review_status 则不覆盖。
    始终保留 legacy decision。
    """
    if "review_status" not in page:
        decision = page.get("decision", "needs_review")
        review_status, action_intent = LEGACY_TO_REVIEW.get(
            decision, ("needs_review", "none")
        )
        page["review_status"] = review_status
        page["action_intent"] = action_intent
    return page


def sync_legacy_decision(page: dict) -> dict:
    """从 review_status/action_intent 同步 legacy decision。"""
    review_status = page.get("review_status", "needs_review")
    action_intent = page.get("action_intent", "none")
    key = (review_status, action_intent)
    if key in REVIEW_TO_LEGACY:
        page["decision"] = REVIEW_TO_LEGACY[key]
    else:
        # fallback based on review_status alone
        if review_status == "approved":
            page["decision"] = "approved"
        elif review_status == "rejected":
            page["decision"] = "rejected"
        else:
            page["decision"] = "needs_review"
    return page


def manifest_path(run_dir: str | Path) -> Path:
    return Path(run_dir).expanduser().resolve() / MANIFEST_NAME


def load_manifest(run_dir: str | Path) -> dict[str, Any]:
    path = manifest_path(run_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"Missing {MANIFEST_NAME}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Invalid JSON in {MANIFEST_NAME}: {exc.msg}") from exc

    validate_manifest(data)
    normalized = deepcopy(data)
    for page in normalized["pages"]:
        migrate_page_to_review_status(page)
    normalized["pages"] = sorted(normalized["pages"], key=lambda page: page["order"])
    return normalized


def validate_manifest(data: Any) -> None:
    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a JSON object.")

    for field in ("run_id", "title", "status", "pages"):
        if field not in data:
            raise ManifestError(f"Missing required field: {field}")

    if not isinstance(data["pages"], list) or not data["pages"]:
        raise ManifestError("pages must be a non-empty list.")

    seen_page_ids: set[str] = set()
    for index, page in enumerate(data["pages"], start=1):
        if not isinstance(page, dict):
            raise ManifestError(f"Page #{index} must be an object.")

        missing = REQUIRED_PAGE_FIELDS - set(page)
        if missing:
            raise ManifestError(
                f"Page #{index} is missing required fields: {', '.join(sorted(missing))}"
            )

        page_id = page["page_id"]
        if not isinstance(page_id, str) or not page_id.strip():
            raise ManifestError(f"Page #{index} has an invalid page_id.")
        if page_id in seen_page_ids:
            raise ManifestError(f"Duplicate page_id: {page_id}")
        seen_page_ids.add(page_id)

        if not isinstance(page["order"], int):
            raise ManifestError(f"Page {page_id} order must be an integer.")
        if page["source_type"] not in SOURCE_TYPES:
            raise ManifestError(f"Page {page_id} has invalid source_type.")
        if page["decision"] not in DECISIONS:
            raise ManifestError(f"Page {page_id} has invalid decision.")
        if "review_status" in page and page["review_status"] not in REVIEW_STATUSES:
            raise ManifestError(
                f"Page {page_id} has invalid review_status: {page['review_status']}"
            )
        if "action_intent" in page and page["action_intent"] not in ACTION_INTENTS:
            raise ManifestError(
                f"Page {page_id} has invalid action_intent: {page['action_intent']}"
            )
        validate_preview_path(page["preview_path"], page_id)


def validate_preview_path(preview_path: Any, page_id: str) -> None:
    if not isinstance(preview_path, str) or not preview_path.strip():
        raise ManifestError(f"Page {page_id} has an invalid preview_path.")

    path = Path(preview_path)
    if path.is_absolute():
        raise ManifestError(f"Page {page_id} preview_path must be relative.")
    if ".." in path.parts:
        raise ManifestError(f"Page {page_id} preview_path cannot contain '..'.")


def find_page(data: dict[str, Any], page_id: str) -> dict[str, Any]:
    for page in data["pages"]:
        if page["page_id"] == page_id:
            return page
    raise ManifestError(f"Unknown page_id: {page_id}")


def write_manifest(run_dir: str | Path, data: dict[str, Any]) -> None:
    validate_manifest(data)
    path = manifest_path(run_dir)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def update_page_decision(
    run_dir: str | Path,
    page_id: str,
    decision: str,
    notes: str,
    review_status: str = "",
    action_intent: str = "",
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ManifestError(f"Invalid decision: {decision}")
    if not isinstance(notes, str):
        raise ManifestError("notes must be a string.")

    data = load_manifest(run_dir)
    page = find_page(data, page_id)
    page["decision"] = decision
    page["notes"] = notes

    if review_status or action_intent:
        # New fields provided: use them and sync legacy decision back
        if review_status:
            if review_status not in REVIEW_STATUSES:
                raise ManifestError(f"Invalid review_status: {review_status}")
            page["review_status"] = review_status
        if action_intent:
            if action_intent not in ACTION_INTENTS:
                raise ManifestError(f"Invalid action_intent: {action_intent}")
            page["action_intent"] = action_intent
        sync_legacy_decision(page)
    else:
        # Legacy path: derive review_status/action_intent from the new decision
        page.pop("review_status", None)
        page.pop("action_intent", None)
        migrate_page_to_review_status(page)

    page["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = page["reviewed_at"]
    write_manifest(run_dir, data)
    return page


def update_page_review(
    run_dir: str | Path,
    page_id: str,
    review_status: str,
    action_intent: str = "none",
    notes: str = "",
) -> dict[str, Any]:
    """使用新 review_status/action_intent 更新页面。

    同时同步 legacy decision。
    """
    if review_status not in REVIEW_STATUSES:
        raise ManifestError(f"Invalid review_status: {review_status}")
    if action_intent not in ACTION_INTENTS:
        raise ManifestError(f"Invalid action_intent: {action_intent}")

    data = load_manifest(run_dir)
    page = find_page(data, page_id)
    page["review_status"] = review_status
    page["action_intent"] = action_intent
    page["notes"] = notes
    sync_legacy_decision(page)
    page["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = page["reviewed_at"]
    write_manifest(run_dir, data)
    return page


def update_page_source_decision(
    run_dir: str | Path,
    page_id: str,
    source_decision: str,
    *,
    review_status: str = "needs_review",
    action_intent: str = "none",
    notes: str = "",
) -> dict[str, Any]:
    if source_decision not in SOURCE_DECISIONS:
        raise ManifestError(f"Invalid source_decision: {source_decision}")
    if review_status not in REVIEW_STATUSES:
        raise ManifestError(f"Invalid review_status: {review_status}")
    if action_intent not in ACTION_INTENTS:
        raise ManifestError(f"Invalid action_intent: {action_intent}")

    data = load_manifest(run_dir)
    page = find_page(data, page_id)
    page["source_decision"] = source_decision
    page["review_status"] = review_status
    page["action_intent"] = action_intent
    page["notes"] = notes
    sync_legacy_decision(page)
    page["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = page["reviewed_at"]
    write_manifest(run_dir, data)
    return page


def preview_file_path(run_dir: str | Path, page: dict[str, Any]) -> Path:
    run_root = Path(run_dir).expanduser().resolve()
    candidate = Path(os.path.abspath(run_root / page["preview_path"]))
    root_text = str(run_root)
    candidate_text = str(candidate)
    if candidate_text != root_text and not candidate_text.startswith(root_text + os.sep):
        raise ManifestError(f"Preview path escapes run directory: {page['page_id']}")
    return candidate


def page_payload(run_dir: str | Path, page: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(page)
    payload["preview_url"] = f"/preview/{page['page_id']}"
    quality = page_quality(run_dir, page["page_id"])
    if quality:
        payload["quality"] = quality

    try:
        asset_path = preview_file_path(run_dir, page)
    except ManifestError as exc:
        payload["asset_exists"] = False
        payload["asset_error"] = str(exc)
        return payload

    payload["asset_exists"] = asset_path.exists()
    payload["asset_error"] = "" if payload["asset_exists"] else "Preview asset is missing."
    return payload


def load_quality_reports(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    reports: dict[str, Any] = {}
    for gate in ("draft", "render", "delivery"):
        path = root / "quality_reports" / f"{gate}_gate.json"
        if not path.exists():
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            reports[gate] = {"status": "invalid", "findings": 0, "blocks_delivery": True}
            continue
        reports[gate] = {
            "status": report.get("status", ""),
            "blocks_delivery": bool(report.get("blocks_delivery", False)),
            "findings": len(report.get("findings", [])),
            "score_summary": report.get("score_summary", {}),
            "artifact": report.get("artifact", ""),
        }
    return reports


def page_quality(run_dir: str | Path, page_id: str) -> list[dict[str, Any]]:
    root = Path(run_dir).expanduser().resolve()
    items: list[dict[str, Any]] = []
    for gate in ("draft", "render", "delivery"):
        path = root / "quality_reports" / f"{gate}_gate.json"
        if not path.exists():
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for finding in report.get("page_findings", []):
            if finding.get("page_id") == page_id:
                item = deepcopy(finding)
                item["gate"] = gate
                items.append(item)
    return items
