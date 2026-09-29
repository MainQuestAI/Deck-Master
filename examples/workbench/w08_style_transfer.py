"""Reproduce style trial/adoption/expansion using explicit synthetic tool events.

No model is called. This proves request scope, frozen identity, recovery and
invalidation only; actual visual style improvement requires separate Host evidence.
All project/operation/task/request/candidate IDs come from service responses.
"""
from __future__ import annotations
import argparse
import copy
import json
import uuid
from pathlib import Path

from deck_master import changes, generation, service, styles
from w07_synthetic import EXECUTION, SyntheticW07


class SyntheticStyle(SyntheticW07):
    def start(self, task):
        return service.task_start(self.project, task_id=task['task_id'], execution_ref=EXECUTION,
                                  supported_protocols=['generation.v1', 'changes.v1'], capabilities=task['required_capabilities'])


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    flow = SyntheticStyle(args.out); store = flow.store; doc = store.load_document(); original = copy.deepcopy(doc['pages'])
    evidence = args.out / 'evidence'; evidence.mkdir()
    def save(name, data):
        (evidence / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        return data
    value = {'schema_version': 'style_input.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
             'reference': {'page_id': 'p01', 'revision_id': doc['revision_id'], 'artifact_ref': doc['pages'][0]['blueprint'], 'role': 'reference'},
             'target_page_ids': ['p02', 'p03'], 'instruction': '借用配色与文字层级，保持目标页标题、事实、数字与构图。'}
    save('input', value); proposal = save('proposal', styles.propose(flow.project, input=value))
    op = str(uuid.uuid4()); recipe = save('confirm', styles.confirm(flow.project, proposal_id=proposal['proposal_id'],
           base_revision=doc['revision_id'], operation_id=op))['operation_result']
    assert store.load_document()['pages'] == original and store.load_document()['tasks'] == doc['tasks']
    def trial(page_id, adopted=None):
        payload = {'recipe_id': recipe['recipe_id'], 'page_ids': [page_id], 'max_calls': 1}
        if adopted: payload['adopted_candidate_id'] = adopted
        plan = save(page_id + '-plan', styles.plan(flow.project, input=payload))
        commit = save(page_id + '-dispatch', changes.commit(flow.project, plan_id=plan['plan_id'], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4())))['operation_result']
        save(page_id + '-handoff', changes.handoff(flow.project, change_id=commit['change_id']))
        task = flow.task(commit['task_ids'][0]); prepared = generation.prepared_input(store, store.load_document(), task)
        assert prepared['style_recipe_ref'] == recipe['recipe_ref'] and prepared['constraints']['preserve_target_content']
        before = copy.deepcopy(store.load_document()['pages']); result = save(page_id + '-returned', flow.image(task))
        assert store.load_document()['pages'] == before
        cid = result['candidate_ids'][0]; save(page_id + '-adopt', flow.adopt([cid]))
        return cid, flow.task(task['task_id'])
    first, task1 = trial('p02'); adopted_first = copy.deepcopy(store.load_document()['pages'][1])
    second, task2 = trial('p03', first); end = store.load_document()
    assert end['pages'][0] == original[0] and end['pages'][1] == adopted_first
    assert [p['page'] for p in end['pages']] == [p['page'] for p in original]
    assert all(end['pages'][i]['svg'] is None for i in (1, 2))
    replay = styles.confirm(flow.project, proposal_id=proposal['proposal_id'], base_revision=doc['revision_id'], operation_id=op)
    assert replay['operation_result'] == recipe
    counts = [len(t['call_allowances']) for t in (task1, task2)]; assert counts == [1, 1]
    result = {'synthetic': True, 'actual_model_calls': 0, 'synthetic_observed_calls': sum(counts),
              'recipe_id': recipe['recipe_id'], 'candidate_ids': [first, second],
              'checks': ['proposal_and_confirmation_do_not_dispatch', 'default_excludes_composition',
                         'fixed_recipe_frozen_into_requests', 'trial_return_preserves_current_pages',
                         'adopted_first_candidate_gates_explicit_expansion', 'reference_page_unchanged',
                         'first_adopted_page_unchanged_by_expansion', 'all_target_content_refs_unchanged',
                         'only_adopted_target_downstream_invalidated', 'confirmation_replay_after_later_writes',
                         'one_bounded_call_per_selected_page'],
              'visual_effect_evaluation': 'not_performed_synthetic_protocol_only'}
    (args.out / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n'); print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
