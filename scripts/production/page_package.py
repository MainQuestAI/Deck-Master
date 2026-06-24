"""Page Package v1 — Producer/Builder boundary (B3).

A Page Package is the formal, page-level handoff from Producer to Builder.
``customer_visible`` carries only client-safe content; ``internal_only`` carries
production rationale, agent instructions and private source refs that the
Builder must NEVER render into client files (D11, B4).

The package is the single page input the Builder consumes (D12); the legacy
``preview_manifest`` is no longer a production input.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deck_page_package.v1"

INDEX_NAME = "index.json"
PACKAGES_DIR = "page_packages"

STATUS_DRAFT = "draft"
STATUS_BLOCKED = "blocked"
STATUS_READY = "ready_for_build"
STATUS_STALE = "stale"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _sha(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# Fields that must NEVER appear in customer_visible output.
INTERNAL_ONLY_FIELDS = (
    "production_rationale",
    "agent_instructions",
    "unresolved_questions",
    "private_source_refs",
    "review_notes",
)


class PagePackageError(RuntimeError):
    pass


class InternalLeakError(PagePackageError):
    """Raised when internal-only content is found leaking into customer-visible fields."""


@dataclass
class PageContent:
    page_id: str
    order: int
    title: str
    body_blocks: list[dict[str, Any]]
    subtitle: str = ""
    labels: list[str] | None = None
    footnotes: list[str] | None = None
    callouts: list[dict[str, Any]] | None = None
    speaker_notes: str = ""
    visual_spec: dict[str, Any] | None = None
    asset_bindings: list[dict[str, Any]] | None = None
    citations: list[dict[str, Any]] | None = None
    claim_bindings: list[str] | None = None
    evidence_bindings: list[str] | None = None
    style_refs: list[str] | None = None
    build_requirements: dict[str, Any] | None = None
    quality_intent: dict[str, Any] | None = None


def build_page_package(
    *,
    run_id: str,
    content: PageContent,
    internal_only: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    source_fingerprint: str = "",
    status: str = STATUS_DRAFT,
    beat_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    customer_visible = {
        "title": content.title,
        "subtitle": content.subtitle,
        "body_blocks": list(content.body_blocks),
        "labels": list(content.labels or []),
        "footnotes": list(content.footnotes or []),
        "callouts": list(content.callouts or []),
    }
    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "page_id": content.page_id,
        "order": content.order,
        "status": status,
        "customer_visible": customer_visible,
        "speaker_notes": content.speaker_notes,
        "audience_context": {},
        "visual_spec": dict(content.visual_spec or {}),
        "asset_bindings": list(content.asset_bindings or []),
        "citations": list(content.citations or []),
        "claim_bindings": list(content.claim_bindings or []),
        "evidence_bindings": list(content.evidence_bindings or []),
        "style_refs": list(content.style_refs or []),
        "build_requirements": dict(content.build_requirements or {}),
        "quality_intent": dict(content.quality_intent or {}),
        "internal_only": _sanitize_internal(internal_only or {}),
        "provenance": _provenance(provenance, now),
        "source_fingerprint": source_fingerprint or _sha(customer_visible),
    }
    if beat_id:
        package["beat_id"] = beat_id
    assert_no_internal_leak(package)
    return package


def _sanitize_internal(internal: dict[str, Any]) -> dict[str, Any]:
    """Keep only the allowed internal_only fields; drop anything else so the
    schema's additionalProperties:false is respected."""
    out: dict[str, Any] = {}
    for k in INTERNAL_ONLY_FIELDS:
        if k in internal:
            out[k] = internal[k]
    return out


def _provenance(prov: dict[str, Any] | None, now: datetime | None) -> dict[str, Any]:
    base = {
        "producer": "deck-producer",
        "created_at": _utc(now or _now()),
        "input_artifacts": list((prov or {}).get("input_artifacts", [])),
    }
    if prov:
        for k, v in prov.items():
            if k not in base:
                base[k] = v
    return base


def assert_no_internal_leak(package: dict[str, Any]) -> None:
    """Verify no internal-only string content appears inside customer_visible.

    A leak is when a value from ``internal_only`` is duplicated verbatim into a
    customer-visible field (title / subtitle / labels / footnotes / callouts /
    body_blocks text). This is a defense-in-depth check; the Builder (B4) also
    strips ``internal_only`` before rendering.
    """
    cv = package.get("customer_visible", {})
    internal = package.get("internal_only", {})
    internal_strings: list[str] = []
    for field in INTERNAL_ONLY_FIELDS:
        val = internal.get(field)
        if isinstance(val, str) and val.strip():
            internal_strings.append(val.strip())
        elif isinstance(val, list):
            internal_strings.extend(str(v).strip() for v in val if isinstance(v, str) and v.strip())

    cv_text = _flatten_customer_text(cv)
    for needle in internal_strings:
        if len(needle) < 4:  # skip trivially short tokens
            continue
        if needle in cv_text:
            raise InternalLeakError(
                f"internal-only content leaked into customer_visible on page {package.get('page_id')}"
            )


def _flatten_customer_text(cv: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(str(cv.get("title", "")))
    parts.append(str(cv.get("subtitle", "")))
    parts.extend(str(x) for x in cv.get("labels", []))
    parts.extend(str(x) for x in cv.get("footnotes", []))
    for block in cv.get("body_blocks", []):
        parts.extend(_block_text(block))
    for co in cv.get("callouts", []):
        parts.extend(_block_text(co))
    return "\n".join(parts)


def _block_text(block: Any) -> list[str]:
    if isinstance(block, dict):
        return [str(v) for v in block.values() if isinstance(v, (str, int, float))]
    if isinstance(block, str):
        return [block]
    return []


def strip_internal(package: dict[str, Any]) -> dict[str, Any]:
    """Return a customer-safe copy with ``internal_only`` removed.

    The Builder consumes this projection so internal production notes can never
    reach a client file (D11).
    """
    safe = json.loads(json.dumps(package))
    safe.pop("internal_only", None)
    return safe


# --- index & coverage ---


class PagePackageIndex:
    def __init__(self, run_dir: str | Path) -> None:
        self.root = Path(run_dir).expanduser().resolve()
        self.dir = self.root / PACKAGES_DIR

    def write(self, package: dict[str, Any]) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f'{package["page_id"]}.json'
        path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._write_index()
        return path

    def list_packages(self) -> list[dict[str, Any]]:
        if not self.dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(self.dir.glob("*.json")):
            if p.name == INDEX_NAME:
                continue
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        out.sort(key=lambda pkg: pkg.get("order", 0))
        return out

    def coverage(self, required_page_ids: list[str]) -> dict[str, Any]:
        present = {p["page_id"] for p in self.list_packages()}
        required = set(required_page_ids)
        missing = sorted(required - present)
        ready = [p for p in self.list_packages() if p.get("status") == STATUS_READY]
        blocked = [p["page_id"] for p in self.list_packages() if p.get("status") == STATUS_BLOCKED]
        return {
            "required_pages": sorted(required),
            "present_pages": sorted(present),
            "missing_pages": missing,
            "ready_pages": [p["page_id"] for p in ready],
            "blocked_pages": blocked,
            "complete": not missing and not blocked,
        }

    def assert_required_coverage(self, required_page_ids: list[str]) -> None:
        cov = self.coverage(required_page_ids)
        if cov["missing_pages"] or cov["blocked_pages"]:
            raise PagePackageError(
                f"page package coverage incomplete: missing={cov['missing_pages']} blocked={cov['blocked_pages']}"
            )

    def _write_index(self) -> None:
        packages = self.list_packages()
        index = {
            "schema_version": SCHEMA_VERSION,
            "run_id": "",
            "page_count": len(packages),
            "pages": [
                {
                    "page_id": p["page_id"],
                    "order": p.get("order", 0),
                    "status": p.get("status"),
                    "source_fingerprint": p.get("source_fingerprint", ""),
                }
                for p in packages
            ],
        }
        (self.dir / INDEX_NAME).write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def generation_result_reference(package: dict[str, Any], *, generation_session: str = "") -> dict[str, Any]:
    """A compact reference a Generation Result v2 can carry to point at a package."""
    return {
        "page_id": package["page_id"],
        "package_path": f'{PACKAGES_DIR}/{package["page_id"]}.json',
        "source_fingerprint": package.get("source_fingerprint", ""),
        "generation_session": generation_session,
    }


__all__ = [
    "PageContent",
    "PagePackageError",
    "InternalLeakError",
    "PagePackageIndex",
    "build_page_package",
    "strip_internal",
    "assert_no_internal_leak",
    "generation_result_reference",
    "SCHEMA_VERSION",
]
