"""Observe the shared CLI/HTTP adapter's §12 missing-reviewer mapping."""
import json
from pathlib import Path
from deck_master.collaboration_api import invoke
OUT=Path(__file__).resolve().parent
source=OUT/'external-gap-source.txt'
source.write_text('Explicit synthetic manuscript for read-only packet generation.\n')
payload={'source':str(source),'scope':{'subject':'external_artifact','page_ids':[],
 'page_manifest_ref':None,'external_artifact_ref':None,'layers':['review'],
 'allow_page_membership_change':False,'allow_page_order_change':False,'purpose':'review'},'persistence':'none'}
response,http,exit_code=invoke(None,'review.evaluate',payload)
result={'input':payload,'response':response,'http_status':http,'cli_exit':exit_code,
 'has_readable_report':bool((response.get('result') or {}).get('external_report'))}
(OUT/'probe-external-gap-status-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':response['status'],'http_status':http,'cli_exit':exit_code,'has_readable_report':result['has_readable_report']}))
