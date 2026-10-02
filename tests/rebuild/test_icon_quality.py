"""Icon scope/transaction regression; synthetic mechanism evidence only."""
import copy
import json
import uuid
import xml.etree.ElementTree as ET
import pytest
from deck_master import icons, changes, candidates, service, tasks, candidate_preview
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from deck_master.samples import create_sample
from deck_master.store import Store

SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><defs><g id="symbol"><path d="M0 0L8 0L8 8"/></g></defs><text x="10" y="30" font-family="Arial" font-size="20">Keep this text</text><g transform="translate(100 100)"><g stroke="#1478ff" fill="none"><path id="duplicate" d="M0 0L30 30"/><path id="duplicate" d="M30 0L0 30"/></g><use href="#symbol" x="60" y="10"/></g></svg>'''

@pytest.fixture
def icon_store(tmp_path):
    project=tmp_path/'icons';create_sample(project,page_count=3,readonly=False);store=Store(project)
    doc=store.load_document();new=copy.deepcopy(doc)
    for entry in new['pages']:
        original=store.read_object_json(entry['blueprint'])['file']['sha256']
        from hostenv import resolve_host_font
        root=icons.tree(SVG);root[1].set('font-family',resolve_host_font());root[1].text=store.read_object_json(entry['page'])['customer_visible']['title']+' Keep this text';root.set('data-blueprint-sha256',original)
        artifact=store.read_object_json(entry['blueprint']);artifact['role']='svg';artifact['media_type']='image/svg+xml';artifact['file']=store.put_blob(ET.tostring(root),ext='svg');entry['svg']=store.put_json_object(artifact)
    new=bump_revision(new,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'synthetic icons','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=new,operation_id=new['change']['operation_id']);return store


def input_for(store,pid='p01',method='redraw'):
    info=icons.inspect(store.project_root,page_id=pid)
    source=next(o for o in info['objects'] if o['path']=='2/0')
    return {'schema_version':'icon_input.v1','project_id':info['project_id'],'base_revision':info['revision_id'],'instruction':'精修图标，保留其它对象。','annotation_refs':[],
            'targets':[{k:info[k] for k in ('page_id','page_ref','svg_ref','blueprint_ref')} | {'icons':[{'label':'交叉','semantic_key':'cross','original_region':{'x':.1,'y':.1,'width':.1,'height':.1},'svg_region':{'x':.1,'y':.18,'width':.04,'height':.08},'objects':[{k:source[k] for k in ('path','sha256')}], 'method':method,'asset_id':'workflow','style':{'color':'#1478ff','stroke_width':2}}]}]}


def confirm(store,value=None):
    value=value or input_for(store);p=icons.propose(store.project_root,input=value)
    result=icons.confirm(store.project_root,proposal_id=p['proposal_id'],base_revision=value['base_revision'],operation_id=str(uuid.uuid4()))
    return result['operation_result']


def dispatch(store,recipe,pids=None):
    plan=icons.plan(store.project_root,input={'recipe_id':recipe['recipe_id'],'page_ids':pids or ['p01']})
    result=changes.commit(store.project_root,plan_id=plan['plan_id'],base_revision=plan['plan']['base_revision'],operation_id=str(uuid.uuid4()))
    return [tasks._lookup_task(store.load_document(),t,store) for t in result['operation_result']['task_ids']]


def start(store,task):
    return service.task_start(store.project_root,task_id=task['task_id'],execution_ref='synthetic-icon-host',supported_protocols=['changes.v1'],capabilities=['change_plan','candidate_result','icon_repair'])


def accept(store,task,data):
    staging=store.staging_dir/task['operation_id'];staging.mkdir(parents=True,exist_ok=True);(staging/'page.svg').write_bytes(data)
    result={'kind':'repair','files':[{'file_id':'svg','path':'page.svg','media_type':'image/svg+xml'}],
            'artifact_specs':[{'file_id':'svg','role':'svg','page_id':task['scope_pages'][0], 'provenance':{'source_type':'unknown','tool':'synthetic-test','invocation_ref':None}}]}
    return service.accept_result(store.project_root,**{k:task[k] for k in ('task_id','operation_id','produced_against')},result_payload=result)


def test_inspect_no_ids_duplicate_ids_transforms_and_local_use(icon_store):
    before=icon_store.current_revision_id();info=icons.inspect(icon_store.project_root,page_id='p01')
    paths={o['path'] for o in info['objects']}
    assert '2/0' in paths and '2/0/0' in paths and '2/0/1' in paths and '2/1' in paths
    assert '1' not in paths and not any(p.startswith('0') for p in paths)
    box=next(o['region'] for o in info['objects'] if o['path']=='2/0')
    assert box['x']>0.09 and icon_store.current_revision_id()==before


def test_confirm_idempotency_writer_boundary_and_no_output_changes(icon_store):
    before=icon_store.load_document();value=input_for(icon_store);p=icons.propose(icon_store.project_root,input=value);op=str(uuid.uuid4())
    args={'proposal_id':p['proposal_id'],'base_revision':value['base_revision'],'operation_id':op}
    first=icons.confirm(icon_store.project_root,**args);second=icons.confirm(icon_store.project_root,**args)
    after=icon_store.load_document();assert first['operation_result']==second['operation_result']
    assert after['compatibility']['minimum_writer']=='icon-quality.v1'
    assert after['pages']==before['pages'] and after['outputs']==before['outputs'] and after['tasks']==before['tasks']


def test_scope_rejects_text_defs_order_and_unselected_changes(icon_store):
    rec=confirm(icon_store);task=dispatch(icon_store,rec)[0];doc=icon_store.load_document();data=icons.svg_bytes(icon_store,doc['pages'][0]['svg'])
    for old,new in [(b'Keep this text',b'Changed text'),(b'M0 0L8 0L8 8',b'M0 0L9 0L8 8'),(b'x="60"',b'x="61"')]:
        with pytest.raises(OperationError,match='outside'):icons.check_scope(icon_store,doc,task,data.replace(old,new))
    root=icons.tree(data);root[2][0][0].set('d','M0 0L25 25');assert icons.check_scope(icon_store,doc,task,ET.tostring(root))['status']=='pass'
    root[2][0].append(ET.Element('{http://www.w3.org/2000/svg}image',{'href':'data:image/png;base64,AA=='}))
    with pytest.raises(OperationError,match='geometry'):icons.check_scope(icon_store,doc,task,ET.tostring(root))


def test_redraw_cannot_erase_the_whole_icon(icon_store):
    recipe=confirm(icon_store);task=dispatch(icon_store,recipe)[0];doc=icon_store.load_document()
    root=icons.tree(icons.svg_bytes(icon_store,doc['pages'][0]['svg']));root[2][0].clear()
    with pytest.raises(OperationError,match='visible native geometry'):
        icons.check_scope(icon_store,doc,task,ET.tostring(root))


def test_invalid_locator_nested_selection_and_old_proposal(icon_store):
    value=input_for(icon_store);info=icons.inspect(icon_store.project_root,page_id='p01');child=next(o for o in info['objects'] if o['path']=='2/0/0')
    value['targets'][0]['icons'][0]['objects'].append({k:child[k] for k in ('path','sha256')})
    with pytest.raises(OperationError,match='non-nested'):icons.propose(icon_store.project_root,input=value)
    original=input_for(icon_store);p=icons.propose(icon_store.project_root,input=original);confirm(icon_store)
    with pytest.raises(OperationError,match='stale'):icons.confirm(icon_store.project_root,proposal_id=p['proposal_id'],base_revision=original['base_revision'],operation_id=str(uuid.uuid4()))


def test_standard_candidate_and_capability_gate(icon_store):
    before=icon_store.load_document();recipe=confirm(icon_store,input_for(icon_store,method='standard'));task=dispatch(icon_store,recipe)[0]
    assert task['required_capabilities'][-1]=='icon_repair' or 'icon_repair' in task['required_capabilities']
    with pytest.raises(Exception,match='declared capabilities'):service.task_start(icon_store.project_root,task_id=task['task_id'],execution_ref='old-host',supported_protocols=['changes.v1'],capabilities=['change_plan','candidate_result'])
    start(icon_store,task);draft=icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')
    accepted=accept(icon_store,task,draft['svg'].encode());assert accepted['status']=='candidate_ready'
    after=icon_store.load_document();assert after['pages']==before['pages'] and after['outputs']==before['outputs']
    with pytest.raises(OperationError,match='PPT checks'):candidates.plan(icon_store.project_root,input={'schema_version':'candidate_selection.v1','project_id':after['project_id'],'base_revision':after['revision_id'],'candidate_ids':accepted['candidate_ids']})


def test_reuse_requires_adopted_sample_and_same_meaning(icon_store):
    value=input_for(icon_store);value['targets'][0]['icons'][0].update(method='reuse',sample_candidate_id='absent',sample_icon_index=0)
    with pytest.raises(OperationError):icons.propose(icon_store.project_root,input=value)


def test_catalog_fixed_and_all_icons_native():
    cat=icons.catalog();assert cat['version']=='1.49.0' and len(cat['icons'])==24
    from deck_master.compiler.svg import parse_svg
    for item in cat['icons']:
        data=(icons.CATALOG/(item['id']+'.svg')).read_bytes().replace(b'currentColor',b'#000000')
        parsed=parse_svg(data,page_id=item['id']);assert parsed['shapes'] and all(s['kind']!='image' for s in parsed['shapes'])

@pytest.mark.render
def test_actual_candidate_preview_and_cross_page_reuse(icon_store):
    before=icon_store.load_document();recipe=confirm(icon_store,input_for(icon_store,method='standard'));task=dispatch(icon_store,recipe)[0];start(icon_store,task)
    data=icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode();cid=accept(icon_store,task,data)['candidate_ids'][0]
    original_revision=icon_store.current_revision_id();result=candidate_preview.request(icon_store.project_root,candidate_id=cid)
    assert result['status']=='ready',result
    assert result['native_check']=='pass' and result['pictures']==0 and result['scope_check']['outside_scope_unchanged']
    assert candidate_preview.status(icon_store.project_root,candidate_id=cid)['cache_key']==result['cache_key']
    assert icon_store.current_revision_id()==original_revision
    doc=icon_store.load_document();selection={'schema_version':'candidate_selection.v1','project_id':doc['project_id'],'base_revision':doc['revision_id'],'candidate_ids':[cid]}
    plan=candidates.plan(icon_store.project_root,input=selection)['plan'];adopted=candidates.adopt(icon_store.project_root,input=plan,base_revision=doc['revision_id'],operation_id=str(uuid.uuid4()))
    assert adopted['operation_result']['icon_checks'][cid]
    values=[input_for(icon_store,pid,'reuse') for pid in ('p02','p03')];value=values[0];value['targets']+=values[1]['targets']
    for t in value['targets']:t['icons'][0].update(sample_candidate_id=cid,sample_icon_index=0)
    batch=confirm(icon_store,value);pending=dispatch(icon_store,batch,['p02','p03']);ids=[]
    for task in pending:
        start(icon_store,task);pid=task['scope_pages'][0]
        raw=icons.draft(icon_store.project_root,recipe_id=batch['recipe_id'],page_id=pid)['svg'].encode()
        next_id=accept(icon_store,task,raw)['candidate_ids'][0];ids.append(next_id)
        assert candidate_preview.request(icon_store.project_root,candidate_id=next_id)['status']=='ready'
    doc=icon_store.load_document();plan=candidates.plan(icon_store.project_root,input={**selection,'base_revision':doc['revision_id'],'candidate_ids':ids})['plan']
    # Another writer advances exactly one page target; the whole batch aborts.
    changed=copy.deepcopy(doc);changed['pages'][2]['svg']=store_ref=icon_store.put_json_object({**icon_store.read_object_json(changed['pages'][2]['svg']),'limitations':['concurrent target version']})
    changed=bump_revision(changed,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'single page conflict','read_set':[]})
    icon_store.commit_change(base_revision=doc['revision_id'],document=changed,operation_id=changed['change']['operation_id'])
    with pytest.raises(OperationError,match='no candidates adopted'):candidates.adopt(icon_store.project_root,input=plan,base_revision=doc['revision_id'],operation_id=str(uuid.uuid4()))
    assert icon_store.load_document()['pages'][1]==doc['pages'][1] and icon_store.load_document()['pages'][2]['svg']==store_ref
    restored=copy.deepcopy(changed);restored['pages'][2]['svg']=doc['pages'][2]['svg'];restored=bump_revision(restored,{'operation_id':str(uuid.uuid4()),'kind':'artifact_adoption','description':'restore target for explicit repreview','read_set':[]})
    icon_store.commit_change(base_revision=changed['revision_id'],document=restored,operation_id=restored['change']['operation_id'])
    plan=candidates.plan(icon_store.project_root,input={**selection,'base_revision':restored['revision_id'],'candidate_ids':ids})['plan'];op=str(uuid.uuid4())
    batch_result=candidates.adopt(icon_store.project_root,input=plan,base_revision=restored['revision_id'],operation_id=op)
    assert candidates.adopt(icon_store.project_root,input=plan,base_revision=restored['revision_id'],operation_id=op)['operation_result']==batch_result['operation_result']
    final=icon_store.load_document();assert all(a['page']==b['page'] and a['blueprint']==b['blueprint'] for a,b in zip(before['pages'],final['pages']))
    assert final['pages'][0]['svg']!=before['pages'][0]['svg']
    # Engineering recovery must retain frozen adopted checks without caches;
    # XML locators are not mistaken for content-addressed file references.
    from deck_master import exports
    import zipfile
    out=icon_store.project_root.parent/'portable';export=exports.create(icon_store.project_root,purpose='engineering',output_dir=out)
    recovered=icon_store.project_root.parent/'recovered'
    with zipfile.ZipFile(out/export['archive']) as z:z.extractall(recovered)
    restored_store=Store(recovered/'project');assert restored_store.load_document()==final
    assert not (restored_store.deck_root/'cache/candidate-previews').exists()
    for adoption in final['candidate_adoptions']:
        if adoption.get('icon_check_ref'):
            proof=restored_store.read_object_json(adoption['icon_check_ref']);assert proof['status']=='ready'
            for record in proof['files'].values():restored_store.read_object_bytes(record['file'])
    import zipfile
    raw,_=candidate_preview.file_bytes(icon_store.project_root,cache_key=result['cache_key'],name='candidate.pptx')
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(raw)) as z:assert b'ISC License' in z.read('docProps/core.xml')
    from deck_master.export_sanitize import sanitize
    with zipfile.ZipFile(BytesIO(sanitize(raw,'.pptx','test'))) as z:
        assert b'ISC License' in z.read('docProps/core.xml') and b'Cole Bemis' in z.read('docProps/core.xml')
    assert b'ISC License' in sanitize(data,'.svg','test')


def test_shared_geometry_cannot_change_unselected_use():
    root=icons.tree(b'<svg viewBox="0 0 100 100"><g id="shared"><rect width="10" height="10"/></g><use href="#shared" x="20"/></svg>')
    with pytest.raises(OperationError,match='shared'):icons.selected(root,[{'path':'0','sha256':icons.digest(icons.canon(root[0]))}])
    assert icons.selected(root,[{'path':'1','sha256':icons.digest(icons.canon(root[1]))}])


def test_text_tail_spaces_are_protected():
    a=icons.tree(b'<svg><text>Hello<tspan>world</tspan> spaced</text></svg>')
    b=icons.tree(b'<svg><text>Hello<tspan>world</tspan>spaced</text></svg>')
    assert icons.canon(a)!=icons.canon(b)


def test_multi_path_replacement_is_bounded(icon_store):
    value=input_for(icon_store,method='standard');info=icons.inspect(icon_store.project_root,page_id='p01')
    value['targets'][0]['icons'][0]['objects']=[{k:o[k] for k in ('path','sha256')} for o in info['objects'] if o['path'] in ('2/0/0','2/0/1')]
    recipe=confirm(icon_store,value);draft=icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')
    assert draft['scope_check']['selected_objects']==2


def test_cancelled_icon_result_is_late_and_repeat_safe(icon_store):
    recipe=confirm(icon_store,input_for(icon_store,method='standard'));task=dispatch(icon_store,recipe)[0];start(icon_store,task)
    raw=icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode()
    service.task_cancel(icon_store.project_root,task_id=task['task_id'],reason='test cancellation')
    before=icon_store.load_document()
    from deck_master.tasks import TaskConflict
    with pytest.raises(TaskConflict,match='after cancellation'):accept(icon_store,task,raw)
    with pytest.raises(TaskConflict,match='cancelled output'):accept(icon_store,task,raw)
    assert icon_store.load_document()['pages']==before['pages']
    assert not icon_store.load_document().get('candidates')


def test_standard_geometry_tamper_is_rejected(icon_store):
    recipe=confirm(icon_store,input_for(icon_store,method='standard'));task=dispatch(icon_store,recipe)[0]
    data=icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode()
    root=icons.tree(data);root[2][0].set('fill','#ff0000')
    with pytest.raises(OperationError,match='confirmed asset'):icons.check_scope(icon_store,icon_store.load_document(),task,ET.tostring(root))


@pytest.mark.render
def test_preview_failure_retry_and_corrupt_files(icon_store,monkeypatch):
    recipe=confirm(icon_store,input_for(icon_store,method='standard'));task=dispatch(icon_store,recipe)[0];start(icon_store,task)
    cid=accept(icon_store,task,icons.draft(icon_store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode())['candidate_ids'][0]
    context=candidate_preview._context(icon_store.project_root,cid);key=context[-1];identity=context[-2]
    folder=candidate_preview._folder(icon_store)/key;folder.mkdir()
    import hashlib
    files={}
    for name in ('candidate.svg','candidate.pptx','candidate.png','readback.json'):
        (folder/name).write_bytes(b'failed diagnostic')
        files[name]={'sha256':hashlib.sha256(b'failed diagnostic').hexdigest(),'bytes':17}
    (folder/'report.json').write_text(json.dumps({'identity':identity,'cache_key':key,'candidate_ref':identity['candidate_ref'],'candidate_id':cid,'status':'failed','files':files}))
    calls=[]
    def broken_compile(*args,**kwargs):calls.append(True);raise ValueError('retry probe')
    monkeypatch.setattr(candidate_preview,'compile_deck',broken_compile)
    candidate_preview.request(icon_store.project_root,candidate_id=cid,retry=True)
    assert calls==[True]
    (folder/'candidate.png').write_bytes(b'corrupted')
    assert candidate_preview._cached(icon_store,key,identity) is None
    with pytest.raises(OperationError):candidate_preview.require_ready(icon_store.project_root,cid)


def test_icon_host_cannot_return_page_or_content_update(icon_store):
    recipe=confirm(icon_store);task=dispatch(icon_store,recipe)[0]
    from deck_master.tasks import _check_scope,EnvelopeError
    for key in ('pages','page_order','content_update','content_plan','reviews'):
        with pytest.raises(EnvelopeError,match='Page and original image stay fixed'):_check_scope('repair',{'kind':'repair',key:[{'page_id':'p01'}]},task)
