from pathlib import Path
import sys,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from quality.semantic_checks import find_unsupported_numbers
from quality.evidence_gate import evaluate_evidence_gate

def data():
 text='审批周期可缩短45%。';quote='试点同口径观测显示审批周期可缩短45%。'
 e=dict(evidence_id='e1',statement=text,unit='%',period='pilot',review_status='supported',review_ref='review/e1.json',quote=quote,quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),source_position={'unit_type':'paragraph','locator':'p1'},publication_status='safe_to_use')
 p=dict(page_id='P001',evidence_bindings=['e1'],customer_visible={'title':'方案','body_blocks':[{'text':text}]},citations=[dict(claim_text=text,evidence_id='e1',unit='%',period='pilot')])
 return p,{'sources':[{'source_id':'s1','evidence_candidates':[e]}]}

def test_exact_reviewed_claim_support_is_accepted():
 p,c=data();assert find_unsupported_numbers([p],context_manifest=c)==[]

def test_same_numeric_string_without_supporting_statement_is_blocked():
 p,c=data();c['sources'][0]['evidence_candidates'][0]['statement']='45%是库存盘点抽样比例。'
 assert find_unsupported_numbers([p],context_manifest=c)

def test_matching_source_id_or_design_basis_is_not_numeric_support():
 p,c=data();p['citations']=[];p['evidence_bindings']=['s1'];p['internal_only']={'design_basis_ref':'solution_model#capability'}
 assert find_unsupported_numbers([p],context_manifest=c)

def test_unit_period_and_quote_integrity_are_required():
 for key,value in [('unit','天'),('period','last-year'),('review_status','unreviewed'),('quote_sha256','0'*64)]:
  p,c=data();c['sources'][0]['evidence_candidates'][0][key]=value
  assert find_unsupported_numbers([p],context_manifest=c),key

def test_one_supported_claim_does_not_exempt_other_numbers_or_title():
 p,c=data();p['customer_visible']['title']='成本降低60%';assert any(f['value']=='60%' for f in find_unsupported_numbers([p],context_manifest=c))

def test_numeric_finding_blocks_formal_evidence_gate():
 p,c=data();p['citations']=[]
 gate=evaluate_evidence_gate('r',{'claims':[]},{'tasks':[]},packages=[p],context_manifest=c)
 assert gate['blocks_delivery'] and any(f['dimension']=='numeric_evidence' for f in gate['findings'])
