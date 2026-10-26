"""RP-28 synthetic cache-only benchmark; never a renderer acceptance test."""
import argparse
import hashlib, importlib.util, json, tempfile, time
from pathlib import Path
from unittest.mock import patch
from deck_master import candidate_preview
from deck_master.local_state import write_json
from deck_master.samples import create_sample
from deck_master.store import Store
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-source', type=Path, required=True)
args = parser.parse_args()
spec=importlib.util.spec_from_file_location('deck_master._rp28_baseline', args.baseline_source/'src/deck_master/candidate_preview.py')
baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
rows=[]
for label,module in [('before',baseline),('after',candidate_preview)]:
 for sample in range(3):
  with tempfile.TemporaryDirectory(prefix='rp28-count-') as temp:
   project=Path(temp)/'project';create_sample(project,page_count=1,readonly=False);store=Store(project)
   identity={'candidate_ref':{'sha256':'candidate'}};key='a'*64
   context=(store,{}, {}, {}, {}, {}, b'', {}, {}, identity,key)
   folder=module._state_path(store,key).parent
   report={'identity':identity,'cache_key':key,'candidate_ref':identity['candidate_ref'],'candidate_id':'candidate','check_id':'fixed','status':'ready','native_check':'pass','readback':{'status':'pass'},'scope_check':{'status':'pass'},'files':{}}
   for name in module._FILES:
    raw=(name.encode()*100000)[:1048576];(folder/name).write_bytes(raw)
    report['files'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
   write_json(folder/'report.json',report);write_json(folder/'state.json',{'status':'ready','cache_key':key,'check_id':'fixed'})
   counts={'contexts':0,'file_reads':0,'hashes':0}
   original_read=Path.read_bytes;original_sha=hashlib.sha256
   def read(p):
    if p.parent==folder and p.name in module._FILES:counts['file_reads']+=1
    return original_read(p)
   def get_context(*args):counts['contexts']+=1;return context
   def sha(raw=b''):
    if len(raw)>=1000000:counts['hashes']+=1
    return original_sha(raw)
   with patch.object(module,'_context',get_context),patch.object(Path,'read_bytes',read),patch.object(hashlib,'sha256',sha):
    cpu=time.process_time();wall=time.perf_counter();ref=module.freeze_check(store,'candidate');cpu=time.process_time()-cpu;wall=time.perf_counter()-wall
   frozen=store.read_object_json(ref)
   rows.append({'variant':label,'sample':sample+1,**counts,'cpu_s':cpu,'wall_s':wall,'check_id':frozen['check_id'],'file_hashes':{n:r['file']['sha256'] for n,r in frozen['files'].items()}})
print(json.dumps({'fixture':'synthetic 4 x 1MiB cache; context stubbed, no actual renderer or toolchain benchmark','samples':rows},indent=2))
