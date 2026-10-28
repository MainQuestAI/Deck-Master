"""Public UI fixture preparation must honor the current effective direction."""
from deck_master import content_review
from deck_master.samples import create_sample
from deck_master.store import Store
from test_action_targets_browser import _prepare_browser_project
from candidate_fixtures import candidate


def test_confirmed_browser_direction_is_reviewed_before_svg_candidate_dispatch(tmp_path):
    project = tmp_path / 'project'
    create_sample(project, page_count=3, readonly=False)
    _prepare_browser_project(project)
    store = Store(project)
    current = store.load_document()
    assert content_review.preproduction_status(store, current)['status'] == 'pass'
    assert candidate(store, width=20)
