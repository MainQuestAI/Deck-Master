"""L1 synthetic public projects, real HTTP service and Chromium.

No default grants, patched product gates, or fabricated professional reviews.
Only transport failure is injected in the retained draft recovery cases.
"""
from __future__ import annotations

import json
import shutil
from urllib.parse import urlencode

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import service, ui_journal
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from rc3_fixtures import authorize_scope, evidence_for, historical_snapshot, public_project, source_snapshot

pytestmark = pytest.mark.browser


def manuscript_page(page_id, title):
    return {"schema_version": "deck_page_package.v2", "page_id": page_id,
            "customer_visible": {"title": title, "body_blocks": [
                {"id": "body", "type": "paragraph", "text": "先核对真实稿件，再确认范围与下一步。"}]},
            "visual_spec": {"intent": "明确范围的内容稿", "reference_mode": "new_design"}}


def open_control_action(page, name):
    page.get_by_role("button", name="查看本次工作与范围", exact=True).click()
    page.get_by_role("button", name=name, exact=True).click()


@pytest.fixture
def rc3_browser(tmp_path, request):
    requested = getattr(request, "param", None)
    handle = public_project(tmp_path, create_input={"brief": "保留原稿主线，核对范围后再制作", "title": "请求与草稿验证"},
                            request_input={"intent": "content_only", "content_intent": requested} if requested else None,
                            manuscript={"pages": [manuscript_page("p01", "先核对实际稿件"),
                                                   manuscript_page("p02", "再决定下一步")]})
    store = Store(handle["project"])
    (tmp_path / "scenario-manifest.json").write_text(json.dumps(handle["scenario_manifest"], indent=2))
    assert store.load_document()["collaboration"]["authorizations"] == []
    server = WorkbenchServer(handle["project"])
    url = server.start()
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.on("page", lambda page: page.on("pageerror", lambda error: errors.append(str(error))))
        page = context.new_page()
        info = ui_journal.project_info(handle["project"])

        def goto(surface="page", revision=None, target=None):
            link = url + "#" + urlencode({"project": info["project_identity"], "surface": surface,
                "page": "p01", "layer": "content", "revision": revision or store.current_revision_id()})
            (target or page).goto(link)
            return link

        goto.stop_server = server.stop
        try:
            yield page, context, store, url, goto, errors
        finally:
            context.close()
            browser.close()
            server.stop()
        assert errors == []


@pytest.mark.parametrize("width,height", [(1280, 800), (1440, 900), (390, 844)])
def test_current_scope_readable_draft_delivery_and_keyboard(rc3_browser, tmp_path, width, height):
    page, _, store, _, goto, _ = rc3_browser
    page.set_viewport_size({"width": width, "height": height})
    before = store.current_revision_id()
    goto()
    expect(page.get_by_role("region", name="页面内容")).to_contain_text("先核对真实稿件")
    scope = page.get_by_role("button", name="查看本次工作与范围", exact=True)
    scope.focus()
    page.keyboard.press("Enter")
    dialog = page.get_by_role("dialog", name="本次工作与范围")
    expect(dialog).to_contain_text("第 1 页 · 先核对实际稿件")
    expect(dialog).to_contain_text("当前控制事实")
    page.keyboard.press("Escape")
    expect(scope).to_be_focused()
    page.get_by_role("button", name="任务与交付", exact=True).click()
    page.get_by_role("button", name="文件", exact=True).click()
    expect(page.get_by_label("所选实际文件的交付判断")).to_contain_text("当前控制")
    expect(page.get_by_label("所选实际文件的交付判断")).to_contain_text("工程检查")
    expect(page.get_by_role("button", name="生成审阅包", exact=True)).to_be_enabled()
    page.get_by_role("button", name="生成正式交付包", exact=True).click()
    expect(page.locator(".export-results")).to_contain_text("未生成")
    expect(page.locator(".export-results")).to_contain_text("当前稿件、可读报告和本次输入均保留")
    dimensions = page.evaluate("({width:innerWidth,scroll:document.documentElement.scrollWidth})")
    assert dimensions["scroll"] <= dimensions["width"]
    assert store.current_revision_id() == before
    page.screenshot(path=str(tmp_path / f"control-delivery-{width}.png"), full_page=True)


@pytest.mark.parametrize("rc3_browser", ["write_only", "content_full"], indirect=True)
def test_completed_content_returns_readable_outputs_without_new_production(rc3_browser):
    page, _, store, _, goto, _ = rc3_browser
    before = store.load_document()
    for _ in range(2):
        response = service.continue_project(store.project_root)
        assert response["status"] == "completed"
        assert response["completion"]["state"] == "completed"
        assert response["pending_tasks"] == []
    assert store.load_document() == before
    goto()
    expect(page.get_by_label("本次工作状态")).to_contain_text("本次内容已完成")
    expect(page.get_by_role("region", name="页面内容")).to_contain_text("先核对真实稿件")
    open_control_action(page, "读取下一工作单")
    dialog = page.get_by_role("dialog", name="下一工作单")
    expect(dialog).to_contain_text("本次内容已完成")
    expect(dialog.get_by_role("button", name="查看工作单", exact=True)).to_have_count(0)
    assert store.load_document() == before


def test_pause_resume_keeps_pages_and_requires_explicit_instruction(rc3_browser):
    page, _, store, _, goto, _ = rc3_browser
    goto()
    original = store.load_document()
    open_control_action(page, "暂停本次请求")
    dialog = page.get_by_role("dialog", name="暂停本次请求")
    dialog.get_by_label("本次明确要求（必填）").fill("暂停这次制作，先核对原稿。")
    dialog.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(dialog).to_contain_text("请求已记录")
    paused = store.load_document()
    assert paused["collaboration"]["request"]["paused"] is True
    assert paused["pages"] == original["pages"]
    dialog.get_by_role("button", name="重新读取当前状态", exact=True).click()
    expect(page.get_by_label("本次工作状态")).to_contain_text("本次请求已暂停")
    open_control_action(page, "恢复本次请求")
    dialog = page.get_by_role("dialog", name="恢复本次请求")
    dialog.get_by_label("本次明确要求（必填）").fill("明确恢复原请求，只保留原范围与原额度。")
    dialog.get_by_role("button", name="确认恢复本次请求", exact=True).click()
    expect(dialog).to_contain_text("请求已记录")
    resumed = store.load_document()
    assert resumed["collaboration"]["request"]["paused"] is False
    assert resumed["pages"] == original["pages"]
    assert resumed["collaboration"]["authorizations"] == []
    assert resumed["collaboration"]["request"]["scope"] == original["collaboration"]["request"]["scope"]


def test_two_windows_stale_control_keeps_text_and_current_pages(rc3_browser):
    a, context, store, _, goto, _ = rc3_browser
    link = goto()
    open_control_action(a, "暂停本次请求")
    stale = a.get_by_role("dialog", name="暂停本次请求")
    stale.get_by_label("本次明确要求（必填）").fill("窗口 A 保留的暂停原因")
    b = context.new_page()
    b.goto(link)
    open_control_action(b, "暂停本次请求")
    fresh = b.get_by_role("dialog", name="暂停本次请求")
    fresh.get_by_label("本次明确要求（必填）").fill("窗口 B 先确认暂停")
    fresh.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(fresh).to_contain_text("请求已记录")
    current = store.load_document()
    stale.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(stale).to_contain_text("本次输入仍保留")
    expect(stale.get_by_label("本次明确要求（必填）")).to_have_value("窗口 A 保留的暂停原因")
    assert store.load_document() == current
    assert current["collaboration"]["request"]["pause_reason"] == "窗口 B 先确认暂停"


def test_new_envelope_retains_path_details_and_readable_result(rc3_browser):
    page, _, _, _, goto, _ = rc3_browser
    goto()
    result = page.evaluate("""async () => {
      const {post} = await import('/v2/api.js');
      try { await post('/api/projects/wrong-project/collaboration/request/pause', {}); }
      catch (error) { return {status:error.status,path:error.path,field:error.field,details:error.details,envelope:error.envelope}; }
    }""")
    assert result["status"] == 404
    assert result["path"] == result["field"] == "project_id"
    assert result["envelope"]["schema_version"] == "collaboration_response.v1"


def scoped_opinions(store):
    scope = {"subject": "pages", "page_ids": ["p01"], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["review"],
             "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "working"}
    authorize_scope(store.project_root, actions=["annotation.save"], scope=scope,
                    max_external_calls=0, max_candidate_count=0, adoption_policy="candidate_only",
                    evidence=evidence_for(store.project_root, text="仅允许对第 1 页记录意见，不派发制作", locator="test:browser:opinion-scope"))


def test_old_revision_new_opinion_then_restore_draft(rc3_browser):
    from test_deep_quality_browser import test_old_revision_draft_never_locks_a_new_opinion
    scoped_opinions(rc3_browser[2])
    test_old_revision_draft_never_locks_a_new_opinion(rc3_browser)


@pytest.mark.parametrize("width,height", [(1280, 800), (1440, 900), (390, 844)])
def test_two_window_offline_drafts_refresh_and_session_recovery(rc3_browser, width, height):
    from test_deep_quality_browser import test_cloned_window_offline_drafts_both_survive
    test_cloned_window_offline_drafts_both_survive(rc3_browser, width, height)


def test_revoke_preserves_actual_pages_and_shows_current_control(rc3_browser):
    page, _, store, _, goto, _ = rc3_browser
    scoped_opinions(store)
    original = store.load_document()
    goto()
    page.get_by_role("button", name="查看本次工作与范围", exact=True).click()
    page.get_by_role("button", name="撤回此授权", exact=True).click()
    dialog = page.get_by_role("dialog", name="撤回此授权")
    dialog.get_by_label("本次明确要求（必填）").fill("撤回对第 1 页继续记录意见的授权。")
    dialog.get_by_role("button", name="确认撤回此授权", exact=True).click()
    expect(dialog).to_contain_text("请求已记录")
    assert store.load_document()["pages"] == original["pages"]
    dialog.get_by_role("button", name="重新读取当前状态", exact=True).click()
    expect(page.get_by_label("本次工作状态")).to_contain_text("存在已撤回授权")


def test_readonly_external_report_keeps_source_and_readable_packet(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    source_root = tmp_path / "external-source"
    source_root.mkdir()
    source = source_root / "manuscript.txt"
    source.write_text("外部原稿：明确比较两个方案，然后保留审阅缺口。", encoding="utf-8")
    before = source_snapshot(source_root)
    original = store.load_document()
    goto()
    page.get_by_role("button", name="查看本次工作与范围", exact=True).click()
    page.get_by_role("button", name="只读审阅稿件", exact=True).click()
    dialog = page.get_by_role("dialog", name="只读审阅稿件")
    dialog.get_by_label("源文件或项目位置（必填）").fill(str(source))
    dialog.get_by_role("button", name="读取并生成审阅报告", exact=True).click()
    expect(dialog).to_contain_text("仍需审阅者")
    expect(dialog).to_contain_text("外部原稿：明确比较两个方案")
    expect(dialog.get_by_role("button", name="下载完整审阅报告", exact=True)).to_be_enabled()
    assert source_snapshot(source_root) == before
    assert store.load_document() == original


def test_new_speech_request_uses_explicit_one_page_scope(rc3_browser):
    page, _, store, _, goto, _ = rc3_browser
    original = store.load_document()
    goto()
    open_control_action(page, "开始新的明确请求")
    dialog = page.get_by_role("dialog", name="开始本次请求")
    dialog.get_by_label("内容产物", exact=True).select_option("speech_only")
    dialog.get_by_role("checkbox", name="第 1 页 · 先核对实际稿件", exact=True).check()
    dialog.get_by_role("checkbox", name="论证主线", exact=True).uncheck()
    dialog.get_by_role("checkbox", name="页面大纲", exact=True).uncheck()
    dialog.get_by_role("checkbox", name="口播稿", exact=True).check()
    dialog.get_by_label("本次明确要求（必填）").fill("只对第 1 页补写口播，不改上屏正文，不制作图稿。")
    dialog.get_by_role("button", name="确认开始本次请求", exact=True).click()
    expect(dialog).to_contain_text("请求已记录")
    changed = store.load_document()
    request = changed["collaboration"]["request"]
    assert request["content_intent"] == "speech_only"
    assert request["scope"]["page_ids"] == ["p01"]
    assert request["scope"]["layers"] == ["speech"]
    assert request["scope"]["allow_page_membership_change"] is False
    assert changed["pages"] == original["pages"]
    assert changed["collaboration"]["authorizations"] == []
    dialog.get_by_role("button", name="读取下一工作单", exact=True).click()
    work = page.get_by_role("dialog", name="下一工作单")
    expect(work.get_by_role("button", name="查看工作单", exact=True)).to_have_count(1)
    first = store.load_document()
    task = store.read_object_json(first["tasks"][-1])
    assert task["scope_pages"] == ["p01"]
    assert task["kind"] == "compose"
    assert task["collaboration_binding"]["phase"] == "speech"
    assert task.get("call_allowances", []) == []
    work.get_by_role("button", name="重新读取下一工作单", exact=True).click()
    expect(work.get_by_role("button", name="查看工作单", exact=True)).to_have_count(1)
    assert store.load_document() == first


def test_confirmed_manuscript_import_compares_actual_copy_and_adopts_atomically(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    original = store.load_document()
    incoming = {"pages": [manuscript_page("p01", "导入后保留的确认稿"), manuscript_page("p02", "再决定下一步")]}
    source = tmp_path / "confirmed-manuscript.json"
    source.write_text(json.dumps(incoming, ensure_ascii=False), encoding="utf-8")
    goto()
    open_control_action(page, "导入确认稿")
    dialog = page.get_by_role("dialog", name="导入确认稿")
    dialog.get_by_label("确认稿 JSON 文件（必填）").set_input_files(source)
    expect(dialog).to_contain_text("当前固定稿")
    expect(dialog).to_contain_text("导入后保留的确认稿")
    assert store.load_document() == original
    dialog.get_by_label("本次明确要求（必填）").fill("采用这份确认稿，保留主线，只进入保真审阅，不批准制作。")
    dialog.get_by_role("button", name="确认导入确认稿", exact=True).click()
    expect(dialog).to_contain_text("请求已记录")
    imported = store.load_document()
    assert store.read_object_json(imported["pages"][0]["page"])["customer_visible"]["title"] == "导入后保留的确认稿"
    assert len(imported["pages"]) == 2
    plan = store.read_object_json(imported["content_plan"])
    assert plan["mode"] == "imported_mapping"
    assert imported["collaboration"]["quality_profile"]["content_review_requirement"] == "fidelity_only"
    assert imported["collaboration"]["authorizations"] == []
    assert json.loads(source.read_text(encoding="utf-8")) == incoming


def test_lost_control_response_refresh_recovers_same_operation(rc3_browser):
    page, _, store, _, goto, _ = rc3_browser
    goto()
    requests = []
    page.on("request", lambda request: requests.append(json.loads(request.post_data))
            if request.method == "POST" and request.url.endswith("/collaboration/request/pause") else None)

    def lose_response(route):
        response = route.fetch()
        assert response.ok, response.text()
        route.abort("failed")

    page.route("**/collaboration/request/pause", lose_response, times=1)
    open_control_action(page, "暂停本次请求")
    dialog = page.get_by_role("dialog", name="暂停本次请求")
    dialog.get_by_label("本次明确要求（必填）").fill("保留原请求编号，暂停后先核对稿件。")
    dialog.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(dialog.get_by_role("button", name="核实并重试原请求", exact=True)).to_be_enabled()
    paused = store.load_document()
    assert paused["collaboration"]["request"]["paused"]
    page.reload()
    open_control_action(page, "核实已保留的请求（1）")
    dialog = page.get_by_role("dialog", name="核实已保留的请求")
    dialog.get_by_role("button", name="按原编号核实请求", exact=True).click()
    expect(dialog).to_contain_text("原请求回执已核实")
    assert len(requests) == 2 and requests[0] == requests[1]
    assert store.load_document() == paused


def test_async_error_waits_for_actual_draft_conflict_resolution(rc3_browser):
    from test_deep_quality_browser import open_note_face
    a, context, _, _, goto, _ = rc3_browser
    link = goto()
    open_note_face(a)
    a.get_by_role("textbox", name="个人草稿", exact=True).fill("两个窗口的共同草稿")
    a.get_by_role("button", name="保存个人草稿", exact=True).click()
    expect(a.locator(".draft-state")).to_contain_text("已保存到项目")
    with a.expect_popup() as popup:
        a.evaluate("url => window.open(url, '_blank')", link)
    b = popup.value
    open_note_face(b)
    expect(b.get_by_role("textbox", name="个人草稿", exact=True)).to_have_value("两个窗口的共同草稿")
    a.get_by_role("textbox", name="个人草稿", exact=True).fill("窗口 A 已保存的独立修改")
    expect(a.locator(".draft-state")).to_contain_text("已保存到项目")
    b.get_by_role("textbox", name="个人草稿", exact=True).fill("窗口 B 需要保留的修改")
    expect(b.locator(".draft-state")).to_contain_text("保存冲突")
    b.get_by_role("button", name="比较两份草稿", exact=True).click()
    protected = b.get_by_role("dialog", name="保留两份个人草稿")
    expect(protected).to_be_visible()
    b.evaluate("""async () => {
      const {post, readableError} = await import('/v2/api.js');
      const {modal, el} = await import('/v2/dom.js');
      try { await post('/api/projects/wrong-project/collaboration/request/pause', {}); }
      catch(error) { modal('异步请求未完成', el('p', {}, readableError(error))); }
    }""")
    expect(protected).to_be_visible()
    expect(protected.get_by_label("本机私人笔记")).to_have_value("窗口 B 需要保留的修改")
    expect(b.get_by_role("dialog", name="异步请求未完成")).not_to_be_visible()
    protected.get_by_role("button", name="关闭", exact=True).click()
    expect(b.get_by_role("dialog", name="异步请求未完成")).to_be_visible()
    expect(b.get_by_role("textbox", name="个人草稿", exact=True)).to_have_value("窗口 B 需要保留的修改")


def test_historical_migration_is_explicit_and_does_not_grant_production(tmp_path):
    handle = historical_snapshot(tmp_path, scenario="L1 legacy manuscript migration", pages=[manuscript_page("p01", "旧稿完整保留")])
    store = Store(handle["project"])
    original = store.load_document()
    server = WorkbenchServer(handle["project"])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(server.start())
            expect(page.get_by_label("本次工作状态")).to_contain_text("需要升级控制记录")
            assert store.load_document() == original
            open_control_action(page, "查看升级影响")
            dialog = page.get_by_role("dialog", name="升级项目控制记录")
            expect(dialog).to_contain_text("保留 1 页")
            dialog.get_by_label("本次明确要求（必填）").fill("仅升级控制记录，保留旧稿；不批准后续制作。")
            dialog.get_by_role("button", name="确认升级项目控制记录", exact=True).click()
            expect(dialog).to_contain_text("请求已记录")
            migrated = store.load_document()
            assert migrated["pages"] == original["pages"]
            assert migrated["collaboration"]["request"] is None
            assert migrated["collaboration"]["authorizations"] == []
        finally:
            browser.close()
            server.stop()


def test_two_actual_versions_select_old_source_under_current_control_without_overwriting(tmp_path):
    from test_variant_requests import variant_pair
    pair = variant_pair(tmp_path)
    store, first, second = pair["store"], pair["first"], pair["second"]
    root = store.project_root / ".deckmaster" / "workbench" / "exports"
    first_before, second_before = source_snapshot(root / first["export_id"]), source_snapshot(root / second["export_id"])
    info = ui_journal.project_info(store.project_root)
    server = WorkbenchServer(store.project_root)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        a, b = context.new_page(), context.new_page()
        requests, errors = [], []
        for page in (a, b):
            page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            base = server.start()
            def link(revision):
                return base + "#" + urlencode({"project": info["project_identity"], "surface": "page", "page": "p1", "layer": "content", "revision": revision})
            a.goto(link(first["revision_id"]))
            b.goto(link(second["revision_id"]))
            expect(a.get_by_role("region", name="页面内容")).to_contain_text("现场版正文")
            expect(b.get_by_role("region", name="页面内容")).to_contain_text("阅读版正文")
            a.get_by_role("button", name="任务与交付", exact=True).click()
            a.get_by_role("button", name="版本", exact=True).click()
            a.on("request", lambda request: requests.append(json.loads(request.post_data))
                 if request.method == "POST" and request.url.endswith("/collaboration/requests") else None)
            a.get_by_role("button", name="以正在阅读的版本局改", exact=True).click()
            dialog = a.get_by_role("dialog", name="按所选版本局改")
            expect(dialog).to_contain_text(first["revision_id"][:8])
            expect(dialog).to_contain_text(info["control_revision_id"][:8])
            dialog.get_by_role("checkbox", name="第 1 页 · 记录未知版本", exact=True).check()
            dialog.get_by_role("checkbox", name="论证主线", exact=True).uncheck()
            dialog.get_by_role("checkbox", name="页面大纲", exact=True).uncheck()
            dialog.get_by_role("checkbox", name="口播稿", exact=True).check()
            dialog.get_by_label("本次明确要求（必填）").fill("按已阅读的现场版只局改第 1 页口播，保留阅读版的固定文件。")
            a.set_viewport_size({"width": 390, "height": 844})
            assert a.evaluate("document.documentElement.scrollWidth <= innerWidth")
            a.screenshot(path=str(tmp_path / "variant-source-scope-390.png"), full_page=True)
            confirm = dialog.get_by_role("button", name="确认按所选版本局改", exact=True)
            confirm.focus()
            a.keyboard.press("Enter")
            expect(dialog).to_contain_text("请求已记录")
            current = store.load_document()
            assert current["content_plan"] == first["manifest"]["variant"]["plan_ref"]
            assert current["collaboration"]["request"]["scope"]["layers"] == ["speech"]
            assert current["collaboration"]["request"]["variant"]["variant_id"] == "live"
            assert requests[0]["request"]["variant_transition"]["source"]["revision_id"] == first["revision_id"]
            expect(b.get_by_role("region", name="页面内容")).to_contain_text("阅读版正文")
            b.reload()
            expect(b.get_by_role("region", name="页面内容")).to_contain_text("阅读版正文")
            expect(b.locator(".history-banner")).to_be_visible()
            assert source_snapshot(root / first["export_id"]) == first_before
            assert source_snapshot(root / second["export_id"]) == second_before
            assert errors == []
        finally:
            context.close()
            browser.close()
            server.stop()
