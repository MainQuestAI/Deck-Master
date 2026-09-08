from quality.evidence_gate import evaluate_evidence_gate

def test_cross_representation_period_and_unit_conflicts_block_gate():
 packages=[{'page_id':'P006','citations':[{'metric_id':'fulfilment','representation':'narrative','claim_text':'试点履约时长','unit':'小时','period':'2026-08'}]}, {'page_id':'P007','citations':[{'metric_id':'fulfilment','representation':'chart','claim_text':'试点履约时长','unit':'天','period':'2026-09'}]}]
 result=evaluate_evidence_gate('metric-run',{}, {},packages=packages)
 assert result['blocks_delivery']
 assert any(f.get('check')=='metric_scope_conflict' and f['severity']=='P1' for f in result['findings'])
 packages[1]['citations'][0].update(unit='小时',period='2026-08')
 assert not any(f.get('check')=='metric_scope_conflict' for f in evaluate_evidence_gate('metric-run',{}, {},packages=packages)['findings'])
