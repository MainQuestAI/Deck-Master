"""T03 x T04 joint gate: the seams the two cards share.

The two cards were developed and reviewed independently; this file pins the
cross-card contracts the joint gate must keep:

1. One binding digest, one implementation — the dispatch side writes it and
   the gate recomputes it (a slice-order drift between the two historical
   implementations was the joint gate's first find).
2. Every production dispatch in an enforced project carries a binding, so the
   gate's unconditional backstop has nothing to refuse (the change flow).
3. A phased compose.v2 task's binding recomputes as valid at the gate, and its
   result is accepted end-to-end with the gate active.
"""
import uuid
from pathlib import Path

import pytest

from synthetic_review_provider import synthetic_context, accept_with_synthetic_provider, dispatch_with_synthetic_provider
from deck_master.review_evidence import EvidenceRejected

from test_eligibility_enforcement import (  # noqa: E402  (shared fixtures)
    _grant, _page, _project, _scope, _settle_preproduction, _start)
from test_compose_v2_phases import _deck_with_pages, _page as _phase_page  # noqa: E402

from test_content_preproduction_review import (  # noqa: E402  (review fixtures)
    _independent_adapter, _review)

from deck_master import (changes, collaboration, collaboration_binding, content_production,
                          content_review, eligibility, service)
from deck_master.store import Store
from rc3_fixtures import claim_fixture_task


def test_one_binding_digest_shared_by_dispatch_and_gate():
    """The gate recomputes the exact bytes the dispatcher wrote.

    Slice-key order (policy < task_fact) deliberately differs from digest
    order here ("zz" sorts after "aa"): sorting the digest values instead of
    the slice keys produced a different digest, and the joint gate caught it.
    """
    scope = {"subject": "pages", "page_ids": ["p2", "p1"], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["svg", "page_copy"],
             "allow_page_membership_change": False, "allow_page_order_change": False,
             "purpose": "working"}
    basis = [{"kind": "policy", "identity": "document", "projection": "value",
              "ref": None, "sha256": "zz"},
             {"kind": "task_fact", "identity": "audience", "projection": "value",
              "ref": None, "sha256": "aa"}]
    dispatch_side = collaboration_binding.eligibility_digest(
        phase="page_copy", write_scope=scope, basis=basis)
    gate_side = eligibility.binding_eligibility_digest("page_copy", scope, basis)
    assert dispatch_side == gate_side
    # Order of the basis list never changes the digest.
    assert eligibility.binding_eligibility_digest(
        "page_copy", scope, list(reversed(basis))) == gate_side


def test_change_dispatch_on_an_enforced_project_is_bound_and_accepted(tmp_path):
    """The edit flow (AC-R03) stays usable in a managed project: commit
    dispatches a bound task, and the result is adopted under the same gate."""
    project, store = _project(tmp_path)
    # The new request changes the audience/intent applicability basis. Review
    # its actual page scope after starting it, with review explicitly in scope.
    _start(project, store, intent="edit",
           scope=_scope(page_ids=["p1"], layers=["page_copy", "svg", "review"]))
    _settle_preproduction(store, seed="change-flow")
    _grant(project, store, actions=("change.commit", "dispatch.host_task"), scope=_scope(page_ids=["p1"]))
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    value = {"schema_version": "change_intent.v1", "project_id": document["project_id"],
             "base_revision": document["revision_id"], "intent": "clarify",
             "instruction": "Clarify the selected page.", "annotation_refs": [],
             "max_calls": 0,
             "targets": [{"page_id": "p1", "page_ref": entry["page"], "layer": "content",
                          "artifact_ref": entry["page"]}]}
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan["plan_id"],
                            base_revision=value["base_revision"],
                            operation_id=str(uuid.uuid4()))
    task_id = result["operation_result"]["task_ids"][0]
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                if store.read_object_json(ref)["task_id"] == task_id)
    binding = task["collaboration_binding"]
    assert binding["phase"] == "production"
    assert binding["write_scope"]["page_ids"] == ["p1"]
    assert eligibility.task_binding_state(store, store.load_document(), task)["status"] == "valid"
    # The host claims the task with the declared protocol, then answers; the
    # gate recomputes the same judgement and adopts.
    claim_fixture_task(project, task, execution_ref="joint-host")
    page = store.read_object_json(entry["page"])
    page["customer_visible"]["title"] = "Clear title"
    accept_with_synthetic_provider(store.project_root, task_id=task_id, operation_id=task["operation_id"],
                          produced_against=task["produced_against"],
                          result_payload={"kind": "repair", "pages": [page]})
    updated = next(e for e in store.load_document()["pages"] if e["page_id"] == "p1")
    assert store.read_object_json(updated["page"])["customer_visible"]["title"] == "Clear title"


def test_change_commit_without_authorization_is_refused_before_dispatch(tmp_path):
    """The same boundary refuses the edit dispatch when no grant covers it."""
    project, store = _project(tmp_path)
    _start(project, store, intent="edit",
           scope=_scope(page_ids=["p1"], layers=["page_copy"]))
    document = store.load_document()
    entry = next(e for e in document["pages"] if e["page_id"] == "p1")
    value = {"schema_version": "change_intent.v1", "project_id": document["project_id"],
             "base_revision": document["revision_id"], "intent": "clarify",
             "instruction": "Clarify the selected page.", "annotation_refs": [],
             "max_calls": 0,
             "targets": [{"page_id": "p1", "page_ref": entry["page"], "layer": "content",
                          "artifact_ref": entry["page"]}]}
    plan = changes.plan(store.project_root, input=value)
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        changes.commit(store.project_root, plan_id=plan["plan_id"],
                       base_revision=value["base_revision"],
                       operation_id=str(uuid.uuid4()))
    assert "authority_insufficient" in excinfo.value.payload()["error"]["reason_codes"]
    tasks = [store.read_object_json(ref) for ref in store.load_document()["tasks"]]
    assert not [t for t in tasks if t.get("kind") in ("repair", "reconstruct", "blueprint")]


def test_phased_result_is_accepted_under_the_gate(tmp_path):
    """End-to-end seam: a phased compose.v2 task written by T03 carries a
    binding whose digest the T04 gate recomputes as valid at acceptance."""
    project, store = _deck_with_pages(tmp_path)
    document = store.load_document()
    task = content_production.open_phase_task(
        store, store.load_document(), operation_id="joint-speech", phase="speech",
        page_ids=["p1"])
    assert eligibility.task_binding_state(store, store.load_document(), task)["status"] == "valid"
    notes = "先讲记录未知。"
    payload = {"updates": [{"page_id": "p1",
                            "page_ref": store.load_document()["pages"][0]["page"],
                            "speaker_notes": notes,
                            "speech_segments": [
                                {"segment_id": "s1", "start_codepoint": 0,
                                 "end_codepoint": len(notes), "narrative_node_ids": ["n1"],
                                 "kind": "cue", "estimated_seconds": 5}]}]}
    envelope = {"schema_version": "compose_result.v2", "kind": "compose", "variant": "speech",
                "task_id": task["task_id"], "operation_id": task["operation_id"],
                "produced_against": task["produced_against"],
                "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                "payload": payload, "usage_events": []}
    claim_fixture_task(project, task, execution_ref='L1-joint-speech')
    out = accept_with_synthetic_provider(project, task_id=task["task_id"],
                                operation_id=task["operation_id"],
                                produced_against=task["produced_against"],
                                result_payload=envelope)
    assert out["status"] == "accepted"
    page = store.read_object_json(store.load_document()["pages"][0]["page"])
    assert page["speaker_notes"] == notes


# ---------------------------------------------------------------------------
# External review F01: a production task binds the authorization it runs under


def _head_authorization_ref(store):
    document = store.load_document()
    region = document["collaboration"]
    assert region["authorizations"], "fixture needs a granted authorization"
    return region["authorizations"][-1]


def test_a_real_dispatch_binds_the_covering_authorization(tmp_path):
    """The task records which grant its work runs under, not just that some
    grant existed at dispatch time (F01): budget attribution and revocation
    follow the bound Ref."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"], layers=["page_copy", "review", "svg"]))
    grant = _grant(project, store, actions=("dispatch.host_task", "call.begin"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=2)
    task = service.open_host_task(store, kind="repair", page_ids=["p1"],
                                  instruction="repair p1 under the grant")
    binding = task["collaboration_binding"]
    assert binding["authorization_ref"] == _head_authorization_ref(store)
    # Budget attribution follows the bound Ref: the task's held slots count
    # against the granted chain, not just the project's totals.
    assert eligibility.task_authorization_id(store, task) == grant["authorization_id"]


def test_revoking_the_bound_grant_refuses_the_late_result(tmp_path):
    """Real dispatch -> claim -> revoke -> late result: the adoption is refused
    on the bound authorization, the page stays untouched, and the call facts
    already observed are preserved (F01's closure path)."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"], layers=["page_copy", "review", "svg"]))
    grant = _grant(project, store, actions=("dispatch.host_task", "call.begin"),
                   scope=_scope(page_ids=["p1"]), max_external_calls=1)
    task = service.open_host_task(store, kind="repair", page_ids=["p1"],
                                  instruction="repair p1 under the grant")
    assert task["collaboration_binding"]["authorization_ref"] is not None
    before = _page_text(store)
    claim_fixture_task(project, task, execution_ref="late-host")
    collaboration.revoke_authorization(
        project, authorization_id=grant["authorization_id"], reason="撤销范围",
        base_revision=store.load_document()["revision_id"], operation_id=str(uuid.uuid4()))
    envelope = {"kind": "repair",
                "files": [], "pages": [_page("p1", "晚到结果。")], "page_order": ["p1"],
                "artifact_specs": [], "reviews": [], "usage_events": [], "notes": "late"}
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        accept_with_synthetic_provider(project, task_id=task["task_id"],
                              operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload=envelope)
    error = excinfo.value.payload()["error"]
    assert "authorization_revoked" in error["reason_codes"]
    assert _page_text(store) == before == "第一页。"


def _page_text(store, page_id="p1"):
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == page_id)
    return store.read_object_json(entry["page"])["customer_visible"]["body_blocks"][0]["text"]


# ---------------------------------------------------------------------------
# External review F02: one preproduction verdict; a delegate never substitutes


def _production_request(project, store, *, operation_id):
    """Replace the compose fixture's content-only request with a full_deck
    request whose scope also covers the review and blueprint layers, so the
    preproduction review can be dispatched and dispatch.blueprint judged on
    the preproduction dimension alone. The prior request stays a background
    id so its direction decision keeps answering for the adopted manuscript."""
    from test_compose_v2_phases import (  # noqa: E402
        _instruction as _phase_instruction, _scope as _phase_scope)
    document = store.load_document()
    current = (document.get("collaboration") or {}).get("request")
    return collaboration.start_request(
        project,
        input={"intent": "full_deck", "content_intent": "content_full",
               "instruction_evidence": _phase_instruction(store),
               "scope": _phase_scope(layers=["narrative", "plan", "page_copy", "speech",
                                             "review", "blueprint"],
                                     allow_page_membership_change=True),
               "replace_request_id": current["request_id"] if current else None,
               "background_request_ids": [current["request_id"]] if current else []},
        base_revision=document["revision_id"], operation_id=operation_id)


def _grant_blueprint(project, store, *, mode="execute", operation_id="op-blueprint-grant"):
    return _grant(project, store, mode=mode, actions=("dispatch.blueprint",),
                  scope=_scope(page_ids=["p1"], layers=["blueprint"]),
                  operation_id=operation_id)


def _blueprint_eligibility(store):
    document = store.load_document()
    return eligibility.evaluate(store, document, document, "dispatch.blueprint",
                                {"targets": {"page_ids": ["p1"],
                                             "layers": ["blueprint"]}})


def _accept_preproduction_reviews(project, store, *, findings_by_kind=None, force_units=None):
    """The real review path: dispatch the preproduction review task under the
    current request, then accept the full unit set through accept_result. An
    optional map carries open must-fix findings per review kind."""
    document = store.load_document()
    adapter = _independent_adapter(store, document)
    outcome = dispatch_with_synthetic_provider(project, adapter_context=adapter, force_units=force_units)
    assert outcome["status"] == "review_dispatched"
    task = outcome["task"]
    document = store.load_document()
    reviewer = {"type": "independent_host", "id": "model-b", "execution_ref": "exec-independent",
                "independence_confirmed": True, "identity_receipt": None,
                "assurance": "host_attested"}
    packet = store.read_object_json(outcome["review_draft_ref"])
    reviews = []
    for kind in packet["required_units"]:
        owners = [row["review_ref"] for row in packet["review_scope"]["owners"] if row["kind"] == kind]
        if not owners:
            reviews.append(_review(store, document, kind, reviewer=reviewer,
                                   findings=(findings_by_kind or {}).get(kind, ())))
        for ref in owners:
            owner = store.read_object_json(ref)
            row = _review(store, document, kind, reviewer=reviewer,
                          findings=[*owner["findings"], *(findings_by_kind or {}).get(kind, ())])
            row.update(review_id=owner["review_id"], replaces=ref)
            reviews.append(row)
    out = accept_with_synthetic_provider(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"kind": "review", "pages": [], "page_order": [], "artifact_specs": [],
                        "reviews": reviews, "usage_events": [],
                        "notes": "preproduction review"},
        adapter_context=adapter)
    assert out["status"] == "accepted"
    return out


def test_a_review_delegate_never_replaces_the_preproduction_review(tmp_path):
    """F02: an effective delegate covering the review topics is reused to
    arrange the review (AC-R06) — it is never the review itself. With no
    review records the production gate stays blocked."""
    project, store = _deck_with_pages(tmp_path)
    _production_request(project, store, operation_id="op-request-full-1")
    _grant_blueprint(project, store, mode="delegate", operation_id="op-review-delegate")
    decision = _blueprint_eligibility(store)
    assert decision["allowed"] is False
    assert "needs_reviewer" in decision["reason_codes"]
    assert decision["preproduction"]["via"] != "delegate"


def test_a_partial_preproduction_failure_keeps_production_blocked(tmp_path):
    """F02: one passing unit never satisfies the whole review; an open
    must-fix page_copy finding keeps production blocked even though the
    argument unit passed on the same current manuscript."""
    project, store = _deck_with_pages(tmp_path)
    _production_request(project, store, operation_id="op-request-full-2")
    _grant_blueprint(project, store)
    finding = {"finding_id": "f-pc-1", "kind": "content", "impact": "must_fix",
               "resolution": "open", "page_id": "p1", "element_refs": ["atom:p1:title"],
               "message": "限定没有进入上屏正文", "expected": "上屏正文带限定",
               "actual": "正文无该限定", "evidence": []}
    _accept_preproduction_reviews(project, store, findings_by_kind={"page_copy": [finding]})
    decision = _blueprint_eligibility(store)
    assert decision["allowed"] is False
    assert "preproduction_blocked" in decision["reason_codes"]
    assert decision["preproduction"]["blocking_findings"]


def test_a_full_pass_qualsifies_production_and_a_new_revision_revokes_it(tmp_path):
    """F02: only a full applicable pass qualifies production; once the
    manuscript moves again the stale pass no longer answers for it."""
    project, store = _deck_with_pages(tmp_path)
    _production_request(project, store, operation_id="op-request-full-3")
    _grant_blueprint(project, store)
    _accept_preproduction_reviews(project, store)
    allowed = _blueprint_eligibility(store)
    assert allowed["preproduction"]["satisfied"] is True
    assert allowed["preproduction"]["via"] == "review"
    assert "needs_reviewer" not in allowed["reason_codes"]
    assert "preproduction_blocked" not in allowed["reason_codes"]
    # The manuscript moves through the real content path: a page_copy phase
    # task rewrites p1, so every review record is stale for the new bytes.
    from test_compose_v2_phases import (_dispatch as _phase_dispatch,  # noqa: E402
                                        _plan_input as _phase_plan_input,
                                        _submit as _phase_submit)
    task = _phase_dispatch(store, phase="page_copy")
    document = store.load_document()
    page = _phase_page(store, document, "p1", notes="修订后的口播。")
    page["customer_visible"]["title"] = "修订后的标题"
    _phase_submit(project, task,
                  {"pages": [page], "page_order": ["p1"],
                   "plan_input": _phase_plan_input(document, ["p1"])},
                  "page_copy")
    blocked = _blueprint_eligibility(store)
    assert blocked["allowed"] is False
    assert blocked["preproduction"]["satisfied"] is False
    assert "needs_reviewer" in blocked["reason_codes"]


def test_a_new_failing_review_on_the_same_manuscript_reblocks_production(tmp_path):
    """F02: a fresh failing record on unchanged bytes answers for the current
    manuscript just like a moved manuscript does — the earlier passing set
    stops qualifying production (independent re-review N3)."""
    project, store = _deck_with_pages(tmp_path)
    _production_request(project, store, operation_id="op-request-full-4")
    _grant_blueprint(project, store)
    _accept_preproduction_reviews(project, store)
    allowed = _blueprint_eligibility(store)
    assert allowed["preproduction"]["satisfied"] is True
    # A second review round on the SAME bytes reports a new must-fix finding.
    finding = {"finding_id": "f-round2", "kind": "content", "impact": "must_fix",
               "resolution": "open", "page_id": "p1", "element_refs": ["atom:p1:title"],
               "message": "第二 round 发现限定缺失", "expected": "上屏正文带限定",
               "actual": "正文无该限定", "evidence": []}
    _accept_preproduction_reviews(project, store,
                                  findings_by_kind={"argument": [finding]}, force_units=["argument"])
    reblocked = _blueprint_eligibility(store)
    assert reblocked["allowed"] is False
    assert "preproduction_blocked" in reblocked["reason_codes"]
    assert reblocked["preproduction"]["blocking_findings"]


# ---------------------------------------------------------------------------
# External review F03: an omitted page is never an implicit deletion


def _two_page_deck(tmp_path):
    """A deck built to p1+p2 through the real phased flow: one full-set
    page_copy result delivers both pages, exactly like the fixture deck."""
    from test_compose_v2_phases import (_accept_argument, _adopt_direction,  # noqa: E402
                                        _dispatch as _phase_dispatch,
                                        _plan_input as _phase_plan_input,
                                        _project as _phase_project,
                                        _request as _phase_request,
                                        _submit as _phase_submit)
    project, store = _phase_project(tmp_path)
    _phase_request(project, store, intent="full_deck", content_intent=None)
    _, out = _accept_argument(project, store)
    _adopt_direction(project, store, out["result_refs"][0])
    task = _phase_dispatch(store, phase="page_copy")
    document = store.load_document()
    pages = [_phase_page(store, document, "p1"),
             _phase_page(store, document, "p2", notes="第二页口播。")]
    _phase_submit(project, task,
                  {"pages": pages, "page_order": ["p1", "p2"],
                   "plan_input": _phase_plan_input(document, ["p1", "p2"])},
                  "page_copy")
    return project, Store(project)


def test_a_scoped_page_copy_result_never_deletes_unselected_pages(tmp_path):
    """F03: a page_copy task scoped to p1 cannot withdraw p2 from the current
    manuscript by leaving it out; the acceptance names the omission instead."""
    from test_compose_v2_phases import (_plan_input as _phase_plan_input,  # noqa: E402
                                        _submit as _phase_submit)
    from deck_master import tasks as tasks_mod
    project, store = _two_page_deck(tmp_path)
    entry_p2 = next(e for e in store.load_document()["pages"] if e["page_id"] == "p2")
    task = content_production.open_phase_task(
        store, store.load_document(), operation_id="scoped-p1", phase="page_copy",
        page_ids=["p1"])
    claim_fixture_task(project, task, execution_ref='L1-scoped-page-copy')
    page = _phase_page(store, store.load_document(), "p1", notes="重写后的口播。")
    with pytest.raises(tasks_mod.EnvelopeError) as excinfo:
        _phase_submit(project, task,
                      {"pages": [page], "page_order": ["p1"],
                       "plan_input": _phase_plan_input(store.load_document(), ["p1"])},
                      "page_copy")
    assert "p2" in str(excinfo.value)
    document = store.load_document()
    assert [e["page_id"] for e in document["pages"]] == ["p1", "p2"]
    kept = next(e for e in document["pages"] if e["page_id"] == "p2")
    assert kept["page"] == entry_p2["page"], "the preserved page keeps its exact Ref"
    assert store.read_object_json(kept["page"]) == store.read_object_json(entry_p2["page"])


def test_a_membership_scope_may_express_a_real_deletion(tmp_path):
    """F03's authorized counterpart: a full-set page_copy under a scope that
    allows membership change may shrink the deck — explicitly, by page_order."""
    from test_compose_v2_phases import (_dispatch as _phase_dispatch,  # noqa: E402
                                        _plan_input as _phase_plan_input,
                                        _submit as _phase_submit)
    project, store = _two_page_deck(tmp_path)
    task = _phase_dispatch(store, phase="page_copy")
    document = store.load_document()
    page = _phase_page(store, document, "p1", notes="收缩后的唯一一页。")
    _phase_submit(project, task,
                  {"pages": [page], "page_order": ["p1"],
                   "plan_input": _phase_plan_input(document, ["p1"])},
                  "page_copy")
    document = store.load_document()
    assert [e["page_id"] for e in document["pages"]] == ["p1"]


# ---------------------------------------------------------------------------
# External review F04: a batch request answers to the remaining credit


def test_a_batch_request_larger_than_the_remaining_credit_gets_zero(tmp_path):
    """F04: with one call left on the bound grant's chain, a batch request of
    two is refused with zero allocations and an unchanged ledger; a request of
    one still succeeds against the same remaining slot."""
    project, store = _project(tmp_path)
    _start(project, store, scope=_scope(page_ids=["p1"], layers=["page_copy", "review", "svg"]))
    _grant(project, store,
           actions=("dispatch.host_task", "allowance.allocate", "call.begin"),
           scope=_scope(page_ids=["p1"]), max_external_calls=2)
    task = service.open_host_task(store, kind="repair", page_ids=["p1"],
                                  instruction="batch the calls under the grant")
    task_id = task["task_id"]
    from deck_master import tasks as tasks_mod
    first = tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    assert first["status"] == "allocated"

    def held():
        current = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                       if store.read_object_json(ref)["task_id"] == task_id)
        return [entry["state"] for entry in current["call_allowances"]]

    assert held() == ["reserved"]
    with pytest.raises(eligibility.EligibilityBlocked) as excinfo:
        tasks_mod.allocate_call_allowances(store, task_id=task_id, count=2)
    assert "budget_exhausted" in excinfo.value.payload()["error"]["reason_codes"]
    assert held() == ["reserved"], "a refused batch leaves zero allocations"
    second = tasks_mod.allocate_call_allowances(store, task_id=task_id, count=1)
    assert second["status"] == "allocated"
    assert held() == ["reserved", "reserved"]


# ---------------------------------------------------------------------------
# External review F05: the reconciliation task itself stays claimable


def test_the_input_revision_task_stays_claimable_during_reconciliation(tmp_path):
    """F05: the compose.v2 input_revision task that inputs_update dispatched is
    claimable while the project reports needs_reconciliation — start, accept,
    cleared alignment — while other production against the stale content stays
    blocked until the revision lands."""
    from test_compose_v2_phases import (_submit as _phase_submit,)  # noqa: E402
    from deck_master import models
    project, store = _deck_with_pages(tmp_path)
    outcome = service.inputs_update(
        project,
        patch={"reason": "受众变化", "task_patch": {"audience": "现场主管"},
               "source_changes": {"add": [], "replace": [], "remove": [], "metadata": []}},
        base_revision=store.load_document()["revision_id"], operation_id="op-input-reconcile")
    assert outcome["input_alignment"] == "needs_reconciliation"
    summary = outcome["pending_tasks"][0]
    assert summary["intent"] == "input_revision"
    task_id = summary["task_id"]
    # Production that still answers to the old content stays blocked...
    document = store.load_document()
    other = content_production.build_phase_task(store, document, operation_id="stale-phase",
                                                phase="speech", page_ids=["p1"])
    still_blocked = eligibility.evaluate(store, document, document, "task.start",
                                         {"task": other, "targets": {"page_ids": ["p1"]}})
    assert "input_reconciliation_pending" in still_blocked["reason_codes"]
    # ...while the reconciliation task itself is claimable (the deadlock under
    # review refused exactly this claim).
    claim_fixture_task(project, summary, execution_ref="reconcile-host")
    claimed = next(t for t in (store.read_object_json(ref)
                               for ref in store.load_document()["tasks"])
                   if t["task_id"] == task_id)
    assert claimed["status"] == "running"
    # The revision lands through the normal acceptance path.
    document = store.load_document()
    updated = store.read_object_json(document['pages'][0]['page'])
    updated['customer_visible']['title'] = '现场主管：记录未知版本并核对下一责任'
    # This instruction changes copy only; retain the exact existing notes and
    # speech mapping rather than silently smuggling a second changed layer.
    out = _phase_submit(project, claimed,
                        {"changed_layers": ["page_copy"],
                         "proposals": [{"layer": "page_copy",
                                        "ref": store.put_json_object(updated)}],
                         "diff": {"input_digest": claimed["input_digest"],
                                  "summary": "按现场主管受众调整表述",
                                  "changed_page_ids": ["p1"]}},
                        "input_revision")
    assert out["status"] == "accepted"
    document = store.load_document()
    assert document["content_basis"]["resolved_by_task_id"] == task_id
    assert models.input_alignment(document) == "current"
    # With the reconciliation landed, the same claim no longer sees the block.
    after = eligibility.evaluate(store, document, document, "task.start",
                                 {"task": other, "targets": {"page_ids": ["p1"]}})
    assert "input_reconciliation_pending" not in after["reason_codes"]


# ---------------------------------------------------------------------------
# External review F06: continue's phase progression is not a write side door


def _pending_phase(tmp_path, phase):
    """A real project paused exactly before the named content phase."""
    from test_compose_v2_phases import (_accept_argument, _adopt_direction,  # noqa: E402
                                        _instruction as _phase_instruction,
                                        _project as _phase_project,
                                        _request as _phase_request)
    tmp_path = Path(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    if phase == "framing":
        project, store = _phase_project(tmp_path)
        _phase_request(project, store)
    elif phase == "page_copy":
        project, store = _phase_project(tmp_path)
        _phase_request(project, store)
        _, out = _accept_argument(project, store)
        _adopt_direction(project, store, out["result_refs"][0])
    else:
        project, store = _deck_with_pages(tmp_path)
    document = store.load_document()
    # Explicitly cancel any prior pending work through its public fact channel
    # so this fixture pauses exactly before a fresh phase dispatch. Completed
    # artifacts and old Task/call facts remain in history; no Task is deleted.
    for ref in document["tasks"]:
        task = store.read_object_json(ref)
        if task.get("status") in ("awaiting_host", "running"):
            service.task_cancel(project, task_id=task["task_id"],
                                reason="L1 explicitly isolate the next phase dispatch; retain prior Task and call facts")
    document = store.load_document()
    collaboration.pause_request(project, reason="暂停审视",
                                base_revision=document["revision_id"],
                                operation_id=f"op-pause-{phase}")
    return project, store


def test_a_paused_request_gains_no_phase_tasks_through_continue(tmp_path):
    """F06: with the request paused, `continue` creates no framing, page_copy
    or speech task through the phase-progression side door; the explicit
    resume dispatches the correct next phase exactly once."""
    import pytest

    from test_compose_v2_phases import _instruction as _phase_instruction
    for phase in ("framing", "page_copy", "speech"):
        project, store = _pending_phase(tmp_path / phase, phase)
        before_document = store.load_document()
        tasks_before = len(before_document["tasks"])
        preexisting = [store.read_object_json(ref) for ref in before_document["tasks"]
            if store.read_object_json(ref)['status'] in ('awaiting_host', 'running')
            and (store.read_object_json(ref).get('collaboration_binding') or {}).get('phase') == phase]
        outcome = service.continue_project(project)
        document = store.load_document()
        # The pinned fact: a paused request gains no task. (Reusing a task that
        # already existed before the pause stays legitimate routing.)
        assert len(document["tasks"]) == tasks_before, \
            f"a paused request must not gain a {phase} task"
        if outcome["status"] == "needs_input":
            assert outcome["findings"][0]["code"] == "request_paused", (phase, outcome)
        collaboration.resume_request(
            project, instruction_evidence=_phase_instruction(store, "resume"),
            base_revision=document["revision_id"],
            operation_id=f"op-resume-{phase}")
        resumed = service.continue_project(project)
        document = store.load_document()
        dispatched = [store.read_object_json(ref) for ref in document["tasks"]][tasks_before:]
        if phase == "speech":
            # Content phases are complete: the next step is visual production,
            # and its gated entry refuses it for its own standing reasons
            # (scope/authority/preproduction review) — no task appears through
            # the side door, and the speech phase is not dispatched twice.
            assert resumed["status"] == "needs_input", (phase, resumed)
            assert not dispatched, (phase, [t["task_id"] for t in dispatched])
            assert all(f["field"].startswith("eligibility/")
                       for f in resumed.get("findings", [])), resumed.get("findings")
        else:
            assert resumed["status"] == "awaiting_host", (phase, resumed)
            if preexisting:
                assert not dispatched
                assert [t['task_id'] for t in resumed['pending_tasks']] == [t['task_id'] for t in preexisting]
            else:
                assert len(dispatched) == 1, (phase, [t["task_id"] for t in dispatched])
                assert dispatched[0]["collaboration_binding"]["phase"] == phase
            stable = store.load_document()
            again = service.continue_project(project)
            assert store.load_document() == stable
            assert [t['task_id'] for t in again['pending_tasks']] == [t['task_id'] for t in resumed['pending_tasks']]


@pytest.mark.parametrize('selection', [[], ['argument', 'argument'], ['unknown'], 'argument', [None]])
def test_explicit_recheck_rejects_invalid_units_without_task_or_review_changes(tmp_path, selection):
    from deck_master.models import ModelError
    project, store = _deck_with_pages(tmp_path)
    _production_request(project, store, operation_id='recheck-invalid')
    _accept_preproduction_reviews(project, store)
    before = store.read_current()
    with pytest.raises(ModelError, match='distinct currently required review units'):
        dispatch_with_synthetic_provider(project,
            adapter_context=_independent_adapter(store, store.load_document()), force_units=selection)
    assert store.read_current() == before


def test_explicit_recheck_freezes_owners_reuses_live_task_and_cancel_refuses_late_result(tmp_path):
    from deck_master import native_review, tasks
    project, store = _deck_with_pages(tmp_path)
    _production_request(project, store, operation_id='recheck-cancel')
    _accept_preproduction_reviews(project, store)
    reviewed = store.load_document()
    before_refs = list(reviewed['reviews'])
    before_pages = list(reviewed['pages'])
    adapter = _independent_adapter(store, reviewed)
    assert dispatch_with_synthetic_provider(project, adapter_context=adapter)['status'] == 'already_reviewed'
    first = dispatch_with_synthetic_provider(project, adapter_context=adapter, force_units=['argument'])
    packet = store.read_object_json(first['review_draft_ref'])
    owner_refs = [ref for ref in before_refs if store.read_object_json(ref)['kind'] == 'argument']
    assert packet['required_units'] == ['argument']
    assert packet['review_scope']['owners'] == [{'kind': 'argument', 'review_ref': ref} for ref in owner_refs]
    repeated = dispatch_with_synthetic_provider(project, adapter_context=adapter, force_units=['argument'])
    assert repeated['task']['task_id'] == first['task']['task_id']
    assert repeated['task']['inputs'] == first['task']['inputs']
    # Explicit execution of a running recheck does not get hidden by the old pass,
    # and cannot launch a second native session.
    assert native_review.run(project, task_id=first['task']['task_id'])['status'] == 'running'
    service.task_cancel(project, task_id=first['task']['task_id'])
    cancelled_document = store.load_document()
    task = first['task']
    with pytest.raises(tasks.TaskConflict, match='cancel'):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], result_payload={'kind': 'review', 'reviews': []})
    settled = store.load_document()
    assert settled['change']['operation_id'] == 'settle-' + task['operation_id']
    cancelled_task = tasks._lookup_task(settled, task['task_id'], store)
    assert cancelled_task['status'] == 'cancelled' and cancelled_task['result_refs'] == []
    assert cancelled_task['call_allowances'] == tasks._lookup_task(
        cancelled_document, task['task_id'], store)['call_allowances']
    assert store.load_document()['reviews'] == before_refs and store.load_document()['pages'] == before_pages
    replacement = dispatch_with_synthetic_provider(project, adapter_context=adapter, force_units=['argument'])
    assert replacement['task']['task_id'] != task['task_id']
    assert store.read_object_json(replacement['review_draft_ref'])['review_scope']['owners'] == packet['review_scope']['owners']


def test_native_cli_exposes_explicit_unit_selection_without_changing_default(tmp_path, monkeypatch, capsys):
    from deck_master import cli, native_review
    calls = []
    def observe(project, **kwargs):
        calls.append((project, kwargs))
        return {'status': 'already_reviewed'}
    monkeypatch.setattr(native_review, 'run', observe)
    cli.main(['review', 'native', '--project', str(tmp_path), '--force-unit', 'argument', '--force-unit', 'speech'])
    assert calls[-1][1] == {'task_id': None, 'force_units': ['argument', 'speech']}
    cli.main(['review', 'native', '--project', str(tmp_path)])
    assert calls[-1][1] == {'task_id': None, 'force_units': None}
    capsys.readouterr()


def test_explicit_recheck_cannot_add_a_known_but_unrequired_review_dimension(tmp_path):
    from deck_master.models import ModelError
    project, store = _project(tmp_path)
    assert 'argument' not in content_review.required_units(store, store.load_document())
    before = store.read_current()
    with pytest.raises(ModelError, match='distinct currently required review units'):
        content_review.dispatch_preproduction_review(project, force_units=['argument'])
    assert store.read_current() == before
