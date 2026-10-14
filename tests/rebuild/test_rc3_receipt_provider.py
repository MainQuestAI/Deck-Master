"""Synthetic L1 contracts for the authenticated provider bridge; no real identity."""
from copy import deepcopy
import json
from datetime import datetime, timedelta, timezone

import pytest

from deck_master import content_review, review_evidence, service
from deck_master.models import canonical_json_bytes
from deck_master.store import Store
from synthetic_review_provider import SyntheticProvider
from test_content_preproduction_review import _deck, _review


def _run(tmp_path):
    project, store = _deck(tmp_path)
    registry = review_evidence.ProviderRegistry()
    provider = SyntheticProvider()
    registry.register(provider)
    channel = registry.channel_context()
    outcome = content_review.dispatch_preproduction_review(project, adapter_context=channel)
    task = outcome["task"]
    document = store.load_document()
    reviewer = {"type": "independent_host", "id": "fixture-model", "execution_ref": "fixture-executor",
                "independence_confirmed": True, "identity_receipt": None, "assurance": "host_attested"}
    reviews = [_review(store, document, kind, reviewer=reviewer) for kind in outcome["units"]]
    envelope = {"kind": "review", "pages": [], "page_order": [], "artifact_specs": [],
                "reviews": reviews, "usage_events": [], "notes": "synthetic L1 event"}
    binding = review_evidence.review_binding(store, document, task, envelope)
    claims = {**binding, "executor_ref": "fixture-executor"}
    selector = provider.issue("fixture-completion", claims, "independent_review_receipts")
    return project, store, registry, provider, channel, task, envelope, claims, selector


def test_healthy_channel_dispatches_but_cannot_accept_without_completion(tmp_path):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    before = store.current_revision_id()
    with pytest.raises(review_evidence.EvidenceRejected, match="not a completed receipt"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope, adapter_context=channel)
    assert store.current_revision_id() == before
    completed = registry.review_context(store, store.load_document(), task, envelope, selector)
    outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                    produced_against=task["produced_against"], result_payload=envelope, adapter_context=completed)
    assert outcome["status"] == "accepted"
    record = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                  if store.read_object_json(ref)["task_id"] == task["task_id"])
    proofs = [store.read_object_json(ref) for ref in record["result_refs"]]
    proof = next(obj for obj in proofs if obj.get("schema_version") == "authenticated_review_receipt.v1")
    assert proof["claims"]["result_sha256"] == review_evidence.result_digest(envelope)
    assert store.read_object_bytes(proof["raw_event_ref"]) == provider.events[selector["event_id"]]
    # Committed replay does not require the provider to remain online.
    provider.ready = False
    replay = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                   produced_against=task["produced_against"], result_payload=envelope,
                                   review_receipt_selector={"provider_id": "offline", "event_id": "old"})
    assert replay["status"] == "already_applied"


@pytest.mark.parametrize("field", ["project_id", "request_id", "task_id", "packet_sha256", "subjects_sha256",
                                  "result_sha256", "author_execution_refs", "write_scope"])
def test_receipt_is_bound_to_exact_manuscript_task_scope_and_result(tmp_path, field):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    changed = {**claims, field: "forged-other-binding"}
    provider.issue(selector["event_id"], changed, "independent_review_receipts")
    before = store.current_revision_id()
    with pytest.raises(review_evidence.EvidenceRejected, match=field):
        registry.review_context(store, store.load_document(), task, envelope, selector)
    assert store.current_revision_id() == before


def test_same_author_different_name_never_counts_as_independent(tmp_path):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    author = claims["author_execution_refs"][0]
    provider.issue(selector["event_id"], {**claims, "executor_ref": author}, "independent_review_receipts")
    with pytest.raises(review_evidence.EvidenceRejected, match="author cannot"):
        registry.review_context(store, store.load_document(), task, envelope, selector)


def test_unregistered_forged_selector_context_and_expiry_are_rejected(tmp_path):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    with pytest.raises(review_evidence.ProviderUnavailable):
        review_evidence.ProviderRegistry().review_context(store, store.load_document(), task, envelope, selector)
    for value in ({"provider_id": provider.provider_id, "event_id": "fixture", "verified": True},
                  {"provider_id": provider.provider_id, "event_id": "../payload.json"}):
        with pytest.raises(review_evidence.EvidenceRejected, match="provide only"):
            registry.review_context(store, store.load_document(), task, envelope, value)
    for ctx in ({"independent_review_receipts": [{"verified": True}]}, review_evidence.TrustedContext(), deepcopy(channel)):
        with pytest.raises(review_evidence.EvidenceRejected, match="opaque"):
            content_review.reviewer_capabilities(ctx)
    provider.issue(selector["event_id"], {**claims, "expires_at": (datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat()},
                   "independent_review_receipts")
    with pytest.raises(review_evidence.EvidenceRejected, match="expired"):
        registry.review_context(store, store.load_document(), task, envelope, selector)


def test_changed_result_and_changed_event_replay_cannot_reuse_context(tmp_path):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    ctx = registry.review_context(store, store.load_document(), task, envelope, selector)
    changed = {**envelope, "notes": "different actual result"}
    with pytest.raises(review_evidence.EvidenceRejected, match="not a completed receipt"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=changed, adapter_context=ctx)
    provider.issue(selector["event_id"], {**claims, "reviewer_id": "changed"}, "independent_review_receipts")
    with pytest.raises(review_evidence.EvidenceRejected, match="replayed"):
        registry.review_context(store, store.load_document(), task, envelope, selector)


def test_provider_authentication_and_health_fail_closed(tmp_path):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    provider.verify = lambda raw: (_ for _ in ()).throw(ValueError("bad signature"))
    with pytest.raises(review_evidence.EvidenceRejected, match="authenticate"):
        registry.review_context(store, store.load_document(), task, envelope, selector)
    provider.ready = False
    assert not any(content_review.reviewer_capabilities(channel).values())
    assert content_review.dispatch_preproduction_review(project, adapter_context=channel)["status"] == "needs_reviewer"
    assert review_evidence.DEFAULT_REGISTRY.describe()["providers"] == []
