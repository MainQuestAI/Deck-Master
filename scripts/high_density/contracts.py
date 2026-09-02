from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts"
SCHEMA_FILES = {
    "page_package": "page-package.v1.schema.json",
    "content_lock": "content-lock.v2.schema.json",
    "blueprint_manifest": "blueprint-manifest.v2.schema.json",
    "blueprint_prompt": "blueprint-prompt.v1.schema.json",
    "blueprint_content_review": "blueprint-content-review.v1.schema.json",
    "page_scene": "page-scene.v2.schema.json",
    "visual_metrics": "visual-metrics.v1.schema.json",
    "visual_review": "visual-review.v2.schema.json",
    "svg_to_drawingml_trace": "svg-to-drawingml-trace.v1.schema.json",
    "pptx_readback": "pptx-readback.v2.schema.json",
    "high_density_manifest": "high-density-manifest.v2.schema.json",
    "high_density_status": "high-density-status.v2.schema.json",
    "mbb_plan": "mbb-plan.v1.schema.json",
    "mbb_selection_receipt": "mbb-selection-receipt.v1.schema.json",
    "mbb_user_decision_receipt": "mbb-user-decision-receipt.v1.schema.json",
    "mbb_runtime_seal": "mbb-runtime-seal.v1.schema.json",
    "style_lock": "style-lock.v1.schema.json",
    "build_manifest": "build-manifest.v2.schema.json",
    "artifact_manifest": "artifact-manifest.v1.schema.json",
    "render_result": "render-result.v2.schema.json",
    "provider_smoke": "high-density-provider-smoke.v1.schema.json",
    "provider_host_receipt": "provider-host-receipt.v1.schema.json",
    "provider_runtime_receipt": "provider-runtime-receipt.v1.schema.json",
    "visual_main_review_receipt": "visual-main-review-receipt.v1.schema.json",
    "icon_external_acceptance": "high-density-icon-external-acceptance.v1.schema.json",
}

LEGACY_SCHEMA_FILES = {
    "build_manifest": "build-manifest-legacy.v2.schema.json",
    "page_scene": "page-scene-legacy.v2.schema.json",
    "provider_host_receipt": "provider-host-receipt-legacy.v1.schema.json",
}

PREVIEW_SCHEMA_FILES = {
    "content_lock": "content-lock.v1.schema.json",
    "blueprint_manifest": "blueprint-manifest.v1.schema.json",
    "page_scene": "page-scene.v1.schema.json",
    "high_density_manifest": "high-density-manifest.v1.schema.json",
    "high_density_status": "high-density-status.v1.schema.json",
}


class ContractError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"missing JSON artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON artifact {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON artifact must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def run_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"artifact path escapes run directory: {path}") from exc


def safe_run_path(root: Path, value: str) -> Path:
    raw = str(value or "").strip()
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or ".." in candidate.parts:
        raise ContractError(f"artifact path must be run-relative: {raw}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ContractError(f"artifact path escapes run directory: {raw}") from exc
    return resolved


def _is_legacy_build_manifest(document: dict[str, Any]) -> bool:
    if document.get("schema_version") != "deck_build_manifest.v2":
        return False
    pages = document.get("pages")
    return isinstance(pages, list) and bool(pages) and all(
        isinstance(page, dict) and "page_role" not in page for page in pages
    )


def _is_legacy_page_scene(document: dict[str, Any]) -> bool:
    return document.get("schema_version") == "deck_page_scene.v2" and "page_role" not in document


def validate_document(kind: str, document: dict[str, Any]) -> dict[str, Any]:
    schema_name = SCHEMA_FILES.get(kind)
    schema_version = document.get("schema_version")
    if isinstance(schema_version, str) and schema_version.endswith(".v1") and kind in PREVIEW_SCHEMA_FILES:
        # v1 artifacts remain readable for migration/diagnostics. Production
        # writers and handback validation always call the v2 schema above.
        schema_name = PREVIEW_SCHEMA_FILES[kind]
    if kind == "provider_host_receipt" and not any(
        field in document for field in ("imported_at", "declared_provider", "approved_by")
    ):
        # Provider host receipts kept the v1 version while their provenance
        # fields were extended. Preserve signed receipts written before that
        # extension without weakening validation for new receipts.
        schema_name = LEGACY_SCHEMA_FILES[kind]
    if kind == "build_manifest" and _is_legacy_build_manifest(document):
        # Build Manifest v2 gained page_role after older runs had already
        # persisted manifests. Validate those files with the legacy shape;
        # the high-density resume path refreshes them before writing again.
        schema_name = LEGACY_SCHEMA_FILES[kind]
    if kind == "page_scene" and _is_legacy_page_scene(document):
        # page_scene.v2 gained a required page_role after older scenes had
        # already been persisted. The loader validates and migrates those
        # scenes before handing them to the current production path.
        schema_name = LEGACY_SCHEMA_FILES[kind]
    if not schema_name:
        raise ContractError(f"unknown contract kind: {kind}")
    schema_path = SCHEMA_DIR / schema_name
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - declared runtime dependency
        raise ContractError("jsonschema is required for high-density contract validation") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: str(list(item.absolute_path)))
    ]
    return {"valid": not errors, "errors": errors, "schema": schema_name}


def assert_valid(kind: str, document: dict[str, Any]) -> None:
    result = validate_document(kind, document)
    if not result["valid"]:
        raise ContractError(f"{kind} contract invalid: {'; '.join(result['errors'])}")


def assert_v2(kind: str, document: dict[str, Any]) -> None:
    """Validate a production document and reject preview-era v1 artifacts."""
    expected = {
        "content_lock": "deck_content_lock.v2",
        "blueprint_manifest": "deck_blueprint_manifest.v2",
        "blueprint_prompt": "deck_blueprint_prompt.v1",
        "blueprint_content_review": "deck_blueprint_content_review.v1",
        "page_scene": "deck_page_scene.v2",
        "visual_metrics": "deck_visual_metrics.v1",
        "visual_review": "deck_visual_review.v2",
        "svg_to_drawingml_trace": "deck_svg_to_drawingml_trace.v1",
        "pptx_readback": "deck_pptx_readback.v2",
        "high_density_manifest": "deck_high_density_manifest.v2",
        "high_density_status": "deck_high_density_status.v2",
        "mbb_plan": "deck_mbb_plan.v1",
        "mbb_selection_receipt": "deck_mbb_selection_receipt.v1",
        "mbb_user_decision_receipt": "deck_mbb_user_decision_receipt.v1",
        "mbb_runtime_seal": "deck_mbb_runtime_seal.v1",
        "style_lock": "deck_high_density_style_lock.v1",
        "provider_host_receipt": "deck_provider_host_receipt.v1",
        "provider_runtime_receipt": "deck_provider_runtime_receipt.v1",
        "visual_main_review_receipt": "deck_visual_main_review_receipt.v1",
    }.get(kind)
    if expected and document.get("schema_version") != expected:
        raise ContractError(f"{kind} production contract must use {expected}")
    schema_name = SCHEMA_FILES.get(kind)
    if not schema_name:
        raise ContractError(f"unknown contract kind: {kind}")
    result = validate_document(kind, document)
    if not result["valid"]:
        raise ContractError(f"{kind} contract invalid: {'; '.join(result['errors'])}")


__all__ = [
    "ContractError",
    "SCHEMA_DIR",
    "assert_valid",
    "assert_v2",
    "canonical_json",
    "read_json",
    "run_relative",
    "safe_run_path",
    "sha256_file",
    "sha256_json",
    "utc_now",
    "validate_document",
    "write_json",
]
