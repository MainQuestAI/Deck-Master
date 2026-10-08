"""Real-browser regressions for the received design's production adaptations."""
from pathlib import Path
import shutil
import re

import pytest

from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.fixture
def workbench_page(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as runtime:
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and not Path(runtime.chromium.executable_path).exists():
            pytest.skip('Chromium is required for real UI geometry and keyboard checks')
        browser = runtime.chromium.launch(executable_path=executable, args=['--no-sandbox'])
        project = tmp_path / 'sample'
        create_gallery_sample(project, page_count=24, readonly=False)
        server = WorkbenchServer(project)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        try:
            page.goto(server.start())
            page.get_by_role('heading', name='制作总览', exact=True).wait_for()
            yield page
        finally:
            browser.close()
            server.stop()


def test_matrix_title_geometry_and_mobile_navigation(workbench_page):
    page = workbench_page
    for width in (360, 390, 430, 600, 820, 1024, 1280, 1366, 1440, 1920):
        page.set_viewport_size({'width': width, 'height': 900})
        # Seven design columns plus a production-only selection column must not
        # squeeze the title into one-character lines or overflow the document.
        dims = page.evaluate('''() => {
          const title = document.querySelector('.matrix .title-button');
          const row = title.closest('tr');
          const head = document.querySelector('.matrix thead tr');
          return {width: innerWidth, scroll: document.documentElement.scrollWidth,
            title: title.getBoundingClientRect().width,
            aligned: [...row.children].every((cell, i) =>
              Math.abs(cell.getBoundingClientRect().x - head.children[i].getBoundingClientRect().x) < 1),
            labels: [...document.querySelectorAll('.nav-label')].every(x => getComputedStyle(x).display !== 'none')};
        }''')
        assert dims['scroll'] <= dims['width'] and dims['title'] >= 280
        assert dims['aligned'] and dims['labels']
    assert page.locator('.brand-logo').evaluate('(image) => image.complete && image.naturalWidth > 0')


def test_matrix_keyboard_selection_sort_and_search_keep_focus(workbench_page):
    from playwright.sync_api import expect
    page = workbench_page
    first = page.get_by_role('checkbox', name='选择第 01 页', exact=True)
    first.focus()
    first.press('Space')
    expect(first).to_be_checked()
    expect(first).to_be_focused()
    page.keyboard.press('Space')
    expect(first).not_to_be_checked()
    expect(first).to_be_focused()
    all_pages = page.get_by_role('checkbox', name='选择当前筛选内所有可操作页面', exact=True)
    all_pages.focus()
    page.keyboard.press('Space')
    expect(all_pages).to_be_checked()
    expect(all_pages).to_be_focused()
    sort = page.get_by_role('button', name='页面 · 升序', exact=True)
    sort.focus()
    page.keyboard.press('Enter')
    expect(page.get_by_role('button', name='页面 · 降序', exact=True)).to_be_focused()
    expect(page.locator('.matrix thead th[aria-sort]')).to_have_attribute('aria-sort', 'descending')
    search = page.get_by_role('searchbox', name='搜索页码或标题', exact=True)
    search.fill('p02')
    expect(search).to_be_focused()
    expect(page.locator('.matrix tbody .title-button')).to_have_count(1)
    # D1：搜索是筛选，保留批量选择——全选选中的第 02 页仍是选中状态。
    expect(page.get_by_role('checkbox', name='选择第 02 页', exact=True)).to_be_checked()


def test_page_shortcuts_respect_controls_and_dialogs(workbench_page):
    page = workbench_page
    page.get_by_role('button', name='打开第 01 页', exact=True).click()
    page.get_by_role('heading', name=re.compile(r'^第 1 页')).wait_for()
    url = page.url
    page.locator('main button:not([disabled])').first.press('ArrowRight')
    assert page.url == url
    page.locator('#view-title').focus()
    page.keyboard.press('ArrowRight')
    page.get_by_role('heading', name=re.compile(r'^第 2 页')).wait_for()
    assert page.url != url
    page.get_by_role('button', name='连接状态', exact=True).click()
    url = page.url
    page.keyboard.press('Escape')
    assert page.locator('dialog[open]').count() == 0 and page.url == url
    from playwright.sync_api import expect
    expect(page.get_by_role('button', name='连接状态', exact=True)).to_be_focused()


def test_picker_cancel_and_failure_preserve_path_and_manual_focus(workbench_page):
    from playwright.sync_api import expect
    page=workbench_page
    page.evaluate('''async()=>{
      const {launcher}=await import('/v2/launcher-ui.js');const original=window.fetch;
      window.pickerOutcome={status:'cancelled',path:null};
      window.fetch=async(url,...args)=>String(url)==='/api/projects'?new Response(JSON.stringify({projects:[]})):String(url)==='/api/directories/pick'?new Response(JSON.stringify(window.pickerOutcome)):original(url,...args);
      const root=document.createElement('div');root.id='picker-test';document.body.append(root);await launcher(root,{service_version:'test'});
    }''')
    page.locator('#picker-test').get_by_role('button',name='选择项目文件夹',exact=True).click()
    path=page.get_by_role('textbox',name='项目文件夹',exact=True)
    path.fill('/existing/project')
    page.get_by_role('button',name='浏览文件夹',exact=True).click()
    expect(path).to_have_value('/existing/project')
    for status in ('timed_out','failed','busy','manual_path_required'):
        page.evaluate("status=>window.pickerOutcome={status,path:null,diagnostic:{message:status+' diagnostic'}}",status)
        page.get_by_role('button',name='浏览文件夹',exact=True).click()
        expect(path).to_be_focused();expect(path).to_have_value('/existing/project')
        expect(page.get_by_text(status+' diagnostic 当前输入保留，可直接填写完整路径。',exact=True)).to_be_visible()
    page.evaluate("()=>window.pickerOutcome={status:'selected',path:'/selected/project'}")
    page.get_by_role('button',name='浏览文件夹',exact=True).click();expect(path).to_have_value('/selected/project')
    page.keyboard.press('Escape')


def test_damaged_personal_reading_does_not_block_workbench(workbench_page,tmp_path):
    from playwright.sync_api import expect
    page=workbench_page;path=tmp_path/'sample/.deckmaster/workbench/result-reading.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text('damaged reading record')
    page.reload();page.get_by_role('heading',name='制作总览',exact=True).wait_for()
    expect(page.get_by_text('个人已读记录暂不可用，已显示未过滤的业务记录；损伤文件保留，请先核实恢复资料。',exact=True)).to_be_visible()
    # 沿导航按钮切换工作面（真实用户路径）。手工改写 hash 会把总览偏好参数带进
    # runs 路由而被路由守卫拒绝——那是链接校验，不是本测试的对象。
    page.get_by_role('button',name='任务与交付',exact=True).click()
    page.get_by_role('heading',name='运行记录',exact=True).wait_for()
    expect(page.get_by_text('个人已读记录暂不可用，任务按未过滤状态展示；损伤文件保留，标记已读暂停。',exact=True)).to_be_visible()
    assert path.read_text()=='damaged reading record'


def test_modal_falls_back_to_the_caller_provided_focus_when_trigger_gone(workbench_page):
    # O2/P01：触发器被移除时，弹窗关闭后焦点回调用方指定的目标（工具标题），
    # 没有指定则维持回工作面标题。
    page = workbench_page
    outcome = page.evaluate('''async () => {
      const {modal} = await import('/v2/dom.js');
      const group = document.createElement('section'); document.body.append(group);
      group.innerHTML = '<button id="p01-trigger">打开比较</button><h2 id="p01-fallback" tabindex="-1">工具标题</h2><h2 id="p01-plain">页面标题</h2>';
      const trigger = group.querySelector('#p01-trigger');
      trigger.focus();
      const dialog = modal('范围比较', document.createElement('p'));
      await new Promise(r => setTimeout(r, 40));
      trigger.remove();
      dialog.close();
      await new Promise(r => setTimeout(r, 40));
      const withoutFallback = document.activeElement.id;

      const second = document.createElement('button'); second.textContent = '触发';
      group.append(second); second.focus();
      const dialog2 = modal('范围比较', document.createElement('p'), [], {fallback: group.querySelector('#p01-fallback')});
      await new Promise(r => setTimeout(r, 40));
      second.remove();
      dialog2.close();
      await new Promise(r => setTimeout(r, 40));
      return {withoutFallback, withFallback: document.activeElement.id, top: group.querySelector('#p01-plain').isConnected};
    }''')
    assert outcome['withoutFallback'] == 'view-title'
    assert outcome['withFallback'] == 'p01-fallback'
