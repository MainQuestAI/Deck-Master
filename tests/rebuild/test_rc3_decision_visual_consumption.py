"""F9: public Decision versioning and actual visual consumption.

All instruction/controller evidence is explicitly synthetic L1. These probes
exercise SDK transactions, immutable audit history and fee facts, never an
image model, human decision or independent visual-quality verdict.
"""
import copy
import uuid

import pytest

from deck_master import candidates, collaboration, dependency_slices, eligibility, generation, models, production, tasks
from deck_master.native_image_evidence import NativeImageRuntime
import test_rc3_native_visual_reuse as reuse
from test_rc3_design_workflows import confirmed, dispatch
from test_rc3_notes_visual_inputs import enf
from test_rc3_restyle_workflows import begin


def _value(store, **overrides):
    return {"topic": "style", "decision_id": "stable-style", "subject_refs": [],
        "value": {"palette": "blue"}, "disposition": "accepted", "authority_mode": "direct_user",
        "scope": enf._scope(page_ids=["p1"]), "instruction_evidence": enf._declared(store), **overrides}


def _record(path, store, value):
    return collaboration.record_decision(path, input=value, base_revision=store.current_revision_id(),
        operation_id=str(uuid.uuid4()))["decision_ref"]


def _setup(tmp_path, **overrides):
    path, store, grant = reuse._project(tmp_path)
    value = _value(store, **overrides)
    ref = _record(path, store, value)
    recipe = confirmed(path, store)
    task = dispatch(path, store, recipe, ["p1"])[0]
    return path, store, grant, value, ref, recipe, task


def _resolved(store, recipe):
    doc = store.load_document()
    return production.resolve_generation_design(store, doc, doc["pages"][0], recipe_ref=recipe["recipe_ref"])


@pytest.mark.parametrize("phase", ["before_context", "after_context", "after_candidate"])
def test_same_decision_new_audit_version_keeps_native_candidate_and_exact_old_digest(tmp_path, phase):
    path, store, _, value, old_ref, recipe, task = _setup(tmp_path)
    original = _resolved(store, recipe)
    original_bytes = store.read_object_bytes(old_ref)
    sent = begin(path, store, task)
    frozen_bytes = store.read_object_bytes(sent[0]["request_ref"])
    budget = eligibility.authorization_budget(store, store.load_document(), reuse._authorization_ref(task))
    # This is exactly the 5db candidate digest encoding, before F9 normalized
    # Decision identity/value comparison. Keep it rather than accepting two hashes.
    old_encoding = {key: item for key, item in original.items() if key != "content_basis"}
    old_encoding["consumed_basis"] = original["content_basis"]["consumed"]
    old_digest = models.sha256_bytes(models.canonical_json_bytes(old_encoding))
    candidate_id = None
    with NativeImageRuntime(sent[3]).bound():
        context = reuse._issue(store, task, sent) if phase != "before_context" else None
        if phase == "after_candidate":
            assert reuse._settle(store, task, sent, context)["native_observation_status"] == "accepted"
            candidate_id = reuse.accept(path, store, task, sent)["candidate_ids"][0]
        new_ref = _record(path, store, {**value, "replaces": old_ref})
        current = _resolved(store, recipe)
        assert current["content_basis"]["decision_refs"] == [new_ref]
        assert original["content_basis"]["decision_refs"] == [old_ref]
        assert production.consumed_design(original, store=store) == production.consumed_design(current, store=store)
        assert tasks.task_inputs_current(store, store.load_document(), task)
        if phase != "after_candidate":
            if context is None:
                context = reuse._issue(store, task, sent)
            assert reuse._settle(store, task, sent, context)["native_observation_status"] == "accepted"
            candidate_id = reuse.accept(path, store, task, sent)["candidate_ids"][0]
    shown = candidates.show(path, candidate_id=candidate_id)
    assert shown["generation_basis"]["status"] == "current"
    assert shown["candidate"]["generation_basis"]["design_digest"] == old_digest
    assert store.read_object_bytes(old_ref) == original_bytes
    assert store.read_object_bytes(sent[0]["request_ref"]) == frozen_bytes
    reuse._assert_call_facts(store, task, sent, budget, outcome="consumed")


@pytest.mark.parametrize("change", ["value", "scope", "layers", "topic", "disposition", "status", "identity"])
@pytest.mark.parametrize("outcome", ["consumed", "unknown"])
def test_changed_consumed_decision_rejects_native_and_adoption_but_keeps_sent_call(tmp_path, change, outcome):
    path, store, _, value, old_ref, recipe, task = _setup(tmp_path)
    sent = begin(path, store, task)
    frozen_bytes = store.read_object_bytes(sent[0]["request_ref"])
    original = copy.deepcopy(store.load_document())
    budget = eligibility.authorization_budget(store, original, reuse._authorization_ref(task))
    with NativeImageRuntime(sent[3]).bound():
        context = reuse._issue(store, task, sent)
        update = {**value, "replaces": old_ref}
        if change == "value":
            update["value"] = {"palette": "green"}
        elif change == "scope":
            update["scope"] = enf._scope(page_ids=["p2"])
        elif change == "layers":
            update["scope"] = enf._scope(page_ids=["p1"], layers=["blueprint"])
        elif change == "topic":
            update["topic"] = "speech"
        elif change == "disposition":
            update["disposition"] = "rejected"
        elif change == "identity":
            # A second real Decision may have the same effective value hash,
            # but its separate identity remains consumed.
            update.pop("replaces")
            update["decision_id"] = "different-style"
        ref = _record(path, store, update)
        if change == "status":
            # Public record_decision always writes active. Inject a withdrawn
            # head only in this disposable schema-valid L1 project to probe
            # status consumption without inventing a public status writer.
            doc = store.load_document()
            record = store.read_object_json(ref)
            record.update(status="withdrawn", replaces=ref)
            models.validate_decision_semantics(record)
            doc["collaboration"]["decisions"].append(store.put_json_object(record))
            from test_rc3_adopted_design_handoff import _commit
            _commit(store, doc, "Explicit synthetic withdrawn Decision status")
        assert not tasks.task_inputs_current(store, store.load_document(), task)
        settled = reuse._settle(store, task, sent, context, outcome=outcome)
    assert settled["native_observation_status"] == "rejected"
    reuse._assert_call_facts(store, task, sent, budget, outcome=outcome)
    with pytest.raises((eligibility.EligibilityBlocked, tasks.TaskConflict, generation.GenerationError)):
        reuse.accept(path, store, task, sent)
    assert store.load_document()["pages"] == original["pages"]
    assert store.load_document().get("candidates", []) == original.get("candidates", [])
    assert store.read_object_bytes(sent[0]["request_ref"]) == frozen_bytes


@pytest.mark.parametrize("topic,page_ids", [("style", ["p2"]), ("speech", ["p1"])])
def test_unconsumed_decision_updates_do_not_pollute_p1(tmp_path, topic, page_ids):
    path, store, _, value, ref, recipe, task = _setup(tmp_path, topic=topic, scope=enf._scope(page_ids=page_ids))
    before = _resolved(store, recipe)
    _record(path, store, {**value, "value": {"palette": "green"}, "replaces": ref})
    after = _resolved(store, recipe)
    assert before["content_basis"]["decision_refs"] == after["content_basis"]["decision_refs"] == []
    assert production.consumed_design(before, store=store) == production.consumed_design(after, store=store)
    assert tasks.task_inputs_current(store, store.load_document(), task)


def test_consumed_normalization_cannot_hide_foreign_or_mismatched_decision_refs(tmp_path):
    _, store, _, _, ref, recipe, _ = _setup(tmp_path)
    resolved = _resolved(store, recipe)
    original = copy.deepcopy(resolved)
    foreign = store.read_object_json(ref)
    foreign["project_id"] = "other-project"
    foreign_ref = store.put_json_object(foreign)
    resolved["content_basis"]["decision_refs"] = [foreign_ref]
    resolved["content_basis"]["consumed"]["decision_slices"][0]["decision_ref"] = foreign_ref
    with pytest.raises(models.ModelError, match="actual project/Page"):
        production.consumed_design(resolved, store=store)
    resolved["content_basis"]["decision_refs"] = [ref]
    with pytest.raises(models.ModelError, match="actual audit Refs"):
        production.consumed_design(resolved, store=store)
    assert original["content_basis"]["decision_refs"] == [ref]


def test_equal_effective_values_from_different_decision_identities_do_not_collapse(tmp_path):
    path, store, _, value, _, recipe, _ = _setup(tmp_path)
    old = _resolved(store, recipe)
    new_ref = _record(path, store, {**value, "decision_id": "another-style"})
    sliced = dependency_slices.build_slice(store, store.load_document(), kind="decision",
        identity="another-style", projection="effective")
    assert sliced["sha256"] == old["content_basis"]["consumed"]["decision_slices"][0]["sha256"]
    # Isolate one validated registered decision per context. This read-only
    # contrast tests identity, not a production resolver's two-decision union.
    other = copy.deepcopy(old)
    other["content_basis"]["decision_refs"] = [new_ref]
    other["content_basis"]["consumed"]["decision_slices"] = [{"decision_ref": new_ref, "sha256": sliced["sha256"]}]
    assert production.consumed_design(old, store=store) != production.consumed_design(other, store=store)


@pytest.mark.parametrize("change", ["value", "scope", "disposition"])
def test_candidate_already_received_still_stales_on_real_decision_change(tmp_path, change):
    path, store, _, value, ref, _, task = _setup(tmp_path)
    sent = begin(path, store, task)
    with NativeImageRuntime(sent[3]).bound():
        context = reuse._issue(store, task, sent)
        assert reuse._settle(store, task, sent, context)["native_observation_status"] == "accepted"
    candidate_id = reuse.accept(path, store, task, sent)["candidate_ids"][0]
    candidate_before = candidates.show(path, candidate_id=candidate_id)
    assert candidate_before["generation_basis"]["status"] == "current"
    update = {**value, "replaces": ref}
    if change == "value":
        update["value"] = {"palette": "green"}
    elif change == "scope":
        update["scope"] = enf._scope(page_ids=["p2"])
    else:
        update["disposition"] = "rejected"
    _record(path, store, update)
    current = candidates.show(path, candidate_id=candidate_id)
    assert current["generation_basis"]["status"] == "changed"
    assert "design_digest" in current["generation_basis"]["changed_fields"]
    assert current["candidate"] == candidate_before["candidate"]
    doc = store.load_document()
    with pytest.raises(candidates.AdoptionConflict, match="candidate"):
        candidates.plan(path, input={"schema_version": "candidate_selection.v1", "project_id": doc["project_id"],
            "base_revision": doc["revision_id"], "candidate_ids": [candidate_id]})
    assert generation.show(path, attempt_id=sent[1]["attempt_id"])["call"]["state"] == "consumed"
