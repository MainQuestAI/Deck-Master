"""Synthetic counters for v1.2 response-local facts and warm projection reuse."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from deck_master import content_review, delivery_eligibility, editing, export_sanitize, workbench
from deck_master.store import Store
from test_x3_design_plan_actions import production_project


def test_v2_builds_artifacts_once_and_warm_read_reuses_projection(tmp_path, monkeypatch):
    project, store = production_project(tmp_path, 'full_deck')
    workbench._summary_cache.clear()
    calls = []
    original = editing._current_artifact_digests
    def counted(*args, **kwargs):
        calls.append(args[1]['revision_id'])
        return original(*args, **kwargs)
    monkeypatch.setattr(editing, '_current_artifact_digests', counted)
    monkeypatch.setattr(content_review, '_current_artifact_digests', counted)
    first = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    assert calls == [store.current_revision_id()]
    assert workbench.workbench_summary(project, protocol='workbench_summary.v2') == first
    assert len(calls) == 1
    workbench._summary_cache.clear()
    assert workbench.workbench_summary(project, protocol='workbench_summary.v2') == first
    assert len(calls) == 2


def test_same_v2_identity_coalesces_builds(tmp_path, monkeypatch):
    project, _ = production_project(tmp_path, 'full_deck')
    workbench._summary_cache.clear()
    entered, release = threading.Event(), threading.Event()
    original = workbench._build_v2_summary
    calls = []
    def blocked(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(workbench, '_build_v2_summary', blocked)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(workbench.workbench_summary, project, protocol='workbench_summary.v2') for _ in range(4)]
        assert entered.wait(5)
        time.sleep(.05)
        release.set()
        results = [future.result(timeout=10) for future in futures]
    assert len(calls) == 1
    assert all(value == results[0] for value in results)
    assert not workbench._summary_inflight


def test_pptx_warm_selection_does_not_read_source_bytes(tmp_path, monkeypatch):
    from test_export import _deck
    _, store = _deck(tmp_path)
    document = store.load_document()
    ref = store.read_object_json(document['outputs']['pptx'])['file']
    delivery_eligibility._projection_cache.clear()
    calls = {'source': 0, 'sanitize': 0}
    original_read, original_pptx = Store.read_object_bytes, export_sanitize.pptx
    def read(self, item):
        if item == ref:
            calls['source'] += 1
        return original_read(self, item)
    def sanitize(*args, **kwargs):
        calls['sanitize'] += 1
        return original_pptx(*args, **kwargs)
    monkeypatch.setattr(Store, 'read_object_bytes', read)
    monkeypatch.setattr(export_sanitize, 'pptx', sanitize)
    first = delivery_eligibility.selected_output(store, document)
    assert calls == {'source': 1, 'sanitize': 1}
    assert delivery_eligibility.selected_output(store, document) == first
    assert calls == {'source': 1, 'sanitize': 1}
    path = store.project_root / ref['path']
    path.write_bytes(path.read_bytes() + b'corrupt')
    with pytest.raises(Exception):
        delivery_eligibility.selected_output(store, document)
    assert calls['source'] == 2


def test_drafts_share_one_history_reader(tmp_path, monkeypatch):
    from deck_master import samples, snapshots, ui_journal
    from test_ui_journal import draft
    project = tmp_path / 'project'
    samples.create_sample(project, page_count=2, readonly=False)
    for index in range(3):
        ui_journal.save(project, draft=draft(project, draft_id=f'd{index}'))
    original = snapshots.FixedSnapshotReader.__init__
    calls = []
    def counted(self, *args, **kwargs):
        calls.append(1)
        original(self, *args, **kwargs)
    monkeypatch.setattr(snapshots.FixedSnapshotReader, '__init__', counted)
    result = ui_journal.list_drafts(project)
    assert len(result['records']) == 3 and not result['errors']
    assert calls == [1]


def test_warm_v2_rechecks_historical_visual_dependency(tmp_path):
    from test_workbench_reads import mixed_project, commit
    project, store = mixed_project(tmp_path)
    document = store.load_document()
    old_ref = document['pages'][0]['page']
    page = store.read_object_json(old_ref)
    page['speaker_notes'] = 'Only narration changed; retained visuals still match.'
    document['pages'][0]['page'] = store.put_json_object(page)
    commit(store, document, 'notes-only-history')
    workbench._summary_cache.clear()
    first = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    assert workbench._summary_cache, 'fixture must exercise a reusable v2 response'
    assert workbench.workbench_summary(project, protocol='workbench_summary.v2') == first
    # Neither current Head nor its Page changes. Only a Page consumed through
    # the retained visual's historical content binding becomes unreadable.
    (store.project_root / old_ref['path']).write_bytes(b'corrupt historical Page')
    guarded = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    workbench._summary_cache.clear()
    reference = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    assert guarded == reference
    assert guarded != first


def test_v2_does_not_freeze_synthetic_human_adapter_verdict(tmp_path, synthetic_human_adapter):
    from test_export import _passing_deck, _set_policy, _review, human_professional_reviewer
    project, store = _passing_deck(tmp_path)
    _set_policy(store, professional_review_required_for_delivery=True)
    document = store.load_document()
    _review(store, document, 'professional_use', 'pass', seed='runtime-identity',
            reviewer=human_professional_reviewer(document, event_id='evt-runtime-identity'))
    head = store.current_revision_id()
    workbench._summary_cache.clear()
    def professional(summary):
        check = next(item for item in summary['current_work']['delivery']['checks']
                     if item['kind'] == 'requested_delivery')
        return check['basis']['professional']
    first = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    assert professional(first)['human_signoff'] is True
    # The controlled verifier now rejects the same immutable receipt. There is
    # no product revision or file mutation to invalidate a static cache key.
    synthetic_human_adapter['evt-runtime-identity'] = 'different-receipt-fingerprint'
    second = workbench.workbench_summary(project, protocol='workbench_summary.v2')
    assert store.current_revision_id() == head
    assert professional(second)['human_signoff'] is False
    assert 'receipt_event_replayed' in professional(second)['gap_reasons']
    workbench._summary_cache.clear()
    assert second == workbench.workbench_summary(project, protocol='workbench_summary.v2')


def test_v2_owner_rechecks_cache_after_miss_registration_race(tmp_path, monkeypatch):
    project, _ = production_project(tmp_path, 'full_deck')
    workbench._summary_cache.clear()
    original_lookup = workbench._cached_summary
    original_build = workbench._build_v2_summary
    delayed_thread = threading.get_ident()
    delayed_once = False
    builds = []
    published = []

    def counted(*args, **kwargs):
        builds.append(1)
        return original_build(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=1) as executor:
        def interleaved(ctx, key, revision):
            nonlocal delayed_once
            cached = original_lookup(ctx, key, revision)
            if threading.get_ident() == delayed_thread and not delayed_once:
                delayed_once = True
                assert cached is None
                # Freeze this caller after its miss but before registration.
                # Another real caller owns, builds, publishes and exits fully.
                owner = executor.submit(workbench.workbench_summary, project,
                                        protocol='workbench_summary.v2')
                published.append(owner.result(timeout=10))
                assert key not in workbench._summary_inflight
                assert original_lookup(ctx, key, revision) is not None
                return None  # Deliver this caller's original, now stale miss.
            return cached

        monkeypatch.setattr(workbench, '_cached_summary', interleaved)
        monkeypatch.setattr(workbench, '_build_v2_summary', counted)
        result = workbench.workbench_summary(project, protocol='workbench_summary.v2')

    assert result == published[0]
    assert builds == [1]
    assert not workbench._summary_inflight
