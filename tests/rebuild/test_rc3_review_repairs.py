"""R1 repairs through formal SDK transactions; all inputs are synthetic L1."""
import copy
import uuid

import pytest

from deck_master import generation, service, tasks
from deck_master.production import stored_blueprint_request
from deck_master.store import Store
from test_rc3_design_workflows import project, confirmed, dispatch
from test_rc3_notes_visual_inputs import enf
from test_content_ops import prepare_editorial_project


def test_actual_frozen_prompt_returns_missing_quantitative_basis_to_content(tmp_path):
    path=tmp_path/'missing-quantitative-basis'
    page=enf._page('p1','需要真实ROI比较；收入、成本和时间依据缺失。不得以示意数量图替代判断。')
    service.create(path,brief='Synthetic explicit quantitative gap',draft={'pages':[page]},project_format='workbench.v3')
    prepare_editorial_project(path)
    summary=service.continue_project(path)['pending_tasks'][0]
    store=Store(path)
    service.task_start(path,task_id=summary['task_id'],execution_ref='synthetic-gap-review',supported_protocols=[generation.PROTOCOL],capabilities=summary['required_capabilities'])
    frozen=generation.freeze(path,task_id=summary['task_id'],input=summary['generation_input'],base_revision=store.current_revision_id(),operation_id='freeze-quantitative-gap')
    prompt=frozen['input']['prompt']
    assert 'return that gap to the content stage for the necessary evidence' in prompt
    assert 'only when the fixed manuscript explicitly requests them' in prompt
    assert 'unlabeled schematic marked' not in prompt
    assert '示意数据' not in prompt
    assert frozen['input']['design_context']['content_requirements']==summary['production_request']['projection']['content_requirements']
    assert summary['production_request']['projection']['customer_visible']['body_blocks']==page['customer_visible']['body_blocks']
    task=tasks._lookup_task(store.load_document(),summary['task_id'],store)
    assert task['call_allowances'][0]['state']=='reserved' and not task['generation_attempts']


@pytest.mark.parametrize('prior_notes_floor',[False,True])
def test_classic_reader_keeps_original_preparation_floor_and_protocol(tmp_path,prior_notes_floor):
    from deck_master import eligibility, models
    from deck_master.production import project_prompt, resolve_design
    from rc3_fixtures import historical_snapshot, source_snapshot
    fixed = enf._page('p1', 'Classic copy.')
    if prior_notes_floor:
        fixed['speaker_notes'] = 'Actual historical speaker-only edit'
    path = historical_snapshot(tmp_path, scenario='Fixed pre-RC3 blueprint queue/preparation',
        pages=[fixed], minimum_writer='workbench-quality.v1' if prior_notes_floor else None)['project']
    store = Store(path)
    document = store.load_document()
    page_ref = document['pages'][0]['page']
    design, _ = resolve_design(fixed, document['design_context'], document['design_context']['assets'])
    preparation = project_prompt(fixed, design, design['assets'])
    preparation_ref = store.put_json_object(preparation)
    task = tasks.new_task(task_id='historical-blueprint', operation_id='historical-blueprint-op',
        kind='blueprint', scope_pages=['p1'], instruction='Originally stored pre-RC3 preparation',
        inputs=[page_ref, preparation_ref], dependencies=[], dispatch_revision=document['revision_id'],
        produced_against=models.content_identity(document))
    recorded = models.bump_revision(document, {'operation_id': 'historical-queue-fixture',
        'kind': 'task_update', 'description': 'Explicit old reader facts; no public legacy dispatch', 'read_set': []})
    recorded['tasks'] = [store.put_json_object(task)]
    store.commit_change(base_revision=document['revision_id'], document=recorded, operation_id='historical-queue-fixture')
    before = source_snapshot(path)
    pointer = store.read_current()
    actual = tasks._lookup_task(store.load_document(), task['task_id'], store)
    read, ref = stored_blueprint_request(store, actual)
    assert read == preparation and ref == preparation_ref
    assert read.get('resolved_design_context') is None
    assert 'content_requirements' not in read['projection']
    assert not actual.get('protocol_version') and not actual.get('required_capabilities')
    service.task_summary(store, store.load_document(), actual)
    assert store.read_current() == pointer and source_snapshot(path) == before
    # Reading the original queue cannot authorize new production/claims.
    with pytest.raises(eligibility.EligibilityBlocked) as blocked:
        service.task_start(path, task_id=actual['task_id'], execution_ref='new-unmigrated-host')
    assert 'migration_required' in blocked.value.decision['reason_codes']
    assert store.read_current() == pointer and source_snapshot(path) == before


def test_workorder_uses_whole_immutable_recipe_context_even_after_live_change(tmp_path):
    path,store,_=project(tmp_path)
    recipe=confirmed(path,store)
    task=dispatch(path,store,recipe,['p1'])[0]
    preparation,_=stored_blueprint_request(store,task)
    summary=service.task_summary(store,store.load_document(),task)
    assert summary['resolved_design_context']==preparation['resolved_design_context']==summary['generation_input']['design_context']
    assert summary['resolved_design_context']['styles'][0]['colors']['accent']=='#006688'
    frozen_context=copy.deepcopy(summary['resolved_design_context'])
    # A read-only alternative live view cannot silently replace the context of
    # an old request. It is not committed, nor a claim that stale work may run.
    live=copy.deepcopy(store.load_document());live['design_context']['styles'][0]['colors']['accent']='#992222'
    changed=service.task_summary(store,live,task)
    assert changed['resolved_design_context']==frozen_context
    assert changed['generation_input']['design_context']==frozen_context


def test_explicit_nonquantitative_teaching_mechanism_remains_legal(tmp_path):
    path=tmp_path/'explicit-teaching'
    page=enf._page('p1','教学步骤：模型草拟，人工确认后提交。仅定性机制示意，不表达数量、比例或效果判断。')
    page['visual_spec']['intent']='明确的非量化教学机制示意'
    service.create(path,brief='Synthetic allowed teaching mechanism',draft={'pages':[page]},project_format='workbench.v3')
    prepare_editorial_project(path)
    summary=service.continue_project(path)['pending_tasks'][0];store=Store(path)
    service.task_start(path,task_id=summary['task_id'],execution_ref='synthetic-teaching',supported_protocols=[generation.PROTOCOL],capabilities=summary['required_capabilities'])
    frozen=generation.freeze(path,task_id=summary['task_id'],input=summary['generation_input'],base_revision=store.current_revision_id(),operation_id='freeze-explicit-teaching')
    assert summary['production_request']['projection']['customer_visible']['body_blocks']==page['customer_visible']['body_blocks']
    assert page['visual_spec']['intent'] in frozen['input']['prompt']
    assert 'Preserve qualitative mechanisms or teaching illustrations only when the fixed manuscript explicitly requests them' in frozen['input']['prompt']
    assert not tasks._lookup_task(store.load_document(),summary['task_id'],store)['generation_attempts']


def test_historical_frozen_policy_prefix_is_read_without_reinterpretation(tmp_path):
    from deck_master.models import sha256_bytes
    path=tmp_path/'historical-policy'
    service.create(path,brief='Synthetic immutable historical preparation',draft={'pages':[enf._page('p1','Fixed historical copy.')]},project_format='workbench.v3')
    prepare_editorial_project(path)
    summary=service.continue_project(path)['pending_tasks'][0];store=Store(path)
    task=tasks._lookup_task(store.load_document(),summary['task_id'],store)
    preparation,old_ref=stored_blueprint_request(store,task)
    historical=copy.deepcopy(preparation)
    payload=historical['prompt'].split('Structured input:\n',1)[1]
    historical['prompt']='Synthetic historical instruction policy, retained as originally frozen.\nStructured input:\n'+payload
    historical['prompt_sha256']=sha256_bytes(historical['prompt'].encode())
    historical_ref=store.put_json_object(historical)
    original_bytes=store.read_object_bytes(historical_ref)
    historic_task={**task,'inputs':[historical_ref if ref==old_ref else ref for ref in task['inputs']]}
    read,read_ref=stored_blueprint_request(store,historic_task)
    assert read_ref==historical_ref and read['prompt']==historical['prompt']
    assert store.read_object_bytes(read_ref)==original_bytes
    assert read['resolved_design_context']==preparation['resolved_design_context']
