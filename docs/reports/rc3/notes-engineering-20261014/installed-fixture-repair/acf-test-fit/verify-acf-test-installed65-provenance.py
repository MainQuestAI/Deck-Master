import sys,json,hashlib,zipfile,subprocess,os,shutil
from pathlib import Path
import deck_master
root=Path(__file__).parent;source=Path('/workspace/work/rc3/reviews/rc3-02-code-snapshot-acf2b');package=Path(deck_master.__file__).resolve().parent
assert 'site-packages' in package.parts
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip();assert head=='acf2b2edd4a88f74e8b671a18e32eb74b780eb84'
wheel=root/'dist/deck_master-1.0.0.dev2-py3-none-any.whl';records=[]
with zipfile.ZipFile(wheel) as z:
 for name in z.namelist():
  if not name.startswith('deck_master/') or name.endswith('/'):continue
  relative=name[len('deck_master/'):];original=source/('skills/deck-master/'+relative[len('resources/skill/'):] if relative.startswith('resources/skill/') else 'src/deck_master/'+relative)
  data=z.read(name);assert original.read_bytes()==(package/relative).read_bytes()==data,name
  records.append({'path':relative,'sha256':hashlib.sha256(data).hexdigest()})
helpers=['tests/rebuild/test_workbench_usability_browser.py','tests/rebuild/test_deep_quality_browser.py','tests/rebuild/test_icon_quality.py']
artifacts=['probe-fixed-acf-three-viewports.py','acf-three-viewports.log','acf-three-viewports/execution.json','acf-three-viewports/case-result-390-844.json','acf-three-viewports/case-result-1280-800.json','acf-three-viewports/case-result-1440-900.json','controlled-mobile-lifecycle-acf.py','acf-lifecycle-control.log','acf-lifecycle-control/execution.json','acf-lifecycle-control/observations.json']
record={'test_source_sha':head,'test_source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=source,text=True).strip(),'source':str(source),'installed_core_build_source_sha':'65d8203ec099b0460dbf031b24cf2ea5a02fd0f2','installed_core_build_tree':'e4e94f7acc9d9156beeb77fa8ede06cb0a954480','wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'python':sys.executable,'isolated':sys.flags.isolated,'module':str(package),'verified_acf_source_65package_install_files':len(records),'files':records,'fixture_source_files':[{'file':s,'sha256':hashlib.sha256((source/s).read_bytes()).hexdigest()} for s in helpers],'result':'3 original viewport cases PASS in5.07s; controlled actual SVG response lifecycle PASS1 in2.03s. No full local suite rerun. Original65 full238PASS/1FAIL remains FAIL.','artifacts':[{'file':s,'sha256':hashlib.sha256((root/s).read_bytes()).hexdigest()} for s in artifacts],'TMPDIR':os.environ.get('TMPDIR'),'chromium':shutil.which('chromium'),'borrowing':'Installed runtime preloaded, each actual test driver audited all loaded core module origins; only fixed test helpers loaded from source.'}
(root/'acf-scoped-provenance.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['test_source_sha','installed_core_build_source_sha','wheel_sha256','verified_acf_source_65package_install_files','result']}))
