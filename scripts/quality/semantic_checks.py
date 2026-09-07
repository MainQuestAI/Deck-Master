"""SC-1 C1/Q-13: deterministic semantic pre-checks for page packages.

These checks find mechanically detectable content problems before the Agent
semantic review runs; they never replace it (D11 — engineering gates prove
structure, not truth):

- numbers in customer-visible text must be anchored to an evidence binding
  that resolves in the context manifest, or come from the approved sourcing
  selections; a bare number on a page with no resolvable source is reported;
- internal production labels must not leak into client-visible text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_NUMBER_PATTERN = re.compile(r"(?<![\w.])(\d[\d,._]*(?:\.\d+)?)\s?(%|万元|亿元|万|亿|天|周|个月|人|单|倍|pp|个百分点)?")
_INTERNAL_LABELS = ("SCR", "MBB", "SO WHAT", " Governing Thought", "行动标题")


def _customer_text(package: dict[str, Any]) -> str:
    visible = package.get("customer_visible") or {}
    parts: list[str] = []
    for block in visible.get("body_blocks") or []:
        if isinstance(block, dict):
            parts.append(str(block.get("text") or ""))
    parts.extend(str(label) for label in visible.get("labels") or [])
    parts.extend(str(callout.get("text") or callout.get("title") or "") for callout in visible.get("callouts") or [])
    return "\n".join(parts)


def find_unsupported_numbers(
    packages: list[dict[str, Any]],
    *,
    context_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Q-13: numbers with no resolvable source on the page are reported."""

    valid_source_ids = {
        str(source.get("source_id") or "").strip()
        for source in (context_manifest or {}).get("sources", [])
        if isinstance(source, dict) and str(source.get("source_id") or "").strip()
    }
    findings: list[dict[str, Any]] = []
    for package in packages:
        page_id = str(package.get("page_id") or "")
        evidence_bindings = [
            str(ref)
            for ref in (package.get("evidence_bindings") or [])
            if str(ref).strip() and (not valid_source_ids or str(ref).strip() in valid_source_ids)
        ]
        internal = package.get("internal_only") or {}
        has_design_basis = bool(str(internal.get("design_basis_ref") or "").strip())
        text = _customer_text(package)
        supported = bool(evidence_bindings) or has_design_basis
        for match in _NUMBER_PATTERN.finditer(text):
            value, unit = match.group(1), match.group(2) or ""
            if not unit and len(value.replace(",", "").replace(".", "")) < 2:
                # bare small integers are usually enumeration, not claims
                continue
            if not supported:
                findings.append(
                    {
                        "page_id": page_id,
                        "check": "unsupported_number",
                        "value": f"{value}{unit}".strip(),
                        "message": (
                            f"page {page_id}: number '{value}{unit}' appears without a resolvable evidence "
                            "binding or design basis; attach the source or remove the claim"
                        ),
                    }
                )
    return findings


def find_internal_label_leak(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for package in packages:
        page_id = str(package.get("page_id") or "")
        text = _customer_text(package)
        for label in _INTERNAL_LABELS:
            if label.lower() in text.lower():
                findings.append(
                    {
                        "page_id": page_id,
                        "check": "internal_label_leak",
                        "message": f"page {page_id}: internal production label '{label.strip()}' leaked into client-visible text",
                    }
                )
    return findings


def scan_delivery_pptx(pptx_path: str | Path) -> list[dict[str, Any]]:
    """C3/Q-10: scan a client-bound PPTX for hidden content leaks.

    Speaker notes, hidden slides, core-property metadata (author/company/
    comments/custom keywords) and internal labels are all in scope — not just
    visible body text (spec 06 §6.6). Read-only inspection.
    """

    from pptx import Presentation  # local import: only needed for delivery scan

    findings: list[dict[str, Any]] = []
    presentation = Presentation(str(pptx_path))
    props = presentation.core_properties
    metadata_checks = (
        ("author", str(props.author or "")),
        ("last_modified_by", str(props.last_modified_by or "")),
        ("comments", str(props.comments or "")),
        ("keywords", str(props.keywords or "")),
        ("category", str(props.category or "")),
    )
    for field, value in metadata_checks:
        if value.strip():
            findings.append(
                {
                    "check": "metadata_leak",
                    "field": field,
                    "message": f"delivery pptx carries {field} metadata ({value.strip()[:60]!r}); strip before client export",
                }
            )
    for index, slide in enumerate(presentation.slides, start=1):
        show_attr = slide._element.get("show")
        hidden = show_attr == "0" or bool(getattr(slide, "hidden", False))
        if hidden:
            findings.append(
                {"check": "hidden_slide", "slide": index, "message": f"slide {index} is hidden; hidden slides must not ship to clients"}
            )
        if slide.has_notes_slide:
            notes_text = str(slide.notes_slide.notes_text_frame.text or "").strip()
            if notes_text:
                findings.append(
                    {"check": "speaker_notes", "slide": index, "message": f"slide {index} carries speaker notes ({notes_text[:60]!r}); internal production language must not ship"}
                )
        for shape in slide.shapes:
            label = getattr(shape, "text", "") or ""
            for internal in _INTERNAL_LABELS:
                if internal.strip().lower() and internal.strip().lower() in str(label).lower():
                    findings.append(
                        {"check": "internal_label_leak", "slide": index, "message": f"slide {index} shows internal label '{internal.strip()}'"}
                    )
    return findings
