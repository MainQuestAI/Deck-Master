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


def _accept(registry, project, **kwargs):
    with review_evidence.ProviderRuntime(registry).bound():
        return service.accept_result(project, **kwargs)


def _run(tmp_path):
    project, store = _deck(tmp_path)
    registry = review_evidence.ProviderRegistry()
    provider = SyntheticProvider()
    registry.register(provider)
    channel = registry.channel_context()
    with review_evidence.ProviderRuntime(registry).bound():
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
        _accept(registry, project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope, adapter_context=channel)
    assert store.current_revision_id() == before
    completed = registry.review_context(store, store.load_document(), task, envelope, selector)
    outcome = _accept(registry, project, task_id=task["task_id"], operation_id=task["operation_id"],
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
    replay = _accept(registry, project, task_id=task["task_id"], operation_id=task["operation_id"],
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
        _accept(registry, project, task_id=task["task_id"], operation_id=task["operation_id"],
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
    with review_evidence.ProviderRuntime(registry).bound():
        assert not any(content_review.reviewer_capabilities(channel).values())
        assert content_review.dispatch_preproduction_review(project, adapter_context=channel)["status"] == "needs_reviewer"
    assert review_evidence.DEFAULT_REGISTRY.describe()["providers"] == []


def test_foreign_registry_echo_provider_is_rejected_by_the_current_runtime(tmp_path):
    project, store = _deck(tmp_path)
    foreign = review_evidence.ProviderRegistry()
    echo = SyntheticProvider()
    foreign.register(echo)
    assert review_evidence.current_registry() is review_evidence.DEFAULT_REGISTRY
    before = store.current_revision_id()
    # Public register/mint does not make this issuer part of the actual service.
    with pytest.raises(review_evidence.EvidenceRejected, match="Runtime's trusted bootstrap"):
        content_review.dispatch_preproduction_review(project, adapter_context=foreign.channel_context())
    assert store.current_revision_id() == before
    project2, store2, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path / "actual-runtime")
    completed = registry.review_context(store2, store2.load_document(), task, envelope, selector)
    with pytest.raises(review_evidence.EvidenceRejected, match="Runtime's trusted bootstrap"):
        service.accept_result(project2, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=envelope, adapter_context=completed)
    assert content_review.preproduction_status(store2, store2.load_document())["status"] == "missing"
    assert review_evidence.DEFAULT_REGISTRY.describe()["providers"] == []


def test_runtime_bootstrap_seals_issuers_and_restores_the_default_scope():
    registry = review_evidence.ProviderRegistry()
    registry.register(SyntheticProvider())
    runtime = review_evidence.ProviderRuntime(registry)
    with pytest.raises(review_evidence.EvidenceRejected, match="sealed"):
        registry.register(SyntheticProvider())
    with runtime.bound():
        assert review_evidence.current_registry() is registry
        assert content_review.reviewer_capabilities(registry.channel_context())["independent_review_receipts"]
    assert review_evidence.current_registry() is review_evidence.DEFAULT_REGISTRY


def _user_run(tmp_path):
    from deck_master import collaboration
    from test_collaboration_service import _project, _declared, _scope
    project, store = _project(tmp_path)
    document = store.load_document()
    receipt = store.put_json_object({"fixture": "transport record"})
    evidence = _declared(store, "user_event", transport_receipt_ref=receipt)
    request = {"intent": "content_only", "content_intent": "write_only", "instruction_evidence": evidence,
               "scope": _scope()}
    digest = collaboration.write_digest(collaboration.ACTION_REQUEST_START, request)
    registry = review_evidence.ProviderRegistry()
    provider = SyntheticProvider()
    registry.register(provider)
    from deck_master.models import sha256_bytes
    claims = {"project_id": document["project_id"], "request_id": None, "action_binding": digest,
              "source_ref": evidence["source_ref"], "presentation_ref": None, "receipt_ref": receipt,
              "transport_record_sha256": sha256_bytes(store.read_object_bytes(receipt)), "actor_id": "synthetic-actor"}
    selector = provider.issue("synthetic-user-completion", claims, "verified_user_events")
    authenticated = provider.verify(provider.events[selector["event_id"]])
    transport = store.read_object_bytes(receipt)
    provider.events[selector["event_id"]] = transport
    provider.verify = lambda raw: authenticated if raw == transport else (_ for _ in ()).throw(ValueError("different original"))
    ctx = registry.user_event_context(store, document, action_binding=digest, source_ref=evidence["source_ref"],
                                      presentation_ref=None, receipt_ref=receipt, selector=selector)
    return project, store, registry, provider, ctx, request, digest


@pytest.mark.parametrize("change", ["expires", "health", "project", "request", "action", "source", "transport"])
def test_cached_user_context_rechecks_time_health_and_exact_binding(tmp_path, monkeypatch, change):
    from deck_master import collaboration
    project, store, registry, provider, ctx, request, digest = _user_run(tmp_path)
    if change == "health":
        other = SyntheticProvider()
        other.provider_id = "another-healthy-issuer"
        registry.register(other)
    with review_evidence.ProviderRuntime(registry).bound():
        evidence = collaboration.resolve_evidence(request["instruction_evidence"], adapter_context=ctx,
                    action_binding=digest, project_id=store.load_document()["project_id"], request_id=None)
        assert evidence["assurance"] == "verified_user"
        actual = dict(request["instruction_evidence"])
        kwargs = {"action_binding": digest, "project_id": store.load_document()["project_id"], "request_id": None}
        if change == "expires":
            future = datetime.now(timezone.utc) + timedelta(hours=2)
            class Later(datetime):
                @classmethod
                def now(cls, tz=None):
                    return future
            monkeypatch.setattr(review_evidence, "datetime", Later)
        elif change == "health":
            provider.ready = False
            assert content_review.reviewer_capabilities(ctx)["verified_user_events"] is True
        elif change in ("project", "request", "action"):
            kwargs[{"project":"project_id", "request":"request_id", "action":"action_binding"}[change]] = "different"
        else:
            actual[{"source":"source_ref", "transport":"transport_receipt_ref"}[change]] = store.put_json_object({"fixture":"changed"})
        downgraded = collaboration.resolve_evidence(actual, adapter_context=ctx, **kwargs)
        assert downgraded["assurance"] == "host_attested"
        if change in ("expires", "health"):
            outcome = collaboration.start_request(project, input=request, base_revision=store.current_revision_id(),
                                                   operation_id="synthetic-expiry-use", adapter_context=ctx)
            assert outcome["assurance"] == "host_attested"
            assert store.load_document()["collaboration"]["request"]["instruction_evidence"]["assurance"] == "host_attested"


def test_user_event_must_persist_the_actual_authenticated_original_bytes(tmp_path):
    project, store, registry, provider, ctx, request, digest = _user_run(tmp_path)
    selector = {"provider_id": provider.provider_id, "event_id": "synthetic-user-completion"}
    original_claims = provider.verify(provider.fetch(selector["event_id"]))
    provider.events[selector["event_id"]] = canonical_json_bytes({"different": "authenticated original"})
    provider.verify = lambda raw: original_claims
    # A new bootstrap still cannot bind different authenticated bytes to the old Ref.
    fresh = review_evidence.ProviderRegistry()
    fresh.register(provider)
    with pytest.raises(review_evidence.EvidenceRejected, match="persisted transport receipt bytes"):
        fresh.user_event_context(store, store.load_document(), action_binding=digest,
               source_ref=request["instruction_evidence"]["source_ref"], presentation_ref=None,
               receipt_ref=request["instruction_evidence"]["transport_receipt_ref"], selector=selector)


@pytest.mark.parametrize("claimed,accepted", [("fixture-executor", True), ("another-actual-claimed-executor", False)])
def test_completed_receipt_rechecks_current_task_execution_after_claim(tmp_path, claimed, accepted):
    project, store, registry, provider, channel, task, envelope, claims, selector = _run(tmp_path)
    assert not task.get("execution_ref")
    ctx = registry.review_context(store, store.load_document(), task, envelope, selector)
    with review_evidence.ProviderRuntime(registry).bound():
        service.task_start(project, task_id=task["task_id"], execution_ref=claimed)
        before = store.current_revision_id()
        kwargs = {"task_id": task["task_id"], "operation_id": task["operation_id"],
                  "produced_against": task["produced_against"], "result_payload": envelope, "adapter_context": ctx}
        if accepted:
            assert service.accept_result(project, **kwargs)["status"] == "accepted"
        else:
            with pytest.raises(review_evidence.EvidenceRejected, match="current claimed review task executor"):
                service.accept_result(project, **kwargs)
            assert store.current_revision_id() == before
            assert content_review.preproduction_status(store, store.load_document())["status"] == "missing"
