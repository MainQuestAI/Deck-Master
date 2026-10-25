"""#138 / RP11: real Store source-only repairs retain owner and currentness gates."""
import copy

import pytest

from deck_master.editing import _current_artifact_digests
from deck_master.review import finding_closed
from test_content_preproduction_review import _deck, _review
from test_workbench_reads import commit


@pytest.mark.parametrize('kind,deck_level', [('page_copy', False), ('speech', False), ('page_copy', True)])
@pytest.mark.parametrize('mutation,closed', [
    ('locator', True), ('unchanged', False), ('speaker_notes', False),
    ('other_page', False), ('metadata', False), ('old_evidence', False),
    ('old_dependencies', False), ('wrong_owner', False), ('wrong_finding', False),
    ('unrelated_content_finding', False),
])
def test_source_only_repair_requires_current_same_page_and_original_identity(tmp_path, mutation, closed, kind, deck_level):
    _, store = _deck(tmp_path)
    before = store.load_document()
    finding = {'finding_id': 'SOURCE-01', 'kind': 'source', 'impact': 'must_fix',
               'resolution': 'open', 'page_id': 'p1',
               'element_refs': ['atom:p1:block:b1:text'], 'message': 'Wrong source locator',
               'actual': 'L1', 'expected': 'L2', 'evidence': [before['pages'][0]['page']]}
    if mutation == 'unrelated_content_finding':
        finding['kind'] = 'content'
    if deck_level:
        finding['page_id'] = None
        if mutation == 'other_page':
            closed = True  # Whole-manuscript owner includes both pages.
    reviewer = {'type': 'host_self', 'id': 'synthetic-author',
                'execution_ref': 'synthetic-author', 'assurance': 'host_attested',
                'independence_confirmed': False, 'identity_receipt': None}
    owner = _review(store, before, kind, reviewer=reviewer, status='fail', findings=[finding])
    owner['ref'] = store.put_json_object(owner)
    doc = copy.deepcopy(before)
    index = 1 if mutation == 'other_page' else 0
    page = store.read_object_json(doc['pages'][index]['page'])
    if mutation == 'speaker_notes':
        page['speaker_notes'] += ' Only verified current evidence supports this claim.'
        closed = kind == 'speech'
    elif mutation == 'metadata':
        page['visual_spec']['production_note'] = 'audit only'
    elif mutation != 'unchanged':
        link = page['content_mapping']['visible_links'][1]['source_links'][0]
        link['locator'] = 'L2'
    doc['pages'][index]['page'] = store.put_json_object(page)
    commit(store, doc, 'synthetic-source-repair')
    doc = store.load_document()
    fixed = {**finding, 'resolution': 'fixed', 'evidence': [doc['pages'][0]['page']]}
    candidate = _review(store, doc, kind, reviewer=reviewer, findings=[fixed])
    candidate['replaces'] = owner['ref']
    if mutation == 'old_evidence':
        fixed['evidence'] = finding['evidence']
    if mutation == 'old_dependencies':
        candidate['dependencies'] = owner['dependencies']
    if mutation == 'wrong_owner':
        candidate['replaces'] = store.put_json_object({'other': 'owner'})
    if mutation == 'wrong_finding':
        fixed['finding_id'] = 'OTHER-01'
    candidate['ref'] = store.put_json_object(candidate)
    artifacts = _current_artifact_digests(store, doc, [*owner['subjects'], *candidate['subjects']])
    assert finding_closed([owner, candidate], owner, finding, artifacts) is closed
    if closed:
        # Exercise the actual review receiver, beyond the derived predicate.
        from deck_master.tasks import _adopt_review
        accepted_review = _adopt_review(store, {k: v for k, v in candidate.items() if k != 'ref'})
        assert accepted_review['replaces'] == owner['ref']
