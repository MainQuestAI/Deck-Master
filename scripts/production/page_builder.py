"""SC-1 B5: production Page Package writer.

Turns an approved narrative (beats with page_job/conclusion) into complete,
concrete page packages — the single page-content input for both standard and
high-density builds (spec 02 §2.3). Guards from spec 06:

- production instructions ("请补充…", "此处绘制…", TODO) must never appear in
  customer-visible body text;
- a page with neither resolvable evidence references nor a design basis is
  recorded as ``evidence_state=insufficient`` and stays out of ``ready``;
- every narrative beat must produce exactly one package (no missing pages);
- sourcing strategy per page comes from the sourcing plan (none → generate).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from production.page_package import PageContent, PagePackageError, PagePackageIndex, build_page_package
except ModuleNotFoundError:  # pragma: no cover - exercised by package-import test path.
    from scripts.production.page_package import PageContent, PagePackageError, PagePackageIndex, build_page_package

PRODUCTION_INSTRUCTION_MARKERS = (
    "请补充",
    "此处绘制",
    "待补充",
    "待填写",
    "占位",
    "TODO",
    "TBD",
    "[插入",
    "【插入",
)
_PLACEHOLDER_PATTERN = re.compile("|".join(re.escape(marker) for marker in PRODUCTION_INSTRUCTION_MARKERS), re.IGNORECASE)
SOURCING_DECISION_STRATEGY = {
    "generate": "generate",
    "reuse": "reuse",
    "adapt": "adapt",
    "manual_placeholder": "manual",
    "evidence_pending": "manual",
    "blocked": "blocked",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_no_production_instructions(text: str, *, page_id: str) -> None:
    match = _PLACEHOLDER_PATTERN.search(str(text or ""))
    if match:
        raise PagePackageError(
            f"page {page_id}: customer-visible text contains a production instruction ({match.group(0)!r}); "
            "finish the content instead of shipping the instruction"
        )


def _sourcing_for_page(sourcing_plan: dict[str, Any] | None, beat_id: str) -> dict[str, Any]:
    for page in (sourcing_plan or {}).get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        if str(page.get("page_id") or "") == beat_id or str(page.get("page_task_id") or "") == beat_id:
            decision = str(page.get("decision") or "")
            return {
                "strategy": SOURCING_DECISION_STRATEGY.get(decision, decision or "generate"),
                "decision": decision,
                "reason": str(page.get("reason") or ""),
                "selected_source_count": len(page.get("selected_sources") or []),
            }
    return {"strategy": "generate", "decision": "", "reason": "", "selected_source_count": 0}


def _page_evidence(beat, context, *, run_dir=None):
    from quality.source_binding import evidence_index, source_quote_matches
    source_ids = {str(s.get("source_id")) for s in (context or {}).get("sources", [])}
    refs = list(beat.get("evidence_refs") or [])
    source_refs = [str(ref) for ref in (beat.get("source_refs") or refs) if str(ref) in source_ids]
    index = evidence_index(context)
    bound = []
    for ref in (beat.get("evidence_bindings") or refs):
        candidates = index.get(str(ref), [])
        if len(candidates) == 1 and source_quote_matches(*candidates[0], run_dir=run_dir):
            source, evidence = candidates[0]
            bound.append(str(source["source_id"]) + "::" + str(evidence["evidence_id"]))
    return source_refs, list(dict.fromkeys(bound))


def build_packages_from_narrative(
    *,
    run_id: str,
    narrative_plan: dict[str, Any],
    context_manifest: dict[str, Any] | None = None,
    solution_model: dict[str, Any] | None = None,
    sourcing_plan: dict[str, Any] | None = None,
    now: datetime | None = None,
    source_run_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Create one complete page package per narrative beat. No silent gaps."""

    beats = [beat for beat in narrative_plan.get("beats", []) if isinstance(beat, dict)]
    if not beats:
        raise PagePackageError("narrative plan has no beats; refusing to create an empty page package set")

    valid_source_ids = {
        str(source.get("source_id") or "").strip()
        for source in (context_manifest or {}).get("sources", [])
        if isinstance(source, dict) and str(source.get("source_id") or "").strip()
    }
    capability_titles = {
        str(item.get("capability_id") or ""): str(item.get("title") or "")
        for item in (solution_model or {}).get("capabilities", [])
        if isinstance(item, dict)
    }
    # Design basis: a page that realizes a model capability through one of the
    # capability's own components.
    component_to_capability: dict[str, str] = {}
    for capability in (solution_model or {}).get("capabilities", []):
        if not isinstance(capability, dict):
            continue
        cid = str(capability.get("capability_id") or "")
        for component_ref in capability.get("component_ids") or []:
            component_to_capability[str(component_ref)] = cid

    packages: list[dict[str, Any]] = []
    for order, beat in enumerate(beats, start=1):
        beat_id = str(beat.get("beat_id") or f"beat_{order:02d}")
        page_id = str(beat.get("page_id") or beat_id)
        title = str(beat.get("page_title") or beat.get("title") or page_id)
        conclusion = str(beat.get("conclusion") or "").strip()
        page_job = str(beat.get("page_job") or beat.get("content_goal") or "").strip()
        if not conclusion:
            raise PagePackageError(f"page {page_id}: narrative beat has no conclusion; a page without a conclusion is not producible")
        assert_no_production_instructions(conclusion, page_id=page_id)
        assert_no_production_instructions(page_job, page_id=page_id)

        claim_bindings = [str(ref) for ref in (beat.get("claim_refs") or beat.get("claim_ids") or []) if str(ref).strip()]
        required_components = [str(ref) for ref in (beat.get("required_components") or []) if str(ref).strip()]
        design_basis = ""
        for component in required_components:
            capability_ref = component_to_capability.get(component)
            if capability_ref:
                design_basis = f"solution_model#capability:{capability_ref}"
                break
        if not design_basis and solution_model:
            design_basis = "solution_model" if beat.get("role") in {"architecture", "solution"} else ""

        body_blocks: list[dict[str, Any]] = [{"type": "conclusion", "text": conclusion}]
        implication = str(beat.get("business_implication") or "").strip()
        if implication:
            body_blocks.append({"type": "business_implication", "text": implication})
        if page_job and page_job != conclusion:
            # The page job is the producer's task description, kept internal.
            pass

        source_refs, evidence_bindings = _page_evidence(beat, context_manifest, run_dir=source_run_dir)
        fact_kind = str(beat.get("fact_kind") or "unclassified")
        if evidence_bindings:
            evidence_state = "referenced"
        elif fact_kind == "customer_fact":
            evidence_state = "insufficient"
        elif design_basis or source_refs:
            evidence_state = "design_basis"
        else:
            evidence_state = "insufficient"
        sourcing = _sourcing_for_page(sourcing_plan, page_id)
        internal_only = {
            "page_job": page_job,
            "evidence_state": evidence_state,
            "design_basis_ref": design_basis,
            "sourcing": sourcing,
            "transition": str(beat.get("transition") or ""),
        }
        # SC-1.1 F-N08: write the schema status value, not a "ready" literal.
        status = "draft" if evidence_state == "insufficient" else "ready_for_build"

        content = PageContent(
            page_id=page_id,
            order=int(beat.get("order") or order),
            title=title,
            body_blocks=body_blocks,
            subtitle=str(beat.get("subtitle") or ""),
            labels=[str(item) for item in (beat.get("labels") or [])],
            callouts=[
                {"type": "required_component", "ref": ref, "title": capability_titles.get(ref, ref)}
                for ref in required_components
            ],
            claim_bindings=claim_bindings,
            evidence_bindings=evidence_bindings,
            visual_spec={
                "page_role": str(beat.get("role") or ""),
                "expected_visual": str(beat.get("expected_visual") or "文字+结构化图形"),
                "view_refs": [str(ref) for ref in (beat.get("view_refs") or [])],
                "content_budget": str(beat.get("content_budget") or "standard"),
            },
        )
        package = build_page_package(
            run_id=run_id,
            content=content,
            internal_only=internal_only,
            status=status,
            beat_id=beat_id,
            now=now,
            provenance={
                "writer": "page_builder.build_packages_from_narrative",
                "source_refs": source_refs,
                "fact_kind": fact_kind,
                "narrative_beat_id": beat_id,
                "sourcing_strategy": sourcing["strategy"],
                "recorded_at": _utc_now(),
            },
        )
        packages.append(package)
    return packages


def write_page_packages(
    run_dir: str | Path,
    *,
    narrative_plan: dict[str, Any],
    context_manifest: dict[str, Any] | None = None,
    solution_model: dict[str, Any] | None = None,
    sourcing_plan: dict[str, Any] | None = None,
    now: datetime | None = None,
    source_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Write the full page package set + index; report coverage honestly."""

    root = Path(run_dir).expanduser().resolve()
    run_id = str(narrative_plan.get("run_id") or root.name)
    packages = build_packages_from_narrative(
        run_id=run_id,
        narrative_plan=narrative_plan,
        context_manifest=context_manifest,
        solution_model=solution_model,
        sourcing_plan=sourcing_plan,
        now=now,
        source_run_dir=source_run_dir or root,
    )
    index = PagePackageIndex(root)
    for package in packages:
        index.write(package)
    required_page_ids = [str(package["page_id"]) for package in packages]
    coverage = index.coverage(required_page_ids)
    report = {
        "run_id": run_id,
        "page_count": len(packages),
        "coverage": coverage,
        "insufficient_pages": [
            str(package["page_id"]) for package in packages if (package.get("internal_only") or {}).get("evidence_state") == "insufficient"
        ],
        "sourcing_strategies": {
            str(package["page_id"]): (package.get("internal_only") or {}).get("sourcing", {}).get("strategy", "")
            for package in packages
        },
    }
    return report
