"""Project approved Page Packages into locks without a second storyline interview.

Only existing customer-visible text is projected. Narrative metadata supplies
lineage, never additional facts or unapproved copy.
"""

from __future__ import annotations
import copy
from pathlib import Path
from typing import Any
from native_pptx.contracts import ContractError, assert_v2, read_json, sha256_json, utc_now
from high_density.visibility import build_visibility_policy
from production.page_package import strip_internal


def _text_refs(value: Any, path: str = "customer_visible") -> list[dict[str, Any]]:
    if isinstance(value, str):
        return (
            [
                {
                    "ref": "content_lock." + path,
                    "priority": "P0" if path == "customer_visible.title" else "P1",
                    "required": True,
                    "value": value,
                }
            ]
            if value.strip()
            else []
        )
    if isinstance(value, list):
        return [ref for i, item in enumerate(value) for ref in _text_refs(item, f"{path}.{i}")]
    if isinstance(value, dict):
        # Block metadata is not client copy. Preserve all explicitly visible
        # textual fields, including labels, caveats, and source annotations.
        return [
            ref
            for key, item in value.items()
            if key not in {"id", "block_id", "type", "kind", "origin", "evidence_refs", "claim_refs", "asset_ref"}
            for ref in _text_refs(item, f"{path}.{key}")
        ]
    return []


def build_native_content_lock(package: dict[str, Any], narrative: dict[str, Any] | None = None) -> dict[str, Any]:
    if package.get("status") not in {"ready_for_build", "ready"}:
        raise ContractError("native content requires an approved page package")
    safe = strip_internal(package)
    page_id = str(package["page_id"])
    visible = copy.deepcopy(safe.get("customer_visible") or {})
    refs = _text_refs(visible)
    if not refs:
        raise ContractError(f"page {page_id} has no approved visible text")
    lineage = {"page_package_sha256": sha256_json(package), "source": "approved_page_package"}
    if narrative is not None:
        lineage.update(narrative_ref="narrative_plan.json", narrative_sha256=sha256_json(narrative))
    evidence = copy.deepcopy(safe.get("evidence_bindings") or [])
    evidence = [item if isinstance(item, dict) else {"evidence_id": str(item)} for item in evidence]
    component = f"{page_id}.content"
    language = str((safe.get("build_requirements") or {}).get("target_language") or "zh-CN")
    lock = {
        "schema_version": "deck_content_lock.v2",
        "run_id": str(package["run_id"]),
        "page_id": page_id,
        "page_package_ref": f"page_packages/{page_id}.json",
        "page_package_sha256": sha256_json(package),
        "source_fingerprint": sha256_json({"package": package, "narrative": narrative}),
        "customer_visible": visible,
        "speaker_notes": str(safe.get("speaker_notes") or ""),
        "asset_bindings": copy.deepcopy(safe.get("asset_bindings") or []),
        "evidence_bindings": evidence,
        "enrichment": {
            "framework": "native_narrative",
            "version": "native_narrative/1",
            "analysis": {"page_role": str((safe.get("visual_spec") or {}).get("page_role") or "content")},
            "component_plan": [{"component_id": component}],
            "claim_bindings": copy.deepcopy(safe.get("claim_bindings") or []),
        },
        "required_component_ids": [component],
        "required_text_refs": refs,
        "density_target": {
            "score": 0,
            "band": "low",
            "information_regions": max(1, len(visible.get("body_blocks") or [])),
            "component_count": 1,
            "evidence_count": len(evidence),
            "numeric_count": 0,
        },
        "target_language": language,
        "effective_language": language,
        "visibility_policy": build_visibility_policy(safe, page_id=page_id),
        "lineage": lineage,
        "created_at": utc_now(),
    }
    lock["content_lock_sha256"] = sha256_json({k: v for k, v in lock.items() if k != "created_at"})
    assert_v2("content_lock", lock)
    return lock


def ensure_native_content(root: Path, packages: list[dict[str, Any]]) -> None:
    from high_density.content import load_content_lock

    narrative_path = root / "narrative_plan.json"
    narrative = read_json(narrative_path) if narrative_path.exists() else None
    if narrative is not None and narrative.get("run_id") not in {None, "", root.name}:
        raise ContractError("narrative belongs to a different run")
    pending = {}
    targets = {}
    for package in packages:
        page_id = str(package["page_id"])
        path = root / "high_density_build/content_locks" / f"{page_id}.content_lock.json"
        legacy = path.with_name(f"{page_id}.json")
        if path.exists() or legacy.exists():
            current = load_content_lock(root, page_id, expected_run_id=str(package["run_id"]))
            # Existing HD runs retain their approved MBB lock; only native
            # projections regenerate from changed approved inputs.
            if current.get("enrichment", {}).get("framework") != "native_narrative":
                if current["page_package_sha256"] != sha256_json(package):
                    raise ContractError(f"approved content lock is stale on {page_id}")
                continue
            desired = build_native_content_lock(package, narrative)
            if current["content_lock_sha256"] == desired["content_lock_sha256"]:
                continue
        else:
            desired = build_native_content_lock(package, narrative)
        import json

        pending[f"{page_id}_lock"] = json.dumps(desired, ensure_ascii=False, indent=2) + "\n"
        pending[f"{page_id}_mirror"] = pending[f"{page_id}_lock"]
        pending[f"{page_id}_package"] = (root / f"page_packages/{page_id}.json").read_bytes()
        targets.update({f"{page_id}_lock": path, f"{page_id}_mirror": legacy, f"{page_id}_package": root / f"page_packages/{page_id}.json"})
    if not pending:
        return
    if narrative is not None:
        pending["narrative"] = narrative_path.read_bytes()
        targets["narrative"] = narrative_path
    from workflow.actions import stage_action_result, commit_action_result, read_current_revision

    fingerprint = sha256_json({"packages": packages, "narrative": narrative})
    parent_revision = read_current_revision(root).get("revision_id", "")
    action_identity = sha256_json({"parent_revision": parent_revision, "inputs": fingerprint})
    envelope = {
        "schema_version": "deck_stage_action.v1",
        "action_id": "native_content_" + action_identity[:32],
        "task_id": "native_content",
        "scope_pages": [str(p["page_id"]) for p in packages],
        "permission": "runtime",
        "input_fingerprint": fingerprint,
    }
    stage_action_result(root, envelope, pending)
    commit_action_result(
        root,
        envelope,
        current_input_fingerprint=lambda: sha256_json(
            {
                "packages": [read_json(root / f"page_packages/{p['page_id']}.json") for p in packages],
                "narrative": read_json(narrative_path) if narrative_path.exists() else None,
            }
        ),
        targets=targets,
        expected_revision=parent_revision,
    )
