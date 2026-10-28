"""Synthetic mechanism proof; no model or professional review claim."""
import copy
import uuid

import pytest

from deck_master import candidates, changes, collaboration, generation, service, tasks
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from deck_master.samples import create_sample
from deck_master.store import Store
from rc3_fixtures import authorize_scope, evidence_for, historical_snapshot, settle_fidelity_review


@pytest.fixture
def store(tmp_path):
    project = tmp_path / 'candidate-project'
    create_sample(project, page_count=2, readonly=False)
    current = Store(project).load_document()
    scope = {'subject': 'deck', 'page_ids': ['p01', 'p02'], 'page_manifest_ref': None,
        'external_artifact_ref': None, 'layers': ['narrative', 'plan', 'page_copy', 'speech',
            'design', 'blueprint', 'svg', 'review', 'output'],
        'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'working'}
    collaboration.start_request(project, input={'intent': 'full_deck', 'content_intent': None,
        'scope': scope, 'replace_request_id': current['collaboration']['request']['request_id'],
        'instruction_evidence': evidence_for(project,
            text='L1 synthetic candidate tests: compare two fixed pages, retain originals and adopt explicit selections.',
            locator='L1:candidates:request')}, base_revision=current['revision_id'], operation_id='L1-candidates-request')
    settle_fidelity_review(project, page_ids=['p01', 'p02'], execution_ref='L1-fidelity-candidates',
        scenario='Confirmed synthetic sample text before bounded candidate workflows')
    authorize_scope(project, actions=['change.commit', 'candidate.adopt', 'dispatch.blueprint',
        'allowance.allocate', 'call.begin'], scope=scope, max_external_calls=2, max_candidate_count=4,
        adoption_policy='within_scope', evidence=evidence_for(project,
            text='Authorize at most two L1 image calls and four bounded candidate trials for these pages.',
            locator='L1:candidates:grant'))
    return Store(project)


def dispatch(store, page='p01', *, mode='trial', layer='svg', references=None):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == page)
    value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
             'base_revision': doc['revision_id'], 'intent': 'repair', 'instruction': 'Improve the spacing.',
             'annotation_refs': [], 'max_calls': int(layer == 'original_image'), 'mode': mode,
             'targets': [{'page_id': page, 'page_ref': entry['page'], 'layer': layer,
                          'artifact_ref': entry['blueprint'] if layer == 'original_image' else entry.get('svg')}]}
    if references is not None:
        value['references'] = references
    plan = changes.plan(store.project_root, input=value)
    result = changes.commit(store.project_root, plan_id=plan['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    return tasks._lookup_task(store.load_document(), result['operation_result']['task_ids'][0], store)


def start(store, task, candidate_support=True):
    capabilities = [value for value in task['required_capabilities'] if value != 'candidate_result']
    if candidate_support:
        capabilities.append('candidate_result')
    return service.task_start(store.project_root, task_id=task['task_id'], execution_ref='synthetic-test-host',
                              supported_protocols=['changes.v1', 'generation.v1'], capabilities=capabilities)


def envelope(store, task, width=20):
    doc = store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == task['scope_pages'][0])
    original = store.read_object_json(entry['blueprint'])['file']['sha256']
    staging = store.staging_dir / task['operation_id']; staging.mkdir(parents=True, exist_ok=True)
    (staging / 'page.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" data-blueprint-sha256="{original}"><rect width="{width}" height="20" fill="#000000"/></svg>')
    return {'kind': task['kind'], 'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
            'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': entry['page_id'],
                                'provenance': {'source_type': 'unknown', 'tool': 'synthetic-test', 'invocation_ref': None}}]}


def accept(store, task, payload=None):
    return service.accept_result(store.project_root, **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
                                  result_payload=payload or envelope(store, task))


def candidate(store, page='p01', width=20):
    task = dispatch(store, page); start(store, task)
    result = accept(store, task, envelope(store, task, width))
    return result['candidate_ids'][0]


def plan(store, ids):
    doc = store.load_document()
    return candidates.plan(store.project_root, input={'schema_version': 'candidate_selection.v1', 'project_id': doc['project_id'],
                                                      'base_revision': doc['revision_id'], 'candidate_ids': ids})['plan']


def adopt(store, value, op=None):
    return candidates.adopt(store.project_root, input=value, base_revision=value['base_revision'], operation_id=op or str(uuid.uuid4()))

