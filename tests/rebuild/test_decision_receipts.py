"""终审补丁 P1/P2 回归：前端收据核对链路的 node 侧语义。

business-operations.js 的 expectedRequestDigest/accept 无法在 jsdom 之外直接
执行（依赖 fetch/DOM）——这里用 node 执行其源码的纯逻辑片段：legacy action
映射、规范 kind 摘要重算（与 api.js wireCanonical 同一序列化器）、unchanged
终态判定，对齐服务端 candidates.decide 的 request_digest（Python 侧同 payload
逐字节比对）。
"""
import json
import shutil
import sys
import subprocess
import uuid
from pathlib import Path

import pytest

from deck_master import candidates, operations, samples
from deck_master.models import canonical_json_bytes, sha256_bytes
from deck_master.store import Store

V2 = Path(__file__).resolve().parents[2] / 'src/deck_master/resources/static/v2'

# 直接导入生产收据实现（receipt-verdict.js 为零 DOM 依赖纯函数模块，
# business-operations.js 与本测试共用同一终态判定/摘要重算——终审补丁 P2：
# 回归测试不得维护仅存在于测试中的判定副本）。
RECEIPT = (V2 / 'receipt-verdict.js').as_uri()

SNIPPET = (
    'import {canonicalAction, expectedRequestDigest, receiptTerminal} from ' + json.dumps(RECEIPT) + ';\n'
    'const result = await (async () => { ${body} })();\n'
    'console.log(JSON.stringify(result));')


def run_node(body: str) -> dict:
    import os
    node = shutil.which('node')
    assert node, 'node required'
    script = SNIPPET.replace('${body}', body)
    result = subprocess.run([node, '--input-type=module', '-e', script],
                            capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        detail = 'node failed rc=' + str(result.returncode) + '; stderr: ' + result.stderr[:600]
        raise AssertionError(detail)
    return json.loads(result.stdout)


def test_legacy_decision_pending_recovers_with_reekind_digest(tmp_path):
    """P2：升级前 candidates.decision pending（旧 kind 摘要）经兼容规则重算后，
    与服务端规范 kind 的 digest 匹配 → 收据核对不再静默跳过。"""
    project = tmp_path / 'legacy-pending'
    samples.create_sample(project, page_count=1, readonly=False)
    store = Store(project)
    doc = store.load_document()
    # 服务端：先产生一个真实 keep 决定（规范 kind 的 digest 可从提交信封取得）
    entry = doc['pages'][0]
    from deck_master import changes, service, tasks
    intent = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
              'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'legacy pending test.',
              'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
              'targets': [{'page_id': entry['page_id'], 'page_ref': entry['page'], 'layer': 'svg',
                           'artifact_ref': entry.get('svg')}]}
    plan = changes.plan(project, input=intent)
    result = changes.commit(project, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    task = tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)
    service.task_start(project, task_id=task['task_id'], execution_ref='legacy-test',
                       supported_protocols=['changes.v1'], capabilities=['change_plan', 'candidate_result'])
    doc = store.load_document()
    task = tasks._lookup_task(doc, task['task_id'], store)
    staging = store.staging_dir / task['operation_id']
    staging.mkdir(parents=True, exist_ok=True)
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    (staging / 'page.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}"><rect width="10" height="10"/></svg>')
    accept = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                                   produced_against=task['produced_against'],
                                   result_payload={'kind': task['kind'],
                                                   'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
                                                   'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': entry['page_id'],
                                                                       'provenance': {'source_type': 'unknown', 'tool': 'legacy-test',
                                                                                      'invocation_ref': None}}]})
    candidate_id = accept['candidate_ids'][0]
    op = str(uuid.uuid4())
    decision_basis = store.load_document()['revision_id']
    committed = candidates.decide(project, input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                                  'base_revision': decision_basis,
                                                  'candidate_id': candidate_id, 'decision': 'keep_current',
                                                  'expected_decision_ref': None},
                                  base_revision=decision_basis, operation_id=op)
    committed = committed['operation_result'] if committed['status'] == 'committed' else committed
    # 前端视角：升级前的 pending（旧 action 名 + 旧 kind 摘要）。请求冻结的是
    # 决定时的基准（提交前修订），与服务端 digest 的 base_revision 同源。
    pending_payload = {'action': 'candidates.decision',
                       'request': {'input': {'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                             'base_revision': decision_basis, 'candidate_id': candidate_id,
                                             'decision': 'keep_current', 'expected_decision_ref': None},
                                   'base_revision': decision_basis, 'operation_id': op}}
    # 旧 kind 摘要（升级前由前端计算并冻结）
    legacy_kind_digest = sha256_bytes(canonical_json_bytes(
        {'protocol': 'changes.v1', 'kind': 'candidates.decision', 'project_id': doc['project_id'],
         'base_revision': decision_basis, 'payload': pending_payload['request']['input']}))
    # 服务端 unchanged 重放（新 operation 重放 committed？不行——重放用原 op 才得 committed。
    # 这里验证：operations show 返回的 request_digest（服务端规范 kind）经前端重算一致）
    shown = operations.show(project, operation_id=op)
    verdict = run_node(
        'const entry = {pending: {payload: ' + json.dumps(pending_payload) + ', operation_id: ' + json.dumps(op) + '}};'
        'const response = {status: "committed", operation_id: ' + json.dumps(op) + ','
        ' request_digest: ' + json.dumps(shown['request_digest']) + ','
        ' operation_result: {revision_id: ' + json.dumps(committed['revision_id']) + '}};'
        'const expected = await expectedRequestDigest(entry.pending.payload, ' + json.dumps(doc['project_id']) + ');'
        'const terminal = await receiptTerminal(entry, response, ' + json.dumps(doc['project_id']) + ');'
        'return {terminal, expected};')
    assert verdict['terminal'] is True and verdict['expected'] == shown['request_digest'], verdict
    # 旧 kind 摘要与规范 kind 摘要不同（证明必须重算，不能直接比对冻结值）
    assert shown['request_digest'] != legacy_kind_digest


def test_unchanged_response_is_terminal_for_client(tmp_path):
    """P1：unchanged 终态信封通过前端判定（身份+摘要一致），不再进待核实。"""
    project = tmp_path / 'unchanged-terminal'
    samples.create_sample(project, page_count=1, readonly=False)
    store = Store(project)
    doc = store.load_document()
    op = str(uuid.uuid4())
    payload = {'input': {'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                         'base_revision': doc['revision_id'], 'candidate_id': 'candidate-missing',
                         'decision': 'reopen', 'expected_decision_ref': None}}
    # unchanged 只对"已满足"发生；这里用 decide 的真实 unchanged 分支验证形状，
    # 然后用 node 侧判定逻辑核对信封可被前端接受。
    from deck_master import changes, service, tasks
    entry = doc['pages'][0]
    intent = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
              'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'unchanged terminal test.',
              'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
              'targets': [{'page_id': entry['page_id'], 'page_ref': entry['page'], 'layer': 'svg',
                           'artifact_ref': entry.get('svg')}]}
    plan = changes.plan(project, input=intent)
    result = changes.commit(project, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    task = tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)
    service.task_start(project, task_id=task['task_id'], execution_ref='unchanged-test',
                       supported_protocols=['changes.v1'], capabilities=['change_plan', 'candidate_result'])
    doc = store.load_document()
    task = tasks._lookup_task(doc, task['task_id'], store)
    staging = store.staging_dir / task['operation_id']
    staging.mkdir(parents=True, exist_ok=True)
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    (staging / 'page.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}"><rect width="10" height="10"/></svg>')
    accept = service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                                   produced_against=task['produced_against'],
                                   result_payload={'kind': task['kind'],
                                                   'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
                                                   'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': entry['page_id'],
                                                                       'provenance': {'source_type': 'unknown', 'tool': 'unchanged-test',
                                                                                      'invocation_ref': None}}]})
    candidate_id = accept['candidate_ids'][0]
    first = candidates.decide(project, input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                              'base_revision': store.load_document()['revision_id'],
                                              'candidate_id': candidate_id, 'decision': 'keep_current',
                                              'expected_decision_ref': None},
                              base_revision=store.load_document()['revision_id'], operation_id=str(uuid.uuid4()))
    op = str(uuid.uuid4())
    first_result = first['operation_result'] if first['status'] == 'committed' else first
    current_revision = store.load_document()['revision_id']
    unchanged = candidates.decide(project, input={'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                                  'base_revision': current_revision, 'candidate_id': candidate_id,
                                                  'decision': 'keep_current', 'expected_decision_ref': first_result['decision_ref']},
                                  base_revision=current_revision, operation_id=op)
    assert unchanged['status'] == 'unchanged'
    pending_payload = {'action': 'candidates.decide',
                       'request': {'input': {'schema_version': 'candidate_decision.v1', 'project_id': doc['project_id'],
                                             'base_revision': current_revision, 'candidate_id': candidate_id,
                                             'decision': 'keep_current', 'expected_decision_ref': first_result['decision_ref']},
                                   'base_revision': current_revision, 'operation_id': op},
                       'request_digest': unchanged['request_digest']}
    verdict = run_node(
        'const entry = {pending: {payload: ' + json.dumps(pending_payload) + ', operation_id: ' + json.dumps(op) + '}};'
        'const response = ' + json.dumps(unchanged) + ';'
        'const terminal = await receiptTerminal(entry, response, ' + json.dumps(doc['project_id']) + ');'
        'return {terminal};')
    assert verdict['terminal'] is True, verdict
