"""Read-only planning and isolated documentation migration for main@62dfcfc.

Writes only the iteration output directory and its dedicated candidate copy.
This is an audit implementation sample; production application needs Codex verification.
"""
import argparse, ast, collections, csv, difflib, hashlib, io, json, os, posixpath, re, shutil, subprocess, zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit, quote

BASELINE='62dfcfc5637f0bee2358074c4458047689dd5299'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=Path.cwd(),help='Read-only fixed-baseline source checkout; defaults to the current directory.')
parser.add_argument('--output',type=Path,required=True,help='Dedicated output directory outside the source checkout.')
parser.add_argument('--tree',type=Path,help='Optional official Git tree JSON; omitted means read the fixed commit via git ls-tree.')
args=parser.parse_args()
# Validate every relationship before mkdir, report writes or candidate mutation.
source_arg=args.source.expanduser(); output_arg=args.output.expanduser()
ROOT=source_arg.resolve(strict=True); OUT=output_arg.resolve()
CANDIDATE=OUT/'candidate'
if ROOT==OUT or ROOT.is_relative_to(OUT) or OUT.is_relative_to(ROOT):
 raise SystemExit('Source and output must be disjoint dedicated trees.')
if any(p.is_symlink() for p in (output_arg,*output_arg.parents)):
 raise SystemExit('Output must not be a symbolic link or pass through one.')
if CANDIDATE.exists() or CANDIDATE.is_symlink():
 raise SystemExit('Candidate must not already exist, including symbolic links.')
if OUT.exists() and any(OUT.iterdir()):
 raise SystemExit('Output root must be empty before generating a candidate.')
OUT.mkdir(parents=True,exist_ok=True)
if args.tree:
 TREE=json.loads(args.tree.read_text())
else:
 raw=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','-z','--full-tree',BASELINE])
 entries=[]
 for entry in raw.split(b'\0'):
  if not entry:continue
  meta,path=entry.split(b'\t',1);mode,kind,digest=meta.decode().split()
  entries.append({'path':path.decode(),'mode':mode,'type':kind,'sha':digest})
 TREE={'sha':BASELINE,'tree':entries,'truncated':False}
BASE=TREE['sha']
assert BASE==BASELINE and TREE.get('truncated') is not True
TRACKED={x['path']:x for x in TREE['tree'] if x['type']=='blob'}
(OUT/'source-tree.json').write_text(json.dumps({'sha':BASE,'tree':[TRACKED[p] for p in TRACKED],'truncated':False},ensure_ascii=False,indent=2))
DIRS={str(Path(p).parent) for p in TRACKED}
for p in list(DIRS):
 DIRS.update(str(x) for x in Path(p).parents)
BINARY={'.png','.jpg','.jpeg','.gif','.webp','.pdf','.pptx','.docx','.xlsx','.zip','.gz','.woff','.woff2','.ttf','.otf','.ico'}
MDLINK=re.compile(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)')
IMAGELINK=re.compile(r'!\[[^\]\n]*\]\(([^)\n]+)\)')
HTMLLINK=re.compile(r'(?:href|src)\s*=\s*[\"\x27]([^\"\x27]+)[\"\x27]')
INLINE=re.compile(r'(?<!`)`([^`\n]+)`(?!`)')
RAW_DOC=re.compile(r'(?<![\w/])docs/[^\s`\"\x27<>\[\]{}(),;，。；]+')
LITERAL=re.compile(r'[\"\x27]([^\"\x27\n]*[/.][^\"\x27\n]*)[\"\x27]')
ARCHIVE_PREFIXES=('docs/reports/','docs/archive/','docs/qa/','docs/reviews/','docs/governance/','docs/design/archive/','docs/specs/deck-master-webui-post127-review-20261020/')
REPLACED_NAV={'docs/archive/README.md','docs/reports/README.md'}
LEGACY_KEEP='docs/archive/pre-rebuild/product-capability-manifest.v09.json'
FIXTURE_ROOT='tests/rebuild/fixtures/history'
FIXTURE_MAP={
 'docs/reports/rc4/iteration-20261019/execution-ledger.json':FIXTURE_ROOT+'/rc4/iteration-20261019/execution-ledger.json',
 'docs/reports/workbench-v3-execution-20260926/w02/real-host-literal/freeze.json':FIXTURE_ROOT+'/generation/real-host-literal/freeze.json',
}
REPORT_BASE='docs/reports/content-collaboration-v1.2'
manifest=json.loads((ROOT/REPORT_BASE/'fixtures/manifest.json').read_text())
relative={'fixtures/manifest.json','anchors/content-anchors.md',manifest['historical_reviewed_inputs']['anchors/content-anchors.md']['archived_path']}
relative.update('evaluation/'+x for x in ('evaluator-a.md','evaluator-b.md','evaluator-c.md','evaluator-d.md','adjudication.md'))
relative.update(manifest['historical_artifacts'])
for name in sorted(relative):FIXTURE_MAP[REPORT_BASE+'/'+name]=FIXTURE_ROOT+'/content-collaboration-v1.2/'+name

def decode(path):
 data=(ROOT/path).read_bytes()
 if Path(path).suffix.lower() in BINARY or b'\0' in data:return data,None
 try:return data,data.decode('utf-8-sig')
 except UnicodeDecodeError:return data,None
CONTENTS={p:decode(p) for p in TRACKED}
for p,(data,_) in CONTENTS.items():
 assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==TRACKED[p]['sha'],f'Baseline byte mismatch: {p}'
LINES={p:text.splitlines() for p,(_,text) in CONTENTS.items() if text is not None}
def sha(data):return hashlib.sha256(data).hexdigest()
def scope_kind(p):
 if p.startswith('docs/specs/'):
  if '/contracts/' in p:return 'spec_schema_mirror'
  if '/prototype/' in p or '/validation/' in p:return 'prototype_or_visual_validation_asset'
  if '/evidence/' in p or '/inputs/' in p or 'ledger' in p or 'validation' in Path(p).name:return 'spec_attached_dated_evidence'
  if '/examples/' in p:return 'inherited_example_or_fixture'
  if p.startswith('docs/specs/deck-master-webui-post127-review-20261020/'):return 'explicitly_superseded_spec_review'
  return 'inherited_or_current_spec_keep'
 if p.startswith('docs/design/webui-opendesign-20261001/'):return 'active_design_received_source'
 if p.startswith('docs/design/webui-opendesign-20260930/'):return 'received_design_history_keep_original'
 if p.startswith(('docs/archive/','docs/design/archive/')):return 'retired_architecture_or_design_history'
 if p.startswith(('docs/reports/','docs/qa/','docs/reviews/')):return 'dated_report_or_raw_evidence'
 if p.startswith('docs/governance/'):return 'dated_governance_record'
 if p.startswith('docs/work-items/'):return 'work_item_contract_or_evidence_keep'
 if p.startswith('skills/'):return 'canonical_skill_or_method_keep'
 if p in ('README.md','AGENTS.md','CLAUDE.md','DESIGN.md','CONTRIBUTING.md','SUPPORT.md','SECURITY.md','ROADMAP.md','CHANGELOG.md') or p.startswith('docs/'):
  return 'active_navigation_or_guidance_keep'
 if p.startswith('tests/'):return 'test_reference_consumer'
 if p.startswith('src/'):return 'runtime_reference_consumer'
 return 'packaging_or_tooling_consumer'

def resolve(raw,source):
 value=raw.strip().strip('<>')
 if ' "' in value:value=value.split(' "',1)[0]
 if not value or value.startswith(('#','mailto:','data:','javascript:')):return None
 if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',value) or value.startswith('//'):return None
 path=unquote(value.split('#',1)[0].split('?',1)[0]).rstrip('/')
 if not path:return None
 candidates=[]
 if path.startswith('docs/') or path.startswith(('src/','tests/','skills/','tools/','.github/')):candidates.append(posixpath.normpath(path))
 candidates.append(posixpath.normpath(posixpath.join(posixpath.dirname(source),path)))
 candidates.append(posixpath.normpath(path))
 return next((p for p in candidates if p in TRACKED or p in DIRS),None)

refs=[];seen=set();unresolved_links=[]
def addref(source,line,raw,kind,target=None):
 target=target or resolve(raw,source)
 if not target:return
 k=(source,line,raw,kind,target)
 if k in seen:return
 seen.add(k);refs.append({'id':len(refs),'source':source,'line':line,'kind':kind,'raw':raw,'target':target,'directory_target':target in DIRS,'excerpt':LINES[source][line-1].strip()[:500]})
for p,(_,text) in CONTENTS.items():
 if text is None:continue
 lines=LINES[p]
 for number,line in enumerate(lines,1):
  for kind,pattern in [('markdown_link',MDLINK),('markdown_image',IMAGELINK),('html_attribute',HTMLLINK),('inline_code_path',INLINE),('literal_path',LITERAL)]:
   for m in pattern.finditer(line):addref(p,number,m.group(1),kind)
  for m in RAW_DOC.finditer(line):addref(p,number,m.group(0),'root_path_mention')
 if p.endswith('.py'):
  try:tree=ast.parse(text)
  except SyntaxError:continue
  def flatten(n):
   if isinstance(n,ast.Constant) and isinstance(n.value,str):return [n.value]
   if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):return flatten(n.left)+flatten(n.right)
   return []
  for node in ast.walk(tree):
   if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
    parts=flatten(node)
    if 'docs' in parts:
     raw='/'.join(parts[parts.index('docs'):]);addref(p,node.lineno,raw,'python_path_expression')
# Resolve the report-local manifest/test reads explicitly after line-by-line inspection.
for old,new in FIXTURE_MAP.items():
 if old.startswith(REPORT_BASE):addref('tests/rebuild/test_rc3_content_methods.py',98,old,'manifest_derived_test_read',old)
addref('src/deck_master/cli.py',1180,LEGACY_KEEP,'runtime_file_read',LEGACY_KEEP)

inbound=collections.defaultdict(list)
for r in refs:
 if r['target'].startswith('docs/'):
  if r['directory_target']:
   for p in TRACKED:
    if p.startswith(r['target'].rstrip('/')+'/'):inbound[p].append(r['id'])
  else:inbound[r['target']].append(r['id'])

ARCHIVE={p for p in TRACKED if p.startswith(ARCHIVE_PREFIXES) and p not in REPLACED_NAV and p!=LEGACY_KEEP}
# A still-current document must not acquire an online-only embedded asset.
# Preserve the transitive dependency of retained image/HTML asset consumers.
EMBEDDED_KEEP=set()
while True:
 required={r['target'] for r in refs if r['source'] not in ARCHIVE and r['kind'] in ('markdown_image','html_attribute') and r['target'] in ARCHIVE}
 if not required:break
 ARCHIVE-=required;EMBEDDED_KEEP|=required
def historical_url(target,raw=None):
 typ='tree' if target in DIRS else 'blob'
 fragment=('#'+raw.split('#',1)[1]) if raw and '#' in raw else ''
 return f'https://github.com/MainQuestAI/Deck-Master/{typ}/{BASE}/{quote(target,safe="/")}{fragment}'

def link_destination(target,source,raw):
 fragment=('#'+raw.split('#',1)[1]) if '#' in raw else ''
 if target in FIXTURE_MAP:
  return posixpath.relpath(FIXTURE_MAP[target],posixpath.dirname(source) or '.')+fragment
 return historical_url(target,raw)

updates={};edits=[]
for p,(data,text) in CONTENTS.items():
 if text is None or p in ARCHIVE or not p.endswith('.md'):continue
 def link_replace(m):
  raw=m.group(1);target=resolve(raw,p)
  if target not in ARCHIVE and not (target in DIRS and any(x.startswith(target.rstrip('/')+'/') for x in ARCHIVE) and not any(x.startswith(target.rstrip('/')+'/') and x not in ARCHIVE for x in TRACKED)):
   return m.group(0)
  new=link_destination(target,p,raw)
  return m.group(0).replace(raw,new,1)
 new=MDLINK.sub(link_replace,text)
 # Exact inline historical paths become clickable references, not dead local instructions.
 def inline_replace(m):
  raw=m.group(1);target=resolve(raw,p)
  if target not in ARCHIVE:return m.group(0)
  if target in FIXTURE_MAP:
   return '`'+FIXTURE_MAP[target]+'`'
  return '['+raw+']('+historical_url(target,raw)+')'
 new=INLINE.sub(inline_replace,new)
 if new!=text:updates[p]=new.encode('utf-8')

# Three source readers are relocated, with all assertions and fixture bytes unchanged.
test_updates={
 'tests/rebuild/test_iteration_ledger.py':[("docs/reports/rc4/iteration-20261019/execution-ledger.json",FIXTURE_MAP['docs/reports/rc4/iteration-20261019/execution-ledger.json'])],
 'tests/rebuild/test_generation_protocol.py':[("docs/reports/workbench-v3-execution-20260926/w02/real-host-literal/freeze.json",FIXTURE_MAP['docs/reports/workbench-v3-execution-20260926/w02/real-host-literal/freeze.json'])],
 'tests/rebuild/test_rc3_content_methods.py':[(REPORT_BASE,FIXTURE_ROOT+'/content-collaboration-v1.2')],
}
for p,replacements in test_updates.items():
 text=CONTENTS[p][1]
 for old,new in replacements:
  assert text.count(old)==1,(p,old,text.count(old));text=text.replace(old,new)
 updates[p]=text.encode()

updates['docs/reports/README.md']=f'''# 历史验证与审查证据

本目录的时点报告、原始日志与截图已按固定基线 `{BASE}` 收入[单一离线历史归档](../history/README.md)。
原始内容逐文件保留，SHA256和原路径见归档索引；不将历史PASS标为当前候选验收。

当前使用见[文档导航](../README.md)，当前行为以源码、实际检查和[运行合同](../../src/deck_master/resources/contracts/)为准。
测试直接读取的十份证据已按原字节迁入[稳定测试夹具](../../tests/rebuild/fixtures/history/)，历史评价和真实freeze的断言没有删除。

新增故障证据只保留必要摘要和可复现输入；大体积原始记录在下一次明确归档时收拢，不新增常驻归档服务。
归档不代表关闭Issue、通过专业审阅或发布版本。
'''.encode()
updates['docs/archive/README.md']=f'''# 历史归档入口

退役架构、旧设计和历史记录已按 `{BASE}` 的原字节收入[单一离线历史归档](../history/README.md)。
使用归档索引按原路径查找；可以解压到独立目录离线阅读，也可打开固定提交永久链接。

当前使用从[文档导航](../README.md)和[首次运行](../getting-started.md)开始；继承合同仍由[Spec索引](../specs/README.md)选择。
唯一原位保留的旧运行查询数据是[历史能力manifest](pre-rebuild/product-capability-manifest.v09.json)，供已有CLI别名按原路径读取。
归档保留全部信息，只减少当前工作树中展开的历史文本，不改写Git历史。
'''.encode()
text=updates.get('docs/README.md',CONTENTS['docs/README.md'][0]).decode()
marker='## 本轮文档整理的边界'
assert marker in text
text=text[:text.index(marker)]+'''## 文档身份与历史保全

当前用户与Agent入口、继承规范、测试所需schema镜像以及现行DESIGN引用的原型保留在工作树。
时点报告、旧架构和明确被接替的评审记录收于[单一离线历史归档](history/README.md)，原路径、字节和SHA均可追溯。
测试向量与历史评价原字节迁入稳定fixtures；当前运行别名仍读取的manifest原位保留。
归档内容不是信息删除，也不证明当前实现通过。此治理方案正式应用与最终CI需要 Codex 核验。
'''
updates['docs/README.md']=text.encode()
if 'AGENTS.md' in updates:
 t=updates['AGENTS.md'].decode().replace('The unique candidate ledger is','The historical RC4 candidate ledger is')
 t=t.replace('旧合同见 docs/archive/pre-rebuild/contracts/', '旧合同见 [固定基线归档合同]('+historical_url('docs/archive/pre-rebuild/contracts')+')')
 updates['AGENTS.md']=t.encode()
if 'docs/agent-task-index.md' in updates:
 t=updates['docs/agent-task-index.md'].decode().replace('records current verification.', 'records that RC4 candidate\'s dated verification.')
 updates['docs/agent-task-index.md']=t.encode()

# The frozen anchor is hash-checked: changing its embedded relative link would
# destroy the historical test vector. A seven-line local target preserves it.
anchor_compat='tests/rebuild/fixtures/specs/deck-master-content-collaboration-v1.2/ACCEPTANCE.md'
anchor_target='docs/specs/deck-master-content-collaboration-v1.2/ACCEPTANCE.md'
ADDITIONS={
 FIXTURE_ROOT+'/README.md':'''# 历史回归夹具

此目录的十份文件是原始报告的逐字节副本；SHA、原路径与归档位置见[历史清单](../../../../docs/history/manifest.csv)。
文件中的日期、PASS、NOT_RUN和相对路径属于原始时点，不是当前候选状态。
不编辑冻结文本来修链接；原内容锚点的相对规范链接由相邻specs目录的短入口接续。
当前规范见[Spec索引](../../../../docs/specs/README.md)，需要新样例时另建文件并明确来源。
正式迁移与候选测试需要 Codex 核验。
'''.encode(),
 anchor_compat:('''# 冻结夹具的规范链接兼容入口

## 1.2 统一失败分级

原始内容锚点的字节和SHA保持不变；此入口只接续它的相对链接。
完整继承判据见[ACCEPTANCE §1.2]('''+posixpath.relpath(anchor_target,posixpath.dirname(anchor_compat))+'''#12-统一失败分级)。
此处不复制判据，也不登记验收结论；正式应用需要 Codex 核验。
''').encode(),
}

# Archive original versions of changed documentation as well; code test readers stay in Git history.
ORIGINALS_IN_ARCHIVE=ARCHIVE|{p for p in updates if p.endswith('.md')}
for p in sorted(updates):
 old=CONTENTS[p][1];new=updates[p].decode()
 chunks=[]
 for op,a,b,c,d in difflib.SequenceMatcher(a=old.splitlines(),b=new.splitlines()).get_opcodes():
  if op!='equal':chunks.append({'operation':op,'old_start':a+1,'old_end':b,'new_start':c+1,'new_end':d,'old_text':'\n'.join(old.splitlines()[a:b]),'new_text':'\n'.join(new.splitlines()[c:d])})
 edits.append({'path':p,'old_sha256':sha(CONTENTS[p][0]),'new_sha256':sha(updates[p]),'old_lines':len(old.splitlines()),'new_lines':len(new.splitlines()),'hunks':chunks})

# Copy only Git-tracked files; no caches or untracked audit material enter the candidate.
CANDIDATE.mkdir(parents=True,exist_ok=True)
for p,(data,_) in CONTENTS.items():
 dest=CANDIDATE/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);dest.chmod(int(TRACKED[p]['mode'],8)&0o777)
for p in ARCHIVE:(CANDIDATE/p).unlink()
for old,new in FIXTURE_MAP.items():
 dest=CANDIDATE/new;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(CONTENTS[old][0])
for p,data in updates.items():(CANDIDATE/p).write_bytes(data)
for p,data in ADDITIONS.items():
 dest=CANDIDATE/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)

HISTORY=CANDIDATE/'docs/history';HISTORY.mkdir(exist_ok=True)
archive_rows=[]
for p in sorted(ORIGINALS_IN_ARCHIVE):
 data,text=CONTENTS[p]
 archive_rows.append({'original_path':p,'git_blob_sha':TRACKED[p]['sha'],'git_mode':TRACKED[p]['mode'],'sha256':sha(data),'bytes':len(data),'text_lines':len(text.splitlines()) if text is not None else 0,'role':'fixture_original' if p in FIXTURE_MAP else 'before_navigation_update' if p in updates else 'historical_record','permalink':historical_url(p)})
buffer=io.StringIO();w=csv.DictWriter(buffer,fieldnames=list(archive_rows[0]));w.writeheader();w.writerows(archive_rows);manifest_bytes=buffer.getvalue().encode()
(HISTORY/'manifest.csv').write_bytes(manifest_bytes)
zip_path=HISTORY/f'main-{BASE[:12]}-documents.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for row in archive_rows:
  info=zipfile.ZipInfo(row['original_path'],date_time=(2026,10,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(int(row['git_mode'],8)<<16)
  z.writestr(info,CONTENTS[row['original_path']][0],compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 info=zipfile.ZipInfo('ARCHIVE-MANIFEST.csv',date_time=(2026,10,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(0o100644<<16)
 z.writestr(info,manifest_bytes,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
zip_sha=sha(zip_path.read_bytes())
readme=f'''# Deck Master 历史文档保全

固定源码基线：`{BASE}`。这是历史材料索引，不代表当前测试、安装或发布状态。

- [离线归档]({zip_path.name})：包含{len(archive_rows)}份原始文件及一份内嵌清单。
- [逐文件清单](manifest.csv)：原路径、Git blob SHA、SHA256、原始字节数、文本行数与固定提交永久链接。
- ZIP SHA256：`{zip_sha}`。
- 当前使用见[文档导航](../README.md)；继承合同见[Spec索引](../specs/README.md)。

## 离线查阅

先在manifest.csv中按原路径查找，再把ZIP解压到一个独立目录；不要覆盖当前工作树或用户项目。
ZIP条目沿用原仓库路径，原始JSON、日志、图片、旧方案及其失败/未执行状态均逐字节保留。
ZIP内部的ARCHIVE-MANIFEST.csv与外部清单相同，可用标准解压工具读取，不需要运行归档脚本或联网服务。
永久链接方便在线阅读；离线阅读不依赖GitHub或额外上传。

测试直接读取的原始向量现位于[fixtures/history](../../tests/rebuild/fixtures/history/)，其原SHA与断言保持不变。
旧CLI仍直接读取的[历史manifest](../archive/pre-rebuild/product-capability-manifest.v09.json)继续原位保留。
活跃文本减少不等于信息删除，压缩归档仍计入仓库字节和文件统计。
正式应用、开发环境及最终CI需要 Codex 核验。
'''
(HISTORY/'README.md').write_text(readme)

inventory=[]
review_scope=[p for p in TRACKED if p.startswith(('docs/','skills/','tests/','tools/','.github/')) or p in ('README.md','AGENTS.md','CLAUDE.md','DESIGN.md','CONTRIBUTING.md','SUPPORT.md','SECURITY.md','ROADMAP.md','CHANGELOG.md','MANIFEST.in','pyproject.toml','setup.py','Makefile') or p== 'src/deck_master/cli.py' or p in updates]
for p in review_scope:
 data,text=CONTENTS[p];kind=scope_kind(p)
 if p in FIXTURE_MAP:action='migrate_fixture';reason='Direct test byte-read; migrate unchanged bytes and change only consumer base path; original also archived.';target=FIXTURE_MAP[p]
 elif p in updates:action='replace';reason='Replace current navigation or historical link; preserve original documentation bytes in single archive; test edits only path relocation.';target=p
 elif p==LEGACY_KEEP:action='keep';reason='Runtime CLI _legacy_manifest explicitly reads this path at cli.py:1180; retain unchanged.';target=p
 elif p in EMBEDDED_KEEP:action='keep';reason='Retained current document embeds this image/HTML asset; keep offline dependency byte-for-byte at original path.';target=p
 elif p in ARCHIVE:action='archive';reason='Dated evidence/retired source or explicitly superseded review; preserved byte-for-byte in single offline archive; no live file reader remains.';target=zip_path.relative_to(CANDIDATE).as_posix()+'!/'+p
 else:action='keep';reason={'spec_schema_mirror':'Byte-parity and schema discovery tests require this mirror; runtime schema consolidation is outside this documentation budget.','prototype_or_visual_validation_asset':'Keep inherited/current specification sample and associated assets; no proof authorizes removing its design or acceptance role.','spec_attached_dated_evidence':'Keep spec-attached evidence until all pack-local consumers are migrated; no speculative saving credited.','inherited_example_or_fixture':'Required by inherited contract/examples or direct tests; retained byte-for-byte.','inherited_or_current_spec_keep':'Active index or inherited contract; age is not retirement evidence.','active_design_received_source':'DESIGN.md directly selects this received design source; preserve source and assets.','received_design_history_keep_original':'Historical received design source remains a referenced original; retain until separate design-source migration.','canonical_skill_or_method_keep':'Canonical packaged Skill/method source; no change to bytes or frozen method hashes.','work_item_contract_or_evidence_keep':'Work-item status is not inferred from date; keep current repair/implementation inputs.','test_reference_consumer':'Existing test behavior and assertions preserved; only three approved path consumers are changed.','runtime_reference_consumer':'Runtime source kept unchanged.','packaging_or_tooling_consumer':'Packaging/tool entry remains unchanged; no docs-directory inclusion added.'}.get(kind,'Current user/Agent navigation or scope-preserved guidance; retain.');target=p
 inventory.append({'path':p,'classification':kind,'action':action,'reason':reason,'target':target,'baseline_line_start':1 if text is not None else None,'baseline_line_end':len(text.splitlines()) if text is not None else None,'bytes_before':len(data),'lines_before':len(text.splitlines()) if text is not None else 0,'sha256_before':sha(data),'git_blob_sha':TRACKED[p]['sha'],'git_mode':TRACKED[p]['mode'],'reference_ids':sorted(set(inbound.get(p,[]))),'direct_source_refs':[r['id'] for r in refs if r['target']==p and (r['source'].startswith(('src/','tests/','tools/','.github/')) or r['source'] in ('MANIFEST.in','pyproject.toml','setup.py','Makefile'))]})

with (OUT/'file-disposition.json').open('w') as f:json.dump(inventory,f,ensure_ascii=False,indent=2)
with (OUT/'file-disposition.csv').open('w') as f:
 fields=list(inventory[0]);writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({**row,'reference_ids':';'.join(map(str,row['reference_ids'])),'direct_source_refs':';'.join(map(str,row['direct_source_refs']))} for row in inventory)
(OUT/'references.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2))
(OUT/'exact-edits.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2))
(OUT/'fixture-map.json').write_text(json.dumps(FIXTURE_MAP,ensure_ascii=False,indent=2))
(OUT/'added-files.json').write_text(json.dumps([{'path':p,'bytes':len(data),'text_lines':len(data.decode().splitlines()),'sha256':sha(data),'content':data.decode()} for p,data in ADDITIONS.items()],ensure_ascii=False,indent=2))
(OUT/'candidate-paths.json').write_text(json.dumps(sorted([p for p in TRACKED if p not in ARCHIVE]+list(FIXTURE_MAP.values())+list(ADDITIONS)+[str(p.relative_to(CANDIDATE)) for p in HISTORY.iterdir()]),ensure_ascii=False,indent=2))
(OUT/'removed-paths.txt').write_text('\n'.join(sorted(ARCHIVE))+'\n')
def write_diff(handle,old,new,old_path,new_path):
 for line in difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile=old_path,tofile=new_path):
  handle.write(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
with (OUT/'candidate.patch').open('w') as f:
 for edit in edits:
  p=edit['path'];write_diff(f,CONTENTS[p][1],updates[p].decode(),'a/'+p,'b/'+p)
 new_text={new:CONTENTS[old][0] for old,new in FIXTURE_MAP.items()}|ADDITIONS|{'docs/history/README.md':(HISTORY/'README.md').read_bytes(),'docs/history/manifest.csv':manifest_bytes}
 for p,data in sorted(new_text.items()):write_diff(f,'',data.decode(),'/dev/null','b/'+p)

# Exact preservation check includes compressed archive bytes and migrated copies.
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 for row in archive_rows:
  assert z.read(row['original_path'])==CONTENTS[row['original_path']][0],row['original_path']
 assert z.read('ARCHIVE-MANIFEST.csv')==manifest_bytes
for old,new in FIXTURE_MAP.items():assert (CANDIDATE/new).read_bytes()==CONTENTS[old][0]
assert (CANDIDATE/LEGACY_KEEP).read_bytes()==CONTENTS[LEGACY_KEEP][0]

def stat(paths,root):
 total=collections.Counter(files=0,bytes=0,text_files=0,text_lines=0)
 for p in paths:
  data=(root/p).read_bytes();total['files']+=1;total['bytes']+=len(data)
  if Path(p).suffix.lower() in BINARY or b'\0' in data:continue
  try:text=data.decode('utf-8-sig')
  except UnicodeDecodeError:continue
  total['text_files']+=1;total['text_lines']+=len(text.splitlines())
 return dict(total)
candidate_paths=json.loads((OUT/'candidate-paths.json').read_text())
summary={'baseline':BASE,'status':'isolated_candidate_generated; production implementation needs Codex verification; 需要 Codex 核验','before_repository':stat(TRACKED,ROOT),'after_repository':stat(candidate_paths,CANDIDATE),'before_docs':stat([p for p in TRACKED if p.startswith('docs/')],ROOT),'after_docs':stat([p for p in candidate_paths if p.startswith('docs/')],CANDIDATE),'archive':{'path':str(zip_path),'original_entries':len(archive_rows),'zip_entries':len(archive_rows)+1,'bytes':zip_path.stat().st_size,'sha256':zip_sha,'uncompressed_original_bytes':sum(r['bytes'] for r in archive_rows),'uncompressed_original_text_lines':sum(r['text_lines'] for r in archive_rows),'all_bytes_verified':True},'fixture_migration':{'files':len(FIXTURE_MAP),'bytes':sum(len(CONTENTS[p][0]) for p in FIXTURE_MAP),'text_lines':sum(len(CONTENTS[p][1].splitlines()) for p in FIXTURE_MAP),'all_bytes_verified':True},'fixture_navigation_cost':stat(ADDITIONS,CANDIDATE),'rewritten_files':len(updates),'deleted_information_files':0,'archived_original_paths_removed':len(ARCHIVE),'reference_records':len(refs),'inventory_scope_files':len(inventory),'doc_inventory_files':sum(p.startswith('docs/') for p in review_scope),'dispositions':dict(collections.Counter(r['action'] for r in inventory)),'history_added_cost':stat([str(p.relative_to(CANDIDATE)) for p in HISTORY.iterdir()],CANDIDATE)}
(OUT/'dry-run-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
