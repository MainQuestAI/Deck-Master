"""W04 warm first window on the W01 300x5x3 fixture; no model calls.

Run with --fixture <w01-output-directory> --out <new-evidence-directory>.
Personal gallery selection changes; business facts remain untouched.
"""
import argparse
import platform
import subprocess
import json,time
from pathlib import Path
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright,expect
from deck_master import thumbnails,ui_journal,workbench,gallery_state
from deck_master.store import Store
from deck_master.web import WorkbenchServer
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--chromium-executable',type=Path);parser.add_argument('--source-commit');args=parser.parse_args()
manifest=json.loads((args.fixture/'manifest.json').read_text());assert manifest['factory']=='w01-pressure.v1' and manifest['candidate_count']==1500 and manifest['attempt_count']==4500
project=args.fixture/'project';out=args.out;out.mkdir(parents=True,exist_ok=False)
store=Store(project);doc=store.load_document();info=ui_journal.project_info(project)
for entry in doc['pages'][:30]:
 if entry.get('blueprint'):thumbnails.request(project,ref=store.read_object_json(entry['blueprint'])['file'])
thumbnails.QUEUE.drain();workbench.workbench_summary(project)
server=WorkbenchServer(project);rows=[];errors=[]
def ready(page):
 page.wait_for_function('''() => {
 const port=document.querySelector('.gallery-viewport');if(!port)return false;
 const rect=port.getBoundingClientRect();const inside=node=>{const r=node.getBoundingClientRect();return r.bottom>rect.top&&r.top<Math.min(innerHeight,rect.bottom);};
 return [...port.querySelectorAll('.gallery-card')].some(inside)&&[...port.querySelectorAll('.pooled-image')].filter(inside).every(n=>n.dataset.imageState==='ready');
 }''')
try:
 url=server.start()+'v2/#'+urlencode({'project':info['project_identity'],'surface':'gallery','layer':'original_image','revision':doc['revision_id'],'zoom':1})
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path=str(args.chromium_executable) if args.chromium_executable else None)
  for width,height in [(1280,800),(1440,900)]:
   for sample in range(3):
    saved=gallery_state.get(project)['record']
    if saved:
     state=saved['state'];state['selected_page_ids']=[];state['anchor']={'page_id':None,'offset':0};gallery_state.save(project,state=state,expected_etag=saved['etag'])
    ctx=browser.new_context(viewport={'width':width,'height':height});page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    t=time.perf_counter();page.goto(url);ready(page)
    page.locator('.gallery-card[data-page-id="p01"]').get_by_role('checkbox').check()
    expect(page.locator('.gallery-selection')).to_contain_text('已选 1 页')
    seconds=time.perf_counter()-t
    row={'viewport':[width,height],'sample':sample,'seconds':seconds,'pass':seconds<=2,'cards':page.locator('.gallery-card').count(),'pool':page.evaluate('async()=>(await import("/v2/images.js")).imagePool.snapshot()')};rows.append(row);print(json.dumps(row),flush=True)
    if sample==0:page.screenshot(path=str(out/f'gallery-{width}.png'),full_page=True)
    expect(page.get_by_text('画廊选择已保存',exact=True)).to_be_visible();ctx.close()
  (out/'checks.json').write_text(json.dumps({'browser':browser.version,'project_id':doc['project_id'],'revision_id':doc['revision_id'],'synthetic':True,'timings':rows,'errors':errors,'fixture_manifest':manifest['factory'],'environment':{'os':platform.platform(),'python':platform.python_version(),'source_commit':args.source_commit or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}},indent=2)+'\n')
  browser.close()
finally:server.stop()
assert all(r['pass'] for r in rows) and not errors
