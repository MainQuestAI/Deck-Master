"""History observations must describe revision facts, not project creation."""
import copy
import uuid
from test_styles import flow, mutate  # noqa: F401
from deck_master import editing
from deck_master.models import bump_revision


def test_relevant_history_keeps_content_changes_and_excludes_task_only(flow):
    before = flow.store.load_document()
    mutate(flow, 'p02')
    changed = flow.store.load_document()
    updated = bump_revision(changed, {'operation_id':str(uuid.uuid4()), 'kind':'task_update', 'description':'only execution state', 'read_set':[]})
    flow.store.commit_change(base_revision=changed['revision_id'],document=updated,operation_id=updated['change']['operation_id'])
    result = editing.history(flow.project,page_id='p02',limit=1)
    row = result['revisions'][0]
    assert row['revision_id'] == changed['revision_id']
    assert row['changed_pages'][0]['layers'] == ['content']
    assert row['committed_at'] and row['committed_at'] != before['created_at']
    assert row['created_at'] == before['created_at']
    assert result['current'] == updated['revision_id']
    assert editing.history(flow.project,page_id='p01',limit=10)['revisions'][0]['revision_id'] != changed['revision_id']
    assert editing.history(flow.project,page_id='p02')['revisions'] == editing.history(flow.project,page_id='p02',limit=100)['revisions']
    assert editing.history(flow.project,layer='content')['revisions'] == editing.history(flow.project,layer='content',limit=100)['revisions']
    assert len(editing.history(flow.project)['revisions']) > len(editing.history(flow.project,page_id='p02')['revisions'])
    assert editing.history(flow.project,page_id='p02',related_only=False)['revisions'][0]['revision_id'] == updated['revision_id']


def test_old_history_time_is_not_invented(flow):
    old=flow.store.load_document()
    row=editing.history(flow.project)['revisions'][0]
    assert row['committed_at'] == old.get('committed_at')
