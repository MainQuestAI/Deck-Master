"""Synthetic feedback provenance tests; no actual client feedback is fabricated."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from learning.pack import build_learning_pack


def write(root, events):
    p=root/'assets/asset_feedback.jsonl';p.parent.mkdir(exist_ok=True)
    p.write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events))


def event(**payload):
    return {'event_type':'preview_rejected','canonical_slide_id':'slideA','run_id':'syntheticA','reviewed_revision':'rev1','notes':'Synthetic confidential revenue is 123456; do not reuse.', 'payload':payload}


def test_raw_feedback_and_nonreview_events_do_not_make_reusable_cards(tmp_path):
    write(tmp_path,[event(),{**event(), 'event_type':'exported_client'}])
    pack=build_learning_pack(tmp_path)
    assert pack['experience_cards']==[]
    assert '123456' not in json.dumps(pack)


def test_explicit_bounded_abstraction_excludes_customer_notes(tmp_path):
    payload={'adopted_structure':'Show assumptions separately from observed results','reusable_reason':'Avoid implying that an unmeasured benefit is proven','evidence_source_category':'review_feedback','applicable_scope':'Proposal claims lacking measurement','not_applicable_scope':'Measured outcomes with traceable evidence','approval_scope':'workspace_experience'}
    write(tmp_path,[event(**payload)])
    cards=build_learning_pack(tmp_path)['experience_cards']
    assert len(cards)==1 and cards[0]['source_run_ref']=='syntheticA'
    assert cards[0]['reviewed_revision']=='rev1'
    assert cards[0]['user_reason']==payload['reusable_reason']
    assert '123456' not in json.dumps(cards)
    assert cards[0]['not_applicable_scope']==payload['not_applicable_scope']
