"""Engineering contracts only; Chinese calibration is not model-effectiveness evidence."""
import copy
import hashlib
import shutil

import pytest

from deck_master import method_resources as methods
from deck_master import resource_catalog as catalog

RESOURCE = 'expression-review-humanizer'


@pytest.mark.parametrize('phase', ['framing', 'argument', 'page_copy', 'speech', 'input_revision'])
def test_content_explicit_selection_only(phase):
    defaults = methods.method_resources('compose', phase=phase)
    assert RESOURCE not in {r['id'] for r in defaults}
    selected = methods.method_resources('compose', phase=phase, selected_resource_ids=[RESOURCE])
    assert [r['id'] for r in selected] == [r['id'] for r in defaults] + [RESOURCE]
    row = selected[-1]
    assert row['sha256'] == hashlib.sha256((methods.resolve_root() / row['relative_path']).read_bytes()).hexdigest()


@pytest.mark.parametrize('unit', ['content', 'argument', 'page_copy', 'progression', 'speech'])
@pytest.mark.parametrize('protocol', [None, 'work_context.v2'])
def test_read_only_review_entry_and_bytes(unit, protocol):
    result = methods.read_skill_methods('deck-review', review_units=[unit],
        selected_resource_ids=[RESOURCE], read_protocol=protocol)
    entries = result['entry_methods'] if protocol else result['methods']
    assert entries[-1]['id'] == RESOURCE
    # The existing read interface requires no project and dispatches no task.
    if protocol:
        assert result['context_ready'] is True
        assert any(RESOURCE in body['content'] for body in result['bodies'].values())
    else:
        assert 'Review 严格只读，不自动写回' in entries[-1]['content']


@pytest.mark.parametrize('options', [
    dict(skill='deck-design'),
    dict(skill='deck-review', review_stage='page_visual'),
    dict(skill='deck-review', review_units=['visual_expression']),
    dict(skill='deck-review', review_units=['readability']),
])
def test_visual_and_design_scopes_cannot_select(options):
    with pytest.raises(ValueError, match='outside'):
        methods.read_skill_methods(**options, selected_resource_ids=[RESOURCE])


def test_frozen_old_task_not_supplemented_and_selected_hash_drift(monkeypatch, tmp_path):
    old = dict(kind='review', review_units=['page_copy'])
    methods.freeze_task_methods(old)
    before = copy.deepcopy(old)
    assert RESOURCE not in {r['id'] for r in methods.resolve_task_methods(old)['methods']}
    assert old == before
    with pytest.raises(ValueError, match='frozen Task'):
        methods.read_skill_methods('deck-review', project='unused', task_id='existing', selected_resource_ids=[RESOURCE])
    selected = dict(kind='review', review_units=['page_copy'])
    methods.freeze_task_methods(selected, selected_resource_ids=[RESOURCE])
    original = copy.deepcopy(selected)
    root = tmp_path / 'methods'
    shutil.copytree(methods.resolve_root(), root)
    monkeypatch.setattr(methods, 'resolve_root', lambda: root)
    (root / 'references/expression-review-humanizer.md').write_text('changed')
    assert methods.resolve_task_methods(selected)['basis_status'] == 'basis_changed'
    assert selected == original
    assert methods.resolve_task_methods(old)['basis_status'] == 'current'


def test_public_skills_and_method_card_count_unchanged():
    resources = catalog.load_catalog(methods.resolve_root())
    assert len(catalog.PUBLIC_SKILLS) == 4
    assert len([mid for mid in resources if mid.startswith('content-m') and mid[9:].isdigit()]) == 10
    assert resources[RESOURCE]['dependencies'] == []
