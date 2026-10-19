"""Regression for PR124's stale completion template and blanket PASS risk."""
import copy
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUMMARIZE = runpy.run_path(str(ROOT / 'tools/summarize_iteration_ledger.py'))['summarize']
LEDGER = ROOT / 'docs/reports/rc4/iteration-20261019/execution-ledger.json'


def test_current_unique_ledger_has_no_stale_completion_template():
    ledger = json.loads(LEDGER.read_text())
    derived = SUMMARIZE(ledger)
    assert len(ledger['acceptance']) == 70
    assert ledger['status_counts'] == derived['status_counts']
    assert ledger['completion'] == derived['completion']
    assert ledger['completion']['summary']


@pytest.mark.parametrize('status', ['FAIL', 'BLOCKED', 'NOT_RUN'])
def test_summary_retains_actual_open_adjudication_and_evidence(status):
    ledger = json.loads(LEDGER.read_text())
    ledger['acceptance'][0].update(status=status, observed_result='actual unresolved counterexample')
    before = copy.deepcopy(ledger)
    result = SUMMARIZE(ledger, ci_status='PASS')
    assert ledger == before
    assert result['acceptance'] == before['acceptance']
    assert result['deferred_observations'] == before['deferred_observations']
    assert result['acceptance'][0]['ac_id'] in result['completion']['unresolved_ac_ids']
    assert result['completion']['engineering_candidate'] != 'PASS'


def test_passing_components_do_not_invent_final_ci_or_user_acceptance():
    ledger = json.loads(LEDGER.read_text())
    for row in ledger['acceptance']:
        row['status'] = 'PASS'  # Synthetic all-met control, never a product adjudication.
    ledger['candidate'].update(build_runtime_and_skill_bytes_match_candidate=True, fresh_build_required=False,
                               installed_instances=[{'status': 'PASS'}])
    pending = SUMMARIZE(ledger, ci_status='in_progress')
    assert pending['completion']['unresolved_ac_ids'] == []
    assert pending['completion']['engineering_candidate'] == 'BLOCKED'
    assert pending['completion']['remaining_engineering_gates'] == ['final_exact_head_ci']
    complete = SUMMARIZE(ledger, ci_status='PASS')
    assert complete['completion']['engineering_candidate'] == 'PASS'
    assert complete['completion']['real_acceptance'] == 'DEFERRED_TO_USER_LOCAL_VALIDATION'
    assert complete['deferred_observations'] == ledger['deferred_observations']
