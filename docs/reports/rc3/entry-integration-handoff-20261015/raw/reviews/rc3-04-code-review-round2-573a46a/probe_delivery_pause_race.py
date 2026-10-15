"""Deterministic lock-contention probe; no product monkeypatches.

The existing helper seeds explicitly synthetic L1 engineering facts. Only
public export and pause operations are under test; no human/desktop claim.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
from deck_master import collaboration, delivery_eligibility, exports
from deck_master.local_state import local_lock

OUT=Path(__file__).resolve().parent
SNAPSHOT=Path('/workspace/work/rc3/reviews/rc3-04-code-snapshot-573a46a')
HELPER=SNAPSHOT/'tests/rebuild/test_export.py'
# Explicit external test helper origin, not an installed-core import override.
sys.path.append(str(SNAPSHOT/'tests/rebuild'))
from test_export import _passing_deck

fixture=OUT/'probe-delivery-race-fixture'
fixture.mkdir()
project,store=_passing_deck(fixture)
before=store.load_document()
initial=delivery_eligibility.describe(project)
assert initial['status']=='ready',initial
lockpath=store.deck_root/'workbench/exports/exports.lock'
lockpath.parent.mkdir(parents=True,exist_ok=True)
outcome={}
def deliver():
 try:
  outcome['result']=exports.create(project,purpose='delivery',output_dir=OUT/'delivery-published-after-pause')
 except Exception as exc:
  outcome['error']={'type':type(exc).__name__,'message':str(exc)}
def open_lock_count():
 count=0
 for item in Path('/proc/self/fd').iterdir():
  try:
   if item.resolve()==lockpath: count+=1
  except OSError: pass
 return count
with local_lock(lockpath):
 worker=threading.Thread(target=deliver)
 worker.start()
 deadline=time.monotonic()+10
 while open_lock_count()<2 and worker.is_alive() and time.monotonic()<deadline:
  time.sleep(.01)
 assert open_lock_count()>=2,{'state':outcome,'message':'worker did not reach exports lock after its initial eligibility gate'}
 paused=collaboration.pause_request(project,reason='Stop delivery before publication.',
  base_revision=store.load_document()['revision_id'],operation_id=str(uuid.uuid4()),
  instruction_evidence={'kind':'host_attested_instruction','text':'Pause the current request now, including delivery.',
  'source_locator':'independent-review:L1-delivery-pause'})
 at_pause=store.load_document()
worker.join(10)
assert not worker.is_alive()
after=store.load_document()
post=delivery_eligibility.describe(project)
try:
 control=exports.create(project,purpose='delivery',output_dir=OUT/'delivery-after-pause-control')
except Exception as exc:
 control={'type':type(exc).__name__,'message':str(exc)}
result={'evidence_level':'L1_SYNTHETIC','fixture_limit':'synthetic engineering facts; no human, model, renderer or desktop execution',
 'helper':{'path':str(HELPER),'sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest()},
 'before':before,'initial_readiness':initial,'pause':paused,'at_pause':at_pause,'outcome':outcome,
 'after':after,'current_readiness':post,'fresh_after_pause_control':control,
 'delivery_published_after_pause':(OUT/'delivery-published-after-pause/deck.pptx').is_file()}
(OUT/'probe-delivery-pause-race-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'initial':initial['status'],'paused':at_pause['collaboration']['request']['paused'],
 'delivery_published_after_pause':result['delivery_published_after_pause'],'outcome_status':outcome.get('result',{}).get('status'),
 'fresh_after_pause_control':control.get('type'), 'current_readiness':post['status']},ensure_ascii=False))
