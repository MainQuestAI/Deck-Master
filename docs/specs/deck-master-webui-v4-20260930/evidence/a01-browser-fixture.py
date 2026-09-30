"""A01 browser-verification fixture: real service, synthetic sample project.

Creates an editable synthetic verification project with 32 repair tasks
(5 started, 1 finished with a candidate) so the run desk has pagination,
multiple statuses and sample identity. Starts a WorkbenchServer and prints
the base URL. No model calls; same fixtures as tests/rebuild.
"""
import json
import sys
import tempfile
import uuid
from pathlib import Path

from deck_master import changes, service, tasks
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def dispatch(store, page):
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == page)
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'A01 verification spacing pass.',
             'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
             'targets': [{'page_id': page, 'page_ref': entry['page'], 'layer': 'svg',
                          'artifact_ref': entry.get('svg')}]}
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan['plan_id'],
                            base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    return tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)


def main():
    root = Path(tempfile.mkdtemp(prefix='deck-master-a01-'))
    project = root / 'a01-project'
    create_sample(project, page_count=3, readonly=False)
    store = Store(project)
    started, finished = [], None
    pages = ['p01', 'p02', 'p03']
    for index in range(32):
        task = dispatch(store, pages[index % 3])
        if index < 5:
            service.task_start(store.project_root, task_id=task['task_id'], execution_ref='synthetic-a01-verification',
                               supported_protocols=['changes.v1', 'generation.v1'],
                               capabilities=['change_plan', 'generation_request_freeze', 'attempt_binding',
                                             'native_tool_observation', 'candidate_result'])
            started.append(task['task_id'])
    # One started task gets a synthetic SVG result so '结果已记录' appears alongside.
    doc = store.load_document()
    entry = next(e for e in doc['pages'] if e['page_id'] == 'p01')
    target = tasks._lookup_task(doc, started[0], store)
    staging = store.staging_dir / target['operation_id']
    staging.mkdir(parents=True, exist_ok=True)
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    (staging / 'page.svg').write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}">'
        '<rect width="20" height="20" fill="#000000"/></svg>')
    service.accept_result(store.project_root, task_id=target['task_id'], operation_id=target['operation_id'],
                          produced_against=target['produced_against'],
                          result_payload={'kind': target['kind'],
                                          'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
                                          'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': 'p01',
                                                              'provenance': {'source_type': 'unknown', 'tool': 'synthetic-a01',
                                                                             'invocation_ref': None}}]})
    finished = target['task_id']
    server = WorkbenchServer(project)
    url = server.start()
    print(json.dumps({'url': url, 'project': str(project), 'total_tasks': 32,
                      'started': started, 'finished_with_result': finished,
                      'revision': store.current_revision_id()}))
    try:
        sys.stdin.read()  # keep the server up until the driver closes stdin
    finally:
        server.stop()


if __name__ == '__main__':
    main()
