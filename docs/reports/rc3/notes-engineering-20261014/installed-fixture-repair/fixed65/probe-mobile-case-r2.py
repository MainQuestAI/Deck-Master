import sys,json,os,shutil
from pathlib import Path
import deck_master,deck_master.web,pytest
from playwright.sync_api import Locator
package=Path(deck_master.__file__).resolve().parent;assert 'site-packages' in package.parts
source=Path('/workspace/work/rc3/reviews/rc3-02-code-snapshot-65d82');root=Path(sys.argv[1]);root.mkdir()
observations=[]
original_box=Locator.bounding_box
def observed_box(locator,*args,**kwargs):
 box=original_box(locator,*args,**kwargs)
 if '.page-image-viewport' in str(locator):
  record={'original_box':box,'locator':str(locator)}
  try:
   record['at_measurement']=locator.page.evaluate("""() => ({viewport:{width:innerWidth,height:innerHeight}, fontsStatus:document.fonts.status, bodyFont:getComputedStyle(document.body).fontFamily, bodyFontSize:getComputedStyle(document.body).fontSize, devicePixelRatio,scrollY, canvas:document.querySelector('.page-image-viewport')?.getBoundingClientRect().toJSON()??null})""")
  except Exception as e:record['observation_error']=repr(e)
  observations.append(record)
 return box
Locator.bounding_box=observed_box
class Observe:
 @pytest.hookimpl(hookwrapper=True)
 def pytest_runtest_makereport(self,item,call):
  result=yield
  report=result.get_result()
  if report.when!='call':return
  record={'nodeid':item.nodeid,'outcome':report.outcome,'duration':report.duration,'observations':observations}
  if 'workbench' in item.funcargs:
   page=item.funcargs['workbench'][0]
   record['browser_version']=page.context.browser.version
   try:
    record['call_end']=page.evaluate("""() => ({canvas:document.querySelector('.page-image-viewport')?.getBoundingClientRect().toJSON()??null,viewport:{width:innerWidth,height:innerHeight},fontsStatus:document.fonts.status,bodyFont:getComputedStyle(document.body).fontFamily,bodyFontSize:getComputedStyle(document.body).fontSize,devicePixelRatio,scrollY})""")
    page.screenshot(path=str(root/'actual-case.png'),full_page=True)
   except Exception as e:record['observation_error']=repr(e)
  (root/'case-result.json').write_text(json.dumps(record,indent=2)+'\n')
args=['-q',str(source/'tests/rebuild/test_workbench_usability_browser.py')+'::test_reading_prioritizes_artwork_and_preserves_fixed_layers[390-844]','--require-browser','-p','no:cacheprovider','--basetemp',str(root/'pytest-tmp')]
status=pytest.main(args,plugins=[Observe()])
modules={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=='deck_master' or n.startswith('deck_master.')) and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(package) for p in modules.values()),modules
(root/'execution.json').write_text(json.dumps({'status':int(status),'python':sys.executable,'module':str(package),'tmpdir':os.environ.get('TMPDIR'),'chromium':shutil.which('chromium'),'isolated':sys.flags.isolated,'fixture_source':str(source),'modules':modules},indent=2)+'\n')
sys.exit(status)
