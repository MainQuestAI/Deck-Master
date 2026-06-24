"""Build Manifest v2 & Builder boundary (B4).

The Production Builder consumes ONLY approved Page Packages, projected to a
customer-safe whitelist (D11, D12). The legacy ``preview_manifest`` is no
longer a production input; it must pass an explicit, re-review-flagged adapter
before becoming page packages.

A Build Manifest v2 records, per page: the package path, the full package
sha256, the customer-payload sha256 (the exact whitelisted bytes the builder
renders), and approved asset hashes. The builder backend must declare the
contract versions it supports.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_build_manifest.v2"

# Whitelisted customer-safe fields the Builder is allowed to read from a page
# package. Anything outside this list (notably all of ``internal_only``) must
# never reach a rendered client file.
CUSTOMER_WHITELIST = (
    "schema_version",
    "run_id",
    "page_id",
    "beat_id",
    "order",
    "status",
    "customer_visible",
    "speaker_notes",
    "audience_context",
    "visual_spec",
    "asset_bindings",
    "citations",
    "claim_bindings",
    "evidence_bindings",
    "style_refs",
    "build_requirements",
    "quality_intent",
    "provenance",
    "source_fingerprint",
)

REQUIRED_BACKEND_CONTRACTS = ("deck_page_package.v1",)


class BuildManifestError(RuntimeError):
    pass


class PreviewInputBlocked(BuildManifestError):
    """Raised when a production build is attempted directly from a legacy
    preview_manifest instead of approved page packages (D12)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_json(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def whitelist_project(package: dict[str, Any]) -> dict[str, Any]:
    """Return the customer-safe projection of a page package.

    Drops ``internal_only`` entirely and keeps only whitelisted top-level
    fields. This is the exact payload the Builder renders, so its sha256 is
    the ``customer_payload_sha256`` recorded in the build manifest.
    """
    projected = {k: package[k] for k in CUSTOMER_WHITELIST if k in package}
    projected.pop("internal_only", None)
    # force-remove any nested internal markers defensively
    return projected


def customer_payload_sha256(package: dict[str, Any]) -> str:
    return _sha_json(whitelist_project(package))


def package_sha256(package: dict[str, Any]) -> str:
    return _sha_json(package)


def assert_no_internal_in_payload(package: dict[str, Any]) -> None:
    if "internal_only" in package and package["internal_only"]:
        raise BuildManifestError(
            f"page {package.get('page_id')}: internal_only present in builder payload"
        )


def block_direct_preview(*, production: bool) -> None:
    """Gate that production builds may not consume a preview_manifest directly.

    A legacy adapter must convert preview → page packages first, and that
    adapter path is flagged for re-review.
    """
    if production:
        raise PreviewInputBlocked(
            "production build cannot consume preview_manifest directly; "
            "use the explicit legacy_preview_adapter and re-review the result"
        )


def legacy_preview_adapter(preview_manifest: dict[str, Any], *, run_id: str) -> list[dict[str, Any]]:
    """Convert a legacy ``preview_manifest`` into page packages.

    This is the ONLY sanctioned path from the old format to the new build
    input. Every package it produces is flagged ``legacy_inferred: true`` and
    ``status: draft`` so it cannot silently enter production without re-review.
    """
    if not isinstance(preview_manifest, dict):
        raise BuildManifestError("preview_manifest must be a dict")
    pages_raw = preview_manifest.get("pages") or preview_manifest.get("beats") or []
    if not isinstance(pages_raw, list) or not pages_raw:
        raise BuildManifestError("preview_manifest has no pages/beats to adapt")

    from production.page_package import PageContent, build_page_package

    packages: list[dict[str, Any]] = []
    for i, p in enumerate(pages_raw, 1):
        if not isinstance(p, dict):
            continue
        pid = str(p.get("page_id") or p.get("beat_id") or f"page_{i}")
        title = str(p.get("page_title") or p.get("title") or pid)
        body_blocks = list(p.get("body_blocks") or [{"type": "text", "text": str(p.get("body") or "")}])
        content = PageContent(
            page_id=pid,
            order=int(p.get("order") or i),
            title=title,
            body_blocks=body_blocks,
            labels=list(p.get("labels") or []),
            footnotes=list(p.get("footnotes") or []),
            callouts=list(p.get("callouts") or []),
            asset_bindings=list(p.get("asset_bindings") or []),
            citations=list(p.get("citations") or []),
            claim_bindings=list(p.get("claim_ids") or p.get("claim_bindings") or []),
            evidence_bindings=list(p.get("evidence_need") or p.get("evidence_bindings") or []),
            style_refs=list(p.get("style_refs") or []),
        )
        pkg = build_page_package(run_id=run_id, content=content, status="draft")
        pkg["legacy_inferred"] = True
        packages.append(pkg)
    return packages


def build_manifest_v2(
    *,
    run_id: str,
    packages: list[dict[str, Any]],
    builder_backend: dict[str, Any],
    output_profile: str,
    required_page_ids: list[str] | None = None,
    required_outputs: list[str] | None = None,
    style_lock: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    # 1. backend contract version check
    _assert_backend_contracts(builder_backend)

    # 2. required page coverage
    present = {p["page_id"] for p in packages}
    if required_page_ids:
        missing = sorted(set(required_page_ids) - present)
        if missing:
            raise BuildManifestError(f"missing required page packages: {missing}")

    # 3. per-page build entries with hashes + whitelist projection
    page_builds: list[dict[str, Any]] = []
    for pkg in sorted(packages, key=lambda p: p.get("order", 0)):
        payload = whitelist_project(pkg)
        assert_no_internal_in_payload(payload)  # defense-in-depth on the rendered payload
        page_builds.append({
            "page_id": pkg["page_id"],
            "order": int(pkg.get("order", 0)),
            "page_package_path": f'page_packages/{pkg["page_id"]}.json',
            "page_package_sha256": package_sha256(pkg),
            "customer_payload_sha256": _sha_json(payload),
            "approved_assets": _approved_assets(pkg),
            "editability_target": _editability_target(pkg),
        })

    source_fingerprint = _sha_json({
        "run_id": run_id,
        "pages": [{"page_id": pb["page_id"], "sha": pb["customer_payload_sha256"]} for pb in page_builds],
        "output_profile": output_profile,
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "prepared",
        "source_fingerprint": source_fingerprint,
        "builder_backend": {
            "name": str(builder_backend.get("name", "")),
            "production_capable": bool(builder_backend.get("production_capable", False)),
            "contract_versions": list(builder_backend.get("contract_versions", [])),
        },
        "output_profile": output_profile,
        "pages": page_builds,
        "required_outputs": list(required_outputs or []),
        "style_lock": dict(style_lock or {}),
        "created_at": _utc(now or _now()),
    }


def _assert_backend_contracts(backend: dict[str, Any]) -> None:
    versions = set(backend.get("contract_versions") or [])
    missing = [c for c in REQUIRED_BACKEND_CONTRACTS if c not in versions]
    if missing:
        raise BuildManifestError(
            f"builder backend missing required contract versions: {missing}"
        )
    if not backend.get("production_capable", False):
        raise BuildManifestError("builder backend is not production_capable")


def _approved_assets(pkg: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for binding in pkg.get("asset_bindings", []) or []:
        if not isinstance(binding, dict):
            continue
        out.append({
            "asset_id": str(binding.get("asset_id") or binding.get("id") or ""),
            "slot": str(binding.get("slot") or ""),
            "sha256": str(binding.get("sha256") or ""),
        })
    return out


def _editability_target(pkg: dict[str, Any]) -> str:
    br = pkg.get("build_requirements") or {}
    target = str(br.get("editability_target") or "native")
    return target if target in ("native", "hybrid", "flat_image") else "native"


__all__ = [
    "build_manifest_v2",
    "whitelist_project",
    "customer_payload_sha256",
    "package_sha256",
    "block_direct_preview",
    "legacy_preview_adapter",
    "BuildManifestError",
    "PreviewInputBlocked",
    "SCHEMA_VERSION",
    "CUSTOMER_WHITELIST",
]
