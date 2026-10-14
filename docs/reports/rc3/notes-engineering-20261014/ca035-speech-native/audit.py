from pathlib import Path
import sys,json,hashlib
from deck_master import editing,content_review
from deck_master.store import Store
from deck_master.compiler.native import notes_records,normalize_notes
root=Path(__file__).resolve().parent
cases=[root/'run-final/bound',root/'run-final/imported_mapping_null_narrative']
records=[]
for case in cases:
 before=json.loads((case/'before-document.json').read_text());after_speech=json.loads((case/'after-speech-document.json').read_text());store=Store(case/'project');current=store.load_document()
 old_notes=notes_records((case/'original.pptx').read_bytes());final_notes=notes_records((case/'downloaded.pptx').read_bytes())
 assert [r['notes'] for r in old_notes]==[normalize_notes(store.read_object_json(e['page']).get('speaker_notes','')) for e in before['pages']]
 assert [r['notes'] for r in final_notes]==[normalize_notes(store.read_object_json(e['page']).get('speaker_notes','')) for e in current['pages']]
 old_images={t['task_id']:ref for ref in before['tasks'] if (t:=store.read_object_json(ref))['kind']=='blueprint'}
 new_images={t['task_id']:ref for ref in current['tasks'] if (t:=store.read_object_json(ref))['kind']=='blueprint'}
 assert old_images==new_images
 visuals=[]
 for old,new in zip(before['pages'],current['pages'],strict=True):
  assert all(old[s]==new[s] and old[s] is not None for s in ('blueprint','svg','svg_preview'))
  summary=editing.page_visual_summary(store,current,new);assert summary['status']=='pass'
  visuals.append({'page_id':new['page_id'],'same_actual_refs':{s:new[s] for s in ('blueprint','svg','svg_preview')},'pagevisual_summary':summary})
 old_visual_reviews=[ref for ref in before['reviews'] if store.read_object_json(ref).get('review_stage')=='page_visual']
 assert all(ref in current['reviews'] for ref in old_visual_reviews)
 assert content_review.preproduction_status(store,current)['status']=='pass'
 assert current['collaboration']['quality_profile']==before['collaboration']['quality_profile']
 assert current['collaboration']['request']==before['collaboration']['request']
 assert current['collaboration']['authorizations']==before['collaboration']['authorizations']
 assert after_speech['outputs']['pptx'] is None
 reread=store.read_object_json(before['outputs']['pptx'])['file'];assert store.read_object_bytes(reread)==(case/'original.pptx').read_bytes()
 report={'case':case.name,'status':'PASS','fixed_source':'ca0351d2397ba154e9f77363bd0f325629eb0ebd','same_completed_image_task_refs':old_images,'same_original_visual_reviews':old_visual_reviews,'visual_refs_and_applicable_reviews':visuals,'current_preproduction_pass':True,'same_quality_profile_request_authorizations':True,'original_notes_full_readback':old_notes,'final_notes_full_readback':final_notes,'old_actual_pptx_immutable':True,'old_current_output_invalidated_by_speech':True,'desktop':'NOT_RUN','human':'NOT_RUN','quality_claim':'Only synthetic L1 review/authorization and actual native file engineering'}
 (case/'supplemental-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');records.append(report)
(root/'fixed-installed-final-audit.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'case':r['case'],'status':r['status']} for r in records]))
