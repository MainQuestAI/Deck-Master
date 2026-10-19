"""RC3 formal SDK workflows using explicitly synthetic L1 instruction/tool evidence."""
import copy
import uuid

import pytest

from deck_master import changes, generation, service, styles, tasks
from deck_master.models import canonical_json_bytes, require_writer, validate_schema
from deck_master.native_image_evidence import NativeImageRegistry, NativeImageRuntime, image_binding
from deck_master.store import Store
from test_rc3_design_recipes import input_value
from test_rc3_native_image_bridge import SyntheticController
from test_rc3_notes_visual_inputs import enf, _seed_imported_plan


def project(tmp_path):
    path,store = enf._project(tmp_path)
    _seed_imported_plan(store)
    enf._start(path,store)
    enf._settle_preproduction(store,seed='rc3-design-workflow-l1')
    grant = enf._grant(path,store,actions=('style.propose','design.update','change.commit','task.start','call.begin','result.accept','candidate.adopt','allowance.allocate'),max_external_calls=2,max_candidate_count=2)
    return path,store,grant


def confirmed(path,store,**updates):
    value = input_value(store.load_document()); value.update(updates)
    proposed = styles.propose(path,input=value)
    assert proposed['model_calls'] == 0
    validate_schema('style_proposal', proposed['proposal'])
    result = styles.confirm(path,proposal_id=proposed['proposal_id'],base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    return result


def dispatch(path,store,recipe,ids):
    plan = styles.plan(path,input={'recipe_id':recipe['recipe_id'],'page_ids':ids,'max_calls':len(ids)})
    result=changes.commit(path,plan_id=plan['plan_id'],base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    return [tasks._lookup_task(store.load_document(),tid,store) for tid in result['task_ids']]


def synthetic_candidate(path,store,task):
    service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-design-native-l1',supported_protocols=[generation.PROTOCOL],capabilities=task['required_capabilities'])
    value=generation.prepared_input(store,store.load_document(),task)
    frozen=generation.freeze(path,task_id=task['task_id'],input=value,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    attempt=tasks.call_begin(store,task_id=task['task_id'],allowance_id=task['call_allowances'][0]['allowance_id'],execution_ref='synthetic-design-native-l1',request_id=frozen['request_id'])
    binding,_,actual,_=image_binding(store,store.load_document(),task['task_id'],attempt['attempt_id'])
    controller=SyntheticController(binding,actual); controller.claims['event_id']=task['task_id']
    registry=NativeImageRegistry(); registry.register(controller)
    with NativeImageRuntime(registry).bound():
        context=registry.image_context(store,store.load_document(),task_id=task['task_id'],attempt_id=attempt['attempt_id'],selector={'provider_id':controller.provider_id,'event_id':task['task_id']})
        settled=tasks.call_settle(store,task_id=task['task_id'],allowance_id=attempt['allowance_id'],attempt_id=attempt['attempt_id'],outcome='consumed',report_bytes=canonical_json_bytes({'source':'native_host_image.v1','provider_id':controller.provider_id,'event_id':task['task_id']}),adapter_context=context)
    assert settled['native_observation_status']=='accepted'
    stage=store.staging_dir/task['operation_id']; stage.mkdir(exist_ok=True); (stage/'result.png').write_bytes(controller.png)
    payload={'kind':'blueprint','files':[{'file_id':'output','path':'result.png','media_type':'image/png'}],
        'generation_result':{'request_id':frozen['request_id'],'attempt_id':attempt['attempt_id']},
        'artifact_specs':[{'role':'blueprint','page_id':task['scope_pages'][0],'file_id':'output','provenance':{'source_type':'host_generated','tool':'image_gen'}}]}
    result=service.accept_result(path,result_payload=payload,**{k:task[k] for k in ('task_id','operation_id','produced_against')})
    return result['candidate_ids'][0],frozen


def test_authorized_first_two_initial_pages_reverse_arrival_remain_candidates(tmp_path):
    path,store,_=project(tmp_path)
    original=copy.deepcopy(store.load_document()['pages'])
    recipe=confirmed(path,store)
    assert store.load_document()['compatibility']['minimum_writer']=='rc4-content.v1'
    pair=dispatch(path,store,recipe,['p1','p2'])
    assert all(task['stage_request']['references']==[] for task in pair)
    assert all(task['collaboration_binding']['adoption_policy']=='candidate_only' for task in pair)
    ids=[]
    for task in reversed(pair):
        cid,frozen=synthetic_candidate(path,store,task); ids.append(cid)
        resolved=frozen['input']['design_context']
        assert resolved['content_requirements']['page_id']==task['scope_pages'][0]
        assert resolved['content_basis']['recipe_ref']==recipe['recipe_ref']
        assert resolved['recipe_parameters']==frozen['input']['constraints']['recipe_parameters']
        assert 'content_requirements' in frozen['input']['prompt']
        assert 'recipe_parameters' in frozen['input']['prompt']
        assert store.load_document()['pages']==original
    assert len(set(ids))==2
    assert not store.load_document().get('candidate_adoptions')
    all_tasks=[store.read_object_json(ref) for ref in store.load_document()['tasks']]
    assert sum(c['state']=='consumed' for task in all_tasks for c in task.get('call_allowances',[]))==2


def test_new_auto_preparation_cannot_freeze_an_unrelated_prompt(tmp_path):
    path=tmp_path/'auto'
    service.create(path,brief='Synthetic auto freeze',draft={'pages':[enf._page('p1','Known 54 units.')]},project_format='workbench.v3')
    from test_content_ops import prepare_editorial_project
    prepare_editorial_project(path)
    summary=service.continue_project(path)['pending_tasks'][0]
    store=Store(path)
    service.task_start(path,task_id=summary['task_id'],execution_ref='synthetic-auto',supported_protocols=[generation.PROTOCOL],capabilities=summary['required_capabilities'])
    value=copy.deepcopy(summary['generation_input']);value['prompt']='invented hidden blueprint request'
    before=store.current_revision_id()
    with pytest.raises(generation.GenerationError,match='committed stage request'):
        generation.freeze(path,task_id=summary['task_id'],input=value,base_revision=before,operation_id='bad-auto')
    assert store.current_revision_id()==before
    assert summary['generation_input']['parameters']=={'transparent_background':False}
