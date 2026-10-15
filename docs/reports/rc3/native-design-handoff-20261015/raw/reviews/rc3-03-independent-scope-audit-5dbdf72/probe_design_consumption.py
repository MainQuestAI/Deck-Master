"""Independent installed public-SDK probes; zero external calls, disposable projects."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess

from deck_master import service, tasks
from deck_master.store import Store

OUT = Path(__file__).resolve().parent
font_paths = {}
for family in ('DejaVu Sans','DejaVu Serif'):
 path = subprocess.run(['fc-match','-f','%{file}',family],check=True,capture_output=True,text=True).stdout
 font_paths[family] = Path(path)

def create(name):
 path = OUT/'isolated-probes'/name
 page = {'schema_version':'deck_page_package.v2','page_id':'p1',
  'customer_visible':{'title':'Fixed copy, actual design consumption','body_blocks':[
   {'id':'fixed','type':'paragraph','text':'Human confirmation precedes formal submission; 10 ms is only a test parameter.'}]},
  'visual_spec':{'intent':'responsibility and condition remain fixed','layout_hint':'one text block','reference_mode':'new_design'}}
 design = {
  'fonts':[
   {'font_id':'body','family':'DejaVu Sans','face':'Regular','weight':400,'asset_id':'font-body','fallback_font_ids':['fallback']},
   {'font_id':'heading','family':'DejaVu Sans','face':'Bold','weight':700,'asset_id':None,'fallback_font_ids':[]},
   {'font_id':'fallback','family':'DejaVu Serif','face':'Regular','weight':400,'asset_id':None,'fallback_font_ids':[]},
   {'font_id':'unused','family':'DejaVu Serif','face':'Regular','weight':400,'asset_id':None,'fallback_font_ids':[]}],
  'styles':[{'style_id':'default','colors':{'text':'#112233','background':'#FFFFFF'},
    'typography':{'body_font_id':'body','heading_font_id':'heading','body_size_pt':18,'heading_size_pt':30,'auxiliary_size_pt':12},
    'layout_notes':'Global layout rule: aligned baseline and generous outer margin.'}],
  'default_style_id':'default',
  'assets':[{'asset_id':'font-body','kind':'font','file':str(font_paths['DejaVu Sans']),'external_use':'allowed'}],
  'allowed_asset_ids':['font-body']}
 service.create(path,brief='Independent engineering audit only; no model call authorized',draft={'pages':[page]},design=design,project_format='workbench.v3')
 summary = service.continue_project(path)['pending_tasks'][0]
 store = Store(path)
 task = tasks._lookup_task(store.load_document(),summary['task_id'],store)
 return path,store,task,summary

results=[]
for mutation in ('unused_font','fallback_font','global_layout','font_asset_bytes'):
 path,store,task,summary = create(mutation)
 request=summary['production_request'];frozen=summary['generation_input']
 assert request['projection']['style']['layout_notes'] == 'Global layout rule: aligned baseline and generous outer margin.'
 assert {font['font_id'] for font in request['projection']['fonts']} == {'body','heading','fallback'}
 assert 'unused' not in {font['font_id'] for font in request['projection']['fonts']}
 permitted=request['permitted_asset_files']
 assert [asset['asset_id'] for asset in permitted] == ['font-body']
 assert store.read_object_bytes(permitted[0]['file']) == font_paths['DejaVu Sans'].read_bytes()
 assert 'content_basis' not in json.loads(frozen['prompt'].split('Structured input:\n',1)[1])
 old_page=copy.deepcopy(store.load_document()['pages'][0]['page'])
 if mutation == 'font_asset_bytes':
  service.import_asset(path,asset_id='font-body',kind='font',file_path=font_paths['DejaVu Serif'])
 else:
  design=copy.deepcopy(store.load_document()['design_context'])
  if mutation == 'global_layout':design['styles'][0]['layout_notes']='Changed global layout: two-column outer alignment.'
  else:next(font for font in design['fonts'] if font['font_id']==('unused' if mutation=='unused_font' else 'fallback'))['face']='Changed registered face'
  service.update_design(path,design_context=design,base_revision=store.current_revision_id())
 doc=store.load_document();current=tasks._lookup_task(doc,task['task_id'],store)
 is_current=tasks.task_inputs_current(store,doc,current)
 assert is_current is (mutation == 'unused_font'), mutation
 assert doc['pages'][0]['page']==old_page
 assert all(allowance['state']=='reserved' for ref in doc['tasks'] for allowance in store.read_object_json(ref).get('call_allowances',[]))
 results.append({'mutation':mutation,'task_still_current':is_current,'page_unchanged':True,'external_calls':0,
  'project':str(path),'dispatched_task_id':task['task_id'],'prompt_sha256':hashlib.sha256(frozen['prompt'].encode()).hexdigest(),
  'font_asset_sha256':permitted[0]['file']['sha256'],'used_fonts_and_fallback':['body','heading','fallback']})
(OUT/'independent-design-consumption.json').write_text(json.dumps({'status':'PASS','evidence_kind':'independent actual installed SDK, disposable fixed text, no model calls','results':results},indent=2)+'\n')
print(json.dumps(results,indent=2))
