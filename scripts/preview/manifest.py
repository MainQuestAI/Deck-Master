from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_NAME = "preview_manifest.json"
SOURCE_TYPES = {"library_slide", "generated", "placeholder", "manual"}
DECISIONS = {"needs_review", "keep", "replace", "approved"}
REQUIRED_PAGE_FIELDS = {
    "page_id",
    "order",
    "source_type",
    "preview_path",
    "narrative_role",
    "decision",
}


class ManifestError(ValueError):
    pass


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
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ManifestError(f"Invalid decision: {decision}")
    if not isinstance(notes, str):
        raise ManifestError("notes must be a string.")

    data = load_manifest(run_dir)
    page = find_page(data, page_id)
    page["decision"] = decision
    page["notes"] = notes
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

    try:
        asset_path = preview_file_path(run_dir, page)
    except ManifestError as exc:
        payload["asset_exists"] = False
        payload["asset_error"] = str(exc)
        return payload

    payload["asset_exists"] = asset_path.exists()
    payload["asset_error"] = "" if payload["asset_exists"] else "Preview asset is missing."
    return payload
