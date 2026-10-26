"""Prompt transport/editability boundary; no generated-image quality claim."""
import copy
import json

import pytest

from deck_master import generation, models, production, service
from test_rc3_design_requirements import _snapshot
from test_rc3_notes_visual_inputs import _blueprint_with_imported_plan
from test_rp17_design_policy import _change_page, _policy, _request


@pytest.mark.parametrize('strategy', ['agreed_layout', 'model_designed'])
def test_actual_blueprint_prompt_explains_native_and_raster_boundary(tmp_path, strategy):
    store, doc, _ = _snapshot(tmp_path)
    page = _change_page(store, doc, 0,
        lambda value: value['visual_spec'].update(design_policy=_policy(strategy)))
    before = copy.deepcopy(page)
    prepared = _request(store, doc)
    instructions, payload = prepared['prompt'].split('Structured input:\n', 1)
    assert 'native editable PowerPoint text and shapes' in instructions
    assert 'relationship connectors and principal business objects' in instructions
    assert 'replaceable as a whole' in instructions and 'not individually editable' in instructions
    assert 'full-slide embedded image' in instructions
    assert 'Before generation or reconstruction' in instructions
    assert 'native redrawing, a bounded raster asset or simplification' in instructions
    assert 'visual and editability impact' in instructions
    assert 'photos, shadows and illustrations are not categorically forbidden' in instructions
    assert json.loads(payload) == prepared['projection']
    assert prepared['projection']['design_policy']['strategy'] == strategy
    assert prepared['projection']['customer_visible'] == page['customer_visible']
    assert prepared['projection']['visual_spec']['nodes'] == page['visual_spec']['nodes']
    assert prepared['projection']['visual_spec']['edges'] == page['visual_spec']['edges']
    assert page == before


@pytest.mark.parametrize('historical_prefix', [False, True])
def test_freeze_preserves_exact_prepared_prompt_without_reinterpreting_old_prefix(tmp_path, monkeypatch, historical_prefix):
    current_prompt = production.project_prompt
    if historical_prefix:
        def old_prompt(*args, **kwargs):
            prepared = current_prompt(*args, **kwargs)
            payload = json.dumps(prepared['projection'], ensure_ascii=False, indent=2, sort_keys=True)
            prepared['prompt'] = 'Historical frozen blueprint instruction.\nStructured input:\n' + payload
            prepared['prompt_sha256'] = models.sha256_bytes(prepared['prompt'].encode('utf-8'))
            return prepared
        # Isolated old-prefix fixture only at original dispatch. New code must
        # subsequently read/freeze those exact immutable bytes, not regenerate.
        # open_blueprint_task uses service's module-level imported alias.
        # Patch the actual dispatch callsite; keep the production reader on
        # today's implementation even while creating the historical fixture.
        monkeypatch.setattr(service, 'project_prompt', old_prompt)
    project, store, task = _blueprint_with_imported_plan(tmp_path)
    monkeypatch.setattr(service, 'project_prompt', current_prompt)
    prepared, ref = production.stored_blueprint_request(store, task)
    original_bytes = store.read_object_bytes(ref)
    assert ('Editability boundary' in prepared['prompt']) is not historical_prefix
    service.task_start(project, task_id=task['task_id'], execution_ref='synthetic-editability-transport',
        supported_protocols=[generation.PROTOCOL], capabilities=task['required_capabilities'])
    actual_input = generation.prepared_input(store, store.load_document(), task)
    assert actual_input['prompt'] == prepared['prompt']
    frozen = generation.freeze(project, task_id=task['task_id'], input=actual_input,
        base_revision=store.current_revision_id(), operation_id='editability-prompt-freeze')
    assert frozen['input'] == actual_input
    assert store.read_object_bytes(ref) == original_bytes
    assert production.stored_blueprint_request(store, task) == (prepared, ref)
