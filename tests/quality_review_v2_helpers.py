"""Synthetic canonical v2 results; never used as actual acceptance evidence."""
import copy, hashlib, json
from quality.external_review import REVIEW_DIMENSIONS_V2

def canonical_report(root=None, page_ids=None):
    page_ids=page_ids or ['P001','P002']
    if root is not None:
        from quality.external_review import prepare_quality_review_v2
        task=prepare_quality_review_v2(root,scope='semantic',required_page_ids=page_ids)
        based=task['based_on']; action=task['review_action_id']; run_id=task['run_id'];mode=task['run_mode']
    else:
        refs=[{'ref':f'page_packages/{p}.json','sha256':'a'*64} for p in page_ids]
        based={'input_refs':refs,'input_fingerprint':hashlib.sha256(json.dumps(refs,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
        action='review-1';run_id='run-q';mode='production'
    return {'schema_version':'deck_external_quality_review.v2','run_id':run_id,'run_mode':mode,'based_on':based,'review_action_id':action,'scope':'semantic','review_kind':'independent','reviewer_session_id':'session-reviewer','producer_session_id':'session-producer','host_execution_ref':'controlled-unit-host-call','reviewed_inputs':copy.deepcopy(based['input_refs']),'coverage':{'required_page_ids':page_ids,'reviewed_page_ids':page_ids.copy(),'claim_refs':[],'skipped':[]},'dimension_scores':{d:4 for d in REVIEW_DIMENSIONS_V2},'observations':[{'dimension':d,'object_refs':page_ids.copy(),'verdict':'pass','rationale':f'Controlled observation for {d}','evidence_refs':[],'check_method':'controlled structural test'} for d in REVIEW_DIMENSIONS_V2],'findings':[],'summary':{'reported_status':'pass','conclusion':'Controlled test only'}}


def canonical_gate(root):
    from quality.external_review import import_external_review
    (root/'page_packages').mkdir(exist_ok=True)
    if not any(p.name!='index.json' for p in (root/'page_packages').glob('*.json')):
        (root/'page_packages/P001.json').write_text('{"page_id":"P001"}')
    if not (root/'request.json').exists():
        (root/'request.json').write_text(json.dumps({'run_id':root.name,'run_mode':'production'}))
    pages=sorted(p.stem for p in (root/'page_packages').glob('*.json') if p.name!='index.json')
    result=import_external_review(root,canonical_report(root,pages),replace=True)
    return json.loads((root/'quality_reports'/result['gate_report']).read_text())
