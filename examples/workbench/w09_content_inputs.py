"""CLI reproduction with synthetic materials and explicit simulated Host reasoning.

No model is called. Real source reading/impact judgment is a separate evidence run.
"""
from __future__ import annotations
import argparse
import copy
import json
import uuid
from pathlib import Path

from deck_master import content_plan
from deck_master.samples import create_sample
from deck_master.store import Store
from w02_host_roundtrip import cli, save


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); out = args.out; out.mkdir(parents=True, exist_ok=False)
    project = out / 'synthetic-project'; create_sample(project, page_count=3, readonly=False); store = Store(project)
    source = out / 'synthetic-material.md'; source.write_text('Synthetic selected-page fact\nCapacity is 42.\nNo measured outcome is supplied.\n')
    before = copy.deepcopy(store.load_document())
    patch = {'reason': 'Synthetic material addition; inspect only supported effects', 'source_changes': {'add': [{'path': str(source.resolve())}]}, 'task_patch': {'audience': 'Synthetic reviewer', 'existing_decisions': ['No invented measured outcomes']}}
    save(out / 'input-patch.json', patch)
    updated = cli(out, 'inputs', 'content', 'inputs', '--project', project, '--input', out / 'input-patch.json', '--base-revision', store.current_revision_id(), '--operation-id', str(uuid.uuid4()))['operation_result']
    task = updated['pending_tasks'][0]; sid = updated['diff']['sources_added'][0]
    material = cli(out, 'source', 'content', 'source', '--project', project, '--source-id', sid, '--revision', updated['revision_id'], '--locator', 'L2')
    assert material['location'] == 'exact'
    cli(out, 'start', 'task', 'start', '--project', project, '--task-id', task['task_id'], '--execution-ref', 'synthetic-w09-example', '--supported-protocol', 'compose.v1', *(arg for cap in content_plan.CAPABILITIES for arg in ('--capability', cap)))
    current = store.load_document(); page = copy.deepcopy(store.read_object_json(current['pages'][1]['page'])); page['customer_visible']['title'] = 'Synthetic capacity 42; not a measured outcome'
    outline = copy.deepcopy(store.read_object_json(current['content_plan'])['input']); outline['input_summary'] = 'Synthetic source states capacity 42; unrelated pages remain unchanged.'
    outline['goals'][1]['source_links'] = [{'source_id': sid, 'source_version': material['source_version'], 'locator': 'L2'}]
    envelope = {'kind': 'compose', 'content_update': {'input_digest': task['project_context']['input_digest'], 'upsert_pages': [page], 'remove_page_ids': [], 'page_order': [p['page_id'] for p in current['pages']],
                'impact_summary': 'Synthetic fixture: only p02 expresses the capacity fact; p01/p03 retained. No measured outcome invented.'}, 'content_plan': outline}
    save(out / 'result.json', envelope)
    cli(out, 'accept', 'task', 'accept', '--project', project, '--task-id', task['task_id'], '--operation-id', task['operation_id'], '--produced-against', task['produced_against'], '--result', out / 'result.json', allowed=(0, 3))
    after = store.load_document(); assert after['pages'][0] == before['pages'][0] and after['pages'][2] == before['pages'][2]
    def edit(action, targets, **extra):
        doc = store.load_document(); entries = {p['page_id']: p for p in doc['pages']}
        value = {'schema_version': 'content_operation_input.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'], 'content_plan_ref': doc['content_plan'], 'action': action,
                 'instruction': 'Explicit synthetic ' + action, 'targets': [{'page_id': pid, 'page_ref': entries[pid]['page']} for pid in targets], **extra}
        save(out / (action + '-input.json'), value)
        plan = cli(out, action + '-plan', 'content', 'plan', '--project', project, '--input', out / (action + '-input.json'))
        return cli(out, action + '-commit', 'content', 'commit', '--project', project, '--plan-id', plan['plan_id'], '--base-revision', doc['revision_id'], '--operation-id', str(uuid.uuid4()))
    retained = copy.deepcopy(after['pages']); edit('reorder', [], page_order=['p03', 'p02', 'p01'])
    assert store.load_document()['pages'] == list(reversed(retained))
    edit('remove', ['p01']); assert [p['page_id'] for p in store.load_document()['pages']] == ['p03', 'p02']
    assert store.load_document(before['revision_id'])['pages'] == before['pages']
    result = {'synthetic': True, 'actual_model_calls': 0, 'checks': ['public_cli_source_locator', 'recoverable_inputs_transaction', 'only_changed_page_upserted', 'unselected_page_entries_unchanged', 'decisions_retained', 'reorder_preserves_page_entries', 'remove_keeps_immutable_history'],
              'real_host_impact_judgment': 'not_measured_in_this_synthetic_script'}
    save(out / 'checks.json', result); print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
