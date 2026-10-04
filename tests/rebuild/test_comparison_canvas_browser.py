"""Shared canvas geometry and explicit actual-PPT states in real Chromium.
Synthetic state proves UI behavior, not production rendering quality.
"""
import pytest
from test_action_targets_browser import action_browser
from test_candidates import candidate

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('size',[(1280,800),(1440,900),(390,844)])
def test_intrinsic_zoom_independent_pan_and_disposal(action_browser,size):
    page, server, _, store = action_browser
    page.set_default_timeout(6000)
    page.set_viewport_size({'width':size[0],'height':size[1]})
    page.goto(server.start())
    page.get_by_role('heading', name='制作总览', exact=True).wait_for()
    page.evaluate("""async () => {
      const {comparisonCanvas}=await import('/v2/comparison-canvas.js');
      const {imagePool}=await import('/v2/images.js');
      const svg='<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="960" height="540" fill="#808080"/></svg>';
      const file={path:'.deckmaster/objects/ff/'+ 'f'.repeat(64)+'.svg',sha256:'f'.repeat(64)};
      const second={path:'.deckmaster/objects/ee/'+ 'e'.repeat(64)+'.svg',sha256:'e'.repeat(64)};
      window.fetchOriginal=window.fetch;window.fetch=(url,...args)=>String(url).includes('f'.repeat(64))?Promise.resolve(new Response(svg,{headers:{'Content-Type':'image/svg+xml'}})):String(url).includes('e'.repeat(64))?Promise.resolve(new Response(svg.replaceAll('960','1920').replaceAll('540','1080'),{headers:{'Content-Type':'image/svg+xml'}})):window.fetchOriginal(url,...args);
      window.poolBaseline=imagePool.snapshot().pinned;
      window.canvasTest=comparisonCanvas({info:{project_identity:'canvas-test'}},[{label:'基准',stage:{file}},{label:'候选',stage:{file:second}}]);
      document.querySelector('#app').replaceChildren(window.canvasTest.node);
      window.poolTest=imagePool;
    }""")
    page.locator('.comparison-viewport canvas').first.wait_for()
    assert page.locator('.comparison-viewport').count() == 2
    page.get_by_role('button', name='100%', exact=True).click()
    assert page.locator('.comparison-viewport canvas').first.evaluate('(n)=>n.getBoundingClientRect().width') == 960
    assert page.locator('.comparison-viewport canvas').nth(1).evaluate('(n)=>n.getBoundingClientRect().width') == 1920
    page.get_by_label('同步缩放和平移', exact=True).uncheck()
    page.locator('.comparison-viewport').nth(1).focus()
    page.get_by_role('button', name='放大', exact=True).click()
    assert page.locator('.comparison-viewport canvas').first.evaluate('(n)=>n.getBoundingClientRect().width') == 960
    assert page.locator('.comparison-viewport canvas').nth(1).evaluate('(n)=>n.getBoundingClientRect().width') == 2400
    page.get_by_label('同步缩放和平移', exact=True).check()
    assert page.locator('.comparison-viewport canvas').first.evaluate('(n)=>n.getBoundingClientRect().width') == 1200
    page.locator('.comparison-viewport').first.focus()
    page.locator('.comparison-viewport').first.evaluate('(n)=>n.scrollTo(200,70)')
    page.wait_for_timeout(80)
    positions = page.locator('.comparison-viewport').evaluate_all('(nodes)=>nodes.map(n=>(n.scrollLeft+n.clientWidth/2)/n.querySelector("canvas").getBoundingClientRect().width)')
    assert abs(positions[0] - positions[1]) < .002
    page.locator('.comparison-viewport').first.press('0')
    assert page.locator('.comparison-viewport').first.get_attribute('data-mode') == 'fit'
    page.get_by_role('button', name='全屏比较', exact=True).click()
    page.wait_for_function('()=>Boolean(document.fullscreenElement)')
    page.get_by_role('button', name='退出全屏', exact=True).click()
    page.wait_for_function('()=>!document.fullscreenElement')
    page.evaluate('window.canvasTest.dispose()')
    assert page.evaluate('window.poolTest.snapshot().pinned <= window.poolBaseline')
    assert page.evaluate('window.poolTest.snapshot().large_peak') <= 4


def test_candidate_ppt_requires_rendered_preview_and_late_results_stay_bound(action_browser):
    page, server, _, store = action_browser
    ids = [candidate(store, width=20), candidate(store, width=24)]
    page.route('**/api/candidate-preview/status?*', lambda route: route.fulfill(json={'status':'not_requested'}))
    page.set_default_timeout(6000)
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.locator('.action-target').first.get_by_role('button', name='查看这个对象').click()
    page.wait_for_selector('.candidate-desk[data-candidate-id="'+ids[0]+'"]')
    page.get_by_label('比较图层', exact=True).select_option('ppt')
    assert page.locator('.comparison-viewport canvas').count() == 0
    assert page.locator('.comparison-pair').get_by_text('候选实际 PPT 尚未生成', exact=True).count() == 1
    page.route('**/api/candidate-preview/request', lambda route: route.fulfill(json={'status':'needs_tool','candidate_id':ids[0],'error':{'message':'renderer absent'}}))
    page.get_by_role('button', name='生成候选实际 PPT', exact=True).click()
    page.locator('.comparison-preview-tools').get_by_text('缺少实际 PPT 编译或渲染工具', exact=True).wait_for()
    assert not page.get_by_text('renderer absent', exact=True).is_visible()
    page.get_by_text('查看检查详情', exact=True).click()
    assert 'renderer absent' in page.locator('.comparison-preview-details').inner_text()
    assert page.locator('.comparison-viewport canvas').count() == 0
    page.get_by_label('比较图层', exact=True).select_option('svg')
    page.locator('.comparison-viewport canvas').first.wait_for()
    page.get_by_label('选择本页候选', exact=True).select_option(ids[1])
    page.wait_for_selector('.candidate-desk[data-candidate-id="'+ids[1]+'"]')
    page.get_by_label('比较图层', exact=True).select_option('ppt')
    page.locator('.comparison-preview-tools').get_by_text('候选实际 PPT 尚未生成', exact=True).wait_for()
    assert page.locator('.comparison-viewport canvas').count() == 0


def test_actual_ppt_bytes_must_match_check_and_candidate_identity(action_browser):
    import hashlib
    import io
    from PIL import Image
    page, server, _, store = action_browser
    page.set_default_timeout(6000)
    candidate_id = candidate(store, width=20)
    data = io.BytesIO()
    Image.new('RGB', (320, 180), '#9b9b9b').save(data, format='PNG')
    png = data.getvalue()
    checksum = hashlib.sha256(png).hexdigest()
    cache_key = 'a' * 64
    calls = []

    def preview(route):
        calls.append(route.request.post_data_json)
        # First report's expected bytes intentionally disagree with its file.
        # Then an explicit retry returns the correctly bound synthetic report.
        expected = 'b' * 64 if len(calls) == 1 else checksum
        route.fulfill(json={'status':'ready','candidate_id':candidate_id,'check_id':'check-'+str(len(calls)),
                            'files':{'candidate.png':{'file':{'path':'.deckmaster/cache/candidate-previews/'+cache_key+'/candidate.png','sha256':expected}}}})

    page.route('**/api/candidate-preview/status?*', lambda route: route.fulfill(json={'status':'not_requested'}))
    page.route('**/api/candidate-preview/request', preview)
    page.route('**/api/candidate-preview/file?*', lambda route: route.fulfill(body=png, content_type='image/png'))
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.wait_for_selector('.candidate-desk[data-candidate-id="'+candidate_id+'"]')
    page.get_by_label('比较图层', exact=True).select_option('ppt')
    page.get_by_role('button', name='生成候选实际 PPT', exact=True).click()
    page.locator('.comparison-pair').get_by_text('实际 PPT 预览已经更新，请重新读取检查结果。', exact=True).wait_for()
    assert page.locator('.comparison-viewport canvas').count() == 0
    page.get_by_role('button', name='重新检查候选实际 PPT', exact=True).click()
    page.locator('.comparison-viewport canvas').wait_for()
    page.get_by_role('button', name='100%', exact=True).click()
    assert page.locator('.comparison-viewport canvas').evaluate('(n)=>n.getBoundingClientRect().width') == 320
    assert all(request['candidate_id'] == candidate_id for request in calls)
    page.get_by_label('比较图层', exact=True).select_option('svg')
    assert page.locator('.comparison-pair').get_by_text('SVG', exact=True).count() > 0


@pytest.mark.parametrize('size',[(1280,800),(1440,900),(390,844)])
def test_candidate_fullscreen_fit_keeps_both_canvases_above_actions(action_browser,size):
    page, server, _, store = action_browser
    candidate_id = candidate(store, width=20)
    page.set_viewport_size({'width':size[0],'height':size[1]})
    page.route('**/api/candidate-preview/status?*', lambda route: route.fulfill(json={'status':'not_requested'}))
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button', name='比较候选', exact=True).click()
    page.wait_for_selector('.candidate-desk[data-candidate-id="'+candidate_id+'"]')
    page.locator('.comparison-viewport canvas').last.wait_for()
    page.get_by_role('button', name='全屏比较', exact=True).click()
    page.wait_for_function('()=>Boolean(document.fullscreenElement)')
    page.get_by_role('button', name='适应窗口', exact=True).click()
    page.wait_for_timeout(100)
    geometry=page.evaluate('''()=>({height:innerHeight,actions:document.querySelector('.candidate-decisions').getBoundingClientRect().top,
        canvases:[...document.querySelectorAll('.comparison-viewport canvas')].map(n=>({top:n.getBoundingClientRect().top,bottom:n.getBoundingClientRect().bottom})),
        viewports:[...document.querySelectorAll('.comparison-viewport')].map(n=>({top:n.getBoundingClientRect().top,bottom:n.getBoundingClientRect().bottom,height:n.clientHeight}))})''')
    assert geometry['canvases']
    assert all(v['height']>0 and v['bottom']<=geometry['actions'] for v in geometry['viewports']), geometry
    assert all(c['top']>=0 and c['bottom']<=geometry['actions']<=geometry['height'] for c in geometry['canvases'])
    page.get_by_role('button', name='退出全屏', exact=True).click()


def test_missing_candidate_font_has_clear_guidance_and_collapsed_technical_detail(action_browser):
    page, server, _, store = action_browser
    candidate_id=candidate(store,width=20)
    page.route('**/api/candidate-preview/status?*', lambda route: route.fulfill(json={'status':'needs_tool','candidate_id':candidate_id,
        'error':{'code':'needs_tool','message':'font Missing QA Font unavailable; explicitly choose an installed font in design and SVG'}}))
    page.goto(server.start())
    page.locator('.todo-priority').get_by_role('button',name='比较候选',exact=True).click()
    page.wait_for_selector('.candidate-desk[data-candidate-id="'+candidate_id+'"]')
    expected='候选字体“Missing QA Font”尚未安装。请在设计与 SVG 中明确选用已安装字体，再重新检查。'
    page.locator('.comparison-preview-tools').get_by_text(expected,exact=True).wait_for()
    assert not page.locator('.comparison-preview-details pre').is_visible()
    page.get_by_label('比较图层',exact=True).select_option('ppt')
    assert page.locator('.comparison-viewport canvas').count()==0
    assert page.locator('.comparison-pair').get_by_text(expected,exact=True).is_visible()
    page.get_by_text('查看检查详情',exact=True).click()
    assert 'explicitly choose an installed font' in page.locator('.comparison-preview-details pre').inner_text()
