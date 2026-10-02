"""Personal result receipts; never a task, candidate or quality decision."""
from __future__ import annotations

from .local_state import LocalStateConflict, LocalStateError, local_lock, read_json, safe_path, write_json
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import load_snapshot, READ_FAILURES
from .ui_journal import context


def key(task):
    return sha256_bytes(canonical_json_bytes([task['task_id'],task['operation_id'],[r['sha256'] for r in task.get('result_refs',[])]]))


def _file(store):return safe_path(store.deck_root,'workbench','result-reading.json')


def _etag(record):return sha256_bytes(canonical_json_bytes({k:v for k,v in record.items() if k!='etag'}))


def _empty(doc,identity):
    record={'schema_version':'result_reading.v1','project_id':doc['project_id'],'project_identity':identity,'sequence':0,'seen':[]}
    return {**record,'etag':_etag(record)}


def _read(store,doc,identity):
    record=read_json(_file(store)) or _empty(doc,identity)
    validate_schema('result_reading',record)
    if record['project_id']!=doc['project_id'] or record['project_identity']!=identity:
        raise LocalStateError('project_identity','result reading record belongs to another project')
    if record['etag']!=_etag(record):raise LocalStateError('result_reading','invalid reading digest; preserve for recovery')
    return record


def get(project, *, expected_etag=None):
    store,doc,identity=context(project);record=_read(store,doc,identity)
    if expected_etag is not None and expected_etag!=record['etag']:
        raise LocalStateConflict('reading_etag','reading state changed; reload this list before continuing')
    return record


def _readable_tasks(store,document):
    for ref in document['tasks']:
        try:
            task=store.read_object_json(ref)
            validate_schema('task',task)
        except READ_FAILURES:
            # A receipt requires a verified target, not every unrelated task.
            # Preserve damaged objects and let their own result remain unread.
            continue
        yield task


def mark(project, *, project_identity, revision, task_id, result_key, expected_etag):
    store,doc,identity=context(project)
    if project_identity!=identity:raise LocalStateError('project_identity','reading request belongs to another project')
    fixed=load_snapshot(store,revision)
    task=next((v for v in _readable_tasks(store,fixed) if v['task_id']==task_id),None)
    if not task or not task.get('result_refs') or key(task)!=result_key:
        raise LocalStateConflict('result_key','task result identity changed; read the exact result before marking')
    with local_lock(safe_path(_file(store).parent,'result-reading.lock')):
        record=_read(store,doc,identity)
        # CAS is checked before idempotence, including after a preference clear.
        if expected_etag!=record['etag']:raise LocalStateConflict('reading_etag','reading state changed; reload before marking')
        if result_key not in record['seen']:
            record={**record,'seen':[*record['seen'],result_key][-5000:],'sequence':record['sequence']+1}
            record['etag']=_etag(record);write_json(_file(store),record)
    return record


def _clear(store,doc,identity):
    try:record=_read(store,doc,identity)
    except (LocalStateError,ValueError,KeyError,TypeError):return
    record={**record,'seen':[],'sequence':record['sequence']+1};record['etag']=_etag(record)
    write_json(_file(store),record)


def import_legacy(project, *, draft_id, project_identity, expected_etag):
    """Explicit import of a validated saved draft; reading never migrates it."""
    import json
    from . import ui_journal
    store,doc,identity=context(project)
    if identity!=project_identity:raise LocalStateError('project_identity','foreign reading request')
    record=ui_journal.get(project,draft_id)['record']
    if not record:raise LocalStateError('draft_id','saved draft is required')
    draft=record['draft'];fixed=load_snapshot(store,draft['base_revision'])
    tasks={t['task_id']:t for t in _readable_tasks(store,fixed) if t.get('result_refs')}
    verified=[]
    for raw in draft['content'].get('run_desk',{}).get('seen',[]):
        try:tid,hashes=json.loads(raw)
        except (ValueError,TypeError):continue
        if not isinstance(tid,str) or not isinstance(hashes,list):continue
        task=tasks.get(tid)
        if task and hashes==[r['sha256'] for r in task['result_refs']]:verified.append(key(task))
    with local_lock(safe_path(_file(store).parent,'result-reading.lock')):
        current=_read(store,doc,identity)
        if expected_etag!=current['etag']:raise LocalStateConflict('reading_etag','reading state changed; reload before importing')
        seen=list(dict.fromkeys([*current['seen'],*verified]))[-5000:]
        if seen==current['seen']:return {'reading':current,'verified_count':len(verified)}
        updated={**current,'seen':seen,'sequence':current['sequence']+1}
        updated['etag']=_etag(updated);write_json(_file(store),updated)
    return {'reading':updated,'verified_count':len(verified)}
