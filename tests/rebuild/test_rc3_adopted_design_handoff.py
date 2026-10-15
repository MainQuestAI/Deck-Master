"""F7 adopted-image handoff through real SDK over explicit synthetic L1 data.

Artificial PNG/controller observations exercise formal candidate/adopt/Host
transactions, never image generation, independent review or visual quality.
Fault injection creates fresh objects only in these disposable test projects.
"""
import copy
from html import escape
import uuid

import pytest

from deck_master import candidates, changes, editing, generation, models, pipeline, service, tasks
from deck_master.content import visible_atoms
from deck_master.production import (adopted_blueprint_design, consumed_design, resolve_design,
    resolve_page_design, resolve_page_rendering_design, style_font_fingerprint)
import test_rc3_native_visual_reuse as reuse
from test_rc3_plan_visual_consumption import _policy_edit
from test_rc3_restyle_workflows import adopted_initial, edit
from test_rc3_design_workflows import confirmed


def _commit(store, document, description):
    before = store.load_document()
    operation = str(uuid.uuid4())
    document = models.bump_revision(document, {'operation_id': operation, 'kind': 'content_update',
        'description': description, 'read_set': []})
    store.commit_change(base_revision=before['revision_id'], document=document, operation_id=operation)
    return store.load_document()


def _adopted(tmp_path):
    path, store, grant = reuse._project(tmp_path)
    blueprint, sent = adopted_initial(path, store)
    doc = store.load_document()
    entry = doc['pages'][0]
    artifact = store.read_object_json(blueprint)
    request = store.read_object_json(artifact['provenance']['generation_request'])
    author = tasks._lookup_task(doc, request['task_id'], store)
    assert author['status'] == 'completed' and entry['blueprint'] == blueprint
    return path, store, grant, sent, author


def _open(store, *, kind='reconstruct', review_stage=None, instruction='Synthetic F7 reconstruct exact adopted image'):
    return service.open_host_task(store, kind=kind, page_ids=['p1'], instruction=instruction,
        base_revision=store.current_revision_id(), review_stage=review_stage)


def _style_digest(effective):
    style = effective['styles'][0]
    assets = {item['asset_id']: item for item in effective['assets']}
    font_fp = style_font_fingerprint(effective, style,
        lambda aid: (assets.get(aid) or {}).get('artifact', {}).get('sha256'))
    return models.sha256_bytes(models.canonical_json_bytes({'style': style, 'fonts': font_fp,
        **({'recipe_parameters': effective['recipe_parameters']} if 'recipe_parameters' in effective else {})}))


def _visual_inputs(store, sent):
    doc=store.load_document()
    for role,media,blob,ext in [('svg','image/svg+xml',b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900"/>','svg'),
            ('svg_preview','image/png',sent[2].png,'png')]:
        artifact={'schema_version':'deck_artifact.v1','artifact_id':'synthetic-f7-'+role,'page_id':'p1',
            'role':role,'file':store.put_blob(blob,ext=ext),'media_type':media,
            'created_at':'2026-10-15T00:00:00Z','dependencies':[],'derived_from':[],
            'provenance':{'source_type':'unknown'},'limitations':['Synthetic L1 dependency inputs; no render or fidelity verdict']}
        models.validate_artifact_semantics(artifact)
        doc['pages'][0][role]=store.put_json_object(artifact)
    _commit(store,doc,'Synthetic L1 SVG/preview dependency inputs only')


def _svg_payload(store, task):
    doc=store.load_document();entry=doc['pages'][0];page=store.read_object_json(entry['page'])
    stage=store.staging_dir/task['operation_id'];stage.mkdir(exist_ok=True)
    # Text-only protocol diagnostic, deliberately no visual-fidelity verdict.
    text=''.join(f'<text x="20" y="{30+i*18}" font-family="Arial">{escape(atom["text"])}</text>'
                 for i,atom in enumerate(visible_atoms(page)))
    (stage/'sample.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">{text}</svg>')
    return {'kind':task['kind'],'files':[{'file_id':'svg','path':'sample.svg','media_type':'image/svg+xml'}],
        'artifact_specs':[{'role':'svg','page_id':'p1','file_id':'svg',
                          'provenance':{'source_type':'host_generated','tool':'synthetic-svg-writer'}}]}


def _review_payload(store, task):
    requirement=service.task_summary(store,store.load_document(),task)['page_visual_requirements'][0]
    evidence=store.put_json_object({'synthetic':'L1 host_self contract diagnostic only, no model or human review'})
    reviews=[]
    for kind in requirement['review_kinds']:
        record={'schema_version':'deck_review.v2','review_id':'synthetic-f8-'+kind,'kind':kind,
            'review_stage':'page_visual','status':'pass','subjects':requirement['subject_refs'],
            'dependencies':requirement['dependencies'],'reviewer':{'type':'host_self','id':'synthetic-f8-self',
                'execution_ref':'synthetic-f8-consumer','independence_confirmed':False,'identity_receipt':None,
                'evidence_ref':evidence,'assurance':'host_attested'},
            'observations':['Explicit synthetic self-review protocol diagnostic; no visual-quality or independent acceptance.'],
            'findings':[],'created_at':'2026-10-15T00:00:00Z','replaces':None}
        models.validate_review_semantics(record);reviews.append(record)
    return {'kind':'review','reviews':reviews}


@pytest.mark.parametrize('kind,stage', [('reconstruct',None),('repair',None),('review','page_visual')])
def test_formal_adoption_hands_full_immutable_context_to_every_visual_consumer(tmp_path, kind, stage):
    _,store,_,sent,author = _adopted(tmp_path)
    frozen = sent[0]
    original = store.read_object_bytes(frozen['request_ref'])
    if stage == 'page_visual':
        _visual_inputs(store,sent)
    task = _open(store, kind=kind, review_stage=stage)
    doc = store.load_document()
    summary = service.task_summary(store, doc, task)
    context = summary['page_design_contexts']['p1']
    assert context == frozen['input']['design_context']
    assert {'content_requirements','content_basis','recipe_parameters','recipe_overrides'} <= context.keys()
    assert context['styles'][0]['layout_notes'] != doc['design_context']['styles'][0]['layout_notes']
    assert task['protocol_version'] == 'changes.v1'
    assert set(task['required_capabilities']) == {'content_requirements_v1','style_recipe','style_recipe_v3','collaboration.v1','rc3-entry.v1'}
    assert 'change_binding' not in task and 'change_plan' not in task['required_capabilities']
    assert doc['compatibility']['minimum_writer'] == 'rc3-entry.v1'
    assert tasks.task_inputs_current(store, doc, task)
    digests = editing._current_artifact_digests(store, doc)
    assert digests['style:p1'] == _style_digest(context)
    legacy,_ = resolve_design(store.read_object_json(doc['pages'][0]['page']),doc['design_context'],[])
    assert digests['style:p1'] != _style_digest(legacy)
    if stage == 'page_visual':
        dependencies = summary['page_visual_requirements'][0]['dependencies']
        assert next(dep['sha256'] for dep in dependencies if dep['kind']=='style') == _style_digest(context)
    assert store.read_object_bytes(frozen['request_ref']) == original
    assert tasks._lookup_task(doc,author['task_id'],store)['generation_attempts'] == author['generation_attempts']


@pytest.mark.parametrize('missing', ['content_requirements_v1','style_recipe','style_recipe_v3'])
def test_new_consumer_requires_explicit_capabilities_before_claim(tmp_path, missing):
    path,store,_,_,_ = _adopted(tmp_path)
    task = _open(store)
    before = store.load_document()
    with pytest.raises(generation.GenerationError, match='requires changes.v1'):
        service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-svg-writer',
            supported_protocols=['changes.v1'],capabilities=[cap for cap in task['required_capabilities'] if cap!=missing])
    assert store.load_document() == before
    service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-svg-writer',
        supported_protocols=['changes.v1'],capabilities=task['required_capabilities'])


@pytest.mark.parametrize('change',['notes','p2_design','p2_body','none_speech_source','unused_font','overridden_default_layout','new_sibling_recipe'])
def test_unconsumed_changes_preserve_frozen_writer_context_and_svg_basis(tmp_path, change):
    path,store,_,sent,_ = _adopted(tmp_path)
    task = _open(store)
    original = copy.deepcopy(store.load_document())
    entry = original['pages'][0]
    before_basis = candidates.generation_basis(store,original,'p1','svg',task=task)
    before_style = editing._current_artifact_digests(store,original)['style:p1']
    if change == 'notes':
        edit(path,store,'p1',lambda page: page.update(speaker_notes='仅讲述变化；视觉主链与业务责任保持原样。'))
    elif change == 'p2_design':
        edit(path,store,'p2',lambda page: page['visual_spec'].update(layout_hint='P2上下排列'))
    elif change == 'p2_body':
        edit(path,store,'p2',lambda page: page['customer_visible'].update(title='P2独立正文变化'))
    elif change == 'none_speech_source':
        _policy_edit(store,{'mode':'none','output':'none','source':'provided'})
    elif change == 'new_sibling_recipe':
        confirmed(path,store,instruction='未派生产的新独立方案不能替换已采用的固定recipe')
    else:
        design = copy.deepcopy(store.load_document()['design_context'])
        if change == 'unused_font':
            design['fonts'].append({'font_id':'unused','family':'Unused Face','face':'Regular','weight':400,
                                   'fallback_font_ids':[],'asset_id':None})
        else:
            design['styles'][0]['layout_notes']='被已采用v3完整composition/spacing等规则覆盖的default文案'
        service.update_design(path,design_context=design,base_revision=store.current_revision_id())
    doc = store.load_document()
    assert tasks.task_inputs_current(store,doc,tasks._lookup_task(doc,task['task_id'],store))
    assert service.task_summary(store,doc,task)['page_design_contexts']['p1'] == sent[0]['input']['design_context']
    assert editing._current_artifact_digests(store,doc)['style:p1'] == before_style
    after_basis = candidates.generation_basis(store,doc,'p1','svg',task=task)
    assert after_basis['design_digest'] == before_basis['design_digest']
    assert after_basis['blueprint_ref'] == entry['blueprint']
    assert store.read_object_bytes(sent[0]['request_ref']) == models.canonical_json_bytes(store.read_object_json(sent[0]['request_ref']))


@pytest.mark.parametrize('change',['body','role','arrow','used_font','target'])
def test_relevant_changes_refuse_new_writer_and_late_consumption(tmp_path, change):
    path,store,grant,sent,author = _adopted(tmp_path)
    task = _open(store)
    original_request = store.read_object_bytes(sent[0]['request_ref'])
    if change == 'used_font':
        design=copy.deepcopy(store.load_document()['design_context'])
        design['fonts'][0]['family']='Changed Actual Used Face'
        service.update_design(path,design_context=design,base_revision=store.current_revision_id())
    else:
        reuse._semantic_or_control_change(path,store,grant,change)
    doc=store.load_document()
    assert not tasks.task_inputs_current(store,doc,tasks._lookup_task(doc,task['task_id'],store))
    if change != 'target':
        with pytest.raises(models.ModelError,match='consumed Page/Plan/design'):
            resolve_page_design(store,doc,doc['pages'][0],require_current=True)
    else:
        with pytest.raises(service.ServiceError,match='outside.*consumer Task inputs'):
            service.task_summary(store,doc,task)
    closed=tasks._lookup_task(doc,author['task_id'],store)
    assert closed['call_allowances'][0]['state']=='consumed'
    assert store.read_object_bytes(sent[0]['request_ref'])==original_request


def test_closed_actual_execution_is_not_reauthenticated_by_a_new_reader(tmp_path, monkeypatch):
    _,store,_,sent,_ = _adopted(tmp_path)
    from deck_master import native_image_evidence
    def forbidden():
        raise AssertionError('a closed historical execution must not be checked against a new reader installation')
    monkeypatch.setattr(native_image_evidence,'execution_installation_identity',forbidden)
    assert resolve_page_design(store,store.load_document(),store.load_document()['pages'][0],require_current=True)==sent[0]['input']['design_context']


@pytest.mark.parametrize('fault',['missing_request','foreign_project','bad_hash','not_owned','missing_context'])
def test_modern_corrupt_lineage_never_silently_falls_back_to_default(tmp_path, fault):
    _,store,_,sent,author = _adopted(tmp_path)
    doc=store.load_document();artifact=store.read_object_json(doc['pages'][0]['blueprint'])
    request=store.read_object_json(artifact['provenance']['generation_request'])
    if fault=='missing_request':
        artifact['provenance'].pop('generation_request')
    else:
        if fault=='foreign_project':request['project_id']='foreign-project'
        elif fault=='bad_hash':request['input_hash']='0'*64
        elif fault=='not_owned':request['task_id']='another-task'
        else:
            request['input']['design_context'].pop('content_requirements')
            request['input']['design_context'].pop('content_basis')
            request['input_hash']=models.sha256_bytes(models.canonical_json_bytes(request['input']))
        artifact['provenance']['generation_request']=store.put_json_object(request)
    doc['pages'][0]['blueprint']=store.put_json_object(artifact)
    _commit(store,doc,'Synthetic explicit broken modern provenance fault')
    before=store.load_document()
    with pytest.raises(models.ModelError):
        resolve_page_design(store,before,before['pages'][0])
    assert store.load_document()==before
    assert generation.show(store.project_root,attempt_id=sent[1]['attempt_id'])['call']['state']=='consumed'
    assert tasks._lookup_task(before,author['task_id'],store)['generation_requests']==author['generation_requests']


def test_formal_changes_svg_handoff_also_declares_adopted_recipe_capabilities(tmp_path):
    path,store,_,_,_ = _adopted(tmp_path)
    doc=store.load_document();entry=doc['pages'][0]
    value={'schema_version':'change_intent.v1','project_id':doc['project_id'],'base_revision':doc['revision_id'],
        'intent':'svg','instruction':'Synthetic reconstruct same adopted image', 'annotation_refs':[], 'max_calls':0,'targets':[{
        'page_id':'p1','page_ref':entry['page'],'layer':'svg','artifact_ref':None}]}
    plan=changes.plan(path,input=value)
    result=changes.commit(path,plan_id=plan['plan_id'],base_revision=doc['revision_id'],operation_id=str(uuid.uuid4()))
    task=tasks._lookup_task(store.load_document(),result['operation_result']['task_ids'][0],store)
    assert {'change_plan','content_requirements_v1','style_recipe','style_recipe_v3'}<=set(task['required_capabilities'])
    assert service.task_summary(store,store.load_document(),task)['page_design_contexts']['p1']['recipe_parameters']


def test_svg_accept_and_asset_materialization_share_the_adopted_design(tmp_path):
    path,store,_,sent,_ = _adopted(tmp_path)
    task=_open(store)
    service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-svg-writer',
        supported_protocols=['changes.v1'],capabilities=task['required_capabilities'])
    doc=store.load_document();entry=doc['pages'][0]
    payload=_svg_payload(store,task)
    stage=store.staging_dir/task['operation_id']
    assert pipeline.page_asset_paths(store,doc,entry,stage)=={}
    result=service.accept_result(path,**{key:task[key] for key in ('task_id','operation_id','produced_against')},
        result_payload=payload)
    assert result['status']=='accepted'
    doc=store.load_document()
    assert doc['pages'][0]['svg'] and doc['pages'][0]['blueprint']==entry['blueprint']
    assert resolve_page_design(store,doc,doc['pages'][0],require_current=True)==sent[0]['input']['design_context']
    assert _style_digest(resolve_page_rendering_design(store,doc,doc['pages'][0]))==editing._current_artifact_digests(store,doc)['style:p1']


def test_historical_no_cap_queue_reads_original_context_but_rejects_target_downgrade(tmp_path):
    path,store,grant,sent,_ = _adopted(tmp_path)
    task=_open(store)
    # Explicit L1 historical 805 queue shape; do not rewrite an actual old Task.
    task.pop('protocol_version');task.pop('required_capabilities')
    doc=store.load_document()
    doc=tasks._replace_task_ref(doc,task,store.put_json_object(task),store)
    _commit(store,doc,'Synthetic historical no-cap consumer queue record')
    before=store.load_document()
    assert service.task_summary(store,before,task)['page_design_contexts']['p1']==sent[0]['input']['design_context']
    assert tasks.task_inputs_current(store,before,task)
    reuse._semantic_or_control_change(path,store,grant,'target')
    after=store.load_document()
    assert not tasks.task_inputs_current(store,after,task)
    with pytest.raises(service.ServiceError,match='outside.*consumer Task inputs'):
        service.task_summary(store,after,task)


def test_legacy_generation_shape_without_requirements_remains_legacy_at_rc3_floor(tmp_path):
    _,store,_,sent,author = _adopted(tmp_path)
    doc=store.load_document();entry=doc['pages'][0]
    page=store.read_object_json(entry['page'])
    legacy,_=resolve_design(page,doc['design_context'],doc['design_context']['assets'])
    from deck_master.production import project_prompt
    preparation=project_prompt(page,legacy,legacy['assets'])
    assert 'resolved_design_context' not in preparation
    # Explicit historical-shape L1 seed: no native proof, actual historical
    # image call, review assurance or migration authorization is asserted.
    owner=copy.deepcopy(author)
    owner.update(task_id='synthetic-pre03-image',operation_id='synthetic-pre03-image-operation',
        inputs=[entry['page'],store.put_json_object(preparation)],
        required_capabilities=['generation_request_freeze','attempt_binding','native_tool_observation'])
    for key in ('stage_request','change_binding','candidate_refs'):
        owner.pop(key,None)
    frozen=copy.deepcopy(store.read_object_json(sent[0]['request_ref']))
    frozen.update(request_id='synthetic-pre03-request',task_id=owner['task_id'],
                  input=generation.prepared_input(store,doc,owner))
    frozen['input_hash']=models.sha256_bytes(models.canonical_json_bytes(frozen['input']))
    models.validate_schema('generation_request',frozen)
    request_ref=store.put_json_object(frozen)
    attempt=copy.deepcopy(store.read_object_json(author['generation_attempts'][0]))
    attempt.update(attempt_id='synthetic-pre03-attempt',task_id=owner['task_id'],
                   request_ref=request_ref,previous_ref=None,observations=[])
    models.validate_schema('generation_attempt',attempt)
    attempt_ref=store.put_json_object(attempt)
    artifact=copy.deepcopy(store.read_object_json(entry['blueprint']))
    artifact.update(artifact_id='synthetic-pre03-image-artifact',provenance={
        'source_type':'unknown','generation_request':request_ref,'generation_attempt':attempt_ref,
        'generated_from_page':entry['page']},limitations=['Synthetic historical contract seed; not native evidence'])
    artifact_ref=store.put_json_object(artifact)
    owner.update(generation_requests=[request_ref],generation_attempts=[attempt_ref],result_refs=[artifact_ref])
    models.validate_task_semantics(owner)
    doc['tasks'].append(store.put_json_object(owner));doc['pages'][0]['blueprint']=artifact_ref
    _commit(store,doc,'Synthetic original pre03 generation contract, no new requirements')
    doc=store.load_document()
    assert adopted_blueprint_design(store,doc,doc['pages'][0]) is None
    assert resolve_page_design(store,doc,doc['pages'][0],require_current=True)==legacy
    task=_open(store,instruction='Synthetic legacy reconstruct keeps original contract')
    assert task['protocol_version'] == 'changes.v1'
    assert {'rc3-entry.v1', 'collaboration.v1'} <= set(task['required_capabilities'])
    assert 'content_requirements_v1' not in task['required_capabilities']
    assert service.task_summary(store,store.load_document(),task)['page_design_contexts']['p1']==legacy
    assert store.load_document()['compatibility']['minimum_writer']=='rc3-entry.v1'
    proposed=copy.deepcopy(page);proposed['customer_visible']['title']='Explicit legacy combined Page/SVG repair'
    assert pipeline.page_asset_paths(store,store.load_document(),store.load_document()['pages'][0],tmp_path,page=proposed)=={}


def test_content_requalification_can_review_changed_page_before_new_visual_production(tmp_path):
    path,store,_,_,_ = _adopted(tmp_path)
    edit(path,store,'p1',lambda page: page['customer_visible'].update(title='已采用图片后的真实业务正文修订'))
    from deck_master import content_review
    outcome=content_review.dispatch_preproduction_review(path)
    assert outcome['status']=='review_dispatched'
    task=outcome['task']
    assert task['review_stage']=='preproduction'
    assert 'content_requirements_v1' not in task.get('required_capabilities',[])
    # Content review consumes the current manuscript, not the stale adopted
    # image's design. Requalification must precede the next image generation.
    summary=service.task_summary(store,store.load_document(),task)
    assert 'content_requirements' not in summary['page_design_contexts']['p1']


@pytest.mark.parametrize('kind,stage',[('reconstruct',None),('repair',None),('review','page_visual')])
@pytest.mark.parametrize('fault',['no_claim','missing_cap','missing_execution'])
def test_direct_new_consumers_reject_first_adoption_without_actual_claim_and_caps(tmp_path,kind,stage,fault):
    path,store,_,sent,author=_adopted(tmp_path)
    if stage=='page_visual':_visual_inputs(store,sent)
    task=_open(store,kind=kind,review_stage=stage)
    assert not task.get('change_binding') and task['protocol_version']=='changes.v1'
    payload=_review_payload(store,task) if kind=='review' else _svg_payload(store,task)
    if fault!='no_claim':
        service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-f8-consumer',
            supported_protocols=['changes.v1'],capabilities=task['required_capabilities'])
        current=tasks._lookup_task(store.load_document(),task['task_id'],store)
        if fault=='missing_cap':current['host_protocol']['capabilities'].remove('content_requirements_v1')
        else:current['execution_ref']=None
        document=tasks._replace_task_ref(store.load_document(),current,store.put_json_object(current),store)
        _commit(store,document,'Synthetic L1 damaged saved Host claim; not a public authority bypass')
    before=store.load_document()
    error=generation.GenerationError if fault=='missing_cap' else tasks.TaskConflict
    with pytest.raises(error):
        service.accept_result(path,**{key:task[key] for key in ('task_id','operation_id','produced_against')},
                              result_payload=payload)
    assert store.load_document()==before
    assert tasks._lookup_task(before,author['task_id'],store)['call_allowances'][0]['state']=='consumed'
    assert generation.show(path,attempt_id=sent[1]['attempt_id'])['call']['state']=='consumed'


@pytest.mark.parametrize('kind,stage',[('reconstruct',None),('repair',None),('review','page_visual')])
def test_direct_new_consumers_full_claim_accept_then_exact_terminal_replay_without_new_write(tmp_path,kind,stage):
    path,store,_,sent,author=_adopted(tmp_path)
    if stage=='page_visual':_visual_inputs(store,sent)
    task=_open(store,kind=kind,review_stage=stage)
    payload=_review_payload(store,task) if kind=='review' else _svg_payload(store,task)
    service.task_start(path,task_id=task['task_id'],execution_ref='synthetic-f8-consumer',
        supported_protocols=['changes.v1'],capabilities=task['required_capabilities'])
    binding={key:task[key] for key in ('task_id','operation_id','produced_against')}
    accepted=service.accept_result(path,**binding,result_payload=payload)
    assert accepted['status']=='accepted'
    closed=tasks._lookup_task(store.load_document(),task['task_id'],store)
    assert closed['status']=='completed'
    # A terminal replay recovers the exact committed operation. It does not
    # become a second adoption or require a new claim on the completed Task.
    closed['host_protocol']['capabilities'].remove('content_requirements_v1')
    document=tasks._replace_task_ref(store.load_document(),closed,store.put_json_object(closed),store)
    _commit(store,document,'Synthetic terminal-declaration fault to prove original receipt recovery order')
    before=store.load_document()
    replay=service.accept_result(path,**binding,result_payload=payload)
    assert replay['status']=='already_applied' and replay['operation_result']['status']=='accepted'
    assert store.load_document()==before
    assert tasks._lookup_task(before,author['task_id'],store)['call_allowances'][0]['state']=='consumed'
    assert generation.show(path,attempt_id=sent[1]['attempt_id'])['call']['state']=='consumed'
