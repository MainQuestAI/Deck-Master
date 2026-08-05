from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from production.page_package import strip_internal

from .contracts import ContractError, assert_valid, assert_v2, read_json, sha256_json, utc_now, write_json

PACKAGES_DIR = "page_packages"
LOCKS_DIR = Path("high_density_build/content_locks")
NBB_DIR = Path("high_density_build/nbb")
NBB_PLAN_PATH = NBB_DIR / "nbb_plan.json"
SAFE_PAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _assert_safe_page_id(page_id: str) -> None:
    raw = str(page_id or "")
    if not SAFE_PAGE_ID.fullmatch(raw) or ".." in raw:
        raise ContractError(f"page_id must be a safe run-relative identifier: {raw}")


def load_page_packages(root: Path, *, expected_run_id: str | None = None) -> list[dict[str, Any]]:
    """Load every package fail-closed; one malformed file cannot disappear."""
    directory = root / PACKAGES_DIR
    if not directory.is_dir():
        return []
    packages: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()
    for path in sorted(directory.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ContractError(f"cannot read page package: {path.name}") from exc
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid page package {path.name}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ContractError(f"page package must be an object: {path.name}")
        try:
            assert_valid("page_package", value)
        except ContractError as exc:
            raise ContractError(f"invalid page package {path.name}: {exc}") from exc
        page_id = str(value.get("page_id") or "")
        _assert_safe_page_id(page_id)
        if page_id in seen_ids:
            raise ContractError(f"duplicate page_id in page packages: {page_id}")
        order = int(value.get("order") or 0)
        if order in seen_orders:
            raise ContractError(f"duplicate page order in page packages: {order}")
        if expected_run_id and str(value.get("run_id") or "") != expected_run_id:
            raise ContractError(f"page package run_id mismatch on {page_id}: expected {expected_run_id}")
        seen_ids.add(page_id)
        seen_orders.add(order)
        packages.append(value)

    index_path = directory / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"invalid page package index: {index_path}") from exc
        index_ids = [str(item.get("page_id") or "") for item in index.get("pages", []) if isinstance(item, dict)]
        package_ids = [str(item.get("page_id") or "") for item in packages]
        if sorted(index_ids) != sorted(package_ids):
            raise ContractError("page package index is inconsistent with package files")
    return sorted(packages, key=lambda item: int(item.get("order") or 0))


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return ""


def _flatten_customer_visible(value: dict[str, Any]) -> str:
    return _text(value)


def _evidence_ledger(package: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    raw_items = list(package.get("evidence_bindings") or [])
    raw_items.extend(item for item in package.get("citations") or [] if isinstance(item, dict))
    seen: set[str] = set()
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, dict):
            evidence_id = str(item.get("evidence_id") or item.get("citation_id") or item.get("id") or f"E{index:03d}")
            record = {
                "evidence_id": evidence_id,
                "source_ref": str(item.get("source_ref") or item.get("source") or evidence_id),
                "period": str(item.get("period") or "unavailable"),
                "unit": str(item.get("unit") or "unavailable"),
                "confidence": str(item.get("confidence") or "declared"),
                "caveat": str(item.get("caveat") or ""),
                "meaning": str(item.get("meaning") or ""),
            }
        else:
            evidence_id = str(item or f"E{index:03d}")
            record = {"evidence_id": evidence_id, "source_ref": evidence_id, "period": "unavailable", "unit": "unavailable", "confidence": "declared", "caveat": "", "meaning": ""}
        if evidence_id and evidence_id not in seen:
            seen.add(evidence_id)
            evidence.append(record)
    return evidence


def _numeric_tokens(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?(?:\s?[%％]|[A-Za-z]{1,5})?", text)


def _density_analysis(customer_visible: dict[str, Any], package: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    text = _flatten_customer_visible(customer_visible)
    body_blocks = customer_visible.get("body_blocks") or []
    callouts = customer_visible.get("callouts") or []
    numeric_tokens = _numeric_tokens(text)
    table_blocks = sum(1 for block in body_blocks if isinstance(block, dict) and str(block.get("type") or "").lower() in {"table", "matrix", "comparison"})
    chart_blocks = sum(1 for block in body_blocks if isinstance(block, dict) and str(block.get("type") or "").lower() in {"chart", "kpi", "trend", "data_story"})
    score = min(100, 20 + len(body_blocks) * 8 + len(callouts) * 10 + len(numeric_tokens) * 3 + table_blocks * 12 + chart_blocks * 8)
    band = "high" if score >= 70 else "medium" if score >= 45 else "low"
    visual_spec = package.get("visual_spec") or {}
    return {
        "content_density_score": score,
        "density_band": band,
        "text_characters": len(text),
        "body_block_count": len(body_blocks),
        "callout_count": len(callouts),
        "numeric_token_count": len(numeric_tokens),
        "numeric_tokens": numeric_tokens,
        "table_block_count": table_blocks,
        "chart_block_count": chart_blocks,
        "evidence_count": len(evidence),
        "page_role": str(visual_spec.get("page_type") or visual_spec.get("role") or "dense_narrative"),
        "target_language": str(visual_spec.get("language") or package.get("audience_context", {}).get("language") or "zh-CN"),
    }


def _structure_decisions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = [
        {"decision": "preserve_locked_text", "reason": "ImageGen output is layout evidence only"},
        {"decision": "use_native_text_for_p0_p1", "reason": "editable output requirement"},
        {"decision": "reserve_so_what_region", "reason": "management implication must remain visible"},
    ]
    if analysis["table_block_count"]:
        decisions.append({"decision": "reserve_table_grid", "reason": "table-like block detected"})
    if analysis["chart_block_count"]:
        decisions.append({"decision": "reserve_chart_region", "reason": "metric or trend block detected"})
    if analysis["numeric_token_count"]:
        decisions.append({"decision": "prioritize_numeric_labels", "reason": "numeric content detected"})
    if analysis["density_band"] == "high":
        decisions.append({"decision": "use_multi_region_layout", "reason": "high density score"})
    return decisions


def _component_plan(customer_visible: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    components = [{"component_id": "component.title", "kind": "title", "priority": "P0", "region": "header"}]
    for index, block in enumerate(customer_visible.get("body_blocks") or [], start=1):
        block_type = str(block.get("type") if isinstance(block, dict) else "narrative").lower()
        kind = "table" if block_type in {"table", "matrix", "comparison"} else "chart" if block_type in {"chart", "kpi", "trend", "data_story"} else "flow" if block_type in {"process", "architecture", "timeline"} else "content_card"
        components.append({"component_id": f"component.body.{index:02d}", "kind": kind, "priority": "P1", "region": f"body.{index:02d}"})
    if customer_visible.get("callouts"):
        components.append({"component_id": "component.callouts", "kind": "callout", "priority": "P0", "region": "insight"})
    components.append({"component_id": "component.so_what", "kind": "so_what", "priority": "P0", "region": "implication"})
    if customer_visible.get("footnotes"):
        components.append({"component_id": "component.sources", "kind": "sources", "priority": "P0", "region": "footer"})
    return components


def _required_text_refs(customer_visible: dict[str, Any], *, so_what: str) -> list[dict[str, Any]]:
    refs = [{"ref": "content_lock.customer_visible.title", "priority": "P0", "required": True}]
    if customer_visible.get("subtitle"):
        refs.append({"ref": "content_lock.customer_visible.subtitle", "priority": "P1", "required": True})
    for index, block in enumerate(customer_visible.get("body_blocks") or []):
        if isinstance(block, dict) and block.get("title"):
            refs.append({"ref": f"content_lock.customer_visible.body_blocks.{index}.title", "priority": "P1", "required": True})
        refs.append({"ref": f"content_lock.customer_visible.body_blocks.{index}", "priority": "P1", "required": True})
    if customer_visible.get("labels"):
        refs.append({"ref": "content_lock.customer_visible.labels", "priority": "P2", "required": True})
    if customer_visible.get("footnotes"):
        refs.append({"ref": "content_lock.customer_visible.footnotes", "priority": "P0", "required": True})
    refs.append({"ref": "content_lock.enrichment.so_what", "priority": "P0", "required": True, "structural": True, "value": so_what})
    return refs


def _derived_claims(package: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_ids = [item["evidence_id"] for item in evidence]
    return [{"claim_id": str(claim_id), "origin": "source", "evidence_refs": evidence_ids, "factual_value_added": False} for claim_id in package.get("claim_bindings") or []]


def build_nbb_page(package: dict[str, Any]) -> dict[str, Any]:
    page_id = str(package.get("page_id") or "")
    run_id = str(package.get("run_id") or "")
    if not page_id or not run_id:
        raise ContractError("page package requires run_id and page_id")
    _assert_safe_page_id(page_id)
    if package.get("status") != "ready_for_build":
        raise ContractError(f"page package {page_id} is not buildable: {package.get('status')}")
    safe_package = strip_internal(package)
    customer_visible = copy.deepcopy(safe_package.get("customer_visible") or {})
    evidence = _evidence_ledger(safe_package)
    analysis = _density_analysis(customer_visible, safe_package, evidence)
    # A preview adapter can only appear in fixture/migration mode.  Preserve
    # that narrow compatibility path while keeping normal v2 production pages
    # fail-closed on evidence and density.
    if analysis["numeric_tokens"] and not evidence and not package.get("legacy_inferred"):
        raise ContractError(f"NBB page {page_id} contains unsupported factual values: {analysis['numeric_tokens']}")
    if (analysis["density_band"] == "low" or not evidence) and not package.get("legacy_inferred"):
        raise ContractError(f"NBB page {page_id} is too sparse for high-density output; add evidence and at least three content regions")
    components = _component_plan(customer_visible, analysis)
    if not components:
        raise ContractError(f"NBB page {page_id} has no required components")
    conclusion = str((safe_package.get("quality_intent") or {}).get("conclusion") or customer_visible.get("title") or "")
    arguments = [str(_text(block)) for block in customer_visible.get("body_blocks") or [] if _text(block)]
    caveats = [item["caveat"] for item in evidence if item.get("caveat")]
    so_what = str((safe_package.get("quality_intent") or {}).get("so_what") or (arguments[-1] if arguments else conclusion))
    coverage = {
        "facts": 1.0 if evidence or package.get("legacy_inferred") else 0.0,
        "numeric_values": 1.0 if evidence or not analysis["numeric_tokens"] else 0.0,
        "derived_claims": 1.0 if all(item.get("evidence_refs") for item in _derived_claims(safe_package, evidence)) else 0.0,
    }
    if min(coverage.values()) < 1.0:
        raise ContractError(f"NBB evidence coverage failed on page {page_id}: {coverage}")
    enrichment = {
        "framework": "nbb",
        "version": "cyber-ppt-nbb.v2",
        "analysis": analysis,
        "evidence_ledger": evidence,
        "conclusion": conclusion,
        "supporting_arguments": arguments,
        "caveat": caveats,
        "so_what": so_what,
        "material_pool": {"facts": copy.deepcopy(customer_visible), "evidence_ids": [item["evidence_id"] for item in evidence], "numeric_values": analysis["numeric_tokens"]},
        "derived_claims": _derived_claims(safe_package, evidence),
        "structure_decisions": _structure_decisions(analysis),
        "component_plan": components,
        "evidence_coverage": coverage,
    }
    return {"customer_visible": customer_visible, "evidence": evidence, "analysis": analysis, "enrichment": enrichment, "components": components, "required_text_refs": _required_text_refs(customer_visible, so_what=so_what), "so_what": so_what}


def build_content_lock(package: dict[str, Any], *, nbb_plan_sha256: str = "") -> dict[str, Any]:
    page_id = str(package.get("page_id") or "")
    run_id = str(package.get("run_id") or "")
    result = build_nbb_page(package)
    safe_package = strip_internal(package)
    lock = {
        "schema_version": "deck_content_lock.v2",
        "run_id": run_id,
        "page_id": page_id,
        "page_package_ref": f"{PACKAGES_DIR}/{page_id}.json",
        "page_package_sha256": sha256_json(package),
        "source_fingerprint": str(package.get("source_fingerprint") or sha256_json(result["customer_visible"])),
        "customer_visible": result["customer_visible"],
        "speaker_notes": str(package.get("speaker_notes") or ""),
        "asset_bindings": copy.deepcopy(safe_package.get("asset_bindings") or []),
        "evidence_bindings": result["evidence"],
        "enrichment": result["enrichment"],
        "required_component_ids": [item["component_id"] for item in result["components"]],
        "required_text_refs": result["required_text_refs"],
        "density_target": {
            "score": result["analysis"]["content_density_score"],
            "band": result["analysis"]["density_band"],
            "information_regions": max(3, len(result["components"])),
            "component_count": len(result["components"]),
            "evidence_count": len(result["evidence"]),
            "numeric_count": result["analysis"]["numeric_token_count"],
        },
        "target_language": result["analysis"]["target_language"],
        "effective_language": result["analysis"]["target_language"],
        "lineage": {"page_package_sha256": sha256_json(package), "nbb_plan_sha256": nbb_plan_sha256 or "0" * 64},
        "created_at": utc_now(),
    }
    source_fp = str(lock["source_fingerprint"])
    if len(source_fp) != 64:
        lock["source_fingerprint"] = sha256_json({"page_id": page_id, "source": source_fp})
    lock["content_lock_sha256"] = sha256_json({key: value for key, value in lock.items() if key not in {"content_lock_sha256", "created_at", "updated_at"}})
    assert_v2("content_lock", lock)
    return lock


def build_nbb_plan(packages: list[dict[str, Any]], *, run_id: str) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for package in packages:
        page_id = str(package.get("page_id") or "")
        try:
            result = build_nbb_page(package)
        except ContractError as exc:
            blocked.append({"page_id": page_id, "reason": str(exc)})
            continue
        ledger.extend(result["evidence"])
        pages.append({"page_id": page_id, "order": int(package.get("order") or 0), "role": result["analysis"]["page_role"], "conclusion": result["enrichment"]["conclusion"], "supporting_arguments": result["enrichment"]["supporting_arguments"], "caveat": result["enrichment"]["caveat"], "so_what": result["so_what"], "components": result["components"], "density": result["analysis"], "status": "ready"})
    if blocked:
        raise ContractError(f"NBB plan blocked pages: {blocked}")
    # Stable deduplication keeps the plan hash reproducible across runs.
    unique_ledger = {str(item["evidence_id"]): item for item in ledger}
    plan = {
        "schema_version": "deck_nbb_plan.v1",
        "run_id": run_id,
        "page_count": len(pages),
        "evidence_ledger": [unique_ledger[key] for key in sorted(unique_ledger)],
        "storyline_audit": {"source": "page_packages", "status": "completed", "notes": "NBB preserves source facts and adds explicit argument, caveat and implication structure."},
        "scr": {"situation": "Page Package context", "complication": "visual and content density must coexist", "resolution": "content lock -> blueprint -> native SVG -> editable PPTX"},
        "pages": sorted(pages, key=lambda item: item["order"]),
        "blocked_pages": [],
        "created_at": utc_now(),
    }
    plan["nbb_plan_sha256"] = sha256_json({key: value for key, value in plan.items() if key not in {"nbb_plan_sha256", "created_at", "updated_at"}})
    assert_v2("nbb_plan", plan)
    return plan


def write_nbb_plan(root: Path, plan: dict[str, Any]) -> Path:
    assert_v2("nbb_plan", plan)
    path = root / NBB_PLAN_PATH
    return write_json(path, plan)


def write_content_lock(root: Path, package: dict[str, Any], *, nbb_plan_sha256: str = "") -> Path:
    lock = build_content_lock(package, nbb_plan_sha256=nbb_plan_sha256)
    canonical = root / LOCKS_DIR / f"{package['page_id']}.content_lock.json"
    write_json(canonical, lock)
    # Keep the old filename as a compatibility mirror for existing run tools.
    write_json(root / LOCKS_DIR / f"{package['page_id']}.json", lock)
    return canonical


def load_content_lock(root: Path, page_id: str, *, expected_run_id: str | None = None) -> dict[str, Any]:
    _assert_safe_page_id(page_id)
    canonical = root / LOCKS_DIR / f"{page_id}.content_lock.json"
    legacy = root / LOCKS_DIR / f"{page_id}.json"
    selected = canonical if canonical.exists() else legacy
    lock = read_json(selected)
    if canonical.exists() and legacy.exists() and read_json(legacy) != lock:
        raise ContractError(f"content lock mirror is stale on page {page_id}")
    assert_v2("content_lock", lock)
    if str(lock.get("page_id") or "") != page_id:
        raise ContractError(f"content lock page_id mismatch: {page_id}")
    if expected_run_id and str(lock.get("run_id") or "") != expected_run_id:
        raise ContractError(f"content lock run_id mismatch on page {page_id}: expected {expected_run_id}")
    expected = sha256_json({key: value for key, value in lock.items() if key not in {"content_lock_sha256", "created_at", "updated_at"}})
    if lock.get("content_lock_sha256") != expected:
        raise ContractError(f"content lock hash is stale on page {page_id}")
    return lock


__all__ = [
    "LOCKS_DIR",
    "NBB_DIR",
    "NBB_PLAN_PATH",
    "build_content_lock",
    "build_nbb_page",
    "build_nbb_plan",
    "load_content_lock",
    "load_page_packages",
    "write_content_lock",
    "write_nbb_plan",
]
