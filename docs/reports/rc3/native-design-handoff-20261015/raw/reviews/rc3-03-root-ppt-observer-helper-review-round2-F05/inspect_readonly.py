"""Readonly actual physical fields plus exact-helper predicate counterexamples."""
from pathlib import Path
import ast
import hashlib
import inspect
import json
import xml.etree.ElementTree as ET
import zipfile
from deck_master.production import resolve_page_design
from deck_master.store import Store

OUT=Path(__file__).resolve().parent
helper=OUT/'observe-native-ppt-0a148342.py'
assert hashlib.sha256(helper.read_bytes()).hexdigest()=='0a148342c51aad0efd46f6910fc59ebefe0f95baee1d7d6a6c5b48fa79021e52'
store=Store('/workspace/work/rc3/native-image-pilot-03/run-02-project')
doc=store.load_document();entry=next(e for e in doc['pages'] if e['page_id']=='p04')
effective=resolve_page_design(store,doc,entry,require_current=True)
canvas=effective['canvas'];typography=effective['styles'][0]['typography']
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
ppt=Path('/workspace/work/rc3/reviews/rc3-03-actual-ppt-mechanical-edit-run02/inputs/original.pptx')
with zipfile.ZipFile(ppt) as z:
    slide=ET.fromstring(z.read('ppt/slides/slide1.xml'))
    size=ET.fromstring(z.read('ppt/presentation.xml')).find('p:sldSz',ns)
run_records=[]
for shape in slide.findall('.//p:sp',ns):
    name=shape.find('p:nvSpPr/p:cNvPr',ns).get('name')
    for run in shape.findall('.//a:r',ns):
        text=run.find('a:t',ns)
        if text is None or not text.text:continue
        props=run.find('a:rPr',ns)
        sz=props.get('sz') if props is not None else None
        run_records.append({'shape_name':name,'text':text.text,'explicit_size_hundredth_pt':sz,
                            'actual_pt':int(sz)/100 if sz is not None else None})
tree=ast.parse(helper.read_text())
def exact_assignment(name):
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
    assert len(nodes)==1
    return compile(ast.Expression(nodes[0].value),str(helper),'eval')
predicate=exact_assignment('typography_matches_pilot')
evaluate=lambda values:eval(predicate,{'point_sizes':sorted(set(values)),'typography':typography,'bool':bool,'min':min,'max':max})
probes=[{'name':'body18_title30_secondary-heading24','kind':'synthetic_L1_predicate_counterexample_not_generated_PPT',
         'role_sizes_pt':{'body':18,'page_title':30,'exceptions_heading':24},'helper_result':evaluate([18,30,24]),
         'expected_role_result':False},
        {'name':'title18_body30','kind':'synthetic_L1_predicate_counterexample_not_generated_PPT',
         'role_sizes_pt':{'body':30,'page_title':18},'helper_result':evaluate([30,18]),'expected_role_result':False}]
assert all(p['helper_result'] is True and p['expected_role_result'] is False for p in probes)
point_expression=exact_assignment('point_sizes')
example=ET.fromstring('<p:spTree xmlns:p="'+ns['p']+'" xmlns:a="'+ns['a']+'"><p:sp><p:txBody><a:p><a:r><a:rPr sz="3000"/><a:t>known size</a:t></a:r><a:r><a:rPr/><a:t>unknown size</a:t></a:r></a:p></p:txBody></p:sp></p:spTree>')
extracted=eval(point_expression,{'root':example,'ns':ns,'sorted':sorted,'int':int})
result={'scope':'readonly_actual_field_check_and_synthetic_predicate_logic_only_no_compile_or_writer',
 'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'resolve_page_design_signature':str(inspect.signature(resolve_page_design)),
 'resolver_origin':inspect.getfile(resolve_page_design),'actual_document_revision_at_read':doc['revision_id'],
 'frozen_canvas':canvas,'frozen_typography':typography,
 'desired_compile_options_px':[canvas['slide_width_in']*96,canvas['slide_height_in']*96],
 'desired_physical_emu':[round(canvas['slide_width_in']*914400),round(canvas['slide_height_in']*914400)],
 'prior_actual_PPTX_sha256':hashlib.sha256(ppt.read_bytes()).hexdigest(),
 'prior_actual_physical_emu':[int(size.get('cx')),int(size.get('cy'))],
 'prior_actual_physical_inches':[int(size.get('cx'))/914400,int(size.get('cy'))/914400],
 'prior_template_type_label':size.get('type'),'prior_actual_visible_run_records':run_records,
 'predicate_counterexamples':probes,
 'missing_size_predicate_counterexample':{'kind':'synthetic_L1_XML_extraction_logic_not_generated_PPT','visible_runs':2,'explicit_sizes_extracted':extracted,'helper_result':evaluate(extracted),'expected':'UNVERIFIABLE_not_PASS'},
 'prediction_only_not_executed_conversion':{'existing_SVG_sizes_px':[24,40],'correct_canvas_uniform_scale':0.8,'compiler_formula':'svg_font_px * min(width_px/svg_width,height_px/svg_height) * 0.75','predicted_new_native_points':[14.4,24]},
 'actual_new_PPTX_or_effect_status':'NOT_RUN','verdict':'REQUEST_CHANGES_role_binding_and_unresolved_size'}
(OUT/'readonly-field-and-predicate-observations.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:result[k] for k in ['desired_compile_options_px','desired_physical_emu','prior_actual_physical_inches','predicate_counterexamples','missing_size_predicate_counterexample','verdict']},ensure_ascii=False,indent=2,sort_keys=True))
