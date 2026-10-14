import os, sys, json, tempfile, subprocess, hashlib
from pathlib import Path
source=Path('/workspace/work/rc3/cards/rc3-02')
fixed=Path('/workspace/work/rc3/reviews/rc3-02-docs-snapshot-0d12')
sys.path.insert(0,str(fixed/'tests/rebuild'))
from deck_master import service
import deck_master
from deck_master.store import Store
from test_service_flow import _draft_page
from test_page_visual_gate import _start,_accept,_svg_envelope
out=Path(__file__).parent
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
assert head=='0d12a9d78ed0526f0fb74d1b8abed0a2ec154b4e'
assert subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True)==''
assert Path(deck_master.__file__).resolve().is_relative_to(source/'src')
original_config=os.environ.get('DECK_MASTER_RSVG_CONVERT')
records=[]
for case in ['unavailable_configured_renderer','actual_available_renderer']:
 if case.startswith('unavailable'):os.environ['DECK_MASTER_RSVG_CONVERT']=str(out/'genuinely-absent-rsvg-convert')
 elif original_config is None:os.environ.pop('DECK_MASTER_RSVG_CONVERT',None)
 else:os.environ['DECK_MASTER_RSVG_CONVERT']=original_config
 project=out/case
 page=_draft_page('p-a','记录未知','54/120＝45%，不是节约率。');page['speaker_notes']='原有讲者备注。\n末段。\n'
 service.create(project,brief='Synthetic exact CI renderer dependency contrast',draft={'pages':[page]})
 task,svg=_start(project,'p-a');ref=Store(project).load_document()['pages'][0]['page']
 envelope=_svg_envelope('p-a');envelope['artifact_specs'][0]['provenance']['generated_from_page']=ref
 envelope['artifact_specs'][0]['dependencies']=[{'kind':'content','identity':'page:p-a','sha256':ref['sha256']}]
 _accept(project,task,envelope,file_name='page.svg',data=svg)
 response=service.continue_project(project);store=Store(project);doc=store.load_document();preview=doc['pages'][0]['svg_preview']
 (out/(case+'-continue.json')).write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n')
 (out/(case+'-document.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
 if case.startswith('unavailable'):
  assert response['status']=='needs_tool' and response['pending_tasks']==[] and preview is None
  assert any('rsvg-convert unavailable' in str(f) for f in response['findings'])
 else:
  assert response['status']=='awaiting_host' and preview is not None
  assert response['pending_tasks'][0]['review_stage']=='page_visual'
  assert store.read_object_bytes(store.read_object_json(preview)['file']).startswith(b'\x89PNG')
 records.append({'case':case,'actual_continue_status':response['status'],'pending_tasks':len(response['pending_tasks']),
                 'findings':response.get('findings'),'svg_preview_ref':preview,'configured_renderer':os.environ.get('DECK_MASTER_RSVG_CONVERT')})
record={'head':head,'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip(),
        'python':sys.executable,'module':str(Path(deck_master.__file__).resolve()),'fixed_fixture_source':str(fixed/'tests/rebuild'),
        'scope':'Actual configured missing/available renderer contrast; formal fixture Page/Task/SVG acceptance and normal continue, no mocked pending or renderer.',
        'status':'ROOT_CAUSE_CONFIRMED','records':records}
(out/'reproduction.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
