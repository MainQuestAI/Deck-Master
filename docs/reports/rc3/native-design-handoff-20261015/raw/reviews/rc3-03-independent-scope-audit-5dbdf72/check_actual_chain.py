"""Read immutable raw artifacts only. Never import the private controller."""
from pathlib import Path
import hashlib
import json
from PIL import Image

OUT = Path(__file__).resolve().parent
PILOT = Path('/workspace/work/rc3/native-image-pilot-03')
PROJECT = PILOT/'run-02-project'
NATIVE = PILOT/'run-02-native'
hash_bytes = lambda data: hashlib.sha256(data).hexdigest()
records = []

def read(path):
 data = path.read_bytes()
 records.append({'path':str(path),'sha256':hash_bytes(data),'bytes':len(data)})
 return json.loads(data)

def object_json(ref):
 path = PROJECT/ref['path']
 value = read(path)
 assert records[-1]['sha256'] == ref['sha256'], path
 return value

raw = read(NATIVE/'actual-root-tool-return.json')
callback = read(NATIVE/'actual-tool-callback.json')
settlement = read(NATIVE/'settlement.json')
shown = read(NATIVE/'actual-generation-attempt.json')
identity = read(NATIVE/'installed-execution-identity.json')
workorder = read(PILOT/'run-02-reconstruction-5dbdf72/workorder.json')
reader = read(PILOT/'run-02-reconstruction-5dbdf72/reader-installation-identity.json')
fixed_page = read(PILOT/'run-02-reconstruction-5dbdf72/fixed-page.json')
request = object_json(shown['attempt']['request_ref'])
frozen = request['input']
page = object_json(frozen['page']['page_ref'])
context = frozen['design_context']
plan = object_json(context['content_basis']['plan_ref'])
recipe = object_json(context['content_basis']['recipe_ref'])
original = (NATIVE/'original-blueprint.png').read_bytes()
records.append({'path':str(NATIVE/'original-blueprint.png'),'sha256':hash_bytes(original),'bytes':len(original)})
assert callback['actual_arguments'] == raw['actual_arguments']
assert callback['actual_arguments']['prompt'] == frozen['prompt']
assert callback['actual_arguments']['transparent_background'] == frozen['parameters']['transparent_background']
assert 'referenced_image_paths' not in callback['actual_arguments']
assert frozen['references'] == []
assert shown['observations'][0]['submitted']['prompt'] == frozen['prompt']
assert shown['observations'][0]['output']['sha256'] == hash_bytes(original) == callback['original_png_sha256']
assert shown['call']['state'] == 'consumed'
assert not settlement['automatic_adoption'] and not settlement['automatic_expansion']
assert not settlement['automatic_candidate_acceptance']
projection = json.loads(frozen['prompt'].split('Structured input:\n',1)[1])
assert projection['customer_visible'] == page['customer_visible']
assert fixed_page == page
assert projection['visual_spec']['nodes'] == page['visual_spec']['nodes']
assert projection['visual_spec']['edges'] == page['visual_spec']['edges']
assert projection['content_requirements'] == context['content_requirements']
assert projection['recipe_parameters'] == context['recipe_parameters']
assert 'content_basis' not in projection
role = next(item for item in plan['input']['page_roles'] if item['page_id'] == 'p04')
for key in ('content_profile','density_rationale','required_qualifications'):
 assert projection['content_requirements'][key] == role[key]
assert workorder['page_design_contexts']['p04'] == context
assert workorder['required_capabilities'] == ['content_requirements_v1','style_recipe','style_recipe_v3']
assert identity['install']['source_sha'] == '8057905162f20926cfc1a0a96252bc6745f4e700'
assert '5dbdf72089d6-94f6f31fcadf' in reader['python_prefix']
with Image.open(NATIVE/'original-blueprint.png') as image:
 dimensions = list(image.size)
summary = {
 'status':'PASS', 'scope':'actual p04 image request / original PNG / immutable installed-5db reconstruct handoff',
 'evidence_kind':'host_attested actual native image; not human/platform-signed/fair E2/E3',
 'image_source_sha':identity['install']['source_sha'],
 'reader_source_sha':'5dbdf72089d6625449a23a52ef3e23859c597b4e',
 'reader_installation':reader,
 'request_id':request['request_id'],'request_ref':shown['attempt']['request_ref'],
 'attempt_id':shown['attempt']['attempt_id'],'page_id':'p04',
 'original_png_sha256':hash_bytes(original),'actual_dimensions':dimensions,
 'requested_canvas':[context['canvas']['width_px'],context['canvas']['height_px']],
 'actual_model':None,'actual_seed':None,'dollar_cost':None,
 'automatic_adoption':False,'automatic_expansion':False,
 'visual_observation':'Auditor viewed original PNG: four forward-linked responsibility nodes, two exception rows with three column owners, human-only formal submission boundary are visible.',
 'limitations':['Actual returned dimensions differ from requested canvas; original bytes were preserved.',
  'No new 5db image call is claimed. The 5db reader retains the old Request identity.',
  'This is one engineering page, not a full-deck risk matrix or fair E2 comparison.',
  'Final SVG/PPTX/render/readback and independent visual review remain pending Root binding.'],
 'checked_files':records,
}
(OUT/'actual-chain-check.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:value for key,value in summary.items() if key not in ('checked_files','reader_installation')},ensure_ascii=False,indent=2))
