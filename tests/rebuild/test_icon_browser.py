"""Real UI integration; synthetic pages and zero model calls."""
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlencode
import pytest
from deck_master import icons, tasks
from deck_master.web import WorkbenchServer
from test_icon_quality import icon_store, input_for

pytestmark=pytest.mark.browser

@pytest.fixture
def icon_browser(icon_store):
    from playwright.sync_api import sync_playwright
    server=WorkbenchServer(icon_store.project_root);url=server.start()
    with sync_playwright() as runtime:
        executable=shutil.which('chromium') or shutil.which('chromium-browser')
        browser=runtime.chromium.launch(executable_path=executable,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.get_by_role('heading',name='制作总览',exact=True).wait_for()
        info=page.request.get(url.rstrip('/')+'/api/project').json()
        page.goto(url.split('#')[0]+'#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p01','layer':'svg','revision':icon_store.current_revision_id()}))
        page.get_by_role('heading',name='优化图标',exact=True).wait_for()
        try:yield page,icon_store,errors
        finally:browser.close();server.stop()
    assert errors==[]


def test_icon_proposal_compare_confirm_keyboard_and_dispatch(icon_browser,tmp_path):
    from playwright.sync_api import expect
    page,store,errors=icon_browser;before=store.load_document()
    icons.propose(store.project_root,input=input_for(store,method='standard'))
    page.get_by_role('button',name='刷新图标方案',exact=True).click()
    page.get_by_role('button',name='查看 p01 的图标范围',exact=True).wait_for()
    page.get_by_role('button',name='查看 p01 的图标范围',exact=True).focus();page.keyboard.press('Enter')
    dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
    page.locator('.icon-comparison canvas').first.wait_for()
    for width,height in [(1280,800),(1440,900),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        page.get_by_label('显示正常页面尺寸').check()
        page.get_by_label('显示正常页面尺寸').uncheck()
        page.get_by_label('图标局部放大倍数').select_option('4')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(tmp_path/f'icon-{width}.png'))
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
    page.get_by_role('button',name='确认这些图标范围和处理方式',exact=True).click()
    page.get_by_label('选入图标页 p01').wait_for()
    assert store.load_document()['pages']==before['pages']
    expect(page.get_by_label('选入图标页 p01')).not_to_be_checked()
    page.get_by_label('选入图标页 p01').check()
    page.get_by_role('button',name='预览选中页图标试作',exact=True).click()
    page.get_by_role('button',name='确认计划并交接图标修复',exact=True).wait_for()
    page.get_by_role('button',name='确认计划并交接图标修复',exact=True).click()
    page.get_by_role('heading',name='优化图标',exact=True).wait_for(state='hidden')
    doc=store.load_document();new=[store.read_object_json(t) for t in doc['tasks'] if store.read_object_json(t).get('stage_request',{}).get('icon_recipe_ref')]
    assert len(new)==1 and 'icon_repair' in new[0]['required_capabilities']
    assert doc['pages']==before['pages'] and doc['outputs']==before['outputs'] and errors==[]
    snapshot=page.evaluate("async()=> (await import('/v2/images.js')).imagePool.snapshot()")
    assert snapshot['network_peak']<=6 and snapshot['decode_peak']<=2 and snapshot['large_peak']<=4


def test_local_zoom_preserves_aspect_ratio_at_canvas_limit(icon_browser):
    page,store,_=icon_browser
    entry=store.load_document()['pages'][0];file=store.read_object_json(entry['svg'])['file']
    info=page.request.get(page.url.split('#')[0].rstrip('/')+'/api/project').json()
    page.evaluate('''async ({identity,file})=>{
      const {iconComparison}=await import('/v2/icon-workbench.js');
      window.aspectProbe=iconComparison({info:{project_identity:identity}},[{title:'比例检查',file,region:{x:0,y:0,width:1,height:1}}]);
      document.body.append(window.aspectProbe.node);
    }''',{'identity':info['project_identity'],'file':file})
    page.locator('select[aria-label="图标局部放大倍数"]').select_option('8')
    page.wait_for_function('document.querySelector(".icon-comparison canvas").width===2048')
    dimensions=page.locator('.icon-comparison canvas').evaluate('(n)=>[n.width,n.height]')
    assert dimensions[0]==2048 and abs(dimensions[1]-1152)<=2
    page.evaluate('()=>{window.aspectProbe.dispose();window.aspectProbe.node.remove();delete window.aspectProbe;}')


def test_icon_http_cli_parity_and_origin(icon_store,tmp_path,capsys):
    from deck_master import cli
    from test_web import _get_json,_post_json,_session_token
    server=WorkbenchServer(icon_store.project_root);url=server.start().rstrip('/')
    try:
        token=_session_token(url);value=input_for(icon_store)
        assert _post_json(url+'/api/icons/propose',{'input':value},None,None)[0]==403
        code,result=_post_json(url+'/api/icons/propose',{'input':value},token,url);assert code==200
        inp=tmp_path/'input.json';inp.write_text(json.dumps(value))
        assert cli.main(['icons','propose','--project',str(icon_store.project_root),'--input',str(inp)])==0
        assert json.loads(capsys.readouterr().out)==result
        assert _get_json(url+'/api/icons/inspect?page_id=p01')[2]==icons.inspect(icon_store.project_root,page_id='p01')
        assert _post_json(url+'/api/icons/confirm',{'unknown':True},token,url)[0]==422
    finally:server.stop()


def test_actual_icon_candidate_ppt_comparison_retry_and_adoption(icon_browser,tmp_path):
    from playwright.sync_api import expect
    from deck_master import candidate_preview,candidates
    from test_icon_quality import confirm,dispatch,start,accept
    page,store,errors=icon_browser
    recipe=confirm(store,input_for(store,method='standard'));task=dispatch(store,recipe)[0];start(store,task)
    cid=accept(store,task,icons.draft(store.project_root,recipe_id=recipe['recipe_id'],page_id='p01')['svg'].encode())['candidate_ids'][0]
    url=page.url.split('#')[0];info=page.request.get(url.rstrip('/')+'/api/project').json()
    page.goto(url+'#'+urlencode({'project':info['project_identity'],'surface':'page','page':'p01','layer':'svg','revision':store.current_revision_id(),'candidate':cid}))
    page.get_by_role('heading',name='候选图标实际检查',exact=True).wait_for()
    page.get_by_role('button',name='打开局部对照',exact=True).click();page.get_by_label('图标比较产物').select_option('ppt')
    expect(page.get_by_text('此固定基准没有有效的实际 PPT 预览',exact=True)).to_be_visible()
    assert page.locator('.candidate-icon-review canvas').count()==1
    page.get_by_role('button',name='生成或重试实际 PPT 检查',exact=True).click()
    expect(page.locator('.candidate-icon-review [role=status]')).to_contain_text('工程检查通过',timeout=60000)
    expect(page.locator('.candidate-icon-review canvas')).to_have_count(2)
    for width,height in ((1280,800),(1440,900),(390,844)):
        page.set_viewport_size({'width':width,'height':height});page.get_by_label('显示正常页面尺寸').check();page.get_by_label('显示正常页面尺寸').uncheck();page.get_by_label('图标局部放大倍数').select_option('8')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    fixed_url=page.url
    canvas=page.locator('.candidate-icon-review canvas').last
    canvas.focus();canvas.press('ArrowRight');canvas.press('ArrowLeft')
    page.evaluate("()=>{const control=document.querySelector('[aria-label=\"图标比较产物\"]');control.value='svg';control.dispatchEvent(new Event('change'));}")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')")=='候选 SVG'
    page.evaluate("()=>{const control=document.querySelector('[aria-label=\"图标比较产物\"]');control.value='ppt';control.dispatchEvent(new Event('change'));}")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')")=='候选实际 PPT'
    assert page.url==fixed_url
    page.screenshot(path=str(tmp_path/'actual-icon-ppt-comparison.png'),full_page=True)
    page.get_by_role('button',name='预览采用这个候选',exact=True).click();page.get_by_role('button',name='采用这个候选',exact=True).wait_for()
    page.get_by_role('button',name='采用这个候选',exact=True).click();expect(page.get_by_text(re.compile('这个候选已采用到'))).to_be_visible()
    assert store.load_document()['pages'][0]['svg']==candidates.show(store.project_root,candidate_id=cid)['candidate']['result_ref']
    assert icons.listing(store.project_root)['samples']
    pool=page.evaluate("async()=> (await import('/v2/images.js')).imagePool.snapshot()")
    assert pool['large_peak']<=4 and pool['decode_peak']<=2 and pool['network_peak']<=6 and errors==[]


def test_saved_sample_identity_survives_reorder_and_missing(icon_browser):
    page,store,_=icon_browser
    outcome=page.evaluate('''async()=>{
      const {iconWorkbench,sampleKey}=await import('/v2/icon-workbench.js');
      const a={sample_candidate_id:'candidate-a',sample_icon_index:0,page_id:'p01',label:'A',semantic_key:'file'};
      const b={sample_candidate_id:'candidate-b',sample_icon_index:0,page_id:'p02',label:'B',semantic_key:'file'};
      const original=window.fetch;let samples=[b,a];
      window.fetch=async(url,...args)=>String(url).startsWith('/api/icons/list')?new Response(JSON.stringify({samples,proposals:[],recipes:[]})):original(url,...args);
      const app={business:{entries:new Map()},health:{ui_capabilities:['icon_quality.v1']},route:{layer:'svg'},root:document.createElement('div'),disposables:[],editor:{draft:{content:{icon_ui:{method:'reuse',sample_identity:a}}},ready:Promise.resolve(),changed(){}}};
      async function build(){const root=iconWorkbench(app,{page_id:'p01',stages:{content:{ref:{sha256:'content'}},blueprint:{existence:'recorded',ref:{sha256:'bp'},file:'bp.png'},svg:{existence:'recorded',ref:{sha256:'svg'},file:'layer.svg'},ppt_preview:{existence:'not_generated'}}});document.body.append(root);for(let i=0;i<100&&!root.querySelector('[aria-label="已采用图标样例"]').options.length;i++)await new Promise(r=>setTimeout(r,10));return root;}
      let root=await build();const restored=root.querySelector('[aria-label="已采用图标样例"]').value;root.remove();samples=[b];root=await build();
      const missing=root.querySelector('[aria-label="已采用图标样例"]').value;const warning=root.textContent.includes('请重新选择');root.remove();samples=[];root=await build();const emptyMethod=root.querySelector('[aria-label="图标处理方式"]').value;root.querySelectorAll('button')[1].click();await new Promise(r=>setTimeout(r,10));const blocked=root.textContent.includes('请重新选择');root.remove();app.disposables.forEach(fn=>fn());window.fetch=original;
      return {restored,expected:sampleKey(a),missing,warning,emptyMethod,blocked};
    }''')
    assert outcome['restored']==outcome['expected'] and outcome['missing']=='' and outcome['warning'] and outcome['emptyMethod']=='reuse' and outcome['blocked']


def test_missing_compare_column_keeps_stable_focus_identity(icon_browser):
    page,store,_=icon_browser
    file=store.read_object_json(store.load_document()['pages'][0]['svg'])['file']
    identity=page.request.get(page.url.split('#')[0].rstrip('/')+'/api/project').json()['project_identity']
    page.evaluate("""async({identity,file})=>{
      const {iconComparison}=await import('/v2/icon-workbench.js');
      const region={x:0,y:0,width:1,height:1};window.focusProbe=iconComparison({info:{project_identity:identity}},[{title:'原图',file,region},{title:'缺少基准实际 PPT',file:null,region},{title:'候选实际 PPT',file,region}]);document.body.append(window.focusProbe.node);
    }""",{'identity':identity,'file':file})
    page.locator('[data-icon-column="2"]').focus()
    assert page.locator('[data-icon-column="2"]').get_attribute('aria-label')=='候选实际 PPT'
    page.locator('[data-icon-column="1"]').focus();fixed=page.url;page.keyboard.press('ArrowRight');assert page.url==fixed
    page.evaluate('()=>{focusProbe.dispose();focusProbe.node.remove();delete window.focusProbe;}')


def test_icon_opinion_scope_and_basis_rows(icon_browser):
    # §3.1/UAC25 参数行：page 意见可列入；其它页排除；仅 revision 推进不判失效；
    # artifact_ref 变化才标旧底稿；复制沿用合法 page 字段不补造 layer/artifact_ref。
    import copy as copy_mod
    import uuid as uuid_mod
    from playwright.sync_api import expect
    from deck_master import annotation_service
    from deck_master.models import bump_revision
    page,store,errors=icon_browser
    url=page.url.split('#')[0];info_identity=re.search(r'project=([^&#]+)',page.url.split('#')[1]).group(1)
    doc=store.load_document();entry=next(e for e in doc['pages'] if e['page_id']=='p01')
    def note(scope,page_id,page_ref,**extra):
        return {'schema_version':'annotation.v1','project_id':doc['project_id'],'base_revision':doc['revision_id'],
                'scope':scope,'page_id':page_id,'page_ref':page_ref,'intent':'clarify','body':NOTE_BODIES[scope][page_id],'status':'open','location':{'kind':'whole'},**extra}
    NOTE_BODIES={'page':{'p01':'整页意见正文样例。','p02':'其它页整页意见不入本页。'},'artifact':{'p01':'SVG 层意见样例。'}}
    page_ref_p01=note('page','p01',entry['page']);page_ref_p02=note('page','p02',next(e['page'] for e in doc['pages'] if e['page_id']=='p02'))
    artifact_ref_p01=note('artifact','p01',entry['page'],layer='svg',artifact_ref=entry['svg'])
    annotation_service.save(store.project_root,input={'schema_version':'annotation_batch.v1','project_id':doc['project_id'],
        'annotations':[page_ref_p01,page_ref_p02,artifact_ref_p01]},base_revision=doc['revision_id'],operation_id=str(uuid_mod.uuid4()))
    # 推进一次修订但所有产物引用不变：意见不得因 base_revision 落后被判失效。
    doc=store.load_document();bumped=bump_revision(copy_mod.deepcopy(doc),{'operation_id':str(uuid_mod.uuid4()),'kind':'task_update','description':'revision advance without content change','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=bumped,operation_id=bumped['change']['operation_id'])
    # 再实际重做 SVG 图层:p01 的 svg 引用变化,SVG 范围意见转为旧底稿。
    doc=store.load_document();new=copy_mod.deepcopy(doc);svg_entry=next(e for e in new['pages'] if e['page_id']=='p01')
    svg_doc=store.read_object_json(svg_entry['svg']);svg_doc['file']=store.put_blob(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540"><rect width="960" height="540" fill="#eeeeee"/><text x="40" y="90">REGENERATED</text></svg>',ext='svg')
    svg_entry['svg']=store.put_json_object(svg_doc)
    bumped=bump_revision(new,{'operation_id':str(uuid_mod.uuid4()),'kind':'artifact_adoption','description':'regenerated svg','read_set':[]})
    store.commit_change(base_revision=doc['revision_id'],document=bumped,operation_id=bumped['change']['operation_id'])
    page.goto(url+'#'+urlencode({'project':info_identity,'surface':'page','page':'p01','layer':'svg','revision':store.current_revision_id()}))
    workbench=page.locator('.icon-workbench');workbench.wait_for(timeout=15000)
    page_box=workbench.locator('label').filter(has_text='整页意见正文样例')
    expect(page_box).to_contain_text('整页文字定位')
    expect(page_box).to_contain_text('与当前产物一致')
    expect(workbench.locator('label').filter(has_text='SVG 层意见样例')).to_contain_text('旧底稿意见 · 需重新定位')
    expect(workbench.get_by_role('status')).not_to_contain_text('已不在本页图标列表')
    assert workbench.locator('label.icon-opinion').count()==2
    page_box.locator('input[type=checkbox]').check()
    page.evaluate("() => {window.iconCopy = null; Object.defineProperty(navigator, 'clipboard', {value: {writeText: async text => {window.iconCopy = text;}}});}")
    workbench.get_by_role('button',name='复制给 Agent 的图标要求',exact=True).click()
    expect(workbench.get_by_role('status')).to_contain_text('图标要求已复制。尚未启动任务')
    payload=page.evaluate('JSON.parse(window.iconCopy)')
    listing=page.request.get(url+'api/annotations').json()
    page_record=next(r for r in listing['annotations'] if r['annotation']['scope']=='page' and r['annotation']['page_id']=='p01')
    assert payload['annotation_refs']==[page_record['ref']]
    assert payload['opinions'][0]['body']=='整页意见正文样例。'
    assert 'layer' not in payload['opinions'][0] and 'artifact_ref' not in payload['opinions'][0]
