"""R2 real Chromium/HTTP manuscript intake and non-success report retention.

All input is synthetic; no professional acceptance or broad grants are used.
"""
import json
import shutil

import pytest
from playwright.sync_api import expect, sync_playwright

from deck_master import collaboration, local_runtime as runtime
from deck_master.store import Store
from rc3_fixtures import evidence_for
from test_rc3_studio_control_browser import manuscript_page, rc3_browser, open_control_action
from test_workbench_services import launcher_service

pytestmark = pytest.mark.browser


def retain_http(response, path):
    path.write_text(json.dumps({"url": response.url, "http_status": response.status,
        "request": json.loads(response.request.post_data), "response": response.json()},
        ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("width,height,work", [(1440, 900, "write_only"), (1280, 800, "full_deck"), (390, 844, "speech_only")])
def test_launcher_creates_project_from_explicit_complete_manuscript(launcher_service, tmp_path, width, height, work):
    _, _, state = launcher_service
    source = tmp_path / "confirmed.json"
    manuscript = {"pages": [manuscript_page("source-a", "已有确认稿第一部分"),
                             manuscript_page("source-b", "已有确认稿第二部分")],
                  "page_order": ["source-b", "source-a"]}
    source.write_text(json.dumps(manuscript, ensure_ascii=False), encoding="utf-8")
    source_bytes = source.read_bytes()
    project = tmp_path / "from-manuscript"
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(state["url"])
            page.get_by_role("button", name="新建项目", exact=True).click()
            dialog = page.get_by_role("dialog", name="新建项目")
            dialog.get_by_label("确认稿 JSON 文件（可选）").set_input_files(source)
            expect(dialog).to_contain_text("已有确认稿第二部分")
            expect(dialog).to_contain_text("完整稿件")
            assert not project.exists()
            dialog.get_by_label("项目名称（必填）").fill("从确认稿建立")
            dialog.get_by_label("用途（必填）").fill("读取已确认主线，不启动额外制作。")
            dialog.get_by_label("受众（必填）").fill("合成验证者")
            dialog.get_by_label("本次约定产物").select_option(work)
            dialog.get_by_label("保存到哪个文件夹（必填）").fill(str(tmp_path))
            dialog.get_by_label("新项目文件夹名（必填）").fill(project.name)
            page.screenshot(path=str(tmp_path / "launcher-intake-before-create.png"), full_page=True)
            with page.expect_response("**/api/projects/create") as created:
                dialog.get_by_role("button", name="创建项目", exact=True).click()
            retain_http(created.value, tmp_path / "launcher-create-http.json")
            assert created.value.status == 200
            expect(page.get_by_label("本次工作状态")).to_be_visible()
            if work == "write_only":
                expect(page.get_by_label("本次工作状态")).to_contain_text("本次内容已完成")
            page.get_by_role("button", name="第 1 页，逐页稿，已就绪", exact=True).click()
            expect(page.get_by_role("region", name="页面内容")).to_contain_text("已有确认稿第二部分")
            doc = Store(project).load_document()
            assert [entry["page_id"] for entry in doc["pages"]] == ["source-b", "source-a"]
            assert set(doc["collaboration"]["request"]["scope"]["page_ids"]) == {"source-b", "source-a"}
            assert doc["collaboration"]["authorizations"] == []
            tasks = [Store(project).read_object_json(ref) for ref in doc["tasks"]]
            assert all(task.get("call_allowances", []) == [] for task in tasks)
            if work == "write_only":
                assert tasks == []
            if work == "speech_only":
                assert doc["collaboration"]["request"]["scope"]["layers"] == ["speech"]
                assert len(tasks) == 1 and tasks[0]["collaboration_binding"]["phase"] == "speech"
            assert Store(project).read_object_json(doc["content_plan"])["mode"] == "imported_mapping"
            assert source.read_bytes() == source_bytes
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(tmp_path / "launcher-confirmed-manuscript.png"), full_page=True)
            browser.close()
    finally:
        if project.exists():
            runtime.stop(runtime.descriptor(project=project))
    assert errors == []


@pytest.mark.parametrize("rc3_browser,order", [(None, ["p02", "new-page"]),
    (None, ["p02", "p01", "new-page"]), ({"empty": True}, ["source-a", "source-b"])], indirect=["rc3_browser"])
def test_import_requires_separate_exact_request_then_complete_adoption(rc3_browser, tmp_path, order):
    page, _, store, _, goto, _ = rc3_browser
    original = store.load_document()
    scope = {"subject": "pages", "page_ids": ["p01"], "page_manifest_ref": None,
             "external_artifact_ref": None, "layers": ["speech"],
             "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "working"}
    if original["pages"]:
        collaboration.start_request(store.project_root, input={"intent": "content_only", "content_intent": "speech_only",
            "scope": scope, "replace_request_id": original["collaboration"]["request"]["request_id"],
            "instruction_evidence": evidence_for(store.project_root, text="仅改第一页面的口播，不允许增删或换序。", locator="r2:explicit-narrow")},
            base_revision=original["revision_id"], operation_id="r2-explicit-narrow-request")
    before = store.load_document()
    pages = {entry["page_id"]: store.read_object_json(entry["page"]) for entry in before["pages"]}
    for pid in order:
        if pid not in pages:
            pages[pid] = manuscript_page(pid, "新稿中明确新增的一页 · " + pid)
    source = tmp_path / "complete-replacement.json"
    manuscript = {"pages": [pages[pid] for pid in order], "page_order": order}
    source.write_text(json.dumps(manuscript, ensure_ascii=False), encoding="utf-8")
    source_before = source.read_bytes()
    goto(surface="overview" if not before["pages"] else "page")
    open_control_action(page, "导入确认稿")
    dialog = page.get_by_role("dialog", name="导入确认稿")
    with page.expect_response("**/draft/preview") as preview_response:
        dialog.get_by_label("确认稿 JSON 文件（必填）").set_input_files(source)
    planned = preview_response.value.json()["result"]
    expect(dialog.get_by_role("button", name="按完整稿件明确新的请求范围", exact=True)).to_be_enabled()
    expect(dialog.get_by_role("button", name="确认导入确认稿", exact=True)).to_be_disabled()
    impact = dialog.get_by_label("完整稿件导入影响")
    expect(impact).to_contain_text(order[-1])
    expect(impact).to_contain_text("p01" if before["pages"] else "source-a")
    expect(impact).to_contain_text("删除页面")
    expect(impact).to_contain_text("实际写入内容层")
    assert store.load_document() == before
    instruction = "按这份完整确认稿，明确所列页面增删与页序；只导入，不授予制作权限。"
    dialog.get_by_label("本次明确要求（必填）").fill(instruction)
    dialog.get_by_role("button", name="按完整稿件明确新的请求范围", exact=True).click()
    request = page.get_by_role("dialog", name="采用确认稿所需范围")
    expect(request).to_contain_text("下一步仍须重新核对并单独确认导入")
    expect(request.get_by_label("本次明确要求（必填）")).to_have_value(instruction)
    with page.expect_response("**/collaboration/requests") as requested:
        request.get_by_role("button", name="确认采用确认稿所需范围", exact=True).click()
    retain_http(requested.value, tmp_path / "scope-request-http.json")
    expect(request).to_contain_text("请求已记录")
    scoped = store.load_document()
    assert scoped["pages"] == before["pages"]
    assert scoped.get("content_plan") == before.get("content_plan")
    assert scoped["collaboration"]["request"]["scope"] == planned["required_scope"]
    assert scoped["collaboration"]["authorizations"] == []
    request.get_by_role("button", name="返回确认稿，重新核对导入", exact=True).click()
    resumed = page.get_by_role("dialog", name="导入确认稿")
    expect(resumed).to_contain_text("当前请求覆盖这次导入")
    expect(resumed.get_by_label("本次明确要求（必填）")).to_have_value(instruction)
    with page.expect_response("**/draft/import") as imported:
        resumed.get_by_role("button", name="确认导入确认稿", exact=True).click()
    retain_http(imported.value, tmp_path / "complete-import-http.json")
    expect(resumed).to_contain_text("请求已记录")
    adopted = store.load_document()
    assert [entry["page_id"] for entry in adopted["pages"]] == order
    if before["pages"]:
        assert next(entry for entry in adopted["pages"] if entry["page_id"] == "p02") == before["pages"][1]
    assert adopted["collaboration"]["authorizations"] == []
    assert source.read_bytes() == source_before
    (tmp_path / "import-plan.json").write_text(json.dumps(planned, indent=2))
    page.screenshot(path=str(tmp_path / "separate-scope-then-complete-import.png"), full_page=True)


def test_invalid_complete_manuscript_never_changes_project(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    source = tmp_path / "invalid.json"
    invalid = {"pages": [manuscript_page("p01", "重复的第一页面"), manuscript_page("p01", "重复的第二页面")]}
    source.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
    before = store.load_document()
    goto()
    open_control_action(page, "导入确认稿")
    dialog = page.get_by_role("dialog", name="导入确认稿")
    dialog.get_by_label("确认稿 JSON 文件（必填）").set_input_files(source)
    expect(dialog).to_contain_text("不重复的 page_id")
    expect(dialog.get_by_role("button", name="确认导入确认稿", exact=True)).to_be_disabled()
    assert store.load_document() == before
    assert json.loads(source.read_text()) == invalid


def test_server_invalid_manuscript_preview_preserves_source_without_import(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    source = tmp_path / "invalid-page-schema.json"
    invalid_page = manuscript_page("new-page", "保留待修正的完整稿件")
    invalid_page["visual_spec"]["reference_mode"] = "not-a-supported-reference-mode"
    manuscript = {"pages": [invalid_page]}
    source.write_text(json.dumps(manuscript, ensure_ascii=False), encoding="utf-8")
    before = store.load_document()
    original_source = source.read_bytes()
    goto()
    open_control_action(page, "导入确认稿")
    dialog = page.get_by_role("dialog", name="导入确认稿")
    with page.expect_response("**/draft/preview") as response:
        dialog.get_by_label("确认稿 JSON 文件（必填）").set_input_files(source)
    retain_http(response.value, tmp_path / "invalid-preview-http.json")
    assert response.value.status == 400
    expect(dialog).to_contain_text("当前稿件、可读报告和本次输入均保留")
    expect(dialog).to_contain_text("保留待修正的完整稿件")
    expect(dialog.get_by_role("button", name="确认导入确认稿", exact=True)).to_be_disabled()
    assert store.load_document() == before
    assert source.read_bytes() == original_source


def test_stale_import_keeps_complete_source_and_instruction_without_rebase(rc3_browser, tmp_path):
    a, context, store, _, goto, _ = rc3_browser
    before = store.load_document()
    manuscript = {"pages": [manuscript_page("p01", "窗口 A 待导入的完整稿"),
                              store.read_object_json(before["pages"][1]["page"])]}
    source = tmp_path / "stale-source.json"
    source.write_text(json.dumps(manuscript, ensure_ascii=False), encoding="utf-8")
    original_source = source.read_bytes()
    link = goto()
    open_control_action(a, "导入确认稿")
    draft = a.get_by_role("dialog", name="导入确认稿")
    draft.get_by_label("确认稿 JSON 文件（必填）").set_input_files(source)
    expect(draft.get_by_role("button", name="确认导入确认稿", exact=True)).to_be_enabled()
    draft.get_by_label("本次明确要求（必填）").fill("窗口 A 保留的原始完整确认稿要求，不按后来的版本覆盖。")
    b = context.new_page()
    b.goto(link)
    open_control_action(b, "暂停本次请求")
    pause = b.get_by_role("dialog", name="暂停本次请求")
    pause.get_by_label("本次明确要求（必填）").fill("窗口 B 先暂停，窗口 A 的基准不得覆盖这次暂停。")
    pause.get_by_role("button", name="确认暂停本次请求", exact=True).click()
    expect(pause).to_contain_text("请求已记录")
    paused = store.load_document()
    with a.expect_response("**/draft/import") as response:
        draft.get_by_role("button", name="确认导入确认稿", exact=True).click()
    retain_http(response.value, tmp_path / "stale-import-http.json")
    assert response.value.status == 409
    expect(draft).to_contain_text("当前稿件、可读报告和本次输入均保留")
    expect(draft).to_contain_text("窗口 A 待导入的完整稿")
    expect(draft.get_by_label("本次明确要求（必填）")).to_have_value("窗口 A 保留的原始完整确认稿要求，不按后来的版本覆盖。")
    expect(draft.get_by_role("button", name="确认导入确认稿", exact=True)).to_be_hidden()
    assert store.load_document() == paused
    assert paused["pages"] == before["pages"]
    assert source.read_bytes() == original_source
    a.screenshot(path=str(tmp_path / "stale-import-keeps-source-and-instruction.png"), full_page=True)


def test_narrow_intake_full_scope_and_keyboard_remain_readable(rc3_browser, tmp_path):
    page, _, store, _, goto, _ = rc3_browser
    page.set_viewport_size({"width": 390, "height": 844})
    before = store.load_document()
    long_id = "source-" + "x" * 110
    source = tmp_path / "narrow-source.json"
    manuscript = {"pages": [store.read_object_json(entry["page"]) for entry in before["pages"]]
                           + [manuscript_page(long_id, "窄屏仍应完整核对新增页面及其来源范围")]}
    source.write_text(json.dumps(manuscript, ensure_ascii=False), encoding="utf-8")
    goto()
    open_control_action(page, "导入确认稿")
    dialog = page.get_by_role("dialog", name="导入确认稿")
    dialog.get_by_label("确认稿 JSON 文件（必填）").set_input_files(source)
    scope = dialog.get_by_role("button", name="按完整稿件明确新的请求范围", exact=True)
    expect(scope).to_be_enabled()
    dialog.get_by_label("完整稿件导入影响").scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path / "narrow-complete-scope.png"), full_page=True)
    assert dialog.evaluate("node => node.scrollWidth <= node.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    dialog.get_by_label("本次明确要求（必填）").fill("键盘核对完整稿件的明确范围，尚不写入。")
    scope.focus()
    page.keyboard.press("Enter")
    request = page.get_by_role("dialog", name="采用确认稿所需范围")
    expect(request).to_be_visible()
    expect(request.get_by_label("本次明确要求（必填）")).to_have_value("键盘核对完整稿件的明确范围，尚不写入。")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert store.load_document() == before
    assert json.loads(source.read_text()) == manuscript
