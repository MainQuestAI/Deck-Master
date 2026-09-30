"""A05 browser-verification fixture: real content operations on a live service.

create_gallery_sample (24 pages, mixed layers) + one real material file
registered through service.inputs_update (extract on disk read = 已读取) + a
real outline commit that attaches source_links to goals (材料关联) + one real
saved annotation. No model calls; synthetic evidence only.
"""
import json
import sys
import tempfile
import uuid
from pathlib import Path

from deck_master import annotation_service, content_ops, service
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def main():
    root = Path(tempfile.mkdtemp(prefix='deck-master-a05-'))
    project = root / 'a05-project'
    create_gallery_sample(project, page_count=24, readonly=False)
    material = project / 'materials'
    material.mkdir()
    (material / '调研纪要.md').write_text(
        '# 区域服务调研纪要\n\n试点范围内的受理、处理与回访流程存在三次人工转接；'
        '数据边界以工单系统为准。\n', encoding='utf-8')
    store = Store(project)
    doc = store.load_document()

    # 真实材料登记：读取磁盘并提取 → 来源带 extract（已读取态）
    service.inputs_update(project,
                          patch={'reason': 'A05 fixture material', 'task_patch': {},
                                 'source_changes': {'add': [{'path': str(material / '调研纪要.md'),
                                                             'usage_note': '受理流程与数据边界'}],
                                                    'replace': [], 'remove': [], 'metadata': []}},
                          base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    doc = store.load_document()
    registered = doc['sources'][-1]
    source_id = registered['source_id']
    source_version = {'original_sha256': registered['original_sha256'], 'extract': registered['extract']}

    # 真实大纲提交：为第 1-6 页目标挂上来源关联
    plan = doc.get('content_plan')
    bound_goals = (store.read_object_json(plan) or {}).get('input', {}).get('goals', [])
    goals = []
    for goal in bound_goals:
        entry = dict(goal)
        if entry['page_id'] in {'p01', 'p02', 'p03', 'p04', 'p05', 'p06'}:
            entry['source_links'] = [{'source_id': source_id, 'source_version': source_version, 'locator': 'L3'}]
        goals.append(entry)
    stored = store.read_object_json(plan) or {}
    bound = stored.get('input') or {}
    outline = {'schema_version': 'content_operation_input.v1', 'project_id': doc['project_id'],
               'base_revision': doc['revision_id'], 'content_plan_ref': plan, 'action': 'outline',
               'targets': [], 'instruction': 'A05 outline links',
               'content_plan': {'schema_version': 'content_plan_input.v1',
                                'input_summary': bound.get('input_summary') or 'A05 fixture outline with material links',
                                'chapters': bound.get('chapters', []),
                                'goals': goals,
                                'unresolved_facts': bound.get('unresolved_facts', ['合成示例，不提供客户事实。'])}}
    outline_plan = content_ops.plan(project, input=outline)
    content_ops.commit(project, plan_id=outline_plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))

    # 一条真实已保存意见（整页）
    doc = store.load_document()
    entry = doc['pages'][0]
    annotation = {'schema_version': 'annotation.v1', 'project_id': doc['project_id'],
                  'base_revision': doc['revision_id'], 'scope': 'artifact', 'intent': '修改建议',
                  'body': '第 1 页的受理流程描述建议补充转接次数。', 'status': 'open', 'location': {'kind': 'whole'},
                  'layer': 'content', 'artifact_ref': entry['page'],
                  'page_id': entry['page_id'], 'page_ref': entry['page']}
    annotation_service.save(project, input={'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'],
                                            'annotations': [annotation]},
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    server = WorkbenchServer(project)
    url = server.start()
    print(json.dumps({'url': url, 'project': str(project), 'source_id': source_id}), flush=True)
    try:
        sys.stdin.read()
    finally:
        server.stop()


if __name__ == '__main__':
    main()
