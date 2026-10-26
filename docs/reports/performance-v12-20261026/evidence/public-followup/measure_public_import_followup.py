import json, subprocess, tempfile, types
from pathlib import Path
from unittest.mock import patch
from collections import Counter
from deck_master import review_import, editing, content_review, tasks
from deck_master.store import Store
from test_perf_review_import_public import _packet, instruction
base=types.ModuleType('deck_master.review_import_724')
base.__package__='deck_master'
exec(compile(subprocess.check_output(['git','show','7244477a:src/deck_master/review_import.py'],text=True),'724:review_import.py','exec'),base.__dict__)
results=[]
for label,module in [('724',base),('candidate',review_import)]:
  for n in (2,4,8):
    with tempfile.TemporaryDirectory(prefix='review-public-') as temp:
      project,external,bindings=_packet(Path(temp),n,large_deck=True)
      store=Store(project)
      paths={store._resolve_object_path(p['page']['path']) for p in store.load_document()['pages']}
      reads=Counter(); phase=['other']; original=Path.read_bytes
      build=editing._current_artifact_digests; adopt=tasks._adopt_review
      def read(path):
        data=original(path)
        if path in paths:
          reads['total']+=1;reads[phase[0]]+=1;reads['bytes']+=len(data)
        return data
      def wrap(fn,name):
        def call(*args,**kw):
          old=phase[0];phase[0]=name
          try:return fn(*args,**kw)
          finally:phase[0]=old
        return call
      with patch.object(Path,'read_bytes',read),patch.object(editing,'_current_artifact_digests',wrap(build,'builder')),patch.object(content_review,'_current_artifact_digests',wrap(build,'builder')),patch.object(tasks,'_adopt_review',wrap(adopt,'adoption')):
        result=module.import_report(project,external_report=external,source_bindings=bindings,base_revision=store.current_revision_id(),operation_id='synthetic-batch-import',evidence=instruction('Explicitly import these synthetic source-bound reviews'))
      assert len(result['review_refs'])==n
      results.append({'implementation':label,'pages':16,'reviews':n,**reads})
print(json.dumps(results,indent=2))
