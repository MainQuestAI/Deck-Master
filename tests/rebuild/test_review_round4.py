"""Migration coverage and enforceable page limits before merge."""
import os

import pytest

from deck_master import install, service, tasks
from deck_master.editing import check_summary
from test_install_host_skill import _build_legacy_layout, _make_release
from test_flow_quality import _setup_project_with_pages, _raw_commit, _load_fixture


@pytest.mark.parametrize('deferred', [False, True])
def test_migrate_ppt_links_with_ownership_and_optout(tmp_path, monkeypatch, deferred):
    prefix, codex = tmp_path / 'prefix', tmp_path / 'codex'
    monkeypatch.setenv('CODEX_HOME', str(codex))
    _build_legacy_layout(prefix, codex)
    _make_release(prefix, 'new')
    names = ['ppt-' + suffix for suffix in ('master', 'library', 'deck-pro-max', 'quality-gate')]
    root = prefix / '.deck-master'
    for name in names:
        (codex / 'skills' / name).symlink_to(root / 'current/skills' / name)
    foreign = codex / 'skills/ppt-foreign'
    foreign.symlink_to(tmp_path / 'other/current/skills/ppt-foreign')
    (codex / 'skills/ppt-user').mkdir()
    if deferred:
        result = install.activate(prefix, 'new', register_host=False)
        assert result['migration']['removed_links'] == []
        assert all((codex / 'skills' / n).is_symlink() for n in names)
    result = install.activate(prefix, 'new')
    assert len(result['migration']['removed_links']) == 19
    assert all(not (codex / 'skills' / n).is_symlink() for n in names)
    assert os.readlink(foreign) == str(tmp_path / 'other/current/skills/ppt-foreign')
    assert (codex / 'skills/ppt-user').is_dir()
    assert install.activate(prefix, 'new')['migration']['removed_links'] == []


def test_page_limit_rejects_full_import(tmp_path):
    project, store, _ = _setup_project_with_pages(tmp_path)
    _raw_commit(store, lambda d: d['task'].update(page_limit=2))
    before = store.load_document()
    with pytest.raises(tasks.EnvelopeError, match='page_limit'):
        service.import_draft(project, draft_payload=_load_fixture('initial-pages.json'))
    assert store.load_document()['pages'] == before['pages']
    assert store.load_document()['content_basis'] == before['content_basis']


def test_page_limit_rejects_unchanged_revision_then_accepts_reduction(tmp_path):
    project, store, _ = _setup_project_with_pages(tmp_path)
    task = service.inputs_update(project, patch={'reason': 'shorter', 'task_patch': {'page_limit': 2}},
                                 base_revision=store.load_document()['revision_id'], operation_id='shorten')['pending_tasks'][0]
    stored = tasks._lookup_task(store.load_document(), task['task_id'], store)
    before = store.load_document()
    update = {'input_digest': stored['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
              'page_order': ['p01','p02','p03'], 'unchanged_reason': 'no change'}
    def accept():
        return service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                                     produced_against=task['produced_against'], result_payload={'kind': 'compose','content_update': update})
    with pytest.raises(tasks.EnvelopeError, match='page_limit'):
        accept()
    assert store.load_document() == before
    update.update(page_order=['p01','p02'], remove_page_ids=['p03'])
    assert accept()['status'] == 'accepted'
    assert len(store.load_document()['pages']) == 2


def test_existing_overlimit_cannot_pass_summary(tmp_path):
    project, store, _ = _setup_project_with_pages(tmp_path)
    _raw_commit(store, lambda d: d['task'].update(page_limit=2))
    summary = check_summary(store, store.load_document())
    assert summary['status'] == 'fail'
    assert 'page_limit' in summary['reason']


def test_ppt_links_restored_after_failed_registration(tmp_path, monkeypatch):
    prefix, codex = tmp_path / 'prefix', tmp_path / 'codex'
    monkeypatch.setenv('CODEX_HOME', str(codex))
    _build_legacy_layout(prefix, codex)
    _make_release(prefix, 'new')
    link = codex / 'skills/ppt-retired'
    target = str(prefix / '.deck-master/current/skills/ppt-retired')
    link.symlink_to(target)
    def fail(*args, **kwargs):
        raise OSError('injected registration')
    monkeypatch.setattr(install, '_sync_host_skill', fail)
    with pytest.raises(OSError, match='injected'):
        install.activate(prefix, 'new')
    assert os.readlink(link) == target
    assert (prefix / '.deck-master/current/companion-manifest.json').is_file()
    assert not list((prefix / '.deck-master').glob('legacy-companion-*'))


@pytest.mark.parametrize('limit', [None, 3, 4])
def test_full_import_at_or_under_limit_remains_accepted(tmp_path, limit):
    project, store, _ = _setup_project_with_pages(tmp_path)
    _raw_commit(store, lambda d: d['task'].update(page_limit=limit))
    assert service.import_draft(project, draft_payload=_load_fixture('initial-pages.json'))['status'] == 'accepted'


def test_initial_compose_cannot_exceed_limit(tmp_path):
    project = tmp_path / 'project'
    service.create(project, brief='two pages only', page_limit=2)
    task = service.continue_project(project)['pending_tasks'][0]
    with pytest.raises(tasks.EnvelopeError, match='page_limit'):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                              produced_against=task['produced_against'],
                              result_payload={'kind': 'compose', **_load_fixture('initial-pages.json')})


def test_existing_overlimit_blocks_delivery_and_handoff(tmp_path):
    from deck_master.editing import export_project
    from deck_master.handoff import check_handoff
    from deck_master.store import StoreError
    from test_flow_quality import _force_fake_output
    project, store, _ = _setup_project_with_pages(tmp_path)
    _force_fake_output(store)
    def historical_overlimit(doc):
        from deck_master.models import compute_input_digest
        doc['task']['page_limit'] = 2
        doc['content_basis']['input_digest'] = compute_input_digest(doc)
    _raw_commit(store, historical_overlimit)
    doc = store.load_document()
    with pytest.raises(StoreError, match='page_limit'):
        export_project(project, output_dir=tmp_path / 'delivery', purpose='delivery')
    assert not (tmp_path / 'delivery').exists()
    output = tmp_path / 'existing.pptx'
    output.write_bytes(store.read_object_bytes(store.read_object_json(doc['outputs']['pptx'])['file']))
    result = check_handoff(project, file_path=output, purpose='delivery')
    assert result['status'] == 'blocked' and result['review_status'] == 'fail'
