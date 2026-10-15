"""Evaluate only exact revised role-check AST on readonly/in-memory inputs."""
from copy import deepcopy
from pathlib import Path
import ast
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from deck_master.production import resolve_page_design
from deck_master.store import Store

OUT=Path(__file__).resolve().parent
helper=OUT/'observe-native-ppt-7fe47e10.py'
assert hashlib.sha256(helper.read_bytes()).hexdigest()=='7fe47e10d9e419cd8408aa8316c032fca6ff122e2e15059c118419ac27232251'
tree=ast.parse(helper.read_text())
blocks=[]
for node in ast.walk(tree):
    if isinstance(node,ast.With):
        ids=[next((t.id for t in s.targets if isinstance(t,ast.Name)),None) if isinstance(s,ast.Assign) else None for s in node.body]
        if 'heading_atoms' in ids and 'typography_matches_pilot' in ids:
            blocks.append(node.body[ids.index('heading_atoms'):ids.index('typography_matches_pilot')+1])
assert len(blocks)==1
code=compile(ast.Module(body=blocks[0],type_ignores=[]),str(helper),'exec')
store=Store('/workspace/work/rc3/native-image-pilot-03/run-02-project');doc=store.load_document()
entry=next(e for e in doc['pages'] if e['page_id']=='p04')
effective=resolve_page_design(store,doc,entry,require_current=True)
typography=effective['styles'][0]['typography']
parsed=json.loads(Path('/workspace/work/rc3/native-image-pilot-03/run-02-native-ppt/actual-svg-ir.json').read_text())
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
ppt=Path('/workspace/work/rc3/reviews/rc3-03-actual-ppt-mechanical-edit-run02/inputs/original.pptx')
with zipfile.ZipFile(ppt) as archive:original=ET.fromstring(archive.read('ppt/slides/slide1.xml'))
def shape(root,name):return next(s for s in root.findall('.//p:sp',ns) if s.find('p:nvSpPr/p:cNvPr',ns).get('name')==name)
def first_props(root,name):return shape(root,name).find('.//a:r/a:rPr',ns)
def evaluate(root):
    scope={'root':root,'parsed':parsed,'typography':typography,'ns':ns}
    exec(code,scope)
    return {key:scope[key] for key in ('typography_matches_pilot','run_checks','seen_headings','point_sizes')}
cases=[]
def check(name,mutate,expected):
    root=deepcopy(original)
    if mutate:mutate(root)
    actual=evaluate(root)
    assert actual['typography_matches_pilot'] is expected,(name,actual)
    cases.append({'name':name,'evidence_kind':'exact_helper_AST_predicate_readonly_or_inmemory_L1_not_new_PPT',
      'expected_role_match':expected,'actual_role_match':actual['typography_matches_pilot'],
      'seen_headings':sorted(actual['seen_headings']),'failed_runs':[r for r in actual['run_checks'] if r['status']!='pass']})
    return actual
actual_old=check('old_actual_native_role_sizes_only_wrong_physical_canvas_separate',None,True)
check('secondary_heading_24_other_heading_30_and_body18',lambda r:first_props(r,'atom:p04:block:exceptions-heading:text').set('sz','2400'),False)
def title_small_body_large(root):
    first_props(root,'atom:p04:title').set('sz','1800')
    first_props(root,'atom:p04:subtitle').set('sz','3000')
check('title18_cannot_borrow_large_body30',title_small_body_large,False)
check('body_run_missing_explicit_sz',lambda r:first_props(r,'atom:p04:subtitle').attrib.pop('sz'),False)
check('body17_99_below_frozen18',lambda r:first_props(r,'atom:p04:subtitle').set('sz','1799'),False)
check('unknown_visible_shape_name',lambda r:shape(r,'atom:p04:subtitle').find('p:nvSpPr/p:cNvPr',ns).set('name','unrecognized-source-text'),False)
def remove_secondary_heading(root):
    s=shape(root,'atom:p04:block:exceptions-heading:text')
    for parent in s.findall('.//a:p',ns):
        for run in list(parent):
            if run.tag=='{'+ns['a']+'}r':parent.remove(run)
check('both_heading_atoms_must_be_seen',remove_secondary_heading,False)
result={'scope':'revised_helper_role_logic_only_no_main_compile_preview_or_project_writer',
 'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),
 'cases':cases,'case_count':len(cases),'all_expected_results_observed':True,
 'old_actual_visible_run_census':actual_old['run_checks'],
 'actual_new_conversion':'NOT_RUN','visual_quality':'NOT_EVALUATED'}
(OUT/'revised-role-predicate-observations.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps({'case_count':len(cases),'all_expected_results_observed':True,'actual_prior_run_count':len(actual_old['run_checks']),'actual_new_conversion':'NOT_RUN'},indent=2))
