"""A06 browser-verification fixture: SVG artifact + content (Page) candidates.

create_gallery_sample 24 pages; a real SVG trial on p01 (accepted via
accept_result -> candidate) and a real single-page content trial on p02
(returning a rewritten Page package as a result_kind=page candidate).
No model calls; synthetic evidence only.
"""
import json
import sys
import tempfile
import uuid
from pathlib import Path

from deck_master import changes, service, tasks
from deck_master.samples import create_gallery_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def trial(store, project, page_id, layer, *, staging_file, media, role):
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == page_id)
    intent = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
              'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'A06 synthetic trial.',
              'annotation_refs': [], 'max_calls': 1 if layer == 'original_image' else 0, 'mode': 'trial',
              'targets': [{'page_id': page_id, 'page_ref': entry['page'], 'layer': layer,
                           'artifact_ref': entry.get('blueprint') if layer == 'original_image' else entry.get('svg')}]}
    plan = changes.plan(project, input=intent)
    result = changes.commit(project, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    task_id = result['operation_result']['task_ids'][0]
    service.task_start(project, task_id=task_id, execution_ref='synthetic-a06',
                       supported_protocols=['changes.v1', 'generation.v1'],
                       capabilities=['change_plan', 'generation_request_freeze', 'attempt_binding',
                                     'native_tool_observation', 'candidate_result'])
    return task_id


def main():
    root = Path(tempfile.mkdtemp(prefix='deck-master-a06-'))
    project = root / 'a06-project'
    create_gallery_sample(project, page_count=24, readonly=False)
    store = Store(project)
    doc = store.load_document()

    # p01 原图 trial：冻结 + 开始 + 合成返回（经真实 accept_result 记录候选）
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    intent = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
              'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'A06 svg trial.',
              'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
              'targets': [{'page_id': 'p01', 'page_ref': entry['page'], 'layer': 'svg',
                           'artifact_ref': entry.get('svg')}]}
    plan = changes.plan(project, input=intent)
    result = changes.commit(project, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    task_id = result['operation_result']['task_ids'][0]
    service.task_start(project, task_id=task_id, execution_ref='synthetic-a06',
                       supported_protocols=['changes.v1', 'generation.v1'],
                       capabilities=['change_plan', 'generation_request_freeze', 'attempt_binding',
                                     'native_tool_observation', 'candidate_result'])
    doc = store.load_document()
    task = tasks._lookup_task(doc, task_id, store)
    doc = store.load_document()
    task = tasks._lookup_task(doc, task_id, store)
    staging = store.staging_dir / task['operation_id']
    staging.mkdir(parents=True, exist_ok=True)
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    (staging / 'page.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}">'
        '<rect width="24" height="24" fill="#000000"/></svg>')
    service.accept_result(project, task_id=task_id, operation_id=task['operation_id'],
                          produced_against=task['produced_against'],
                          result_payload={'kind': task['kind'],
                                          'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
                                          'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': 'p01',
                                                              'provenance': {'source_type': 'unknown', 'tool': 'synthetic-a06',
                                                                             'invocation_ref': None}}]})
    # p02 content (Page) trial：返回改写后的 Page 包 → result_kind=page 候选
    import copy as copy_module
    doc = store.load_document()
    entry2 = next(e for e in doc['pages'] if e['page_id'] == 'p02')
    intent2 = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
               'base_revision': doc['revision_id'], 'intent': 'content', 'instruction': 'A06 content trial.',
               'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
               'targets': [{'page_id': 'p02', 'page_ref': entry2['page'], 'layer': 'content',
                            'artifact_ref': entry2['page']}]}
    plan2 = changes.plan(project, input=intent2)
    result2 = changes.commit(project, plan_id=plan2['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    task_id2 = result2['operation_result']['task_ids'][0]
    service.task_start(project, task_id=task_id2, execution_ref='synthetic-a06',
                       supported_protocols=['changes.v1'],
                       capabilities=['change_plan', 'candidate_result', 'content_candidate'])
    doc = store.load_document()
    task2 = tasks._lookup_task(doc, task_id2, store)
    page2 = copy_module.deepcopy(store.read_object_json(entry2['page']))
    page2['customer_visible']['title'] += '（改写候选）'
    service.accept_result(project, task_id=task_id2, operation_id=task2['operation_id'],
                          produced_against=task2['produced_against'],
                          result_payload={'kind': task2['kind'], 'pages': [page2]})

    server = WorkbenchServer(project)
    url = server.start()
    print(json.dumps({'url': url, 'project': str(project)}), flush=True)
    try:
        sys.stdin.read()
    finally:
        server.stop()


if __name__ == '__main__':
    main()
