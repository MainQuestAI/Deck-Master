"""PR108: exercise record boundaries through the real Store and services."""
import copy
from datetime import datetime, timezone

import pytest

from deck_master import collaboration as co, collaboration_migration, dependency_slices as ds, models, service, tasks
from deck_master.store import Store
from test_collaboration_service import _declared, _project, _ref, _scope, _start, _stored_ref
from test_content_contracts import _narrative, _node, _plan, _plan_input, _review_v2


def _grant(project, store, operation_id, **over):
    payload = {"mode": "delegate", "actions": ["design.propose"],
               "scope": _scope(page_ids=["p1"], layers=["design"]),
               "delegated_topics": ["style"], "instruction_evidence": _declared(store)}
    payload.update(over)
    return co.grant(project, input=payload, base_revision=store.load_document()["revision_id"], operation_id=operation_id)


def _decision(project, store, operation_id, **over):
    payload = {"topic": "direction", "value": "same", "disposition": "accepted",
               "authority_mode": "direct_user", "instruction_evidence": _declared(store), "scope": _scope()}
    payload.update(over)
    return co.record_decision(project, input=payload, base_revision=store.load_document()["revision_id"], operation_id=operation_id)


@pytest.mark.parametrize("change", [
    {"page_ids": ["p2"]}, {"layers": ["output"]}, {"subject": "deck"},
    {"purpose": "delivery"}, {"allow_page_membership_change": True}, {"allow_page_order_change": True},
])
@pytest.mark.parametrize("family", ["decision", "authorization"])
def test_delegated_records_cannot_widen_any_scope_dimension(tmp_path, change, family):
    project, store = _project(tmp_path)
    _start(project, store)
    parent = _grant(project, store, "parent")
    scope = _scope(page_ids=["p1"], layers=["design"])
    scope.update(change)
    before = store.load_document()["revision_id"]
    with pytest.raises(models.ModelError, match="scope|pages|layers"):
        if family == "decision":
            _decision(project, store, "child", topic="style", authority_mode="delegated",
                      delegation_ref=parent["authorization_ref"], scope=scope)
        else:
            _grant(project, store, "child", mode="execute", delegated_topics=[],
                   parent_authorization_ref=parent["authorization_ref"], scope=scope)
    assert store.load_document()["revision_id"] == before


def test_parent_must_delegate_and_cover_actions(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    execute = _grant(project, store, "execute", mode="execute", delegated_topics=[])
    with pytest.raises(models.ModelError, match="delegate"):
        _grant(project, store, "bad-mode", mode="execute", delegated_topics=[], parent_authorization_ref=execute["authorization_ref"])
    parent = _grant(project, store, "parent")
    with pytest.raises(models.ModelError, match="actions"):
        _grant(project, store, "bad-actions", mode="execute", delegated_topics=[],
               actions=["exports.delivery"], parent_authorization_ref=parent["authorization_ref"])


def test_parent_replacement_rechecks_children_and_decisions(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    parent = _grant(project, store, "parent", scope=_scope(page_ids=["p1", "p2"], layers=["design"]))
    child = _grant(project, store, "child", mode="execute", delegated_topics=[],
                   scope=_scope(page_ids=["p2"], layers=["design"]), parent_authorization_ref=parent["authorization_ref"])
    decision = _decision(project, store, "decision", topic="style", authority_mode="delegated",
                         scope=_scope(page_ids=["p2"], layers=["design"]), delegation_ref=parent["authorization_ref"])
    assert ds.authorization_effectiveness(store, store.load_document(), child["authorization_ref"])["effective"]
    assert ds.decision_effectiveness(store, store.load_document(), decision["decision_ref"])["effective"]
    _grant(project, store, "narrow", authorization_id=parent["authorization_id"], replaces=parent["authorization_ref"])
    assert not ds.authorization_effectiveness(store, store.load_document(), child["authorization_ref"])["effective"]
    assert not ds.decision_effectiveness(store, store.load_document(), decision["decision_ref"])["effective"]


@pytest.mark.parametrize("expires", ["not-a-date", "2026-01-01T00:00:00", "", "2026-99-01T00:00:00Z"])
def test_expiration_is_validated_before_commit(tmp_path, expires):
    project, store = _project(tmp_path)
    _start(project, store)
    before = store.load_document()["revision_id"]
    with pytest.raises(models.ModelError, match="expires_at"):
        _grant(project, store, "expiry", expires_at=expires)
    assert store.load_document()["revision_id"] == before


def test_legacy_malformed_expiration_fails_closed_and_exact_expiry_is_expired(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    valid = _grant(project, store, "expiry", expires_at="2026-10-13T00:00:00Z")
    assert not ds.authorization_effectiveness(store, store.load_document(), valid["authorization_ref"],
        now=datetime(2026, 10, 13, tzinfo=timezone.utc))["effective"]
    document = store.load_document()
    for expires in ["invalid", "2026-01-01T00:00:00"]:
        old = store.read_object_json(valid["authorization_ref"])
        ref = store.put_json_object({**old, "expires_at": expires})
        snapshot = copy.deepcopy(document)
        snapshot["collaboration"]["authorizations"] = [ref]
        state = ds.authorization_effectiveness(store, snapshot, ref)
        assert not state["effective"] and "authorization_expiry_invalid" in state["reasons"]


@pytest.mark.parametrize("family", ["request", "decision", "authorization"])
@pytest.mark.parametrize("slot", ["page_manifest_ref", "external_artifact_ref"])
def test_scope_references_must_exist_before_commit(tmp_path, family, slot):
    project, store = _project(tmp_path)
    if family != "request":
        _start(project, store)
    scope = _scope(**{slot: _ref("missing")})
    before = store.load_document()["revision_id"]
    with pytest.raises(models.ModelError, match="not in the store"):
        if family == "request":
            _start(project, store, scope=scope)
        elif family == "decision":
            _decision(project, store, "decision", scope=scope)
        else:
            _grant(project, store, "grant", scope=scope)
    assert store.load_document()["revision_id"] == before


def test_authorization_decisions_are_real_and_auto_bind_effective_dependencies(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    with pytest.raises(models.ModelError, match="decision|not in the store"):
        _grant(project, store, "dangling", decision_refs=[_ref("absent")])
    decision = _decision(project, store, "direction")
    grant = _grant(project, store, "dependent", mode="execute", delegated_topics=[], decision_refs=[decision["decision_ref"]])
    assert ds.authorization_effectiveness(store, store.load_document(), grant["authorization_ref"])["effective"]
    service.inputs_update(project, patch={"reason": "different audience", "task_patch": {"audience": "new audience"}},
                          base_revision=store.load_document()["revision_id"], operation_id="audience")
    assert not ds.decision_effectiveness(store, store.load_document(), decision["decision_ref"])["effective"]
    assert not ds.authorization_effectiveness(store, store.load_document(), grant["authorization_ref"])["effective"]


@pytest.mark.parametrize("change", ["authority", "basis"])
def test_effective_slice_detects_authority_and_transitive_invalidation(tmp_path, change):
    project, store = _project(tmp_path)
    _start(project, store)
    decision = _decision(project, store, "direction")
    basis = ds.make_dependency_slice(store, store.load_document(), kind="decision", identity=decision["decision_id"], projection="effective")
    if change == "authority":
        _decision(project, store, "replace", decision_id=decision["decision_id"], replaces=decision["decision_ref"], authority_mode="system_default")
    else:
        service.inputs_update(project, patch={"reason": "different audience", "task_patch": {"audience": "new audience"}},
                              base_revision=store.load_document()["revision_id"], operation_id="audience")
    assert not ds.assess_basis(store, store.load_document(), [basis])["current"]


def test_replay_retains_receipt_after_later_changes(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    payload = {"topic": "direction", "value": "same", "disposition": "accepted", "authority_mode": "direct_user",
               "instruction_evidence": _declared(store), "scope": _scope()}
    original_base = store.load_document()["revision_id"]
    first = co.record_decision(project, input=payload, base_revision=original_base, operation_id="decision")
    _grant(project, store, "later")
    current = store.load_document()["revision_id"]
    replay = co.record_decision(project, input=payload, base_revision=original_base, operation_id="decision")
    assert replay["status"] == "already_applied"
    assert {key: replay[key] for key in first if key != "status"} == {key: value for key, value in first.items() if key != "status"}
    assert replay["current_revision_id"] == current
    assert store.operation_receipt("decision")["response"] == first


def test_migration_replay_preserves_actionable_details(tmp_path):
    project, store = _project(tmp_path, migrate=False)
    description = collaboration_migration.describe(project)
    args = dict(base_revision=description["revision_id"], plan_digest=description["plan_digest"], operation_id="migrate")
    first = collaboration_migration.apply(project, **args)
    replay = collaboration_migration.apply(project, **args)
    assert replay["preserved"] == first["preserved"]
    assert replay["pending_decisions"] == first["pending_decisions"]
    assert replay["superseded_tasks"] == first["superseded_tasks"]


def test_review_v2_rejects_claimed_human_assurance_at_adoption(tmp_path):
    project, store = _project(tmp_path)
    review = _review_v2()
    review["subjects"] = [_stored_ref(store, "subject")]
    review["reviewer"].update(type="human_external", assurance="verified_user", identity_receipt=None)
    with pytest.raises(models.ModelError, match="receipt"):
        tasks._adopt_review(store, review)
    review["reviewer"]["identity_receipt"] = {"adapter_id": "untrusted", "event_id": "e1",
        "issued_at": "2026-10-13T00:00:00Z", "reviewer_id": review["reviewer"]["id"],
        "project_id": store.load_document()["project_id"], "subjects": review["subjects"]}
    with pytest.raises((models.ModelError, tasks.EnvelopeError), match="identity|assurance"):
        tasks._adopt_review(store, review)


def test_content_plan_roles_budget_and_imported_evidence():
    with pytest.raises(models.ModelError, match="role"):
        models.validate_content_plan_semantics(_plan(input=_plan_input(page_order=["p1", "p2"])))
    with pytest.raises(models.ModelError, match="exact"):
        models.validate_content_plan_semantics(_plan(input=_plan_input(page_budget={"exact": 6, "target": 6, "max": 8})))
    data = _plan(mode="imported_mapping", narrative_ref=None, imported_manuscript={
        "source_ref": _ref("manuscript"), "claimed_confirmation_evidence": {
            "kind": "approved_document", "assurance": "verified_user", "source_ref": _ref("manuscript"),
            "source_locator": "file:synthetic", "actor_id": None, "transport_receipt_ref": None, "presentation_ref": None},
        "preserve_mainline": True, "unresolved_mapping_items": []})
    with pytest.raises(models.ModelError, match="assurance"):
        models.validate_content_plan_semantics(data)


@pytest.mark.parametrize("resolution", ["resolved", "accepted_limit"])
def test_source_exception_requires_open_blocker(resolution):
    narrative = _narrative(nodes=[_node(authority="reported_fact", unresolved_issue_ids=["i1"])],
        issues=[{"issue_id": "i1", "question": "missing source", "impact": "blocker", "affected_node_ids": ["n1"],
                 "resolution": resolution, "resolution_ref": None}])
    with pytest.raises(models.ModelError, match="source"):
        models.validate_narrative_semantics(narrative)


def test_alternatives_reference_known_nodes():
    with pytest.raises(models.ModelError, match="node"):
        models.validate_narrative_semantics(_narrative(alternatives=[
            {"option_id": "a1", "description": "choice", "benefit": "benefit", "cost": "cost", "affected_node_ids": ["absent"]}]))


def test_scope_manifest_compares_order_and_external_binding(tmp_path):
    from deck_master.collaboration_scope import scope_gaps
    project, store = _project(tmp_path)
    original = _plan()
    manifest = store.put_json_object(original)
    changed_links = store.put_json_object({**original, "page_links": [{"page_id": "p1", "page_ref": _ref("new-copy")} ]})
    external = _stored_ref(store, "external")
    parent = _scope(subject="deck", page_ids=["p1"], page_manifest_ref=manifest, external_artifact_ref=external)
    assert scope_gaps(store, parent, {**parent, "page_manifest_ref": changed_links}) == []
    reordered = copy.deepcopy(original)
    reordered["input"]["page_order"] = ["p2", "p1"]
    assert "page_manifest_ref" in scope_gaps(store, parent, {**parent, "page_manifest_ref": store.put_json_object(reordered)})
    assert "external_artifact_ref" in scope_gaps(store, parent, {**parent, "external_artifact_ref": None})
    assert "page_manifest_ref" in scope_gaps(store, parent, {**parent, "page_manifest_ref": _ref("missing")})


def test_effective_dependency_cycles_fail_closed(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    grant = _grant(project, store, "parent")
    document = store.load_document()
    record = store.read_object_json(grant["authorization_ref"])
    dep = ds.make_dependency_slice(store, document, kind="authorization", identity=record["authorization_id"], projection="effective")
    record["basis"].append(dep)
    ref = store.put_json_object(record)
    document["collaboration"]["authorizations"] = [ref]
    assert not ds.authorization_effectiveness(store, document, ref)["effective"]


def test_all_collaboration_mutations_save_replayable_receipts(tmp_path):
    project, store = _project(tmp_path)
    request = _start(project, store)
    grant = _grant(project, store, "grant")
    paused = co.pause_request(project, reason="wait", base_revision=store.load_document()["revision_id"], operation_id="pause")
    resumed = co.resume_request(project, instruction_evidence=_declared(store),
        base_revision=store.load_document()["revision_id"], operation_id="resume")
    revoked = co.revoke_authorization(project, authorization_id=grant["authorization_id"], reason="stop",
        base_revision=store.load_document()["revision_id"], operation_id="revoke")
    for op, response in [("grant", grant), ("pause", paused), ("resume", resumed), ("revoke", revoked)]:
        assert store.operation_receipt(op)["response"] == response


def test_review_v2_can_replace_same_review_family(tmp_path):
    project, store = _project(tmp_path)
    review = _review_v2()
    review["subjects"] = [_stored_ref(store, "subject")]
    review["reviewer"]["evidence_ref"] = _stored_ref(store, "review execution")
    review.update(status="fail", findings=[{"finding_id": "f1", "page_id": None,
        "kind": "content", "message": "Unsupported causal claim", "element_refs": [],
        "expected": "Bounded hypothesis", "actual": "Asserted fact",
        "evidence": [], "resolution": "open", "impact": "must_fix"}])
    ref = store.put_json_object(tasks._adopt_review(store, review))
    updated = {**review, "replaces": ref}
    adopted = tasks._adopt_review(store, updated)
    assert adopted["replaces"] == ref


def test_rehashing_stale_dependency_cannot_launder_authority(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    decision = _decision(project, store, "direction")
    old_basis = ds.make_dependency_slice(store, store.load_document(), kind="decision", identity=decision["decision_id"], projection="effective")
    service.inputs_update(project, patch={"reason": "different audience", "task_patch": {"audience": "changed"}},
        base_revision=store.load_document()["revision_id"], operation_id="audience")
    document = store.load_document()
    with pytest.raises(models.ModelError, match="ineffective"):
        ds.make_dependency_slice(store, document, kind="decision", identity=decision["decision_id"], projection="effective")
    # Even a caller that submits the freshly observed hash cannot turn the
    # failed dependency into a satisfied basis.
    current = ds.build_slice(store, document, kind="decision", identity=decision["decision_id"], projection="effective")
    forged = {**old_basis, "sha256": current["sha256"]}
    assert not ds.assess_basis(store, document, [forged])["current"]
    grant = _grant(project, store, "dependent", mode="execute", delegated_topics=[], basis=[forged])
    assert not ds.authorization_effectiveness(store, store.load_document(), grant["authorization_ref"])["effective"]


@pytest.mark.parametrize("over", [{"disposition": "rejected"}, {"disposition": "deferred"},
    {"authority_mode": "host_proposal"}, {"authority_mode": "system_default"}, {"authority_mode": "imported_unknown"}])
def test_unaccepted_decisions_cannot_back_execution(tmp_path, over):
    project, store = _project(tmp_path)
    _start(project, store)
    decision = _decision(project, store, "direction", **over)
    assert ds.decision_effectiveness(store, store.load_document(), decision["decision_ref"])["effective"]
    with pytest.raises(models.ModelError, match="accepted|authority"):
        _grant(project, store, "execute", mode="execute", delegated_topics=[], decision_refs=[decision["decision_ref"]])


def test_decision_rejection_invalidates_derived_authorization(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    decision = _decision(project, store, "direction")
    grant = _grant(project, store, "execute", mode="execute", delegated_topics=[], decision_refs=[decision["decision_ref"]])
    _decision(project, store, "reject", decision_id=decision["decision_id"], replaces=decision["decision_ref"], disposition="rejected")
    assert not ds.authorization_effectiveness(store, store.load_document(), grant["authorization_ref"])["effective"]


def test_set_order_does_not_invalidate_effective_dependencies(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store)
    scope = _scope(page_ids=["p1", "p2"], layers=["design", "review"])
    parent = _grant(project, store, "parent", actions=["design.propose", "review"], scope=scope)
    basis = ds.make_dependency_slice(store, store.load_document(), kind="authorization", identity=parent["authorization_id"], projection="effective")
    decision = _decision(project, store, "style", topic="style", basis=[basis])
    _grant(project, store, "reorder", actions=["review", "design.propose"],
        scope={**scope, "page_ids": ["p2", "p1"], "layers": ["review", "design"]},
        authorization_id=parent["authorization_id"], replaces=parent["authorization_ref"])
    assert ds.decision_effectiveness(store, store.load_document(), decision["decision_ref"])["effective"]
