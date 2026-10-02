"""Q03–Q05: candidate adoption lifecycle; synthetic projects, no model calls."""
import copy
import uuid
from xml.sax.saxutils import escape

import pytest

from deck_master import candidates, content_ops, service, stages, tasks
from deck_master.generation import GenerationError
from deck_master.samples import create_sample
from deck_master.store import Store
from page_visual_helpers import pass_page_review
from hostenv import resolve_host_font
import test_candidates as artifacts
import test_content_candidates as content


@pytest.fixture
def project(tmp_path):
    path = tmp_path / 'quality-project'
    create_sample(path, page_count=1, readonly=False)
    return Store(path)


def svg_payload(store, task, width):
    payload = artifacts.envelope(store, task, width)
    path = store.staging_dir / task['operation_id'] / 'page.svg'
    title = store.read_object_json(store.load_document()['pages'][0]['page'])['customer_visible']['title']
    text = f'<text x="50" y="80" font-family="{resolve_host_font()}" font-size="32">{escape(title)}</text>'
    path.write_text(path.read_text().replace('</svg>', text + '</svg>'))
    return payload


@pytest.mark.render
@pytest.mark.parametrize('restore_stale_output', [False, True])
def test_adopted_svg_continue_rebuilds_existing_ppt(project, restore_stale_output):
    from deck_master.models import bump_revision
    store = project
    first = artifacts.dispatch(store, mode='auto'); artifacts.start(store, first)
    artifacts.accept(store, first, svg_payload(store, first, 20))
    pending = service.continue_project(store.project_root)['pending_tasks'][0]
    pass_page_review(store.project_root, pending)
    stages.assemble(store.project_root, base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    old = copy.deepcopy(store.load_document())
    trial = artifacts.dispatch(store); artifacts.start(store, trial)
    cid = artifacts.accept(store, trial, svg_payload(store, trial, 100))['candidate_ids'][0]
    value = artifacts.plan(store, [cid]); op = str(uuid.uuid4())
    result = artifacts.adopt(store, value, op)
    assert artifacts.adopt(store, value, op)['operation_result'] == result['operation_result']
    if not restore_stale_output:
        assert all(v is None for v in store.load_document()['outputs'].values())
    else:
        # An old writer already adopted the SVG but retained the old PPT.
        doc = store.load_document(); updated = copy.deepcopy(doc); updated['outputs'] = old['outputs']
        updated = bump_revision(updated, {'kind': 'artifact_adoption', 'operation_id': 'old-writer', 'description': 'synthetic old writer state', 'read_set': []})
        store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='old-writer')
    pending = service.continue_project(store.project_root)['pending_tasks'][0]
    pass_page_review(store.project_root, pending)
    result = service.continue_project(store.project_root)
    doc = store.load_document()
    assert doc['outputs']['pptx'] != old['outputs']['pptx']
    assert doc['pages'][0]['ppt_preview'] is not None
    assert result['next_action'] == 'codex_review_renderings'


@pytest.mark.parametrize('changed', [True, False])
def test_content_adoption_retires_only_obsolete_tasks(project, changed):
    store = project; path = store.project_root
    automatic = service.open_host_task(store, kind='reconstruct', page_ids=['p01'], instruction='reconstruct current page')
    trial = content.dispatch_content_trial(path, store); content.start_task(path, trial)
    cid = content.accept(path, trial, content.page_envelope(store, trial, title_suffix=' changed' if changed else ''))['candidate_ids'][0]
    content.adopt(path, store, [cid])
    current = tasks._lookup_task(store.load_document(), automatic['task_id'], store)
    assert current['status'] == ('superseded' if changed else 'awaiting_host')
    if changed:
        with pytest.raises(Exception, match='supersed|late|terminal|cancellation'):
            artifacts.accept(store, automatic, svg_payload(store, automatic, 40))
        pending = service.continue_project(path)['pending_tasks']
        assert all(t['task_id'] != automatic['task_id'] for t in pending)


def test_input_trial_rejects_unclaimed_host_before_completion(project):
    store = project; path = store.project_root
    material = path / 'new-source.md'; material.write_text('Synthetic clarification, no new page required.')
    result = content_ops.inputs(path, input={'reason': 'clarification', 'mode': 'trial', 'source_changes': {'add': [{'path': str(material)}]}},
                               base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))['operation_result']
    task = tasks._lookup_task(store.load_document(), result['pending_tasks'][0]['task_id'], store)
    doc = store.load_document(); before = store.read_current()
    payload = {'kind': 'compose', 'content_update': {'input_digest': task['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
               'page_order': [p['page_id'] for p in doc['pages']], 'unchanged_reason': 'Clarification does not change the existing page.'},
               'content_plan': copy.deepcopy(store.read_object_json(doc['content_plan'])['input'])}
    with pytest.raises(GenerationError, match='requires'):
        content.accept(path, task, payload)
    assert store.read_current() == before
    assert candidates.listing(path)['candidates'] == []
    content.start_task(path, task)
    cid = content.accept(path, task, payload)['candidate_ids'][0]
    content.adopt(path, store, [cid])
