"""Real Chromium + core transactions, synthetic image; no professional acceptance."""
import uuid
import pytest
from deck_master import tasks
from deck_master.web import WorkbenchServer
from test_styles import flow  # noqa: F401
from test_visual_styles import result,image_bytes

pytestmark=pytest.mark.browser


def test_screenshot_ui_upload_reasoning_confirmation_dispatch_and_restore(flow):
    from playwright.sync_api import sync_playwright,expect
    server=WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(args=['--no-sandbox']);page=browser.new_page(viewport={'width':1280,'height':800});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(server.start());page.get_by_role('heading',name='制作总览',exact=True).wait_for()
            page.get_by_role('button',name='风格校准',exact=True).click()
            page.get_by_role('combobox',name='风格参考来源').select_option('screenshot')
            before=flow.store.load_document()['pages']
            page.get_by_role('textbox',name='截图风格要求').fill('Use palette and hierarchy from this screenshot')
            page.get_by_role('combobox',name='截图风格试作目标').select_option('p02')
            page.get_by_label('导入参考截图',exact=True).set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':image_bytes()})
            expect(page.get_by_role('checkbox',name='选用参考截图 1')).to_be_checked()
            page.get_by_role('button',name='分析截图',exact=True).click()
            expect(page.get_by_role('button',name='查看分析结果',exact=True)).to_be_enabled()
            doc=flow.store.load_document();task=next(flow.store.read_object_json(ref) for ref in reversed(doc['tasks']) if flow.store.read_object_json(ref)['kind']=='style_analyze')
            row=flow.store.read_object_json(doc['style_references'][0]);flow.start(task)
            tasks.accept_result(flow.store,task_id=task['task_id'],operation_id=task['operation_id'],produced_against=task['produced_against'],envelope_raw=result(row['reference_id']))
            page.reload();page.get_by_role('button',name='查看分析结果',exact=True).click();page.get_by_role('textbox',name='配色规范').wait_for()
            page.get_by_role('textbox',name='配色规范').fill('Use blue #225588 and white')
            page.get_by_role('button',name='检查并确认视觉规范',exact=True).click()
            expect(page.get_by_role('button',name='预览单页试作',exact=True)).to_be_enabled()
            assert flow.store.load_document()['pages']==before
            page.get_by_role('button',name='预览单页试作',exact=True).click()
            expect(page.get_by_role('button',name='保存并交接试作',exact=True)).to_be_enabled()
            page.get_by_role('button',name='保存并交接试作',exact=True).click()
            page.get_by_role('heading',name='当前任务',exact=True).wait_for()
            assert flow.store.load_document()['pages']==before
            assert not errors
        finally:
            if errors: print('BROWSER ERRORS', errors)

            browser.close();server.stop()


def test_large_reference_catalog_releases_images_and_preserves_selection(flow):
    from deck_master import visual_styles
    from playwright.sync_api import sync_playwright,expect
    from PIL import Image
    from io import BytesIO
    # Use unique registered bytes so shared image identities cannot mask leaks.
    for i in range(65):
        stream=BytesIO();Image.new('RGB',(64,36),(i,100,200)).save(stream,format='PNG')
        visual_styles.import_reference(flow.project,data=stream.getvalue(),base_revision=flow.store.current_revision_id(),operation_id=str(uuid.uuid4()))
    server=WorkbenchServer(flow.project)
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':800})
        try:
            page.goto(server.start());page.get_by_role('heading',name='制作总览',exact=True).wait_for();page.get_by_role('button',name='风格校准',exact=True).click();page.get_by_role('combobox',name='风格参考来源').select_option('screenshot')
            page.get_by_role('checkbox',name='选用参考截图 1',exact=True).check()
            for _ in range(5):page.get_by_role('button',name='下一组参考',exact=True).click()
            expect(page.get_by_role('checkbox',name='选用参考截图 65',exact=True)).to_be_visible()
            expect(page.get_by_role('checkbox',name='选用参考截图 1',exact=True)).to_be_checked()
            assert page.locator('.visual-reference-choice').count()<=17
            page.get_by_role('checkbox',name='选用参考截图 65',exact=True).check()
            for _ in range(5):page.get_by_role('button',name='上一组参考',exact=True).click()
            expect(page.get_by_role('checkbox',name='选用参考截图 65',exact=True)).to_be_checked()
            assert page.locator('.visual-reference-choice').count()<=17
            assert '阅读位已满' not in page.locator('.visual-reference-list').inner_text()
        finally:browser.close();server.stop()
