"""Build a fixed randomized author packet after all eight I0 outputs exist.

No model calls. Keep the mapping outside the blind packet and never expose it
to the author or auxiliary reviewers before their judgments are recorded.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import secrets
from pathlib import Path

from triage import ROOT, digest, save


def build(run: Path, packet: Path):
    tasks = [item for item in json.loads((ROOT / 'tasks.json').read_bytes())['tasks']
             if item['split'] == 'development']
    outputs = {}
    for task in tasks:
        for arm in ('baseline', 'experiment'):
            stage = run / 'calls' / (arm + '--' + task['id']) / 'argument'
            receipt = json.loads((stage / 'acceptance.json').read_bytes())
            if receipt['status'] != 'accepted':
                raise ValueError('all eight accepted planning results are required for this packet')
            envelope = stage / 'repaired-envelope.json'
            if not envelope.exists():
                envelope = stage / 'envelope.json'
            outputs[(task['id'], arm)] = json.loads(envelope.read_bytes())['payload']
    packet.mkdir(parents=True, exist_ok=False)
    mapping = []
    initial = []
    for number, task in enumerate(tasks, 1):
        pair = f'P{number:02d}'
        arms = ['baseline', 'experiment']
        if secrets.randbelow(2):
            arms.reverse()
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        material = next(item for item in manifest['packs'] if item['id'] == task['pack_id'])
        text = '# ' + pair + '｜' + task['title'] + '\n\n'
        text += '两份均为未采用、未专业审查的策划提案；只评内容，不根据长短或字段数判断。\n\n'
        text += '本次作者任务：' + task['brief'] + '\n\n'
        text += '已知共识：' + '；'.join(task['existing_decisions']) + '\n\n'
        text += '## 同源合成材料\n\n' + (ROOT / material['path']).read_text() + '\n'
        for label, arm in zip(('A', 'B'), arms):
            payload = copy.deepcopy(outputs[(task['id'], arm)])
            # Keep all semantic content, relationships and planning fields.
            # Remove identity/provenance fields only, using the same rule in both arms.
            narrative, plan = payload['narrative'], payload['plan']
            for record in (narrative, plan):
                for key in ('project_id', 'task_id', 'narrative_id', 'plan_id',
                            'version', 'previous_ref', 'basis', 'input_basis', 'narrative_ref'):
                    record.pop(key, None)

            def clean(node):
                if isinstance(node, dict):
                    if 'source_id' in node and 'source_version' in node and 'locator' in node:
                        return {'source': task['pack_id'], 'locator': node['locator']}
                    return {key: clean(value) for key, value in node.items()}
                if isinstance(node, list):
                    return [clean(value) for value in node]
                if isinstance(node, str):
                    value = re.sub(r'\bM(?:0[1-9]|10)\b', '（方法标识隐去）', node)
                    value = value.replace(arm + '--' + task['id'], '（项目标识隐去）')
                    return value
                return node
            payload = clean(payload)
            narrative, plan = payload['narrative'], payload['plan']
            text += '\n## ' + label + '\n\n'
            text += '### 中心主张\n\n'
            central = next(row for row in narrative['nodes'] if row['node_id'] == narrative['central_node_id'])
            text += central['statement'] + '\n\n'
            notes = (run / 'calls' / (arm + '--' + task['id']) / 'argument' / 'author-notes.md').read_text()
            notes = clean(notes)
            notes = re.sub(r'\b[a-f0-9]{64}\b', '（版本标识隐去）', notes)
            notes = re.sub(r'\bsrc-[a-zA-Z0-9_.-]+', '（同源材料）', notes)
            text += '### 完整可读策划说明\n\n' + notes + '\n\n'
            text += '### 完整论证与逐页计划\n\n'
            for number_in_plan, role in enumerate(plan['input']['page_roles'], 1):
                text += f"{number_in_plan}. **{role['role']}**：{role['intended_takeaway']}\n\n"
            structure_name = f'{pair}-{label}-structure.json'
            save(packet / structure_name, payload)
            text += f'[完整结构与来源对应]({structure_name})保留全部节点、关系、限定、未决项、选项和页职责；只隐去版本身份及方法标识。\n'
            mapping.append({'pair': pair, 'label': label, 'sample': arm + '--' + task['id'],
                            'payload_sha256': digest(json.dumps(outputs[(task['id'], arm)], sort_keys=True).encode())})
        path = packet / (pair + '.md')
        path.write_text(text)
        initial.append({'pair_id': pair, 'packet_sha256': digest(path.read_bytes()),
                        'A_scores_first_four': None, 'B_scores_first_four': None,
                        'A_plan_continuity': None, 'B_plan_continuity': None,
                        'full_text_continuity': 'not_evaluated_in_plan_only',
                        'A_severe_failures': None, 'B_severe_failures': None,
                        'better': None, 'expandable_structure_and_reason': None})
    save(run / 'blind-key.json', mapping)
    save(packet / 'author-initial-template.json', {'author': None, 'saved_at': None, 'pairs': initial})
    (packet / 'README.md').write_text(
        '# D00 作者初判包\n\n'
        '先阅读四对材料与 A/B 完整策划；两份都未采用。请按 protocol 的前四维 0–3 分评议，'
        '另记计划连续性；全文贯穿本轮未测。记录哪份更适合本次任务、关键事实错误及可展开结构。'
        '填写 author-initial-template.json 或用文字按 P01–P04 给出判断即可。\n\n'
        '四维顺序：策略适配、业务框架、反向展开、内容取舍。分数锚点：0 明显不成立或偏离；'
        '1 有方向但需实质重构；2 作者小改可用；3 业务具体、结构有解释力且可直接展开。'
        '关键失败包括编造能力/对手事实、扭曲需求与限制、框架无法展开、只换首提/竞标措辞、越界或混稿。\n\n'
        '作者初判保存前没有三模型反馈。当前不要求您知道哪份是新版；映射另存，终判记录后解盲。'
        '每对以完整可读说明和页序为主，另附完整语义结构与计划 JSON；工程字段齐全不代表内容更好。\n\n'
        + '\n'.join(f'- [{"P"+str(n).zfill(2)}]({"P"+str(n).zfill(2)}.md)' for n in range(1, 5)) + '\n')
    return {'status': 'author_initial_required', 'pairs': len(tasks), 'outputs': len(outputs)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.run.expanduser().resolve(), args.packet.expanduser().resolve())))
