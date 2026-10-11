"""Geometry of layout sections; independent artwork retains its object boundary."""
import json
import os
from pathlib import Path
import pytest
from test_ui_design_browser import workbench_page  # noqa: F401

pytestmark = pytest.mark.browser

@pytest.mark.parametrize('width,height', [(1440,900),(1280,800),(1024,768),(830,900),(390,844)])
def test_layout_sections_and_style_routes(workbench_page, tmp_path, width, height):
    from playwright.sync_api import expect
    page=workbench_page
    page.set_viewport_size({'width':width,'height':height})
    out=Path(os.environ.get('CONTAINER_EVIDENCE',str(tmp_path/'evidence')))/str(width)
    out.mkdir(parents=True,exist_ok=True)
    records=[]
    def capture(name):
        page.evaluate('async()=>{await document.fonts.ready;scrollTo({top:0,behavior:"instant"})}')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), name
        sections=page.locator('[data-container=section]:visible').evaluate_all('''nodes=>nodes.map(n=>{const s=getComputedStyle(n);return {name:n.getAttribute('aria-label')||n.querySelector('h2')?.textContent,border:s.borderTopWidth,shadow:s.boxShadow}})''')
        assert all(s['border']=='0px' and s['shadow']=='none' for s in sections), sections
        page.screenshot(path=str(out/(name+'.png')),full_page=True)
        records.append({'name':name,'sections':sections,'url':page.url})
    for title in ['制作总览','内容与来源','整稿画廊','任务与交付','风格校准']:
        page.locator('.sidebar').get_by_role('button',name=title,exact=True).click()
        expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
        capture(title)
        if title=='任务与交付':
            for area in ['待决定','版本','文件']:
                page.get_by_role('button',name=area,exact=True).click();capture(title+'-'+area)
        if title=='风格校准':
            for route in ['项目页面','外部图片']:
                page.get_by_role('button',name=route,exact=True).click()
                expect(page.get_by_role('button',name=route,exact=True)).to_be_enabled()
                if route=='外部图片':expect(page.locator('.visual-style input[type=file]')).to_be_enabled()
                host=page.locator('.visual-style' if route=='外部图片' else '.style-calibration')
                nav=host.locator(':scope > .studio-style-stages')
                for i in range(4):
                    nav.get_by_role('button').nth(i).click()
                    capture(route+'-'+str(i+1))
                    phase=host.locator(':scope > section.style-phase:visible')
                    assert phase.count()==1
                    assert phase.evaluate('n=>getComputedStyle(n).borderTopWidth')=='0px'
                    assert phase.evaluate('n=>parseFloat(getComputedStyle(n).paddingLeft)')==0
                    for select in phase.locator('select:visible').all():
                        assert select.bounding_box()['width']<=480.01
                    if i==0:
                        cols=phase.locator('.studio-style-columns')
                        dims=cols.evaluate('n=>({width:n.getBoundingClientRect().width,children:[...n.children].map(c=>({x:c.getBoundingClientRect().x,y:c.getBoundingClientRect().y,width:c.getBoundingClientRect().width}))})')
                        if dims['width']<840:
                            assert abs(dims['children'][0]['x']-dims['children'][1]['x'])<1
                            assert dims['children'][1]['y']>dims['children'][0]['y']
                        for obj in phase.locator('.style-target-card').all()[:1]:
                            assert obj.evaluate('n=>parseFloat(getComputedStyle(n).borderTopWidth)')>=1
                            assert obj.locator('label').bounding_box()['height']>=43.99
    (out/'inventory.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))

@pytest.mark.parametrize('width,height', [(1440,900),(1280,800),(1024,768),(830,900),(390,844)])
def test_single_page_faces_and_content_sections(workbench_page,tmp_path,width,height):
    from urllib.parse import urlsplit,parse_qs,urlencode
    from playwright.sync_api import expect
    page=workbench_page
    page.set_viewport_size({'width':width,'height':height})
    out=Path(os.environ.get('CONTAINER_EVIDENCE',str(tmp_path/'evidence')))/str(width)
    out.mkdir(parents=True,exist_ok=True)
    def shot(name):
        page.evaluate('async()=>{await document.fonts.ready;scrollTo({top:0,behavior:"instant"})}')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name
        page.screenshot(path=str(out/(name+'.png')),full_page=True)
    page.locator('.sidebar').get_by_role('button',name='内容与来源',exact=True).click()
    for area in ['方案概览','逐页编辑与顺序','内容计划','工作笔记']:
        page.locator('.studio-content-areas').get_by_role('button',name=area,exact=True).click()
        shot('内容-'+area)
    original=urlsplit(page.url)
    params={k:v[0] for k,v in parse_qs(original.fragment).items()}
    params.update(surface='page',page='p01')
    for layer in ['source','content','prepared_prompt','original_image','svg','ppt']:
        params['layer']=layer
        page.goto(original._replace(fragment=urlencode(params)).geturl())
        page.locator('[aria-label="单页工具"]').wait_for()
        shot('单页-'+layer)
        for face in ['意见','试作与候选','图标优化','笔记','详情']:
            control=page.get_by_role('group',name='单页工具',exact=True).get_by_role('button',name=face,exact=True)
            control.click();expect(control).to_have_attribute('aria-pressed','true')
            if face=='详情' and layer in ['svg','ppt']:
                expect(page.locator('.page-tools .production-detail > h3')).to_be_visible()
                assert page.locator('.page-tools details.production-detail').count()==0
                expect(page.locator('.page-tools .production-facts')).to_be_visible()
                disclosures=page.locator('.page-tools .production-detail>.panel-body>details')
                boxes=disclosures.evaluate_all('ns=>ns.map(n=>({top:n.getBoundingClientRect().top,bottom:n.getBoundingClientRect().bottom}))')
                assert boxes[1]['top']-boxes[0]['bottom']>=8
            # Any remaining panel inside the single tool shell must be an
            # independent object, never a second decorated layout shell.
            sections=page.locator('.page-tools [data-container=section]:visible')
            assert sections.evaluate_all('ns=>ns.every(n=>getComputedStyle(n).boxShadow==="none" && parseFloat(getComputedStyle(n).borderTopWidth)===0)')
            shot('单页-'+layer+'-'+face)
            dialog=page.locator('dialog.page-tools-panel[open]')
            if dialog.count():dialog.get_by_role('button',name='回到画面',exact=True).click()
