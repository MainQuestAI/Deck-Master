"""Fixed synthetic workbench fixture; probes and timings run separately."""
import argparse, hashlib, json, time, urllib.request
from pathlib import Path
from unittest.mock import patch
from deck_master import editing, content_review, workbench
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_workbench_reads import make_project
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
project=a.root/'project'
if not project.exists(): make_project(a.root,count=300)
store=Store(project);before=store.load_document();identity=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()
server=WorkbenchServer(project);rows=[]
try:
 url=server.start().rstrip('/')
 for query in ('protocol=workbench_summary.v1','protocol=workbench_summary.v2','protocol=workbench_summary.v2&personal=1'):
  def request():
   with urllib.request.urlopen(url+'/api/view/summary?'+query) as r:return json.loads(r.read())
  workbench._summary_cache.clear();request()
  for i in range(3):
   cpu=time.process_time();wall=time.perf_counter();value=request();wall=time.perf_counter()-wall;cpu=time.process_time()-cpu
   rows.append({'query':query,'phase':'warm_uninstrumented','sample':i,'wall_seconds':wall,'driver_and_service_cpu_seconds':cpu,'response_sha256':hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()})
  for phase in ('cold_probe','warm_probe'):
   if phase=='cold_probe':workbench._summary_cache.clear()
   counts={'artifact_builds':0,'store_byte_reads':0,'store_bytes':0};graph=editing._current_artifact_digests;read=Store.read_object_bytes
   def g(*args,**kwargs):counts['artifact_builds']+=1;return graph(*args,**kwargs)
   def b(self,ref):
    value=read(self,ref);counts['store_byte_reads']+=1;counts['store_bytes']+=len(value);return value
   with patch.object(editing,'_current_artifact_digests',g),patch.object(content_review,'_current_artifact_digests',g),patch.object(Store,'read_object_bytes',b):value=request()
   rows.append({'query':query,'phase':phase,**counts})
finally:server.stop()
assert store.load_document()==before
import deck_master,platform
result={'fixture':'existing make_project, 300 pages; no PPTX; framing task retained by factory','fixture_document_sha256':identity,'page_count':len(before['pages']),'task_count':len(before['tasks']),'module_origin':deck_master.__file__,'python':platform.python_version(),'scope':'same process HTTP client+service; 3 warm samples are not p95; Store bytes count excludes direct read-context cache IO; probes separate from timing','rows':rows}
a.out.write_text(json.dumps(result,indent=2)+'\n');print(a.out)
