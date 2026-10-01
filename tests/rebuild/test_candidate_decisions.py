"""B04: persistent candidate review decisions (keep_current / reopen).

Synthetic mechanism proof on the real Store; no model call, no professional
review claim. Decisions are review activity records: they never move the
candidate, the current artifacts or the call ledger, and they live in
document.candidate_decisions — separate from candidate_adoptions.
"""
import copy
import json
import urllib.request
import uuid

import pytest

from deck_master import candidates, changes, generation, service, tasks, workbench
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


@pytest.fixture
def store(tmp_path):
    project = tmp_path / 'decision-project'
    create_sample(project, page_count=2, readonly=False)
    return Store(project)


def dispatch(store, page='p01', *, layer='svg'):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == page)
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'Improve the spacing.',
             'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
             'targets': [{'page_id': page, 'page_ref': entry['page'], 'layer': layer,
                          'artifact_ref': entry.get(layer)}]}
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    return tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)


def start(store, task):
    return service.task_start(store.project_root, task_id=task['task_id'], execution_ref='synthetic-b04',
                              supported_protocols=['changes.v1', 'generation.v1'],
                              capabilities=['change_plan', 'generation_request_freeze', 'attempt_binding',
                                            'native_tool_observation', 'candidate_result'])


def envelope(store, task, width=20):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == task['scope_pages'][0])
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    staging = store.staging_dir / task['operation_id']; staging.mkdir(parents=True, exist_ok=True)
    (staging / 'page.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}"><rect width="{width}" height="20" fill="#000000"/></svg>')
    return {'kind': task['kind'], 'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
            'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': entry['page_id'],
                                'provenance': {'source_type': 'unknown', 'tool': 'synthetic-b04', 'invocation_ref': None}}]}


def accept(store, task):
    return service.accept_result(store.project_root, **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
                                 result_payload=envelope(store, task))


def candidate(store, page='p01', width=20):
    task = dispatch(store, page); start(store, task)
    result = accept(store, task, )
    return result['candidate_ids'][0], task


def decide(store, candidate_id, decision, *, expected=None, op=None, base_revision=None, project_id=None):
    doc = store.load_document()
    candidates.show(store.project_root, candidate_id=candidate_id)
    response = candidates.decide(store.project_root,
                                 input={'schema_version': 'candidate_decision.v1', 'project_id': project_id or doc['project_id'],
                                        'base_revision': base_revision or doc['revision_id'], 'candidate_id': candidate_id,
                                        'decision': decision, 'expected_decision_ref': expected},
                                 base_revision=base_revision or doc['revision_id'],
                                 operation_id=op or str(uuid.uuid4()))
    # commit_locked 包装层统一解包；unchanged 未提交分支本就是裸结果
    return response['operation_result'] if response['status'] == 'committed' else response


def current_ref(store, candidate_id):
    detail = candidates.show(store.project_root, candidate_id=candidate_id)
    return detail['decision']['decision_ref']


def adoption_plan(store, ids):
    doc = store.load_document()
    return candidates.plan(store.project_root, input={'schema_version': 'candidate_selection.v1', 'project_id': doc['project_id'],
                                                      'base_revision': doc['revision_id'], 'candidate_ids': ids})['plan']


def summary(store):
    return workbench.workbench_summary(store.project_root)['candidates']


def test_keep_current_is_atomic_idempotent_and_never_moves_artifacts(store):
    cid, task = candidate(store)
    before = store.load_document()
    ledger_before = [(t['task_id'], t.get('call_allowances'), t.get('generation_attempts'))
                     for t in (store.read_object_json(r) for r in before['tasks'])]
    result = decide(store, cid, 'keep_current')
    assert result['status'] == 'kept_current' and result['decision'] == 'keep_current'
    ref = result['decision_ref']
    doc = store.load_document()
    assert len(doc['candidate_decisions']) == 1
    record = store.read_object_json(ref)
    assert record['schema_version'] == 'candidate_decision.v1' and record['candidate_id'] == cid
    assert record['decision'] == 'keep_current' and record['revision_id'] == result['revision_id']
    # 决定不改变当前产物、候选与调用账
    assert doc['pages'] == before['pages'] and doc['outputs'] == before['outputs']
    ledger_after = [(t['task_id'], t.get('call_allowances'), t.get('generation_attempts'))
                    for t in (store.read_object_json(r) for r in doc['tasks'])]
    assert ledger_after == ledger_before
    # 同一 operation 幂等重放：逐字节同结果
    op = str(uuid.uuid4())
    first = decide(store, cid, 'keep_current', expected=ref, op=op)
    replay = decide(store, cid, 'keep_current', expected=ref, op=op)
    assert replay == first
    # 新 operation、同向决定 + 正确 expected ref：unchanged，不新增修订
    again = decide(store, cid, 'keep_current', expected=ref)
    assert again['status'] == 'unchanged' and again['decision_ref'] == ref
    # 首次 keep 已落一条；op 重放与同向 unchanged 都不再新增决定记录
    assert len(store.load_document()['candidate_decisions']) == 1


def test_expected_decision_ref_conflict_returns_current_ref_and_recovers(store):
    cid, _task = candidate(store)
    with pytest.raises(OperationError) as stale:
        decide(store, cid, 'keep_current', expected={'path': '.deckmaster/objects/aa/' + '0' * 64 + '.json', 'sha256': '0' * 64})
    payload = stale.value.payload()['error']
    assert stale.value.http_status == 409 and payload['code'] == 'decision_conflict'
    assert payload['current_decision_ref'] is None and payload['candidate_id'] == cid
    # 用当前引用（未决 = null）重试成功
    result = decide(store, cid, 'keep_current', expected=None)
    assert result['status'] == 'kept_current'
    ref = current_ref(store, cid)
    # 第二个并发决定基于旧引用 → 冲突并带当前引用，恢复后成功
    with pytest.raises(OperationError) as conflict:
        decide(store, cid, 'reopen', expected=None)
    assert conflict.value.payload()['error']['current_decision_ref'] == ref
    recovered = decide(store, cid, 'reopen', expected=ref)
    assert recovered['status'] == 'reopened'


def test_decisions_do_not_cross_candidates_or_projects(store):
    first, _ = candidate(store, 'p01', 20)
    second, _ = candidate(store, 'p02', 40)
    decide(store, first, 'keep_current')
    kept_detail = candidates.show(store.project_root, candidate_id=first)
    other_detail = candidates.show(store.project_root, candidate_id=second)
    assert kept_detail['decision']['state'] == 'keep_current' and kept_detail['pending'] is False
    assert other_detail['decision']['state'] is None and other_detail['pending'] is True
    assert summary(store)['pending_count'] == 1
    # 跨项目候选 404：candidate_id 不在本项目记录中
    with pytest.raises(OperationError) as missing:
        decide(store, 'candidate-' + '0' * 32, 'keep_current')
    assert missing.value.http_status == 404
    # project_id 不匹配 → conflict，不落任何记录
    doc = store.load_document()
    before = len(doc.get('candidate_decisions', []))
    with pytest.raises(OperationError):
        decide(store, second, 'keep_current', project_id='other-project')
    assert len(store.load_document().get('candidate_decisions', [])) == before


def test_summary_and_details_match_after_reload_and_in_history(store):
    cid, _task = candidate(store)
    assert summary(store) == {'status': 'recorded', 'count': 1, 'pending_count': 1,
                              'adopted_count': 0, 'kept_count': 0, 'unreadable_count': 0}
    keep = decide(store, cid, 'keep_current')
    keep_revision = keep['revision_id']
    # 刷新（新 Store 实例）后 summary 与详情吻合
    fresh = Store(store.project_root)
    block = workbench.workbench_summary(fresh.project_root)['candidates']
    assert block['pending_count'] == 0 and block['kept_count'] == 1 and block['adopted_count'] == 0
    detail = candidates.show(fresh.project_root, candidate_id=cid)
    assert detail['decision']['state'] == 'keep_current' and detail['pending'] is False
    block = workbench.workbench_summary(fresh.project_root)['next_actions']
    actions = block.get('actions', []) if isinstance(block, dict) else block
    assert all(item['kind'] != 'compare_candidates' for item in actions)
    # reopen 恢复待决；决定历史保留可读
    reopen = decide(fresh, cid, 'reopen', expected=keep['decision_ref'])
    block = workbench.workbench_summary(fresh.project_root)['candidates']
    assert block['pending_count'] == 1 and block['kept_count'] == 0
    assert candidates.show(fresh.project_root, candidate_id=cid)['pending'] is True
    # 历史 revision 各自可读其当时决定
    past = candidates.listing(fresh.project_root, revision=keep_revision)['candidates'][0]
    assert past['decision']['state'] == 'keep_current' and past['pending'] is False
    now = candidates.listing(fresh.project_root)['candidates'][0]
    assert now['decision']['state'] == 'reopen' and now['pending'] is True


def test_adopted_candidate_stays_adopted_and_refuses_decisions(store):
    cid, _task = candidate(store)
    plan_value = adoption_plan(store, [cid])
    candidates.adopt(store.project_root, input=plan_value, base_revision=plan_value['base_revision'], operation_id=str(uuid.uuid4()))
    detail = candidates.show(store.project_root, candidate_id=cid)
    assert detail['status'] == 'adopted' and detail['pending'] is False and detail['decision']['state'] is None
    assert summary(store)['adopted_count'] == 1 and summary(store)['kept_count'] == 0
    # 曾采用不被决定顶替：keep/reopen 都拒绝
    for decision in ('keep_current', 'reopen'):
        with pytest.raises(OperationError) as refused:
            decide(store, cid, decision)
        assert refused.value.payload()['error']['code'] == 'candidate_adopted'
        assert refused.value.http_status == 409


def test_reopen_requires_new_adoption_plan_and_old_plan_still_blocked(store):
    cid, _task = candidate(store)
    old_plan = adoption_plan(store, [cid])
    keep = decide(store, cid, 'keep_current')
    # 基准变更（管理修订）后旧 plan 依然被拒，决定不绕过
    doc = store.load_document(); updated = bump_revision(copy.deepcopy(doc),
        {'operation_id': 'b04-management', 'kind': 'task_update', 'description': 'synthetic management bump', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='b04-management')
    with pytest.raises(OperationError):
        candidates.adopt(store.project_root, input=old_plan, base_revision=old_plan['base_revision'], operation_id=str(uuid.uuid4()))
    # reopen 后采用仍需全新 plan（决定不恢复旧 plan 效力）
    decide(store, cid, 'reopen', expected=keep['decision_ref'])
    fresh_plan = adoption_plan(store, [cid])
    assert fresh_plan['base_revision'] == store.load_document()['revision_id']
    adopted = candidates.adopt(store.project_root, input=fresh_plan, base_revision=fresh_plan['base_revision'], operation_id=str(uuid.uuid4()))
    assert adopted['operation_result']['status'] == 'adopted'
    assert candidates.show(store.project_root, candidate_id=cid)['status'] == 'adopted'


def test_committed_operation_replays_and_payload_conflict_detected(store):
    cid, _task = candidate(store)
    op = str(uuid.uuid4())
    doc = store.load_document()
    original_base = doc['revision_id']
    first = decide(store, cid, 'keep_current', op=op)
    assert first['status'] == 'kept_current'
    before = len(store.load_document()['candidate_decisions'])
    # 已提交 operation 按原始 payload 原样重放：recover 返回原提交结果，不新增决定记录
    replay = candidates.decide(store.project_root,
                               input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                      'base_revision': original_base, 'candidate_id': cid,
                                      'decision': 'keep_current', 'expected_decision_ref': None},
                               base_revision=original_base, operation_id=op)
    assert replay['status'] == 'committed' and replay['operation_result'] == first
    assert len(store.load_document()['candidate_decisions']) == before
    # 同 operation 换 payload → 可恢复冲突，不产生第二事务
    from deck_master.operations import OperationError
    with pytest.raises(OperationError) as conflict:
        candidates.decide(store.project_root,
                          input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                 'base_revision': original_base, 'candidate_id': cid,
                                 'decision': 'reopen', 'expected_decision_ref': None},
                          base_revision=original_base, operation_id=op)
    assert conflict.value.exit_code == 5 and conflict.value.payload()['error']['code'] == 'operation_payload_conflict'
    assert len(store.load_document()['candidate_decisions']) == before


def test_damaged_decision_ref_is_visible_and_never_blocks_adoption(store):
    cid, _task = candidate(store)
    keep = decide(store, cid, 'keep_current')
    doc = store.load_document()
    # 注入损伤：决定引用指向缺失对象（模拟外部损坏）
    broken = {'path': '.deckmaster/objects/dd/' + '0' * 62 + 'ff.json', 'sha256': 'd' * 64}
    updated = {**doc, 'candidate_decisions': [broken]}
    from deck_master.models import bump_revision
    bumped = bump_revision({**updated, 'revision_id': doc['revision_id']},
                           {'operation_id': 'damage-sim', 'kind': 'task_update', 'description': 'synthetic damage', 'read_set': []})
    store.commit_change(base_revision=doc['revision_id'], document=bumped, operation_id='damage-sim')
    # show 如实投影 unreadable 且按待决
    detail = candidates.show(store.project_root, candidate_id=cid)
    assert detail['decision']['state'] == 'unreadable' and detail['pending'] is True
    # 采用规划不被辅助元数据阻断
    plan_value = adoption_plan(store, [cid])
    adopted = candidates.adopt(store.project_root, input=plan_value, base_revision=plan_value['base_revision'], operation_id=str(uuid.uuid4()))
    assert adopted['operation_result']['status'] == 'adopted'
    # workbench 隔离：候选回到待决且 kept_count=0
    assert summary(store)['kept_count'] == 0 and summary(store)['pending_count'] == 0  # adopted 后
    assert summary(store)['adopted_count'] == 1


def test_non_enum_decision_value_is_isolated_not_trusted(store, monkeypatch):
    import json as json_module
    from pathlib import Path
    cid, _task = candidate(store)
    decide(store, cid, 'keep_current')
    doc = store.load_document()
    ref = doc['candidate_decisions'][0]
    record_path = store.project_root / ref['path']
    record = json_module.loads(record_path.read_text())
    record['decision'] = 'banana'
    record_path.write_text(json_module.dumps(record, ensure_ascii=False, indent=1) + '\n')
    # 非枚举决定值：workbench 不当作 kept，也不当可读决定
    block = summary(store)
    assert block['kept_count'] == 0 and block['pending_count'] == 1


def test_historical_base_revision_and_unknown_decision_rejected(store):
    cid, _task = candidate(store)
    old_revision = store.load_document()['revision_id']
    decide(store, cid, 'keep_current')
    with pytest.raises(OperationError) as historical:
        decide(store, cid, 'reopen', expected=current_ref(store, cid), base_revision=old_revision)
    assert historical.value.exit_code == 5
    with pytest.raises(OperationError) as invalid:
        candidates.decide(store.project_root,
                          input={'schema_version': 'candidate_decision.v1', 'project_id': store.load_document()['project_id'],
                                 'base_revision': store.load_document()['revision_id'], 'candidate_id': cid,
                                 'decision': 'discard', 'expected_decision_ref': None},
                          base_revision=store.load_document()['revision_id'], operation_id=str(uuid.uuid4()))
    assert invalid.value.payload()['error']['field'] == 'input/decision'


def test_readonly_sample_http_refuses_decision_writes(tmp_path):
    project = tmp_path / 'readonly-project'
    create_sample(project, page_count=1, readonly=True)
    server = WorkbenchServer(project)
    url = server.start()
    try:
        token = json.load(urllib.request.urlopen(url.rstrip('/') + '/api/session'))['token']
        request = urllib.request.Request(
            url.rstrip('/') + '/api/candidates/decision',
            data=json.dumps({'input': {'schema_version': 'candidate_decision.v1', 'project_id': 'x',
                                       'base_revision': 'x', 'candidate_id': 'c', 'decision': 'keep_current',
                                       'expected_decision_ref': None},
                             'base_revision': 'x', 'operation_id': str(uuid.uuid4())}).encode(),
            headers={'Origin': url.rstrip('/'), 'X-Deck-Token': token, 'Content-Type': 'application/json'})
        try:
            urllib.request.urlopen(request)
            raise AssertionError('readonly sample must refuse decision writes')
        except urllib.error.HTTPError as error:
            assert error.code == 403
            assert json.load(error)['error']['code'] == 'sample_readonly'
    finally:
        server.stop()


def test_client_action_kind_matches_server_digest_kind():
    from pathlib import Path
    """A06 评审 P1 回归：business.submit 的 action 字符串必须与服务端 decide 的
    request_digest kind 完全一致，否则收据核对链路断裂（待核实死循环）。"""
    module = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2/business-operations.js'
    source = module.read_text(encoding='utf-8')
    assert "'candidates.decide': '/api/candidates/decision'" in source
    # 旧名只允许作为 LEGACY_ACTIONS 兼容映射的键（现居于生产 receipt-verdict.js），
    # 不得出现在端点表或任何 submit 调用点
    paths_line = next(line for line in source.splitlines() if line.startswith('const paths'))
    assert 'candidates.decision' not in paths_line
    verdict_src = (Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2/receipt-verdict.js').read_text(encoding='utf-8')
    assert "LEGACY_ACTIONS = {'candidates.decision': 'candidates.decide'}" in verdict_src
    # 终审 P2-2 锚定：accept() 必须调用生产 receiptTerminal（含 unchanged 终态）——
    # 若退回内联只认 committed 的判定，本断言失败
    assert 'receiptTerminal' in source
    import inspect
    assert 'candidates.decide' in inspect.getsource(candidates.decide)


def test_unchanged_is_a_verifiable_terminal_envelope(store):
    """终审补丁 P1：同向 unchanged 必须携带与请求一致的 operation 身份与摘要，
    且不新增决定记录——前端据此做完整身份校验后清除收据，不落入待核实循环。"""
    cid, _task = candidate(store)
    keep = decide(store, cid, 'keep_current')
    before = len(store.load_document()['candidate_decisions'])
    doc = store.load_document()
    op = str(uuid.uuid4())
    unchanged = candidates.decide(store.project_root,
                                  input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                         'base_revision': doc['revision_id'], 'candidate_id': cid,
                                         'decision': 'keep_current', 'expected_decision_ref': keep['decision_ref']},
                                  base_revision=doc['revision_id'], operation_id=op)
    assert unchanged['status'] == 'unchanged'
    assert unchanged['operation_id'] == op
    assert unchanged['request_digest'] and unchanged['request_digest'] == unchanged['request_digest']
    assert unchanged['current_revision_id'] == doc['revision_id']
    assert len(store.load_document()['candidate_decisions']) == before
    # 同向 reopen 预检后（expected=当前决定）的 unchanged 同样是终态
    reopened = decide(store, cid, 'reopen', expected=keep['decision_ref'])
    again = candidates.decide(store.project_root,
                              input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                     'base_revision': store.load_document()['revision_id'], 'candidate_id': cid,
                                     'decision': 'reopen', 'expected_decision_ref': reopened['decision_ref']},
                              base_revision=store.load_document()['revision_id'], operation_id=str(uuid.uuid4()))
    assert again['status'] == 'unchanged' and again['operation_id']
