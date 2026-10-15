"""Campaign engineering checks. Synthetic observations are never Host evidence.

These tests exercise actual public SDK calls and recorder rejection paths. They
do not run a benchmark Writer, establish GENTRY admission, or grade content.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from deck_master.store import Store


SCRIPT = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/controller.py"
SPEC = importlib.util.spec_from_file_location("rc3_campaign_controller_test", SCRIPT)
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def fixture(tmp_path):
    project = tmp_path / "p"
    source = tmp_path / "source.txt"
    source.write_text("Synthetic engineering material: the ledger can contain an unknown field.\n")
    journal = c.Journal(tmp_path / "r")
    state = {"project": str(project), "arm": "B", "case": "GENTRY",
             "materials": [c.reference(source)],
             "budget": {"initial_writer": 5, "feedback": 1, "repair_cycles": 1, "repair_writer": 3}}
    grammar = tmp_path / "grammar.json"
    c.save(grammar, {"status": "UNIT_TEST_TECHNICAL_GRAMMAR_NOT_ADMISSION"})
    exposure = tmp_path / "exposure.json"
    c.save(exposure, {"status": "FROZEN", "excluded_identities": ["/root/preparer"]})
    import deck_master
    config = {"grammar": c.reference(grammar), "exposure_registry": c.reference(exposure),
              "installations": {"B": {"module_file": deck_master.__file__}}}
    c.sdk_operation(journal, state, "service.create", {"brief": "Synthetic engineering only", "sources": [str(source)]})
    store = Store(project)
    task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"])
    return journal, state, config, store, task


def fake_invocation(tmp_path, dispatch, identity="/root/unit_writer", *, tool="collaboration.spawn_agent"):
    path = tmp_path / ("invoke-" + str(len(list(tmp_path.glob("invoke-*")))) + ".json")
    c.save(path, {"observation_kind": c.OBSERVER_KIND, "assurance": "host_attested",
                 "observed_at_utc": c.now(), "project_id": dispatch["project_id"], "task_id": dispatch["task_id"],
                 "UNIT_TEST_SYNTHETIC_NOT_NATIVE_EVIDENCE": True,
                 "spawn": {"tool": tool, "canonical_task_name": identity, "returned_task_name": identity,
                           "fork_turns": "none", "inherited_identities": []}})
    return path


def test_journal_detects_tamper_and_never_replaces_original(tmp_path):
    journal = c.Journal(tmp_path)
    journal.append("first", {"actual": "unknown"})
    journal.append("second", {})
    first = tmp_path / "journal/000001.json"
    with pytest.raises(FileExistsError):
        c.save(first, {"pretend": "replacement"})
    first.write_bytes(first.read_bytes().replace(b"unknown", b"changed"))
    with pytest.raises(c.CampaignError, match="chain changed"):
        journal.events()


def test_actual_create_and_inputs_update_keep_real_input_revision(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    assert task["protocol_version"] == "compose.v2"
    assert len(store.load_document()["tasks"]) == 1  # no second framing/migration
    c.sdk_operation(journal, state, "service.inputs_update", {
        "patch": {"reason": "Neutral actual input-change route", "task_patch": {"audience": "New staff"}},
        "base_revision": store.current_revision_id(), "operation_id": "neutral-input-update"})
    pending = [store.read_object_json(ref) for ref in store.load_document()["tasks"]]
    revisions = [t for t in pending if t.get("intent") == "input_revision" and t["status"] == "awaiting_host"]
    assert len(revisions) == 1
    assert any(t["task_id"] == task["task_id"] and t["status"] == "superseded" for t in pending)
    packet = c.prepare(journal, state, config, "reconciliation", revisions[0]["task_id"], "initial_writer")
    metadata = c.read(Path(packet["packet"]) / "envelope-metadata.json")
    assert metadata["variant"] == "input_revision"
    assert not any(e["data"].get("operation") == "service.task_cancel" for e in journal.events())


@pytest.mark.parametrize("operation", ["service.task_cancel", "content_production.open_phase_task", "service.accept_result"])
def test_public_operations_cannot_cancel_force_phase_or_bypass_native(tmp_path, operation):
    journal = c.Journal(tmp_path)
    with pytest.raises(c.CampaignError, match="not exposed"):
        c.sdk_operation(journal, {"project": str(tmp_path / "p")}, operation, {})
    assert journal.events() == []


def test_sdk_exception_leaves_unknown_intent_until_actual_observation(tmp_path):
    journal = c.Journal(tmp_path / "r")
    with pytest.raises(RuntimeError, match="transport interrupted"):
        c.record_sdk(journal, "unit-interrupted", {}, lambda: (_ for _ in ()).throw(RuntimeError("transport interrupted")), key="op1")
    assert "op1" in journal.unfinished()
    with pytest.raises(c.CampaignError, match="unresolved"):
        c.record_sdk(journal, "unit-wrong-retry", {}, lambda: {"fake": "pass"})
    observation = tmp_path / "actual-query.json"
    c.save(observation, {"status": "not_found", "UNIT_TEST_ONLY": True})
    record = tmp_path / "reconcile.json"
    c.save(record, {"operation_key": "op1", "observed_state": "not_found",
                    "runtime_observations": [c.reference(observation)]})
    assert c.reconcile(journal, record) == {"status": "recorded_no_retry", "observed_state": "not_found"}
    # Reconciliation is an explicit observation, never an automatic retry.
    assert not journal.unfinished()
    assert len([e for e in journal.events() if e["kind"] == "sdk_intent"]) == 1


def test_six_actual_invocations_are_recorded_not_silently_rebudgeted(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    dispatch = c.prepare(journal, state, config, "initial", task["task_id"], "initial_writer")
    actual = []
    for index in range(6):
        path = fake_invocation(tmp_path, dispatch, f"/root/unit_writer_{index}")
        actual.append(c.begin_native(journal, state, config, "initial", path))
    assert [item["within_budget"] for item in actual] == [True] * 5 + [False]
    assert len([e for e in journal.events() if e["kind"] == "native_begun"]) == 6


@pytest.mark.parametrize("role", ["production", "post_comparison_writer", "extra_writer"])
def test_compose_cannot_evade_equal_budget_with_role_label(tmp_path, role):
    journal, state, config, store, task = fixture(tmp_path)
    with pytest.raises(c.CampaignError):
        c.prepare(journal, state, config, "evasion", task["task_id"], role)


def test_raw_invalid_json_is_frozen_before_rejection(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    dispatch = c.prepare(journal, state, config, "initial", task["task_id"], "initial_writer")
    ordinal = c.begin_native(journal, state, config, "initial", fake_invocation(tmp_path, dispatch))["ordinal"]
    c.claim_read(journal, state, "initial", ordinal, "/root/unit_writer")
    invocation, target = c.execution(journal, "initial", ordinal)
    raw = tmp_path / "malformed.txt"
    raw.write_bytes(b"This is not an SDK envelope. Original bytes must survive.\n")
    observation = tmp_path / "completion.json"
    c.save(observation, {"observation_kind": c.OBSERVER_KIND, "assurance": "host_attested",
        "project_id": dispatch["project_id"], "task_id": task["task_id"],
        "observed_at_utc": c.now(), "model_output_bytes_sha256": c.reference(raw)["sha256"],
        "method_release": dispatch["method_release"], "all_method_bytes_read": True,
        "method_read_record_sha256": c.reference(target / "method-read-record.json")["sha256"],
        "completion": {"sender": invocation["executor"], "message_type": "FINAL_ANSWER",
                       "status_observation_tool": "collaboration.list_agents", "observed_status": "completed",
                       "observed_completed_agents": [invocation["executor"]], "raw_final_message": "UNIT TEST ONLY"}})
    revision = store.current_revision_id()
    with pytest.raises(json.JSONDecodeError):
        c.observe(journal, state, "initial", ordinal, raw, c.reference(raw)["sha256"],
                  observation, c.reference(observation)["sha256"])
    assert (target / "raw-native-output").read_bytes() == raw.read_bytes()
    assert not (target / "observed.json").exists()
    assert store.current_revision_id() == revision


def test_preparer_exclusion_is_not_waived_by_a_new_role(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    dispatch = c.prepare(journal, state, config, "initial", task["task_id"], "initial_writer")
    with pytest.raises(c.CampaignError, match="excluded"):
        c.begin_native(journal, state, config, "initial", fake_invocation(tmp_path, dispatch, "/root/preparer"))
    assert not any(e["kind"] == "native_begun" for e in journal.events())


def test_changed_generation_parameters_refused_before_any_sdk_write(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    revision = store.current_revision_id()
    with pytest.raises(c.CampaignError, match="opaque-background"):
        c.sdk_operation(journal, state, "generation.freeze", {"task_id": task["task_id"],
            "input": {"parameters": {"transparent_background": True}},
            "base_revision": revision, "operation_id": "wrong-parameter"})
    assert store.current_revision_id() == revision
    assert not journal.unfinished()


def test_scripted_answers_need_actual_trigger_and_preregistered_timepoint(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    message = tmp_path / "later.txt"
    message.write_text("Later neutral change, not initial input.")
    config["cases"] = {"GENTRY": {"events": {"later": {"planned_dispatch": True,
        "message": c.reference(message), "required_snapshots": ["equal_budget_evaluated"], "source": "unit-only"}}}}
    trigger = tmp_path / "trigger.json"
    c.save(trigger, {"event_id": "later", "assurance": "host_attested", "actual_trigger_satisfied": True,
                     "actual_trigger_explanation": "UNIT TEST, not an actual question",
                     "source_observations": [c.reference(message)]})
    with pytest.raises(c.CampaignError, match="premature"):
        c.scripted_event(journal, state, config, "later", trigger)
    assert not (journal.root / "messages").exists()


def test_empty_manuscript_never_becomes_qualified(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    with pytest.raises(c.CampaignError, match="central"):
        c.snapshot(journal, state, "qualified_for_owner")
    assert not (journal.root / "snapshots/qualified_for_owner.json").exists()


def test_plain_json_cannot_mint_independent_context():
    from deck_master import review_evidence
    with pytest.raises(review_evidence.EvidenceRejected, match="opaque"):
        review_evidence.context_payload({"independent_review_receipts": [{"verified": True}]})


def test_store_snapshot_is_not_a_native_complete_draft(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    with pytest.raises(c.CampaignError, match="Store is not the raw draft"):
        c.snapshot(journal, state, "original_complete")
    assert not (journal.root / "snapshots/original_complete.json").exists()


def test_actual_sdk_consumes_exact_frozen_synthetic_framing_without_adopting_it(tmp_path):
    journal, state, config, store, task = fixture(tmp_path)
    dispatch = c.prepare(journal, state, config, "initial", task["task_id"], "initial_writer")
    ordinal = c.begin_native(journal, state, config, "initial", fake_invocation(tmp_path, dispatch))["ordinal"]
    c.claim_read(journal, state, "initial", ordinal, "/root/unit_writer")
    invocation, target = c.execution(journal, "initial", ordinal)
    envelope = c.read(target.parent.parent / "envelope-metadata.json")
    envelope["payload"] = {"narrative": {"schema_version": "narrative.v1", "narrative_id": "neutral-framing",
        "version": 1, "project_id": store.load_document()["project_id"], "origin": "host_composed", "maturity": "framing",
        "input_basis": [], "communication_job": {"mode": "explain", "audience_fact_key": "task.audience",
            "audience_question": "Which ledger field is unknown?", "desired_outcome": "Record missing fields honestly",
            "observable_success": "The reader identifies an unprovided field", "use_mode": "read_alone", "primary_use": "read_alone"},
        "central_node_id": None, "nodes": [], "edges": [], "issues": [], "alternatives": [], "previous_ref": None}}
    raw = tmp_path / "native-result.json"
    c.save(raw, envelope)
    observation = tmp_path / "completion.json"
    c.save(observation, {"observation_kind": c.OBSERVER_KIND, "assurance": "host_attested",
        "project_id": dispatch["project_id"], "task_id": task["task_id"], "observed_at_utc": c.now(),
        "model_output_bytes_sha256": c.reference(raw)["sha256"], "method_release": dispatch["method_release"],
        "all_method_bytes_read": True, "method_read_record_sha256": c.reference(target / "method-read-record.json")["sha256"],
        "completion": {"sender": invocation["executor"], "message_type": "FINAL_ANSWER",
            "status_observation_tool": "collaboration.list_agents", "observed_status": "completed",
            "observed_completed_agents": [invocation["executor"]], "raw_final_message": "SYNTHETIC UNIT FIXTURE, NOT A NATIVE CALL"}})
    c.observe(journal, state, "initial", ordinal, raw, c.reference(raw)["sha256"], observation, c.reference(observation)["sha256"])
    accepted = c.accept(journal, state, "initial", ordinal)
    assert accepted["status"] == "accepted" and accepted["variant"] == "framing"
    assert store.load_document().get("narrative") is None  # proposal requires a separate genuine decision
    assert (target / "raw-native-output").read_bytes() == raw.read_bytes()
    assert c.task_for(store, task["task_id"])["status"] == "completed"
    assert not journal.unfinished()


@pytest.mark.parametrize("wrong_ref", [False, True, "missing", "duplicate", "extra", "corrupted", "foreign", "invalid",
                                     "framing", "wrong-task", "wrong-operation", "wrong-basis", "wrong-eligibility",
                                     "outer-schema", "stale", "bad-completion", "bad-first-hash"])
def test_input_revision_objects_are_frozen_before_sdk_storage_and_never_rewritten(tmp_path, wrong_ref):
    from deck_master.models import canonical_json_bytes, ModelError
    from deck_master.store import StoreError
    journal, state, config, store, initial = fixture(tmp_path)
    if wrong_ref == "framing":
        task = initial
    else:
        c.sdk_operation(journal, state, "service.inputs_update", {"patch": {"reason": "Neutral change",
            "task_patch": {"audience": "Engineering reader"}}, "base_revision": store.current_revision_id(), "operation_id": "objects-update"})
        task = next(store.read_object_json(ref) for ref in store.load_document()["tasks"]
                    if store.read_object_json(ref).get("intent") == "input_revision")
    dispatch = c.prepare(journal, state, config, "reconcile", task["task_id"], "initial_writer")
    ordinal = c.begin_native(journal, state, config, "reconcile", fake_invocation(tmp_path, dispatch))["ordinal"]
    c.claim_read(journal, state, "reconcile", ordinal, "/root/unit_writer")
    invocation, target = c.execution(journal, "reconcile", ordinal)
    narrative = {"schema_version": "narrative.v1", "narrative_id": "neutral-reconciled", "version": 1,
        "project_id": dispatch["project_id"], "origin": "host_composed", "maturity": "framing", "input_basis": [],
        "communication_job": {"mode": "explain", "audience_fact_key": "task.audience", "audience_question": "Which fields are missing?",
            "desired_outcome": "Record unknowns honestly", "observable_success": "Identify missing information",
            "use_mode": "read_alone", "primary_use": "read_alone"}, "central_node_id": None,
        "nodes": [], "edges": [], "issues": [], "alternatives": [], "previous_ref": None}
    if wrong_ref == "invalid":
        narrative.pop("input_basis")
    hashed = c.digest(canonical_json_bytes(narrative))
    expected = {"path": f".deckmaster/objects/{hashed[:2]}/{hashed}.json", "sha256": hashed}
    obj = target.parent.parent / "native-narrative.json"
    c.save(obj, narrative)
    envelope = c.read(target.parent.parent / "envelope-metadata.json")
    envelope["variant"] = "input_revision"
    envelope["payload"] = {"changed_layers": ["narrative"], "proposals": [{"layer": "narrative", "ref": expected}],
        "diff": {"input_digest": task["input_digest"], "summary": "The audience is now the engineering reader; framing is reconciled.",
                 "changed_page_ids": [], "page_order": []}}
    if wrong_ref == "missing":
        envelope["payload"]["proposals"].append({"layer": "plan", "ref": {"path": ".deckmaster/objects/00/" + "0" * 64 + ".json", "sha256": "0" * 64}})
    if wrong_ref == "duplicate":
        envelope["payload"]["proposals"].append({"layer": "narrative", "ref": expected})
    if wrong_ref == "foreign":
        envelope["payload"]["proposals"][0]["ref"] = {**expected, "path": ".deckmaster/objects/ff/" + hashed + ".json"}
    if wrong_ref == "wrong-task": envelope["task_id"] = "other-task"
    if wrong_ref == "wrong-operation": envelope["operation_id"] = "other-operation"
    if wrong_ref == "wrong-basis": envelope["produced_against"] = "0" * 64
    if wrong_ref == "wrong-eligibility": envelope["eligibility_digest"] = "0" * 64
    if wrong_ref == "outer-schema": envelope["unexpected"] = "not a formal field"
    result = target.parent.parent / "native-envelope.json"
    c.save(result, envelope)
    observation = tmp_path / "observed-objects.json"
    sidecars = [{**c.reference(obj), "declared_ref": {**expected, "sha256": "0" * 64} if wrong_ref is True else expected}]
    if wrong_ref in {"extra", "bad-completion", "bad-first-hash"}:
        extra = target.parent.parent / "extra-unrelated-object.json"
        c.save(extra, {"unrelated": "not a formal proposal"})
        extra_hash = c.digest(canonical_json_bytes(c.read(extra)))
        sidecars.append({**c.reference(extra), "declared_ref": {"path": f".deckmaster/objects/{extra_hash[:2]}/{extra_hash}.json", "sha256": extra_hash}})
    if wrong_ref == "bad-first-hash": sidecars[0]["sha256"] = "0" * 64
    c.save(observation, {"observation_kind": c.OBSERVER_KIND, "assurance": "host_attested", "observed_at_utc": c.now(),
        "project_id": dispatch["project_id"], "task_id": task["task_id"], "model_output_bytes_sha256": c.reference(result)["sha256"],
        "method_release": dispatch["method_release"], "all_method_bytes_read": True,
        "method_read_record_sha256": c.reference(target / "method-read-record.json")["sha256"],
        "native_object_files": sidecars,
        "completion": {"sender": invocation["executor"], "message_type": "FINAL_ANSWER", "raw_final_message": "SYNTHETIC UNIT ONLY",
            "status_observation_tool": "collaboration.list_agents", "observed_status": "running" if wrong_ref == "bad-completion" else "completed",
            "observed_completed_agents": [invocation["executor"]]}})
    revision = store.current_revision_id()
    with pytest.raises(StoreError):
        store.read_object_bytes(expected)
    if wrong_ref in {"bad-completion", "bad-first-hash"}:
        with pytest.raises(c.CampaignError):
            c.observe(journal, state, "reconcile", ordinal, result, c.reference(result)["sha256"], observation, c.reference(observation)["sha256"])
        frozen = next(e["data"]["objects"] for e in journal.events() if e["kind"] == "native_objects_frozen")
        assert len(frozen) == 2
        assert [Path(item["frozen"]["path"]).read_bytes() for item in frozen] == [Path(item["path"]).read_bytes() for item in sidecars]
        assert not (target / "observed.json").exists()
        with pytest.raises(StoreError): store.read_object_bytes(expected)
        assert store.current_revision_id() == revision
        return
    c.observe(journal, state, "reconcile", ordinal, result, c.reference(result)["sha256"], observation, c.reference(observation)["sha256"])
    if wrong_ref == "stale":
        c.sdk_operation(journal, state, "service.inputs_update", {"patch": {"reason": "Later actual input",
            "task_patch": {"audience": "Another reader"}}, "base_revision": store.current_revision_id(), "operation_id": "later-update"})
        revision = store.current_revision_id()
    if wrong_ref == "corrupted":
        # An isolated test corruption, never a change to an actual preserved run.
        frozen = Path(c.read(target / "observed.json")["native_objects"][0]["frozen"]["path"])
        frozen.write_bytes(frozen.read_bytes() + b" ")
    with pytest.raises(StoreError):
        store.read_object_bytes(expected)  # observation freezes externally, not in the SDK Store
    if wrong_ref:
        with pytest.raises((c.CampaignError, ModelError)):
            c.materialize_native_objects(journal, state, "reconcile", ordinal)
        with pytest.raises(StoreError):
            store.read_object_bytes(expected)
        assert store.current_revision_id() == revision
    else:
        materialized = c.materialize_native_objects(journal, state, "reconcile", ordinal)
        assert materialized["refs"] == [expected] and store.current_revision_id() == revision
        assert store.read_object_json(expected) == narrative
        outcome = c.accept(journal, state, "reconcile", ordinal)
        assert outcome["status"] == "accepted" and outcome["variant"] == "input_revision"
        assert (target / "raw-native-output").read_bytes() == result.read_bytes()
        assert not journal.unfinished()
