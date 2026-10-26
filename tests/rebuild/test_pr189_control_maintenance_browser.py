"""Actual Chromium and HTTP service; inject transport loss and retained local copies only."""
import json

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import ui_journal
from deck_master.web import WorkbenchServer
from test_candidates import store as candidate_store, dispatch  # noqa: F401
from test_rc3_studio_control_browser import open_control_action, rc3_browser  # noqa: F401

pytestmark = pytest.mark.browser


def draft_prefix(store, action="pause"):
    identity = ui_journal.project_info(store.project_root)["project_identity"]
    return f"deck-master:v3:control-draft:{identity}:{action}:"


def local_copies(page, prefix):
    return page.evaluate("prefix => Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.startsWith(prefix)))", prefix)


def seed_copies(page, copies):
    page.evaluate("copies => {for (const [key, value] of Object.entries(copies)) localStorage.setItem(key, value);}", copies)


def test_failed_control_read_marks_handoffs_unknown_and_recovers(candidate_store):
    store = candidate_store
    dispatch(store)
    before = store.load_document()
    server = WorkbenchServer(store.project_root)
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(server.start() + "studio/")
            expect(page.get_by_role("button", name="查看待交接任务，1 项", exact=True)).to_be_visible()
            reading_url = page.url
            reading = page.locator(".matrix")
            expect(reading).to_be_visible()
            page.evaluate("window.maintenanceReading = document.querySelector('.matrix')")
            page.route("**/api/project?light=1", lambda route: route.abort("failed"))
            page.evaluate("document.querySelector('#app').dispatchEvent(new CustomEvent('business-state-changed'))")
            expect(page.get_by_role("button", name="待交接数量暂不可核实，打开任务核对", exact=True)).to_have_text("待交接 暂不可核实")
            expect(page.locator(".runtime-sync-row")).to_contain_text("同步中断")
            assert page.url == reading_url
            assert page.evaluate("window.maintenanceReading === document.querySelector('.matrix')")
            page.unroute("**/api/project?light=1")
            page.evaluate("document.querySelector('#app').dispatchEvent(new CustomEvent('business-state-changed'))")
            expect(page.get_by_role("button", name="查看待交接任务，1 项", exact=True)).to_be_visible()
            assert store.load_document() == before and errors == []
            browser.close()
    finally:
        server.stop()


def test_plain_recovery_download_and_explicit_delete_survive_unreadable_copy(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    before = store.load_document()
    goto()
    prefix = draft_prefix(store)
    seed_copies(page, {prefix + "one": "{}", prefix + "two": "{}"})
    keys = list(local_copies(page, prefix))
    # Storage enumeration order is browser-defined: make its first entry the
    # unreadable one, then prove a later independent copy remains reachable.
    seed_copies(page, {keys[0]: "{", keys[1]: json.dumps({"text": "保留独立副本中的明确要求", "pending": None})})
    open_control_action(page, "暂停本次请求")
    dialog = page.get_by_role("dialog", name="暂停本次请求")
    recovery = dialog.get_by_label("恢复本机的请求文字", exact=True)
    expect(recovery).to_be_visible()
    recovery.select_option(label="保留独立副本中的明确要求")
    expect(dialog.get_by_label("本次明确要求（必填）")).to_have_value("保留独立副本中的明确要求")
    with page.expect_download() as saved:
        dialog.get_by_role("button", name="下载请求文字", exact=True).click()
    saved.value.save_as(tmp_path / "request-copy.json")
    assert json.loads((tmp_path / "request-copy.json").read_text()) == {"instruction_text": "保留独立副本中的明确要求", "pending": None}
    dialog.get_by_role("button", name="删除选中的恢复副本", exact=True).click()
    expect(dialog).to_contain_text("选中的恢复副本已删除，当前输入保留")
    expect(dialog.get_by_label("本次明确要求（必填）")).to_have_value("保留独立副本中的明确要求")
    retained = local_copies(page, prefix)
    assert keys[1] not in retained and retained[keys[0]] == "{"
    assert len(retained) == 2  # unreadable original and the current editable buffer
    assert store.load_document() == before


def test_unknown_request_retained_protected_downloaded_and_retry_cleans_only_its_copies(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    goto()
    before = store.load_document()
    prefix = draft_prefix(store)
    requests = []
    page.on("request", lambda request: requests.append(json.loads(request.post_data))
            if request.method == "POST" and request.url.endswith("/collaboration/request/pause") else None)
    page.route("**/collaboration/request/pause", lambda route: route.abort("failed"), times=1)
    open_control_action(page, "暂停本次请求")
    dialog = page.get_by_role("dialog", name="暂停本次请求")
    dialog.get_by_label("本次明确要求（必填）").fill("保持原编号核实暂停，不能重复派发。")
    dialog.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(dialog.get_by_role("button", name="核实并重试原请求", exact=True)).to_be_enabled()
    stored = local_copies(page, prefix)
    assert len(stored) == 1 and store.load_document() == before
    original = json.loads(next(iter(stored.values())))
    unrelated = {"text": "另一份结果待核实的请求", "pending": {**original["pending"], "payload": {**original["pending"]["payload"], "operation_id": "other-unknown-operation"}}}
    seed_copies(page, {prefix + "broken": "{", prefix + "duplicate": json.dumps(original), prefix + "other": json.dumps(unrelated), prefix + "plain": json.dumps({"text": "无关文字", "pending": None})})
    page.reload()
    open_control_action(page, "暂停本次请求")
    dialog = page.get_by_role("dialog", name="暂停本次请求")
    recovery = dialog.get_by_label("恢复本机的请求文字", exact=True)
    recovery.select_option(label="提交结果待核实 · 保持原编号核实暂停，不能重复派发。")
    expect(dialog.get_by_label("本次明确要求（必填）")).to_have_attribute("readonly", "")
    dialog.get_by_role("button", name="删除选中的恢复副本", exact=True).click()
    expect(dialog).to_contain_text("该副本的提交结果待核实，请先核实原请求")
    assert next(iter(stored)) in local_copies(page, prefix)
    with page.expect_download() as saved:
        dialog.get_by_role("button", name="下载请求文字", exact=True).click()
    saved.value.save_as(tmp_path / "unknown-request.json")
    downloaded = json.loads((tmp_path / "unknown-request.json").read_text())
    assert downloaded == {"instruction_text": original["text"], "pending": original["pending"]}
    dialog.get_by_role("button", name="核实并重试原请求", exact=True).click()
    expect(dialog).to_contain_text("请求已记录")
    retained = local_copies(page, prefix)
    assert set(retained) == {prefix + "broken", prefix + "other", prefix + "plain"}
    assert json.loads(retained[prefix + "other"]) == unrelated
    with page.expect_download() as confirmed:
        dialog.get_by_role("button", name="下载请求文字", exact=True).click()
    confirmed.value.save_as(tmp_path / "confirmed-request.json")
    assert json.loads((tmp_path / "confirmed-request.json").read_text()) == {"instruction_text": original["text"], "pending": None}
    assert len(requests) == 2 and requests[0] == requests[1]
    assert store.load_document()["pages"] == before["pages"]


def test_receipt_recovery_cleans_confirmed_copies_despite_unreadable_copy(rc3_browser):
    page, _, store, _, goto, _ = rc3_browser
    goto()
    prefix = draft_prefix(store)

    def lose_response(route):
        response = route.fetch()
        assert response.ok
        route.abort("failed")

    page.route("**/collaboration/request/pause", lose_response, times=1)
    open_control_action(page, "暂停本次请求")
    dialog = page.get_by_role("dialog", name="暂停本次请求")
    dialog.get_by_label("本次明确要求（必填）").fill("已执行但未收到回包，先核实原回执。")
    dialog.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(dialog.get_by_role("button", name="核实并重试原请求", exact=True)).to_be_enabled()
    paused = store.load_document()
    assert paused["collaboration"]["request"]["paused"]
    seed_copies(page, {prefix + "broken": "{", prefix + "plain": json.dumps({"text": "独立编辑文字", "pending": None})})
    page.reload()
    open_control_action(page, "核实已保留的请求（1）")
    dialog = page.get_by_role("dialog", name="核实已保留的请求")
    dialog.get_by_role("button", name="按原编号核实请求", exact=True).click()
    expect(dialog).to_contain_text("原请求回执已核实")
    assert set(local_copies(page, prefix)) == {prefix + "broken", prefix + "plain"}
    assert store.load_document() == paused
