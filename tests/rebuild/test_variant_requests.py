"""T03 slice 5: sequential live/read variant sub-requests (CONTRACTS §11.7, AC-M02).

Two optimised versions are two sequential bounded sub-requests that share one
fixed Narrative Ref, each with its own Plan/Page/output and its own immutable
versioned export. Document.current stays single, no third version appears, and
the first export's bytes stay exactly what they were.
"""
import json

import pytest

from deck_master import collaboration, content_production, exports, models, service, variant_requests
from deck_master.models import ModelError
from deck_master.store import Store

from test_content_preproduction_review import (
    _argument_narrative, _deck, _instruction, _page, _plan_input, _scope,
    _source_link, _stored)


def _grant_variants(project, store, *, declared=("live", "read"), operation_id="op-variants"):
    return collaboration.grant(
        project, input={"mode": "delegate", "actions": ["content.compose"],
                        "delegated_topics": ["direction"],
                        "max_external_calls": 0, "max_candidate_count": 0,
                        "scope": _scope(),
                        "constraints": {"variant_ids": list(declared),
                                        "note": "两套优化版本（live/read）"},
                        "instruction_evidence": _instruction(store, operation_id)},
        base_revision=store.load_document()["revision_id"], operation_id=operation_id)


def _declared_group(store, document) -> str:
    """The group a caller reads back: the current variant's group, else the
    declaration's Runtime-derived group."""
    carried = ((document.get("collaboration") or {}).get("request") or {}).get("variant") or {}
    if carried.get("group_id"):
        return carried["group_id"]
    declaration = variant_requests.declaring_authorization(store, document)
    if declaration is None:
        return "vg-undeclared"
    return variant_requests.variant_group_id(declaration[0], declaration[2])


def _start_variant(project, store, *, variant_id, replace_request_id, requested=("live", "read"),
                   group_id=None, label=None, operation_id=None):
    document = store.load_document()
    group = group_id if group_id is not None else _declared_group(store, document)
    return collaboration.start_request(
        project, input={"intent": "full_deck", "content_intent": None,
                        "instruction_evidence": _instruction(store, f"variant-{variant_id}"),
                        "scope": _scope(),
                        "variant": {"group_id": group, "variant_id": variant_id,
                                    "label": label or f"{variant_id} 版",
                                    "requested_variant_ids": list(requested)},
                        "replace_request_id": replace_request_id},
        base_revision=store.load_document()["revision_id"],
        operation_id=operation_id or f"op-variant-{variant_id}")


def _produce_variant(project, store, *, text):
    """Adopt the shared Narrative, bind a plan and write the variant's copy."""
    document = store.load_document()
    proposal_ref = document.get("narrative")
    if proposal_ref is None:
        task = content_production.open_phase_task(store, document, operation_id="arg",
                                                  phase="argument")
        service.accept_result(
            project, task_id=task["task_id"], operation_id=task["operation_id"],
            produced_against=task["produced_against"],
            result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                            "variant": "narrative", "task_id": task["task_id"],
                            "operation_id": task["operation_id"],
                            "produced_against": task["produced_against"],
                            "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                            "payload": {"narrative": _argument_narrative(document["project_id"])},
                            "usage_events": []})
        store = Store(project)
        document = store.load_document()
        latest = store.read_object_json(document["tasks"][-1])
        proposal_ref = latest["result_refs"][0]
        decision = collaboration.record_decision(
            project, input={"topic": "direction", "disposition": "accepted",
                            "authority_mode": "direct_user", "value": {"selected": "两维度记录"},
                            "scope": _scope(layers=["narrative", "plan", "page_copy"]),
                            "instruction_evidence": _instruction(store, "direction"),
                            "subject_refs": [{"artifact_kind": "narrative",
                                              "artifact_ref": proposal_ref,
                                              "projection": "direction"}]},
            base_revision=store.load_document()["revision_id"], operation_id="op-direction")
        content_production.adopt_proposal(
            project, input={"proposal_ref": proposal_ref,
                            "decision_ref": decision["decision_ref"],
                            "write_scope": _scope(layers=["narrative"])},
            base_revision=store.load_document()["revision_id"], operation_id="op-adopt")
    store = Store(project)
    document = store.load_document()
    task = content_production.open_phase_task(store, document,
                                              operation_id=f"pc-{abs(hash(text)) % 10**8}",
                                              phase="page_copy")
    document = store.load_document()
    page = _page(store, document, "p1", notes=f"{text} 的口播。")
    page["customer_visible"] = {**page["customer_visible"],
                                "body_blocks": [{"id": "b1", "type": "paragraph", "text": text}]}
    plan_input = {**_plan_input(document, ["p1"], [_source_link(store, document, "L1")]),
                  "speech_policy": {"mode": "cues", "source": "provided",
                                    "output": "pptx_notes"}}
    return service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                        "variant": "page_copy", "task_id": task["task_id"],
                        "operation_id": task["operation_id"],
                        "produced_against": task["produced_against"],
                        "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                        "payload": {"pages": [page], "page_order": ["p1"],
                                    "plan_input": plan_input},
                        "usage_events": []})


def _export(project, store, purpose="review"):
    return exports.create(project, purpose=purpose)


def test_two_variants_are_sequential_shared_and_single_current(tmp_path):
    project, store = _deck(tmp_path)  # request 1 is already open
    _grant_variants(project, store)
    store = Store(project)
    document = store.load_document()
    current = document["collaboration"]["request"]["request_id"]
    first = _start_variant(project, store, variant_id="live", replace_request_id=current)
    assert first["status"] == "accepted"
    _produce_variant(project, store, text="现场版正文：按两维度记录并说明下一动作。")
    store = Store(project)
    narrative_after_first = store.load_document()["narrative"]
    export_one = _export(project, store)
    manifest_one = export_one["manifest"]
    record_one = json.loads(
        (store.project_root / ".deckmaster" / "workbench" / "exports"
         / export_one["export_id"] / "export-record.json").read_text("utf-8"))

    # Second, sequential sub-request: replace the current request, same Narrative.
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    second = _start_variant(project, store, variant_id="read", replace_request_id=current)
    assert second["status"] == "accepted"
    assert second["request_id"] != first["request_id"]
    assert store.load_document()["narrative"] == narrative_after_first
    _produce_variant(project, store, text="阅读版正文：同样两维度，独立阅读也能定位限定。")
    store = Store(project)
    export_two = _export(project, store)
    manifest_two = export_two["manifest"]

    # Each version has its own revision, Plan and Page set, and its own label.
    assert manifest_one["revision_id"] != manifest_two["revision_id"]
    assert manifest_one["variant"]["variant_id"] == "live"
    assert manifest_two["variant"]["variant_id"] == "read"
    assert manifest_one["variant"]["group_id"] == manifest_two["variant"]["group_id"]
    assert manifest_one["variant"]["narrative_ref"] == manifest_two["variant"]["narrative_ref"]
    assert manifest_one["variant"]["plan_ref"] != manifest_two["variant"]["plan_ref"]
    # Document.current is still one pointer set: one plan, one page set.
    document = store.load_document()
    assert document["content_plan"] == manifest_two["variant"]["plan_ref"]
    assert [entry["page_id"] for entry in document["pages"]] == ["p1"]
    # The first version is addressed by its own revision and export, unchanged.
    assert manifest_one["files"] == record_one["manifest"]["files"]
    frozen = store.project_root / ".deckmaster" / "workbench" / "exports" / export_one["export_id"]
    assert json.loads((frozen / "export-record.json").read_text("utf-8")) == record_one
    assert manifest_one["files"], "the first export must have real files"


def test_variant_request_refusals(tmp_path):
    project, store = _deck(tmp_path)
    _grant_variants(project, store)
    store = Store(project)
    document = store.load_document()
    declared = variant_requests.declaring_authorization(store, document)
    group_id = variant_requests.variant_group_id(declared[0], declared[2])
    current = document["collaboration"]["request"]["request_id"]
    # An undeclared variant id is refused.
    with pytest.raises(ModelError, match="every variant id must be in this set|does not declare"):
        _start_variant(project, store, variant_id="slide", replace_request_id=current,
                       requested=("live", "slide"))
    # A different group id cannot open a second group for the same declaration.
    with pytest.raises(ModelError, match="derived by the Runtime"):
        _start_variant(project, store, variant_id="live", replace_request_id=current,
                       group_id="vg-invented")
    # A variant id outside the requested list is refused.
    with pytest.raises(ModelError, match="must name a variant id"):
        _start_variant(project, store, variant_id="read", replace_request_id=current,
                       requested=("live",))
    # Three versions are not part of this contract.
    with pytest.raises(ModelError, match="at most 2"):
        _start_variant(project, store, variant_id="live", replace_request_id=current,
                       requested=("live", "read", "extra"))
    # A sub-request must be sequential: it replaces the current open request.
    with pytest.raises(ModelError, match="sequential"):
        _start_variant(project, store, variant_id="live", replace_request_id=None)


def test_a_variant_cannot_be_produced_twice(tmp_path):
    project, store = _deck(tmp_path)
    _grant_variants(project, store)
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    _start_variant(project, store, variant_id="live", replace_request_id=current)
    _produce_variant(project, store, text="现场版正文。")
    store = Store(project)
    _export(project, store)
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    with pytest.raises(ModelError, match="already fixed in this group"):
        _start_variant(project, store, variant_id="live", replace_request_id=current,
                       operation_id="op-variant-live-again")
    # The replacement must be the other declared variant, not a duplicate label.
    _start_variant(project, store, variant_id="read", replace_request_id=current,
                   label="现场版", operation_id="op-variant-read-label")
    store = Store(project)
    document = store.load_document()
    assert document["collaboration"]["request"]["variant"]["variant_id"] == "read"
    assert document["collaboration"]["request"]["variant"]["label"] == "现场版"


def test_declaring_authorization_is_required(tmp_path):
    project, store = _deck(tmp_path)
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    with pytest.raises(ModelError, match="decision_needed"):
        _start_variant(project, store, variant_id="live", replace_request_id=current)


def test_a_new_narrative_breaks_the_shared_basis(tmp_path):
    project, store = _deck(tmp_path)
    _grant_variants(project, store)
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    _start_variant(project, store, variant_id="live", replace_request_id=current)
    _produce_variant(project, store, text="现场版正文。")
    store = Store(project)
    _export(project, store)
    # Adopting a different argument changes the shared basis for the group.
    store = Store(project)
    document = store.load_document()
    other = store.put_json_object({**_argument_narrative(document["project_id"]),
                                   "narrative_id": "nar-other"})
    region = dict(document["collaboration"])
    request = dict(region["request"])
    region["request"] = request
    bumped = models.bump_revision(
        document, {"operation_id": "swap-narrative", "kind": "collaboration_update",
                   "description": "fixture: replace the narrative", "read_set": []})
    bumped["narrative"] = other
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="swap-narrative")
    store = Store(project)
    current = store.load_document()["collaboration"]["request"]["request_id"]
    with pytest.raises(ModelError, match="reuse the same Narrative Ref"):
        _start_variant(project, store, variant_id="read", replace_request_id=current)
