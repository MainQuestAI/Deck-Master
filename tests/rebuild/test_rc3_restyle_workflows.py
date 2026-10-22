"""Formal v3 style transactions with synthetic L1 control/tool evidence only.

These tests prove input, attachment, freshness and fee-ledger behavior.  They
do not call an image model or assert design quality or human acceptance.
"""
import copy
import io
import json
import uuid

import pytest
from PIL import Image

from deck_master import candidates, collaboration, editing, eligibility, generation, service, tasks, visual_styles
from deck_master.models import canonical_json_bytes
from deck_master.content import atom_ids
from deck_master.native_image_evidence import NativeImageRegistry, NativeImageRuntime, image_binding
from deck_master.production import stored_blueprint_request
from test_rc3_design_recipes import input_value
from test_rc3_design_workflows import confirmed, dispatch
from test_rc3_native_image_bridge import SyntheticController
from test_rc3_notes_visual_inputs import enf, _seed_imported_plan


def project(tmp_path):
    path, store = enf._project(tmp_path)
    _seed_imported_plan(store)
    enf._start(path, store)
    enf._settle_preproduction(store, seed="rc3-restyle-l1")
    grant = enf._grant(path, store, actions=("style.propose", "design.update", "asset.import", "page.edit",
        "change.commit", "task.start", "task.cancel", "call.begin", "result.accept", "candidate.adopt", "allowance.allocate"),
        max_external_calls=2, max_candidate_count=2)
    return path, store, grant


def begin(path, store, task):
    execution = "synthetic-restyle-native-l1"
    service.task_start(path, task_id=task["task_id"], execution_ref=execution,
                       supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])
    prepared = generation.prepared_input(store, store.load_document(), task)
    frozen = generation.freeze(path, task_id=task["task_id"], input=prepared,
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    attempt = tasks.call_begin(store, task_id=task["task_id"], allowance_id=task["call_allowances"][0]["allowance_id"],
                              execution_ref=execution, request_id=frozen["request_id"])
    binding, _, actual, _ = image_binding(store, store.load_document(), task["task_id"], attempt["attempt_id"])
    controller = SyntheticController(binding, actual)
    controller.claims["event_id"] = task["task_id"]
    refs = frozen["input"]["references"]
    if refs:
        controller.claims["arguments"]["referenced_image_paths"] = [str(store.project_root / ref["file"]["path"]) for ref in refs]
    registry = NativeImageRegistry()
    registry.register(controller)
    return frozen, attempt, controller, registry


def settle(store, task, sent, *, after_context=None):
    frozen, attempt, controller, registry = sent
    report = {"source": "native_host_image.v1", "provider_id": controller.provider_id, "event_id": task["task_id"]}
    with NativeImageRuntime(registry).bound():
        context = registry.image_context(store, store.load_document(), task_id=task["task_id"],
            attempt_id=attempt["attempt_id"], selector={"provider_id": controller.provider_id, "event_id": task["task_id"]})
        if after_context:
            after_context()
        result = tasks.call_settle(store, task_id=task["task_id"], allowance_id=attempt["allowance_id"],
            attempt_id=attempt["attempt_id"], outcome="consumed", report_bytes=canonical_json_bytes(report), adapter_context=context)
    return result


def payload(store, task, sent):
    frozen, attempt, controller, _ = sent
    stage = store.staging_dir / task["operation_id"]
    stage.mkdir(exist_ok=True)
    (stage / "result.png").write_bytes(controller.png)
    return {"kind": "blueprint", "files": [{"file_id": "output", "path": "result.png", "media_type": "image/png"}],
            "generation_result": {"request_id": frozen["request_id"], "attempt_id": attempt["attempt_id"]},
            "artifact_specs": [{"role": "blueprint", "page_id": task["scope_pages"][0], "file_id": "output",
                                "provenance": {"source_type": "host_generated", "tool": "image_gen"}}]}


def accept(path, store, task, sent):
    return service.accept_result(path, result_payload=payload(store, task, sent),
        **{key: task[key] for key in ("task_id", "operation_id", "produced_against")})


def candidate(path, store, task):
    sent = begin(path, store, task)
    assert settle(store, task, sent)["native_observation_status"] == "accepted"
    result = accept(path, store, task, sent)
    assert result["status"] == "candidate_ready" and result["current_artifacts_changed"] is False
    return result["candidate_ids"][0], sent


def adopted_initial(path, store):
    initial = confirmed(path, store)
    task = dispatch(path, store, initial, ["p1"])[0]
    candidate_id, sent = candidate(path, store, task)
    doc = store.load_document()
    plan = candidates.plan(path, input={"schema_version": "candidate_selection.v1", "project_id": doc["project_id"],
        "base_revision": doc["revision_id"], "candidate_ids": [candidate_id]})["plan"]
    candidates.adopt(path, input=plan, base_revision=plan["base_revision"], operation_id=str(uuid.uuid4()))
    blueprint = store.load_document()["pages"][0]["blueprint"]
    assert blueprint == candidates.show(path, candidate_id=candidate_id)["candidate"]["result_ref"]
    return blueprint, sent


def import_reference(path, store, *, jpeg=False):
    image = Image.new("RGB", (80, 40), "#336699" if jpeg else "#996633")
    stream = io.BytesIO()
    if jpeg:
        exif = Image.Exif()
        exif[274] = 6
        image.save(stream, format="JPEG", exif=exif)
    else:
        image.save(stream, format="PNG")
    raw = stream.getvalue()
    out = visual_styles.import_reference(path, data=raw, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    reference_id = out["operation_result"]["reference_id"]
    row = visual_styles.listing(path, reference_id=reference_id)["references"][0]
    description = {"kind": "external", "reference_id": reference_id, "artifact_ref": row["reference"]["artifact_ref"], "role": "reference"}
    return description, row, raw


def edit(path, store, page_id, mutate):
    doc = store.load_document()
    entry = next(item for item in doc["pages"] if item["page_id"] == page_id)
    page = store.read_object_json(entry["page"])
    old_notes = page.get('speaker_notes', '')
    mutate(page)
    mapping = page.get('content_mapping')
    if mapping is not None and mapping.get('narrative_ref') is None:
        previous = {link['element_ref']: link for link in mapping['visible_links']}
        mapping['visible_links'] = [copy.deepcopy(previous.get(atom, {
            'element_ref': atom, 'narrative_node_ids': [], 'source_links': []})) for atom in sorted(atom_ids(page))]
        if page.get('speaker_notes', '') != old_notes:
            from test_rc3_notes_visual_inputs import _set_notes
            _set_notes(page, page.get('speaker_notes', ''))
    editing.edit_page(path, page=page, base_revision=doc["revision_id"], page_hash=entry["page"]["sha256"], operation_id=str(uuid.uuid4()))


def allowance_states(store):
    return [allowance["state"] for ref in store.load_document()["tasks"]
            for allowance in store.read_object_json(ref).get("call_allowances", [])]


def test_restyle_uses_target_first_then_ordered_original_jpeg_and_png_through_freeze(tmp_path):
    path, store, _ = project(tmp_path)
    target_ref, _ = adopted_initial(path, store)
    jpeg, jpeg_row, jpeg_raw = import_reference(path, store, jpeg=True)
    png, png_row, png_raw = import_reference(path, store)
    value = input_value(store.load_document(), intent="restyle", ids=["p1"])
    value["reference_refs"] = [jpeg, png]
    recipe = confirmed(path, store, **value)
    task = dispatch(path, store, recipe, ["p1"])[0]
    expected = [{"file": store.read_object_json(target_ref)["file"], "role": "reference"},
                {"file": jpeg_row["original"]["file"], "role": "reference"},
                {"file": png_row["original"]["file"], "role": "reference"}]
    assert task["stage_request"]["references"] == expected
    assert task["stage_request"]["target_reference_ref"] == target_ref
    assert expected[1]["file"] != jpeg_row["preview"]["file"]
    assert store.read_object_bytes(expected[1]["file"]) == jpeg_raw
    assert store.read_object_bytes(expected[2]["file"]) == png_raw
    assert jpeg_row["original"]["media_type"] == "image/jpeg"
    assert jpeg_row["preview"]["media_type"] == "image/png"
    assert (jpeg_row["reference"]["width"], jpeg_row["reference"]["height"]) == (40, 80)
    prepared = generation.prepared_input(store, store.load_document(), task)
    stored, _ = stored_blueprint_request(store, task)
    immutable_recipe = store.read_object_json(recipe["recipe_ref"])
    parameters = {key: immutable_recipe["parameters"][key] for key in ("palette", "typography", "density", "composition", "spacing", "lines", "icons")}
    assert prepared["references"] == expected
    assert prepared["design_context"]["recipe_parameters"] == prepared["constraints"]["recipe_parameters"] == parameters
    assert stored["projection"]["recipe_parameters"] == parameters
    prompt_projection = json.loads(prepared["prompt"].split("Structured input:\n", 1)[1])
    assert prompt_projection == stored["projection"]
    assert prompt_projection["recipe_parameters"] == parameters
    service.task_start(path, task_id=task["task_id"], execution_ref="synthetic-restyle-native-l1",
                       supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])
    wrong_references = copy.deepcopy(prepared)
    wrong_references["references"][1]["file"] = jpeg_row["preview"]["file"]
    before = store.read_current()
    with pytest.raises(generation.GenerationError, match="reference"):
        generation.freeze(path, task_id=task["task_id"], input=wrong_references,
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert store.read_current() == before
    wrong_parameters = copy.deepcopy(prepared)
    wrong_parameters["design_context"]["recipe_parameters"]["density"] = "Unconfirmed execution parameter"
    with pytest.raises(generation.GenerationError):
        generation.freeze(path, task_id=task["task_id"], input=wrong_parameters,
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert store.read_current() == before
    original_pages = copy.deepcopy(store.load_document()["pages"])
    candidate_id, sent = candidate(path, store, task)
    detail = candidates.show(path, candidate_id=candidate_id)
    assert detail["references"] == expected
    assert [row["file"] for row in detail["reference_sources"]] == [row["file"] for row in expected[1:]]
    assert store.read_object_bytes(detail["reference_sources"][0]["file"]) == jpeg_raw
    assert store.read_object_bytes(detail["reference_sources"][1]["file"]) == png_raw
    frozen, attempt, controller, _ = sent
    assert frozen["input"] == prepared
    assert controller.claims["arguments"]["referenced_image_paths"] == [str(store.project_root / item["file"]["path"]) for item in expected]
    shown = generation.show(path, attempt_id=attempt["attempt_id"])
    assert shown["observations"][-1]["submitted"]["references"] == expected
    assert shown["call"]["state"] == "consumed"
    assert store.load_document()["pages"] == original_pages


@pytest.mark.parametrize("ids", [["p1"], ["p1", "p2"]])
def test_explicit_initial_scope_one_or_two_pages_stays_candidate_only(tmp_path, ids):
    path, store, _ = project(tmp_path)
    original = copy.deepcopy(store.load_document()["pages"])
    recipe = confirmed(path, store)
    pair = dispatch(path, store, recipe, ids)
    assert len(pair) == len(ids)
    for task in reversed(pair):
        assert task["stage_request"]["references"] == []
        assert task["collaboration_binding"]["adoption_policy"] == "candidate_only"
        candidate(path, store, task)
    assert store.load_document()["pages"] == original
    assert allowance_states(store).count("consumed") == len(ids)
    assert not store.load_document().get("candidate_adoptions")


@pytest.mark.parametrize("mutation", ["used_font", "effective_parameter", "unused_font", "unrelated_density", "sibling_recipe"])
def test_consumed_font_and_page_parameters_alone_control_task_freshness(tmp_path, mutation):
    path, store, _ = project(tmp_path)
    design = copy.deepcopy(store.load_document()["design_context"])
    unused = copy.deepcopy(design["fonts"][0])
    unused["font_id"] = "unused"
    design["fonts"].append(unused)
    service.update_design(path, design_context=design, base_revision=store.current_revision_id())
    value = input_value(store.load_document())
    value["recipe_draft"]["allowed_overrides"] = ["typography"]
    recipe = confirmed(path, store, **value)
    task = dispatch(path, store, recipe, ["p1"])[0]
    frozen_before = generation.prepared_input(store, store.load_document(), task)
    if mutation in ("used_font", "unused_font"):
        design = copy.deepcopy(store.load_document()["design_context"])
        selected = next(font for font in design["fonts"] if font["font_id"] == ("body" if mutation == "used_font" else "unused"))
        selected["family"] = "Changed synthetic face"
        service.update_design(path, design_context=design, base_revision=store.current_revision_id())
    elif mutation == "effective_parameter":
        edit(path, store, "p1", lambda page: page["visual_spec"].update(design_overrides={"body_font_id": "heading"}))
    elif mutation == "unrelated_density":
        edit(path, store, "p2", lambda page: page["visual_spec"].update(intent="Unrelated p2 density layout change"))
    else:
        newer = input_value(store.load_document())
        newer["recipe_draft"]["density"] = "New sibling recipe keeps all details in another layout."
        confirmed(path, store, **newer)
    doc = store.load_document()
    current = tasks._lookup_task(doc, task["task_id"], store)
    expected = mutation in ("unused_font", "unrelated_density", "sibling_recipe")
    assert tasks.task_inputs_current(store, doc, current) is expected
    assert generation.prepared_input(store, doc, current) == frozen_before
    assert allowance_states(store) == ["reserved"]
    if expected:
        enf._settle_preproduction(store, seed="rc3-restyle-current-snapshot-" + mutation)
        service.task_start(path, task_id=task["task_id"], execution_ref="synthetic-current-style",
            supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])
    else:
        before = store.read_current()
        with pytest.raises((tasks.StaleInputContext, tasks.TaskConflict, eligibility.EligibilityBlocked)):
            service.task_start(path, task_id=task["task_id"], execution_ref="synthetic-stale-style",
                supported_protocols=[generation.PROTOCOL], capabilities=task["required_capabilities"])
        assert store.read_current() == before


def test_exhausted_trial_budget_refuses_new_dispatch_and_preserves_consumed_calls(tmp_path):
    path, store, _ = project(tmp_path)
    recipe = confirmed(path, store)
    pair = dispatch(path, store, recipe, ["p1", "p2"])
    for task in pair:
        candidate(path, store, task)
    before = store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        dispatch(path, store, recipe, ["p1"])
    assert "budget_exhausted" in failure.value.decision["reason_codes"]
    assert store.read_current() == before
    assert allowance_states(store) == ["consumed", "consumed"]
    assert len(candidates.listing(path)["candidates"]) == 2


def test_scope_replacement_refuses_outside_page_dispatch_without_reservations(tmp_path):
    path, store, _ = project(tmp_path)
    recipe = confirmed(path, store)
    doc = store.load_document()
    enf._start(path, store, operation_id="restyle-scope-replace", replace_request_id=doc["collaboration"]["request"]["request_id"],
               scope=enf._scope(page_ids=["p1"]))
    enf._settle_preproduction(store, seed="restyle-scope-current")
    enf._grant(path, store, actions=("change.commit", "task.start", "call.begin", "result.accept"),
               scope=enf._scope(page_ids=["p1"]), operation_id="restyle-scope-grant", max_external_calls=1)
    before = store.read_current()
    with pytest.raises(eligibility.EligibilityBlocked) as failure:
        dispatch(path, store, recipe, ["p2"])
    assert "scope" in json.dumps(failure.value.decision)
    assert store.read_current() == before and allowance_states(store) == []


@pytest.mark.parametrize("control", ["cancel", "pause", "replace_scope"])
def test_late_trial_result_refused_after_control_change_retains_consumed_fee_fact(tmp_path, control):
    path, store, _ = project(tmp_path)
    recipe = confirmed(path, store)
    task = dispatch(path, store, recipe, ["p1"])[0]
    sent = begin(path, store, task)
    original = copy.deepcopy(store.load_document()["pages"])
    def change_control():
        doc = store.load_document()
        if control == "cancel":
            service.task_cancel(path, task_id=task["task_id"], reason="Synthetic cancel after begin")
        elif control == "pause":
            collaboration.pause_request(path, reason="Synthetic pause after begin", base_revision=doc["revision_id"], operation_id="restyle-pause")
        else:
            enf._start(path, store, operation_id="restyle-late-scope", replace_request_id=doc["collaboration"]["request"]["request_id"],
                       scope=enf._scope(page_ids=["p2"]))
    settle(store, task, sent, after_context=change_control)
    before = store.read_current()
    before_doc = store.load_document()
    with pytest.raises((eligibility.EligibilityBlocked, tasks.TaskConflict, generation.GenerationError)):
        accept(path, store, task, sent)
    if control in ("cancel", "replace_scope"):
        assert tasks._lookup_task(before_doc, task["task_id"], store)["status"] == (
            "cancelled" if control == "cancel" else "superseded")
        # First cancelled/superseded submission records a late-settlement receipt; retry
        # cannot duplicate that fact or adopt the output.
        settled_pointer = store.read_current()
        with pytest.raises(tasks.TaskConflict, match="late result call facts were settled"):
            accept(path, store, task, sent)
        assert store.read_current() == settled_pointer
    else:
        assert store.read_current() == before
    shown = generation.show(path, attempt_id=sent[1]["attempt_id"])
    assert shown["call"]["state"] == "consumed"
    final_doc = store.load_document()
    final_task = tasks._lookup_task(final_doc, task["task_id"], store)
    assert final_task["usage"] == {"source": "not_reported", "external_calls": None}
    assert final_doc["outputs"] == before_doc["outputs"]
    assert final_doc["collaboration"] == before_doc["collaboration"]
    assert store.load_document()["pages"] == original
    assert not candidates.listing(path)["candidates"]
