"""PR97 R3: real adoption transaction and pending-final recovery."""
import copy
import uuid

import pytest

from deck_master import candidates, pipeline, service, stages, tasks
from deck_master.compiler import CompileOptions, SvgInput, compile_deck
from deck_master.models import bump_revision
from deck_master.samples import create_sample
from deck_master.store import Store
from page_visual_helpers import pass_page_review
from test_deep_quality_state import svg_payload
import test_candidates as artifacts


def attach_svg(store,page='p01',width=20):
    task=artifacts.dispatch(store,page,mode='auto');artifacts.start(store,task)
    artifacts.accept(store,task,svg_payload(store,task,width))


def trial_candidate(store,page='p01',width=100):
    task=artifacts.dispatch(store,page);artifacts.start(store,task)
    return artifacts.accept(store,task,svg_payload(store,task,width))['candidate_ids'][0]


def native_output(store):
    svg=store.project_root/'native.svg';svg.write_text('<svg viewBox="0 0 100 100"><rect width="40" height="40"/></svg>')
    compiled=compile_deck([SvgInput('p01',svg)],CompileOptions(width_px=100,height_px=100),store.project_root/'native-output')
    doc=store.load_document();updated=copy.deepcopy(doc);updated['outputs']['pptx']=pipeline.artifact(store,compiled.pptx_path,'pptx')
    updated=bump_revision(updated,{'operation_id':'native-output','kind':'artifact_adoption','description':'synthetic native reference fixture','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='native-output')


@pytest.mark.render
@pytest.mark.parametrize('running',[False,True])
def test_old_final_is_retired_atomically_and_normal_continue_rebuilds(tmp_path,running):
    path=tmp_path/'project';create_sample(path,page_count=1,readonly=False);store=Store(path)
    attach_svg(store);page_review=service.continue_project(path)['pending_tasks'][0];pass_page_review(path,page_review)
    stages.assemble(path,base_revision=store.current_revision_id(),operation_id=str(uuid.uuid4()))
    old=copy.deepcopy(store.load_document());final=service.continue_project(path)['pending_tasks'][0]
    if running:service.task_start(path,task_id=final['task_id'],execution_ref='synthetic-review')
    cid=trial_candidate(store);plan=artifacts.plan(store,[cid]);operation=str(uuid.uuid4());applied=artifacts.adopt(store,plan,operation)
    doc=store.load_document();retired=tasks._lookup_task(doc,final['task_id'],store)
    assert retired['status']=='superseded'
    assert retired['call_allowances']==final['call_allowances']
    assert all(value is None for value in doc['outputs'].values())
    assert artifacts.adopt(store,plan,operation)['operation_result']==applied['operation_result']
    with pytest.raises(Exception,match='supersed|stale|late|cancellation'):
        service.accept_result(path,task_id=final['task_id'],operation_id=final['operation_id'],produced_against=final['produced_against'],result_payload={'kind':'review','reviews':[]})
    page_review=service.continue_project(path)['pending_tasks'][0];assert page_review['review_stage']=='page_visual'
    pass_page_review(path,page_review);result=service.continue_project(path);doc=store.load_document()
    assert doc['outputs']['pptx']!=old['outputs']['pptx'] and doc['pages'][0]['ppt_preview']
    assert result['next_action']=='codex_review_renderings'
    assert result['pending_tasks'][0]['task_id']!=final['task_id']
    assert service.continue_project(path)['pending_tasks'][0]['task_id']==result['pending_tasks'][0]['task_id']


@pytest.mark.parametrize('kind',['review','repair'])
def test_output_only_change_invalidates_final_before_identity_shortcut(tmp_path,kind):
    path=tmp_path/'project';create_sample(path,page_count=1,readonly=False);store=Store(path)
    native_output(store)
    final=service.open_host_task(store,kind=kind,page_ids=['p01'],instruction='synthetic final review',review_stage='final')
    doc=store.load_document();updated=copy.deepcopy(doc);updated['outputs']={key:None for key in updated['outputs']}
    assert doc['outputs']!=updated['outputs']
    assert not tasks.task_inputs_current(store,updated,final)


@pytest.mark.render
def test_historical_stale_final_recovers_without_retiring_valid_trial_or_other_page(tmp_path):
    path=tmp_path/'project';create_sample(path,page_count=2,readonly=False);store=Store(path)
    attach_svg(store,'p02');pipeline.preview_svg_page(path,'p02')
    final=service.open_host_task(store,kind='review',page_ids=['p01','p02'],instruction='historical final',review_stage='final')
    other=service.open_host_task(store,kind='review',page_ids=['p02'],instruction='other page',review_stage='page_visual')
    trial=artifacts.dispatch(store,'p02');doc=store.load_document();updated=copy.deepcopy(doc)
    # A historical writer changed p01 but failed to retire old final. Preserve
    # p02 geometry and preview so its page review is genuinely still current.
    page=store.read_object_json(updated['pages'][0]['page']);page['customer_visible']['title']+=' updated';updated['pages'][0]['page']=store.put_json_object(page)
    updated['outputs']={key:None for key in updated['outputs']}
    updated=bump_revision(updated,{'operation_id':'old-writer','kind':'content_update','description':'synthetic historical stale final','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='old-writer')
    assert tasks.task_inputs_current(store,store.load_document(),other)
    assert tasks.task_inputs_current(store,store.load_document(),trial)
    result=service.continue_project(path);after=store.load_document()
    assert tasks._lookup_task(after,final['task_id'],store)['status']=='superseded'
    assert tasks._lookup_task(after,other['task_id'],store)['status']=='awaiting_host'
    assert tasks._lookup_task(after,trial['task_id'],store)['status']=='awaiting_host'
    assert all(t['task_id']!=final['task_id'] for t in result['pending_tasks'])
    revision=after['revision_id'];service.continue_project(path);assert store.current_revision_id()==revision


def test_same_reference_adoption_keeps_valid_final_and_outputs(tmp_path):
    path=tmp_path/'project';create_sample(path,page_count=1,readonly=False);store=Store(path)
    attach_svg(store);native_output(store)
    final=service.open_host_task(store,kind='review',page_ids=['p01'],instruction='valid final',review_stage='final')
    cid=trial_candidate(store);doc=store.load_document();candidate,ref,task=candidates._lookup(candidates._records(store,doc),cid)
    # An explicitly returned immutable existing reference, rather than a new
    # Artifact object whose metadata happens to wrap identical SVG bytes.
    old_svg=doc['pages'][0]['svg'];candidate={**candidate,'result_ref':old_svg};new_ref=store.put_json_object(candidate)
    updated=copy.deepcopy(doc);updated['candidates']=[new_ref if r==ref else r for r in doc['candidates']]
    for index,r in enumerate(updated['tasks']):
        if store.read_object_json(r)['task_id']==task['task_id']:
            updated['tasks'][index]=store.put_json_object({**task,'candidate_refs':[new_ref], 'result_refs':[old_svg,new_ref]})
    updated=bump_revision(updated,{'operation_id':'existing-ref','kind':'task_update','description':'synthetic same-reference candidate','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='existing-ref')
    before=store.load_document();artifacts.adopt(store,artifacts.plan(store,[cid]));after=store.load_document()
    assert after['pages']==before['pages'] and after['outputs']==before['outputs']
    assert tasks._lookup_task(after,final['task_id'],store)['status']=='awaiting_host'


def test_batch_conflict_does_not_partially_adopt_or_retire_final(tmp_path):
    path=tmp_path/'project';create_sample(path,page_count=2,readonly=False);store=Store(path);native_output(store)
    final=service.open_host_task(store,kind='review',page_ids=['p01','p02'],instruction='final before batch',review_stage='final')
    first=trial_candidate(store,'p01');second=trial_candidate(store,'p02');plan=artifacts.plan(store,[first,second])
    attach_svg(store,'p02',width=40);before=store.read_current();doc=store.load_document()
    with pytest.raises(Exception,match='conflict|basis|base_revision'):
        artifacts.adopt(store,plan)
    assert store.read_current()==before
    assert store.load_document()['pages']==doc['pages']
    assert store.load_document()['tasks']==doc['tasks']
    assert tasks._lookup_task(doc,final['task_id'],store)['status']=='awaiting_host'
