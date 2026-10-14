"""T02 slice 4: registered dependency slices and computed invalidation
(CONTRACTS §7, AC-C03): an audience change invalidates decisions and
authorizations built on it, a single-page edit only stales that page's slice,
and unrelated facts stay effective."""
import hashlib

import pytest

from deck_master import collaboration, dependency_slices, service
from deck_master.dependency_slices import (assess_basis, authorization_effectiveness,
                                           decision_effectiveness, make_dependency_slice)
from deck_master.models import ModelError, bump_revision, require_writer
from deck_master.store import Store


def _ref(seed: str) -> dict:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return {"path": f".deckmaster/objects/{digest[:2]}/{digest}.json", "sha256": digest}


def _scope(**over) -> dict:
    # T04: the fixture's request names the pages/layers its tests actually
    # edit (a direct page edit now consumes the same eligibility judgement).
    scope = {"subject": "pages", "page_ids": ["p1", "p2"], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["narrative", "page_copy"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "exploratory"}
    scope.update(over)
    return scope


def _declared(store=None) -> dict:
    source = store.put_json_object({"fixture": "source"}) if store is not None else _ref("source")
    return {"kind": "host_attested_instruction", "source_ref": source,
            "source_locator": "chat:msg-1", "actor_id": None,
            "transport_receipt_ref": None, "presentation_ref": None}


def _page(pid: str, text: str) -> dict:
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
            "customer_visible": {"title": f"标题{pid}", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": text}]},
            "visual_spec": {"intent": "synthetic", "reference_mode": "new_design"}}


def _project(tmp_path):
    project = tmp_path / "proj"
    service.create(project, brief="slices", draft={"pages": [_page("p1", "原句。"),
                                                            _page("p2", "第二页。")]})
    store = Store(project)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "bootstrap", "kind": "collaboration_update",
                                      "description": "bootstrap", "read_set": []})
    bumped["collaboration"] = {
        "schema_version": "collaboration.v1", "authority_policy": "traceable",
        "quality_profile": {"content_review_requirement": "independent_model_or_human",
                            "requirement_origin": "default_new_argument",
                            "override_decision_ref": None},
        "request": None, "decisions": [], "authorizations": [],
    }
    require_writer(bumped, "collaboration.v1")
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="bootstrap")
    store = Store(project)
    collaboration.start_request(
        project, input={"intent": "content_only", "content_intent": "write_only",
                        "instruction_evidence": _declared(store), "scope": _scope()},
        base_revision=store.load_document()["revision_id"], operation_id="op-start")
    return project, Store(project)


def _audience_slice(store):
    return make_dependency_slice(store, store.load_document(),
                                 kind="task_fact", identity="audience", projection="value")


def _page_slice(store, page_id):
    return make_dependency_slice(store, store.load_document(),
                                 kind="artifact", identity=f"page:{page_id}", projection="content")


def _record_decision(project, store, *, basis, topic="direction") -> dict:
    return collaboration.record_decision(
        project, input={"topic": topic, "value": "按培训路径", "disposition": "accepted",
                        "authority_mode": "direct_user", "instruction_evidence": _declared(store),
                        "scope": _scope(), "basis": basis},
        base_revision=store.load_document()["revision_id"], operation_id=f"op-dec-{topic}")


def _grant(project, store, *, basis, parent_ref=None, expires_at=None, operation_id="op-grant") -> dict:
    payload = {"mode": "execute", "actions": ["task.start"], "scope": _scope(layers=["page_copy"]),
               "basis": basis, "max_external_calls": 1, "instruction_evidence": _declared(store)}
    if parent_ref is not None:
        payload["parent_authorization_ref"] = parent_ref
    if expires_at is not None:
        payload["expires_at"] = expires_at
    return collaboration.grant(project, input=payload,
                               base_revision=store.load_document()["revision_id"],
                               operation_id=operation_id)


def test_audience_change_invalidates_its_dependents_only(tmp_path):
    project, store = _project(tmp_path)
    audience = _audience_slice(store)
    policy_slice = make_dependency_slice(store, store.load_document(),
                                         kind="policy", identity="document", projection="value")
    decision = _record_decision(project, store, basis=[audience])
    unrelated = _record_decision(project, store, basis=[policy_slice], topic="tradeoff")
    audience_authz = _grant(project, store, basis=[audience, _page_slice(store, "p1")])

    decision_ref = {"path": decision["decision_ref"]["path"], "sha256": decision["decision_ref"]["sha256"]}
    assert decision_effectiveness(store, store.load_document(), decision_ref)["effective"]
    assert authorization_effectiveness(store, store.load_document(),
                                       audience_authz["authorization_ref"])["effective"]

    service.inputs_update(project, patch={"reason": "new audience",
                                          "task_patch": {"audience": "主管阅读"}},
                          base_revision=store.load_document()["revision_id"],
                          operation_id="op-input-audience")
    document = store.load_document()
    state = decision_effectiveness(store, document, decision_ref)
    assert not state["effective"] and "basis_stale" in state["reasons"]
    assert [item["key"] for item in state["basis"]["stale"]] == ["task_fact:audience:value"]
    authz_state = authorization_effectiveness(store, document, audience_authz["authorization_ref"])
    assert not authz_state["effective"] and "basis_stale" in authz_state["reasons"]
    # The unrelated decision sits on the policy slice and stays effective.
    assert decision_effectiveness(store, document,
                                  {"path": unrelated["decision_ref"]["path"],
                                   "sha256": unrelated["decision_ref"]["sha256"]})["effective"]


def test_single_page_edit_stales_only_that_pages_slice(tmp_path):
    # T04: a direct page edit is an adoption boundary, so the fixture's work
    # request (below) authorizes these pages and the page_copy layer.
    project, store = _project(tmp_path)
    p1_basis = _page_slice(store, "p1")
    decision = _record_decision(project, store, basis=[p1_basis])
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    updated = _page("p1", "原句，加一个标点。")
    from deck_master.editing import edit_page
    edit_page(project, page=updated, base_revision=document["revision_id"],
              page_hash=entry["page"]["sha256"], operation_id="op-edit-p1")
    document = store.load_document()
    after = assess_basis(store, document, [p1_basis])
    assert not after["current"] and [item["key"] for item in after["stale"]] == ["artifact:page:p1:content"]
    # A page p2 slice is untouched by the p1 edit.
    assert assess_basis(store, document, [_page_slice(store, "p2")])["current"]
    state = decision_effectiveness(store, document,
                                   {"path": decision["decision_ref"]["path"],
                                    "sha256": decision["decision_ref"]["sha256"]})
    assert not state["effective"] and "basis_stale" in state["reasons"]


def test_unregistered_or_absent_slices_are_never_current(tmp_path):
    project, store = _project(tmp_path)
    document = store.load_document()
    with pytest.raises(ModelError, match="not registered"):
        make_dependency_slice(store, document, kind="task_fact", identity="audience",
                              projection="custom_path")
    with pytest.raises(ModelError, match="absent or the projection is not registered"):
        make_dependency_slice(store, document, kind="artifact", identity="page:p9",
                              projection="content")
    forged = {"kind": "artifact", "identity": "page:p9", "projection": "content",
              "ref": None, "sha256": hashlib.sha256(b"x").hexdigest()}
    state = assess_basis(store, document, [forged])
    assert not state["current"] and state["unregistered"]


def test_authorization_states_and_parent_chain(tmp_path):
    project, store = _project(tmp_path)
    parent = collaboration.grant(
        project, input={"mode": "delegate", "actions": ["task.start"],
                        "scope": _scope(layers=["page_copy"]), "delegated_topics": ["manuscript"],
                        "max_external_calls": 0, "instruction_evidence": _declared(store)},
        base_revision=store.load_document()["revision_id"], operation_id="op-parent")
    child = _grant(project, store, basis=[], parent_ref=parent["authorization_ref"],
                   operation_id="op-child")
    assert authorization_effectiveness(store, store.load_document(),
                                       child["authorization_ref"])["effective"]
    collaboration.revoke_authorization(
        project, authorization_id=parent["authorization_id"], reason="范围撤回",
        base_revision=store.load_document()["revision_id"], operation_id="op-revoke-parent")
    state = authorization_effectiveness(store, store.load_document(), child["authorization_ref"])
    assert not state["effective"] and "parent_ineffective" in state["reasons"]


def test_expired_authorization_is_not_effective(tmp_path):
    from datetime import datetime, timezone
    project, store = _project(tmp_path)
    past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    expired = _grant(project, store, basis=[], expires_at=past, operation_id="op-expired")
    state = authorization_effectiveness(store, store.load_document(), expired["authorization_ref"])
    assert not state["effective"] and "authorization_expired" in state["reasons"]


def test_paused_request_blocks_authorizations_but_keeps_decisions(tmp_path):
    project, store = _project(tmp_path)
    decision = _record_decision(project, store, basis=[])
    grant = _grant(project, store, basis=[], operation_id="op-grant-pause")
    collaboration.pause_request(project, reason="等材料",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    document = store.load_document()
    assert decision_effectiveness(store, document,
                                  {"path": decision["decision_ref"]["path"],
                                   "sha256": decision["decision_ref"]["sha256"]})["effective"]
    state = authorization_effectiveness(store, document, grant["authorization_ref"])
    assert not state["effective"] and "request_paused" in state["reasons"]
