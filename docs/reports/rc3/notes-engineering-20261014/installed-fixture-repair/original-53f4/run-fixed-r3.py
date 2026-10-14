import sys,runpy,json,hashlib,zipfile,subprocess
from pathlib import Path
import deck_master
root=Path(__file__).parent;source=Path('/workspace/work/rc3/reviews/rc3-02-docs-snapshot-53f4a')
package=Path(deck_master.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve()) and 'site-packages' in package.parts
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()=='53f4ab335d4bacb0862d810cf8acf55eeba7e744'
wheel=root/'dist/deck_master-1.0.0.dev2-py3-none-any.whl';records=[]
with zipfile.ZipFile(wheel) as z:
 for name in z.namelist():
  if not name.startswith('deck_master/') or name.endswith('/'):continue
  relative=name[len('deck_master/'):];original=source/('skills/deck-master/'+relative[len('resources/skill/'):] if relative.startswith('resources/skill/') else 'src/deck_master/'+relative)
  data=z.read(name);assert original.read_bytes()==(package/relative).read_bytes()==data,name
  records.append({'path':relative,'sha256':hashlib.sha256(data).hexdigest()})
record={'head':'53f4ab335d4bacb0862d810cf8acf55eeba7e744','tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip(),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'python':sys.executable,'isolated':sys.flags.isolated,'module':str(package),'verified_source_package_install_files':len(records),'files':records,'fixture_source':str(source/'examples/workbench'),'source_borrowing':'Only example sibling imports allowed; installed deck_master preloaded and modules audited.'}
(root/'installed-source-provenance-r3.json').write_text(json.dumps(record,indent=2)+'\n')
sys.path.insert(0,str(source/'examples/workbench'))
sys.argv=['w12_offline_browser.py','--require-installed','--font','DejaVu Sans','--out',str(root/'w12-old-r3')]
try:runpy.run_path(str(source/'examples/workbench/w12_offline_browser.py'),run_name='__main__')
finally:
 modules={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.items() if (name=='deck_master' or name.startswith('deck_master.')) and getattr(m,'__file__',None)}
 assert all(Path(p).is_relative_to(package) for p in modules.values()),modules
 (root/'actual-module-origins-r3.json').write_text(json.dumps({'python':sys.executable,'isolated':sys.flags.isolated,'modules':modules},indent=2)+'\n')
