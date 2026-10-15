"""Finite source-runtime re-review: exact F9 and actual C6 input workorder.

L1 software evidence only. No Host application, model, professional or human
acceptance is claimed. Mutations create only private review fixture projects.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from deck_master import method_resources, run_desk, service
from deck_master.samples import create_sample
from deck_master.store import Store

OUT = Path(__file__).resolve().parent


def snapshot(project):
    return {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(project.rglob('*')) if p.is_file()}


def main():
    project = OUT / 'f9-project'
    service.create(project, brief='L1 source-runtime method-read context; no production grant')
    before = snapshot(project)
    cases = [
        ('请协调这次档案值班培训的策划与后续职责，先把真实范围和下一责任说明白，不制作整套PPT。', 'deck-master', None),
        ('请给协调流程这一页写正文，不做设计。', 'deck-content', 'write_only'),
        ('只做内容策划，不要写稿和讲稿。', 'deck-content', 'plan_only'),
        ('只写讲稿，不要审稿，也不要设计。', 'deck-content', 'speech_only'),
        ('只写正文，不要讲稿。', 'deck-content', 'write_only'),
        ('请给固定p2新损伤处置页出视觉方案，清楚保留停阅→保持原状→通知保管员以及保管员确认恢复；不要生图，不改正文。', 'deck-design', None),
        ('请审查已有文件，指出实际缺口，不修改。', 'deck-review', None),
        ('请恢复之前的项目，接着完成现有工作。', 'deck-master', None),
        ('deck-content 请协调内容策划', 'deck-content', 'plan_only'),
    ]
    routed = []
    for text, skill, intent in cases:
        value = method_resources.route_request(text)
        assert value['skill'] == skill and value['content_intent'] == intent, (text, value)
        assert value['authority'] == 'routing_suggestion_only'
        read = method_resources.read_skill_methods(skill, entry_mode='natural', project=project, text=text)
        assert read['skill'] == skill and read['host_application'] == 'not_recorded'
        routed.append({'text': text, 'expected_skill': skill, 'expected_content_intent': intent,
                       'actual': value, 'method_read_skill': read['skill'],
                       'method_hashes': [entry['sha256'] for entry in read['methods']]})
    assert snapshot(project) == before

    c6 = OUT / 'c6-project'
    create_sample(c6, page_count=2, readonly=False)
    store = Store(c6)
    reason = '保留用户原话 API、Page v2、proposal Ref。\n补充：下一责任须另行确认。'
    service.inputs_update(c6, patch={'reason': reason, 'task_patch': {'audience': '档案值班组长'}},
        base_revision=store.current_revision_id(), operation_id='L1-independent-C6-input-update')
    task_ref, task = next((ref, value) for ref in store.load_document()['tasks']
                         if (value := store.read_object_json(ref)).get('intent') == 'input_revision')
    assert task['protocol_version'] == 'compose.v2'
    raw = task['instruction']
    task_bytes = store.read_object_bytes(task_ref)
    before_c6 = snapshot(c6)
    rows = []
    row = run_desk.task_row(task)
    assert row['instruction'] == raw and task['instruction'] == raw
    assert row['display_instruction'].startswith(reason + ' · ')
    assert 'compose.v2 input_revision：changed_layers' not in row['display_instruction']
    rows.append({'case': 'actual_input_workorder', 'raw': raw, 'display': row['display_instruction']})

    trial = deepcopy(task)
    trial['instruction'] += (' 当前为显式 trial：除 content_update 外还须提交完整 content_plan_input；'
        '结果保存为候选，采用前不改动当前正文、页序或产物。')
    display = run_desk.task_row(trial)['display_instruction']
    assert display.startswith(reason + ' · ') and display.endswith('先返回候选，采用前保持当前稿。')
    rows.append({'case': 'known_trial_wrapper', 'raw': trial['instruction'], 'display': display})

    variants = [
        ('appended_user_prose', {**task, 'instruction': raw + ' 用户追加：请保留 API 讨论和新的责任说明。'}),
        ('unknown_template', {**task, 'instruction': raw.replace('读取新输入与 diff', '读取未知新版模板与 diff')}),
        ('different_input_identity', {**task, 'input_revision_id': 'different-user-input-identity'}),
        ('unknown_protocol', {**task, 'protocol_version': 'compose.future'}),
    ]
    for label, candidate in variants:
        row = run_desk.task_row(candidate)
        assert row['instruction'] == row['display_instruction'] == candidate['instruction'], label
        rows.append({'case': label, 'raw': candidate['instruction'], 'display': row['display_instruction']})
    assert store.read_object_bytes(task_ref) == task_bytes
    assert snapshot(c6) == before_c6
    output = {'evidence_level': 'L1_SOURCE_RUNTIME', 'f9_cases': routed,
              'f9_method_reads_are_pure': True, 'c6_cases': rows,
              'c6_stored_instruction_and_source_unchanged': True,
              'module': str(Path(method_resources.__file__).resolve()),
              'real_host_application': 'NOT_RUN', 'human_desktop': 'NOT_RUN'}
    (OUT / 'probe-f9-c6-result.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'routing_cases': len(routed), 'c6_cases': len(rows), 'status': 'PASS'}))


if __name__ == '__main__':
    main()
