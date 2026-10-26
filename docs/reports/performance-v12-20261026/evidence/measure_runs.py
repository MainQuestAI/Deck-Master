"""Reuse w01 fixture at 24 pages with 80 background tasks (200 total), no new fixture model."""
import argparse,hashlib,importlib.util,json,time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from deck_master import run_desk,current_relationship,candidates,tasks,workbench,operation_coverage
from deck_master.store import Store
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--factory',type=Path,required=True);a=p.parse_args()
project=a.root/'project';a.root.mkdir(exist_ok=True,parents=True)
if not project.exists():
 spec=importlib.util.spec_from_file_location('pressure',a.factory);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 manifest=module.create_fixture(project,page_count=24,background_task_count=80);(a.root/'manifest.json').write_text(json.dumps(manifest))
store=Store(project);before=store.load_document();rows=[]
for attention in (False,True):
 for limit in (1,30,100):
  fn=lambda:run_desk.listing(project,limit=limit,attention=attention)
  fn()
  for i in range(3):
   cpu=time.process_time();wall=time.perf_counter();value=fn();wall=time.perf_counter()-wall;cpu=time.process_time()-cpu
   rows.append(dict(attention=attention,limit=limit,phase='uninstrumented',sample=i,cpu_seconds=cpu,wall_seconds=wall,total=value['pagination']['total'],response_sha256=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()))
  counts={};unique=set()
  def wrap(label,original):
   def call(*args,**kwargs):
    counts[label]=counts.get(label,0)+1
    if label=='relationship' and args[1]['task_id'] not in args[0].task_cache:counts['relationship_misses']=counts.get('relationship_misses',0)+1
    if label=='snapshot' and args[1] not in args[0].snapshots:counts['snapshot_misses']=counts.get('snapshot_misses',0)+1
    value=original(*args,**kwargs)
    if label=='object_bytes':
     counts['physical_bytes']=counts.get('physical_bytes',0)+len(value);unique.add((args[1]['path'],args[1]['sha256']))
    return value
   return call
  with ExitStack() as stack:
   for obj,attr,label in [(run_desk,'task_row','row'),(current_relationship.CurrentRelationships,'task','relationship'),(candidates,'basis_state','candidate_basis'),(candidates,'inputs_current','candidate_inputs'),(tasks,'task_inputs_current','task_inputs'),(workbench._ReadContext,'read_snapshot','snapshot'),(operation_coverage,'scan','history_scan'),(Store,'read_object_bytes','object_bytes')]:
    stack.enter_context(patch.object(obj,attr,wrap(label,getattr(obj,attr))))
   value=fn()
  rows.append(dict(attention=attention,limit=limit,phase='probe',**counts,unique_store_refs=len(unique),total=value['pagination']['total']))
assert store.load_document()==before
import deck_master
result={'module_origin':deck_master.__file__,'task_count':len(before['tasks']),'fixture_document_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'scope':'same 200-task w01 fixture; original copied-heavy scopes not conflated; 3 samples are not p95; Store bytes exclude direct context cache IO','rows':rows}
a.out.write_text(json.dumps(result,indent=2)+'\n');print(a.out)
