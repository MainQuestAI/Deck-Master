"""Mechanical recorder tests; synthetic native metadata is never native proof.

Public SDK creation, local Task dispatch and method returns below are real.
Only installation admission is bypassed in this source-env unit suite. The
separate installed engineering trace uses the actual isolated installation.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/supplementary_recorder.py"
spec = importlib.util.spec_from_file_location("rc3_supplementary_test", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
c = m.c


def page(pid):
    notes = "SYNTHETIC " + pid + " original complete notes"
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
        "customer_visible": {"title": "Neutral " + pid, "body_blocks": [{"id": "body", "type": "paragraph", "text": "A neutral circle."}]},
        "speaker_notes": notes, "visual_spec": {"intent": "A circle", "reference_mode": "new_design"},
        "content_mapping": {"narrative_ref": None, "plan_role_page_id": pid,
            "speech_segments": [{"segment_id": "cue", "kind": "cue", "start_codepoint": 0, "end_codepoint": len(notes), "estimated_seconds": None, "narrative_node_ids": []}],
            "visible_links": [{"element_ref": "atom:" + pid + ":title", "narrative_node_ids": [], "source_links": []},
                              {"element_ref": "atom:" + pid + ":block:body:text", "narrative_node_ids": [], "source_links": []}]}}


def setup(tmp_path, monkeypatch, *, full_source=False, other_slot=False, sdk_cap=12, profile=None):
    import deck_master
    monkeypatch.setattr(c, "installation", lambda *_a, **_k: {"SYNTHETIC_INSTALLATION_ADMISSION_SEAM": True})
    instruction = c.write_once(tmp_path / "instruction.txt", b"SYNTHETIC NONHUMAN ENGINEERING. Work only on p5. No images.")
    source = c.save(tmp_path / "p5.json", {"pages": [page("p1"), page("p5"), page("p9")]} if full_source else page("p5"))
    grammar = c.save(tmp_path / "grammar.json", {"public_technical_only": True})
    exposure = c.save(tmp_path / "exposure.json", {"status": "FROZEN", "excluded_identities": ["/root/preparer"]})
    row = {"profile": "q3q4", "case": "Q4", "checkpoint": "Q4A", "matrix_slot": "05", "whole_run_id": "synthetic-neutral",
        "repetition": 1, "arm": "B", "scope_slot": "local-p5", "project": str(tmp_path / "project"), "project_mode": "new",
        "page_ids": ["p5"], "instruction": instruction, "materials": [source], "technical_supplements": [],
        "limits": {"writer": 4, "review": 4, "sdk": sdk_cap, "render": 4},
        "native_limits": {"initial_writer": 2, "repair_writer": 2, "feedback": 1, "verification": 1, "production": 3, "production_review": 2}}
    if profile:
        row.update(profile=profile, case="Q1" if profile == "q1-p5" else "E2", checkpoint="Q1P5" if profile == "q1-p5" else "E2")
        row["limits"]["review"] = 3
        for role in ("initial_writer", "repair_writer", "feedback", "verification"):
            row["native_limits"][role] = 0
    config = {"format": m.FORMAT, "status": m.ENGINEERING, "recorder_sha256": c.digest(SCRIPT.read_bytes()),
        "ledger_root": str(tmp_path / "campaign"),
        "common": c.reference(m.SOURCE), "protocol": grammar, "policy_epoch": grammar, "admission_review": grammar,
        "exposure_registry": exposure, "grammar": grammar, "installations": {"B": {"module_file": deck_master.__file__}}, "scopes": {"local": row}}
    if other_slot:
        row2 = deepcopy(row)
        row2.update(checkpoint="Q4B", scope_slot="later-p5", project=str(tmp_path / "other-project"))
        config["scopes"]["later"] = row2
    c.save(tmp_path / "registration.json", config)
    m.freeze(tmp_path / "registration.json", tmp_path / "campaign")
    state = m.init(tmp_path / "campaign", tmp_path / "run", "local")
    root = Path(state["root"])
    trigger = c.save(tmp_path / "trigger.json", {"assurance": "host_attested", "observer_id": "/root", "scope_slot": "local-p5",
        "actual_trigger": True, "instruction_sha256": instruction["sha256"], "source_observations": [source],
        "SYNTHETIC_NOT_NATIVE_NOT_HUMAN": True})
    m.instruction_event(root, "local-p5", trigger["path"])
    text = Path(instruction["path"]).read_text()
    request = {"intent": "edit", "content_intent": None, "scope": {"subject": "pages", "page_ids": ["p5"],
        "page_manifest_ref": None, "external_artifact_ref": None, "layers": ["page_copy", "speech", "design", "blueprint", "svg", "review", "output"],
        "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "working"},
        "instruction_evidence": {"kind": "host_attested_instruction", "text": text, "source_locator": "synthetic-neutral-only"}}
    m.operate(root, "service.create", {"brief": text, "sources": [source["path"]],
        "draft": {"pages": [page("p1"), page("p5"), page("p9")]}, "request_input": request})
    task = m.operate(root, "service.open_host_task", {"kind": "repair", "page_ids": ["p5"], "instruction": text})
    return root, state, config, task


def test_real_p5_task_full_methods_and_explicit_view(tmp_path, monkeypatch):
    root, state, _, task = setup(tmp_path, monkeypatch)
    result = m.prepare_task(root, "local", task["task_id"], "production", "q4-p5")
    raw = c.read(result["original_raw_ref"]["path"])
    view = c.read(result["author_view_ref"]["path"])
    closure = c.read(result["read_closure_manifest_ref"]["path"])
    assert raw["work_order"]["scope_pages"] == ["p5"]
    assert raw["work_order"]["source_reading"] == view["source_reading"]
    assert "work_order" not in view and view["raw_response_read_permission"] is False
    assert {p["page_id"] for p in [c.read(item["author_copy"]["path"]) for item in closure["required_read"]]
            if isinstance(p, dict) and "page_id" in p} == {"p5"}
    assert closure["opaque_binding_only"]  # actual full Plan binding remains opaque
    assert len(view["methods"]) == 4
    for item in view["methods"]:
        assert Path(item["read_file"]["path"]).read_bytes() == Path(item["own_installed_path"]).read_bytes()
    assert m.status(root)["scope_used"]["sdk"] == 3  # create / real dispatch / methods
    assert c.store_for(state).load_document()["pages"][0]["page_id"] == "p1"


def test_real_full_source_rejected_with_original_response_retained(tmp_path, monkeypatch):
    root, _, _, task = setup(tmp_path, monkeypatch, full_source=True)
    with pytest.raises(m.Error, match="source_reading"):
        m.prepare_task(root, "unsafe", task["task_id"], "production", "q4-p5")
    raw = root / "stages/unsafe/preflight/quarantine/sdk-method-response.json"
    assert c.read(raw)["work_order"]["source_reading"][0]["text"]
    assert not (root / "stages/unsafe/preflight/independent-packet-audit.json").exists()
    assert m.status(root)["scope_used"]["sdk"] == 3


@pytest.mark.parametrize("profile", ["q1-p5", "e2"])
def test_production_profiles_really_dispatch_own_task_with_own_public_materials(tmp_path, monkeypatch, profile):
    root, state, _, task = setup(tmp_path, monkeypatch, full_source=True, profile=profile)
    result = m.prepare_task(root, "production", task["task_id"], "production", "q3-full")
    view = c.read(result["author_view_ref"]["path"])
    assert view["work_order"]["task_id"] == task["task_id"]
    assert state["profile"] == profile and task["scope_pages"] == ["p5"]
    assert m.status(root)["scope_used"]["sdk"] == 3
    with pytest.raises(m.Error, match="scope exceeds"):
        m.role_task(c.Journal(root), state, {**task, "scope_pages": ["p1", "p5"]}, "production")


def test_opaque_whole_output_ref_not_required_read_and_expansion_refused(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    # Deliberately synthetic closure fixture, not a generated/native PPTX.
    artifact = c.save(project / "whole-file.json", {"SYNTHETIC_WHOLE_FILE": [page("p1"), page("p9")]})
    ref = {"path": "whole-file.json", "sha256": artifact["sha256"]}
    closure = m.Closure(str(project), page("p5"), tmp_path / "safe", bounded=True)
    closure.identity(ref, "/outputs/pptx")
    assert not closure.items and closure.opaque[0]["read_permission"] is False
    with pytest.raises(m.Error, match="opaque binding"):
        closure.identity(c.read(artifact["path"]), "/outputs/pptx")
    with pytest.raises(m.Error, match="Page|closure"):
        closure.visit(ref, "/required_full_file")


@pytest.fixture(params=["narrative", "plan"])
def full_semantic_object(tmp_path, request):
    """Actual schema-valid objects; structural seam, not a claimed Host Task."""
    from deck_master import models
    if request.param == "narrative":
        project = tmp_path / "project"; project.mkdir()
        target = page("p5")
        value = {"schema_version": "narrative.v1", "narrative_id": "synthetic-whole-narrative", "version": 1,
            "project_id": "synthetic-project", "origin": "host_composed", "maturity": "framing", "input_basis": [],
            "communication_job": {"mode": "explain", "audience_fact_key": "audience", "audience_question": "How does the neutral sequence fit?",
                "desired_outcome": "Understand the neutral sequence.", "observable_success": "Explain the sequence.", "use_mode": "read_alone", "primary_use": "read_alone"},
            "central_node_id": None, "nodes": [], "edges": [], "issues": [], "alternatives": [], "previous_ref": None}
        models.validate_narrative_semantics(value)
    else:
        from rc3_fixtures import public_project
        from deck_master.store import Store
        project = public_project(tmp_path, create_input={"brief": "Synthetic bounded closure schema check"}, manuscript={"pages": [page("p5")]})["project"]
        store = Store(project); doc = store.load_document(); value = store.read_object_json(doc["content_plan"])
        target = store.read_object_json(doc["pages"][0]["page"])
        models.validate_content_plan_semantics(value)
        assert value["schema_version"] == "content_plan.v2" and value["input"]["page_order"] == ["p5"]
    return project, value, target


@pytest.mark.parametrize("layout", ["inline", "nested-inline", "ref", "nested-ref", "inline-in-ref", "alternate-extension"])
def test_bounded_closure_rejects_real_full_semantic_schemas(full_semantic_object, tmp_path, layout):
    project, value, target = full_semantic_object
    path = project / ("full.txt" if layout == "alternate-extension" else "full.json")
    saved = c.save(path, {"wrapper": [value]} if layout == "inline-in-ref" else value)
    ref = {"path": path.name, "sha256": saved["sha256"]}
    payload = value if layout == "inline" else {"required": [value]} if layout == "nested-inline" else {"required": [ref]} if layout == "nested-ref" else ref
    destination = tmp_path / "bounded-author"
    closure = m.Closure(str(project), target, destination, bounded=True)
    with pytest.raises(m.Error, match="full Narrative/Plan"):
        closure.visit(payload, "/required/inputs/extra")
    assert not closure.items and not list(destination.rglob("*"))


def test_real_semantic_refs_stay_opaque_and_nonbounded_reading_unchanged(full_semantic_object, tmp_path):
    project, value, target = full_semantic_object
    saved = c.save(project / "full.json", value); ref = {"path": "full.json", "sha256": saved["sha256"]}
    key = "narrative_ref" if value["schema_version"] == "narrative.v1" else "page_manifest_ref"
    bounded = m.Closure(str(project), target, tmp_path / "bounded", bounded=True)
    bounded.visit({key: ref}, "/target/content_mapping")
    assert not bounded.items and bounded.opaque[0]["read_permission"] is False
    # Explicit full/nonblind profile; no new limit on Q1/E2 public source files.
    full = m.Closure(str(project), None, tmp_path / "full-profile", bounded=False)
    full.visit(ref, "/required")
    assert c.read(full.items[0]["author_copy"]["path"]) == value


@pytest.mark.parametrize("fault", ["other-page", "plan", "foreign", "dotdot", "symlink", "hash", "uri"])
def test_required_read_graph_negative_controls(tmp_path, fault):
    project = tmp_path / "project"; project.mkdir()
    leaf = c.save(project / "target.json", page("p5"))
    closure = m.Closure(str(project), page("p5"), tmp_path / "safe", bounded=True)
    value = {"path": "target.json", "sha256": leaf["sha256"]}
    if fault == "other-page": value = page("p9")
    if fault == "plan": value = {"page_order": ["p1", "p5"]}
    if fault == "foreign": value["path"] = c.save(tmp_path / "foreign.json", page("p5"))["path"]
    if fault == "dotdot": value["path"] = "../project/target.json"
    if fault == "symlink":
        (project / "alias.json").symlink_to(project / "target.json"); value["path"] = "alias.json"
    if fault == "hash": value["sha256"] = "0" * 64
    if fault == "uri": value = {"source_uri": "file:///unclassified-not-opened"}
    with pytest.raises(m.Error): closure.visit(value, "/required")


def test_shared_pool_case_feedback_and_stable_svg_do_not_reset(tmp_path, monkeypatch):
    root, state, _, _ = setup(tmp_path, monkeypatch, other_slot=True)
    other = m.init(tmp_path / "campaign", tmp_path / "other-run", "later")
    r1, r2 = m.Resources(state), m.Resources(other)
    r1.charge("writer", 4, "SYNTHETIC_NATIVE_METADATA_NOT_A_CALL")
    assert r2.totals()[0]["writer"] == 4 and r2.totals()[1]["writer"] == 0
    r1.once("content_feedback", "one", {"SYNTHETIC": True})
    r1.once("necessary_svg_repair", "p5", {"SYNTHETIC": True})
    with pytest.raises(m.Error): r2.once("content_feedback", "one", {})
    with pytest.raises(m.Error): r2.once("necessary_svg_repair", "p5", {})
    with pytest.raises((m.Error, FileExistsError)): m.init(tmp_path / "campaign", tmp_path / "third-run", "local")
    copied = tmp_path / "copied-run"; shutil.copytree(root, copied)
    with pytest.raises(m.Error, match="copied run"): m.load(copied)


def synthetic_feedback_record(tmp_path, monkeypatch, *, role='feedback', within=True, scoped=True):
    """Isolate post-acceptance mechanics; these events are not native proof."""
    root, state, _, task = setup(tmp_path, monkeypatch)
    journal = c.Journal(root)
    target = root/'stages/review/executions/0001'
    raw = c.save(target/'raw-native-output', {'SYNTHETIC_NOT_NATIVE': True, 'reviews': [
        {'review_id': 'synthetic-review', 'status': 'fail', 'findings': [{'finding_id': 'F1'}]}]})
    observation = c.save(target/'raw-root-completion.json', {'SYNTHETIC_NOT_NATIVE': True})
    c.save(target/'observed.json', {'raw': raw, 'observation': observation})
    journal.append('native_begun', {'ordinal': 1, 'stage': 'review', 'role': role,
        'executor': '/root/synthetic-reviewer', 'within_budget': within})
    if scoped:
        journal.append('scoped_native_observed', {'ordinal': 1, 'stage': 'review'})
    return root, state, task, journal, raw, observation


def test_accepted_feedback_delivers_once_and_allows_one_necessary_repair(tmp_path, monkeypatch):
    root, state, task, journal, raw, _ = synthetic_feedback_record(tmp_path, monkeypatch)
    resources = m.Resources(state)
    before = resources.journal.events()
    with pytest.raises(c.CampaignError, match='formal review acceptance'):
        m.feedback(root, 'review', 1)
    assert resources.journal.events() == before
    journal.append('result_accepted', {'ordinal': 1, 'role': 'feedback', 'task_id': task['task_id'],
        'SYNTHETIC_ACCEPTANCE_FACT_NOT_NATIVE': True})
    original = Path(raw['path']).read_bytes()
    result = m.feedback(root, 'review', 1)
    assert result['feedback_raw'] == raw and result['actual_reviews'][0]['findings'] == [{'finding_id': 'F1'}]
    assert Path(raw['path']).read_bytes() == original
    with pytest.raises((m.Error, c.CampaignError)):
        m.feedback(root, 'review', 1)
    assert sum(event['kind'] == 'feedback_delivered' for event in journal.events()) == 1
    assert sum(event['kind'] == 'content_feedback' for event in resources.journal.events()) == 1
    necessity = c.save(tmp_path/'necessary.json', {'necessary_layers': ['page_copy'],
        'actual_review_finding_refs': ['F1'], 'reason': 'Synthetic existing finding only.'})
    assert m.repair_begin(root, necessity['path'])['repair_cycle'] == 1
    with pytest.raises((m.Error, c.CampaignError)):
        m.repair_begin(root, necessity['path'])
    assert sum(event['kind'] == 'content_repair_cycle' for event in resources.journal.events()) == 1


@pytest.mark.parametrize('fault', ['unscoped', 'role', 'over_budget', 'raw_hash', 'observation_hash'])
def test_feedback_keeps_scope_budget_and_original_evidence_guards(tmp_path, monkeypatch, fault):
    root, state, task, journal, raw, observation = synthetic_feedback_record(tmp_path, monkeypatch,
        scoped=fault != 'unscoped', role='initial_writer' if fault == 'role' else 'feedback',
        within=fault != 'over_budget')
    journal.append('result_accepted', {'ordinal': 1, 'role': 'feedback', 'task_id': task['task_id'],
        'SYNTHETIC_ACCEPTANCE_FACT_NOT_NATIVE': True})
    if fault in ('raw_hash', 'observation_hash'):
        Path((raw if fault == 'raw_hash' else observation)['path']).write_text('changed')
    before = m.Resources(state).journal.events()
    with pytest.raises((m.Error, c.CampaignError)):
        m.feedback(root, 'review', 1)
    assert m.Resources(state).journal.events() == before
    assert not any(event['kind'] == 'feedback_delivered' for event in journal.events())


def test_sdk_refusal_counts_and_actual_queries_remain_possible(tmp_path, monkeypatch):
    root, _, _, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(Exception):
        m.operate(root, "editing.restore", {"revision_id": "missing", "base_revision": "wrong", "operation_id": "synthetic-stale"})
    after = m.status(root)
    assert after["scope_used"]["sdk"] == 3 and after["sdk_unresolved"]
    with pytest.raises(m.Error, match="unresolved"):
        m.operate(root, "service.continue_project", {})
    m.operate(root, "service.inputs_show", {})
    assert m.status(root)["scope_used"]["sdk"] == 4
    assert m.status(root)["sdk_unresolved"]


def test_real_compiler_entry_is_charged_even_when_it_raises(tmp_path, monkeypatch):
    root, _, _, _ = setup(tmp_path, monkeypatch)
    from deck_master.compiler import CompileOptions, compile_deck
    with pytest.raises(ValueError, match="At least one"):
        with m.resource_session(root, render_reserve=1) as (journal, _, _):
            m.perform(journal, "compiler.compile_deck", {"SYNTHETIC_EMPTY_INPUT": True},
                lambda: compile_deck([], CompileOptions(), tmp_path / "not-produced"))
    state = m.status(root)
    assert state["scope_used"]["render"] == 1 and not state["render_pending"]
    assert state["scope_used"]["sdk"] == 3
    ledger = c.Journal(tmp_path / "campaign/resource-ledger").events()
    trace = next(e["data"] for e in ledger if e["kind"] == "render_reconciled" and e["data"]["actual_calls"])
    assert trace["actual_calls"][0]["unit"] == "compile" and trace["operation_returned"] is False


def test_zero_reservation_does_not_hide_actual_attempt(tmp_path, monkeypatch):
    root, state, _, _ = setup(tmp_path, monkeypatch)
    from deck_master.compiler import CompileOptions, compile_deck
    with pytest.raises(m.Error, match="exceeded prior reservation"):
        with m.resource_session(root) as (journal, _, _):
            m.perform(journal, "compiler.compile_deck", {}, lambda: compile_deck([], CompileOptions(), tmp_path / "none"))
    assert m.status(root)["scope_used"]["render"] == 1
    with pytest.raises(m.Error, match="unreserved"):
        m.budget_clean(c.Journal(root), state)


@pytest.mark.parametrize("operation,args", [
    ("tasks.call_settle", {}), ("store.put_json_object", {}), ("service.create", {"adapter_context": {}}),
    ("service.inputs_show", {"project_dir": "/foreign"}), ("tasks.call_begin", {"task_id": "invented"}),
])
def test_closed_operation_and_project_boundary(tmp_path, monkeypatch, operation, args):
    root, _, _, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(m.Error): m.operate(root, operation, args)
    assert m.status(root)["scope_used"]["sdk"] == 2


def test_compose_cannot_be_relabelled_production(tmp_path, monkeypatch):
    root, state, _, task = setup(tmp_path, monkeypatch)
    bad = {**task, "kind": "compose"}
    with pytest.raises(m.Error, match="relabel"):
        m.role_task(c.Journal(root), state, bad, "production")


def test_missing_independent_audit_stops_native_begin(tmp_path, monkeypatch):
    root, _, _, task = setup(tmp_path, monkeypatch)
    m.prepare_task(root, "p5", task["task_id"], "production", "q4-p5")
    with pytest.raises(m.Error, match="audit"):
        m.begin_native(root, "p5", tmp_path / "never-read-observation.json")
    assert not any(e["kind"] == "native_begun" for e in c.Journal(root).events())


def test_finite_profile_semantics_no_aliases_or_unlimited_roles(tmp_path, monkeypatch):
    _, _, config, _ = setup(tmp_path, monkeypatch)
    bad = deepcopy(config)
    bad["scopes"]["local"]["case"] = "M02"
    with pytest.raises(m.Error, match="mismatch"): m.validate(bad)
    bad = deepcopy(config)
    bad["scopes"]["local"]["native_limits"]["production"] = None
    with pytest.raises(m.Error, match="finite"): m.validate(bad)
    bad = deepcopy(config)
    bad["scopes"]["alias"] = deepcopy(bad["scopes"]["local"])
    with pytest.raises(m.Error, match="alias"): m.validate(bad)


def test_fixed_registration_cannot_freeze_or_init_another_ledger(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, other_slot=True)
    with pytest.raises(m.Error, match="one fixed"):
        m.freeze(tmp_path / "registration.json", tmp_path / "second-campaign")
    shutil.copytree(tmp_path / "campaign", tmp_path / "copied-campaign")
    with pytest.raises(m.Error, match="copied campaign"):
        m.init(tmp_path / "copied-campaign", tmp_path / "third-run", "later")


def test_actual_claim_has_new_full_raw_and_same_p5_closure(tmp_path, monkeypatch):
    root, state, _, task = setup(tmp_path, monkeypatch)
    prepared = m.prepare_task(root, "p5", task["task_id"], "production", "q4-p5")
    from deck_master import service
    with m.resource_session(root) as (journal, _, _):
        args = {"task_id": task["task_id"], "execution_ref": "synthetic-engineering-host-not-a-native-agent",
            "supported_protocols": [task["protocol_version"]], "capabilities": task["required_capabilities"]}
        m.perform(journal, "service.task_start", args, lambda: service.task_start(state["project"], **args))
        current = c.task_for(c.store_for(state), task["task_id"])
        full = m.read_methods(journal, state, current)
        after = m.packet(journal, state, current, full, tmp_path / "post-claim", "q4-p5")
    assert current["status"] == "running"
    assert c.read(after["original_raw_ref"]["path"])["work_order"]["execution_ref"] == args["execution_ref"]
    before_view, after_view = [c.read(x["author_view_ref"]["path"]) for x in (prepared, after)]
    assert before_view["source_reading"] == after_view["source_reading"]
    assert before_view["methods"] != after_view["methods"]  # copied to distinct immutable packets
    assert [x["sha256"] for x in before_view["methods"]] == [x["sha256"] for x in after_view["methods"]]
    assert m.status(root)["scope_used"]["sdk"] == 5


def test_audit_cannot_launder_changed_closure_or_preparer_identity(tmp_path, monkeypatch):
    root, state, _, task = setup(tmp_path, monkeypatch)
    result = m.prepare_task(root, "p5", task["task_id"], "production", "q4-p5")
    obs = {"assurance": "host_attested", "observer_id": "/root/preparer", "status": "PASS", "task_id": task["task_id"],
        "project": state["project"], "required_read_closure_checked": True, "raw_workorder_preserved": True,
        **{k: result[k] for k in ("original_raw_ref", "author_view_ref", "read_closure_manifest_ref")}, "SYNTHETIC_AUDIT_METADATA_NOT_NATIVE": True}
    ref = c.save(tmp_path / "excluded-audit.json", obs)
    with pytest.raises(m.Error, match="independent"):
        m.audit_packet(root, "p5", ref["path"])
    obs["observer_id"] = "/root/synthetic-independent-unit-fixture"
    closure = c.read(result["read_closure_manifest_ref"]["path"])
    Path(closure["required_read"][0]["author_copy"]["path"]).write_bytes(b"SYNTHETIC TAMPER")
    ref = c.save(tmp_path / "drift-audit.json", obs)
    with pytest.raises(m.Error, match="changed"):
        m.audit_packet(root, "p5", ref["path"])


def test_unknown_renderer_reservation_blocks_writes_but_allows_actual_query(tmp_path, monkeypatch):
    root, state, _, _ = setup(tmp_path, monkeypatch)
    resources = m.Resources(state)
    resources.journal.append("render_reserved", {"pool": m.pool_key(state), "slot": state["slot"], "key": "synthetic-interruption", "maximum": 1})
    with pytest.raises(m.Error, match="unresolved"):
        m.operate(root, "service.continue_project", {})
    m.operate(root, "service.inputs_show", {})
    current = m.status(root)
    assert current["scope_used"]["sdk"] == 3 and "synthetic-interruption" in current["render_pending"]
