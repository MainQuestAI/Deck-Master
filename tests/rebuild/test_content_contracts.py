"""T02 slice 2: narrative.v1, content_plan v2, compose_result.v2, review.v2,
page content_mapping and export-manifest variant contracts (CONTRACTS
§11.1–11.3, §11.5–11.7) with schema_version dispatch that keeps old objects
readable."""
import hashlib

import pytest

from deck_master import models
from deck_master.models import ModelError


def _ref(seed: str) -> dict:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}


def _source_link() -> dict:
    extract = _ref("extract")
    return {"source_id": "s1", "source_version": {"original_sha256": None, "extract": extract},
            "locator": "L1-L3"}


def _node(**over) -> dict:
    node = {"node_id": "n1", "role": "claim", "statement": "可接手的记录规则",
            "authority": "instruction", "source_links": [], "qualification_node_ids": [],
            "unresolved_issue_ids": []}
    node.update(over)
    return node


def _narrative(**over) -> dict:
    narrative = {
        "schema_version": "narrative.v1", "narrative_id": "nar-1", "version": 1,
        "project_id": "proj", "origin": "host_composed", "maturity": "argument",
        "input_basis": [],
        "communication_job": {
            "mode": "train", "audience_fact_key": "task.audience",
            "audience_question": "如何记录未知", "desired_outcome": "能填写可接手记录",
            "observable_success": "新情境题答对", "use_mode": "live", "primary_use": "live",
        },
        "central_node_id": "n1",
        "nodes": [_node()],
        "edges": [],
        "issues": [],
        "alternatives": [],
        "previous_ref": None,
    }
    narrative.update(over)
    return narrative


def _plan_input(**over) -> dict:
    data = {
        "schema_version": "content_plan_input.v2",
        "chapters": [{"chapter_id": "c1", "title": "第一章", "page_ids": ["p1"]}],
        "page_order": ["p1"],
        "page_roles": [{
            "page_id": "p1", "role": "目标", "audience_question": "为什么练这个",
            "intended_takeaway": "知道可接手定义", "narrative_node_ids": ["n1"],
            "source_links": [_source_link()], "required_qualifications": [],
            "content_profile": "simple", "density_rationale": "单条目标",
            "timing_seconds": 30, "transition_to_next": None,
        }],
        "page_budget": {"exact": None, "target": 6, "max": 8},
        "time_budget": {"total_seconds": 480, "speaking_seconds": 380,
                        "interaction_seconds": 100, "constraint": "hard"},
        "speech_policy": {"mode": "verbatim", "source": "provided", "output": "separate_script"},
        "issues": [],
        "tradeoff_issue_ids": [],
    }
    data.update(over)
    return data


def _plan(**over) -> dict:
    plan = {
        "schema_version": "content_plan.v2", "plan_id": "plan-1", "version": 1,
        "project_id": "proj", "task_id": None, "origin": "host_composed",
        "basis": {"revision_id": "rev-1", "input_digest": hashlib.sha256(b"d").hexdigest()},
        "previous_ref": None, "mode": "planned", "narrative_ref": _ref("narrative"),
        "imported_manuscript": None, "input": _plan_input(), "page_links": [],
    }
    plan.update(over)
    return plan


def _compose(variant: str, payload: dict, **over) -> dict:
    result = {
        "schema_version": "compose_result.v2", "kind": "compose", "variant": variant,
        "task_id": "task-1", "operation_id": "op-1",
        "produced_against": hashlib.sha256(b"basis").hexdigest(),
        "eligibility_digest": hashlib.sha256(b"elig").hexdigest(),
        "payload": payload, "usage_events": [],
    }
    result.update(over)
    return result


def _review_v2(**over) -> dict:
    review = {
        "schema_version": "deck_review.v2", "review_id": "rv-1", "kind": "argument",
        "status": "pass", "review_stage": "preproduction",
        "subjects": [_ref("narrative")], "dependencies": [],
        "reviewer": {"type": "independent_host", "id": "reviewer-1", "execution_ref": None,
                     "independence_confirmed": True, "identity_receipt": None,
                     "evidence_ref": _ref("receipt"), "assurance": "host_attested"},
        "observations": ["核对论证与证据边界"], "findings": [],
        "created_at": "2026-10-12T08:00:00Z", "replaces": None,
    }
    review.update(over)
    return review


# ---------------------------------------------------------------------------
# Registration and version dispatch


def test_slice2_contracts_are_registered():
    for kind in ("narrative", "content_plan_input_v2", "content_plan_v2",
                 "compose_result_v2", "review_v2"):
        assert kind in models.SCHEMA_FILES, kind


def test_review_v2_dispatches_by_schema_version():
    models.validate_review_semantics(_review_v2())
    v1 = {"schema_version": "deck_review.v1", "review_id": "rv-1", "kind": "content",
          "status": "pass", "subjects": [_ref("page")],
          "dependencies": [{"kind": "content", "identity": "page:p1",
                            "sha256": hashlib.sha256(b"p").hexdigest()}],
          "reviewer": {"type": "host_self", "id": "h1", "execution_ref": None,
                       "independence_confirmed": False},
          "observations": ["ok"], "findings": [], "created_at": "2026-10-12T08:00:00Z",
          "replaces": None}
    models.validate_review_semantics(v1)  # legacy record still readable


def test_review_v2_assurance_floors():
    bad = _review_v2()
    bad["reviewer"] = {**bad["reviewer"], "type": "human_external", "assurance": "host_attested"}
    with pytest.raises(ModelError, match="assurance"):
        models.validate_review_semantics(bad)
    good = _review_v2()
    good["reviewer"] = {**good["reviewer"], "type": "human_external", "assurance": "verified_user"}
    models.validate_review_semantics(good)


def test_content_plan_v2_dispatches_through_plain_kind():
    models.validate_schema("content_plan", _plan())  # routes to content_plan.v2
    models.validate_content_plan_semantics(_plan())


# ---------------------------------------------------------------------------
# Narrative


def test_argument_narrative_requires_existing_central_node():
    with pytest.raises(ModelError, match="central node"):
        models.validate_narrative_semantics(_narrative(central_node_id=None))
    with pytest.raises(ModelError, match="central node"):
        models.validate_narrative_semantics(_narrative(central_node_id="missing"))


def test_framing_narrative_may_have_no_nodes():
    models.validate_narrative_semantics(_narrative(
        maturity="framing", central_node_id=None, nodes=[], edges=[]))


def test_narrative_reference_integrity():
    with pytest.raises(ModelError, match="unknown node ids"):
        models.validate_narrative_semantics(_narrative(edges=[
            {"from_node_id": "n1", "to_node_id": "n9", "relation": "supports"}]))
    with pytest.raises(ModelError, match="unknown node ids"):
        models.validate_narrative_semantics(_narrative(nodes=[
            _node(), _node(node_id="n2", qualification_node_ids=["n9"])]))
    with pytest.raises(ModelError, match="unknown issue ids"):
        models.validate_narrative_semantics(_narrative(nodes=[
            _node(unresolved_issue_ids=["i9"])]))


def test_reported_fact_needs_source_or_blocker():
    fact = _node(authority="reported_fact")
    with pytest.raises(ModelError, match="source locator or an explicit blocker"):
        models.validate_narrative_semantics(_narrative(nodes=[fact]))
    with_blocker = _node(authority="reported_fact", unresolved_issue_ids=["i1"])
    models.validate_narrative_semantics(_narrative(
        nodes=[with_blocker],
        issues=[{"issue_id": "i1", "question": "来源缺失", "impact": "blocker",
                 "affected_node_ids": ["n1"], "resolution": "open", "resolution_ref": None}]))
    sourced = _node(authority="calculation", source_links=[_source_link()])
    models.validate_narrative_semantics(_narrative(nodes=[sourced]))
    # inference is allowed to be unsourced (it must not masquerade as a fact)
    models.validate_narrative_semantics(_narrative(nodes=[_node(authority="hypothesis")]))


# ---------------------------------------------------------------------------
# ContentPlan v2


def test_plan_roles_and_chapters_stay_inside_page_order():
    with pytest.raises(ModelError, match="outside page_order"):
        models.validate_content_plan_semantics(_plan(input=_plan_input(
            page_roles=[{**_plan_input()["page_roles"][0], "page_id": "p9"}])))
    with pytest.raises(ModelError, match="outside page_order"):
        models.validate_content_plan_semantics(_plan(input=_plan_input(
            chapters=[{"chapter_id": "c1", "title": "x", "page_ids": ["p9"]}])))


def test_exact_budget_above_max_is_rejected():
    with pytest.raises(ModelError, match="exceeds the hard max"):
        models.validate_content_plan_semantics(_plan(input=_plan_input(
            page_budget={"exact": 9, "target": 6, "max": 8})))


def test_bound_plan_must_link_every_page_exactly_once():
    with pytest.raises(ModelError, match="link every page_order page"):
        models.validate_content_plan_semantics(_plan(mode="bound", page_links=[]))
    models.validate_content_plan_semantics(_plan(mode="bound", page_links=[
        {"page_id": "p1", "page_ref": _ref("page"), "plan_role_page_id": "p1"}]))


def test_imported_mapping_requires_manuscript_evidence():
    with pytest.raises(ModelError, match="imported_mapping requires"):
        models.validate_content_plan_semantics(_plan(mode="imported_mapping", narrative_ref=None))
    models.validate_content_plan_semantics(_plan(mode="imported_mapping", narrative_ref=None,
        imported_manuscript={"source_ref": _ref("manuscript"),
                             "claimed_confirmation_evidence": {
                                 "kind": "approved_document", "assurance": "unverified",
                                 "source_ref": _ref("manuscript"), "source_locator": "file:deck.pptx",
                                 "actor_id": None, "transport_receipt_ref": None,
                                 "presentation_ref": None},
                             "preserve_mainline": True, "unresolved_mapping_items": []}))


def test_tradeoff_ids_must_exist_in_plan_issues():
    with pytest.raises(ModelError, match="unknown issue ids"):
        models.validate_content_plan_semantics(_plan(input=_plan_input(tradeoff_issue_ids=["i9"])))


# ---------------------------------------------------------------------------
# Compose v2


def test_compose_v2_variant_payloads():
    models.validate_compose_result_semantics(_compose("framing", {"narrative": {}}))
    models.validate_compose_result_semantics(_compose(
        "page_copy", {"pages": [{}], "page_order": ["p1"], "plan_input": {}}))
    with pytest.raises(ModelError):
        models.validate_compose_result_semantics(_compose("page_copy", {"pages": [{}]}))
    with pytest.raises(ModelError):
        models.validate_compose_result_semantics(_compose("speech", {"updates": []}))
    with pytest.raises(ModelError):
        models.validate_compose_result_semantics(_compose("unknown_variant", {}))
    with pytest.raises(ModelError):
        models.validate_compose_result_semantics(_compose("framing", {"narrative": {}, "pages": []}))


# ---------------------------------------------------------------------------
# Page content_mapping


def _page(**over) -> dict:
    page = {
        "schema_version": "deck_page_package.v2", "page_id": "p1",
        "customer_visible": {"title": "标题", "body_blocks": [{"id": "b1", "type": "paragraph", "text": "正文"}]},
        "speaker_notes": "第一段口播。第二段口播。",
        "visual_spec": {"intent": "培训", "reference_mode": "new_design"},
    }
    page.update(over)
    return page


def test_content_mapping_structural_rules():
    mapping = {
        "narrative_ref": _ref("narrative"), "plan_role_page_id": "p1",
        "visible_links": [
            {"element_ref": "atom:p1:title", "narrative_node_ids": ["n1"], "source_links": []},
            {"element_ref": "atom:p1:block:b1:text", "narrative_node_ids": ["n1"],
             "source_links": [_source_link()]},
        ],
        "speech_segments": [
            {"segment_id": "s1", "start_codepoint": 0, "end_codepoint": 6,
             "narrative_node_ids": ["n1"], "kind": "verbatim", "estimated_seconds": 3},
            {"segment_id": "s2", "start_codepoint": 6, "end_codepoint": 12,
             "narrative_node_ids": ["n1"], "kind": "verbatim", "estimated_seconds": 3},
        ],
    }
    models.validate_page_semantics(_page(content_mapping=mapping))
    duplicate = {**mapping, "visible_links": mapping["visible_links"] + [mapping["visible_links"][0]]}
    with pytest.raises(ModelError, match="exactly one mapping"):
        models.validate_page_semantics(_page(content_mapping=duplicate))
    overlap = {**mapping, "speech_segments": [
        {"segment_id": "s1", "start_codepoint": 0, "end_codepoint": 8,
         "narrative_node_ids": [], "kind": "cue", "estimated_seconds": None},
        {"segment_id": "s2", "start_codepoint": 6, "end_codepoint": 12,
         "narrative_node_ids": [], "kind": "cue", "estimated_seconds": None},
    ]}
    with pytest.raises(ModelError, match="overlap"):
        models.validate_page_semantics(_page(content_mapping=overlap))
    empty = {**mapping, "speech_segments": [
        {"segment_id": "s1", "start_codepoint": 5, "end_codepoint": 5,
         "narrative_node_ids": [], "kind": "cue", "estimated_seconds": None}]}
    with pytest.raises(ModelError, match="non-empty"):
        models.validate_page_semantics(_page(content_mapping=empty))


# ---------------------------------------------------------------------------
# Export manifest variant metadata


def test_export_manifest_variant_metadata():
    manifest = {
        "schema_version": "export_manifest.v1", "export_id": "export-00000000-0000-0000-0000-000000000000",
        "project_identity": hashlib.sha256(b"proj").hexdigest(),
        "revision_id": "rev-1", "purpose": "delivery",
        "files": [], "excluded": [], "metadata_policy": "sanitized_public_copy",
        "variant": {"group_id": "grp-1", "variant_id": "live", "label": "现场版",
                    "narrative_ref": _ref("narrative"), "plan_ref": None},
    }
    models.validate_schema("export_manifest", manifest)
    manifest["variant"] = {**manifest["variant"], "variant_id": "Live V2"}
    with pytest.raises(ModelError):
        models.validate_schema("export_manifest", manifest)
