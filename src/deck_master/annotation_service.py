"""Version-bound opinions. Saving opinions never dispatches or invalidates work."""
from __future__ import annotations

import copy
import io
import uuid

from . import operations, text_ranges
from .local_state import project_path
from .models import bump_revision, validate_schema
from .snapshots import load_snapshot
from .store import Store
from .ui_journal import _base_refs


def invalid(field, message):
    raise operations.OperationError('annotation_invalid', field, message)


def validate(store, current, note):
    validate_schema('annotation', note)
    if note['project_id'] != current['project_id']:
        invalid('project_id', 'opinion belongs to another project')
    if not note['intent'].strip() or not note['body'].strip():
        invalid('body', 'opinion intent and body must contain text')
    base = load_snapshot(store, note['base_revision'])
    scope = note['scope']; location = note['location']; kind = location['kind']
    permitted = {'project': set(), 'chapter': {'chapter_id', 'content_plan_ref'},
                 'page': {'page_id', 'page_ref'},
                 'artifact': {'page_id', 'page_ref', 'layer', 'artifact_ref'}}[scope]
    fields = {'chapter_id', 'content_plan_ref', 'page_id', 'page_ref', 'layer', 'artifact_ref'}
    if (set(note) & fields) != permitted:
        invalid('scope', 'scope requires only its exact identity fields')
    if scope == 'chapter':
        if base.get('content_plan') != note['content_plan_ref']:
            invalid('content_plan_ref', 'chapter plan is not the plan in this fixed version')
        plan = store.read_object_json(note['content_plan_ref']); validate_schema('content_plan', plan)
        if note['chapter_id'] not in {c['chapter_id'] for c in plan['input']['chapters']}:
            invalid('chapter_id', 'chapter does not exist in the bound plan')
    if scope in ('page', 'artifact'):
        entry = next((e for e in base['pages'] if e['page_id'] == note['page_id']), None)
        if entry is None or entry['page'] != note['page_ref']:
            invalid('page_ref', 'page reference does not belong to this fixed version')
    if scope == 'artifact':
        refs = _base_refs(store, base, {'scope': 'page', 'page_id': note['page_id'], 'layer': note['layer']})
        if note['artifact_ref'] not in refs:
            invalid('artifact_ref', 'reference does not belong to this page, layer and fixed version')
        if kind == 'text':
            if location['range']['ref'] != note['artifact_ref']:
                invalid('location/range/ref', 'text range must use the exact selected reference')
            text_ranges.validate(store.project_root, page_id=note['page_id'], layer=note['layer'],
                                 revision_id=note['base_revision'], selection=location['range'])
        if kind in ('point', 'rect'):
            if note['layer'] not in ('original_image', 'svg', 'ppt'):
                invalid('location', 'geometric selection requires an image layer')
            slot = {'original_image': 'blueprint', 'svg': 'svg', 'ppt': 'ppt_preview'}[note['layer']]
            artifact = store.read_object_json(entry[slot]); validate_schema('artifact', artifact)
            raw = store.read_object_bytes(artifact['file'])
            if note['layer'] == 'svg':
                import re
                import math
                from xml.etree import ElementTree
                if re.search(br'<!\s*(DOCTYPE|ENTITY)', raw, re.I):
                    invalid('location/canvas', 'SVG entities are not supported')
                root = ElementTree.fromstring(raw)
                box = [float(value) for value in re.split(r'[\s,]+', root.get('viewBox', '').strip()) if value]
                if len(box) != 4 or not all(math.isfinite(v) for v in box) or min(box[2:]) <= 0:
                    invalid('location/canvas', 'SVG requires an explicit finite viewBox')
                dimensions = tuple(box[2:])
            else:
                from PIL import Image
                with Image.open(io.BytesIO(raw)) as image:
                    dimensions = image.size
            if (location['canvas']['width'], location['canvas']['height']) != dimensions:
                invalid('location/canvas', 'canvas dimensions differ from the fixed original')
            if kind == 'rect' and (location['x'] + location['width'] > 1 or location['y'] + location['height'] > 1):
                invalid('location', 'normalized rectangle extends outside the original canvas')
    return copy.deepcopy(note)


@operations.public
def save(project, *, input, base_revision, operation_id):
    operations.validate_id(operation_id, new=True)
    validate_schema('annotation_batch', input)
    store = Store(project_path(project))
    with store._locked():
        document = store.load_document()
        digest = operations.request_digest(document, 'annotations.save', base_revision, input)
        previous = operations.recover(store, operation_id, digest)
        if previous:
            return previous
        if document.get('compatibility', {}).get('project_format') != 'workbench.v3':
            invalid('project', 'new opinion writes require an explicit workbench.v3 project')
        if document['revision_id'] != base_revision:
            raise operations.OperationError('conflict', 'base_revision', 'project changed; reload before saving', exit_code=5)
        if input['project_id'] != document['project_id']:
            invalid('project_id', 'batch belongs to another project')
        notes = [validate(store, document, note) for note in input['annotations']]
        existing = {store.read_object_json(ref)['annotation_id'] for ref in document.get('annotations', [])}
        ids = set()
        for note in notes:
            note.setdefault('annotation_id', 'note-' + uuid.uuid4().hex)
            if note['annotation_id'] in existing or note['annotation_id'] in ids:
                invalid('annotation_id', 'opinion IDs must be new and unique; historical opinions are immutable')
            ids.add(note['annotation_id'])
        refs = [store.put_json_object(note) for note in notes]
        updated = bump_revision(document, {'operation_id': operation_id, 'kind': 'review_update',
                                           'description': 'Opinions saved without execution', 'read_set': []})
        updated['annotations'] = [*document.get('annotations', []), *refs]
        result = {'status': 'saved', 'revision_id': updated['revision_id'],
                  'annotations': [{'annotation_id': note['annotation_id'], 'ref': ref} for note, ref in zip(notes, refs)]}
        return operations.commit_locked(store, document=updated, base_revision=base_revision,
                                        operation_id=operation_id, kind='annotations.save', digest=digest, result=result)


@operations.public
def list_annotations(project, *, revision=None):
    store = Store(project_path(project)); document = load_snapshot(store, revision)
    records = []
    for ref in document.get('annotations', []):
        note = store.read_object_json(ref)
        validate(store, document, note)
        records.append({'ref': ref, 'annotation': note})
    return {'project_id': document['project_id'], 'revision_id': document['revision_id'], 'annotations': records}
