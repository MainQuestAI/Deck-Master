"""Fixed-snapshot reader integration, over explicit synthetic Runtime projects."""
import copy
import pytest
from deck_master import content_insight as ui, content_production
from deck_master.insight_http import route
from test_compose_v2_phases import _project, _request, _accept_argument, _adopt_direction


def bytes_at(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob('*') if p.is_file()}


def candidate(tmp_path):
    project, store = _project(tmp_path)
    _request(project, store, content_intent='plan_only')
    task, result = _accept_argument(project, store)
    ref = next(r for r in result['result_refs'] if store.read_object_json(r)['schema_version'] == 'narrative.v1')
    return project, store, task, ref


def test_readers_no_writes_and_missing_decision_can_be_recorded(tmp_path):
    project, store, task, ref = candidate(tmp_path)
    before = bytes_at(project); rev = store.current_revision_id()
    index = ui.arguments(project, revision=rev)
    assert index['data']['items'][0]['ref'] == ref
    detail = ui.argument(project, ref['sha256'], revision=rev)
    assert detail['data']['adoption']['needs_decision'] is True
    assert detail['data']['adoption']['can_record_direction_decision'] is True
    assert detail['data']['adoption']['can_adopt'] is False
    assert detail['data']['item']['central_statement']
    methods = ui.task_methods(project, task['task_id'], revision=rev, availability='current')
    assert methods['data']['resources']
    assert bytes_at(project) == before
    _adopt_direction(project, store, ref)
    later = bytes_at(project)
    current = ui.argument(project, ref['sha256'])
    assert current['data']['adoption']['can_adopt'] is True
    assert current['data']['adoption']['needs_decision'] is False
    historic = ui.argument(project, ref['sha256'], revision=rev)
    assert not historic['data']['adoption']['can_adopt']
    assert bytes_at(project) == later


def test_unreachable_and_query_boundaries(tmp_path):
    project, store, task, ref = candidate(tmp_path)
    for query in ['revision=x&revision=y', 'limit=0', 'limit=-1', 'offset=-1', 'unknown=x']:
        with pytest.raises(Exception): route(project, '/api/content/arguments', query)
    with pytest.raises(ui.InsightError): ui.argument(project, 'a'*64)
    with pytest.raises(ui.InsightError): ui.task_methods(project, 'missing')
    with pytest.raises(ui.InsightError): ui.arguments(project, limit=True)


def test_adoption_shared_check_is_pure_and_matches_write(tmp_path):
    project, store, task, ref = candidate(tmp_path)
    _adopt_direction(project, store, ref)
    doc = store.load_document(); before = copy.deepcopy(doc); files = bytes_at(project)
    preview = ui.argument(project, ref['sha256'])['data']['adoption']
    updated, _, _ = content_production.check_proposal_adoption(store, doc, input={'proposal_ref': ref,
        'decision_ref': preview['existing_decision_ref'], 'write_scope': preview['write_scope']})
    assert updated['narrative'] == ref
    assert doc == before and files == bytes_at(project)


def test_schemas_and_corrupt_object_are_discriminated(tmp_path):
    from deck_master import models
    project, store, task, ref = candidate(tmp_path)
    for value in (ui.arguments(project), ui.argument(project, ref['sha256']), ui.task_methods(project, task['task_id'])):
        models.validate_schema(value['schema_version'].split('.')[0], value)
    # A reachable corrupt formal pointer stays distinguishable from absent.
    _adopt_direction(project, store, ref)
    (project / ref['path']).write_bytes(b'{broken')
    value = ui.arguments(project)
    item = next(i for i in value['data']['items'] if i['ref'] == ref)
    assert item['readable'] is False and set(item) == {'ref', 'readable', 'issues'}
    models.validate_schema('ui_arguments', value)
    detail = ui.argument(project, ref['sha256'])
    assert detail['status'] == 'unreadable' and detail['data'] is None
    models.validate_schema('ui_argument', detail)
    invalid = copy.deepcopy(detail); invalid['data'] = {}
    with pytest.raises(ValueError): models.validate_schema('ui_argument', invalid)
    invalid = copy.deepcopy(value); invalid['data']['items'][0]['maturity'] = 'argument'
    with pytest.raises(ValueError): models.validate_schema('ui_arguments', invalid)


def test_method_preview_no_phase_browse_and_independent_dependency(tmp_path):
    from deck_master import method_library_view as lib, models
    project, store, task, ref = candidate(tmp_path)
    before = bytes_at(project)
    no_phase = lib.preview(project, {'context': {'mode': 'project', 'revision': store.current_revision_id()}, 'selected_resource_ids': ['content-m04']})
    assert no_phase['browse_status'] == 'available' and no_phase['dispatch_status'] == 'cannot_dispatch'
    assert no_phase['preparation_only'] and not no_phase['handoff']['copy_allowed']
    assert no_phase['explicit_ids'] == ['content-m04']
    ctx = {'mode':'independent', 'role':'deck-content', 'phase':'argument', 'review_units':[]}
    value = lib.preview(project, {'context':ctx, 'selected_resource_ids':['content-m04']})
    models.validate_schema('ui_method_preview', value)
    assert value['selection_status'] == 'validated' and value['dispatch_status'] == 'not_applicable'
    r = next(r for r in value['resolved_manifest'] if r['id'] == 'content-m04')
    assert lib.resource(r['id'], catalog_digest=value['catalog_digest'], sha256=r['sha256'])['content']
    with pytest.raises(ui.InsightError) as conflict:
        lib.resource(r['id'], catalog_digest=value['catalog_digest'], sha256='0'*64)
    assert conflict.value.http_status == 409
    with pytest.raises(ui.InsightError) as conflict:
        lib.preview(project, {'context':ctx,'selected_resource_ids':[], 'expected_basis':{'catalog_digest':'0'*64,'context_digest':value['context_digest']}})
    assert conflict.value.http_status == 409
    for ids in [['../outside'], ['installation']]:
        with pytest.raises(ui.InsightError): lib.preview(project, {'context':ctx, 'selected_resource_ids':ids})
    assert bytes_at(project) == before


def test_http_read_routes_and_preview(tmp_path):
    from deck_master.web import WorkbenchServer
    from test_web import _get_json, _post_json
    project, store, task, ref = candidate(tmp_path)
    server = WorkbenchServer(project); url = server.start().rstrip('/')
    try:
        token = _get_json(url+'/api/session')[2]['token']; before = bytes_at(project)
        status, _, data = _get_json(url+'/api/content/arguments')
        assert status == 200 and data['data']['items']
        status, _, data = _get_json(url+'/api/content/arguments?limit=0')
        assert status == 400
        status, data = _post_json(url+'/api/method-library/preview', {'context':{'mode':'project','revision':store.current_revision_id()},'selected_resource_ids':[]},token=token,origin=url)
        assert status == 200 and data['dispatch_status'] == 'cannot_dispatch'
        assert bytes_at(project) == before
    finally: server.stop()


def test_plan_only_associates_real_plan_without_pages(tmp_path):
    from test_compose_v2_phases import _dispatch, _submit, _argument_narrative, _plan_input
    from deck_master import models
    project, store = _project(tmp_path); _request(project, store, content_intent='plan_only')
    task = _dispatch(store, phase='argument'); doc = store.load_document()
    plan = {'schema_version':'content_plan.v2','plan_id':'plan-1','version':1,'project_id':doc['project_id'],
        'task_id':None,'origin':'host_composed','basis':{'revision_id':doc['revision_id'],'input_digest':models.compute_input_digest(doc)},
        'previous_ref':None,'mode':'planned','narrative_ref':None,'imported_manuscript':None,
        'input':_plan_input(doc,['p1']),'page_links':[]}
    out = _submit(project,task,{'narrative':_argument_narrative(doc['project_id']),'plan':plan},'narrative')
    value = ui.argument(project,out['result_refs'][0]['sha256'])
    assert not store.load_document()['pages']
    assert value['data']['plans'][0]['ref'] == out['result_refs'][1]
    assert value['data']['plans'][0]['data']['planned_roles'][0]['page_ref'] is None
    models.validate_schema('ui_argument',value)

    # A later synthetic current direction has its own Plan, while the completed
    # task still exposes the earlier pair. Never borrow the current Plan for it.
    old_narrative, old_plan = out['result_refs']
    current=store.load_document();n=store.read_object_json(old_narrative);n['narrative_id']='different-direction'
    n['nodes'][0]['statement']='另一份合法方向';nref=store.put_json_object(n)
    p=store.read_object_json(old_plan);p['plan_id']='different-plan';p['narrative_ref']=nref
    p['input']['page_roles'][0]['role']='另一方向的页面职责'
    models.validate_schema('content_plan',p);pref=store.put_json_object(p)
    updated=models.bump_revision(current,{'operation_id':'synthetic-plan-pair','kind':'task_update','description':'synthetic distinct pair','read_set':[]})
    updated['narrative']=nref;updated['content_plan']=pref
    store.commit_change(base_revision=current['revision_id'],document=updated,operation_id='synthetic-plan-pair')
    left=ui.argument(project,old_narrative['sha256'])['data']
    right=ui.argument(project,nref['sha256'])['data']
    assert [p['ref'] for p in left['plans']]==[old_plan]
    assert [p['ref'] for p in right['plans']]==[pref]
    assert left['plans'][0]['data']['planned_roles']!=right['plans'][0]['data']['planned_roles']
    assert not store.load_document()['pages']


def reviewed_project(tmp_path):
    from rc3_fixtures import public_project
    from deck_master.store import Store
    from deck_master import models
    handle = public_project(tmp_path,create_input={'brief':'合成教学阅读验证','title':'教学'},manuscript={'pages':[{'schema_version':'deck_page_package.v2','page_id':'p1',
        'customer_visible':{'title':'合成教学稿','body_blocks':[{'id':'b1','type':'paragraph','text':'明确未知，不猜结论。'}]},
        'visual_spec':{'intent':'教学','reference_mode':'new_design'}}]})
    project=handle['project']; store=Store(project);doc=store.load_document()
    review={'schema_version':'deck_review.v1','review_id':'reading-review','kind':'content','status':'needs_review',
        'subjects':[doc['pages'][0]['page']],'dependencies':[],
        'reviewer':{'type':'host_self','id':'synthetic','execution_ref':None,'independence_confirmed':False},
        'observations':['合成工程验证'], 'findings':[
            {'finding_id':'f1','kind':'content','impact':'must_fix','page_id':'p1','element_refs':['atom:p1:block:b1:text'],
             'message':'补充限定条件','expected':'说明适用范围','actual':'未说明','evidence':[],'resolution':'open'},
            {'finding_id':'f2','kind':'content','impact':'must_fix','page_id':'p1','element_refs':['atom:p1:missing'],
             'message':'核实原位置','expected':'原位置可读','actual':'位置已失效','evidence':[],'resolution':'open'}],
        'created_at':'2026-10-20T10:00:00Z','replaces':None}
    models.validate_schema('review',review);ref=store.put_json_object(review)
    updated=models.bump_revision(doc,{'operation_id':'synthetic-review','kind':'task_update','description':'synthetic review','read_set':[]});updated['reviews']=[ref]
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='synthetic-review')
    return project,store,ref


def test_review_identity_source_index_page_fallback_and_no_write(tmp_path):
    from deck_master import models
    project,store,ref=reviewed_project(tmp_path);before=bytes_at(project)
    value=ui.review_reading(project,'reading-review',review_sha256=ref['sha256'])
    assert value['data']['review']['data']['status']=='needs_review'
    assert [t['source_index'] for t in value['data']['targets']]==[0,1]
    assert [t['locator_status'] for t in value['data']['targets']]==['exact','page_only']
    models.validate_schema('ui_review_reading',value)
    for result in (ui.evidence(project,'p1'),ui.requirements(project,'p1')):
        models.validate_schema(result['schema_version'].split('.')[0],result)
    assert bytes_at(project)==before
    with pytest.raises(ui.InsightError):ui.review_reading(project,'other-review',review_sha256=ref['sha256'])
    (project/ref['path']).write_bytes(b'broken')
    broken=ui.review_reading(project,'reading-review',review_sha256=ref['sha256'])
    assert broken['data'] is None and broken['status']=='unreadable'
    models.validate_schema('ui_review_reading',broken)


def test_m04_e04_preview_uses_real_dag_without_execution(tmp_path):
    from deck_master import method_library_view as lib
    from deck_master.resource_catalog import load_catalog, select
    from deck_master.method_resources import resolve_root
    project, store, _, _ = candidate(tmp_path)
    chosen=['content-m04','case-e04-walkthrough'];ctx={'mode':'independent','role':'deck-content','phase':'argument','review_units':[]}
    before=bytes_at(project);value=lib.preview(project,{'context':ctx,'selected_resource_ids':chosen})
    expected=select(load_catalog(resolve_root()),chosen,role='deck-content',phase='argument')
    manifest_ids=[r['id'] for r in value['resolved_manifest']]
    assert [i for i in manifest_ids if i not in value['default_ids']]==[i for i in expected if i not in value['default_ids']]
    assert 'example-e04-input' in manifest_ids and 'example-e04-after' in manifest_ids
    assert 'example-e04-before' not in manifest_ids
    assert bytes_at(project)==before


def test_resource_list_does_not_read_unselected_bodies(tmp_path,monkeypatch):
    from deck_master import method_library_view as lib
    from pathlib import Path
    project,store,_,_=candidate(tmp_path);original=Path.read_bytes;read_paths=[]
    def observed(self):
        read_paths.append(str(self));return original(self)
    monkeypatch.setattr(Path,'read_bytes',observed)
    lib.preview(project,{'context':{'mode':'independent','role':'deck-content','phase':'argument','review_units':[]},'selected_resource_ids':['content-m04']})
    assert not any('E06' in p or 'M10' in p or 'check_case_numbers.py' in p for p in read_paths)


def test_page_keeps_old_narrative_and_reports_source_damage_locally(tmp_path):
    from test_compose_v2_phases import _dispatch,_submit,_page,_plan_input
    from deck_master import models
    project,store=_project(tmp_path);_request(project,store)
    _,out=_accept_argument(project,store);old=out['result_refs'][0];_adopt_direction(project,store,old)
    task=_dispatch(store,phase='page_copy');doc=store.load_document()
    _submit(project,task,{'pages':[_page(store,doc,'p1')],'page_order':['p1'],'plan_input':_plan_input(doc,['p1'])},'page_copy')
    old_revision=store.current_revision_id()
    # Synthetic historical snapshot: the page intentionally remains bound to its
    # original immutable Narrative. Adoption policy itself is covered separately.
    doc=store.load_document();n=store.read_object_json(old)
    n['narrative_id']='nar-second';n['nodes'][0]['statement']='第二份明确不同的论证方向'
    new=store.put_json_object(n)
    updated=models.bump_revision(doc,{'operation_id':'synthetic-new-mainline','kind':'task_update',
        'description':'synthetic later mainline with preserved page binding','read_set':[]})
    updated['narrative']=new
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='synthetic-new-mainline')
    before=bytes_at(project)
    value=ui.evidence(project,'p1')
    assert value['data']['narrative_ref']==old and value['data']['alignment']=='bound_to_older_narrative'
    body=next(e for e in value['data']['elements'] if e['element_ref']=='atom:p1:block:b1:text')
    assert body['nodes'][0]['statement']!='第二份明确不同的论证方向'
    assert body['qualifications']
    assert ui.evidence(project,'p1',revision=old_revision)['data']['alignment']=='current'
    models.validate_schema('ui_page_evidence',value)
    assert bytes_at(project)==before
    source=store.load_document()['sources'][0];(project/source['extract']['path']).write_bytes(b'broken')
    broken=ui.evidence(project,'p1')
    assert broken['status']=='partial' and broken['data']['elements']
    assert any(i['field']=='source' for i in broken['issues'])


def test_review_source_issue_never_becomes_body_repair(tmp_path):
    from deck_master import models
    project,store,ref=reviewed_project(tmp_path);doc=store.load_document()
    review=store.read_object_json(ref);review['findings'][0]['kind']='source'
    new=store.put_json_object(review)
    updated=models.bump_revision(doc,{'operation_id':'synthetic-source-finding','kind':'task_update','description':'synthetic source issue','read_set':[]})
    updated['reviews']=[new]
    store.commit_change(base_revision=doc['revision_id'],document=updated,operation_id='synthetic-source-finding')
    target=ui.review_reading(project,'reading-review')['data']['targets'][0]
    assert target['repair_layer']=='source' and not target['repair_allowed']
    (project/doc['pages'][0]['page']['path']).write_bytes(b'broken')
    value=ui.requirements(project,'p1')
    assert value['status']=='unreadable' and value['data'] is None
    models.validate_schema('ui_content_requirements',value)
