from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from production.page_package import strip_internal

from .contracts import ContractError, assert_valid, sha256_json, utc_now, write_json

PACKAGES_DIR = "page_packages"
LOCKS_DIR = Path("high_density_build/content_locks")


def load_page_packages(root: Path) -> list[dict[str, Any]]:
    directory = root / PACKAGES_DIR
    packages: list[dict[str, Any]] = []
    if not directory.is_dir():
        return packages
    for path in sorted(directory.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            import json

            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict) and value.get("page_id"):
            packages.append(value)
    return sorted(packages, key=lambda item: int(item.get("order") or 0))


def _assert_safe_page_id(page_id: str) -> None:
    raw = str(page_id or "")
    if not raw or "/" in raw or "\\" in raw or Path(raw).is_absolute() or ".." in Path(raw).parts:
        raise ContractError(f"page_id must be a safe run-relative identifier: {raw}")


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


def _density_analysis(customer_visible: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    text = _flatten_customer_visible(customer_visible)
    body_blocks = customer_visible.get("body_blocks") or []
    callouts = customer_visible.get("callouts") or []
    citations = package.get("citations") or []
    numeric_tokens = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?%?", text)
    table_blocks = sum(
        1
        for block in body_blocks
        if isinstance(block, dict) and str(block.get("type") or "").lower() in {"table", "matrix", "comparison"}
    )
    score = min(100, 20 + len(body_blocks) * 8 + len(callouts) * 10 + len(numeric_tokens) * 3 + table_blocks * 12)
    if score >= 70:
        band = "high"
    elif score >= 45:
        band = "medium"
    else:
        band = "low"
    visual_spec = package.get("visual_spec") or {}
    return {
        "content_density_score": score,
        "density_band": band,
        "text_characters": len(text),
        "body_block_count": len(body_blocks),
        "callout_count": len(callouts),
        "numeric_token_count": len(numeric_tokens),
        "table_block_count": table_blocks,
        "citation_count": len(citations),
        "page_role": str(visual_spec.get("page_type") or visual_spec.get("role") or "dense_narrative"),
    }


def _derived_claims(package: dict[str, Any], evidence: list[Any]) -> list[dict[str, Any]]:
    claim_ids = package.get("claim_bindings") or []
    evidence_ids = [item.get("evidence_id") if isinstance(item, dict) else str(item) for item in evidence]
    return [
        {
            "claim_id": str(claim_id),
            "evidence_refs": [value for value in evidence_ids if value],
            "factual_value_added": False,
        }
        for claim_id in claim_ids
    ]


def _structure_decisions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = [
        {"decision": "preserve_locked_text", "reason": "ImageGen output is layout evidence only"},
        {"decision": "use_native_text_for_p0_p1", "reason": "editable output requirement"},
    ]
    if analysis["table_block_count"]:
        decisions.append({"decision": "reserve_table_grid", "reason": "table-like block detected"})
    if analysis["numeric_token_count"]:
        decisions.append({"decision": "prioritize_numeric_labels", "reason": "numeric content detected"})
    if analysis["density_band"] == "high":
        decisions.append({"decision": "use_multi_region_layout", "reason": "high density score"})
    return decisions


def build_content_lock(package: dict[str, Any]) -> dict[str, Any]:
    page_id = str(package.get("page_id") or "")
    run_id = str(package.get("run_id") or "")
    if not page_id or not run_id:
        raise ContractError("page package requires run_id and page_id")
    _assert_safe_page_id(page_id)
    if package.get("status") != "ready_for_build":
        raise ContractError(f"page package {page_id} is not buildable: {package.get('status')}")
    safe_package = strip_internal(package)
    customer_visible = copy.deepcopy(safe_package.get("customer_visible") or {})
    evidence = copy.deepcopy(safe_package.get("evidence_bindings") or [])
    analysis = _density_analysis(customer_visible, safe_package)
    lock = {
        "schema_version": "deck_content_lock.v1",
        "run_id": run_id,
        "page_id": page_id,
        "page_package_ref": f"{PACKAGES_DIR}/{page_id}.json",
        "page_package_sha256": sha256_json(package),
        "source_fingerprint": str(package.get("source_fingerprint") or sha256_json(customer_visible)),
        "customer_visible": customer_visible,
        "speaker_notes": str(package.get("speaker_notes") or ""),
        "asset_bindings": copy.deepcopy(safe_package.get("asset_bindings") or []),
        "evidence_bindings": evidence,
        "enrichment": {
            "framework": "nbb",
            "version": "v1",
            "analysis": analysis,
            "derived_claims": _derived_claims(safe_package, evidence),
            "structure_decisions": _structure_decisions(analysis),
        },
        "created_at": utc_now(),
    }
    if len(lock["source_fingerprint"]) != 64:
        lock["source_fingerprint"] = sha256_json({"page_id": page_id, "source": lock["source_fingerprint"]})
    lock["content_lock_sha256"] = sha256_json(
        {
            key: value
            for key, value in lock.items()
            if key not in {"content_lock_sha256", "created_at"}
        }
    )
    assert_valid("content_lock", lock)
    return lock


def write_content_lock(root: Path, package: dict[str, Any]) -> Path:
    lock = build_content_lock(package)
    path = root / LOCKS_DIR / f"{package['page_id']}.json"
    write_json(path, lock)
    return path


def load_content_lock(root: Path, page_id: str) -> dict[str, Any]:
    from .contracts import read_json

    path = root / LOCKS_DIR / f"{page_id}.json"
    lock = read_json(path)
    assert_valid("content_lock", lock)
    return lock


__all__ = ["LOCKS_DIR", "build_content_lock", "load_content_lock", "load_page_packages", "write_content_lock"]
