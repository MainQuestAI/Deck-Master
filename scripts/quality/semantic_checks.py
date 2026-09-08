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
import hashlib
from pathlib import Path
from typing import Any

_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9.])(\d[\d,._]*(?:\.\d+)?)\s?(%|万元|亿元|万|亿|天|周|个月|人|单|倍|pp|个百分点)?")
_INTERNAL_LABELS = ("SCR", "MBB", "SO WHAT", " Governing Thought", "行动标题")
_LOCAL_PATH = re.compile(r"(?:/(?:Users|home|private|var|etc|tmp)/|[A-Za-z]:\\)")


def _customer_claims(package: dict[str, Any]) -> list[str]:
    visible = package.get("customer_visible") or {}
    claims = [str(visible.get(key) or "") for key in ("title", "subtitle")]
    claims.extend(str(block.get("text") or "") for block in visible.get("body_blocks") or [] if isinstance(block, dict))
    claims.extend(str(label) for label in visible.get("labels") or [])
    claims.extend(str(item.get("text") or item.get("title") or "") for item in visible.get("callouts") or [] if isinstance(item, dict))
    claims.extend(str(item) for item in visible.get("footnotes") or [])
    return [claim for claim in claims if claim.strip()]


def _customer_text(package: dict[str, Any]) -> str:
    return "\n".join(_customer_claims(package))


def find_unsupported_numbers(
    packages: list[dict[str, Any]],
    *,
    context_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Require reviewed support for each exact numeric claim, not a page citation.

    Package citations bind ``claim_text`` to an existing Context evidence_id,
    with explicit unit and period. Context evidence_candidates already carry
    the statement, captured quote hash, applicability and review provenance.
    A reviewer establishes the support relation; number-string overlap cannot.
    """
    evidence: dict[str, list[dict]] = {}
    for source in (context_manifest or {}).get("sources") or []:
        if not isinstance(source, dict):
            continue
        for item in source.get("evidence_candidates") or []:
            if isinstance(item, dict) and item.get("evidence_id"):
                evidence.setdefault(str(item["evidence_id"]), []).append(item)
    findings: list[dict[str, Any]] = []
    for package in packages:
        page_id = str(package.get("page_id") or "")
        bound = set(str(ref) for ref in package.get("evidence_bindings") or [])
        citations = [item for item in package.get("citations") or [] if isinstance(item, dict)]
        for claim in _customer_claims(package):
            for match in _NUMBER_PATTERN.finditer(claim):
                value, unit = match.group(1), match.group(2) or ""
                if not unit and len(value.replace(",", "").replace(".", "")) < 2:
                    continue
                supported = False
                for citation in citations:
                    candidates = evidence.get(str(citation.get("evidence_id") or ""), [])
                    if citation.get("claim_text") != claim or citation.get("evidence_id") not in bound or len(candidates) != 1:
                        continue
                    candidate = candidates[0]
                    quote = str(candidate.get("quote") or "")
                    if (
                        candidate.get("statement") == claim
                        and candidate.get("review_status") == "supported"
                        and str(candidate.get("review_ref") or "").strip()
                        and candidate.get("publication_status") == "safe_to_use"
                        and candidate.get("source_position")
                        and quote
                        and candidate.get("quote_sha256") == hashlib.sha256(quote.encode("utf-8")).hexdigest()
                        and "unit" in citation and "period" in citation
                        and citation["unit"] == candidate.get("unit")
                        and citation["period"] == candidate.get("period")
                        and (not unit or unit == citation["unit"])
                    ):
                        supported = True
                        break
                if not supported:
                    findings.append({
                        "page_id": page_id,
                        "check": "unsupported_number",
                        "value": f"{value}{unit}".strip(),
                        "claim_text": claim,
                        "message": f"page {page_id}: number '{value}{unit}' lacks an exact reviewed claim-to-evidence binding with matching unit and period; a source id or design basis alone is insufficient",
                    })
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
        # Walk the complete slide XML so groups and accessibility descriptions
        # receive the same checks as top-level visible text.
        for node in slide._element.iter():
            local_tag = str(node.tag).split('}')[-1]
            values = [str(node.text or '')] if local_tag == 't' else []
            values.extend(str(node.get(key) or '') for key in ('descr', 'title') if node.get(key))
            label = ' '.join(values)
            if _LOCAL_PATH.search(label):
                findings.append(
                    {'check': 'internal_path_leak', 'slide': index, 'message': f'slide {index} carries a local path in text or accessibility metadata; remove the internal reference'}
                )
            for internal in _INTERNAL_LABELS:
                if internal.strip().lower() and internal.strip().lower() in str(label).lower():
                    findings.append(
                        {"check": "internal_label_leak", "slide": index, "message": f"slide {index} shows internal label '{internal.strip()}'"}
                    )
    return findings
