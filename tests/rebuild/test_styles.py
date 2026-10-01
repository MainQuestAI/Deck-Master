"""Style safety over real services; synthetic image events do not prove visual quality."""
import copy
import json
import uuid
from pathlib import Path
import importlib.util

import pytest

from deck_master import changes, generation, service, styles, tasks
from deck_master.models import bump_revision, content_identity
from deck_master.operations import OperationError

spec = importlib.util.spec_from_file_location('w08_synthetic_base', Path(__file__).resolve().parents[2] / 'examples/workbench/w07_synthetic.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)


class Flow(base.SyntheticW07):
    def start(self, task):
        return service.task_start(self.project, task_id=task['task_id'], execution_ref=base.EXECUTION,
                                  supported_protocols=['generation.v1', 'changes.v1'], capabilities=task['required_capabilities'])


@pytest.fixture
def flow(tmp_path):
    return Flow(tmp_path)


def value(flow, **extra):
    doc = flow.store.load_document()
    return {'schema_version': 'style_input.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
            'reference': {'page_id': 'p01', 'revision_id': doc['revision_id'], 'artifact_ref': doc['pages'][0]['blueprint'], 'role': 'reference'},
            'target_page_ids': ['p02', 'p03'], 'instruction': '借用配色与文字层级，保留目标内容', **extra}


def confirm(flow, data=None):
    proposed = styles.propose(flow.project, input=data or value(flow))
    return styles.confirm(flow.project, proposal_id=proposed['proposal_id'], base_revision=flow.store.current_revision_id(),
                          operation_id=str(uuid.uuid4()))['operation_result']


def dispatch(flow, recipe, pages=None, adopted=None):
    payload = {'recipe_id': recipe['recipe_id'], 'page_ids': pages or ['p02'], 'max_calls': len(pages or ['p02'])}
    if adopted:
        payload['adopted_candidate_id'] = adopted
    plan = styles.plan(flow.project, input=payload)
    result = changes.commit(flow.project, plan_id=plan['plan_id'], base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    return flow.task(result['operation_result']['task_ids'][0])


def mutate(flow, pid, field='content'):
    store = flow.store; doc = store.load_document(); updated = copy.deepcopy(doc); entry = next(e for e in updated['pages'] if e['page_id'] == pid)
    if field == 'content':
        page = store.read_object_json(entry['page']); page['customer_visible']['title'] += ' NEW 987'; entry['page'] = store.put_json_object(page)
    elif field == 'density':
        page = store.read_object_json(entry['page']); page['visual_spec']['intent'] = '高密度事实表'; entry['page'] = store.put_json_object(page)
    else:
        artifact = store.read_object_json(entry['blueprint']); artifact['provenance']['tool'] = 'synthetic-concurrent-update'; entry['blueprint'] = store.put_json_object(artifact)
    updated = bump_revision(updated, {'operation_id': 'test-' + uuid.uuid4().hex, 'kind': 'task_update', 'description': 'Explicit synthetic mutation', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id=updated['change']['operation_id'])


def test_proposal_and_confirmation_preserve_pages_and_do_not_dispatch(flow):
    before = flow.store.load_document(); proposal = styles.propose(flow.project, input=value(flow, host_suggestion='建议使用绿色；需用户确认'))
    assert flow.store.load_document() == before
    assert proposal['proposal']['suggestion_state'] == 'unconfirmed'
    assert proposal['proposal']['reference_sources']['submitted']['state'] == 'not_recorded'
    assert set(proposal['proposal']['dimensions']) == {'palette', 'typography'}
    op = str(uuid.uuid4()); result = styles.confirm(flow.project, proposal_id=proposal['proposal_id'], base_revision=before['revision_id'], operation_id=op)
    after = flow.store.load_document()
    assert before['pages'] == after['pages'] and before['tasks'] == after['tasks'] and content_identity(before) == content_identity(after)
    assert after['compatibility']['minimum_writer'] == 'style-recipes.v1'
    recipe = styles.show(flow.project, recipe_id=result['operation_result']['recipe_id'])['recipe']
    assert recipe['suggestion_state'] == 'confirmed'
    mutate(flow, 'p03')
    replay = styles.confirm(flow.project, proposal_id=proposal['proposal_id'], base_revision=before['revision_id'], operation_id=op)
    assert replay['operation_result'] == result['operation_result']


def test_recipe_revision_has_diff_and_does_not_mutate_old_fixed_input(flow):
    first = confirm(flow); old = styles.show(flow.project, recipe_id=first['recipe_id'])['recipe']
    task = dispatch(flow, first); original = generation.prepared_input(flow.store, flow.store.load_document(), task)
    second = confirm(flow, value(flow, parent_recipe_id=first['recipe_id'], dimensions={'palette': 'new orange'}))
    new = styles.show(flow.project, recipe_id=second['recipe_id'])['recipe']
    assert new['version'] == 2 and new['parent_ref'] == first['recipe_ref']
    assert any(row['field'] == 'dimensions' for row in new['diff'])
    assert styles.show(flow.project, recipe_id=first['recipe_id'])['recipe'] == old
    assert generation.prepared_input(flow.store, flow.store.load_document(), task) == original
    flow.start(task)
    bad = copy.deepcopy(original); bad['style_recipe_ref'] = second['recipe_ref']
    with pytest.raises(generation.GenerationError): generation.freeze(flow.project, task_id=task['task_id'], input=bad, base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    frozen = generation.freeze(flow.project, task_id=task['task_id'], input=original, base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert frozen['input']['style_recipe_ref'] == first['recipe_ref']
    assert flow.store.load_document()['compatibility']['minimum_writer'] == 'style-recipes.v1'


def test_conflicting_density_requires_explicit_new_proposal(flow):
    mutate(flow, 'p02', 'density'); data = value(flow, instruction='极简留白')
    proposed = styles.propose(flow.project, input=data); assert proposed['proposal']['conflicts'][0]['page_id'] == 'p02'
    before = flow.store.read_current()
    with pytest.raises(styles.StyleConflict) as failure:
        styles.confirm(flow.project, proposal_id=proposed['proposal_id'], base_revision=data['base_revision'], operation_id=str(uuid.uuid4()))
    assert failure.value.payload()['error']['items'][0]['resolution'] is None and flow.store.read_current() == before
    data['resolutions'] = {'p02:density': 'keep_target'}; recipe = confirm(flow, data); task = dispatch(flow, recipe)
    assert '保留目标页密度约束' in generation.prepared_input(flow.store, flow.store.load_document(), task)['prompt']


def test_first_trial_then_adoption_then_explicit_expansion(flow):
    original = copy.deepcopy(flow.store.load_document()['pages']); recipe = confirm(flow)
    with pytest.raises(OperationError, match='exactly one'): dispatch(flow, recipe, ['p02', 'p03'])
    task = dispatch(flow, recipe); candidate = flow.image(task)['candidate_ids'][0]
    assert flow.store.load_document()['pages'] == original
    with pytest.raises(OperationError, match='currently adopted'): dispatch(flow, recipe, ['p03'], candidate)
    flow.adopt([candidate]); after_first = copy.deepcopy(flow.store.load_document()['pages'])
    next_task = dispatch(flow, recipe, ['p03'], candidate)
    second = flow.image(next_task, 2)['candidate_ids'][0]; flow.adopt([second]); end = flow.store.load_document()
    assert end['pages'][0] == original[0] and end['pages'][1] == after_first[1]
    assert [e['page'] for e in end['pages']] == [e['page'] for e in original]
    assert end['pages'][2]['blueprint'] != original[2]['blueprint'] and end['pages'][2]['svg'] is None
    for t in (task, next_task):
        current = flow.task(t['task_id']); assert len(current['call_allowances']) == 1 and current['call_allowances'][0]['state'] == 'consumed'
    assert end['compatibility']['minimum_writer'] == 'style-recipes.v1'


@pytest.mark.parametrize('field', ['content', 'blueprint'])
def test_changed_expansion_target_is_reported_individually_without_writes(flow, field):
    recipe = confirm(flow); cid = flow.image(dispatch(flow, recipe))['candidate_ids'][0]; flow.adopt([cid])
    mutate(flow, 'p03', field); before = flow.store.load_document()
    with pytest.raises(styles.StyleConflict) as error: dispatch(flow, recipe, ['p03'], cid)
    assert [x['page_id'] for x in error.value.items] == ['p03'] and flow.store.load_document() == before


def test_unselected_or_reference_page_and_other_recipe_cannot_expand(flow):
    recipe = confirm(flow, value(flow, target_page_ids=['p02']))
    with pytest.raises(OperationError, match='not explicitly'): dispatch(flow, recipe, ['p01'])
    with pytest.raises(OperationError, match='not explicitly'): dispatch(flow, recipe, ['p03'])
    cid = flow.image(dispatch(flow, recipe))['candidate_ids'][0]; flow.adopt([cid]); other = confirm(flow)
    with pytest.raises(OperationError, match='exact recipe'): dispatch(flow, other, ['p03'], cid)


def test_fixed_reference_survives_reference_page_update_and_freeze_rejects_tampering(flow):
    recipe = confirm(flow); old = styles.show(flow.project, recipe_id=recipe['recipe_id'])['recipe']['input']['reference']
    mutate(flow, 'p01', 'blueprint'); task = dispatch(flow, recipe); prepared = generation.prepared_input(flow.store, flow.store.load_document(), task)
    assert prepared['references'][0]['file'] == flow.store.read_object_json(old['artifact_ref'])['file']
    flow.start(task)
    for field, value_ in [('constraints', {}), ('prompt', 'copy the reference facts'), ('references', [])]:
        bad = copy.deepcopy(prepared); bad[field] = value_
        with pytest.raises(generation.GenerationError): generation.freeze(flow.project, task_id=task['task_id'], input=bad, base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert not flow.task(task['task_id'])['generation_requests']


def test_old_host_claim_and_cancelled_late_result_are_rejected(flow):
    recipe = confirm(flow); task = dispatch(flow, recipe)
    with pytest.raises(generation.GenerationError): base.SyntheticW07.start(flow, task)
    assert flow.task(task['task_id'])['status'] == 'awaiting_host'
    flow.start(task); prepared = generation.prepared_input(flow.store, flow.store.load_document(), task)
    service.task_cancel(flow.project, task_id=task['task_id'], reason='synthetic cancellation')
    before = flow.store.load_document()
    with pytest.raises(generation.GenerationError): generation.freeze(flow.project, task_id=task['task_id'], input=prepared, base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4()))
    assert flow.store.load_document() == before


def test_schema_mirrors_and_cli_typed_errors(flow, capsys):
    from deck_master.cli import main
    root = Path(__file__).resolve().parents[2]
    for file in (root / 'src/deck_master/resources/contracts').glob('*.schema.json'):
        mirrors = list((root / 'docs/specs').glob('*/contracts/' + file.name))
        assert len(mirrors) == 1, file.name
        assert file.read_bytes() == mirrors[0].read_bytes()
    assert main(['styles', 'list', '--project', str(flow.project)]) == 0
    assert json.loads(capsys.readouterr().out)['recipes'] == []
    assert main(['styles', 'show', '--project', str(flow.project), '--recipe-id', 'missing']) == 2
    assert json.loads(capsys.readouterr().err)['error']['code'] == 'style_invalid'


def test_exact_prompt_excerpt_is_verified_and_never_relabels_prepared_as_actual(flow):
    from deck_master.models import sha256_bytes
    from deck_master.workbench import page_lineage
    original_task = flow.dispatch('p01', reference_page='p02'); flow.image(original_task)
    line = page_lineage(flow.project, 'p01')
    source = line['text_sources']['prepared_prompt'][0]
    text = source['text']; excerpt = text[:20]
    selection = {'schema_version': 'text_range.v1', 'ref': source['ref'], 'locator': source['locator'], 'text_sha256': sha256_bytes(text.encode()),
                 'start': 0, 'end': len(excerpt), 'excerpt': excerpt}
    # Schema owns the exact selection shape; this is a recorded code-point span.
    data = value(flow, prompt_selection={'layer': 'prepared_prompt', 'selection': selection})
    proposed = styles.propose(flow.project, input=data)
    assert proposed['proposal']['input']['prompt_selection']['selection']['excerpt'] == excerpt
    data['prompt_selection']['selection']['excerpt'] = 'invented actual prompt'
    with pytest.raises(OperationError): styles.propose(flow.project, input=data)


def test_http_fixed_recipe_reads_and_origin_token_boundaries(flow):
    from http.client import HTTPConnection
    from urllib.parse import urlsplit
    from deck_master.web import WorkbenchServer
    server = WorkbenchServer(flow.project)
    try:
        url = server.start(); parsed = urlsplit(url)
        def request(path, data=None, headers=None):
            conn = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
            try:
                conn.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, headers or {})
                response = conn.getresponse(); return response.status, json.loads(response.read())
            finally: conn.close()
        token = request('/api/session')[1]['token']; auth = {'Origin': url.rstrip('/'), 'X-Deck-Token': token}
        data = {'input': value(flow)}; pointer = flow.store.read_current()
        assert request('/api/styles/propose', data)[0] == 403
        assert request('/api/styles/propose', data, {**auth, 'Origin': 'https://foreign.example'})[0] == 403
        assert request('/api/styles/propose', data, {**auth, 'X-Deck-Token': 'wrong'})[0] == 403
        assert flow.store.read_current() == pointer
        code, proposed = request('/api/styles/propose', data, auth); assert code == 200
        confirm_input = {'proposal_id': proposed['proposal_id'], 'base_revision': data['input']['base_revision'], 'operation_id': str(uuid.uuid4())}
        code, confirmed = request('/api/styles/confirm', confirm_input, auth); assert code == 200
        rev = confirmed['operation_result']['revision_id']; recipe_id = confirmed['operation_result']['recipe_id']
        assert request('/api/styles/' + recipe_id + '?revision=' + rev)[1]['recipe']['recipe_id'] == recipe_id
        assert request('/api/styles?revision=missing')[0] == 503
        assert request('/api/styles?unexpected=1')[0] == 422
        before = flow.store.read_current()
        code, error = request('/api/styles/plan', {'input': {'recipe_id': recipe_id, 'page_ids': ['p02','p03'], 'max_calls': 2}}, auth)
        assert code == 422 and error['error']['code'] == 'style_invalid' and flow.store.read_current() == before
    finally: server.stop()


def test_confirm_after_pointer_receipt_loss_recovers_without_duplicate_recipe(flow, monkeypatch):
    from deck_master import operations
    data = value(flow); proposed = styles.propose(flow.project, input=data); op = str(uuid.uuid4())
    monkeypatch.setattr(operations, 'publish_index', lambda *args: {'code': 'injected_cache_loss'})
    first = styles.confirm(flow.project, proposal_id=proposed['proposal_id'], base_revision=data['base_revision'], operation_id=op)
    mutate(flow, 'p03')
    second = styles.confirm(flow.project, proposal_id=proposed['proposal_id'], base_revision=data['base_revision'], operation_id=op)
    assert first['operation_result'] == second['operation_result'] and len(flow.store.load_document()['style_recipes']) == 1


def test_b06_preserve_dimensions_projected_scoped_and_in_instruction(flow):
    """B06-AC01: 未选维度成为显式保持项并进入 instruction；维度键限定已知集合。"""
    data = value(flow)
    proposed = styles.propose(flow.project, input=data)
    proposal = proposed['proposal']
    # 默认选 palette+typography → 未选 density/lines/composition 成为保持项
    assert proposal['preserve_dimensions'] == {'density': '密度', 'lines': '线条', 'composition': '构图'}
    assert proposal['dimensions'] == {'palette': '借用参考页配色', 'typography': '借用参考页文字层级'}
    # 未知维度键拒绝（范围校验）
    with pytest.raises(OperationError) as unknown:
        styles.propose(flow.project, input=value(flow, dimensions={'palette': '配色', 'texture': '质感'}))
    assert 'texture' in unknown.value.payload()['error']['message']
    # 选满五维 → preserve 为空
    full = styles.propose(flow.project, input=value(flow, dimensions={k: DIMENSION_TEXT[k] for k in styles.DIMENSIONS}))
    assert full['proposal']['preserve_dimensions'] == {}
    # 确认后 recipe 携带保持项且 instruction 显式列出
    confirmed = confirm(flow, data)
    recipe_id = confirmed['recipe_id']
    saved = styles.show(flow.project, recipe_id=recipe_id)
    assert saved['recipe']['preserve_dimensions'] == {'density': '密度', 'lines': '线条', 'composition': '构图'}
    text = styles.instruction(saved['recipe'], '*')
    assert '明确保持维度' in text and 'density' in text and '沿用目标页' in text
    # 显式借用维度不受影响
    assert '明确借用维度' in text


DIMENSION_TEXT = {'palette': '借用参考页配色', 'typography': '借用参考页文字层级',
                  'density': '借用参考页密度', 'lines': '借用参考页线条', 'composition': '借用参考页构图'}


def test_b06_diff_tracks_preserve_and_legacy_proposal_confirms(flow):
    """B06 终审 P3：diff 记录未选维度集合变化；旧核心无 preserve 键的 proposal 可确认。"""
    first = confirm(flow)  # version 1: palette+typography → preserve density/lines/composition
    recipe_one = styles.show(flow.project, recipe_id=first['recipe_id'])['recipe']
    # 子提案改选 palette+composition → preserve 集合变化应出现在 diff
    child = value(flow, parent_recipe_id=recipe_one['recipe_id'],
                  dimensions={'palette': '配色', 'composition': '构图'})
    proposed = styles.propose(flow.project, input=child)['proposal']
    fields = [entry['field'] for entry in proposed['diff']]
    assert 'preserve_dimensions' in fields
    entry = next(e for e in proposed['diff'] if e['field'] == 'preserve_dimensions')
    assert entry['before'] == {'density': '密度', 'lines': '线条', 'composition': '构图'}
    assert entry['after'] == {'typography': '文字层级', 'density': '密度', 'lines': '线条'}
    # 旧核心兼容：手工剥掉 preserve_dimensions 的 proposal 仍可确认（按重推导补齐比较）
    legacy = {k: v for k, v in proposed.items() if k != 'preserve_dimensions'}
    from deck_master.store import Store as _Store
    ref = _Store(flow.project).put_json_object(legacy)
    confirmed = styles.confirm(flow.project, proposal_id='style-proposal-' + ref['sha256'],
                               base_revision=_Store(flow.project).current_revision_id(),
                               operation_id=str(uuid.uuid4()))['operation_result']
    assert confirmed['status'] == 'confirmed'


def test_b06_real_legacy_proposal_shapes_confirm_and_tampering_refused(flow):
    """终审补丁 P2：真实旧形态 proposal（diff 无 preserve 条目／顶层缺键）可确认；
    篡改业务字段的 proposal 仍被拒绝。旧形态按旧 diff 算法输出构造（等价于在
    新推导结果上剥离派生 preserve 条目/顶层键）。"""
    from deck_master.store import Store as _Store

    def fresh_proposal():
        return styles.propose(flow.project, input=value(flow))['proposal']

    def confirm_raw(proposal_object):
        ref = _Store(flow.project).put_json_object(proposal_object)
        return styles.confirm(flow.project, proposal_id='style-proposal-' + ref['sha256'],
                              base_revision=proposal_object['base_revision'],
                              operation_id=str(uuid.uuid4()))['operation_result']

    # 形态一：diff 无 preserve 条目（B06 初版 diff 算法输出）；confirm 会推进基准，
    # 故每个形态用各自新鲜 propose 的当前基准。
    shape_one = fresh_proposal()
    legacy_diff = {**shape_one, 'diff': [item for item in shape_one['diff'] if item.get('field') != 'preserve_dimensions']}
    assert confirm_raw(legacy_diff)['status'] == 'confirmed'
    # 形态二：顶层缺 preserve_dimensions 键（B06 之前的核心产物）
    shape_two = fresh_proposal()
    legacy_nokey = {k: v for k, v in shape_two.items() if k != 'preserve_dimensions'}
    legacy_nokey = {**legacy_nokey, 'diff': [item for item in legacy_nokey['diff'] if item.get('field') != 'preserve_dimensions']}
    assert confirm_raw(legacy_nokey)['status'] == 'confirmed'
    # 篡改业务字段（instruction）的 proposal 必须被拒绝
    shape_three = fresh_proposal()
    tampered = {**shape_three, 'input': {**shape_three['input'], 'instruction': '篡改后的要求'}}
    with pytest.raises(OperationError) as refused:
        confirm_raw(tampered)
    assert 'suggestion changed' in refused.value.payload()['error']['message']
