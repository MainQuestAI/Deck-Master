import sys,json,os
from pathlib import Path
import deck_master,deck_master.web,pytest
package=Path(deck_master.__file__).resolve().parent;assert 'site-packages' in package.parts
source=Path('/workspace/work/rc3/reviews/rc3-02-code-snapshot-65d82')
sys.path.insert(0,str(source/'tests/rebuild')) # fixed test helpers only, runtime preloaded installed
from test_icon_quality import icon_store
from test_deep_quality_browser import workbench
from playwright.sync_api import expect
root=Path(sys.argv[1]);root.mkdir()
record={}
def geometry(page):
 return page.evaluate("""()=>{let v=document.querySelector('.page-image-viewport');return {box:v.getBoundingClientRect().toJSON(),fontsStatus:document.fonts.status,readingMode:v.dataset.readingMode??null,inlineHeight:v.style.height,imageState:v.querySelector('.pooled-image')?.dataset.imageState??null,canvasPresent:Boolean(v.querySelector('canvas.page-image')),viewport:{width:innerWidth,height:innerHeight},scrollY}}""")
def test_actual_loading_to_reading(workbench):
 page,_,store,_,goto,_=workbench
 page.set_viewport_size({'width':390,'height':844})
 held=[]
 page.route('**/api/file?*',lambda route:held.append(route))
 goto()
 viewport=page.locator('.page-image-viewport')
 expect(viewport).to_be_visible()
 record['loading']=geometry(page)
 record['held_requests']=[r.request.url for r in held]
 page.screenshot(path=str(root/'loading.png'),full_page=True)
 assert held,'actual image request must be held'
 for route in held:route.continue_()
 page.unroute('**/api/file?*')
 expect(viewport).to_have_attribute('data-reading-mode','fit')
 record['ready']=geometry(page)
 record['browser_version']=page.context.browser.version
 page.screenshot(path=str(root/'ready.png'),full_page=True)
 assert record['loading']['imageState']=='loading' and not record['loading']['canvasPresent']
 assert record['ready']['imageState']=='ready' and record['ready']['canvasPresent']
 assert record['ready']['box']['bottom']<844
status=pytest.main(['-q',__file__,'-p','no:cacheprovider','--basetemp',str(root/'pytest-tmp')])
modules={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=='deck_master' or n.startswith('deck_master.')) and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(package) for p in modules.values()),modules
record.update(status=int(status),python=sys.executable,module=str(package),tmpdir=os.environ.get('TMPDIR'),source=str(source),modules=modules,method='Actual image fetch held then continued unchanged; source/tests/runtime/viewport/threshold unchanged')
(root/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
sys.exit(status)
