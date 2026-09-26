"""Personal gallery selections: separate from Document and recipe truth."""
from __future__ import annotations

from .local_state import LocalStateConflict, LocalStateError, local_lock, read_json, safe_path, write_json
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import load_snapshot
from .ui_journal import context, _base_refs


def _file(store):
    return safe_path(store.deck_root, 'workbench', 'gallery.json')


def _validate(store, current, identity, state):
    validate_schema('ui_gallery', state)
    if state['project_id'] != current['project_id'] or state['project_identity'] != identity:
        raise LocalStateError('project_identity', 'gallery state belongs to another project')
    base = load_snapshot(store, state['revision_id'])
    ids = {entry['page_id'] for entry in base['pages']}
    selected = set(state['selected_page_ids'])
    if not selected <= ids:
        raise LocalStateError('selected_page_ids', 'selected page is not in the fixed version')
    if state['anchor']['page_id'] is not None and state['anchor']['page_id'] not in ids:
        raise LocalStateError('anchor/page_id', 'reading anchor is not in the fixed version')
    if state['mode'] == 'compare' and len(selected) < 2:
        raise LocalStateError('selected_page_ids', 'comparison requires two to four pages')
    if state['filter']['chapter_id'] is not None:
        from .content_plan import projection
        chapters = {item['chapter_id'] for item in projection(store, base).get('chapters', [])}
        if state['filter']['chapter_id'] not in chapters:
            raise LocalStateError('filter/chapter_id', 'chapter is not in the fixed content plan')
    seen = set()
    for reference in state['references']:
        page_id = reference['page_id']
        if page_id in seen:
            raise LocalStateError('references', 'each personal reference page is listed once')
        seen.add(page_id)
        doc = load_snapshot(store, reference['revision_id'])
        refs = _base_refs(store, doc, {'scope': 'page', 'page_id': page_id, 'layer': 'original_image'})
        if reference['original_ref'] not in refs:
            raise LocalStateError('references/original_ref', 'reference is not that page original at its fixed version')
        store.read_object_bytes(reference['original_ref'])


def _read(store, current, identity):
    record = read_json(_file(store))
    if record is None:
        return None
    if set(record) != {'schema_version', 'state', 'etag', 'sequence'} or record['schema_version'] != 'ui_gallery_record.v1':
        raise LocalStateError('gallery', 'invalid personal gallery record; preserve it for recovery')
    if type(record['sequence']) is not int or record['sequence'] < 1:
        raise LocalStateError('gallery', 'invalid personal gallery sequence')
    expected = sha256_bytes(canonical_json_bytes({'state': record['state'], 'sequence': record['sequence']}))
    if expected != record['etag']:
        raise LocalStateError('gallery', 'personal gallery record hash mismatch')
    validate_schema('ui_gallery', record['state'])
    if record['state']['project_id'] != current['project_id'] or record['state']['project_identity'] != identity:
        raise LocalStateError('project_identity', 'gallery record belongs to another project')
    return record


def get(project):
    store, current, identity = context(project)
    record = _read(store, current, identity)
    issues = []
    if record is not None:
        try:
            _validate(store, current, identity, record['state'])
        except (OSError, RuntimeError, ValueError):
            issues.append({'code': 'gallery_basis_unavailable', 'message': 'saved selection is retained; a fixed page, chapter or reference is no longer readable'})
    return {'project_id': current['project_id'], 'project_identity': identity, 'record': record, 'issues': issues}


def save(project, *, state, expected_etag=None):
    store, current, identity = context(project)
    _validate(store, current, identity, state)
    path = _file(store)
    with local_lock(safe_path(path.parent, 'gallery.lock')):
        previous = _read(store, current, identity)
        if previous and previous['state'] == state:
            return {'status': 'saved', 'record': previous, 'replayed': True}
        if expected_etag != (previous['etag'] if previous else None):
            raise LocalStateConflict('expected_etag', 'another window saved different personal gallery state')
        sequence = previous['sequence'] + 1 if previous else 1
        record = {'schema_version': 'ui_gallery_record.v1', 'state': state, 'sequence': sequence,
                  'etag': sha256_bytes(canonical_json_bytes({'state': state, 'sequence': sequence}))}
        write_json(path, record)
    return {'status': 'saved', 'record': record, 'replayed': False}
