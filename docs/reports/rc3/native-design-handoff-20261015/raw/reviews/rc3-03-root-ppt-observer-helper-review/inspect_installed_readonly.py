"""Installed signatures and current document fields only: no writer/compiler."""
from pathlib import Path
import dataclasses
import hashlib
import inspect
import json
import sys
import deck_master
from deck_master import pipeline,service
from deck_master.compiler import CompileOptions,SvgInput,compile_deck
from deck_master.compiler.svg import parse_svg
from deck_master.store import Store

ROOT=Path(__file__).resolve().parent
INSTALL=Path('/workspace/work/rc3/candidate-03-5dbdf72')
manifest_data=(INSTALL/'manifest.json').read_bytes();manifest=json.loads(manifest_data)
assert hashlib.sha256(manifest_data).hexdigest()=='bcb668040f2c5e7cd0613b792517f6ec055f1d5925b5e5a582c076e67dfdbb10'
assert deck_master.__file__==manifest['module_path']
store=Store('/workspace/work/rc3/native-image-pilot-03/run-02-project')
doc=store.load_document();entry=next(e for e in doc['pages'] if e['page_id']=='p04')
page=store.read_object_json(entry['page'])
assert len(doc['pages'])==8
assert entry['page']['sha256']=='cdbdd15ec62121abac495025cbbf92855557c8d815ae3e843ae1b151fb583e8b'
assert doc['design_context']['canvas']['width_px']==1600 and doc['design_context']['canvas']['height_px']==900
out={'observation_kind':'installed_API_signatures_and_fields_read_only_no_helper_execution',
 'python':sys.executable,'package':deck_master.__file__,'source_sha':manifest['source_sha'],
 'source_tree':manifest['source_tree'],'wheel_sha256':manifest['wheel_sha256'],
 'manifest_sha256':hashlib.sha256(manifest_data).hexdigest(),
 'signatures':{name:str(inspect.signature(fn)) for name,fn in [('preview_svg_page',pipeline.preview_svg_page),
  ('parse_svg',parse_svg),('resolve_fonts',pipeline.resolve_fonts),('compile_deck',compile_deck),
  ('readback',pipeline.readback),('render_deck',pipeline.render_deck),('SvgInput',SvgInput),('CompileOptions',CompileOptions)]},
 'origins':{name:inspect.getfile(fn) for name,fn in [('service',service),('pipeline',pipeline),
  ('parse_svg',parse_svg),('compile_deck',compile_deck)]},
 'document_revision':doc['revision_id'],'page_count':len(doc['pages']),
 'document_fields_used_by_helper':{key:doc.get(key) for key in ('narrative','content_plan','outputs')},
 'actual_p04_slots':entry,'actual_canvas':doc['design_context']['canvas'],
 'speaker_notes_present':isinstance(page.get('speaker_notes'),str),
 'writes_or_compile_or_tool_calls':0}
(ROOT/'installed-signatures-and-fields.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
