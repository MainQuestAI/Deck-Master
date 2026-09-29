"""Editorial invariants over real Store/Host services; all materials are synthetic."""
import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from deck_master import content_ops, content_plan, operations, service, tasks
from deck_master.models import content_identity
from deck_master.samples import create_sample
from deck_master.store import Store


@pytest.fixture
def project(tmp_path):
    path = tmp_path / 'project'; create_sample(path, page_count=3, readonly=False)
    return path, Store(path)


def value(store, action='edit', ids=('p02',), **extra):
    doc = store.load_document(); entries = {e['page_id']: e for e in doc['pages']}
    result = {'schema_version': 'content_operation_input.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
              'content_plan_ref': doc.get('content_plan'), 'action': action, 'instruction': 'Explicit synthetic editorial change',
              'targets': [{'page_id': pid, 'page_ref': entries[pid]['page']} for pid in ids], **extra}
    if action == 'edit' and 'customer_visible' not in extra:
        result['customer_visible'] = copy.deepcopy(store.read_object_json(entries[ids[0]]['page'])['customer_visible'])
        result['customer_visible']['title'] += ' Changed 42'
    return result


def commit(path, store, input):
    preview = content_ops.plan(path, input=input)
    return content_ops.commit(path, plan_id=preview['plan_id'], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']


def dispatch(path, store, action, ids):
    result = commit(path, store, value(store, action, ids))
    return tasks._lookup_task(store.load_document(), result['task_ids'][0], store)


def start(path, task):
    service.task_start(path, task_id=task['task_id'], execution_ref='synthetic-editorial-host', supported_protocols=['compose.v1'], capabilities=task['required_capabilities'])


def result(store, task, action='rewrite'):
    doc = store.load_document(); entries = {e['page_id']: e for e in doc['pages']}; ids = task['scope_pages']
    outline = copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])
    upserts = []; removed = []
    if action == 'rewrite':
        for pid in ids:
            page = copy.deepcopy(store.read_object_json(entries[pid]['page'])); page['customer_visible']['title'] += ' Rewritten'; upserts.append(page)
        order = list(entries)
    else:
        removed = ids
        for i in range(1 if action == 'merge' else 2):
            page = copy.deepcopy(store.read_object_json(entries[ids[0]]['page'])); page['page_id'] = 'derived-' + str(i); page['customer_visible']['title'] = 'Synthetic derived page ' + str(i); upserts.append(page)
        old_goals = {g['page_id']: g for g in outline['goals']}; new_goals = []
        for page in upserts:
            goal = copy.deepcopy(old_goals[ids[0]]); goal['goal_id'] = 'goal-' + page['page_id']; goal['page_id'] = page['page_id']; new_goals.append(goal)
        outline['goals'] = [g for g in outline['goals'] if g['page_id'] not in ids] + new_goals
        outline['chapters'] = [{'chapter_id': 'synthetic-editorial', 'title': 'Synthetic editorial chapter', 'goal_ids': [g['goal_id'] for g in outline['goals']]}]
        order = [pid for pid in entries if pid not in ids] + [p['page_id'] for p in upserts]
    return {'kind': 'compose', 'content_update': {'input_digest': task['input_digest'], 'upsert_pages': upserts,
            'remove_page_ids': removed, 'page_order': order, 'impact_summary': 'Explicit synthetic selected-page edit; all other facts preserved.'}, 'content_plan': outline}


def accept(path, task, envelope):
    return service.accept_result(path, task_id=task['task_id'], operation_id=task['operation_id'], produced_against=task['produced_against'], result_payload=envelope)


def test_direct_edit_preserves_original_unselected_and_rebinds_outline(project):
    path, store = project; before = copy.deepcopy(store.load_document()); planned = content_ops.plan(path, input=value(store))
    assert store.load_document() == before
    commit(path, store, planned['plan']['input']); after = store.load_document()
    assert after['pages'][0] == before['pages'][0] and after['pages'][2] == before['pages'][2]
    assert after['pages'][1]['blueprint'] == before['pages'][1]['blueprint'] and after['pages'][1]['svg'] is None
    assert after['pages'][1]['page'] != before['pages'][1]['page'] and not any(after['outputs'].values())
    projection = content_plan.show(path)['content_plan']; assert projection['origin'] == 'user_edited' and projection['applicability'] == 'current'
    assert after['annotations'] == before['annotations'] if 'annotations' in before else 'annotations' not in after


def test_identical_edit_and_reorder_do_not_invalidate_or_change_content_identity(project):
    path, store = project; before = copy.deepcopy(store.load_document()); visible = store.read_object_json(before['pages'][1]['page'])['customer_visible']
    for input in [value(store, customer_visible=visible), value(store, 'reorder', (), page_order=[p['page_id'] for p in before['pages']])]:
        input['base_revision'] = store.current_revision_id()
        commit(path, store, input); after = store.load_document()
        assert after['pages'] == before['pages'] and after['tasks'] == before['tasks'] and content_identity(after) == content_identity(before)


def test_reorder_remove_preserve_objects_and_history(project):
    path, store = project; before = copy.deepcopy(store.load_document()); old = {e['page_id']: e for e in before['pages']}
    commit(path, store, value(store, 'reorder', (), page_order=['p03', 'p01', 'p02']))
    assert store.load_document()['pages'] == [old[p] for p in ('p03', 'p01', 'p02')]
    commit(path, store, value(store, 'remove', ('p01',)))
    doc = store.load_document(); assert doc['pages'] == [old['p03'], old['p02']]
    assert store.load_document(before['revision_id'])['pages'] == before['pages']
    assert {g['page_id'] for g in content_plan.show(path)['content_plan']['goals']} == {'p02', 'p03'}


def test_reorder_keeps_page_generation_task_but_remove_supersedes_it(project):
    from deck_master import changes
    path, store = project; doc = store.load_document(); e = doc['pages'][1]
    data = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'], 'mode': 'auto', 'intent': 'test', 'instruction': 'Synthetic pending page', 'annotation_refs': [], 'max_calls': 1,
            'targets': [{'page_id': 'p02', 'page_ref': e['page'], 'layer': 'original_image', 'stage': 'blueprint', 'artifact_ref': e['blueprint']}]}
    preview = changes.plan(path, input=data); t = changes.commit(path, plan_id=preview['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))['operation_result']['task_ids'][0]
    commit(path, store, value(store, 'reorder', (), page_order=['p03', 'p02', 'p01']))
    assert tasks._lookup_task(store.load_document(), t, store)['status'] == 'awaiting_host'
    commit(path, store, value(store, 'remove', ('p02',)))
    assert tasks._lookup_task(store.load_document(), t, store)['status'] == 'superseded'


def test_receipt_replay_after_index_loss_and_concurrent_commit(project):
    path, store = project; p = content_ops.plan(path, input=value(store)); op = str(uuid.uuid4()); args = dict(plan_id=p['plan_id'], base_revision=store.current_revision_id(), operation_id=op)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: content_ops.commit(path, **args), range(2)))
    assert first['operation_result'] == second['operation_result']
    commit(path, store, value(store, ids=('p01',))); pointer = store.read_current(); (store.deck_root / 'operations' / (op + '.json')).unlink()
    assert content_ops.commit(path, **args)['operation_result'] == first['operation_result'] and store.read_current() == pointer


@pytest.mark.parametrize('action,ids', [('rewrite', ('p02',)), ('merge', ('p01', 'p02')), ('split', ('p02',))])
def test_host_result_scope_and_new_identity_lineage(project, action, ids):
    path, store = project; before = copy.deepcopy(store.load_document()); task = dispatch(path, store, action, ids)
    assert store.load_document()['pages'] == before['pages'] and task['call_allowances'] == []
    start(path, task); envelope = result(store, task, action); accept(path, task, envelope); after = store.load_document()
    for original in before['pages']:
        if original['page_id'] not in ids:
            assert next(e for e in after['pages'] if e['page_id'] == original['page_id']) == original
    if action != 'rewrite':
        lineage = content_ops.lineage(path, page_id='derived-0')['records'][0]['derivation']
        assert [e['page_id'] for e in lineage['source_pages']] == list(ids) and lineage['annotation_policy'] == 'retain_original_basis'
    assert content_plan.show(path)['content_plan']['applicability'] == 'current'


def test_rewrite_cannot_change_unselected_page_or_goals(project):
    path, store = project; task = dispatch(path, store, 'rewrite', ('p02',)); start(path, task); e = result(store, task)
    before = store.current_revision_id(); extra = store.read_object_json(store.load_document()['pages'][0]['page']); e['content_update']['upsert_pages'].append(extra)
    with pytest.raises(operations.OperationError): accept(path, task, e)
    assert store.current_revision_id() == before
    e = result(store, task); e['content_plan']['goals'][0]['purpose'] = 'Unselected goal changed'
    with pytest.raises(operations.OperationError): accept(path, task, e)
    assert store.current_revision_id() == before


def test_split_cannot_reuse_removed_historical_id(project):
    path, store = project; commit(path, store, value(store, 'remove', ('p01',))); task = dispatch(path, store, 'split', ('p02',)); start(path, task)
    e = result(store, task, 'split'); e['content_update']['upsert_pages'][0]['page_id'] = 'p01'; e['content_update']['page_order'][-2] = 'p01'
    with pytest.raises(operations.OperationError, match='historical'): accept(path, task, e)


def test_stale_host_and_stale_plan_do_not_overwrite_new_page(project):
    path, store = project; task = dispatch(path, store, 'rewrite', ('p02',)); start(path, task); envelope = result(store, task)
    stale = content_ops.plan(path, input=value(store, ids=('p01',))); commit(path, store, value(store, ids=('p02',))); before = copy.deepcopy(store.load_document())
    with pytest.raises(operations.OperationError): content_ops.commit(path, plan_id=stale['plan_id'], base_revision=stale['plan']['base_revision'], operation_id=str(uuid.uuid4()))
    with pytest.raises(tasks.TaskConflict): accept(path, task, envelope)
    assert store.load_document()['pages'] == before['pages'] and store.load_document()['content_plan'] == before['content_plan']


def test_recoverable_input_noop_and_material_replacement(project, tmp_path):
    path, store = project; source = tmp_path / 'new.md'; source.write_text('Synthetic material\nOnly one page fact changes: 42.\n')
    patch = {'reason': 'Add explicit synthetic material', 'source_changes': {'add': [{'path': str(source)}]}}
    base = store.current_revision_id(); op = str(uuid.uuid4()); original = copy.deepcopy(store.load_document()['pages'])
    response = content_ops.inputs(path, input=patch, base_revision=base, operation_id=op); r = response['operation_result']; assert r['input_alignment'] == 'needs_reconciliation'
    source.unlink(); (store.deck_root / 'operations' / (op + '.json')).unlink()
    assert content_ops.inputs(path, input=patch, base_revision=base, operation_id=op)['operation_result'] == r
    assert store.load_document()['pages'] == original
    assert operations.show(path, operation_id=op)['operation_result'] == r
    noop = content_ops.inputs(path, input={'reason': 'Explicit no-op', 'task_patch': {'audience': store.load_document()['task']['audience']}}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert noop['operation_result']['status'] == 'unchanged' and store.load_document()['pages'] == original


def test_versioned_source_locator_does_not_fake_precision(project, tmp_path):
    path, store = project; material = tmp_path / 'material.md'; material.write_text('Alpha\nOriginal detail\n')
    r = content_ops.inputs(path, input={'reason': 'Synthetic add', 'source_changes': {'add': [{'path': str(material)}]}}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']
    source_id = r['diff']['sources_added'][0]; old = content_ops.source(path, source_id=source_id, locator='L2')
    assert old['location'] == 'exact' and 'Original detail' in json.dumps(old['matches'])
    material.write_text('Beta\nReplacement detail\n')
    content_ops.inputs(path, input={'reason': 'Synthetic replace', 'source_changes': {'replace': [{'source_id': source_id, 'path': str(material)}]}}, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    restored = content_ops.source(path, source_id=source_id, extract_sha256=old['source_version']['extract']['sha256'], locator='L2')
    assert restored['text'] == old['text'] and restored['revision_id'] == old['revision_id']
    assert content_ops.source(path, source_id=source_id, locator='imagined-page-99')['location'] == 'material_only'
    assert 'original_uri' not in json.dumps(restored)


def test_outline_keeps_page_copy_separate_and_requires_dual_basis(project):
    path, store = project; before = copy.deepcopy(store.load_document()); outline = copy.deepcopy(store.read_object_json(before['content_plan'])['input'])
    outline['goals'][1]['purpose'] += ' Explicit outline goal edit'
    input = value(store, 'outline', (), content_plan=outline); commit(path, store, input)
    after = store.load_document(); assert after['pages'] == before['pages'] and after['outputs'] == before['outputs']
    assert store.read_object_json(after['content_plan'])['input'] == outline
    input['base_revision'] = after['revision_id']
    with pytest.raises(operations.OperationError): content_ops.plan(path, input=input)


def test_source_hash_cannot_escape_selected_historical_snapshot(project, tmp_path):
    path, store = project; old = store.current_revision_id(); material = tmp_path / 'later.md'; material.write_text('Later source')
    r = content_ops.inputs(path, input={'reason': 'Later input', 'source_changes': {'add': [{'path': str(material)}]}}, base_revision=old, operation_id=str(uuid.uuid4()))['operation_result']
    sid = r['diff']['sources_added'][0]; ref = content_ops.source(path, source_id=sid)['source_version']['extract']['sha256']
    with pytest.raises(operations.OperationError): content_ops.source(path, source_id=sid, revision=old, extract_sha256=ref)


def test_cli_http_origin_and_recoverable_result(project, capsys, tmp_path):
    import urllib.request
    import urllib.error
    from deck_master import cli
    from deck_master.web import WorkbenchServer
    path, store = project; payload = value(store); file = tmp_path / 'input.json'; file.write_text(json.dumps(payload))
    assert cli.main(['content', 'plan', '--project', str(path), '--input', str(file)]) == 0
    planned = json.loads(capsys.readouterr().out); server = WorkbenchServer(path); url = server.start().rstrip('/')
    def post(endpoint, body, headers):
        request = urllib.request.Request(url + endpoint, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **headers}, method='POST')
        try:
            with urllib.request.urlopen(request) as response:return response.status, json.load(response)
        except urllib.error.HTTPError as error:return error.code, json.load(error)
    try:
        session = json.load(urllib.request.urlopen(url + '/api/session')); request = {'plan_id': planned['plan_id'], 'base_revision': store.current_revision_id(), 'operation_id': str(uuid.uuid4())}; before = store.read_current()
        assert post('/api/content/commit', request, {'Origin': 'https://example.invalid', 'X-Deck-Token': session['token']})[0] == 403
        assert post('/api/content/commit', request, {'Origin': url})[0] == 403
        assert store.read_current() == before
        status, accepted = post('/api/content/commit', request, {'Origin': url, 'X-Deck-Token': session['token']})
        assert status == 200 and accepted['status'] == 'committed'
        stored = json.load(urllib.request.urlopen(url + '/api/operations/' + request['operation_id'])); assert stored['operation_result'] == accepted['operation_result']
    finally:server.stop()


def test_derived_pages_do_not_retarget_original_annotations(project):
    from deck_master import annotation_service
    path, store = project; doc = store.load_document(); original = doc['pages'][1]
    note = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
            'scope': 'page', 'page_id': 'p02', 'page_ref': original['page'], 'intent': 'clarify', 'body': 'Synthetic old-basis note', 'status': 'open', 'location': {'kind': 'whole'}}
    annotation_service.save(path, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'], 'annotations': [note]}, base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    annotations = copy.deepcopy(store.load_document()['annotations']); task = dispatch(path, store, 'split', ('p02',)); start(path, task); envelope = result(store, task, 'split')
    accept(path, task, envelope); record_count = len(store.load_document()['page_derivations']); accept(path, task, envelope)
    after = store.load_document(); assert after['annotations'] == annotations and len(after['page_derivations']) == record_count == 1
    retained = store.read_object_json(annotations[0]); assert retained['page_id'] == 'p02' and retained['page_ref'] == original['page']


def test_changed_body_marks_retained_original_basis_stale(project):
    from deck_master import workbench
    path, store = project; commit(path, store, value(store))
    stage = workbench.page_lineage(path, 'p02')['stages']['blueprint']
    assert stage['existence'] == 'recorded' and stage['applicability']['status'] == 'basis_changed'


def test_direct_edit_supports_recursive_bullets_and_tables(project):
    """Embedded customer_visible refs must resolve in input AND stored plan roots."""
    path, store = project
    before = copy.deepcopy(store.load_document())
    visible = copy.deepcopy(store.read_object_json(before['pages'][1]['page'])['customer_visible'])
    visible['body_blocks'] = [
        {'id': 'paragraph', 'type': 'paragraph', 'text': 'A revised paragraph'},
        {'id': 'list', 'type': 'bullets', 'items': [{'id': 'parent', 'text': 'Parent fact',
          'children': [{'id': 'child', 'text': 'Nested evidence'}]}]},
        {'id': 'table', 'type': 'table', 'columns': [{'id': 'col', 'label': 'Capacity'}],
         'rows': [{'id': 'row', 'cells': [{'column_id': 'col', 'display_text': '42 units'}]}]},
    ]
    commit(path, store, value(store, customer_visible=visible))
    after = store.load_document()
    assert store.read_object_json(after['pages'][1]['page'])['customer_visible'] == visible
    assert after['pages'][0] == before['pages'][0] and after['pages'][2] == before['pages'][2]
    broken = copy.deepcopy(visible)
    del broken['body_blocks'][1]['items'][0]['children'][0]['text']
    with pytest.raises(operations.OperationError):
        content_ops.plan(path, input=value(store, customer_visible=broken))
