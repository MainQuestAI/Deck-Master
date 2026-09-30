"""Ancestry metadata stays fast without trusting replaced/corrupt snapshots."""
import copy
import json
import uuid
import pytest
from deck_master import samples, snapshots, ui_journal
from deck_master.models import bump_revision
from deck_master.store import Store


def advance(store):
    doc = store.load_document()
    changed = bump_revision(copy.deepcopy(doc), {'operation_id':str(uuid.uuid4()), 'kind':'policy_update', 'description':'test', 'read_set':[]})
    store.commit_change(base_revision=doc['revision_id'], document=changed, operation_id=changed['change']['operation_id'])
    return changed


@pytest.fixture
def store(tmp_path):
    project = tmp_path/'project'; samples.create_sample(project, page_count=2, readonly=False)
    store = Store(project)
    for _ in range(12): advance(store)
    return store


def test_advancing_identity_does_not_reparse_all_ancestors(store, monkeypatch):
    identity = ui_journal.project_info(store.project_root)['project_identity']
    base = store.current_revision_id(); advance(store)
    read = snapshots._snapshot; seen=[]
    def observed(store, revision):
        seen.append(revision); return read(store, revision)
    monkeypatch.setattr(snapshots, '_snapshot', observed)
    assert ui_journal.project_info(store.project_root)['project_identity']==identity
    assert base not in seen and len(seen)<=3
    assert snapshots.load_snapshot(store, base)['revision_id']==base
    assert seen.count(base)==1


@pytest.mark.parametrize('damage', ['invalid_ref', 'foreign_project', 'cycle', 'symlink'])
def test_cached_ancestry_is_rechecked_after_external_change(store, damage):
    ui_journal.project_info(store.project_root)
    head=store.load_document(); parent=head['parent_revision_id']; path=store.revisions_dir/(parent+'.json')
    doc=json.loads(path.read_text())
    if damage=='invalid_ref': doc['pages'][0]['page']['path']='/outside/private.json'
    elif damage=='foreign_project': doc['project_id']='another-project'
    elif damage=='cycle': doc['parent_revision_id']=head['revision_id']
    if damage=='symlink':
        moved=path.with_suffix('.backup'); path.rename(moved); path.symlink_to(moved)
    else: path.write_text(json.dumps(doc))
    with pytest.raises((snapshots.ReadModelError, ui_journal.LocalStateError)):
        ui_journal.project_info(store.project_root)
