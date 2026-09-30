"""Validate the handoff package; this does not accept product behavior."""
from pathlib import Path
import json, re, hashlib, subprocess
R=Path(__file__).resolve().parents[4];D=R/'docs/specs/deck-master-webui-v4-20260930';OD=R/'docs/design/webui-opendesign-20260930'
def read(p):return json.loads(p.read_text())
tasks=read(D/'tasks.json');ids={t['id'] for t in tasks};assert len(ids)==15
acs=[a['id'] for t in tasks for a in t['acceptance']];assert len(acs)==len(set(acs))==45
visited=set();active=set()
def visit(i):
 assert i not in active,('cycle',i)
 if i in visited:return
 active.add(i)
 t=next(t for t in tasks if t['id']==i)
 for d in t['dependencies']:assert d in ids;visit(d)
 active.remove(i);visited.add(i)
for t in tasks:
 visit(t['id']);s=(D/'task-cards'/f"{t['id']}.md").read_text()
 for ac in t['acceptance']:assert ac['id'] in s and ac['text'] in s,(t['id'],ac['id'])
 for dep in t['dependencies']:assert dep in s.split('##')[0],(t['id'],dep)
gaps=read(D/'gap-matrix.json');assert len(gaps)==len({r['id'] for r in gaps})==53
for r in gaps:
 assert r['final_owner'] in ids
 for f in r['code_source'].split('; '):assert (R/f).exists(),f
old=read(D/'acceptance-carryover.json');assert len(old)==len({a['id'] for a in old})==87
assert {a['id'] for a in old}==set(read(D/'evidence/inherited-execution-state.json')['acceptance'])
for a in old:assert a['carry_owner'] in ids and a['accepted'] is False
m=read(OD/'manifest.json');assert len(m['files'])==17
for f in m['files']:
 b=(OD/f['path']).read_bytes();assert len(b)==f['bytes'];assert hashlib.sha256(b).hexdigest()==f['sha256'],f['path']
actions=read(D/'design-actions.json');assert len(actions)==107
assert len({(a['file'],a['action_family']) for a in actions})==107
for a in actions:assert a['owner'] in ids
broken=[]
for p in list(D.rglob('*.md'))+[OD/'README.md',R/'DESIGN.md']:
 for raw in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',p.read_text()):
  target=raw.split('#')[0]
  if not target or re.match(r'^[a-z]+:',target):continue
  if not (p.parent/target).exists():broken.append((str(p.relative_to(R)),target))
assert not broken,broken
assert read(D/'evidence/pr66.json')['headRefOid']=='93c76a152394a50ad0bc226597992c5a4357b7a3'
result={'status':'passed','scope':'Spec integrity only; not production acceptance','tasks':15,'new_ac':45,'old_ac':87,'gaps':53,'design_action_families':107,'received_files':17,'received_bytes':sum(f['bytes'] for f in m['files']),'dag':'acyclic','local_markdown_links':'valid','raw_design_hashes':'all match','current_core_tests':148,'behavior_probes':len(read(D/'evidence/gap-probes.json')['observations'])}
(D/'evidence/spec-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
