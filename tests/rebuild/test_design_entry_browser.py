"""RP-21 real Chromium/no-reference service handoff, no image model call."""

import shutil
import pytest
from deck_master.web import WorkbenchServer
from test_styles import flow  # noqa: F401
from test_design_entry_basis import without_original

pytestmark = pytest.mark.browser


def test_no_reference_initial_basis_and_fixed_scope_handoff(flow, tmp_path):
    from playwright.sync_api import sync_playwright, expect

    before = without_original(flow)
    server = WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which("chromium"))
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(server.start() + "studio/")
            page.locator(".sidebar").get_by_role("button", name="风格校准", exact=True).click()
            panel = page.locator(".initial-design")
            expect(panel).to_be_visible()
            page.get_by_label("无参考初始设计目标").select_option("p02")
            page.get_by_label("初始设计要求").fill("保留正文与关系方向；先试单页，不继承旧图错误。")
            page.get_by_role("button", name="预览无参考初始试作", exact=True).click()
            expect(panel.get_by_label("本轮制作依据")).to_be_visible()
            expect(panel).to_contain_text("参考图：0 张")
            expect(page.get_by_role("button", name="保存并交接初始试作", exact=True)).to_be_enabled()
            assert flow.store.load_document() == before
            for width, height in ((1440, 900), (1280, 800), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(tmp_path / f"initial-basis-{width}.png"), full_page=True)
            page.get_by_role("button", name="保存并交接初始试作", exact=True).click()
            expect(page.locator(".initial-design")).to_have_count(0)
            after = flow.store.load_document()
            new_refs = [r for r in after["tasks"] if r not in before["tasks"]]
            assert len(new_refs) == 1
            task = flow.store.read_object_json(new_refs[0])
            assert task["scope_pages"] == ["p02"] and task["stage_request"]["references"] == []
            assert not task.get("generation_requests") and after["pages"][1]["blueprint"] is None
            assert not errors
        finally:
            browser.close()
            server.stop()
