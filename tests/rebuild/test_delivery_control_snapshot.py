"""T04 slice 5: historical artifact snapshot read under the current control
(AC-R02/R03, CONTRACTS §7/§8).

Delivery and restore read the *selected* artifact with the *current* control
snapshot: an old revision's relaxed policy, its still-active-looking
authorization or its unverified human label never overrides a current
withdrawal, a current requirement or the current policy switch.
"""
import pytest

from test_eligibility_enforcement import (  # noqa: E402  (shared fixtures)
    _declared, _grant, _project, _scope, _start)
from deck_master import collaboration, dependency_slices, eligibility
from deck_master.models import bump_revision
from deck_master.store import Store


def _set_policy(store, over):
    import uuid
    operation_id = f"policy-{uuid.uuid4().hex[:10]}"
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": operation_id, "kind": "policy_update",
                                      "description": "policy", "read_set": []})
    bumped["policy"] = {**document["policy"], **over}
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id=operation_id)
    return bumped


def _delivery_request(project, store, pages=("p1", "p2")):
    _start(project, store, scope=_scope(subject="deck", page_ids=list(pages),
                                        layers=["output"], purpose="delivery"))
    return _grant(project, store, actions=("export.delivery",),
                  scope=_scope(subject="deck", page_ids=list(pages), layers=["output"],
                               purpose="delivery"),
                  delivery_binding="process_delegation")


# ---------------------------------------------------------------------------
# Historical delivery


def test_a_current_withdrawal_stops_a_historical_delivery(tmp_path):
    project, store = _project(tmp_path)
    grant = _delivery_request(project, store)
    active_revision = store.load_document()["revision_id"]
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回交付", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    current = store.load_document()
    artifact = store.load_document(active_revision)
    # In the historical snapshot the authorization was still active…
    assert dependency_slices.authorization_effectiveness(
        store, artifact, grant["authorization_ref"])["effective"] is True
    # …but the delivery is judged against the current control.
    decision = eligibility.evaluate(store, artifact, current, "delivery.historical")
    assert decision["allowed"] is False
    assert "authorization_revoked" in decision["reason_codes"]
    assert decision["artifact_revision_id"] == active_revision
    assert decision["control_revision_id"] == current["revision_id"]


def test_historical_delivery_entry_consumes_the_current_control(tmp_path):
    """The real entry (exports.create with a selected revision) reads the old
    artifact under the current control, and review copies stay report-only."""
    project, store = _project(tmp_path)
    grant = _delivery_request(project, store)
    active_revision = store.load_document()["revision_id"]
    collaboration.revoke_authorization(project, authorization_id=grant["authorization_id"],
                                       reason="撤回", base_revision=store.load_document()["revision_id"],
                                       operation_id="op-revoke")
    from deck_master import exports
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        exports.create(project, purpose="delivery", revision=active_revision,
                       output_dir=tmp_path / "historical-delivery")
    error = excinfo.value.payload()["error"]
    assert "authorization_revoked" in error["reason_codes"]
    assert not (tmp_path / "historical-delivery").exists()
    review = exports.create(project, purpose="review", revision=active_revision,
                            output_dir=tmp_path / "historical-review")
    assert review["status"] == "exported"


def test_an_old_relaxed_policy_cannot_override_a_current_requirement(tmp_path):
    project, store = _project(tmp_path)
    old_revision = store.load_document()["revision_id"]        # professional review off
    _set_policy(store, {"professional_review_required_for_delivery": True})
    _delivery_request(project, store)
    current = store.load_document()
    artifact = store.load_document(old_revision)
    assert artifact["policy"]["professional_review_required_for_delivery"] is False
    decision = eligibility.evaluate(store, artifact, current, "delivery.historical")
    assert "professional_review_required" in decision["reason_codes"]
    assert decision["delivery"]["professional"]["required"] is True


def test_an_old_human_label_does_not_satisfy_the_current_human_policy(tmp_path):
    project, store = _project(tmp_path)
    _delivery_request(project, store)
    # The snapshot carries a self-declared human pass with no verified receipt.
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    review_ref = store.put_json_object({
        "schema_version": "deck_review.v1", "review_id": "review-old-human",
        "kind": "professional_use", "review_stage": "final", "status": "pass",
        "reviewer": {"type": "human_internal", "id": "someone", "assurance": "verified_user",
                     "identity_receipt": {"adapter_id": "not-installed", "event_id": "e1"}},
        "subjects": [entry["page"]], "dependencies": [], "observations": ["looks fine"],
        "findings": [], "replaces": None})
    bumped = bump_revision(document, {"operation_id": "review-op", "kind": "review_update",
                                      "description": "old human label", "read_set": []})
    bumped["reviews"] = [*document["reviews"], review_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="review-op")
    old_revision = store.load_document()["revision_id"]
    _set_policy(store, {"professional_review_required_for_delivery": True})
    current = store.load_document()
    decision = eligibility.evaluate(store, store.load_document(old_revision), current,
                                    "delivery.historical")
    assert "professional_review_required" in decision["reason_codes"]
    professional = decision["delivery"]["professional"]
    assert professional["human_signoff"] is False
    assert "identity_adapter_unavailable" in professional["gap_reasons"]


def test_a_current_loosening_is_honored_for_a_historical_snapshot(tmp_path):
    project, store = _project(tmp_path)
    _set_policy(store, {"professional_review_required_for_delivery": True})
    old_revision = store.load_document()["revision_id"]
    _set_policy(store, {"professional_review_required_for_delivery": False})
    _delivery_request(project, store)
    current = store.load_document()
    decision = eligibility.evaluate(store, store.load_document(old_revision), current,
                                    "delivery.historical")
    assert "professional_review_required" not in decision["reason_codes"]
    assert decision["allowed"] is True, decision["reason_codes"]


# ---------------------------------------------------------------------------
# Restore keeps the current control


def test_restore_to_a_relaxed_snapshot_does_not_restore_its_policy(tmp_path):
    project, store = _project(tmp_path)
    _delivery_request(project, store)
    relaxed_revision = store.load_document()["revision_id"]
    _set_policy(store, {"professional_review_required_for_delivery": True})
    collaboration.pause_request(project, reason="等确认",
                                base_revision=store.load_document()["revision_id"],
                                operation_id="op-pause")
    from deck_master.editing import restore
    restore(project, revision_id=relaxed_revision,
            base_revision=store.load_document()["revision_id"], operation_id="op-restore")
    after = store.load_document()
    # Content came back; the control facts did not move.
    assert after["policy"]["professional_review_required_for_delivery"] is True
    assert after["collaboration"]["request"]["paused"] is True
    assert after["compatibility"]["minimum_writer"] == "collaboration.v1"
    decision = eligibility.evaluate(store, after, after, "readiness.final")
    assert "professional_review_required" in decision["reason_codes"]


def test_restored_scope_is_still_the_current_request_scope(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"]))
    wide_revision = store.load_document()["revision_id"]
    _start(project, store, operation_id="op-start-2", intent="edit", content_intent=None,
           scope=_scope(page_ids=["p2"], layers=["page_copy"]),
           replace_request_id=store.load_document()["collaboration"]["request"]["request_id"])
    from deck_master.editing import restore
    restore(project, revision_id=wide_revision,
            base_revision=store.load_document()["revision_id"], operation_id="op-restore")
    after = store.load_document()
    # The old request is not restored: the current narrower request stays.
    assert after["collaboration"]["request"]["scope"]["page_ids"] == ["p2"]
    decision = eligibility.evaluate(store, after, after, "page.edit",
                                    {"targets": {"page_ids": ["p1"], "layers": ["page_copy"]}})
    assert "scope_exceeded" in decision["reason_codes"]
    assert _declared(store)  # fixture still works after the restore transaction
