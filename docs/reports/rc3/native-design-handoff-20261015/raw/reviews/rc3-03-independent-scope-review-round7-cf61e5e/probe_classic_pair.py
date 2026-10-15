"""Compare the same classic public path across old/new installed SDKs."""
from pathlib import Path
import json,sys,uuid
import deck_master
from deck_master import service,tasks,editing
from deck_master.store import Store
OUT=Path(__file__).resolve().parent
phase=sys.argv[1]
project=OUT/('classic-pair-'+phase)
page={'schema_version':'deck_page_package.v2','page_id':'p1',
 'customer_visible':{'title':'Classic boundary','body_blocks':[{'id':'b1','type':'paragraph','text':'Fixed classic test fact.'}]},
 'visual_spec':{'intent':'one paragraph','reference_mode':'new_design'}}
service.create(project,brief='Classic protocol boundary; no model call',draft={'pages':[page]})
store=Store(project);before=store.load_document()
summary=service.continue_project(project)['pending_tasks'][0]
doc=store.load_document();task=tasks._lookup_task(doc,summary['task_id'],store)
entry=doc['pages'][0];changed=store.read_object_json(entry['page']);changed['speaker_notes']='Explicit classic notes edit.'
editing.edit_page(project,page=changed,base_revision=store.current_revision_id(),page_hash=entry['page']['sha256'],operation_id=str(uuid.uuid4()))
after=store.load_document()
result={'phase':phase,'module':deck_master.__file__,'evidence_kind':'disposable classic public SDK path, zero model calls',
 'facts':{'initial_compatibility':before.get('compatibility'),'workbench_protocol_required_before':store.workbench_protocol_required(doc),
  'task_protocol':task.get('protocol_version'),'task_capabilities':task.get('required_capabilities'),
  'generation_input_present':'generation_input' in summary,
  'requirements_added_to_classic_request':'resolved_design_context' in summary['production_request'],
  'requirements_added_to_classic_context':'content_requirements' in summary['resolved_design_context'],
  'after_existing_edit_compatibility':after.get('compatibility'),
  'workbench_protocol_required_after':store.workbench_protocol_required(after),
  'task_current_after_existing_notes_edit':tasks.task_inputs_current(store,after,task)},'actual_image_calls':0}
(OUT/('classic-pair-'+phase+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
