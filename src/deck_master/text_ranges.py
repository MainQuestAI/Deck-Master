"""Exact Unicode code-point ranges over recorded text; never OCR or fuzzy match."""
from __future__ import annotations

import copy

from .content import visible_atoms
from .local_state import LocalStateError
from .models import sha256_bytes, validate_schema
from .snapshots import load_snapshot
from .store import Store
from .ui_journal import _base_refs


class TextRangeError(LocalStateError):
    error_code = 'text_range_invalid'


def text_digest(text):
    try:
        return sha256_bytes(text.encode('utf-8'))
    except (AttributeError, UnicodeError) as error:
        raise TextRangeError('text', 'source must be valid original UTF-8 text') from error


def validate(project, *, page_id, layer, revision_id, selection):
    """Read-only validation shared with W06's future opinion transaction.

    Offsets are Python string indices (Unicode code points). CRLF and combining
    characters are preserved. The locator names a real stored text field.
    """
    validate_schema('text_range', selection)
    if not isinstance(revision_id, str) or not revision_id:
        raise TextRangeError('revision_id', 'a fixed committed revision is required')
    if layer not in ('content', 'prepared_prompt', 'submitted_prompt'):
        raise TextRangeError('layer', 'images and previews have no recorded text selection layer')
    store = Store(project); document = load_snapshot(store, revision_id)
    target = {'scope': 'page', 'page_id': page_id, 'layer': layer}
    if selection['ref'] not in _base_refs(store, document, target):
        raise TextRangeError('ref', 'text reference is not bound to this page, layer and fixed version')
    locator = selection['locator']
    if layer == 'submitted_prompt':
        if locator != '':
            raise TextRangeError('locator', 'submitted text requires the raw text-object locator')
        try:
            text = store.read_object_bytes(selection['ref']).decode('utf-8')
        except UnicodeError as error:
            raise TextRangeError('ref', 'recorded prompt is not UTF-8 text') from error
    else:
        obj = store.read_object_json(selection['ref'])
        if layer == 'content':
            fields = {atom['pointer']: atom['text'] for atom in visible_atoms(obj)}
            if locator not in fields:
                raise TextRangeError('locator', 'locator must name one customer-visible text field')
            text = fields[locator]
        elif obj.get('schema_version') == 'generation_request.v1' and locator == '/input/prompt':
            text = obj['input']['prompt']
        elif obj.get('schema_version') == 'deck_blueprint_request.v1' and locator == '/prompt':
            text = obj['prompt']
        else:
            raise TextRangeError('locator', 'locator does not name the recorded prompt field')
    start, end = selection['start'], selection['end']
    if selection['text_sha256'] != text_digest(text):
        raise TextRangeError('text_sha256', 'source text hash changed; select the intended original again')
    if not 0 <= start < end <= len(text) or text[start:end] != selection['excerpt']:
        raise TextRangeError('range', 'code-point bounds and exact original excerpt do not match')
    return {'status': 'valid', 'project_id': document['project_id'], 'revision_id': document['revision_id'],
            'page_id': page_id, 'layer': layer, 'code_point_length': len(text), 'selection': copy.deepcopy(selection)}
