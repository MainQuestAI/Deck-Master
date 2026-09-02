from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from production.page_package import strip_internal
from page_roles import STRUCTURAL_PAGE_ROLES, canonical_page_role

from .contracts import ContractError, assert_valid, assert_v2, read_json, sha256_file, sha256_json, utc_now, write_json
from .integrity import sign_runtime_payload, verify_runtime_payload, verify_user_attestation, sign_user_attestation
from .migration import assert_current_mbb_artifact
from .visibility import build_visibility_policy, validate_visibility_policy

PACKAGES_DIR = "page_packages"
LOCKS_DIR = Path("high_density_build/content_locks")
MBB_DIR = Path("high_density_build/mbb")
MBB_PLAN_PATH = MBB_DIR / "mbb_plan.json"
MBB_SELECTION_RECEIPT_PATH = MBB_DIR / "selection_receipt.json"
MBB_USER_DECISION_RECEIPT_PATH = MBB_DIR / "user_decision_receipt.json"
MBB_SEAL_PATH = MBB_DIR / "runtime_seal.json"
SAFE_PAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
STRUCTURAL_VISUAL_HINT_TERMS = (
    "acceptance",
    "agenda",
    "chapter",
    "contents",
    "cover",
    "divider",
    "framework",
    "introduction",
    "intro",
    "layout",
    "opening",
    "overview",
    "roadmap",
    "section",
    "structure",
    "table of contents",
    "toc",
    "验收",
    "议程",
    "章节",
    "目录",
    "封面",
    "分隔",
    "框架",
    "导言",
    "介绍",
    "布局",
    "开场",
    "概览",
    "路线图",
    "结构",
)
STRUCTURAL_FACTUAL_ASSERTION_TERMS = (
    "achieved",
    "adoption",
    "advantage",
    "best",
    "customer",
    "decrease",
    "delivered",
    "dominant",
    "fastest",
    "first",
    "growth",
    "highest",
    "improve",
    "increase",
    "leader",
    "leadership",
    "lowest",
    "market",
    "only",
    "performance",
    "profit",
    "proven",
    "ready",
    "revenue",
    "result",
    "share",
    "supports",
    "users",
    "value",
    "领先",
    "份额",
    "增长",
    "提升",
    "降低",
    "最高",
    "最低",
    "唯一",
    "显著",
    "实现",
    "达到",
    "证明",
    "客户",
    "收入",
    "利润",
    "效率",
    "优势",
    "规模",
    "占比",
)


def _assert_safe_page_id(page_id: str) -> None:
    raw = str(page_id or "")
    if not SAFE_PAGE_ID.fullmatch(raw) or ".." in raw:
        raise ContractError(f"page_id must be a safe run-relative identifier: {raw}")


def _run_mode(root: Path) -> str:
    request = read_json(root / "request.json")
    mode = str(request.get("run_mode") or "production").strip().lower()
    return mode if mode in {"production", "benchmark", "fixture", "dev"} else "production"


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
        if not isinstance(index, dict):
            raise ContractError(f"page package index must be an object: {index_path}")
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
    source_context = str((package.get("customer_visible") or {}).get("title") or package.get("page_id") or "page")
    raw_items = list(package.get("evidence_bindings") or [])
    raw_items.extend(item for item in package.get("citations") or [] if isinstance(item, dict))
    seen: set[str] = set()
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, dict):
            evidence_id = str(item.get("evidence_id") or item.get("citation_id") or item.get("id") or f"E{index:03d}")
            record = {
                "evidence_id": evidence_id,
                "source_ref": str(item.get("source_ref") or item.get("source") or evidence_id),
                "source_position": str(item.get("source_position") or item.get("position") or "unavailable"),
                "period": str(item.get("period") or "unavailable"),
                "unit": str(item.get("unit") or "unavailable"),
                "confidence": str(item.get("confidence") or "declared"),
                "conflicts": [str(value) for value in item.get("conflicts") or []],
                "caveat": str(item.get("caveat") or ""),
                "source_context": source_context,
                "meaning": str(item.get("meaning") or ""),
                "implication": str(item.get("implication") or ""),
                "recommended_visual": str(item.get("recommended_visual") or ""),
            }
        else:
            evidence_id = str(item or f"E{index:03d}")
            # Legacy Page Packages may carry only an evidence ID. Preserve the
            # package as the evidence payload so an Agent claim can still point
            # to an exact, inspectable source span instead of an ID-only stub.
            package_text = _flatten_customer_visible(package.get("customer_visible") or {})
            record = {
                "evidence_id": evidence_id,
                "source_ref": evidence_id,
                "source_position": "unavailable",
                "period": "unavailable",
                "unit": "unavailable",
                "confidence": "declared",
                "conflicts": [],
                "caveat": "",
                "source_context": source_context,
                "meaning": package_text or evidence_id,
                "implication": str((package.get("quality_intent") or {}).get("so_what") or ""),
                "recommended_visual": "",
            }
        if not evidence_id:
            raise ContractError(f"Page Package {package.get('page_id') or 'unknown'} contains an empty evidence_id")
        if evidence_id in seen:
            raise ContractError(f"Page Package {package.get('page_id') or 'unknown'} contains duplicate evidence_id: {evidence_id}")
        seen.add(evidence_id)
        evidence.append(record)
    if not evidence and package.get("legacy_inferred"):
        page_id = str(package.get("page_id") or "page")
        evidence.append(
            {
                "evidence_id": f"LEGACY-{page_id}",
                "source_ref": "legacy_preview_manifest",
                "source_position": "preview_manifest.json",
                "period": "unavailable",
                "unit": "unavailable",
                "confidence": "migration_only",
                "conflicts": [],
                "caveat": "Legacy preview content requires evidence enrichment before production circulation.",
                "source_context": str((package.get("customer_visible") or {}).get("title") or page_id),
                "meaning": "Migration adapter evidence placeholder.",
                "implication": "Keep this page in fixture or migration mode until source evidence is attached.",
                "recommended_visual": "dense_narrative",
            }
        )
    return evidence


def _numeric_tokens(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?(?:\s?[%％]|[A-Za-z]{1,5})?", text)


def _unsupported_structural_numeric_tokens(
    customer_visible: dict[str, Any],
    tokens: list[str],
    *,
    evidence: list[dict[str, Any]] | None = None,
) -> list[str]:
    text = _flatten_customer_visible(customer_visible)
    evidence_numbers = {
        normalized
        for record in evidence or []
        if isinstance(record, dict)
        for normalized in _normalized_numeric_tokens(_evidence_text(record))
    }
    date_spans = [
        match.span()
        for match in re.finditer(
            r"(?:19|20)\d{2}\s*[-/.年]\s*\d{1,2}(?:\s*[-/.月]\s*\d{1,2})?",
            text,
        )
    ]
    unsupported: list[str] = []
    for token in tokens:
        normalized = re.sub(r"\s+", "", token)
        if re.fullmatch(r"(?:19|20)\d{2}", normalized):
            continue
        occurrences = list(re.finditer(re.escape(token), text, flags=re.IGNORECASE))
        if any(any(start <= match.start() and match.end() <= end for start, end in date_spans) for match in occurrences):
            continue
        page_pattern = r"(?:第\s*|page\s*|页码\s*|页\s*)" + re.escape(token)
        if any(re.search(page_pattern, text[max(0, match.start() - 8) : match.end() + 8], flags=re.IGNORECASE) for match in occurrences):
            continue
        if normalized.replace("％", "%").replace(",", "").casefold() in evidence_numbers:
            continue
        unsupported.append(token)
    return unsupported


def _normalized_numeric_tokens(text: str) -> set[str]:
    return {
        re.sub(r"\s+", "", token).replace("％", "%").replace(",", "").casefold()
        for token in _numeric_tokens(text)
    }


def _evidence_text(record: dict[str, Any]) -> str:
    return " ".join(
        value
        for value in (
            record.get("source_context"),
            record.get("meaning"),
            record.get("implication"),
            record.get("caveat"),
            record.get("source_ref"),
            record.get("source_position"),
            record.get("period"),
            record.get("unit"),
            record.get("recommended_visual"),
            " ".join(str(item) for item in record.get("conflicts") or []),
        )
        if str(value or "").strip()
    )


def _evidence_body_text(record: dict[str, Any]) -> str:
    return " ".join(
        value
        for value in (
            record.get("meaning"),
            record.get("implication"),
            record.get("caveat"),
            record.get("source_ref"),
            record.get("source_position"),
            record.get("period"),
            record.get("unit"),
            record.get("recommended_visual"),
            " ".join(str(item) for item in record.get("conflicts") or []),
        )
        if str(value or "").strip()
    )


def _grounding_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[0-9]+|[\u4e00-\u9fff]+", text.casefold()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", word):
            tokens.update(word[index : index + 2] for index in range(max(0, len(word) - 1)))
        elif word not in {"the", "and", "for", "with", "from", "that", "this", "into", "while", "only", "must", "should"}:
            tokens.add(word)
    return tokens


def _claim_requires_evidence_overlap(target: str) -> bool:
    return (
        target in {"management_conclusion", "situation", "complication", "resolution", "conclusion", "detailed_argument"}
        or target.startswith("issue_hypothesis_tree.branches.") and target.endswith(".hypothesis")
        or target.startswith("supporting_arguments.")
    )


def _evidence_spans(
    evidence_refs: list[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    spans: list[dict[str, str]] = []
    for evidence_ref in evidence_refs:
        evidence_text = _evidence_text(evidence_by_id.get(str(evidence_ref), {})).strip()
        if not evidence_text:
            continue
        quote = evidence_text[:240]
        spans.append(
            {
                "evidence_ref": str(evidence_ref),
                "quote": quote,
                "quote_sha256": sha256_json(quote),
            }
        )
    return spans


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
    page_role = canonical_page_role(
        package.get("page_role")
        or visual_spec.get("page_role")
        or visual_spec.get("page_type")
        or visual_spec.get("role"),
        default="dense_narrative",
    )
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
        "page_role": page_role,
        "structural_page": page_role in STRUCTURAL_PAGE_ROLES,
        "target_language": str(visual_spec.get("language") or package.get("audience_context", {}).get("language") or "zh-CN"),
    }


def _structure_decisions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = [
        {"decision": "preserve_locked_text", "reason": "ImageGen output is layout evidence only"},
        {"decision": "use_native_text_for_p0_p1", "reason": "editable output requirement"},
    ]
    if not analysis.get("structural_page"):
        decisions.append({"decision": "reserve_so_what_region", "reason": "management implication must remain visible"})
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
    if not analysis.get("structural_page"):
        components.append({"component_id": "component.business_implication", "kind": "business_implication", "priority": "P0", "region": "implication"})
    return components


def _required_text_refs(customer_visible: dict[str, Any], *, so_what: str) -> list[dict[str, Any]]:
    refs = [{"ref": "content_lock.customer_visible.title", "priority": "P0", "required": True}]
    if customer_visible.get("subtitle"):
        refs.append({"ref": "content_lock.customer_visible.subtitle", "priority": "P1", "required": True})
    for index, block in enumerate(customer_visible.get("body_blocks") or []):
        if isinstance(block, dict) and block.get("title"):
            refs.append({"ref": f"content_lock.customer_visible.body_blocks.{index}.title", "priority": "P1", "required": True})
        refs.append({"ref": f"content_lock.customer_visible.body_blocks.{index}", "priority": "P1", "required": True})
    if customer_visible.get("callouts"):
        refs.append({"ref": "content_lock.customer_visible.callouts", "priority": "P0", "required": True})
    if so_what:
        refs.append({"ref": "content_lock.enrichment.business_implication", "priority": "P0", "required": True, "structural": True, "value": so_what})
    return refs


def _is_non_factual_structural_text(value: Any) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "").casefold()).strip()
    if not normalized:
        return True
    if any(term in normalized for term in STRUCTURAL_FACTUAL_ASSERTION_TERMS):
        return False
    return any(term in normalized for term in STRUCTURAL_VISUAL_HINT_TERMS)


def _structural_factual_entries(customer_visible: dict[str, Any]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    subtitle = str(customer_visible.get("subtitle") or "").strip()
    if subtitle and not _is_non_factual_structural_text(subtitle):
        entries.append(("material_pool.customer_visible.subtitle", subtitle))
    for collection in ("body_blocks", "callouts"):
        for index, item in enumerate(customer_visible.get(collection) or []):
            prefix = f"material_pool.customer_visible.{collection}.{index}"
            if isinstance(item, dict):
                for field in ("text", "body", "description", "value"):
                    text = _text(item.get(field)).strip()
                    if text:
                        entries.append((f"{prefix}.{field}", text))
            else:
                text = _text(item).strip()
                if text:
                    entries.append((prefix, text))
    for index, item in enumerate(customer_visible.get("footnotes") or []):
        text = _text(item).strip()
        if text:
            entries.append((f"material_pool.customer_visible.footnotes.{index}", text))
    return entries


def _structural_factual_texts(customer_visible: dict[str, Any]) -> list[str]:
    return [text for _target, text in _structural_factual_entries(customer_visible)]


def _resolve_target(payload: dict[str, Any], target: str) -> Any:
    value: Any = payload
    for part in target.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ContractError(f"MBB claim binding target cannot be resolved: {target}")
    return value


def _candidate_claim_targets(candidate: dict[str, Any]) -> list[str]:
    targets = [
        "management_conclusion",
        "audience",
        "issue_hypothesis_tree.root",
        "caveat",
        "visual_potential",
        "not_recommended_because",
        "page_handoff",
        "evidence_assessment.synthesis",
        "chart_plan.visual_type",
        "chart_plan.comparison_axis",
    ]
    for index, _branch in enumerate((candidate.get("issue_hypothesis_tree") or {}).get("branches") or []):
        targets.extend(
            [
                f"issue_hypothesis_tree.branches.{index}.question",
                f"issue_hypothesis_tree.branches.{index}.hypothesis",
            ]
        )
    return targets


def _scr_claim_targets(_scr: dict[str, Any]) -> list[str]:
    return ["situation", "complication", "resolution", "decision_implication", "evidence_assessment.synthesis"]


def _page_claim_targets(page: dict[str, Any]) -> list[str]:
    if bool((page.get("role") or "") in STRUCTURAL_PAGE_ROLES):
        targets = [
            "role",
            "chart_plan.visual_type",
            "storyline_context.visual_potential",
            "material_pool.recommended_visual",
            "material_pool.storyline_visual_potential",
        ]
        targets.extend(target for target, _text_value in _structural_factual_entries((page.get("material_pool") or {}).get("customer_visible") or {}))
        targets.extend(f"components.{index}.{field}" for index, component in enumerate(page.get("components") or []) if isinstance(component, dict) for field in component)
        targets.extend(f"required_text_refs.{index}.{field}" for index, item in enumerate(page.get("required_text_refs") or []) if isinstance(item, dict) for field in item if field != "value")
        return targets
    targets = [
        "role",
        "conclusion",
        "so_what",
        "handoff",
        "detailed_argument",
        "business_implication",
        "chart_plan.visual_type",
        "chart_plan.comparison_axis",
        "storyline_context.management_conclusion",
        "storyline_context.visual_potential",
        "storyline_context.page_handoff",
        "storyline_context.caveat",
        "material_pool.recommended_visual",
        "material_pool.storyline_visual_potential",
        "material_pool.storyline_page_handoff",
        "material_pool.storyline_caveat",
    ]
    targets.extend(f"supporting_arguments.{index}" for index, _value in enumerate(page.get("supporting_arguments") or []))
    targets.extend(f"caveat.{index}" for index, _value in enumerate(page.get("caveat") or []))
    targets.extend(f"material_pool.numeric_values.{index}" for index, _value in enumerate((page.get("material_pool") or {}).get("numeric_values") or []))
    targets.extend(f"material_pool.comparisons.{index}" for index, _value in enumerate((page.get("material_pool") or {}).get("comparisons") or []))
    targets.extend(f"material_pool.changes.{index}" for index, _value in enumerate((page.get("material_pool") or {}).get("changes") or []))
    targets.extend(f"material_pool.annotations.{index}" for index, _value in enumerate((page.get("material_pool") or {}).get("annotations") or []))
    for index, component in enumerate(page.get("components") or []):
        if isinstance(component, dict):
            targets.extend(f"components.{index}.{field}" for field in component)
    for index, item in enumerate(page.get("required_text_refs") or []):
        if isinstance(item, dict):
            targets.extend(f"required_text_refs.{index}.{field}" for field in item)
    return targets


def _page_structural_claim_targets(page: dict[str, Any]) -> set[str]:
    # Structural exemptions are limited to visual/layout metadata. A page role
    # does not make its conclusions, implications, caveats, or numbers
    # evidence-free.
    targets: set[str] = {
        "role",
        "chart_plan.visual_type",
        "storyline_context.visual_potential",
        "material_pool.recommended_visual",
        "material_pool.storyline_visual_potential",
    }
    for index, component in enumerate(page.get("components") or []):
        if isinstance(component, dict):
            targets.update(f"components.{index}.{field}" for field in component)
    for index, item in enumerate(page.get("required_text_refs") or []):
        if isinstance(item, dict):
            targets.update(f"required_text_refs.{index}.{field}" for field in item if field != "value")
    return targets


def _claim_bindings(
    payload: dict[str, Any],
    targets: list[str],
    evidence_refs: list[str],
    *,
    source_text: str,
    structural_targets: set[str] | None = None,
    evidence_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    structural = structural_targets or set()
    for target in targets:
        text = str(_resolve_target(payload, target) or "")
        origin = "structural_label" if target in structural else "source" if text and text in source_text else "derived"
        spans = [] if origin == "structural_label" else _evidence_spans(evidence_refs, evidence_by_id or {})
        bindings.append(
            {
                "target": target,
                "text_sha256": sha256_json(text),
                "origin": origin,
                "evidence_refs": [] if origin == "structural_label" else list(evidence_refs),
                "evidence_spans": spans,
                "derivation_note": (
                    "Runtime-owned structural registry value."
                    if origin == "structural_label"
                    else "Exact Page Package projection."
                    if origin == "source"
                    else "Editorial synthesis grounded only in the referenced Page Package evidence."
                ),
            }
        )
    return bindings


def _validate_claim_bindings(
    payload: dict[str, Any],
    *,
    required_targets: list[str],
    allowed_evidence_refs: set[str],
    evidence_by_id: dict[str, dict[str, Any]],
        source_text: str,
        context: str,
        structural_targets: set[str] | None = None,
) -> None:
    bindings = payload.get("claim_bindings")
    if not isinstance(bindings, list):
        raise ContractError(f"MBB claim bindings are required for {context}")
    by_target: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ContractError(f"MBB claim binding must be an object for {context}")
        target = str(binding.get("target") or "")
        if not target or target in by_target:
            raise ContractError(f"MBB claim binding target is missing or duplicated for {context}: {target}")
        by_target[target] = binding
    if set(by_target) != set(required_targets):
        missing = sorted(set(required_targets) - set(by_target))
        extra = sorted(set(by_target) - set(required_targets))
        raise ContractError(f"MBB claim binding coverage failed for {context}: missing={missing}, extra={extra}")
    for target in required_targets:
        binding = by_target[target]
        text = str(_resolve_target(payload, target) or "")
        if not text or str(binding.get("text_sha256") or "") != sha256_json(text):
            raise ContractError(f"MBB claim binding text hash is stale for {context}:{target}")
        refs = {str(ref) for ref in binding.get("evidence_refs") or []}
        origin = str(binding.get("origin") or "")
        expected_origin = "structural_label" if target in (structural_targets or set()) else "source" if text in source_text else "derived"
        if origin != "structural_label" and (not refs or not refs.issubset(allowed_evidence_refs)):
            raise ContractError(f"MBB claim binding evidence is invalid for {context}:{target}")
        if origin not in {"source", "derived", "structural_label"} or origin != expected_origin:
            raise ContractError(f"MBB claim binding origin is invalid for {context}:{target}")
        if not str(binding.get("derivation_note") or ""):
            raise ContractError(f"MBB claim binding derivation note is missing for {context}:{target}")
        if origin != "structural_label":
            spans = binding.get("evidence_spans")
            if not isinstance(spans, list) or not spans:
                raise ContractError(f"MBB claim binding evidence spans are missing for {context}:{target}")
            grounded_text: list[str] = []
            evidence_tokens: set[str] = set()
            for span in spans:
                if not isinstance(span, dict):
                    raise ContractError(f"MBB claim binding evidence span is invalid for {context}:{target}")
                span_ref = str(span.get("evidence_ref") or "")
                quote = str(span.get("quote") or "")
                if span_ref not in refs or not quote or str(span.get("quote_sha256") or "") != sha256_json(quote):
                    raise ContractError(f"MBB claim binding evidence span is stale for {context}:{target}")
                if quote not in _evidence_text(evidence_by_id[span_ref]):
                    raise ContractError(f"MBB claim binding evidence quote is not exact for {context}:{target}")
                grounded_text.append(quote)
                evidence_tokens.update(_grounding_tokens(_evidence_body_text(evidence_by_id[span_ref])))
            overlap = _grounding_tokens(text) & _grounding_tokens(" ".join(grounded_text))
            if origin == "derived" and len(overlap) < 2:
                raise ContractError(f"MBB claim binding is not lexically grounded for {context}:{target}")
            if origin == "derived" and _claim_requires_evidence_overlap(target) and not (_grounding_tokens(text) & evidence_tokens):
                raise ContractError(f"MBB claim binding does not match evidence content for {context}:{target}")
            numeric_source = " ".join(_evidence_text(evidence_by_id[ref]) for ref in refs)
            supported_numbers = _normalized_numeric_tokens(numeric_source)
            unsupported_numbers = [token for token in _numeric_tokens(text) if re.sub(r"\s+", "", token).replace("％", "%").replace(",", "").casefold() not in supported_numbers]
            if unsupported_numbers:
                raise ContractError(f"MBB claim binding adds unsupported factual values for {context}:{target}: {unsupported_numbers}")


def _derived_claims(package: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_ids = [item["evidence_id"] for item in evidence]
    return [
        {
            "claim_id": str(claim_id),
            "origin": "source",
            "evidence_refs": evidence_ids,
            "derivation_note": "Copied from the Page Package claim binding; no new factual value was added.",
            "factual_value_added": False,
        }
        for claim_id in package.get("claim_bindings") or []
    ]


def _storyline_candidates(
    packages: list[dict[str, Any]],
    evidence_ledger: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    titles = [str((package.get("customer_visible") or {}).get("title") or package.get("page_id") or "page") for package in packages]
    topic = titles[0] if titles else "the deck decision"
    audience_context = packages[0].get("audience_context") if packages else {}
    audience_role = str(audience_context.get("role") or "Executive decision makers") if isinstance(audience_context, dict) else "Executive decision makers"
    # Keep the audience statement grounded in the page topic so it remains a
    # real MBB claim binding rather than a free-floating template label.
    audience = f"{audience_role} deciding on {topic}"
    evidence_refs = [str(item["evidence_id"]) for item in evidence_ledger]
    evidence_refs = evidence_refs[:8]
    if not evidence_refs:
        raise ContractError("MBB storyline candidates require at least one evidence reference")
    page_refs = evidence_refs[: max(1, min(3, len(evidence_refs)))]
    content_fragments: list[str] = []
    for package in packages:
        visible = package.get("customer_visible") or {}
        content_fragments.append(str(visible.get("title") or ""))
        content_fragments.extend(_text(block) for block in visible.get("body_blocks") or [])
        content_fragments.extend(_text(callout) for callout in visible.get("callouts") or [])
    evidence_fragments = [str(item.get("meaning") or item.get("implication") or "") for item in evidence_ledger]
    signal = " ".join(fragment.strip() for fragment in [*content_fragments, *evidence_fragments] if fragment.strip())
    signal = signal[:180] or topic
    roles = sorted({str((package.get("visual_spec") or {}).get("page_type") or "dense_narrative") for package in packages})
    visual_language = ", ".join(roles[:4])
    specs = (
        (
            "storyline.decision",
            f"Prioritize the management decision around {topic}, grounded in: {signal}.",
            "decision-led",
            f"Makes {topic} the executive choice and turns the evidence into a clear recommendation using {visual_language}.",
            f"It can underweight implementation risks for {topic} when the operating constraints are material.",
        ),
        (
            "storyline.risk",
            f"Reduce the execution risk exposed by {topic} and its evidence signal: {signal}.",
            "risk-led",
            f"Surfaces the constraint and evidence gap around {topic} before committing resources, with {visual_language} proof points.",
            f"It can delay the decision on {topic} when the audience needs a direct recommendation first.",
        ),
        (
            "storyline.scale",
            f"Build a repeatable operating path from {topic} toward the observed outcome: {signal}.",
            "scale-led",
            f"Connects {topic} to a reusable process, controls, and measurable next actions across {visual_language}.",
            f"It can spread attention across operating detail for {topic} when one decision is the immediate need.",
        ),
    )
    candidates: list[dict[str, Any]] = []
    for storyline_id, conclusion, lens, visual_potential, rejection_reason in specs:
        candidate = {
                "storyline_id": storyline_id,
                "management_conclusion": conclusion,
                "audience": audience,
                "issue_hypothesis_tree": {
                    "root": f"How should leadership act on {topic}?",
                    "branches": [
                        {
                            "branch_id": f"{storyline_id}.evidence",
                            "question": f"What does the evidence say about {topic} and the observed signal?",
                            "hypothesis": f"The evidence supports a {lens} reading of {topic}: {signal}.",
                            "evidence_refs": page_refs,
                        },
                        {
                            "branch_id": f"{storyline_id}.action",
                            "question": f"What action follows from the evidence about {topic}?",
                            "hypothesis": conclusion,
                            "evidence_refs": page_refs,
                        },
                    ],
                },
                "evidence_refs": evidence_refs,
                "caveat": f"Validate the caveat and source period for {topic}; the candidate is grounded in the available signal: {signal}.",
                "visual_potential": visual_potential,
                "not_recommended_because": rejection_reason,
                "page_handoff": f"Carry the {lens} conclusion from {topic} into the next page's decision or proof point.",
                "density_target": {"band": "high", "information_regions": max(3, len(packages))},
                "language": "zh-CN",
                "evidence_assessment": _evidence_assessment(evidence_ledger, evidence_refs, subject=topic),
                "chart_plan": {
                    "visual_type": f"evidence_sequence for {topic}",
                    "metric_refs": [str(item.get("unit") or "") for item in evidence_ledger if str(item.get("unit") or "") != "unavailable"],
                    "comparison_axis": f"{topic} evidence under the {lens} lens",
                    "annotations": [str(item.get("caveat") or "") for item in evidence_ledger if item.get("caveat")],
                    "source_refs": list(evidence_refs),
                },
            }
        candidate["claim_bindings"] = _claim_bindings(
            candidate,
            _candidate_claim_targets(candidate),
            evidence_refs,
            source_text=_text(packages),
            evidence_by_id={str(item["evidence_id"]): item for item in evidence_ledger},
        )
        candidates.append(candidate)
    return candidates


def _storyline_context(storyline: dict[str, Any], *, structural_page: bool = False) -> dict[str, Any]:
    if structural_page:
        return {
            "storyline_id": str(storyline.get("storyline_id") or ""),
            "management_conclusion": "",
            "visual_potential": "structural layout",
            "page_handoff": "",
            "caveat": "",
            "evidence_refs": [],
        }
    return {
        "storyline_id": str(storyline.get("storyline_id") or ""),
        "management_conclusion": str(storyline.get("management_conclusion") or ""),
        "visual_potential": str(storyline.get("visual_potential") or ""),
        "page_handoff": str(storyline.get("page_handoff") or ""),
        "caveat": str(storyline.get("caveat") or ""),
        "evidence_refs": [str(ref) for ref in storyline.get("evidence_refs") or []],
    }


def _material_pool(
    package: dict[str, Any],
    source_result: dict[str, Any],
    storyline: dict[str, Any],
) -> dict[str, Any]:
    safe_package = strip_internal(package)
    analysis = source_result["analysis"]
    evidence_refs = [str(item["evidence_id"]) for item in source_result["evidence"]]
    visible = source_result["customer_visible"]
    blocks = [block for block in visible.get("body_blocks") or [] if isinstance(block, dict)]
    comparisons = [_text(block) for block in blocks if str(block.get("type") or "").lower() in {"comparison", "table", "matrix"}]
    changes = [value for value in analysis["numeric_tokens"] if value]
    annotations = [_text(item) for item in [*(visible.get("callouts") or []), *(visible.get("footnotes") or [])] if _text(item)]
    structural_page = bool(analysis.get("structural_page"))
    return {
        "customer_visible": copy.deepcopy(source_result["customer_visible"]),
        "evidence_refs": [] if structural_page else evidence_refs,
        "recommended_visual": canonical_page_role(
            (safe_package.get("visual_spec") or {}).get("page_type")
            or (safe_package.get("visual_spec") or {}).get("page_role")
            or analysis["page_role"],
            default=analysis["page_role"],
        ),
        "numeric_values": [] if structural_page else list(analysis["numeric_tokens"]),
        "storyline_id": str(storyline["storyline_id"]),
        "storyline_visual_potential": "structural layout" if structural_page else str(storyline["visual_potential"]),
        "storyline_page_handoff": "" if structural_page else str(storyline["page_handoff"]),
        "storyline_caveat": "" if structural_page else str(storyline["caveat"]),
        "comparisons": [] if structural_page else comparisons,
        "rankings": [],
        "changes": [] if structural_page else changes,
        "funnel_steps": [],
        "matrix_axes": [],
        "annotations": [] if structural_page else annotations,
        "legend": [str(value) for value in visible.get("labels") or []],
        "microcharts": [] if structural_page else [str(block.get("type") or "") for block in blocks if str(block.get("type") or "").lower() in {"chart", "kpi", "trend", "data_story"}],
        "area_count": max(3, len(source_result["components"])),
        "low_density_risk": "high" if analysis["density_band"] == "low" else "managed",
    }


def _evidence_assessment(
    evidence: list[dict[str, Any]],
    refs: list[str],
    *,
    subject: str = "",
    structural_page: bool = False,
) -> dict[str, Any]:
    selected = [item for item in evidence if str(item.get("evidence_id") or "") in set(refs)]
    contrary = [str(item["evidence_id"]) for item in selected if item.get("conflicts")]
    missing = [
        str(item["evidence_id"])
        for item in selected
        if str(item.get("source_position") or "unavailable") == "unavailable"
        or str(item.get("period") or "unavailable") == "unavailable"
    ]
    conflicts = [
        {"evidence_id": str(item["evidence_id"]), "conflicts": [str(value) for value in item.get("conflicts") or []]}
        for item in selected
        if item.get("conflicts")
    ]
    strongest = sorted(
        (str(item["evidence_id"]) for item in selected),
        key=lambda evidence_id: (
            "high" not in str(next(item for item in selected if str(item["evidence_id"]) == evidence_id).get("confidence") or "").lower(),
            evidence_id,
        ),
    )
    return {
        "strongest_evidence_refs": strongest[: min(3, len(strongest))],
        "evidence_strength": {str(item["evidence_id"]): str(item.get("confidence") or "declared") for item in selected},
        "contrary_evidence_refs": contrary,
        "missing_evidence": missing,
        "conflicts": conflicts,
        "synthesis": (
            "Structural page metadata; no page-level business conclusion is asserted."
            if structural_page
            else f"Evidence assessment for {subject or ', '.join(str(item.get('evidence_id') or '') for item in selected)}: preserve source caveats and resolve missing periods before circulation."
        ),
    }


def _chart_plan(source_result: dict[str, Any], storyline: dict[str, Any]) -> dict[str, Any]:
    analysis = source_result["analysis"]
    page_role = str(analysis.get("page_role") or "dense_narrative")
    visual_type = {
        "table": "comparison_table",
        "comparison": "side_by_side_comparison",
        "process": "sequenced_process",
        "architecture": "layered_architecture",
        "data_story": "annotated_data_story",
        "framework": "framework_map",
    }.get(page_role, "evidence_dense_narrative")
    subject = str((source_result.get("customer_visible") or {}).get("title") or page_role)
    structural_page = bool(analysis.get("structural_page"))
    return {
        "visual_type": f"structural_layout for {subject}" if structural_page else f"{visual_type} for {subject}",
        "metric_refs": [] if structural_page else list(analysis.get("numeric_tokens") or []),
        "comparison_axis": f"{subject} structural layout" if structural_page else f"{subject} {page_role} evidence against the {storyline['storyline_id'].split('.')[-1]} decision lens",
        "annotations": [] if structural_page else [str(item.get("caveat") or "") for item in source_result["evidence"] if item.get("caveat")],
        "source_refs": [] if structural_page else [str(item["evidence_id"]) for item in source_result["evidence"]],
    }


def _runtime_required_text_refs(source_result: dict[str, Any], so_what: str) -> list[dict[str, Any]]:
    refs = copy.deepcopy(source_result["required_text_refs"])
    for text_ref in refs:
        if text_ref.get("ref") == "content_lock.enrichment.business_implication":
            text_ref["value"] = so_what
    return refs


def _page_plan(
    package: dict[str, Any],
    source_result: dict[str, Any],
    storyline: dict[str, Any],
    packages_by_order: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    safe_package = strip_internal(package)
    visible = source_result["customer_visible"]
    analysis = source_result["analysis"]
    evidence = source_result["evidence"]
    structural_page = bool(analysis.get("structural_page"))
    evidence_refs = [str(item["evidence_id"]) for item in evidence]
    # Structural pages may omit evidence when they only carry layout metadata,
    # but source claim bindings still need their supporting refs preserved.
    if structural_page and not package.get("claim_bindings") and not _structural_factual_entries(visible):
        evidence_refs = []
    quality_intent = safe_package.get("quality_intent") or {}
    title = str(visible.get("title") or package.get("page_id") or "page")
    conclusion = "" if structural_page else str(quality_intent.get("conclusion") or f"{title}: {storyline['management_conclusion']}")
    arguments = [] if structural_page else [str(_text(block)) for block in visible.get("body_blocks") or [] if _text(block)]
    if not structural_page and not arguments:
        arguments = [f"Evidence-backed analysis for {title}."]
    caveat = [] if structural_page else [item["caveat"] for item in evidence if item.get("caveat")]
    if not structural_page and not caveat:
        caveat = [str(storyline["caveat"])]
    so_what = "" if structural_page else str(quality_intent.get("so_what") or f"Therefore, leadership should act on {title} through the {storyline['storyline_id'].split('.')[-1]} route.")
    next_package = packages_by_order.get(int(package.get("order") or 0) + 1)
    next_title = str((next_package or {}).get("customer_visible", {}).get("title") or "the next decision")
    handoff = "" if structural_page else f"Hand off the {title} conclusion to {next_title}."
    components = copy.deepcopy(source_result["components"])
    required_text_refs = _runtime_required_text_refs(source_result, so_what)
    chart_plan = _chart_plan(source_result, storyline)
    evidence_hierarchy = {
        "primary": evidence_refs[: min(3, len(evidence_refs))],
        "supporting": evidence_refs[min(3, len(evidence_refs)) :],
        "caveat": [] if structural_page else [str(item["evidence_id"]) for item in evidence if item.get("caveat")],
    }
    page_plan = {
        "page_id": str(package["page_id"]),
        "order": int(package.get("order") or 0),
        "page_package_sha256": sha256_json(package),
        "storyline_id": str(storyline["storyline_id"]),
        "storyline_context": _storyline_context(storyline, structural_page=structural_page),
        "role": str(analysis["page_role"]),
        "conclusion": conclusion,
        "supporting_arguments": arguments,
        "detailed_argument": " ".join(arguments),
        "evidence_refs": evidence_refs,
        "caveat": caveat,
        "so_what": so_what,
        "business_implication": so_what,
        "handoff": handoff,
        "evidence_hierarchy": evidence_hierarchy,
        "evidence_assessment": _evidence_assessment(evidence, evidence_refs, subject=title, structural_page=structural_page),
        "chart_plan": chart_plan,
        "material_pool": _material_pool(package, source_result, storyline),
        "density_target": {
            "score": analysis["content_density_score"],
            "band": analysis["density_band"],
            "information_regions": max(3 if structural_page else 3, len(components)),
        },
        "components": components,
        "required_text_refs": required_text_refs,
        "derived_claims": _derived_claims(safe_package, evidence),
        "status": "ready",
    }
    page_plan["claim_bindings"] = _claim_bindings(
        page_plan,
        _page_claim_targets(page_plan),
        evidence_refs,
        source_text=_text(safe_package),
        structural_targets=_page_structural_claim_targets(page_plan),
        evidence_by_id={str(item["evidence_id"]): item for item in evidence},
    )
    page_plan["page_plan_sha256"] = sha256_json(page_plan)
    return page_plan


def build_mbb_page(package: dict[str, Any]) -> dict[str, Any]:
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
    structural_page = bool(analysis.get("structural_page"))
    # A preview adapter can only appear in fixture/migration mode.  Preserve
    # that narrow compatibility path while keeping normal v2 production pages
    # fail-closed on evidence and density.
    unsupported_numeric = (
        _unsupported_structural_numeric_tokens(customer_visible, analysis["numeric_tokens"], evidence=evidence)
        if structural_page
        else analysis["numeric_tokens"]
    )
    structural_factual_texts = _structural_factual_texts(customer_visible) if structural_page else []
    if structural_factual_texts and not evidence and not package.get("legacy_inferred"):
        preview = ", ".join(repr(text[:80]) for text in structural_factual_texts[:3])
        raise ContractError(f"MBB page {page_id} contains structural factual text without evidence: {preview}")
    if unsupported_numeric and (structural_page or not evidence) and not package.get("legacy_inferred"):
        raise ContractError(f"MBB page {page_id} contains unsupported factual values: {unsupported_numeric}")
    if (analysis["density_band"] == "low" or not evidence) and not structural_page and not package.get("legacy_inferred"):
        raise ContractError(f"MBB page {page_id} is too sparse for high-density output; add evidence and at least three content regions")
    components = _component_plan(customer_visible, analysis)
    if not components:
        raise ContractError(f"MBB page {page_id} has no required components")
    conclusion = "" if structural_page else str((safe_package.get("quality_intent") or {}).get("conclusion") or customer_visible.get("title") or "")
    arguments = [] if structural_page else [str(_text(block)) for block in customer_visible.get("body_blocks") or [] if _text(block)]
    caveats = [] if structural_page else [item["caveat"] for item in evidence if item.get("caveat")]
    so_what = "" if structural_page else str((safe_package.get("quality_intent") or {}).get("so_what") or (arguments[-1] if arguments else conclusion))
    coverage = {
        "facts": 1.0 if evidence or structural_page or package.get("legacy_inferred") else 0.0,
        "numeric_values": 1.0
        if (structural_page and not unsupported_numeric) or evidence or not analysis["numeric_tokens"]
        else 0.0,
        "derived_claims": 1.0 if all(item.get("evidence_refs") for item in _derived_claims(safe_package, evidence)) else 0.0,
    }
    if min(coverage.values()) < 1.0:
        raise ContractError(f"MBB evidence coverage failed on page {page_id}: {coverage}")
    enrichment = {
        "framework": "mbb",
        "version": "cyber-ppt-mbb.v2",
        "analysis": analysis,
        "evidence_ledger": evidence,
        "conclusion": conclusion,
        "supporting_arguments": arguments,
        "detailed_argument": " ".join(arguments),
        "caveat": caveats,
        "so_what": so_what,
        "business_implication": so_what,
        "handoff": "" if structural_page else str((safe_package.get("quality_intent") or {}).get("handoff") or ""),
        "evidence_hierarchy": {"primary": [item["evidence_id"] for item in evidence], "supporting": [], "caveat": []},
        "evidence_assessment": _evidence_assessment(
            evidence,
            [item["evidence_id"] for item in evidence],
            subject=str(customer_visible.get("title") or page_id),
            structural_page=structural_page,
        ),
        "chart_plan": {"visual_type": "structural_layout" if structural_page else "evidence_dense_narrative", "metric_refs": [], "comparison_axis": "structural layout" if structural_page else "evidence", "annotations": [], "source_refs": [] if structural_page else [item["evidence_id"] for item in evidence]},
        "material_pool": {
            "facts": copy.deepcopy(customer_visible),
            "evidence_ids": [item["evidence_id"] for item in evidence],
            "numeric_values": [] if structural_page else analysis["numeric_tokens"],
        },
        "derived_claims": _derived_claims(safe_package, evidence),
        "structure_decisions": _structure_decisions(analysis),
        "component_plan": components,
        "evidence_coverage": coverage,
    }
    return {"customer_visible": customer_visible, "evidence": evidence, "analysis": analysis, "enrichment": enrichment, "components": components, "required_text_refs": _required_text_refs(customer_visible, so_what=so_what), "so_what": so_what}


def build_content_lock(
    package: dict[str, Any],
    page_plan: dict[str, Any] | None = None,
    *,
    mbb_plan_sha256: str,
) -> dict[str, Any]:
    page_id = str(package.get("page_id") or "")
    run_id = str(package.get("run_id") or "")
    if not isinstance(page_plan, dict):
        raise ContractError(f"approved MBB page plan is required for content lock on {page_id}")
    if str(page_plan.get("page_id") or "") != page_id:
        raise ContractError(f"MBB page plan page_id mismatch on {page_id}")
    if page_plan.get("status") != "ready":
        raise ContractError(f"MBB page plan is not ready on {page_id}")
    expected_page_plan_sha = sha256_json({key: value for key, value in page_plan.items() if key not in {"page_plan_sha256", "created_at", "updated_at"}})
    if str(page_plan.get("page_plan_sha256") or "") != expected_page_plan_sha:
        raise ContractError(f"MBB page plan hash is stale on {page_id}")
    if str(page_plan.get("page_package_sha256") or "") != sha256_json(package):
        raise ContractError(f"MBB page plan is stale for Page Package {page_id}")
    if not re.fullmatch(r"[a-f0-9]{64}", str(mbb_plan_sha256 or "")):
        raise ContractError(f"MBB plan hash is required for content lock on {page_id}")
    result = build_mbb_page(package)
    structural_page = bool(result["analysis"].get("structural_page"))
    storyline_context = page_plan.get("storyline_context")
    if (
        not isinstance(storyline_context, dict)
        or str(storyline_context.get("storyline_id") or "") != str(page_plan.get("storyline_id") or "")
        or storyline_context != _storyline_context(storyline_context, structural_page=structural_page)
    ):
        raise ContractError(f"MBB page plan storyline context is missing or stale on {page_id}")
    safe_package = strip_internal(package)
    evidence_by_id = {str(item["evidence_id"]): item for item in result["evidence"]}
    evidence_refs = [str(ref) for ref in page_plan.get("evidence_refs") or []]
    missing_evidence = sorted(set(evidence_refs) - set(evidence_by_id))
    if missing_evidence:
        raise ContractError(f"MBB page plan references unknown evidence on {page_id}: {missing_evidence}")
    if page_plan.get("material_pool") != _material_pool(package, result, storyline_context):
        raise ContractError(f"MBB page plan material pool is outside the Runtime registry on {page_id}")
    if page_plan.get("components") != result["components"]:
        raise ContractError(f"MBB page plan components are outside the Runtime registry on {page_id}")
    expected_text_refs = _runtime_required_text_refs(result, str(page_plan.get("so_what") or ""))
    if page_plan.get("required_text_refs") != expected_text_refs:
        raise ContractError(f"MBB page plan required text refs are outside the Runtime registry on {page_id}")
    expected_derived_claims = _derived_claims(safe_package, result["evidence"])
    if page_plan.get("derived_claims") != expected_derived_claims:
        raise ContractError(f"MBB page plan derived claims are outside the Runtime registry on {page_id}")
    for claim in expected_derived_claims:
        claim_refs = {str(ref) for ref in claim.get("evidence_refs") or []}
        if not claim_refs or not claim_refs.issubset(set(evidence_refs)) or not str(claim.get("derivation_note") or ""):
            raise ContractError(f"MBB derived claim evidence is imprecise on {page_id}")
    _validate_claim_bindings(
        page_plan,
        required_targets=_page_claim_targets(page_plan),
        allowed_evidence_refs=set(evidence_refs),
        evidence_by_id=evidence_by_id,
        source_text=_text(safe_package),
        context=f"page {page_id}",
        structural_targets=_page_structural_claim_targets(page_plan),
    )
    enrichment = {
        "framework": "mbb",
        "version": "cyber-ppt-mbb.v2",
        "storyline_id": str(page_plan.get("storyline_id") or ""),
        "storyline_context": copy.deepcopy(storyline_context),
        "analysis": result["analysis"],
        "evidence_ledger": result["evidence"],
        "conclusion": str(page_plan.get("conclusion") or ""),
        "supporting_arguments": list(page_plan.get("supporting_arguments") or []),
        "detailed_argument": str(page_plan.get("detailed_argument") or ""),
        "caveat": list(page_plan.get("caveat") or []),
        "so_what": str(page_plan.get("so_what") or ""),
        "business_implication": str(page_plan.get("business_implication") or ""),
        "handoff": str(page_plan.get("handoff") or ""),
        "evidence_hierarchy": copy.deepcopy(page_plan.get("evidence_hierarchy") or {}),
        "evidence_assessment": copy.deepcopy(page_plan.get("evidence_assessment") or {}),
        "chart_plan": copy.deepcopy(page_plan.get("chart_plan") or {}),
        "material_pool": copy.deepcopy(page_plan.get("material_pool") or {}),
        "derived_claims": copy.deepcopy(page_plan.get("derived_claims") or []),
        "claim_bindings": copy.deepcopy(page_plan.get("claim_bindings") or []),
        "structure_decisions": _structure_decisions(result["analysis"]),
        "component_plan": copy.deepcopy(page_plan.get("components") or []),
        "evidence_coverage": {
            "facts": 1.0 if structural_page or evidence_refs else 0.0,
            "numeric_values": 1.0
            if (
                (
                    structural_page
                    and not _unsupported_structural_numeric_tokens(
                        result["customer_visible"],
                        result["analysis"]["numeric_tokens"],
                        evidence=result["evidence"],
                    )
                )
                or result["evidence"]
                or not result["analysis"]["numeric_tokens"]
            )
            else 0.0,
            "derived_claims": 1.0 if all(item.get("evidence_refs") and item.get("derivation_note") for item in page_plan.get("derived_claims") or []) else 0.0,
        },
    }
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
        "enrichment": enrichment,
        "required_component_ids": [item["component_id"] for item in page_plan.get("components") or []],
        "required_text_refs": copy.deepcopy(page_plan.get("required_text_refs") or []),
        "density_target": {
            "score": float((page_plan.get("density_target") or {}).get("score") or result["analysis"]["content_density_score"]),
            "band": str((page_plan.get("density_target") or {}).get("band") or result["analysis"]["density_band"]),
            "information_regions": int((page_plan.get("density_target") or {}).get("information_regions") or max(1 if result["analysis"].get("structural_page") else 3, len(result["components"]))),
            "component_count": len(result["components"]),
            "evidence_count": len(result["evidence"]),
            "numeric_count": result["analysis"]["numeric_token_count"],
        },
        "target_language": result["analysis"]["target_language"],
        "effective_language": result["analysis"]["target_language"],
        "visibility_policy": build_visibility_policy(safe_package, page_id=page_id),
        "lineage": {
            "page_package_sha256": sha256_json(package),
            "mbb_plan_sha256": mbb_plan_sha256,
            "selected_storyline_id": str(page_plan.get("storyline_id") or ""),
            "mbb_page_plan_sha256": str(page_plan.get("page_plan_sha256") or ""),
        },
        "created_at": utc_now(),
    }
    source_fp = str(lock["source_fingerprint"])
    if len(source_fp) != 64:
        lock["source_fingerprint"] = sha256_json({"page_id": page_id, "source": source_fp})
    lock["content_lock_sha256"] = sha256_json({key: value for key, value in lock.items() if key not in {"content_lock_sha256", "created_at", "updated_at"}})
    assert_v2("content_lock", lock)
    return lock


def _build_scr(packages: list[dict[str, Any]], storyline: dict[str, Any]) -> dict[str, Any]:
    first_title = str((packages[0].get("customer_visible") or {}).get("title") or packages[0].get("page_id") or "page")
    scr = {
        "situation": f"The deck contains evidence-backed material about {first_title} and related page decisions.",
        "complication": f"Leadership must decide how to act on {first_title} while preserving evidence, caveats, and execution constraints.",
        "resolution": str(storyline["management_conclusion"]),
        "evidence_refs": list(storyline["evidence_refs"]),
        "decision_implication": str(storyline["page_handoff"]),
        "evidence_assessment": _evidence_assessment(
            [item for package in packages for item in _evidence_ledger(package)],
            list(storyline["evidence_refs"]),
            subject=first_title,
        ),
    }
    scr["claim_bindings"] = _claim_bindings(
        scr,
        _scr_claim_targets(scr),
        list(storyline["evidence_refs"]),
        source_text=_text(packages),
        evidence_by_id={str(item["evidence_id"]): item for package in packages for item in _evidence_ledger(package)},
    )
    return scr


def enrich_selected_mbb_plan(plan: dict[str, Any], packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic fixture/dev enrichment adapter.

    Production and benchmark runs receive this artifact from the MBB Agent;
    the Runtime only validates and seals the selected content. Keeping the
    adapter explicit prevents a generic Runtime template from replacing Agent
    SCR, arguments, caveats, or page material in a real run.
    """
    enriched = copy.deepcopy(plan)
    selection = enriched.get("selection") or {}
    if str(selection.get("status") or "") not in {"selected_pending_enrichment", "approved"}:
        raise ContractError("MBB storyline must be selected before page enrichment")
    selected_id = str(selection.get("selected_storyline_id") or "")
    storyline = next(
        (item for item in enriched.get("storyline_candidates") or [] if str(item.get("storyline_id") or "") == selected_id),
        None,
    )
    if storyline is None:
        raise ContractError(f"unknown MBB storyline_id: {selected_id}")
    source_results = {str(package["page_id"]): build_mbb_page(package) for package in packages}
    packages_by_order = {int(package.get("order") or 0): package for package in packages}
    enriched["scr"] = _build_scr(packages, storyline)
    enriched["pages"] = [
        _page_plan(package, source_results[str(package["page_id"])], storyline, packages_by_order)
        for package in sorted(packages, key=lambda item: int(item.get("order") or 0))
    ]
    enriched["mbb_plan_sha256"] = sha256_json(
        {key: value for key, value in enriched.items() if key not in {"mbb_plan_sha256", "created_at", "updated_at"}}
    )
    assert_v2("mbb_plan", enriched)
    return enriched


def build_mbb_plan(
    packages: list[dict[str, Any]],
    *,
    run_id: str,
) -> dict[str, Any]:
    if not packages:
        raise ContractError("MBB plan requires at least one Page Package")
    source_results: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for package in packages:
        page_id = str(package.get("page_id") or "")
        if str(package.get("run_id") or "") != run_id:
            raise ContractError(f"MBB plan package run_id mismatch on {page_id}: expected {run_id}")
        try:
            result = build_mbb_page(package)
        except ContractError as exc:
            blocked.append({"page_id": page_id, "reason": str(exc)})
            continue
        source_results[page_id] = result
        ledger.extend(result["evidence"])
    if blocked:
        raise ContractError(f"MBB plan blocked pages: {blocked}")
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in ledger:
        evidence_id = str(item.get("evidence_id") or "")
        if not evidence_id:
            raise ContractError("MBB evidence ledger contains an empty evidence_id")
        if evidence_id in evidence_by_id:
            raise ContractError(f"MBB evidence_id must be globally unique across Page Packages: {evidence_id}")
        evidence_by_id[evidence_id] = item
    evidence_ledger = [evidence_by_id[key] for key in sorted(evidence_by_id)]
    candidates = _storyline_candidates(packages, evidence_ledger)
    recommended_id = str(candidates[0]["storyline_id"])
    plan = {
        "schema_version": "deck_mbb_plan.v1",
        "run_id": run_id,
        "page_count": len(packages),
        "evidence_ledger": evidence_ledger,
        "storyline_candidates": candidates,
        "selection": {
            "status": "pending_user_decision",
            "recommended_storyline_id": recommended_id,
            "selected_storyline_id": None,
            "selected_by": None,
            "selected_at": None,
            "sealed_at": None,
        },
        "storyline_audit": {
            "source": "page_packages",
            "status": "pending_user_decision",
            "candidate_count": len(candidates),
            "recommendation_id": recommended_id,
            "selected_id": None,
            "content_specific": True,
            "notes": "MBB candidates are derived from page titles, evidence refs, page roles, caveats, and visual requirements.",
        },
        "scr": None,
        "pages": [],
        "blocked_pages": [],
        "created_at": utc_now(),
    }
    plan["mbb_plan_sha256"] = sha256_json(
        {key: value for key, value in plan.items() if key not in {"mbb_plan_sha256", "created_at", "updated_at"}}
    )
    assert_v2("mbb_plan", plan)
    return plan


def _selection_receipt_payload(
    plan: dict[str, Any],
    packages: list[dict[str, Any]],
) -> dict[str, Any]:
    selection = plan.get("selection") or {}
    return {
        "schema_version": "deck_mbb_selection_receipt.v1",
        "run_id": str(plan.get("run_id") or ""),
        "selected_storyline_id": str(selection.get("selected_storyline_id") or ""),
        "recommended_storyline_id": str(selection.get("recommended_storyline_id") or ""),
        "selected_by": str(selection.get("selected_by") or ""),
        "selected_at": str(selection.get("selected_at") or ""),
        "candidate_set_sha256": sha256_json(plan.get("storyline_candidates") or []),
        "evidence_ledger_sha256": sha256_json(plan.get("evidence_ledger") or []),
        "page_package_sha256": {
            str(package.get("page_id") or ""): sha256_json(package)
            for package in packages
        },
    }


def record_mbb_user_decision(root: Path, storyline_id: str, *, attestor_id: str) -> Path:
    """Record a host/UI-attested storyline choice before Runtime selection."""
    packages = load_page_packages(root, expected_run_id=str(read_json(root / "request.json").get("run_id") or root.name))
    if not packages:
        raise ContractError("cannot attest an MBB decision without Page Packages")
    plan = load_mbb_plan(root, packages=packages, expected_run_id=str(packages[0].get("run_id") or ""), require_approved=False)
    if str((plan.get("selection") or {}).get("status") or "") != "pending_user_decision":
        raise ContractError("MBB user decision can only be attested while selection is pending")
    candidate_ids = {str(item.get("storyline_id") or "") for item in plan.get("storyline_candidates") or [] if isinstance(item, dict)}
    if storyline_id not in candidate_ids:
        raise ContractError(f"unknown MBB storyline_id: {storyline_id}")
    if not str(attestor_id or "").strip():
        raise ContractError("external MBB decision attestor_id is required")
    payload = {
        "schema_version": "deck_mbb_user_decision_receipt.v1",
        "run_id": str(plan.get("run_id") or ""),
        "selected_storyline_id": storyline_id,
        "attestor_id": str(attestor_id),
        "attested_at": utc_now(),
        "candidate_set_sha256": sha256_json(plan.get("storyline_candidates") or []),
        "evidence_ledger_sha256": sha256_json(plan.get("evidence_ledger") or []),
        "page_package_sha256": {str(package.get("page_id") or ""): sha256_json(package) for package in packages},
    }
    receipt = {**payload, "integrity": sign_user_attestation(payload)}
    assert_v2("mbb_user_decision_receipt", receipt)
    return write_json(root / MBB_USER_DECISION_RECEIPT_PATH, receipt)


def _load_mbb_user_decision_receipt(root: Path, plan: dict[str, Any], packages: list[dict[str, Any]], storyline_id: str) -> dict[str, Any]:
    try:
        receipt = read_json(root / MBB_USER_DECISION_RECEIPT_PATH)
    except ContractError as exc:
        raise ContractError("external user decision attestation is required before production storyline selection") from exc
    assert_v2("mbb_user_decision_receipt", receipt)
    payload = {key: value for key, value in receipt.items() if key != "integrity"}
    try:
        verify_user_attestation(payload, receipt.get("integrity") or {})
    except ContractError as exc:
        raise ContractError(f"external user decision attestation is invalid: {exc}") from exc
    expected = {
        "run_id": str(plan.get("run_id") or ""),
        "selected_storyline_id": storyline_id,
        "candidate_set_sha256": sha256_json(plan.get("storyline_candidates") or []),
        "evidence_ledger_sha256": sha256_json(plan.get("evidence_ledger") or []),
        "page_package_sha256": {str(package.get("page_id") or ""): sha256_json(package) for package in packages},
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ContractError(f"external user decision attestation {field} is stale")
    return receipt


def _load_mbb_selection_receipt(
    root: Path,
    plan: dict[str, Any],
    *,
    packages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = root / MBB_SELECTION_RECEIPT_PATH
    receipt = read_json(path)
    assert_v2("mbb_selection_receipt", receipt)
    payload = {key: value for key, value in receipt.items() if key != "integrity"}
    verify_runtime_payload("mbb_storyline_selection.v1", payload, receipt.get("integrity") or {})
    selection = plan.get("selection") or {}
    expected_fields = {
        "run_id": str(plan.get("run_id") or ""),
        "selected_storyline_id": str(selection.get("selected_storyline_id") or ""),
        "recommended_storyline_id": str(selection.get("recommended_storyline_id") or ""),
        "selected_by": str(selection.get("selected_by") or ""),
        "selected_at": str(selection.get("selected_at") or ""),
        "candidate_set_sha256": sha256_json(plan.get("storyline_candidates") or []),
        "evidence_ledger_sha256": sha256_json(plan.get("evidence_ledger") or []),
    }
    for field, expected in expected_fields.items():
        if str(receipt.get(field) or "") != expected:
            raise ContractError(f"MBB Runtime selection receipt {field} is stale")
    if packages is not None:
        expected_package_hashes = {
            str(package.get("page_id") or ""): sha256_json(package)
            for package in packages
        }
        if receipt.get("page_package_sha256") != expected_package_hashes:
            raise ContractError("MBB Runtime selection receipt Page Package lineage is stale")
    return receipt


def load_mbb_plan(
    root: Path,
    *,
    packages: list[dict[str, Any]] | None = None,
    expected_run_id: str | None = None,
    require_approved: bool = True,
) -> dict[str, Any]:
    assert_current_mbb_artifact(root)
    path = root / MBB_PLAN_PATH
    plan = read_json(path)
    assert_current_mbb_artifact(root, plan)
    assert_v2("mbb_plan", plan)
    run_id = expected_run_id or str((packages or [{}])[0].get("run_id") or "")
    if run_id and str(plan.get("run_id") or "") != run_id:
        raise ContractError(f"MBB plan run_id mismatch: expected {run_id}")
    expected_hash = sha256_json({key: value for key, value in plan.items() if key not in {"mbb_plan_sha256", "created_at", "updated_at"}})
    if str(plan.get("mbb_plan_sha256") or "") != expected_hash:
        raise ContractError("MBB plan hash is stale")
    candidates = plan.get("storyline_candidates") or []
    candidate_ids = {str(item.get("storyline_id") or "") for item in candidates if isinstance(item, dict)}
    if len(candidate_ids) != len(candidates):
        raise ContractError("MBB storyline candidate IDs must be unique")
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in plan.get("evidence_ledger") or []:
        if not isinstance(item, dict):
            raise ContractError("MBB evidence ledger entries must be objects")
        evidence_id = str(item.get("evidence_id") or "")
        if not evidence_id:
            raise ContractError("MBB evidence ledger contains an empty evidence_id")
        if evidence_id in evidence_by_id:
            raise ContractError(f"MBB evidence_id must be globally unique across MBB plan: {evidence_id}")
        evidence_by_id[evidence_id] = item
    ledger_ids = set(evidence_by_id)
    minimum_candidate_refs = min(5, len(ledger_ids))
    if len(candidates) < 2 or len(candidates) > 3:
        raise ContractError("MBB plan must contain two or three storyline candidates")
    source_text = _text(packages or plan.get("evidence_ledger") or [])
    for candidate in candidates:
        candidate_refs = {str(ref) for ref in candidate.get("evidence_refs") or []}
        if len(candidate_refs) < minimum_candidate_refs or not candidate_refs.issubset(ledger_ids):
            raise ContractError(f"MBB storyline evidence coverage is invalid: {candidate.get('storyline_id')}")
        tree = candidate.get("issue_hypothesis_tree") or {}
        for branch in tree.get("branches") or []:
            branch_refs = {str(ref) for ref in branch.get("evidence_refs") or []}
            if not branch_refs or not branch_refs.issubset(ledger_ids):
                raise ContractError(f"MBB issue/hypothesis evidence refs are invalid: {candidate.get('storyline_id')}")
        _validate_claim_bindings(
            candidate,
            required_targets=_candidate_claim_targets(candidate),
            allowed_evidence_refs=candidate_refs,
            evidence_by_id=evidence_by_id,
            source_text=source_text,
            context=f"storyline {candidate.get('storyline_id')}",
        )
    selection = plan.get("selection") or {}
    selection_status = str(selection.get("status") or "")
    selected_id = str(selection.get("selected_storyline_id") or "")
    audit = plan.get("storyline_audit") or {}
    if (
        str(audit.get("status") or "") != selection_status
        or str(audit.get("recommendation_id") or "") != str(selection.get("recommended_storyline_id") or "")
        or str(audit.get("selected_id") or "") != (selected_id or "")
    ):
        raise ContractError("MBB storyline audit is inconsistent with selection")
    if selection_status not in {"pending_user_decision", "selected_pending_enrichment", "approved"}:
        raise ContractError("MBB plan selection status is invalid")
    if str(selection.get("recommended_storyline_id") or "") not in candidate_ids:
        raise ContractError("MBB plan recommended storyline is unknown")
    if selection_status == "pending_user_decision":
        if any(selection.get(field) is not None for field in ("selected_storyline_id", "selected_by", "selected_at", "sealed_at")):
            raise ContractError("pending MBB plan cannot contain selection or seal fields")
        if plan.get("scr") is not None or plan.get("pages"):
            raise ContractError("pending MBB plan must contain candidates only")
        if require_approved:
            raise ContractError("MBB plan awaits user storyline confirmation")
    else:
        if selected_id not in candidate_ids or not str(selection.get("selected_by") or "") or not str(selection.get("selected_at") or ""):
            raise ContractError("selected MBB plan requires a known storyline, selector, and selection time")
        if selection_status == "approved" and not str(selection.get("sealed_at") or ""):
            raise ContractError("approved MBB plan requires a seal time")
        if selection_status == "selected_pending_enrichment" and selection.get("sealed_at") is not None:
            raise ContractError("unsealed MBB plan cannot contain a seal time")
        if require_approved and selection_status != "approved":
            raise ContractError("MBB plan awaits selected-storyline enrichment")
        _load_mbb_selection_receipt(root, plan, packages=packages)
    if plan.get("blocked_pages"):
        raise ContractError("MBB plan contains blocked pages")
    if packages is None:
        if selection_status == "approved":
            _validate_mbb_runtime_seal(root, plan)
        return plan
    expected_pages = {(str(package.get("page_id") or ""), int(package.get("order") or 0)) for package in packages}
    plan_pages = plan.get("pages")
    if not isinstance(plan_pages, list):
        raise ContractError("MBB plan pages must be an array")
    if selection_status == "pending_user_decision":
        return plan
    if selection_status == "selected_pending_enrichment" and not plan_pages and plan.get("scr") is None:
        return plan
    if (not plan_pages) != (plan.get("scr") is None):
        raise ContractError("selected MBB enrichment must contain both SCR and page plans")
    scr = plan.get("scr") or {}
    scr_refs = {str(ref) for ref in scr.get("evidence_refs") or []}
    if not scr_refs or not scr_refs.issubset(ledger_ids):
        raise ContractError("MBB SCR evidence refs are invalid")
    _validate_claim_bindings(
        scr,
        required_targets=_scr_claim_targets(scr),
        allowed_evidence_refs=scr_refs,
        evidence_by_id=evidence_by_id,
        source_text=source_text,
        context="SCR",
    )
    actual_pages = {(str(page.get("page_id") or ""), int(page.get("order") or 0)) for page in plan_pages if isinstance(page, dict)}
    if int(plan.get("page_count") or 0) != len(expected_pages) or actual_pages != expected_pages:
        raise ContractError("MBB plan page coverage is stale for the current Page Packages")
    for page in plan_pages:
        if not isinstance(page, dict):
            raise ContractError("MBB plan page entry must be an object")
        page_id = str(page.get("page_id") or "")
        package = next((item for item in packages if str(item.get("page_id") or "") == page_id), None)
        if package is None or str(page.get("page_package_sha256") or "") != sha256_json(package):
            raise ContractError(f"MBB plan Page Package hash is stale on {page_id}")
        if str(page.get("storyline_id") or "") not in candidate_ids:
            raise ContractError(f"MBB plan page storyline is unknown on {page_id}")
        storyline = next(item for item in candidates if str(item.get("storyline_id") or "") == str(page.get("storyline_id") or ""))
        source_result = build_mbb_page(package)
        structural_page = bool((source_result.get("analysis") or {}).get("structural_page"))
        context = page.get("storyline_context") or {}
        if context != _storyline_context(storyline, structural_page=structural_page):
            raise ContractError(f"MBB page storyline context is stale on {page_id}")
        page_evidence = {str(ref) for ref in page.get("evidence_refs") or []}
        package_evidence = {str(ref.get("evidence_id") if isinstance(ref, dict) else ref) for ref in _evidence_ledger(package)}
        if (not structural_page and not page_evidence) or not page_evidence.issubset(ledger_ids) or not page_evidence.issubset(package_evidence):
            raise ContractError(f"MBB plan evidence refs are invalid on {page_id}")
        if page.get("material_pool") != _material_pool(package, source_result, storyline):
            raise ContractError(f"MBB plan material pool is outside the Runtime registry on {page_id}")
        if page.get("components") != source_result["components"]:
            raise ContractError(f"MBB plan components are outside the Runtime registry on {page_id}")
        expected_text_refs = _runtime_required_text_refs(source_result, str(page.get("so_what") or ""))
        if page.get("required_text_refs") != expected_text_refs:
            raise ContractError(f"MBB plan required text refs are outside the Runtime registry on {page_id}")
        expected_derived_claims = _derived_claims(strip_internal(package), source_result["evidence"])
        if page.get("derived_claims") != expected_derived_claims:
            raise ContractError(f"MBB plan derived claims are outside the Runtime registry on {page_id}")
        for claim in expected_derived_claims:
            claim_refs = {str(ref) for ref in claim.get("evidence_refs") or []}
            if not claim_refs or not claim_refs.issubset(page_evidence) or not str(claim.get("derivation_note") or ""):
                raise ContractError(f"MBB plan derived claim evidence is imprecise on {page_id}")
        _validate_claim_bindings(
            page,
            required_targets=_page_claim_targets(page),
            allowed_evidence_refs=page_evidence,
            evidence_by_id=evidence_by_id,
            source_text=_text(package),
            context=f"page {page_id}",
            structural_targets=_page_structural_claim_targets(page),
        )
        expected_page_hash = sha256_json({key: value for key, value in page.items() if key not in {"page_plan_sha256", "created_at", "updated_at"}})
        if str(page.get("page_plan_sha256") or "") != expected_page_hash:
            raise ContractError(f"MBB page plan hash is stale on {page_id}")
        if str(page.get("storyline_id") or "") != selected_id:
            raise ContractError(f"MBB page plan uses an unselected storyline on {page_id}")
    if selection_status == "approved":
        _validate_mbb_runtime_seal(root, plan, packages=packages)
    return plan


def _validate_mbb_runtime_seal(
    root: Path,
    plan: dict[str, Any],
    *,
    packages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = root / MBB_SEAL_PATH
    if not path.is_file():
        raise ContractError("approved MBB plan is missing its Runtime seal")
    seal = read_json(path)
    assert_v2("mbb_runtime_seal", seal)
    seal_payload = {key: value for key, value in seal.items() if key != "integrity"}
    verify_runtime_payload("mbb_plan_seal.v1", seal_payload, seal.get("integrity") or {})
    if str(seal.get("run_id") or "") != str(plan.get("run_id") or ""):
        raise ContractError("MBB Runtime seal run_id is stale")
    if str(seal.get("selected_storyline_id") or "") != str((plan.get("selection") or {}).get("selected_storyline_id") or ""):
        raise ContractError("MBB Runtime seal storyline is stale")
    if str(seal.get("mbb_plan_sha256") or "") != str(plan.get("mbb_plan_sha256") or ""):
        raise ContractError("MBB Runtime seal plan hash is stale")
    _load_mbb_selection_receipt(root, plan, packages=packages)
    if str(seal.get("selection_receipt_sha256") or "") != sha256_file(root / MBB_SELECTION_RECEIPT_PATH):
        raise ContractError("MBB Runtime seal selection receipt is stale")
    if packages is not None:
        expected_package_hashes = {
            str(package.get("page_id") or ""): sha256_json(package)
            for package in packages
        }
        if seal.get("page_package_sha256") != expected_package_hashes:
            raise ContractError("MBB Runtime seal Page Package lineage is stale")
    return seal


def select_mbb_storyline(root: Path, storyline_id: str, *, selected_by: str = "user") -> dict[str, Any]:
    packages = load_page_packages(root, expected_run_id=str(read_json(root / "request.json").get("run_id") or root.name))
    if not packages:
        raise ContractError("cannot approve MBB plan without Page Packages")
    plan = load_mbb_plan(root, packages=packages, expected_run_id=str(packages[0].get("run_id") or ""), require_approved=False)
    selection = plan.get("selection") or {}
    if str(selection.get("selected_storyline_id") or "") == storyline_id and str(selection.get("status") or "") in {"selected_pending_enrichment", "approved"}:
        return plan
    if str(selection.get("status") or "") != "pending_user_decision":
        raise ContractError("MBB storyline selection is already in progress; regenerate candidates before changing it")
    candidate_ids = {str(item.get("storyline_id") or "") for item in plan.get("storyline_candidates") or [] if isinstance(item, dict)}
    if storyline_id not in candidate_ids:
        raise ContractError(f"unknown MBB storyline_id: {storyline_id}")
    plan["selection"] = {
        "status": "selected_pending_enrichment",
        "recommended_storyline_id": str((plan.get("selection") or {}).get("recommended_storyline_id") or storyline_id),
        "selected_storyline_id": storyline_id,
        "selected_by": str(selected_by or "unidentified_local_input"),
        "selected_at": utc_now(),
        "sealed_at": None,
    }
    audit = plan.get("storyline_audit") or {}
    audit.update({"status": "selected_pending_enrichment", "selected_id": storyline_id})
    plan["storyline_audit"] = audit
    plan["mbb_plan_sha256"] = sha256_json({key: value for key, value in plan.items() if key not in {"mbb_plan_sha256", "created_at", "updated_at"}})
    assert_v2("mbb_plan", plan)
    write_mbb_plan(root, plan)
    receipt_payload = _selection_receipt_payload(plan, packages)
    receipt = {
        **receipt_payload,
        "integrity": sign_runtime_payload("mbb_storyline_selection.v1", receipt_payload),
    }
    assert_v2("mbb_selection_receipt", receipt)
    write_json(root / MBB_SELECTION_RECEIPT_PATH, receipt)
    return plan


def seal_mbb_plan(root: Path) -> dict[str, Any]:
    packages = load_page_packages(root, expected_run_id=str(read_json(root / "request.json").get("run_id") or root.name))
    plan = load_mbb_plan(root, packages=packages, expected_run_id=str(packages[0].get("run_id") or ""), require_approved=False)
    selection = plan.get("selection") or {}
    if str(selection.get("status") or "") == "approved":
        return plan
    if str(selection.get("status") or "") != "selected_pending_enrichment" or not plan.get("pages") or plan.get("scr") is None:
        raise ContractError("selected MBB plan is not ready to seal")
    selection["status"] = "approved"
    selection["sealed_at"] = utc_now()
    plan["selection"] = selection
    audit = plan.get("storyline_audit") or {}
    audit["status"] = "approved"
    plan["storyline_audit"] = audit
    plan["mbb_plan_sha256"] = sha256_json(
        {key: value for key, value in plan.items() if key not in {"mbb_plan_sha256", "created_at", "updated_at"}}
    )
    assert_v2("mbb_plan", plan)
    write_mbb_plan(root, plan)
    _load_mbb_selection_receipt(root, plan, packages=packages)
    seal_payload = {
        "schema_version": "deck_mbb_runtime_seal.v1",
        "run_id": str(plan.get("run_id") or ""),
        "selected_storyline_id": str(selection.get("selected_storyline_id") or ""),
        "mbb_plan_sha256": str(plan.get("mbb_plan_sha256") or ""),
        "selection_receipt_sha256": sha256_file(root / MBB_SELECTION_RECEIPT_PATH),
        "page_package_sha256": {
            str(package.get("page_id") or ""): sha256_json(package)
            for package in packages
        },
        "sealed_at": str(selection.get("sealed_at") or ""),
    }
    seal = {
        **seal_payload,
        "integrity": sign_runtime_payload("mbb_plan_seal.v1", seal_payload),
    }
    assert_v2("mbb_runtime_seal", seal)
    write_json(root / MBB_SEAL_PATH, seal)
    return load_mbb_plan(root, packages=packages, expected_run_id=str(packages[0].get("run_id") or ""), require_approved=True)


def write_mbb_plan(root: Path, plan: dict[str, Any]) -> Path:
    assert_current_mbb_artifact(root, plan)
    assert_v2("mbb_plan", plan)
    selection_status = str((plan.get("selection") or {}).get("status") or "")
    selection_receipt_path = root / MBB_SELECTION_RECEIPT_PATH
    user_decision_receipt_path = root / MBB_USER_DECISION_RECEIPT_PATH
    if selection_status == "pending_user_decision":
        selection_receipt_path.unlink(missing_ok=True)
        user_decision_receipt_path.unlink(missing_ok=True)
    elif selection_receipt_path.exists():
        try:
            _load_mbb_selection_receipt(root, plan)
        except (ContractError, OSError, json.JSONDecodeError):
            selection_receipt_path.unlink(missing_ok=True)
    seal_path = root / MBB_SEAL_PATH
    if seal_path.exists():
        try:
            seal = read_json(seal_path)
        except (ContractError, OSError, json.JSONDecodeError):
            seal_path.unlink(missing_ok=True)
        else:
            if selection_status != "approved" or str(seal.get("mbb_plan_sha256") or "") != str(plan.get("mbb_plan_sha256") or ""):
                seal_path.unlink(missing_ok=True)
    path = root / MBB_PLAN_PATH
    return write_json(path, plan)


def write_content_lock(
    root: Path,
    package: dict[str, Any],
    page_plan: dict[str, Any],
    *,
    mbb_plan_sha256: str,
) -> Path:
    assert_current_mbb_artifact(root, page_plan)
    lock = build_content_lock(package, page_plan, mbb_plan_sha256=mbb_plan_sha256)
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
    assert_current_mbb_artifact(root, lock)
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
    validate_visibility_policy(lock.get("visibility_policy") or {}, page_id=page_id)
    return lock


__all__ = [
    "LOCKS_DIR",
    "MBB_DIR",
    "MBB_PLAN_PATH",
    "MBB_SELECTION_RECEIPT_PATH",
    "MBB_USER_DECISION_RECEIPT_PATH",
    "build_content_lock",
    "build_mbb_page",
    "build_mbb_plan",
    "enrich_selected_mbb_plan",
    "load_content_lock",
    "load_mbb_plan",
    "load_page_packages",
    "seal_mbb_plan",
    "select_mbb_storyline",
    "record_mbb_user_decision",
    "write_content_lock",
    "write_mbb_plan",
]
