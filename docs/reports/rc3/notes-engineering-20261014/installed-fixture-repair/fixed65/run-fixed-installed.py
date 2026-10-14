import sys,runpy,json,hashlib,zipfile,subprocess
from pathlib import Path
import deck_master
root=Path(__file__).parent;source=Path('/workspace/work/rc3/reviews/rc3-02-code-snapshot-65d82');kind=sys.argv[1]
package=Path(deck_master.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve()) and 'site-packages' in package.parts
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()=='65d8203ec099b0460dbf031b24cf2ea5a02fd0f2'
wheel=root/'dist/deck_master-1.0.0.dev2-py3-none-any.whl';records=[]
with zipfile.ZipFile(wheel) as z:
 for name in z.namelist():
  if not name.startswith('deck_master/') or name.endswith('/'):continue
  relative=name[len('deck_master/'):];original=source/('skills/deck-master/'+relative[len('resources/skill/'):] if relative.startswith('resources/skill/') else 'src/deck_master/'+relative)
  data=z.read(name);assert original.read_bytes()==(package/relative).read_bytes()==data,name
  records.append({'path':relative,'sha256':hashlib.sha256(data).hexdigest()})
record={'head':'65d8203ec099b0460dbf031b24cf2ea5a02fd0f2','tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip(),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'python':sys.executable,'isolated':sys.flags.isolated,'module':str(package),'verified_source_package_install_files':len(records),'files':records,'fixture_source':str(source/'examples/workbench'),'examples':{name:hashlib.sha256((source/'examples/workbench'/name).read_bytes()).hexdigest() for name in ['w11_browser.py','w12_offline_browser.py','w12_installed_regressions.py']},'source_borrowing':'Only example siblings and fixed test helpers allowed; installed core modules preloaded and audited.'}
(root/(kind+'-installed-provenance.json')).write_text(json.dumps(record,indent=2)+'\n')
sys.path.insert(0,str(source/'examples/workbench'))
if kind=='w12':
 script='w12_offline_browser.py';sys.argv=[script,'--require-installed','--font','DejaVu Sans','--out',str(root/'w12-complete')]
else:
 assert kind=='recovery';script='w12_installed_regressions.py';sys.argv=[script,'--out',str(root/'installed-recovery.json')]
try:runpy.run_path(str(source/'examples/workbench'/script),run_name='__main__')
finally:
 modules={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.items() if (name=='deck_master' or name.startswith('deck_master.')) and getattr(m,'__file__',None)}
 assert all(Path(p).is_relative_to(package) for p in modules.values()),modules
 (root/(kind+'-module-origins.json')).write_text(json.dumps({'python':sys.executable,'isolated':sys.flags.isolated,'modules':modules},indent=2)+'\n')
