"""Project approved Page Packages into locks without a second storyline interview.

Only existing customer-visible text is projected. Narrative metadata supplies
lineage, never additional facts or unapproved copy.
"""

from __future__ import annotations
import copy
import re
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


def narrative_page_projection(narrative: dict[str, Any] | None, page_id: str) -> Any:
    """Scope recognized page collections; preserve unknown/global dependencies.

    Administrative timestamps/revision counters remain in the global build and
    semantic fingerprints. All other top-level fields are shared dependencies.
    """
    if narrative is None:
        return None
    keys = [key for key in ('pages', 'beats') if key in narrative]
    if len(keys) != 1 or not isinstance(narrative[keys[0]], list):
        return {'version': 1, 'conservative_full_narrative': narrative}
    key = keys[0]
    entries = narrative[key]
    ids = [str(i.get('page_id') or i.get('beat_id') or '') if isinstance(i, dict) else '' for i in entries]
    if not all(ids) or len(set(ids)) != len(ids) or page_id not in ids:
        return {'version': 1, 'conservative_full_narrative': narrative}
    global_fields = {k: v for k, v in narrative.items() if k not in {key, 'revision', 'created_at', 'updated_at'}}
    return {'version': 1, 'global': global_fields, 'page': entries[ids.index(page_id)]}


def _compatible_legacy_narrative(root: Path, current: dict, package: dict, narrative: dict | None) -> bool:
    """Keep an already issued lock byte-for-byte when its exact historical input
    proves that only another page changed. Never infer missing old dependencies.
    """
    from workflow.actions import read_current_revision
    from native_pptx.contracts import sha256_file
    lineage = current.get('lineage', {})
    old_hash = lineage.get('narrative_sha256')
    if current.get('page_package_sha256') != sha256_json(package):
        return False
    if not old_hash:
        return (narrative is None and not lineage.get('narrative_projection_version')
                and current.get('source_fingerprint') == sha256_json({'package': package, 'narrative': None}))
    if narrative is not None and sha256_json(narrative) == old_hash:
        return True
    revision = read_current_revision(root).get('revision_id', '')
    seen = set()
    while revision and revision not in seen:
        if not isinstance(revision, str) or not re.fullmatch(r'[a-f0-9]{32}', revision):
            return False
        seen.add(revision)
        folder = root / 'build/revisions' / revision
        manifest_path = folder / 'revision_manifest.json'
        path = folder / 'narrative_plan.json'
        if folder.is_symlink() or manifest_path.is_symlink() or path.is_symlink() or not manifest_path.is_file():
            return False
        manifest = read_json(manifest_path)
        if path.is_file() and manifest.get('files', {}).get('narrative_plan.json') == sha256_file(path):
            old = read_json(path)
            if sha256_json(old) == old_hash:
                return narrative_page_projection(old, package['page_id']) == narrative_page_projection(narrative, package['page_id'])
        revision = manifest.get('parent_revision_id', '')
    return False


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
    projection = narrative_page_projection(narrative, page_id)
    if narrative is not None:
        lineage.update(narrative_ref="narrative_plan.json", narrative_page_projection_sha256=sha256_json(projection), narrative_projection_version=1)
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
        "source_fingerprint": sha256_json({"package": package, "narrative_page_projection": projection}),
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
            if _compatible_legacy_narrative(root, current, package, narrative):
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
