"""F6: actual Plan consumption, immutable requests and synthetic L1 native facts."""
import copy
import uuid

import pytest

from deck_master import content_plan, generation, models, tasks
from deck_master.design_requirements import plan_global_projection
from deck_master.native_image_evidence import NativeImageRuntime
import test_rc3_native_visual_reuse as helper


def _policy_edit(store, policy):
    doc=store.load_document();plan=store.read_object_json(doc['content_plan'])
    value=copy.deepcopy(plan['input']);value['speech_policy']=policy
    updated=copy.deepcopy(doc)
    updated['content_plan']=content_plan.build_v2_plan(store,doc,
        {'task_id':None,'dispatch_revision':doc['revision_id']},value,doc['pages'],narrative_ref=None,
        mode='imported_mapping',imported_manuscript=plan['imported_manuscript'])
    operation=str(uuid.uuid4())
    updated=models.bump_revision(updated,{'operation_id':operation,'kind':'content_update','description':'Synthetic actual Plan policy edit','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id=operation)
    return plan,store.read_object_json(updated['content_plan'])


@pytest.mark.parametrize('when',['before_context','after_context'])
def test_absent_speech_origin_retains_current_visual_native_candidate(when,tmp_path):
    path,store,_,task,sent=helper._begun(tmp_path)
    frozen,attempt,_,registry=sent
    original_request=generation.show(path,request_id=frozen['request_id'])['request']
    old_plan_ref=store.load_document()['content_plan']
    with NativeImageRuntime(registry).bound():
        context=helper._issue(store,task,sent) if when=='after_context' else None
        before,after=_policy_edit(store,{'mode':'none','output':'none','source':'provided'})
        assert before['input']['speech_policy']['source']=='default'
        assert after['input']['speech_policy']['source']=='provided'
        assert plan_global_projection(before)==plan_global_projection(after)
        assert store.load_document()['content_plan']!=old_plan_ref
        assert original_request['input']['design_context']['content_basis']['plan_ref']==old_plan_ref
        assert tasks.task_inputs_current(store,store.load_document(),task) is True
        if context is None:context=helper._issue(store,task,sent)
        settled=helper._settle(store,task,sent,context)
    assert settled['native_observation_status']=='accepted'
    assert generation.show(path,request_id=frozen['request_id'])['request']==original_request
    result=helper.accept(path,store,task,sent)
    assert result['status']=='candidate_ready'
    assert generation.show(path,attempt_id=attempt['attempt_id'])['call']['state']=='consumed'


def test_real_speech_product_requirement_still_invalidates_visual_basis(tmp_path):
    path,store,_,task,sent=helper._begun(tmp_path)
    frozen,attempt,_,registry=sent
    with NativeImageRuntime(registry).bound():
        context=helper._issue(store,task,sent)
        before,after=_policy_edit(store,{'mode':'cues','output':'pptx_notes','source':'provided'})
        assert plan_global_projection(before)!=plan_global_projection(after)
        assert after['input']['speech_policy']=={'mode':'cues','output':'pptx_notes','source':'provided'}
        assert tasks.task_inputs_current(store,store.load_document(),task) is False
        settled=helper._settle(store,task,sent,context)
    assert settled['native_observation_status']=='rejected'
    assert generation.show(path,attempt_id=attempt['attempt_id'])['call']['state']=='consumed'
    assert generation.show(path,request_id=frozen['request_id'])['request']['input']==frozen['input']


def test_active_speech_origin_retains_its_actual_policy_dependency(tmp_path):
    _,store,_,_,_=helper._begun(tmp_path)
    _policy_edit(store,{'mode':'cues','output':'pptx_notes','source':'default'})
    before,after=_policy_edit(store,{'mode':'cues','output':'pptx_notes','source':'provided'})
    assert plan_global_projection(before)!=plan_global_projection(after)
    assert before['input']['speech_policy']['source']=='default'
    assert after['input']['speech_policy']['source']=='provided'
