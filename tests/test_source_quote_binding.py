import hashlib
import pytest
from quality.semantic_checks import find_unsupported_numbers


def case(tmp_path):
    claim='试点效率提升45%'
    source=tmp_path/'original.txt';source.write_text('原始试点记录\n'+claim+'\n其他范围说明',encoding='utf-8')
    evidence={'evidence_id':'E1','statement':claim,'review_status':'supported','review_ref':'review/E1.json','publication_status':'safe_to_use','quote':claim,'quote_sha256':hashlib.sha256(claim.encode()).hexdigest(),'source_position':{'unit_type':'line','start':2,'end':2,'detail':''},'unit':'%','period':'pilot'}
    context={'sources':[{'source_id':'S1','path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'evidence_candidates':[evidence]}]}
    package={'page_id':'P001','customer_visible':{'title':claim},'evidence_bindings':['E1'],'citations':[{'claim_text':claim,'evidence_id':'E1','unit':'%','period':'pilot'}]}
    return package,context,evidence


@pytest.mark.parametrize('mutation',['position','quote','source_hash','generated_source'])
def test_source_location_and_bytes_cannot_be_self_certified(tmp_path,mutation):
    package,context,e=case(tmp_path)
    assert not find_unsupported_numbers([package],context_manifest=context)
    if mutation=='position':e['source_position'].update(start=3,end=3)
    elif mutation=='quote':
        e['quote']='生成内容声称效率提升45%';e['quote_sha256']=hashlib.sha256(e['quote'].encode()).hexdigest()
    elif mutation=='source_hash':context['sources'][0]['sha256']='0'*64
    else:context['sources'][0]['origin_type']='generated_page'
    assert find_unsupported_numbers([package],context_manifest=context)


def test_non_numeric_claim_cannot_use_generated_page_as_source(tmp_path):
    from quality.evidence_gate import evaluate_evidence_gate
    package,context,e=case(tmp_path)
    package['customer_visible']['title']='库存服务负责预占'
    context['sources'][0]['origin_type']='generated_page'
    gate=evaluate_evidence_gate('r',{}, {},packages=[package],context_manifest=context)
    assert gate['blocks_delivery']
    assert any(f.get('check')=='source_span_mismatch' for f in gate['findings'])


def test_source_qualified_reference_disambiguates_identical_local_ids(tmp_path):
    from copy import deepcopy
    package,context,e=case(tmp_path)
    other=deepcopy(context['sources'][0]);other['source_id']='S2'
    context['sources'].append(other)
    assert find_unsupported_numbers([package],context_manifest=context)
    package['evidence_bindings']=['S1::E1'];package['citations'][0]['evidence_id']='S1::E1'
    assert not find_unsupported_numbers([package],context_manifest=context)
