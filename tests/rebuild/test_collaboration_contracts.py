"""T02 collaboration contracts: registration, writer boundary and record
semantics for the single collaboration region, decisions and authorizations
(content collaboration v1.2 CONTRACTS §2–§4). Schema completeness and semantic
quality are separate checks; these tests pin the structural half."""
import hashlib

import pytest

from deck_master import models
from deck_master import tasks as tasks_mod
from deck_master.models import ModelError, new_document


def _ref(seed: str) -> dict:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}


def _evidence(kind="host_attested_instruction", assurance="host_attested") -> dict:
    return {
        "kind": kind,
        "assurance": assurance,
        "source_ref": _ref("evidence-source"),
        "source_locator": "chat:msg-1",
        "actor_id": None,
        "transport_receipt_ref": None,
        "presentation_ref": None,
    }


def _scope(**over) -> dict:
    scope = {
        "subject": "pages",
        "page_ids": [],
        "page_manifest_ref": None,
        "external_artifact_ref": None,
        "layers": ["narrative"],
        "allow_page_membership_change": False,
        "allow_page_order_change": False,
        "purpose": "exploratory",
    }
    scope.update(over)
    return scope


def _region(**over) -> dict:
    region = {
        "schema_version": "collaboration.v1",
        "authority_policy": "traceable",
        "quality_profile": {
            "content_review_requirement": "independent_model_or_human",
            "requirement_origin": "default_new_argument",
            "override_decision_ref": None,
        },
        "request": None,
        "decisions": [],
        "authorizations": [],
    }
    region.update(over)
    return region


def _decision(**over) -> dict:
    decision = {
        "schema_version": "collaboration_decision.v1",
        "decision_id": "dec-1",
        "project_id": "proj",
        "request_id": "req-1",
        "topic": "direction",
        "subject_refs": [],
        "scope": _scope(),
        "value": "按培训路径",
        "disposition": "accepted",
        "authority_mode": "direct_user",
        "evidence": _evidence("user_event", "verified_user"),
        "delegation_ref": None,
        "basis": [],
        "status": "active",
        "replaces": None,
        "invalidated_by": None,
        "created_at": "2026-10-12T08:00:00Z",
    }
    decision.update(over)
    return decision


def _authorization(**over) -> dict:
    authorization = {
        "schema_version": "collaboration_authorization.v1",
        "authorization_id": "authz-1",
        "project_id": "proj",
        "request_id": "req-1",
        "mode": "execute",
        "actions": ["task.start"],
        "scope": _scope(layers=["page_copy"], purpose="working"),
        "decision_refs": [],
        "delegated_topics": [],
        "constraints": {},
        "max_external_calls": 0,
        "max_candidate_count": 0,
        "budget_template": None,
        "budget_parent_ref": None,
        "budget_key": None,
        "adoption_policy": "candidate_only",
        "delivery_binding": "none",
        "evidence": _evidence(),
        "basis": [],
        "parent_authorization_ref": None,
        "replaces": None,
        "status": "active",
        "expires_at": None,
        "stop_conditions": [],
        "created_at": "2026-10-12T08:00:00Z",
    }
    authorization.update(over)
    return authorization


def _document(**over) -> dict:
    document = new_document(project_id="proj", task={"title": "t", "brief": "b"})
    document["compatibility"] = {
        "project_format": "workbench.v3",
        "minimum_writer": over.pop("writer", "workbench-quality.v1"),
    }
    document.update(over)
    return document


# ---------------------------------------------------------------------------
# Schema registration and cross-file refs


def test_new_contracts_are_registered_and_validate():
    assert models.SCHEMA_FILES["collaboration"] == "collaboration.v1.schema.json"
    assert models.SCHEMA_FILES["collaboration_decision"] == "collaboration-decision.v1.schema.json"
    assert models.SCHEMA_FILES["collaboration_authorization"] == "collaboration-authorization.v1.schema.json"
    models.validate_schema("collaboration", _region())
    models.validate_schema("collaboration_decision", _decision())
    models.validate_schema("collaboration_authorization", _authorization())


def test_document_schema_resolves_cross_file_collaboration_ref():
    document = _document(writer="collaboration.v1", collaboration=_region())
    models.validate_schema("document", document)  # $ref: collaboration.v1.schema.json


def test_unknown_collaboration_fields_are_rejected():
    with pytest.raises(ModelError):
        models.validate_schema("collaboration", {**_region(), "extra_fact": True})
    with pytest.raises(ModelError):
        models.validate_schema("collaboration_decision", {**_decision(), "confirmed": True})


# ---------------------------------------------------------------------------
# Writer boundary: old snapshots stay readable; new facts need the new writer


def test_legacy_document_without_collaboration_still_validates():
    document = _document()  # workbench-quality.v1 writer, no collaboration region
    models.validate_document_semantics(document)


def test_collaboration_facts_require_the_collaboration_writer():
    document = _document(collaboration=_region())  # writer still workbench-quality.v1
    with pytest.raises(ModelError, match="collaboration.v1 writer boundary"):
        models.validate_document_semantics(document)


def test_narrative_pointer_requires_the_collaboration_writer():
    document = _document(narrative=_ref("narrative"))
    with pytest.raises(ModelError, match="Narrative pointer"):
        models.validate_document_semantics(document)


def test_collaboration_writer_requires_the_region():
    document = _document(writer="collaboration.v1")
    with pytest.raises(ModelError, match="requires the collaboration region"):
        models.validate_document_semantics(document)


def test_collaboration_writer_document_validates_with_existing_facts():
    document = _document(writer="collaboration.v1", collaboration=_region(),
                         narrative=_ref("narrative"))
    models.validate_document_semantics(document)


def test_rank_helper_covers_all_previous_boundaries():
    """MIGRATION §2.6: every legacy writer list is a rank comparison now, so
    the new top rank satisfies all of them."""
    document = _document(writer="collaboration.v1", collaboration=_region())
    for boundary in ("content-plan.v1", "changes.v1", "candidates.v1",
                     "style-recipes.v1", "content-ops.v1", "icon-quality.v1",
                     "workbench-quality.v1", "collaboration.v1"):
        assert models.writer_at_least(document, boundary), boundary
    document["compatibility"]["minimum_writer"] = "unknown-writer.v9"
    for boundary in ("content-plan.v1", "collaboration.v1", "workbench-quality.v1"):
        assert not models.writer_at_least(document, boundary), boundary


# ---------------------------------------------------------------------------
# Region semantics


def test_quality_profile_downgrade_must_bind_its_decision():
    region = _region()
    region["quality_profile"]["content_review_requirement"] = "host_self"
    with pytest.raises(ModelError, match="override_decision_ref"):
        models.validate_collaboration_region(region)
    region["quality_profile"]["override_decision_ref"] = _ref("downgrade-decision")
    models.validate_collaboration_region(region)


def test_fidelity_only_requires_confirmed_manuscript_origin():
    region = _region()
    region["quality_profile"]["content_review_requirement"] = "fidelity_only"
    with pytest.raises(ModelError, match="confirmed-manuscript"):
        models.validate_collaboration_region(region)
    region["quality_profile"]["requirement_origin"] = "confirmed_manuscript"
    models.validate_collaboration_region(region)


def test_request_pause_and_close_reasons_are_paired():
    request = {
        "request_id": "req-1", "intent": "content_only", "content_intent": "plan_only",
        "instruction_evidence": _evidence(), "scope": _scope(),
        "paused": True, "pause_reason": None, "closed": False, "closed_reason": None,
        "background_request_ids": [], "variant": None,
    }
    with pytest.raises(ModelError, match="pause_reason"):
        models.validate_collaboration_region(_region(request=request))
    request["pause_reason"] = "用户暂停等待新材料"
    models.validate_collaboration_region(_region(request=request))
    request["paused"] = False
    request["pause_reason"] = None
    request["closed"] = True
    with pytest.raises(ModelError, match="closed_reason"):
        models.validate_collaboration_region(_region(request=request))


def test_client_cannot_upgrade_evidence_assurance():
    with pytest.raises(ModelError, match="assurance"):
        models.validate_evidence_semantics(_evidence("host_attested_instruction", "verified_user"), "e")
    with pytest.raises(ModelError, match="assurance"):
        models.validate_evidence_semantics(_evidence("imported_unknown", "host_attested"), "e")
    with pytest.raises(ModelError, match="assurance"):
        models.validate_evidence_semantics(_evidence("user_event", "host_attested"), "e")
    models.validate_evidence_semantics(_evidence("approved_document", "unverified"), "e")
    models.validate_evidence_semantics(_evidence("delegated", "host_attested"), "e")


# ---------------------------------------------------------------------------
# Decision semantics


def test_delegated_decision_requires_its_authorization_ref():
    with pytest.raises(ModelError, match="delegation_ref"):
        models.validate_decision_semantics(_decision(authority_mode="delegated"))
    models.validate_decision_semantics(
        _decision(authority_mode="delegated", delegation_ref=_ref("authz")))


def test_non_delegated_decision_must_not_carry_delegation_ref():
    with pytest.raises(ModelError, match="delegation_ref"):
        models.validate_decision_semantics(_decision(delegation_ref=_ref("authz")))


def test_decision_projection_must_be_registered_slice():
    proposal = {"artifact_kind": "narrative", "artifact_ref": _ref("narrative"), "projection": "direction"}
    models.validate_decision_semantics(_decision(subject_refs=[proposal]))
    # Well-formed but unregistered projection: the central registry rejects it.
    with pytest.raises(ModelError, match="registered slice"):
        models.validate_decision_semantics(
            _decision(subject_refs=[{**proposal, "projection": "unregistered.slice"}]))
    # Arbitrary JSONPath does not even pass the projection pattern.
    with pytest.raises(ModelError):
        models.validate_decision_semantics(
            _decision(subject_refs=[{**proposal, "projection": "custom.jsonpath[*]"}]))

def test_decision_rejection_and_deferral_are_recordable_facts():
    """rejected/deferred decisions stay reusable business facts (CONTRACTS §3.1)."""
    models.validate_decision_semantics(_decision(disposition="rejected", value="改用主管说明"))
    models.validate_decision_semantics(_decision(disposition="deferred", value="等新材料"))


def test_decision_scope_rejects_duplicate_pages_and_layers():
    with pytest.raises(ModelError, match="duplicate page ids"):
        models.validate_decision_semantics(_decision(scope=_scope(page_ids=["p1", "p1"])))
    with pytest.raises(ModelError, match="duplicate layers"):
        models.validate_decision_semantics(_decision(scope=_scope(layers=["narrative", "narrative"])))


# ---------------------------------------------------------------------------
# Authorization semantics


def test_delegate_authorization_names_its_topics():
    with pytest.raises(ModelError, match="delegated_topics"):
        models.validate_authorization_semantics(_authorization(mode="delegate"))
    models.validate_authorization_semantics(
        _authorization(mode="delegate", delegated_topics=["style"],
                       constraints={"future_pages": {"selector": "adopted_plan_for_this_request",
                                                     "max_pages": 8, "max_pages_basis": "delegated"}}))


def test_execute_authorization_does_not_declare_topics():
    with pytest.raises(ModelError, match="delegated_topics"):
        models.validate_authorization_semantics(_authorization(delegated_topics=["style"]))


def test_call_ceiling_is_integer_and_never_null():
    with pytest.raises(ModelError):
        models.validate_authorization_semantics(_authorization(max_external_calls=None))
    with pytest.raises(ModelError):
        models.validate_authorization_semantics(_authorization(max_external_calls=-1))
    models.validate_authorization_semantics(_authorization(max_external_calls=0))
    models.validate_authorization_semantics(_authorization(max_external_calls=3))


def test_authorization_requires_at_least_one_named_action():
    with pytest.raises(ModelError):
        models.validate_authorization_semantics(_authorization(actions=[]))


# ---------------------------------------------------------------------------
# Task collaboration binding


def test_task_binding_is_optional_and_validated_when_present(tmp_path):
    task = tasks_mod.new_task(
        task_id="task-1", operation_id="op-1", kind="compose", scope_pages=["p1"],
        instruction="x", inputs=[_ref("page")], dependencies=[],
        dispatch_revision="rev-1",
        produced_against=hashlib.sha256(b"basis").hexdigest())
    models.validate_task_semantics(task)  # binding optional for legacy tasks
    task["collaboration_binding"] = {
        "request_id": "req-1",
        "phase": "page_copy",
        "executor_type": "host",
        "authorization_ref": _ref("authz"),
        "decision_refs": [_ref("decision")],
        "write_scope": _scope(layers=["page_copy"], purpose="working"),
        "adoption_policy": "within_scope",
        "eligibility_basis": [],
        "eligibility_digest": hashlib.sha256(b"digest").hexdigest(),
    }
    models.validate_task_semantics(task)
    task["collaboration_binding"] = {**task["collaboration_binding"], "phase": "shipping"}
    with pytest.raises(ModelError):
        models.validate_task_semantics(task)
