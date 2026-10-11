"""Auxiliary metadata damage must not hide healthy candidates."""
import pytest
from deck_master import candidates
from test_candidate_decisions import store, candidate, decide, adoption_plan  # noqa: F401


def damage(store, task, kind, monkeypatch):
    ref = task['change_binding']['change_ref']
    if kind == 'missing':
        (store.project_root/ref['path']).unlink()
    elif kind == 'hash':
        (store.project_root/ref['path']).write_text('{}')
    else:
        original = type(store).read_object_json
        def read(self, requested):
            return [] if requested == ref else original(self, requested)
        monkeypatch.setattr(type(store), 'read_object_json', read)


@pytest.mark.parametrize('kind', ['missing', 'hash', 'structure'])
def test_change_group_damage_is_local(store, kind, monkeypatch):
    first, task = candidate(store)
    second, _ = candidate(store, 'p02')
    damage(store, task, kind, monkeypatch)
    rows = {r['candidate']['candidate_id']:r for r in candidates.listing(store.project_root)['candidates']}
    assert set(rows) == {first, second}
    assert rows[first]['change_group_status'] == 'unreadable'
    assert rows[first]['change_id'] is None
    assert rows[second]['change_group_status'] == 'available'
    assert candidates.show(store.project_root, candidate_id=second)['candidate_id'] == second
    assert adoption_plan(store, [second])['selections']


def test_unreadable_decision_does_not_disable_selection(store):
    first, _ = candidate(store)
    second, _ = candidate(store, 'p02')
    decide(store, first, 'keep_current')
    ref = store.load_document()['candidate_decisions'][0]
    (store.project_root/ref['path']).unlink()
    rows = candidates.listing(store.project_root)['candidates']
    assert all(row['decision']['state']=='unreadable' for row in rows)
    assert all(row['selection_allowed'] for row in rows)
    assert len(adoption_plan(store, [first, second])['selections']) == 2


@pytest.mark.browser
@pytest.mark.parametrize('kind', ['decision', 'missing'])
def test_metadata_damage_keeps_healthy_candidate_interactive(store, kind, monkeypatch):
    from deck_master.web import WorkbenchServer
    from playwright.sync_api import sync_playwright, expect
    first, task = candidate(store)
    second, _ = candidate(store, 'p02')
    if kind == 'decision':
        decide(store, first, 'keep_current')
        ref = store.load_document()['candidate_decisions'][0]
        (store.project_root/ref['path']).unlink()
    else:
        damage(store, task, kind, monkeypatch)
    server = WorkbenchServer(store.project_root)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(server.start()+'studio/')
            page.get_by_role('button',name='任务与交付',exact=True).click()
            page.get_by_role('button',name='待决定',exact=True).click()
            root = page.locator('.candidate-batch')
            expect(root.locator('.candidate-card')).to_have_count(2)
            expect(root).to_contain_text('决定待核实' if kind=='decision' else '修改组信息不可读')
            root.locator(f'[data-candidate-id="{second}"] input').check()
            if kind == 'decision':
                root.locator(f'[data-candidate-id="{first}"] input').check()
            root.get_by_role('button',name='预览所选候选的采用影响',exact=True).click()
            expect(root.get_by_role('button',name='采用所选候选',exact=True)).to_be_enabled()
        finally:
            browser.close()
            server.stop()
