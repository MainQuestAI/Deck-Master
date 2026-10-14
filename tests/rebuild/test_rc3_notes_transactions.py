"""RC3-02 formal writes with explicitly synthetic authority/review fixtures.

Actual native files are checked separately; these tests never claim human or
independent model quality approval.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from deck_master import content_production, editing, service, workbench
from deck_master.content_plan import ContentPlanError, refresh_v2_plan_links
from deck_master.models import bump_revision, require_writer
from deck_master.store import Store, StoreError
from deck_master.tasks import EnvelopeError
from page_visual_helpers import pass_page_review, make_page_reviews
from test_page_visual_gate import _start, _accept, _svg_envelope
from test_service_flow import _draft_page
from test_compose_v2_phases import _deck_with_pages, _submit


def _completed_visual(tmp_path, *, finding=False):
    project = tmp_path / 'project'
    page = _draft_page('p-a', '记录未知', '54/120＝45%，不是节约率。')
    page['speaker_notes'] = '原有讲者备注。\n末段。\n'
    service.create(project, brief='Synthetic notes engineering fixture', draft={'pages': [page]})
    task, svg = _start(project, 'p-a')
    page_ref = Store(project).load_document()['pages'][0]['page']
    envelope = _svg_envelope('p-a')
    envelope['artifact_specs'][0]['provenance']['generated_from_page'] = page_ref
    envelope['artifact_specs'][0]['dependencies'] = [{'kind': 'content', 'identity': 'page:p-a', 'sha256': page_ref['sha256']}]
    _accept(project, task, envelope, file_name='page.svg', data=svg)
    review = service.continue_project(project)['pending_tasks'][0]
    if finding:
        reviews = make_page_reviews(review)
        reviews[0]['status'] = 'fail'
        reviews[0]['findings'] = [{'finding_id': 'visual-open', 'page_id': 'p-a',
                                 'element_refs': [], 'kind': 'design',
                                 'message': 'Synthetic open visual issue.', 'impact': 'must_fix',
                                 'expected': 'Visual issue repaired.', 'actual': 'Issue remains.',
                                 'evidence': [],
                                 'resolution': 'open'}]
        _accept(project, review, {'kind': 'review', 'reviews': reviews})
    else:
        pass_page_review(project, review)
    return project, Store(project)


def test_notes_edit_preserves_completed_visual_and_actual_review_bytes(tmp_path):
    project, store = _completed_visual(tmp_path)
    before = store.load_document()
    entry = before['pages'][0]
    raw_reviews = [store.read_object_bytes(ref) for ref in before['reviews']]
    page = store.read_object_json(entry['page'])
    page['speaker_notes'] = '新备注中文。\n\n末段54/120＝45%，不是节约率。\n'
    result = editing.edit_page(project, page=page, base_revision=before['revision_id'],
                               page_hash=entry['page']['sha256'], operation_id='notes-change')
    after = store.load_document()
    assert after['compatibility']['minimum_writer'] == 'rc3.v1'
    assert after.get('collaboration') is None
    assert all(after['pages'][0][slot] == entry[slot] for slot in ('blueprint', 'svg', 'svg_preview'))
    assert after['pages'][0]['ppt_preview'] is None
    assert after['reviews'] == before['reviews']
    assert [store.read_object_bytes(ref) for ref in after['reviews']] == raw_reviews
    assert editing.page_visual_summary(store, after, after['pages'][0])['status'] == 'pass'
    projection = workbench._ReadContext(store, after)
    for slot in ('blueprint', 'svg', 'svg_preview'):
        artifact = store.read_object_json(after['pages'][0][slot])
        assert workbench._applicability(projection, after['pages'][0], artifact)['status'] == 'current'
    assert result['status'] == 'edited'
    replay = editing.edit_page(project, page=page, base_revision=before['revision_id'],
                               page_hash=entry['page']['sha256'], operation_id='notes-change')
    assert replay['status'] == 'already_applied'
    assert store.load_document()['revision_id'] == after['revision_id']


def test_visual_open_finding_not_fixed_by_notes(tmp_path):
    project, store = _completed_visual(tmp_path, finding=True)
    before = store.load_document(); entry = before['pages'][0]
    page = store.read_object_json(entry['page']); page['speaker_notes'] = '仅改备注。'
    editing.edit_page(project, page=page, base_revision=before['revision_id'],
                      page_hash=entry['page']['sha256'], operation_id='notes-not-visual-fix')
    after = store.load_document()
    assert editing.page_visual_summary(store, after, after['pages'][0])['status'] == 'fail'
    from deck_master.stages import require_assembly_ready
    with pytest.raises(Exception, match='visual review must pass'):
        require_assembly_ready(store, after)
    old_ref = after['reviews'][0]
    old_review = store.read_object_json(old_ref)
    task = service.open_host_task(store, kind='review', page_ids=['p-a'],
                instruction='Synthetic attempted closure after only notes changed', review_stage='page_visual')
    reviews = make_page_reviews(service.task_summary(store, store.load_document(), task))
    candidate = reviews[0]
    candidate['review_id'] = old_review['review_id']
    candidate['replaces'] = old_ref
    candidate['findings'] = [{**old_review['findings'][0], 'resolution': 'fixed',
         'evidence': [store.load_document()['pages'][0]['page']],
         'resolution_reason': 'Synthetic unsupported claim; only notes changed.'}]
    with pytest.raises(EnvelopeError, match='not closed'):
        _accept(project, task, {'kind': 'review', 'reviews': reviews})
    assert editing.page_visual_summary(store, store.load_document(), store.load_document()['pages'][0])['status'] == 'fail'


def test_speech_strict_unknown_and_duplicate_updates_leave_current_unchanged(tmp_path):
    project, store = _deck_with_pages(tmp_path)
    task = content_production.open_phase_task(store, store.load_document(),
                operation_id='speech-strict', phase='speech', page_ids=['p1'])
    before = store.load_document(); entry = before['pages'][0]
    notes = '只改口播。'
    update = {'page_id': 'p1', 'page_ref': entry['page'], 'speaker_notes': notes,
              'speech_segments': [{'segment_id': 's1', 'start_codepoint': 0,
                                  'end_codepoint': len(notes), 'narrative_node_ids': ['n1'],
                                  'kind': 'cue', 'estimated_seconds': 4}]}
    with pytest.raises(EnvelopeError, match='unknown speech update'):
        _submit(project, task, {'updates': [{**update, 'hidden_write': None}]}, 'speech')
    assert store.load_document()['revision_id'] == before['revision_id']
    with pytest.raises(EnvelopeError, match='duplicate'):
        _submit(project, task, {'updates': [update, update]}, 'speech')
    assert store.load_document()['revision_id'] == before['revision_id']


@pytest.mark.parametrize('mode', ['bound', 'imported_mapping'])
def test_plan_refresh_rejects_stale_mapping_and_duplicates(tmp_path, mode):
    project, store = _deck_with_pages(tmp_path)
    doc = store.load_document(); plan = store.read_object_json(doc['content_plan'])
    if mode == 'imported_mapping':
        plan['mode'] = mode; plan['origin'] = 'user_imported'
        plan['imported_manuscript'] = {'source_ref': store.put_blob(b'Synthetic confirmed manuscript', ext='txt'),
             'claimed_confirmation_evidence': {'kind': 'imported_unknown', 'assurance': 'unverified',
                 'source_ref': store.put_blob(b'Synthetic claim only', ext='txt'), 'source_locator': None,
                 'actor_id': None, 'transport_receipt_ref': None, 'presentation_ref': None},
             'preserve_mainline': True, 'unresolved_mapping_items': []}
    before = deepcopy(doc)
    stale = deepcopy(plan); stale['page_links'][0]['page_ref'] = store.put_json_object({'fixture': 'bad ref'})
    with pytest.raises(ContentPlanError, match='stale'):
        refresh_v2_plan_links(store, doc, {}, stale, doc['pages'], previous_ref=doc['content_plan'])
    with pytest.raises(ContentPlanError, match='unique'):
        refresh_v2_plan_links(store, doc, {}, plan, doc['pages'] * 2, previous_ref=doc['content_plan'])
    assert store.load_document() == before


def test_migrated_control_cannot_be_removed_at_higher_feature_floor(tmp_path):
    _, store = _deck_with_pages(tmp_path)
    doc = store.load_document(); updated = bump_revision(doc, {'operation_id': 'drop-control',
             'kind': 'content_update', 'description': 'Synthetic forbidden removal', 'read_set': []})
    require_writer(updated, 'rc3.v1'); updated.pop('collaboration'); updated.pop('narrative')
    with pytest.raises(StoreError, match='cannot drop its collaboration'):
        store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='drop-control')
    assert store.load_document()['revision_id'] == doc['revision_id']


def test_notes_feature_floor_does_not_manufacture_narrative_or_task_migration(tmp_path):
    from deck_master.models import ModelError, require_task_binding, validate_document_semantics
    project = tmp_path / 'project'
    service.create(project, brief='Synthetic historical notes fixture',
                   draft={'pages': [_draft_page('p1', '标题', '正文')]})
    store = Store(project); doc = store.load_document(); require_writer(doc, 'rc3.v1')
    validate_document_semantics(doc)
    with pytest.raises(ModelError, match='actual migrated control region'):
        require_task_binding(doc, {'collaboration_binding': {'request_id': 'forged'}})
    doc['narrative'] = store.put_json_object({'fixture': 'not a migrated Narrative'})
    with pytest.raises(ModelError, match='real control region'):
        validate_document_semantics(doc)


def test_notes_only_refresh_reuses_non_speech_preproduction_but_stales_speech(tmp_path):
    from deck_master import content_review
    import test_eligibility_enforcement as enf
    from test_content_preproduction_review import _deck
    from test_rc3_01_gate_repair import _publish
    project, store = _deck(tmp_path)
    _publish(project, store)
    assert content_review.preproduction_status(store, store.load_document())['status'] == 'pass'
    enf._grant(project, store, actions=('page.edit',))
    before = store.load_document(); entry = before['pages'][0]
    page = store.read_object_json(entry['page']); page['speaker_notes'] += '新增过渡。'
    page['content_mapping']['speech_segments'][0]['end_codepoint'] = len(page['speaker_notes'])
    editing.edit_page(project, page=page, base_revision=before['revision_id'],
                      page_hash=entry['page']['sha256'], operation_id='notes-scope-units')
    status = content_review.preproduction_status(store, store.load_document())
    assert set(status['satisfied_units']) == {'argument', 'page_copy', 'progression'}
    assert status['missing_units'] == ['speech']


def test_imported_null_narrative_speech_creates_honest_mapping_and_current_plan_links(tmp_path):
    import test_eligibility_enforcement as enf
    from test_rc3_notes_visual_inputs import _seed_imported_plan
    project, store = enf._project(tmp_path)
    _seed_imported_plan(store)
    doc = store.load_document(); plan = store.read_object_json(doc['content_plan'])
    plan['input']['speech_policy'] = {'mode': 'cues', 'source': 'provided', 'output': 'pptx_notes'}
    updated = bump_revision(deepcopy(doc), {'operation_id': 'seed-speech-policy',
         'kind': 'content_update', 'description': 'Explicit synthetic speaker request', 'read_set': []})
    updated['content_plan'] = store.put_json_object(plan)
    store.commit_change(base_revision=doc['revision_id'], document=updated, operation_id='seed-speech-policy')
    enf._start(project, store)
    enf._grant(project, store, actions=('dispatch.compose', 'task.accept', 'task.start'))
    before = store.load_document(); previous_plan = store.read_object_json(before['content_plan'])
    task = content_production.open_phase_task(store, before, operation_id='imported-speech',
                    phase='speech', page_ids=['p1'])
    notes = '原稿主线保留。\n\n只增加口播提示。'
    payload = {'updates': [{'page_id': 'p1', 'page_ref': store.load_document()['pages'][0]['page'],
              'speaker_notes': notes, 'speech_segments': [{'segment_id': 's1', 'start_codepoint': 0,
               'end_codepoint': len(notes), 'narrative_node_ids': [], 'kind': 'cue', 'estimated_seconds': 5}]}]}
    result = _submit(project, task, payload, 'speech')
    after = store.load_document(); current_plan = store.read_object_json(after['content_plan'])
    assert result['status'] == 'accepted' and after.get('narrative') is None
    assert current_plan['mode'] == 'imported_mapping' and current_plan['narrative_ref'] is None
    assert current_plan['input'] == previous_plan['input']
    assert current_plan['imported_manuscript'] == previous_plan['imported_manuscript']
    assert {link['page_id']: link['page_ref'] for link in current_plan['page_links']} == {
        entry['page_id']: entry['page'] for entry in after['pages']}
    current_page = store.read_object_json(after['pages'][0]['page'])
    original_page = store.read_object_json(before['pages'][0]['page'])
    assert current_page['customer_visible'] == original_page['customer_visible']
    assert current_page['speaker_notes'] == notes
    assert current_page['content_mapping']['narrative_ref'] is None
    assert after['pages'][1] == before['pages'][1]
    status = content_production.content_phase_status(store, after)
    assert status['phase'] == 'speech' and status['page_ids'] == ['p2']


def test_actual_completed_visual_notes_assembly_export_zero_image_ledger(tmp_path):
    from deck_master import pipeline, stages, exports
    from deck_master.compiler.native import notes_records
    import uuid
    project, store = _completed_visual(tmp_path)
    original = store.load_document()
    pipeline.produce(project)
    before = store.load_document(); entry = before['pages'][0]
    page = store.read_object_json(entry['page'])
    page['speaker_notes'] = '新口播54/120＝45%，不是节约率。\n\n末段。\n'
    task_facts = [store.read_object_json(ref) for ref in before['tasks']]
    editing.edit_page(project, page=page, base_revision=before['revision_id'],
                      page_hash=entry['page']['sha256'], operation_id='notes-for-final-file')
    changed = store.load_document()
    assert not pipeline.output_matches_current_svg(store, changed)
    assert changed['outputs']['pptx'] is None
    assert editing.page_visual_summary(store, changed, changed['pages'][0])['status'] == 'pass'
    stages.assemble(project, base_revision=changed['revision_id'], operation_id=str(uuid.uuid4()))
    after = store.load_document()
    assert after['outputs']['pptx'] != before['outputs']['pptx']
    assert workbench._deck_output(workbench._ReadContext(store, after))['applicability'] == 'current'
    assert all(after['pages'][0][slot] == before['pages'][0][slot] for slot in ('blueprint', 'svg', 'svg_preview'))
    assert [store.read_object_json(ref) for ref in after['tasks']] == task_facts
    result = exports.create(project, notes_policy='pptx_notes', output_dir=tmp_path / 'public')
    data, _ = exports.download(project, export_id=result['export_id'], filename='deck.pptx')
    records = notes_records(data)
    assert [(record['page_id'], record['notes']) for record in records] == [('p-a', page['speaker_notes'])]
    stale = deepcopy(after)
    stale['outputs'] = before['outputs']
    assert workbench._deck_output(workbench._ReadContext(store, stale))['applicability'] == 'basis_changed'


def test_frozen_a_real_sdk_refuses_protected_notes_write_boundaries(tmp_path):
    """Use the immutable actual A installation; never patch its writer set."""
    python = Path('/workspace/work/rc3/baseline-a/venv/bin/python')
    if not python.exists():
        pytest.skip('Frozen A installation is an external engineering resource')
    project, store = _completed_visual(tmp_path)
    before = store.load_document(); entry = before['pages'][0]
    page = store.read_object_json(entry['page']); page['speaker_notes'] = '受保护备注。'
    editing.edit_page(project, page=page, base_revision=before['revision_id'],
                      page_hash=entry['page']['sha256'], operation_id='protect-notes')
    protected = store.load_document()
    code = '''import json,sys
from deck_master import service, editing, pipeline, stages
project=sys.argv[1];page=json.loads(sys.argv[2])
ops={"compile":lambda:pipeline.produce(project),
"assemble":lambda:stages.assemble(project,base_revision="old",operation_id="old-assemble"),
"claim":lambda:service.task_start(project,task_id="old",execution_ref="old-host"),
"accept":lambda:service.accept_result(project,task_id="old",operation_id="old-accept",produced_against="old",result_payload={"kind":"review","reviews":[]}),
"edit":lambda:editing.edit_page(project,page=page,base_revision="old",page_hash="old",operation_id="old-edit"),
"restore":lambda:editing.restore(project,revision_id="old",base_revision="old",operation_id="old-restore")}
out={}
for name,fn in ops.items():
 try:fn();out[name]={"refused":False}
 except Exception as error:
  reasons=[];seen=set();cause=error
  while cause is not None and id(cause) not in seen:
   seen.add(id(cause));reasons.append(str(cause));cause=cause.__cause__ or cause.__context__
  out[name]={"refused":True,"reason":str(error),"cause":"; ".join(reasons)}
print(json.dumps(out))
'''
    result = subprocess.run([str(python), '-I', '-c', code, str(project), json.dumps(page)],
                            capture_output=True, text=True, check=True)
    outcomes = json.loads(result.stdout)
    assert len(outcomes) == 6 and all(item['refused'] for item in outcomes.values())
    assert all('minimum writer' in (item['reason'] + item['cause']) for item in outcomes.values())
    assert store.load_document() == protected
