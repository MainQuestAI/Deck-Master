"""Synthetic transaction tests; not evidence of actual Agent image analysis."""
import copy
import io
import uuid

import pytest
from PIL import Image
from test_styles import flow, dispatch, mutate  # noqa: F401
from deck_master import service, styles, tasks, visual_styles, generation
from deck_master.models import content_identity
from deck_master.operations import OperationError


def image_bytes():
    data=io.BytesIO();Image.new('RGB',(80,40),'white').save(data,format='PNG');return data.getvalue()


def imported(flow):
    op=str(uuid.uuid4());base=flow.store.current_revision_id()
    out=visual_styles.import_reference(flow.project,data=image_bytes(),base_revision=base,operation_id=op)
    return out['operation_result'],op,base


def analysis(flow, ids):
    out=visual_styles.analyze(flow.project,reference_ids=ids,instruction='分析文字层级与配色，不借用正文',base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))
    return flow.task(out['operation_result']['task_id'])


def result(refid):
    return {'kind':'style_analyze','style_analysis':{'dimensions':{key:{'summary':'Observed '+key,'evidence':[{'reference_id':refid,'region':[0,0,1,1],'observation':'Synthetic test observation','certainty':'approximate'}]} for key in visual_styles.DIMENSIONS},'palette':['#225588'],'font_suggestions':[{'family':'Arial','approximate':True,'reason':'Synthetic approximate suggestion'}],'conflicts':[],'limitations':['Synthetic fixture; not actual visual acceptance']}}


def completed(flow):
    row,_,_=imported(flow);task=analysis(flow,[row['reference_id']]);flow.start(task)
    out=tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=result(row['reference_id']))
    return out['result_refs'][0],task,row


def test_import_and_analysis_preserve_pages_outputs_and_recover_exact_receipt(flow):
    before=copy.deepcopy(flow.store.load_document());row,op,base=imported(flow)
    visual_styles.import_reference(flow.project,data=image_bytes(),base_revision=base,operation_id=op)
    task=analysis(flow,[row['reference_id']]);after=flow.store.load_document()
    assert len(after['style_references'])==1 and after['pages']==before['pages'] and after['outputs']==before['outputs']
    assert content_identity(after)==content_identity(before) and task['call_allowances']==[]
    order=service.task_summary(flow.store,after,task)['visual_analysis']
    assert order['reference_images'][0]['reference_id']==row['reference_id']
    assert after['compatibility']['minimum_writer']=='workbench-quality.v1'


@pytest.mark.parametrize('data',[b'invalid',b'',b'<svg><script/></svg>'])
def test_bad_image_never_publishes_reference(flow,data):
    before=flow.store.read_current()
    with pytest.raises(OperationError):visual_styles.import_reference(flow.project,data=data,base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))
    assert flow.store.read_current()==before


def test_analysis_result_is_bound_has_safe_breakdown_and_no_slide_scope(flow):
    ref,task,row=completed(flow);spec=flow.store.read_object_json(ref)
    assert set(spec['dimensions'])==set(visual_styles.DIMENSIONS)
    assert b'<script' not in flow.store.read_object_bytes(spec['breakdown'])
    replay=tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=result(row['reference_id']))
    assert replay['status']=='already_applied'
    recipe=styles.propose(flow.project,input={'schema_version':'style_input.v2','project_id':flow.store.load_document()['project_id'],'base_revision':flow.store.current_revision_id(),'visual_style_ref':ref,'target_page_ids':['p02','p03'],'instruction':'借用配色与文字层级'})
    confirmed=styles.confirm(flow.project,proposal_id=recipe['proposal_id'],base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    trial=dispatch(flow,confirmed)
    prepared=generation.prepared_input(flow.store,flow.store.load_document(),trial)
    assert prepared['constraints']['visual_style_ref']==ref
    assert prepared['references'][1]['file'] == visual_styles.listing(flow.project)['references'][0]['preview']['file']
    assert 'visual_reference' in trial['required_capabilities']
    assert 'Observed palette' in prepared['prompt']


def test_analysis_remains_current_after_unrelated_page_edit(flow):
    row,_,_=imported(flow);task=analysis(flow,[row['reference_id']]);mutate(flow,'p02')
    assert tasks.task_inputs_current(flow.store,flow.store.load_document(),task)


def test_analysis_rejects_out_of_reference_evidence_and_page_writes(flow):
    row,_,_=imported(flow);task=analysis(flow,[row['reference_id']]);flow.start(task)
    before=flow.store.read_current();bad=result(row['reference_id']);bad['style_analysis']['dimensions']['palette']['evidence'][0]['region']=[0.9,0,0.5,1]
    with pytest.raises(OperationError):tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=bad)
    assert flow.store.read_current()==before
    bad=result(row['reference_id']);bad['pages']=[{'page_id':'p02'}]
    with pytest.raises(OperationError):tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=bad)
    assert flow.store.read_current()==before


def test_visual_analysis_forbids_all_image_call_paths(flow):
    row,_,_=imported(flow);task=analysis(flow,[row['reference_id']]);before=flow.store.read_current()
    with pytest.raises(tasks.CallBlocked,match='zero image calls'):
        tasks.allocate_call_allowances(flow.store,task_id=task['task_id'],count=1)
    with pytest.raises(tasks.CallBlocked,match='zero image calls'):
        tasks.call_begin(flow.store,task_id=task['task_id'],allowance_id='call-1',execution_ref='test')
    assert before==flow.store.read_current()


def test_conflicting_references_require_new_single_reference_analysis(flow):
    row,_,_=imported(flow);another,_,_=imported(flow);task=analysis(flow,[row['reference_id'],another['reference_id']]);flow.start(task)
    raw=result(row['reference_id']);raw['style_analysis']['conflicts']=[{'reference_ids':[row['reference_id'],another['reference_id']], 'description':'Different typography'}]
    response=tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=raw)
    before=flow.store.read_current()
    with pytest.raises(OperationError,match='analyze it again'):
        styles.propose(flow.project,input={'schema_version':'style_input.v2','project_id':flow.store.load_document()['project_id'],'base_revision':flow.store.current_revision_id(),'visual_style_ref':response['result_refs'][0],'primary_reference_id':row['reference_id'],'target_page_ids':['p02'],'instruction':'Choose one reference'})
    assert flow.store.read_current()==before


def test_cancelled_analysis_rejects_first_and_duplicate_late_results(flow):
    row,_,_=imported(flow);task=analysis(flow,[row['reference_id']]);flow.start(task)
    service.task_cancel(flow.project,task_id=task['task_id'],reason='No longer needed')
    for _ in range(2):
        with pytest.raises(tasks.TaskConflict,match='(cancellation|cancelled output)'):
            tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=result(row['reference_id']))
    assert flow.task(task['task_id'])['result_refs']==[]


def test_edited_rules_are_authoritative_and_support_all_seven_dimensions(flow):
    ref,_,_=completed(flow)
    inp={'schema_version':'style_input.v2','project_id':flow.store.load_document()['project_id'],'base_revision':flow.store.current_revision_id(),'visual_style_ref':ref,'target_page_ids':['p02'],'instruction':'Use edited spacing','dimensions':{'spacing':'Keep 40px spacing'}}
    proposal=styles.propose(flow.project,input=inp)
    out=styles.confirm(flow.project,proposal_id=proposal['proposal_id'],base_revision=inp['base_revision'],operation_id=str(uuid.uuid4()))['operation_result']
    task=dispatch(flow,out);prompt=generation.prepared_input(flow.store,flow.store.load_document(),task)['prompt']
    assert 'Keep 40px spacing' in prompt and 'Observed spacing' not in prompt


def test_rotated_jpeg_retains_original_bytes_and_derives_orientation(flow):
    img=Image.new('RGB',(80,40),'green');exif=Image.Exif();exif[274]=6;data=io.BytesIO();img.save(data,format='JPEG',exif=exif)
    out=visual_styles.import_reference(flow.project,data=data.getvalue(),base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))
    row=visual_styles.listing(flow.project,reference_id=out['operation_result']['reference_id'])['references'][0]
    assert (row['reference']['width'],row['reference']['height'])==(40,80)
    assert flow.store.read_object_bytes(row['original']['file'])==data.getvalue()
    with Image.open(io.BytesIO(flow.store.read_object_bytes(row['preview']['file']))) as normalized:
        assert normalized.size==(40,80)


def test_palette_override_removes_conflicting_original_palette_from_execution(flow):
    ref,_,_=completed(flow)
    inp={'schema_version':'style_input.v2','project_id':flow.store.load_document()['project_id'],'base_revision':flow.store.current_revision_id(),'visual_style_ref':ref,'target_page_ids':['p02'],'instruction':'Only use green','dimensions':{'palette':'Only #00FF00'}}
    p=styles.propose(flow.project,input=inp)
    out=styles.confirm(flow.project,proposal_id=p['proposal_id'],base_revision=inp['base_revision'],operation_id=str(uuid.uuid4()))['operation_result']
    task=dispatch(flow,out);prepared=generation.prepared_input(flow.store,flow.store.load_document(),task)
    assert '参考配色' not in prepared['prompt'] and '#225588' not in prepared['prompt']
    assert prepared['constraints']['visual_style_spec']['dimensions']['palette']=='Only #00FF00'
    assert 'palette' not in prepared['constraints']['visual_style_spec']
    target=flow.store.load_document()['pages'][1]['blueprint']
    assert prepared['references'][0]['file']==flow.store.read_object_json(target)['file']


@pytest.mark.parametrize('format',['PNG','WEBP'])
def test_transparent_references_preserve_alpha_in_derived_generation_input(flow,format):
    image=Image.new('RGBA',(80,40),(0,0,0,0));image.putpixel((10,10),(255,0,0,255));raw=io.BytesIO();image.save(raw,format=format,lossless=True)
    row=visual_styles.import_reference(flow.project,data=raw.getvalue(),base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))['operation_result']
    record=visual_styles.listing(flow.project,reference_id=row['reference_id'])['references'][0]
    with Image.open(io.BytesIO(flow.store.read_object_bytes(record['preview']['file']))) as preview:
        assert preview.mode=='RGBA' and preview.getpixel((0,0))[3]==0
        assert preview.getpixel((10,10))==(255,0,0,255)
    assert flow.store.read_object_bytes(record['original']['file'])==raw.getvalue()
