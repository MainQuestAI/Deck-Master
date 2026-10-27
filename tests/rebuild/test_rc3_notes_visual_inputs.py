"""RC3 shared visual consumption; synthetic services, never model quality.

The imported factories dispatch real immutable Task.inputs and use explicitly
synthetic, isolated observation events for the fee-ledger protocol only.
"""
import copy
import importlib.util
import uuid
from pathlib import Path

import pytest

from deck_master import candidates, collaboration, editing, generation, service, tasks
from deck_master.models import ModelError
from deck_master.production import stored_blueprint_request
from deck_master.visual_dependencies import page_visual_equivalent
from rc3_fixtures import authorize_scope, evidence_for, public_project, settle_fidelity_review


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


gen = _module("rc3_synthetic_generation", "test_generation_protocol.py")
trial = _module("rc3_synthetic_candidates", "candidate_fixtures.py")
sty = _module("rc3_synthetic_styles", "test_styles.py")
enf = _module("rc3_synthetic_control", "test_eligibility_enforcement.py")
content_trials = _module("rc3_synthetic_content_trials", "test_content_candidates.py")
flow = gen.flow


def _set_notes(page, text):
    """Keep a complete canonical mapping for the explicit synthetic notes."""
    page["speaker_notes"] = text
    if page.get('content_mapping') is not None:
        page['content_mapping']['speech_segments'] = [{
            'segment_id': 'L1-notes', 'start_codepoint': 0, 'end_codepoint': len(text),
            'narrative_node_ids': [], 'kind': 'cue', 'estimated_seconds': None}] if text else []
    return page


def _edit_notes(store, page_id, text="中文 54/120=45%，不是节约率。\n\n末段原注"):
    doc = store.load_document()
    entry = next(entry for entry in doc["pages"] if entry["page_id"] == page_id)
    page = _set_notes(store.read_object_json(entry['page']), text)
    editing.edit_page(store.project_root, page=page, base_revision=doc["revision_id"],
                      page_hash=entry["page"]["sha256"], operation_id=str(uuid.uuid4()))
    return store.load_document()


@pytest.mark.parametrize("phase", ["before_claim", "before_freeze", "after_freeze", "after_begin"])
def test_actual_task_notes_edit_keeps_inputs_frozen_hash_and_one_call(flow, phase):
    project, store, task, native = flow
    original_task = tasks._lookup_task(store.load_document(), task["task_id"], store)
    original_request, original_ref = stored_blueprint_request(store, original_task)
    before_page = store.load_document()["pages"][0]["page"]
    frozen = attempt = None
    if phase != "before_claim":
        gen.start(flow)
    if phase in ("after_freeze", "after_begin"):
        frozen = gen.freeze(flow)
    if phase == "after_begin":
        attempt = gen.begin(flow, frozen)
    before = tasks._lookup_task(store.load_document(), task["task_id"], store)
    doc = _edit_notes(store, "p1")
    current = tasks._lookup_task(doc, task["task_id"], store)
    assert current == before
    assert current["inputs"] == original_task["inputs"]
    assert stored_blueprint_request(store, current) == (original_request, original_ref)
    assert tasks.task_inputs_current(store, doc, current)
    assert page_visual_equivalent(store, before_page, doc["pages"][0]["page"], "p1")
    if phase == "before_claim":
        gen.start(flow)
    if frozen is None:
        frozen = gen.freeze(flow)
    if attempt is None:
        attempt = gen.begin(flow, frozen)
    report, raw = native(prompt=frozen["input"]["prompt"])
    gen.settle(flow, attempt, report)
    gen.accept(flow, frozen, attempt, raw)
    current_doc = store.load_document()
    assert store.read_object_json(current_doc["pages"][0]["page"])["speaker_notes"].endswith("末段原注")
    final_task = tasks._lookup_task(current_doc, task["task_id"], store)
    assert len(final_task["generation_attempts"]) == 1
    assert final_task["generation_requests"] == [frozen["request_ref"]]
    assert generation.show(project, request_id=frozen["request_id"])["request"]["input_hash"] == frozen["input_hash"]


@pytest.mark.parametrize("mutation", ["body", "visual", "design", "font", "style"])
def test_real_task_rejects_actual_consumed_changes(flow, mutation):
    _, store, task, _ = flow
    doc = store.load_document()
    changed = copy.deepcopy(doc)
    if mutation == "design":
        changed["design_context"]["language"] = "en-US"
    elif mutation == "font":
        changed["design_context"]["fonts"][0]["family"] = "Changed actual body font"
    elif mutation == "style":
        changed["design_context"]["styles"][0]["colors"]["accent"] = "#FF0000"
    else:
        entry = changed["pages"][0]
        page = store.read_object_json(entry["page"])
        if mutation == "body":
            page["customer_visible"]["title"] += " changed"
        else:
            page["visual_spec"]["intent"] += " changed owner/arrow layout"
        entry["page"] = store.put_json_object(page)
    actual_task = tasks._lookup_task(doc, task["task_id"], store)
    assert not tasks.task_inputs_current(store, changed, actual_task)


@pytest.mark.parametrize("bad", ["missing", "identity", "prompt_hash", "conflict", "broken_ref", "shape"])
def test_unique_getter_validates_actual_inputs_without_task_preparation(flow, bad):
    _, store, summary, _ = flow
    task = tasks._lookup_task(store.load_document(), summary["task_id"], store)
    obj, ref = stored_blueprint_request(store, task)
    task = copy.deepcopy(task)
    if bad == "missing":
        task["inputs"] = [item for item in task["inputs"] if item != ref]
    elif bad == "broken_ref":
        task["inputs"] = [{"path": ".deckmaster/objects/00/missing.json", "sha256": "0" * 64}]
    else:
        altered = copy.deepcopy(obj)
        if bad == "identity":
            altered["page_id"] = "other-page"
        elif bad == "prompt_hash":
            altered["prompt_sha256"] = "0" * 64
        elif bad == "shape":
            from deck_master.models import canonical_json_bytes, sha256_bytes
            altered["projection"] = {"page_id": obj["page_id"]}
            altered["projection_sha256"] = sha256_bytes(canonical_json_bytes(altered["projection"]))
        else:
            from deck_master.models import sha256_bytes
            altered["prompt"] += " conflicting immutable preparation"
            altered["prompt_sha256"] = sha256_bytes(altered["prompt"].encode())
        replacement = store.put_json_object(altered)
        task["inputs"] = [replacement if item == ref else item for item in task["inputs"]]
        if bad == "conflict":
            task["inputs"].append(ref)
    with pytest.raises(ModelError):
        stored_blueprint_request(store, task)


def test_svg_trial_candidate_real_plan_adopt_after_notes_without_image_calls(tmp_path):
    store = trial.store.__wrapped__(tmp_path)
    task = trial.dispatch(store)
    trial.start(store, task)
    before = store.load_document()["pages"][0]
    cid = trial.accept(store, task)["candidate_ids"][0]
    _edit_notes(store, "p01")
    state = candidates.show(store.project_root, candidate_id=cid)
    assert state["generation_basis"]["status"] == "current"
    planned = trial.plan(store, [cid])
    trial.adopt(store, planned)
    doc = store.load_document()
    assert store.read_object_json(doc["pages"][0]["page"])["speaker_notes"].endswith("末段原注")
    assert doc["pages"][0]["blueprint"] == before["blueprint"]
    actual = tasks._lookup_task(doc, task["task_id"], store)
    assert not actual.get("generation_attempts")
    assert not actual["call_allowances"]


def test_confirmed_recipe_notes_equivalence_preserves_real_trial_dispatch(tmp_path):
    flow = sty.Flow(tmp_path)
    doc = flow.store.load_document()
    scope = copy.deepcopy(doc['collaboration']['request']['scope'])
    scope.update(page_ids=['p01', 'p02', 'p03'], allow_page_membership_change=False,
                 allow_page_order_change=False)
    collaboration.start_request(flow.project, input={'intent': 'full_deck', 'content_intent': None,
        'scope': scope, 'replace_request_id': doc['collaboration']['request']['request_id'],
        'instruction_evidence': evidence_for(flow.project,
            text='L1 confirmed style recipe and one explicit page trial, preserving notes.',
            locator='L1:notes-style:request')}, base_revision=doc['revision_id'], operation_id='L1-notes-style-request')
    settle_fidelity_review(flow.project, page_ids=scope['page_ids'], execution_ref='L1-notes-style-review',
        scenario='Confirmed imported style fixture')
    authorize_scope(flow.project, actions=['style.propose', 'change.commit', 'allowance.allocate', 'call.begin'],
        scope=scope, max_external_calls=1, max_candidate_count=1, adoption_policy='within_scope',
        evidence=evidence_for(flow.project, text='Authorize one L1 page style trial.', locator='L1:notes-style:grant'))
    recipe = sty.confirm(flow)
    before = flow.store.load_document()["pages"][1]
    _edit_notes(flow.store, "p02")
    task = sty.dispatch(flow, recipe)
    prepared, _ = stored_blueprint_request(flow.store, task)
    assert prepared["page_id"] == "p02"
    assert task["stage_request"]["style_recipe_ref"] == recipe["recipe_ref"]
    assert flow.store.load_document()["pages"][1]["blueprint"] == before["blueprint"]


def test_history_equivalence_rejects_wrong_id_corrupt_or_visible_change(flow):
    _, store, _, _ = flow
    ref = store.load_document()["pages"][0]["page"]
    assert not page_visual_equivalent(store, ref, ref, "different-page")
    assert not page_visual_equivalent(store, {"path": "missing", "sha256": "0" * 64}, ref, "p1")
    page = store.read_object_json(ref)
    page["customer_visible"]["title"] += " changed"
    assert not page_visual_equivalent(store, ref, store.put_json_object(page), "p1")


def test_visual_accept_refuses_old_presenter_text_after_actual_call_settlement(flow):
    project, store, summary, native = flow
    old_page = store.read_object_json(store.load_document()["pages"][0]["page"])
    gen.start(flow)
    frozen = gen.freeze(flow)
    attempt = gen.begin(flow, frozen)
    _edit_notes(store, "p1")
    report, raw = native(prompt=frozen["input"]["prompt"])
    gen.settle(flow, attempt, report)
    before = store.load_document()
    stage = store.staging_dir / summary["operation_id"]
    stage.mkdir(exist_ok=True)
    (stage / "result.png").write_bytes(raw)
    payload = {"kind": "blueprint", "pages": [old_page],
               "files": [{"file_id": "output", "path": "result.png", "media_type": "image/png"}],
               "generation_result": {"request_id": frozen["request_id"], "attempt_id": attempt["attempt_id"]},
               "artifact_specs": [{"role": "blueprint", "page_id": "p1", "file_id": "output",
                                   "provenance": {"source_type": "host_generated", "tool": "image_gen"}}]}
    with pytest.raises(tasks.EnvelopeError, match="cannot overwrite current speech"):
        service.accept_result(project, result_payload=payload,
                              **{key: summary[key] for key in ("task_id", "operation_id", "produced_against")})
    assert store.load_document() == before
    actual = tasks._lookup_task(before, summary["task_id"], store)
    assert actual["call_allowances"][0]["state"] == "consumed"
    gen.accept(flow, frozen, attempt, raw)


def _controlled_blueprint(tmp_path):
    project, store = enf._project(tmp_path)
    _seed_imported_plan(store)
    enf._start(project, store)
    enf._settle_preproduction(store, seed="rc3-notes-control")
    grant = enf._grant(project, store, actions=("dispatch.blueprint", "allowance.allocate", "task.start"))
    doc = store.load_document()
    task = service.open_blueprint_task(store, doc, doc["pages"][0])
    return project, store, task, grant


def test_active_binding_retains_visual_page_basis_after_real_notes_edit(tmp_path):
    from deck_master import eligibility
    project, store, task, _ = _controlled_blueprint(tmp_path)
    basis = copy.deepcopy(task["collaboration_binding"])
    _edit_notes(store, "p1")
    current = tasks._lookup_task(store.load_document(), task["task_id"], store)
    assert current["collaboration_binding"] == basis
    assert eligibility.task_binding_state(store, store.load_document(), current)["status"] == "valid"
    service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-notes-executor",
                       supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])


def test_visual_equivalence_never_restores_revoked_authority(tmp_path):
    from deck_master import collaboration, eligibility
    project, store, task, grant = _controlled_blueprint(tmp_path)
    _edit_notes(store, "p1")
    doc = store.load_document()
    collaboration.revoke_authorization(
        project, authorization_id=grant["authorization_id"], reason="Synthetic explicit withdrawal",
        base_revision=doc["revision_id"], operation_id="rc3-explicit-revoke")
    before = store.load_document()
    with pytest.raises(eligibility.EligibilityBlocked) as error:
        service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-notes-executor",
                           supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])
    assert "authorization_revoked" in error.value.decision["reason_codes"]
    assert store.load_document() == before


def _seed_imported_plan(store, *, speech_policy=None):
    """Import explicit role/speech input through the canonical current entry."""
    doc = store.load_document()
    ids = [entry["page_id"] for entry in doc["pages"]]
    roles = [{"page_id": pid, "role": "detail", "audience_question": "What follows?",
              "intended_takeaway": "Record the known rule", "narrative_node_ids": [],
              "source_links": [], "required_qualifications": [], "content_profile": "simple",
              "density_rationale": "One actual rule", "timing_seconds": None,
              "transition_to_next": None} for pid in ids]
    value = {"schema_version": "content_plan_input.v2", "chapters": [], "page_order": ids,
             "page_roles": roles, "page_budget": {"exact": len(ids), "target": None, "max": None},
             "time_budget": {"total_seconds": None, "speaking_seconds": None,
                             "interaction_seconds": None, "constraint": "unspecified"},
             "speech_policy": speech_policy or {"mode": "none", "source": "default", "output": "none"},
             "issues": [], "tradeoff_issue_ids": []}
    return service.import_draft(store.project_root,
        draft_payload={'pages': [store.read_object_json(entry['page']) for entry in doc['pages']],
                       'page_order': ids, 'content_plan': value},
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()),
        instruction_evidence={'kind': 'host_attested_instruction',
            'text': 'Import this explicit confirmed manuscript role mapping and speech policy.',
            'source_locator': 'L1:role-mapping-import'}, preserve_mainline=True)


def _blueprint_with_imported_plan(tmp_path):
    project, store = enf._project(tmp_path)
    _seed_imported_plan(store)
    enf._start(project, store)
    enf._settle_preproduction(store, seed="rc3-imported-role-control")
    enf._grant(project, store, actions=("dispatch.blueprint", "allowance.allocate", "task.start"))
    doc = store.load_document()
    task = service.open_blueprint_task(store, doc, doc["pages"][0])
    return project, store, task


def test_imported_null_narrative_notes_rebind_keeps_actual_consumed_role_basis(tmp_path):
    from deck_master import eligibility
    project, store, task = _blueprint_with_imported_plan(tmp_path)
    original = copy.deepcopy(task)
    old_plan = store.load_document()["content_plan"]
    doc = _edit_notes(store, "p1")
    assert doc["content_plan"] != old_plan
    assert store.read_object_json(doc["content_plan"])["narrative_ref"] is None
    assert tasks.task_inputs_current(store, doc, task)
    assert eligibility.task_binding_state(store, doc, task)["status"] == "valid"
    assert tasks._lookup_task(doc, task["task_id"], store) == original
    service.task_start(project, task_id=task["task_id"], execution_ref="synthetic-role-executor",
                       supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])


@pytest.mark.parametrize("affected", ["same_page_role", "other_page_role", "global_order"])
def test_real_dispatched_task_consumes_scoped_roles_and_global_order(tmp_path, affected):
    from deck_master import eligibility
    _, store, task = _blueprint_with_imported_plan(tmp_path)
    doc = store.load_document()
    current = copy.deepcopy(doc)
    plan = store.read_object_json(doc["content_plan"])
    if affected == "global_order":
        plan["input"]["page_order"].reverse()
        current["pages"].reverse()
    else:
        index = int(affected == "other_page_role")
        plan["input"]["page_roles"][index]["density_rationale"] += " changed density role"
    current["content_plan"] = store.put_json_object(plan)
    expected = affected == "other_page_role"
    assert tasks.task_inputs_current(store, current, task) is expected
    assert (eligibility.task_binding_state(store, current, task)["status"] == "valid") is expected


@pytest.mark.parametrize("mutation", ["arrow", "responsibility", "row_owner"])
def test_real_task_detects_relationship_and_ownership_changes_with_same_literal_set(tmp_path, mutation):
    from deck_master.content import check_page
    from deck_master.store import Store
    page = {"schema_version": "deck_page_package.v2", "page_id": "p1",
            "customer_visible": {"title": "Synthetic rule ownership", "body_blocks": [
                {"id": "b1", "type": "paragraph", "text": "Approve"},
                {"id": "b2", "type": "paragraph", "text": "Execute"},
                {"id": "t1", "type": "table", "columns": [
                    {"id": "owner", "label": "Owner"}, {"id": "value", "label": "Value"}],
                 "rows": [
                     {"id": "r1", "cells": [{"column_id": "owner", "display_text": "A"},
                                               {"column_id": "value", "display_text": "54", "value": 54}]},
                     {"id": "r2", "cells": [{"column_id": "owner", "display_text": "B"},
                                               {"column_id": "value", "display_text": "120", "value": 120}]}]}]},
            "visual_spec": {"intent": "Use actual directed relationship", "reference_mode": "new_design",
                            "nodes": [
                                {"node_id": "n1", "label_ref": "atom:p1:block:b1:text", "status": "existing",
                                 "responsibility_refs": ["atom:p1:block:b1:text"]},
                                {"node_id": "n2", "label_ref": "atom:p1:block:b2:text", "status": "existing"}],
                            "edges": [{"edge_id": "e1", "from": "n1", "to": "n2",
                                       "direction": "forward", "relationship": "handoff", "label_ref": None}]}}
    scope = {'subject': 'deck', 'page_ids': ['p1'], 'page_manifest_ref': None,
        'external_artifact_ref': None, 'layers': ['plan', 'page_copy', 'speech', 'blueprint', 'review'],
        'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'working'}
    project = public_project(tmp_path, create_input={'brief': 'Explicit synthetic visual regression'},
        manuscript={'pages': [page]}, request_input={'intent': 'full_deck', 'content_intent': None,
            'scope': scope, 'instruction_evidence': {'kind': 'host_attested_instruction',
                'text': 'L1 generate exactly one synthetic relationship page.',
                'source_locator': 'L1:relationships:request'}})['project']
    settle_fidelity_review(project, page_ids=['p1'], execution_ref='L1-relationship-review',
        scenario='Relationship and ownership visual basis')
    authorize_scope(project, actions=['dispatch.blueprint', 'allowance.allocate', 'call.begin'],
        scope=scope, max_external_calls=1, max_candidate_count=0, adoption_policy='within_scope',
        evidence=evidence_for(project, text='Authorize one bounded L1 relationship image call.',
                              locator='L1:relationships:grant'))
    summary = service.continue_project(project)["pending_tasks"][0]
    store = Store(project)
    doc = store.load_document()
    task = tasks._lookup_task(doc, summary["task_id"], store)
    updated_page = store.read_object_json(doc["pages"][0]["page"])
    if mutation == "arrow":
        updated_page["visual_spec"]["edges"][0].update({"from": "n2", "to": "n1"})
    elif mutation == "responsibility":
        updated_page["visual_spec"]["nodes"][0]["responsibility_refs"] = ["atom:p1:block:b2:text"]
    else:
        rows = updated_page["customer_visible"]["body_blocks"][2]["rows"]
        rows[0]["cells"][1], rows[1]["cells"][1] = rows[1]["cells"][1], rows[0]["cells"][1]
    updated_page = check_page(updated_page)
    current = copy.deepcopy(doc)
    old_ref = current["pages"][0]["page"]
    current["pages"][0]["page"] = store.put_json_object(updated_page)
    assert not page_visual_equivalent(store, old_ref, current["pages"][0]["page"], "p1")
    assert not tasks.task_inputs_current(store, current, task)


@pytest.mark.parametrize("kind", ["page", "content_update"])
def test_content_candidate_notes_adoption_protects_current_same_cas_and_old_core_refuses(tmp_path, kind):
    import json
    import subprocess
    python = Path('/workspace/work/rc3/baseline-a/venv/bin/python')
    store = trial.store.__wrapped__(tmp_path)
    path = store.project_root
    if kind == 'content_update':
        doc = store.load_document()
        scope = doc['collaboration']['request']['scope']
        collaboration.record_decision(path, input={'topic': 'direction', 'subject_refs': [],
            'value': 'Retain the confirmed manuscript direction while rewriting the selected copy.',
            'disposition': 'accepted', 'authority_mode': 'direct_user', 'scope': scope,
            'instruction_evidence': evidence_for(path,
                text='Use the existing direction for this explicit L1 selected-copy rewrite.',
                locator='L1:content-notes:direction')}, base_revision=doc['revision_id'],
            operation_id='L1-content-notes-direction')
        authorize_scope(path, actions=['content.operation'], scope=scope, max_external_calls=0,
            max_candidate_count=1, adoption_policy='within_scope', evidence=evidence_for(path,
                text='Authorize one L1 content changeset trial and its explicit selection.',
                locator='L1:content-notes:grant'))
    original = store.load_document()
    assert original['compatibility']['minimum_writer'] == 'method-catalog.v1'
    if kind == 'page':
        task = content_trials.dispatch_content_trial(path, store)
        envelope = content_trials.page_envelope(store, task)
        _set_notes(envelope['pages'][0], '采用时保护中文 54/120=45%，不是节约率。\n\n末段')
    else:
        _edit_notes(store, 'p01', '完整 changeset 备注。\n\n末段')
        settle_fidelity_review(path, page_ids=['p01', 'p02'], execution_ref='L1-content-notes-fidelity',
            scenario='Notes are current before a page-copy-only rewrite candidate')
        original = store.load_document()
        task = content_trials.dispatch_content_ops_trial(path, store, 'rewrite', ['p01'])
        envelope = content_trials.changeset_envelope(store, task, 'rewrite')
        content_trials.start_task(path, task)
        refused = copy.deepcopy(envelope)
        _set_notes(refused['content_update']['upsert_pages'][0], 'Unauthorized speech change via page_copy')
        before = store.load_document()
        with pytest.raises(tasks.EnvelopeError, match='page_copy cannot silently change speech'):
            content_trials.accept(path, task, refused)
        assert store.load_document() == before
    content_trials.start_task(path, task)
    result = content_trials.accept(path, task, envelope)
    recorded = store.load_document()
    assert recorded['pages'] == original['pages']
    assert recorded['compatibility']['minimum_writer'] == original['compatibility']['minimum_writer']
    outcome = content_trials.adopt(path, store, result['candidate_ids'])
    protected = store.load_document()
    assert protected['revision_id'] == outcome['revision_id']
    assert protected['compatibility']['minimum_writer'] == 'method-catalog.v1'
    adopted_page = store.read_object_json(protected['pages'][0]['page'])
    assert adopted_page['speaker_notes'].endswith('末段')
    assert all(not store.read_object_json(ref).get('generation_attempts') for ref in protected['tasks'])
    if not python.exists():
        pytest.skip('Frozen A installation is an external engineering resource')
    code = '''import json,sys
from deck_master import editing,pipeline,service
project=sys.argv[1];page=json.loads(sys.argv[2]);out={}
ops={"edit":lambda:editing.edit_page(project,page=page,base_revision="old",page_hash="old",operation_id="old-write"),
"compile":lambda:pipeline.produce(project),
"claim":lambda:service.task_start(project,task_id="old",execution_ref="old-host")}
for name,fn in ops.items():
 try:fn();out[name]={"refused":False}
 except Exception as error:
  causes=[];seen=set();cause=error
  while cause is not None and id(cause) not in seen:
   seen.add(id(cause));causes.append(str(cause));cause=cause.__cause__ or cause.__context__
  out[name]={"refused":True,"reason":"; ".join(causes)}
print(json.dumps(out))
'''
    actual = subprocess.run([str(python), '-I', '-c', code, str(path), json.dumps(adopted_page)],
                            capture_output=True, text=True, check=True)
    outcomes = json.loads(actual.stdout)
    assert all(item['refused'] and 'minimum writer' in item['reason'] for item in outcomes.values())
    assert store.load_document() == protected


def test_empty_notes_content_candidate_preserves_current_writer_floor(tmp_path):
    store = trial.store.__wrapped__(tmp_path)
    path = store.project_root
    before_writer = store.load_document()['compatibility']['minimum_writer']
    task = content_trials.dispatch_content_trial(path, store)
    content_trials.start_task(path, task)
    envelope = content_trials.page_envelope(store, task)
    _set_notes(envelope['pages'][0], '')
    result = content_trials.accept(path, task, envelope)
    content_trials.adopt(path, store, result['candidate_ids'])
    assert store.load_document()['compatibility']['minimum_writer'] == before_writer == 'method-catalog.v1'


@pytest.mark.parametrize('output', ['pptx_notes', 'both', 'separate_script'])
def test_explicit_content_candidate_policy_consumption_protects_writer_even_without_notes(tmp_path, output):
    """Explicit canonical policy input remains protected even without notes."""
    store = trial.store.__wrapped__(tmp_path)
    path = store.project_root
    _seed_imported_plan(store, speech_policy={'mode': 'cues', 'source': 'provided', 'output': output})
    settle_fidelity_review(path, page_ids=['p01', 'p02'], execution_ref='L1-policy-fidelity',
        scenario='Explicit imported speech output policy with empty original notes')
    task = content_trials.dispatch_content_trial(path, store)
    content_trials.start_task(path, task)
    envelope = content_trials.page_envelope(store, task, title_suffix='')
    assert not envelope['pages'][0].get('speaker_notes')
    result = content_trials.accept(path, task, envelope)
    before = store.load_document()
    assert before['compatibility']['minimum_writer'] == 'method-catalog.v1'
    content_trials.adopt(path, store, result['candidate_ids'])
    adopted = store.load_document()
    assert adopted['compatibility']['minimum_writer'] == 'method-catalog.v1'
    assert adopted['pages'] == before['pages']
    assert adopted['content_plan'] == before['content_plan']
