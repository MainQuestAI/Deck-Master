"""Exact recorded text descriptors and narrowly verified prompt sections."""
from __future__ import annotations

import json

from .content import visible_atoms
from .models import canonical_json_bytes, sha256_bytes


def descriptor(ref, locator, text, **extra):
    return {'ref': ref, 'locator': locator, 'text': text,
            'text_sha256': sha256_bytes(text.encode('utf-8')), 'code_point_length': len(text), **extra}


def prompt_sections(request):
    """Only the versioned core projection format is eligible. Arbitrary text stays whole."""
    text = request['prompt']
    projection = request.get('projection')
    if (request.get('schema_version') != 'deck_blueprint_request.v1' or not isinstance(projection, dict)
            or sha256_bytes(canonical_json_bytes(projection)) != request.get('projection_sha256')):
        return {'state': 'unstructured', 'segments': []}
    suffix = 'Structured input:\n' + json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True)
    if not text.endswith(suffix):
        return {'state': 'unstructured', 'segments': []}
    offset = len(text) - len(suffix)
    return {'state': 'verified_core_projection', 'segments': [
        {'label': 'instructions', 'start': 0, 'end': offset},
        {'label': 'structured_input', 'start': offset, 'end': len(text)}]}


def projection(entry, page, prompts, generation):
    content = [descriptor(entry['page'], atom['pointer'], atom['text'], atom_id=atom['atom_id'], kind=atom['kind'])
               for atom in visible_atoms(page)] if page else []
    prepared = [descriptor(p['ref'], '/prompt', p['text']) for p in prompts['prepared']]
    prepared += [descriptor(r['ref'], '/input/prompt', r['input']['prompt']) for r in generation['requests']]
    submitted = prompts['submitted']
    return {'content': content, 'prepared_prompt': prepared,
            'submitted_prompt': [descriptor(submitted['ref'], '', submitted['text'])] if submitted['state'] == 'recorded' else []}
