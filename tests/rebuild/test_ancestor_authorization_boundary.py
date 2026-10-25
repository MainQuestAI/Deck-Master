"""Synthetic public-API evidence: withdrawn ancestry cannot claim or adopt.

The call ledger cases record synthetic observations only; no provider is called.
"""
from copy import deepcopy

import pytest

from deck_master import collaboration, dependency_slices, eligibility, service, tasks
from test_eligibility_enforcement import _project, _scope, _start, _grant


ACTIONS = ("dispatch.host_task", "task.start", "task.accept", "allowance.allocate", "call.begin")


def chain_task(tmp_path, *, kind="repair", calls=0, page_basis=False):
    project, store = _project(tmp_path)
    scope = _scope(page_ids=["p1"], layers=["review"] if kind == "review" else ["page_copy", "svg", "review"])
    _start(project, store, intent="edit", scope=scope)
    basis = ([dependency_slices.make_dependency_slice(store, store.load_document(),
        kind="artifact", identity="page:p1", projection="content")] if page_basis else [])
    chain = []
    for name, mode in (("grandparent", "delegate"), ("parent", "delegate"), ("child", "execute")):
        chain.append(_grant(project, store, actions=ACTIONS, mode=mode, scope=scope,
            operation_id="synthetic-" + name, max_external_calls=calls, basis=basis,
            **({"parent_authorization_ref": chain[-1]["authorization_ref"]} if chain else {})))
    task = service.open_host_task(store, kind=kind, page_ids=["p1"],
        instruction="Synthetic local ancestor-boundary check; no model execution")
    assert task["collaboration_binding"]["authorization_ref"] == chain[-1]["authorization_ref"]
    return project, store, chain, task, scope


def claim(project, task):
    return service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-local-host",
        supported_protocols=[task["protocol_version"]] if task.get("protocol_version") else [],
        capabilities=task.get("required_capabilities") or [])


def withdraw(project, store, authorization):
    collaboration.revoke_authorization(project, authorization_id=authorization["authorization_id"],
        reason="Synthetic explicit withdrawal", base_revision=store.current_revision_id(),
        operation_id="synthetic-withdraw")


def payload(store):
    page = deepcopy(store.read_object_json(store.load_document()["pages"][0]["page"]))
    page["customer_visible"]["body_blocks"][0]["text"] = "Synthetic repaired body."
    return {"kind": "repair", "pages": [page]}


def accept(project, task, value):
    return service.accept_result(project, task_id=task["task_id"],
        operation_id=task["operation_id"], produced_against=task["produced_against"], result_payload=value)


def assert_withdrawal(error):
    assert error.value.decision["reason_codes"] == ["authorization_revoked"]
    assert error.value.decision["next_action"] == (
        "the withdrawal stands; a new authorization requires a new explicit user instruction")


@pytest.mark.parametrize("kind", ["review", "repair"])
@pytest.mark.parametrize("ancestor", [0, 1, 2], ids=["grandparent", "parent", "direct"])
def test_withdrawal_stops_real_task_claim_without_writes(tmp_path, kind, ancestor):
    project, store, chain, task, _ = chain_task(tmp_path, kind=kind)
    withdraw(project, store, chain[ancestor])
    before = store.load_document()
    effectiveness = dependency_slices.authorization_effectiveness(store, before, chain[-1]["authorization_ref"])
    assert not effectiveness["effective"]
    if ancestor != 2:
        assert "ancestor_authorization_revoked" in effectiveness["reasons"]
        assert "parent_ineffective" in effectiveness["reasons"]
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        claim(project, task)
    assert_withdrawal(error)
    assert store.load_document() == before
    assert tasks._lookup_task(before, task["task_id"], store)["status"] == "awaiting_host"


@pytest.mark.parametrize("ancestor", [0, 1, 2], ids=["grandparent", "parent", "direct"])
def test_withdrawal_stops_running_repair_adoption_without_changing_current(tmp_path, ancestor):
    project, store, chain, task, _ = chain_task(tmp_path)
    claim(project, task)
    value = payload(store)
    withdraw(project, store, chain[ancestor])
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        accept(project, task, value)
    assert_withdrawal(error)
    assert store.load_document() == before
    assert store.operation_receipt(task["operation_id"]) is None


def test_effective_chain_still_claims_and_adopts_the_actual_repair(tmp_path):
    project, store, _, task, _ = chain_task(tmp_path)
    before = store.load_document()
    assert claim(project, task)["status"] == "running"
    value = payload(store)
    assert accept(project, task, value)["status"] == "accepted"
    after = store.load_document()
    assert after["pages"][0]["page"] != before["pages"][0]["page"]
    assert store.read_object_json(after["pages"][0]["page"]) == value["pages"][0]


@pytest.mark.parametrize("ancestor", [None, 0, 1], ids=["effective", "grandparent-withdrawn", "parent-withdrawn"])
def test_explicit_background_permission_preserves_only_effective_bound_work(tmp_path, ancestor):
    project, store, chain, task, scope = chain_task(tmp_path)
    old_request = store.load_document()["collaboration"]["request"]["request_id"]
    _start(project, store, operation_id="synthetic-background-request", intent="edit", scope=scope,
        background_request_ids=[old_request])
    if ancestor is not None:
        withdraw(project, store, chain[ancestor])
        before = store.load_document()
        with pytest.raises(eligibility.EligibilityBlocked) as error:
            claim(project, task)
        assert_withdrawal(error)
        assert store.load_document() == before
    else:
        assert claim(project, task)["status"] == "running"
        assert accept(project, task, payload(store))["status"] == "accepted"


def test_another_active_grant_cannot_take_over_a_withdrawn_task(tmp_path):
    project, store, chain, task, scope = chain_task(tmp_path)
    other = _grant(project, store, actions=ACTIONS, scope=scope,
        operation_id="synthetic-unrelated-grant", max_external_calls=0)
    withdraw(project, store, chain[0])
    before = store.load_document()
    assert dependency_slices.authorization_effectiveness(store, before, other["authorization_ref"])["effective"]
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        claim(project, task)
    assert_withdrawal(error)
    assert store.load_document() == before


@pytest.mark.parametrize("surface", ["call_settle", "accept_result"])
def test_withdrawal_keeps_settlement_and_cancellation_facts_without_adopting(tmp_path, surface):
    project, store, chain, task, _ = chain_task(tmp_path, calls=1)
    claim(project, task)
    allowance = tasks.allocate_call_allowances(store, task_id=task["task_id"], count=1)["allowance_ids"][0]
    tasks.call_begin(store, task_id=task["task_id"], allowance_id=allowance, execution_ref="synthetic-local-host")
    withdraw(project, store, chain[0])
    before = store.load_document()
    report = b'{"evidence_level":"synthetic-local","outcome":"consumed"}'
    if surface == "call_settle":
        tasks.call_settle(store, task_id=task["task_id"], allowance_id=allowance,
            outcome="consumed", report_bytes=report)
    else:
        staging = store.staging_dir / task["operation_id"]
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "call.json").write_bytes(report)
        value = {**payload(store), "files": [{"file_id": "call", "path": "call.json", "media_type": "application/json"}],
            "usage_events": [{"allowance_id": allowance, "outcome": "consumed", "evidence_file_ids": ["call"]}]}
        with pytest.raises(eligibility.EligibilityBlocked) as error:
            accept(project, task, value)
        assert_withdrawal(error)
        assert store.operation_receipt(task["operation_id"]) is None
    after = store.load_document()
    for key in ("pages", "reviews", "outputs"):
        assert after[key] == before[key]
    settled = tasks._lookup_task(after, task["task_id"], store)
    assert settled["call_allowances"][0]["state"] == "consumed"
    assert settled["call_allowances"][0]["evidence"]
    assert service.task_cancel(project, task_id=task["task_id"], reason="Synthetic stop")["status"] == "cancelled"
    final = store.load_document()
    assert final["pages"] == before["pages"]
    assert tasks._lookup_task(final, task["task_id"], store)["call_allowances"] == settled["call_allowances"]


def test_completed_acceptance_replays_exactly_after_parent_withdrawal(tmp_path):
    project, store, chain, task, _ = chain_task(tmp_path)
    claim(project, task)
    value = payload(store)
    accepted = accept(project, task, value)
    withdraw(project, store, chain[0])
    current = store.load_document()
    replay = accept(project, task, value)
    assert replay["status"] == "already_applied"
    assert replay["revision_id"] == accepted["revision_id"]
    assert replay["current_revision_id"] == current["revision_id"]
    assert replay["operation_result"] == accepted["operation_result"] == store.operation_receipt(task["operation_id"])["response"]
    assert store.load_document() == current
    changed = deepcopy(value)
    changed["pages"][0]["customer_visible"]["body_blocks"][0]["text"] += " Different payload."
    with pytest.raises(tasks.TaskConflict):
        accept(project, task, changed)
    assert store.load_document() == current


@pytest.mark.parametrize("current_withdrawn_head", [False, True])
def test_unreadable_ancestor_blocks_claim_but_keeps_cancellation(tmp_path, current_withdrawn_head):
    project, store, chain, task, _ = chain_task(tmp_path)
    ref = chain[0]["authorization_ref"]
    if current_withdrawn_head:
        withdraw(project, store, chain[0])
        ref, _ = dependency_slices._resolve_current(store, store.load_document(), "authorizations",
            "authorization_id", ref)
        assert ref != chain[0]["authorization_ref"]
    path = store.project_root / ref["path"]
    path.write_bytes(b"unreadable synthetic ancestor")
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        claim(project, task)
    assert error.value.decision["reason_codes"] == ["binding_invalid"]
    assert store.load_document() == before
    assert service.task_cancel(project, task_id=task["task_id"], reason="Synthetic damaged-ancestor stop")["status"] == "cancelled"


def test_nonwithdrawal_authority_failure_does_not_claim_a_revocation(tmp_path):
    project, store, chain, task, _ = chain_task(tmp_path)
    collaboration.pause_request(project, reason="Synthetic request pause", base_revision=store.current_revision_id(),
        operation_id="synthetic-pause")
    before = store.load_document()
    effectiveness = dependency_slices.authorization_effectiveness(store, before, chain[-1]["authorization_ref"])
    assert not effectiveness["effective"] and "ancestor_authorization_revoked" not in effectiveness["reasons"]
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        claim(project, task)
    assert "request_paused" in error.value.decision["reason_codes"]
    assert "authorization_revoked" not in error.value.decision["reason_codes"]
    assert store.load_document() == before


def test_existing_binding_basis_stale_keeps_its_reissue_diagnostic(tmp_path):
    from deck_master.editing import edit_page

    project, store, chain, task, _ = chain_task(tmp_path, page_basis=True)
    before = store.load_document()
    entry = before["pages"][0]
    page = deepcopy(store.read_object_json(entry["page"]))
    page["customer_visible"]["body_blocks"][0]["text"] += " Current manuscript changed."
    edit_page(project, page=page, base_revision=before["revision_id"],
        page_hash=entry["page"]["sha256"], operation_id="synthetic-manuscript-edit")
    current = store.load_document()
    authorization = dependency_slices.authorization_effectiveness(store, current, chain[-1]["authorization_ref"])
    assert not authorization["effective"] and "basis_stale" in authorization["reasons"]
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        claim(project, task)
    assert error.value.decision["reason_codes"] == ["binding_stale"]
    assert error.value.decision["next_action"] == "re-dispatch the task with a recomputed binding; do not accept this result"
    assert store.load_document() == current


def test_zero_call_review_without_bound_authorization_still_claims(tmp_path):
    project, store = _project(tmp_path)
    _start(project, store, intent="review_only", scope=_scope(page_ids=["p1"], layers=["review"]))
    task = service.open_host_task(store, kind="review", page_ids=["p1"], instruction="Synthetic read-only review")
    assert task["collaboration_binding"]["authorization_ref"] is None
    assert claim(project, task)["status"] == "running"
