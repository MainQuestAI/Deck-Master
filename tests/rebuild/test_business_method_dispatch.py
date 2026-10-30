"""D02b synthetic mechanism checks; no live model or professional judgments."""
import json
from urllib.request import Request, urlopen

import pytest

from deck_master import cli, content_production, content_review, method_library_view, method_resources
from deck_master import models, native_review, outline_review, review_evidence, service
from deck_master.web import WorkbenchServer
from test_business_framing import SCOPE, adoption_request, pending, project, proposals, submit, v2
from test_content_preproduction_review import _deck
from test_native_review import native  # noqa: F401 - shared explicitly synthetic transport fixture
from test_rc5_resource_catalog import fixture_catalog  # noqa: F401 - isolated canonical method copy
from synthetic_review_provider import synthetic_context, synthetic_runtime_call


def ids(items):
    return [x['id'] for x in items]


def adopted_outline(tmp_path):
    path, store, refs = proposals(tmp_path)
    _, decision = adoption_request(path, store, refs)
    for index, ref in enumerate(refs):
        content_production.adopt_proposal(path,
            input={'proposal_ref': ref, 'decision_ref': decision, 'write_scope': SCOPE},
            base_revision=store.current_revision_id(), operation_id=f'business-adopt-{index}')
    return path, store


def test_new_create_freezes_small_package_without_reopening_old_task(tmp_path):
    (tmp_path / 'old').mkdir()
    (tmp_path / 'new').mkdir()
    old_path, old = project(tmp_path / 'old')
    old_task = pending(old)
    new_path, new = project(tmp_path / 'new', business_framing=True)
    new_task = pending(new)
    assert 'content-examples' in ids(old_task['method_manifest'])
    assert ids(new_task['method_manifest']) == ['source-reading', 'content-methods', 'method-selection', 'content-m01']
    before = old.current_revision_id()
    assert method_resources.read_task_methods(old_path, old_task['task_id'])['work_order']['task_id'] == old_task['task_id']
    assert pending(old) == old_task and old.current_revision_id() == before
    actual = method_resources.read_task_methods(new_path, new_task['task_id'])
    assert actual['status'] == 'current' and ids(actual['methods']) == ids(new_task['method_manifest'])


def test_host_selects_additional_argument_method_before_freeze(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    submit(path, store, task, v2(store.load_document()['project_id'], task=task, maturity='framing'))
    service.continue_project(path, selected_resource_ids=['content-m04'])
    argument = pending(store)
    assert set(ids(argument['method_manifest'])) == {
        'source-reading', 'content-methods', 'method-selection', 'content-m02', 'content-m07', 'content-m08', 'content-m04'}
    with pytest.raises(service.ServiceError, match='frozen'):
        service.continue_project(path, selected_resource_ids=['content-m05'])
    assert pending(store) == argument


def test_preparation_and_skill_reads_negotiate_without_changing_legacy(tmp_path):
    ctx = {'mode': 'independent', 'role': 'deck-content', 'phase': 'framing', 'review_units': []}
    legacy = method_library_view.preview(None, {'context': ctx, 'selected_resource_ids': []})
    new = method_library_view.preview(None, {'context': ctx, 'selected_resource_ids': [], 'business_framing': True})
    assert 'content-examples' in legacy['default_ids'] and 'content-examples' not in new['default_ids']
    handoff = json.loads(new['handoff']['text'].split('```json\n')[1].split('\n```')[0])
    assert method_library_view.preview(None, handoff['preview_request'])['preview_digest'] == new['preview_digest']
    assert handoff['effective_context']['business_framing'] is True
    assert 'content-examples' not in ids(method_resources.read_skill_methods('deck-content', business_framing=True)['methods'])
    negotiated = method_resources.read_skill_methods('deck-content', business_framing=True, read_protocol='work_context.v2')
    assert 'content-examples' not in ids(negotiated['entry_methods'])
    assert 'content-m01' in ids(negotiated['entry_methods'])
    path, store = project(tmp_path, business_framing=True)
    before = store.current_revision_id()
    assert 'content-examples' not in ids(method_resources.read_skill_methods('deck-content', project=path)['methods'])
    assert store.current_revision_id() == before


def test_explicit_examples_still_return_complete_bytes():
    small = method_resources.read_methods('compose', phase='framing', business_framing=True)
    expanded = method_resources.read_methods('compose', phase='framing', business_framing=True,
        selected_resource_ids=['content-examples'])
    old = method_resources.read_methods('compose', phase='framing')
    assert 'content-examples' not in ids(small) and 'content-examples' in ids(expanded)
    assert len(next(x['content'] for x in expanded if x['id'] == 'content-examples')) > 1000
    assert sum(len(x['content'].encode()) for x in small) < sum(len(x['content'].encode()) for x in old)
    for phase in ('speech', 'page_copy'):
        assert method_resources.method_ids_for('compose', phase=phase, business_framing=True) == (
            method_resources.method_ids_for('compose', phase=phase))


def test_selected_complete_case_keeps_all_dependency_bodies():
    rows = method_resources.read_methods('compose', phase='argument', business_framing=True,
        selected_resource_ids=['case-e04-walkthrough'])
    assert ids(rows)[-3:] == ['example-e04-input', 'example-e04-after', 'case-e04-walkthrough']
    assert all(m['content'] and models.sha256_bytes(m['content'].encode()) == m['sha256'] for m in rows)


def test_project_preview_and_dispatch_share_new_contract_and_selection(tmp_path):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    submit(path, store, task, v2(store.load_document()['project_id'], task=task, maturity='framing'))
    req = {'context': {'mode': 'project', 'revision': store.current_revision_id()},
           'selected_resource_ids': ['content-m04']}
    preview = method_library_view.preview(path, req)
    assert preview['dispatch_status'] == 'new_content_task_possible'
    assert 'content-examples' not in preview['default_ids']
    service.continue_project(path, selected_resource_ids=req['selected_resource_ids'])
    assert pending(store)['method_manifest'] == preview['resolved_manifest']


def test_new_method_drift_requires_formal_reissue_and_keeps_original(tmp_path, fixture_catalog):
    root, _ = fixture_catalog
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    original_ref = store.load_document()['tasks'][-1]
    p = root / 'references/methods/M01-framing.md'
    p.write_bytes(p.read_bytes() + b'\nSynthetic engineering-only method drift.\n')
    assert method_resources.resolve_task_methods(task)['basis_status'] == 'basis_changed'
    service.continue_project(path)
    replacement = pending(store)
    assert replacement['task_id'] != task['task_id']
    assert store.read_object_json(original_ref) == task
    assert 'business-framing.v1' in replacement['required_capabilities']
    assert ids(replacement['method_manifest']) == ids(task['method_manifest'])
    assert replacement['method_manifest'] != task['method_manifest']


def test_cli_pre_task_methods_match_real_frozen_package(tmp_path, capsys):
    path, store = project(tmp_path, business_framing=True)
    task = pending(store)
    assert cli.main(['methods', '--business-framing', '--phase', 'framing', '--read']) == 0
    output = json.loads(capsys.readouterr().out)
    assert [{k: m[k] for k in ('id', 'relative_path', 'sha256')} for m in output['methods']] == task['method_manifest']
    assert cli.main(['methods', '--business-framing', '--project', str(path), '--task-id', task['task_id']]) != 0
    capsys.readouterr()


def test_outline_selection_reaches_frozen_task_and_preserves_full_packet(tmp_path):
    path, store = adopted_outline(tmp_path)
    ctx = synthetic_context()
    out = synthetic_runtime_call(outline_review.dispatch, path, adapter_context=ctx,
        selected_resource_ids=['content-m07'])
    task = out['task']
    assert 'business-framing.v1' in task['required_capabilities']
    assert 'content-m07' in ids(task['method_manifest']) and 'content-examples' not in ids(task['method_manifest'])
    packet = outline_review.packet(store, store.load_document())
    assert packet['narrative']['business_frame']['topics']
    assert packet['plan']['input']['page_roles'] and packet['materials']
    before = store.current_revision_id()
    reused = synthetic_runtime_call(outline_review.dispatch, path, adapter_context=ctx)
    assert reused['task'] == task and store.current_revision_id() == before
    with pytest.raises(models.ModelError, match='frozen'):
        synthetic_runtime_call(outline_review.dispatch, path, adapter_context=ctx, selected_resource_ids=['content-m08'])
    assert store.current_revision_id() == before


@pytest.mark.parametrize('subject', [None, 'outline'])
@pytest.mark.parametrize('selection', [['missing-resource'], ['template-page-draft'], 'content-m07'])
def test_invalid_review_selection_refused_before_native_start(tmp_path, monkeypatch, subject, selection):
    path, store = adopted_outline(tmp_path) if subject else _deck(tmp_path)
    before = store.current_revision_id()
    def forbidden():
        pytest.fail('invalid selection must not open a native session')
    monkeypatch.setattr(native_review, 'CodexReviewSession', forbidden)
    with pytest.raises(models.ModelError):
        native_review.run(path, subject=subject, selected_resource_ids=selection)
    assert store.current_revision_id() == before


def test_native_preproduction_selected_methods_are_real_prompt_bytes(tmp_path, native):
    path, store = _deck(tmp_path)
    out = native_review.run(path, selected_resource_ids=['content-m07'])
    assert out['preproduction']['status'] == 'pass'
    assert 'content-m07' in ids(native.calls[0]['methods'])
    assert native.calls[0]['packet']['manuscript']['pages']
    assert native.calls[0]['packet']['materials']
    assert 'content-examples' in ids(native.calls[0]['methods'])  # legacy contract retained


def test_native_pending_selection_cannot_replace_frozen_manifest(tmp_path, native):
    path, store = adopted_outline(tmp_path)
    task = synthetic_runtime_call(outline_review.dispatch, path, adapter_context=synthetic_context(),
        selected_resource_ids=['content-m07'])['task']
    with pytest.raises(review_evidence.EvidenceRejected, match='frozen'):
        native_review.run(path, subject='outline', selected_resource_ids=['content-m08'])
    with pytest.raises(review_evidence.EvidenceRejected, match='frozen'):
        native_review.run(path, task_id=task['task_id'], selected_resource_ids=['content-m07'])
    assert not native.calls
    assert next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                if store.read_object_json(ref)['task_id'] == task['task_id']) == task


def test_completed_observation_recovers_original_methods_without_new_call(tmp_path, native, monkeypatch):
    path, store = _deck(tmp_path)
    def fail_accept(*args, **kwargs):
        raise OSError('synthetic failure after the owned completion')
    with monkeypatch.context() as patch:
        patch.setattr(service, 'accept_result', fail_accept)
        with pytest.raises(OSError):
            native_review.run(path, selected_resource_ids=['content-m07'])
    task = store.read_object_json(store.load_document()['tasks'][-1])
    before = store.load_document()
    with pytest.raises(review_evidence.EvidenceRejected, match='frozen'):
        native_review.run(path, selected_resource_ids=['content-m08'])
    assert store.load_document() == before and len(native.calls) == 1
    recovered = native_review.recover(path, task_id=task['task_id'])
    assert recovered['model_called'] is False
    assert len(native.calls) == 1
    assert store.read_object_json(store.load_document()['tasks'][-1])['method_manifest'] == task['method_manifest']


def test_http_native_outline_selected_methods_use_same_pipeline(tmp_path, native):
    path, store = adopted_outline(tmp_path)
    server = WorkbenchServer(path)
    base = server.start().rstrip('/')
    try:
        token = json.load(urlopen(base + '/api/session'))['token']
        req = Request(base + '/api/reviews/native', json.dumps({'subject': 'outline',
            'selected_resource_ids': ['content-m07']}).encode(),
            {'Content-Type': 'application/json', 'X-Deck-Token': token, 'Origin': base})
        out = json.load(urlopen(req))
        assert out['preproduction']['review_subject'] == 'outline'
        assert 'content-m07' in ids(native.calls[0]['methods'])
        assert 'content-examples' not in ids(native.calls[0]['methods'])
        assert native.calls[0]['packet']['narrative']['business_frame']['topics']
        assert content_review.preproduction_status(store, store.load_document())['status'] == 'no_manuscript'
    finally:
        server.stop()
