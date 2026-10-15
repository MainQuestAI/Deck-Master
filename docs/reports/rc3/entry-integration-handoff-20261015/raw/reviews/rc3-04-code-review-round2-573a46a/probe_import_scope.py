"""Independent L1 probe; real services only, no fixture or product edits."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import uuid

from deck_master import collaboration, service
from deck_master.models import canonical_json_bytes
from deck_master.store import Store

OUT = Path(__file__).resolve().parent
project = OUT / 'probe-import-scope-project'

def op():
    return str(uuid.uuid4())

def page(pid):
    return {'schema_version': 'deck_page_package.v2', 'page_id': pid,
        'customer_visible': {'title': 'Fixed visible copy ' + pid, 'body_blocks': []},
        'speaker_notes': 'Original notes ' + pid,
        'visual_spec': {'intent': 'Explicit synthetic L1 manuscript', 'reference_mode': 'new_design'}}

created = service.create(project, brief='Use the fixed two-page manuscript, retain both pages and their notes.',
                         draft={'pages': [page('p1'), page('p2')]})
store = Store(project)
before_request = store.load_document()
source = store.put_blob(b'Change p1 only. Keep all other pages and notes. Do not add, remove, or reorder pages.', ext='txt')
scope = {'subject': 'pages', 'page_ids': ['p1'], 'page_manifest_ref': None,
    'external_artifact_ref': None, 'layers': ['page_copy', 'plan'],
    'allow_page_membership_change': False, 'allow_page_order_change': False, 'purpose': 'working'}
start = collaboration.start_request(project, input={'intent': 'edit', 'content_intent': None,
    'scope': scope, 'replace_request_id': before_request['collaboration']['request']['request_id'],
    'instruction_evidence': {'kind': 'host_attested_instruction', 'source_ref': source,
        'source_locator': 'independent-review:L1-p1-only', 'actor_id': None,
        'transport_receipt_ref': None, 'presentation_ref': None}},
    base_revision=before_request['revision_id'], operation_id=op())
before = store.load_document()
replacement = page('p1')
replacement['customer_visible']['title'] += ' revised'
try:
    response = service.import_draft(project, draft_payload={'pages': [replacement]},
        base_revision=before['revision_id'], operation_id=op())
    error = None
except Exception as exc:
    response = None
    error = {'type': type(exc).__name__, 'message': str(exc)}
after = store.load_document()
result = {'evidence_level': 'L1_SYNTHETIC', 'module': service.__file__,
    'scope': scope, 'create': created, 'start': start,
    'before': before, 'response': response, 'error': error, 'after': after,
    'before_page_ids': [p['page_id'] for p in before['pages']],
    'after_page_ids': [p['page_id'] for p in after['pages']],
    'removed_unselected_page': any(p['page_id'] == 'p2' for p in before['pages']) and not any(p['page_id'] == 'p2' for p in after['pages']),
    'control_unchanged': before['collaboration'] == after['collaboration']}
(OUT / 'probe-import-scope-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('error', 'before_page_ids', 'after_page_ids', 'removed_unselected_page', 'control_unchanged')}, ensure_ascii=False))
