"""RP-12/RP-14 cross-commit integration regression, synthetic only."""
from deck_master import native_review
from test_native_review import native
from test_content_preproduction_review import _deck
from test_rp14_effective_requirements import decision
from test_selective_content_review import recheck_owners


def test_new_speech_requirement_dispatches_only_speech_then_rechecks(tmp_path, native, monkeypatch):
    project, store = _deck(tmp_path)
    native_review.run(project)
    old_refs = list(store.load_document()['reviews'])
    decision(project, store, 'new-speech-requirement', topic='speech', layers=('speech',))
    recheck_owners(monkeypatch)
    result = native_review.run(project)
    assert native.calls[-1]['packet']['required_units'] == ['speech']
    assert result['preproduction']['status'] == 'pass'
    assert store.load_document()['reviews'][:4] == old_refs
    assert len(store.load_document()['reviews']) == 5
