"""M02 mechanical integration only. All native observations here are synthetic.

Real SDK calls and immutable objects are exercised. Explicit seams below do not
establish native trust, model quality, full production or a benchmark result.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/m02_recorder.py"
_spec = importlib.util.spec_from_file_location("rc3_m02_engineering_test", SCRIPT)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
c = m.c


def setup(tmp_path, monkeypatch):
    import deck_master
    source = tmp_path / "source.txt"
    source.write_text("SYNTHETIC ENGINEERING ONLY. OMEGA is a neutral label, not a measured outcome.\n")
    grammar = c.save(tmp_path / "grammar.json", {"scope": "SYNTHETIC_ENGINEERING_ONLY"})
    review = c.save(tmp_path / "limited-review.json", {"scope": "SYNTHETIC_ENGINEERING_REVIEW_NOT_ADMISSION"})
    exposure = c.save(tmp_path / "exposure.json", {"status": "FROZEN", "excluded_identities": ["/root/preparer"]})
    budgets = c.save(tmp_path / "budget.json", {"format": "rc3-image-global-budget.v1", "status": "SYNTHETIC_ENGINEERING_NOT_NATIVE_NOT_BENCHMARK",
        "protocol": grammar, "admission_review": review,
        "workflow_arm_caps": [{"case": "M02", "whole_run_id": "synthetic-m02", "repetition": 1, "arm": "B", "max_calls": 2}],
        "ledger_root": str(tmp_path / "global-ledger"), "total_call_cap": 2,
        "allowed_page_arms": [{"case": "M02", "whole_run_id": "synthetic-m02", "repetition": 1, "arm": "B", "page_id": pid}
            for phase, pid in [("live", "p1"), ("read", "r1")]]})
    scopes = {}
    for phase in m.PHASES:
        msg = tmp_path / (phase + ".txt"); msg.write_text("NEW SYNTHETIC NON-HUMAN M02 scope: " + phase)
        scopes[phase] = {"instruction": c.reference(msg), "page_ids": [] if phase == "common" else ["r1" if phase == "read" else "p1"],
            "native_limits": {"initial_writer": 7, "repair_writer": 4, "feedback": 1, "verification": 1, "production": 3, "production_review": 3},
            "max_external_calls": 0 if phase in ("common", "live_notes_edit") else 1, "max_candidates": 0,
            "notes_policy": "both" if phase == "live" else "pure_reading",
            "input_patch": None}
    config = {"format": m.FORMAT, "status": m.ENGINEERING, "experiment_id": "synthetic-m02",
        "recorder_sha256": c.digest(SCRIPT.read_bytes()), "common": c.reference(m.SOURCE), "image_controller": c.reference(m.SOURCE.with_name("image_controller.py")), "protocol": grammar,
        "grammar": grammar, "admission_review": review, "exposure_registry": exposure,
        "global_image_budget": budgets, "technical_supplements": [], "materials": [c.reference(source)],
        "scopes": scopes, "installation": {"module_file": deck_master.__file__},
        "create_arguments": {"presentation_mode": "mixed", "page_limit": 2}}
    config_ref = c.save(tmp_path / "config.json", config)
    monkeypatch.setattr(c, "installation", lambda *_args, **_kwargs: {"SYNTHETIC_INSTALLATION_SEAM": True})
    m.freeze(config_ref["path"], tmp_path / "campaign")
    state = m.init(tmp_path / "campaign", tmp_path / "run", tmp_path / "p")
    journal = c.Journal(tmp_path / "run")
    trigger = c.save(tmp_path / "trigger.json", {"assurance": "host_attested", "actual_trigger_satisfied": True,
        "source_observations": [review], "evidence_level": "SYNTHETIC_NO_NATIVE"})
    m.instruction(journal, state, config, "common", trigger["path"])
    arguments = {**config["create_arguments"], "brief": Path(scopes["common"]["instruction"]["path"]).read_text(), "sources": [str(source)]}
    m.operate(journal, state, config, "service.create", arguments)
    return journal, state, config, trigger


def common_argument(journal, state, config):
    from test_compose_v2_phases import _accept_argument, _adopt_direction
    store = c.store_for(state)
    _, outcome = _accept_argument(state["project"], store)
    # Explicit result-boundary seam: true SDK result, no native completion.
    journal.append("result_accepted", {"ordinal": 0, "outcome": outcome, "SYNTHETIC_ENGINEERING_SEAM_NO_NATIVE": True})
    _adopt_direction(state["project"], store, outcome["result_refs"][0])
    return m.fix_narrative(journal, state, config)


def declare_and_start(journal, state, config, trigger):
    from deck_master import variant_requests
    from test_compose_v2_phases import _scope
    evidence = m.instruction_evidence(journal, state, "common")
    args = {"input": {"mode": "delegate", "actions": ["content.compose"], "delegated_topics": ["direction"],
        "constraints": {"variant_ids": ["live", "read"]}, "scope": _scope(),
        "max_external_calls": 0, "max_candidate_count": 0, "instruction_evidence": evidence},
        "base_revision": c.store_for(state).current_revision_id(), "operation_id": "declare-pair"}
    m.operate(journal, state, config, "collaboration.grant", args)
    m.instruction(journal, state, config, "live", trigger["path"])
    evidence = m.instruction_evidence(journal, state, "live")
    store = c.store_for(state); doc = store.load_document()
    actual = variant_requests.declaring_authorization(store, doc)
    group = variant_requests.variant_group_id(actual[0], actual[2])
    args = {"input": {"intent": "full_deck", "content_intent": None, "scope": _scope(page_ids=["p1"]),
        "instruction_evidence": evidence, "replace_request_id": doc["collaboration"]["request"]["request_id"],
        "variant": {"group_id": group, "variant_id": "live", "label": "Synthetic live", "requested_variant_ids": ["live", "read"]}},
        "base_revision": doc["revision_id"], "operation_id": "start-live"}
    return args


def test_independent_registration_does_not_inherit_e1_five_execution_budget(tmp_path, monkeypatch):
    journal, state, config, _ = setup(tmp_path, monkeypatch)
    assert config["scopes"]["live"]["native_limits"]["initial_writer"] == 7
    assert state["budget"]["initial_writer"] == 28
    assert state["case"] == "M02"
    assert state["comparison_credit"] == "NOT_E1_NOT_ORIGINAL12"
    assert m.load(journal.root)[1] == state


@pytest.mark.parametrize("fault", ["code", "common", "third-scope", "image-scope", "notes-budget", "notes-page"])
def test_registration_failures_precede_any_new_project(tmp_path, monkeypatch, fault):
    _, _, config, _ = setup(tmp_path, monkeypatch)
    bad = deepcopy(config)
    if fault == "code": bad["recorder_sha256"] = "0" * 64
    if fault == "common": bad["common"]["sha256"] = "0" * 64
    if fault == "third-scope": bad["scopes"]["third"] = bad["scopes"]["read"]
    if fault == "image-scope": bad["scopes"]["read"]["page_ids"] = ["outside"]
    if fault == "notes-budget": bad["scopes"]["live_notes_edit"]["max_external_calls"] = 1
    if fault == "notes-page": bad["scopes"]["live_notes_edit"]["page_ids"] = ["other"]
    with pytest.raises(m.Error): m.validate(bad)
    assert not (tmp_path / "another-project").exists()


def test_real_sdk_fixed_argument_and_variant_metadata_and_no_third_version(tmp_path, monkeypatch):
    journal, state, config, trigger = setup(tmp_path, monkeypatch)
    fixed = common_argument(journal, state, config)
    args = declare_and_start(journal, state, config, trigger)
    result = m.start_variant(journal, state, config, "live", args)
    assert result["status"] == "accepted"
    document = c.store_for(state).load_document()
    assert document["narrative"] == fixed["narrative_ref"]
    assert document["collaboration"]["request"]["variant"] == args["input"]["variant"]
    before = document
    with pytest.raises(m.Error, match="two variants"): m.start_variant(journal, state, config, "third", args)
    with pytest.raises(m.Error, match="sequential"): m.start_variant(journal, state, config, "live", args)
    assert c.store_for(state).load_document() == before


@pytest.mark.parametrize("fault", ["wrong-group", "third-requested", "out-of-scope", "wrong-evidence", "wrong-transition"])
def test_bad_first_variant_rejected_before_sdk_or_partial_write(tmp_path, monkeypatch, fault):
    journal, state, config, trigger = setup(tmp_path, monkeypatch)
    common_argument(journal, state, config)
    args = declare_and_start(journal, state, config, trigger)
    if fault == "wrong-group": args["input"]["variant"]["group_id"] = "vg-made-up"
    if fault == "third-requested": args["input"]["variant"]["requested_variant_ids"].append("extra")
    if fault == "out-of-scope": args["input"]["scope"]["page_ids"] = ["elsewhere"]
    if fault == "wrong-evidence": args["input"]["instruction_evidence"]["actor_id"] = "fake-owner"
    if fault == "wrong-transition": args["input"]["variant_transition"] = {"kind": "next_variant", "source": {"revision_id": "future"}}
    project = Path(state["project"])
    before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    with pytest.raises(m.Error): m.start_variant(journal, state, config, "live", args)
    assert before == {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}


def test_sources_and_current_project_identity_are_rechecked(tmp_path, monkeypatch):
    journal, state, config, _ = setup(tmp_path, monkeypatch)
    common_argument(journal, state, config)
    Path(config["materials"][0]["path"]).write_text("Changed original material")
    with pytest.raises(m.Error, match="pinned bytes changed"): m.load(journal.root)


def test_full_version_rejects_content_only_and_future_transition(tmp_path, monkeypatch):
    from test_variant_requests import _produce_variant
    journal, state, config, trigger = setup(tmp_path, monkeypatch)
    common_argument(journal, state, config)
    args = declare_and_start(journal, state, config, trigger)
    m.start_variant(journal, state, config, "live", args)
    store = c.store_for(state)
    _produce_variant(state["project"], store, text="Explicit synthetic SDK content fixture; no professional claim.")
    before = store.load_document()
    with pytest.raises(m.Error, match="gate|checks|PPTX"):
        m.complete_version(journal, state, config, "live")
    with pytest.raises(m.Error, match="complete live export"):
        m.instruction(journal, state, config, "read", trigger["path"])
    assert store.load_document() == before
    assert not m.events(journal, "m02_version_exported")


def test_raw_originals_and_actual_role_binding_reuse_pinned_helpers(tmp_path, monkeypatch):
    from test_rc3_campaign_controller import fake_invocation
    journal, state, config, _ = setup(tmp_path, monkeypatch)
    task = c.store_for(state).read_object_json(c.store_for(state).load_document()["tasks"][0])
    packet = m.prepare(journal, state, config, "common01", task["task_id"], "initial_writer")
    with pytest.raises(m.Error): m.prepare(journal, state, config, "wrong-role", task["task_id"], "production")
    invocation = fake_invocation(tmp_path, packet, "/root/m02-unit-author")
    actual = m.begin(journal, state, config, "common01", invocation)
    c.claim_read(journal, state, "common01", actual["ordinal"], "/root/m02-unit-author")
    raw = tmp_path / "bad-native.txt"; raw.write_bytes(b"Complete original malformed engineering output\n")
    bad = c.save(tmp_path / "bad-root.json", {"completion": {}, "native_object_files": [], "SYNTHETIC_ONLY": True})
    with pytest.raises((m.Error, KeyError)):
        c.observe(journal, state, "common01", actual["ordinal"], raw, c.reference(raw)["sha256"], bad["path"], bad["sha256"])
    _, target = c.execution(journal, "common01", actual["ordinal"])
    assert (target / "raw-native-output").read_bytes() == raw.read_bytes()
    assert not (target / "observed.json").exists()
    assert len(m.events(journal, "m02_native_started", "common")) == 1


def test_immutable_export_tree_rejects_changed_file_without_current_mutation(tmp_path, monkeypatch):
    journal, state, _, _ = setup(tmp_path, monkeypatch)
    root = tmp_path / "explicit-export-seam"; root.mkdir()
    original = c.write_once(root / "file.txt", b"Explicit engineering file; not a completed M02 export")
    journal.append("m02_version_exported", {"phase": "live", "export_root": str(root), "export_tree": {"file.txt": original["sha256"]}, "SYNTHETIC_VALIDATOR_SEAM_NOT_FULL_VERSION": True})
    m.preserved(journal)
    (root / "file.txt").write_bytes(b"Tampered")
    before = c.store_for(state).load_document()
    with pytest.raises(m.Error, match="export tree"): m.preserved(journal)
    assert c.store_for(state).load_document() == before


def produce_use_content(project, store, use):
    """Explicit synthetic public SDK payload, distinct IDs and real Plan policy."""
    from deck_master import service
    from rc3_fixtures import claimed_phase_task
    from test_content_preproduction_review import _page, _plan_input, _source_link
    doc = store.load_document()
    task = claimed_phase_task(store, doc, operation_id="pc-" + use, phase="page_copy")
    doc = store.load_document(); pid = "p1" if use == "live" else "r1"
    page = _page(store, doc, pid, notes="SYNTHETIC notes" if use == "live" else "")
    if use == "read": page["content_mapping"]["speech_segments"] = []
    plan = {**_plan_input(doc, [pid], [_source_link(store, doc, "L1")]),
            "speech_policy": {"mode": "cues" if use == "live" else "none", "source": "provided", "output": "pptx_notes"}}
    return service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"], produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose", "variant": "page_copy", "task_id": task["task_id"], "operation_id": task["operation_id"],
            "produced_against": task["produced_against"], "eligibility_digest": task["collaboration_binding"]["eligibility_digest"], "payload": {"pages": [page], "page_order": [pid], "plan_input": plan}, "usage_events": []})


def two_content_versions_seam(journal, state, config, trigger):
    """Actual SDK variants/exports; explicit milestone seam bypasses FILE gate.

    These content-only exports are NOT proof of complete M02 production. This
    fixture isolates next/edit public transitions and native notes consumption.
    Full-version validation is separately required by the actual CLI.
    """
    from deck_master import exports
    from test_compose_v2_phases import _scope
    common_argument(journal, state, config)
    args = declare_and_start(journal, state, config, trigger)
    m.start_variant(journal, state, config, "live", args)
    records = []
    for use in ("live", "read"):
        store = c.store_for(state)
        produce_use_content(state["project"], store, use)
        actual = exports.create(state["project"], purpose="review")
        root = Path(state["project"]) / ".deckmaster/workbench/exports" / actual["export_id"]
        record = {"phase": use, "revision_id": actual["revision_id"], "export_id": actual["export_id"],
            "variant": actual["manifest"]["variant"], "export_root": str(root),
            "export_tree": {p.relative_to(root).as_posix(): c.reference(p)["sha256"] for p in root.rglob("*") if p.is_file()},
            "SYNTHETIC_CONTENT_ONLY_MILESTONE_SEAM_NOT_FULL_VERSION": True}
        journal.append("m02_version_exported", record)
        records.append(record)
        if use == "live":
            m.instruction(journal, state, config, "read", trigger["path"])
            evidence = m.instruction_evidence(journal, state, "read")
            doc = store.load_document()
            args = {"input": {"intent": "full_deck", "content_intent": None,
                "scope": _scope(page_ids=["r1"]), "instruction_evidence": evidence,
                "replace_request_id": doc["collaboration"]["request"]["request_id"],
                "variant": {"group_id": record["variant"]["group_id"], "variant_id": "read", "label": "Synthetic read", "requested_variant_ids": ["live", "read"]},
                "variant_transition": {"kind": "next_variant", "source": {"revision_id": record["revision_id"], "export_id": record["export_id"]}}},
                "base_revision": doc["revision_id"], "operation_id": "start-read"}
            m.start_variant(journal, state, config, "read", args)
    m.instruction(journal, state, config, "live_notes_edit", trigger["path"])
    evidence = m.instruction_evidence(journal, state, "live_notes_edit")
    doc = c.store_for(state).load_document()
    args = {"input": {"intent": "edit", "content_intent": None,
        "scope": _scope(page_ids=["p1"], layers=["speech"], allow_page_membership_change=False),
        "instruction_evidence": evidence, "replace_request_id": doc["collaboration"]["request"]["request_id"],
        "variant_transition": {"kind": "edit_variant", "source": {"revision_id": records[0]["revision_id"], "export_id": records[0]["export_id"]}}},
        "base_revision": doc["revision_id"], "operation_id": "edit-old-live"}
    m.start_variant(journal, state, config, "live_notes_edit", args)
    return records


@pytest.mark.parametrize("bad", [None, "body", "foreign-page", "wrong-base", "wrong-completion"])
def test_direct_notes_operation_has_true_sdk_boundary_and_immutable_originals(tmp_path, monkeypatch, bad):
    journal, state, config, trigger = setup(tmp_path, monkeypatch)
    records = two_content_versions_seam(journal, state, config, trigger)
    packet = m.prepare_notes(journal, state, config, "notes01", "synthetic-notes-operation")
    target = Path(packet["packet"])
    invocation = c.save(tmp_path / "notes-invocation.json", {"observation_kind": c.OBSERVER_KIND,
        "assurance": "host_attested", "observed_at_utc": c.now(),
        "dispatch_sha256": c.reference(target / "dispatch.json")["sha256"],
        "SYNTHETIC_OBSERVATION_NOT_NATIVE": True,
        "spawn": {"tool": "collaboration.spawn_agent", "canonical_task_name": "/root/unit-notes-author",
            "returned_task_name": "/root/unit-notes-author", "fork_turns": "none", "inherited_identities": []}})
    ordinal = m.begin_notes(journal, state, config, "notes01", invocation["path"])["ordinal"]
    m.read_notes(journal, state, "notes01", ordinal, "/root/unit-notes-author")
    binding = packet["direct_operation_binding"]
    page = c.read(target / "original-page.json")
    page["speaker_notes"] += " Synthetic notes-only transition."
    page["content_mapping"]["speech_segments"][0]["end_codepoint"] = len(page["speaker_notes"])
    if bad == "body": page["customer_visible"]["title"] += " Forbidden body change"
    if bad == "foreign-page": page["page_id"] = "another-page"
    args = {"page": page, **{k: binding[k] for k in ("base_revision", "page_hash", "operation_id")}}
    if bad == "wrong-base": args["base_revision"] = "wrong-revision"
    raw = c.save(tmp_path / "notes-raw.json", args)
    _, execution = c.execution(journal, "notes01", ordinal)
    observed = c.save(tmp_path / "notes-completed.json", {"observation_kind": c.OBSERVER_KIND,
        "assurance": "host_attested", "observed_at_utc": c.now(), "dispatch_sha256": c.reference(target / "dispatch.json")["sha256"],
        "model_output_bytes_sha256": raw["sha256"], "all_method_bytes_read": True,
        "method_read_record_sha256": c.reference(execution / "method-read-record.json")["sha256"],
        "SYNTHETIC_OBSERVATION_NOT_NATIVE": True,
        "completion": {"sender": "/root/unit-notes-author", "message_type": "FINAL_ANSWER", "status_observation_tool": "collaboration.list_agents",
            "observed_status": "running" if bad == "wrong-completion" else "completed", "observed_completed_agents": ["/root/unit-notes-author"], "raw_final_message": "SYNTHETIC UNIT RESULT"}})
    store = c.store_for(state); before = store.load_document()
    if bad == "wrong-completion":
        with pytest.raises(m.Error): m.observe_notes(journal, state, "notes01", ordinal, raw["path"], raw["sha256"], observed["path"], observed["sha256"])
        assert (execution / "raw-native-output").read_bytes() == Path(raw["path"]).read_bytes()
        assert store.load_document() == before
        return
    m.observe_notes(journal, state, "notes01", ordinal, raw["path"], raw["sha256"], observed["path"], observed["sha256"])
    if bad:
        with pytest.raises(m.Error): m.accept_notes(journal, state, config, "notes01", ordinal)
        assert store.load_document() == before
    else:
        result = m.accept_notes(journal, state, config, "notes01", ordinal)
        assert result["status"] == "edited"
        assert store.load_document()["parent_revision_id"] == before["revision_id"]
        assert store.read_object_json(store.load_document()["pages"][0]["page"]) == page
        assert m.events(journal, "m02_notes_edit_accepted")[0]["new_image_calls"] == 0
        assert store.load_document()["collaboration"]["request"]["variant"]["variant_id"] == "live"
        for record in records: assert c.store_for(state).load_document(record["revision_id"])["narrative"] == m.fixed(journal)["narrative_ref"]
    m.preserved(journal)


def test_late_scope_or_original_author_cannot_be_independent_reviewer(tmp_path, monkeypatch):
    from test_rc3_campaign_controller import fake_invocation
    journal, state, config, _ = setup(tmp_path, monkeypatch)
    task = c.store_for(state).read_object_json(c.store_for(state).load_document()["tasks"][0])
    packet = m.prepare(journal, state, config, "common01", task["task_id"], "initial_writer")
    m.begin(journal, state, config, "common01", fake_invocation(tmp_path, packet, "/root/m02-author"))
    journal.append("m02_phase_started", {"phase": "live"})
    with pytest.raises(m.Error, match="earlier use"): m.current_stage(journal, "common01")
    # The shared d0 bridge checks all actual native writer roles across this
    # one journal. It is reused, not replaced with a test provider in product.
    assert "/root/m02-author" in {r["executor"] for r in m.events(journal, "native_begun") if r["role"] in c.WRITER_ROLES}


def test_checkpoint_joins_real_common_event_shape_by_ordinal_not_missing_stage(tmp_path, monkeypatch):
    journal, state, config, trigger = setup(tmp_path, monkeypatch)
    common_argument(journal, state, config)
    m.start_variant(journal, state, config, "live", declare_and_start(journal, state, config, trigger))
    produce_use_content(state["project"], c.store_for(state), "live")
    # Exact d0 event shape: native_output_frozen has ordinal, no stage.
    raw = c.save(tmp_path / "explicit-raw-seam.json", {"SYNTHETIC_ONLY": True})
    journal.append("stage_prepared", {"stage": "sdk-seam", "m02_phase": "live"})
    journal.append("native_begun", {"stage": "sdk-seam", "ordinal": 99, "role": "initial_writer"})
    journal.append("native_output_frozen", {"ordinal": 99, "raw": raw, "observation": raw})
    m.content_checkpoint(journal, state, config)
    checkpoint = c.read(journal.root / "before-feedback-live.json")
    assert checkpoint["original_native_stages"] == [{"ordinal": 99, "raw": raw, "observation": raw}]
    assert checkpoint["sdk_manuscript_before_first_review"]["pages"]


def test_same_whole_run_requires_distinct_pages_and_single_combined_image_cap(tmp_path, monkeypatch):
    _, _, config, _ = setup(tmp_path, monkeypatch)
    bad = deepcopy(config); bad["scopes"]["read"]["page_ids"] = ["p1"]
    with pytest.raises(m.Error, match="distinct stable"): m.validate(bad)
    budget = c.read(config["global_image_budget"]["path"])
    assert len(budget["workflow_arm_caps"]) == 1
    assert budget["workflow_arm_caps"][0]["case"] == "M02"
    assert budget["workflow_arm_caps"][0]["max_calls"] == 2
    assert {row["page_id"] for row in budget["allowed_page_arms"]} == {"p1", "r1"}
    # Initialization of the exact ledger can wait until before first image.
    assert not Path(budget["ledger_root"]).exists()
    assert m.validate(config) == config


def test_recorded_writer_cannot_begin_feedback_even_with_followup_label(tmp_path, monkeypatch):
    from test_rc3_campaign_controller import fake_invocation
    journal, state, config, _ = setup(tmp_path, monkeypatch)
    task = c.store_for(state).read_object_json(c.store_for(state).load_document()["tasks"][0])
    packet = m.prepare(journal, state, config, "author01", task["task_id"], "initial_writer")
    m.begin(journal, state, config, "author01", fake_invocation(tmp_path, packet, "/root/m02-author"))
    # Synthetic dispatch seam isolates the real pinned author guard. It is not
    # a real review Task, review receipt, or evidence of native execution.
    target = journal.root / "stages/reviewer-seam"; target.mkdir()
    dispatch = {**c.read(Path(packet["packet"]) / "dispatch.json"), "stage": "reviewer-seam", "role": "feedback"}
    c.save(target / "dispatch.json", dispatch)
    invocation = c.read(fake_invocation(tmp_path, dispatch, "/root/m02-author"))
    invocation["spawn"]["tool"] = "collaboration.followup_task"
    ref = c.save(tmp_path / "bad-followup.json", invocation)
    before = len(m.events(journal, "native_begun"))
    with pytest.raises(m.Error, match="continuation|author"): m.begin(journal, state, config, "reviewer-seam", ref["path"])
    assert len(m.events(journal, "native_begun")) == before


def test_actual_invocation_overrun_is_counted_and_marked_unconsumable(tmp_path, monkeypatch):
    from test_rc3_campaign_controller import fake_invocation
    journal, state, config, _ = setup(tmp_path, monkeypatch)
    task = c.store_for(state).read_object_json(c.store_for(state).load_document()["tasks"][0])
    packet = m.prepare(journal, state, config, "counted", task["task_id"], "initial_writer")
    runs = [m.begin(journal, state, config, "counted", fake_invocation(tmp_path, packet, "/root/m02-synthetic-" + str(i))) for i in range(8)]
    assert [r["within_budget"] for r in runs] == [True] * 7 + [False]
    assert len(m.events(journal, "m02_native_started", "common")) == 8
    assert runs[-1]["cap"] == 7  # this use only, rather than global total 28
