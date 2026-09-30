"""Read/plan probes on temporary synthetic projects; no real Host/model calls."""
import copy
import importlib.util
import json
import tempfile
import urllib.request
from pathlib import Path

from jsonschema import Draft202012Validator
from deck_master import changes, editing, service, workbench
from deck_master.samples import create_sample
from deck_master.store import Store
from deck_master.web import WorkbenchServer

ROOT = Path(__file__).resolve().parents[4]

def run():
    rows = []
    with tempfile.TemporaryDirectory(prefix='dm-design-gaps-') as tmp:
        project = Path(tmp) / 'modern'
        create_sample(project, page_count=2, readonly=False)
        store = Store(project)
        doc = store.load_document()
        entry = doc['pages'][0]
        intent = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'],
                  'base_revision': doc['revision_id'], 'intent': 'content',
                  'instruction': 'Improve the title; keep current until explicitly adopted.',
                  'annotation_refs': [], 'max_calls': 0, 'mode': 'trial',
                  'targets': [{'page_id': entry['page_id'], 'page_ref': entry['page'],
                               'layer': 'content', 'artifact_ref': entry['page']}]}
        try:
            changes.plan(project, input=intent)
        except Exception as error:
            assert 'trial supports original-image and SVG candidates' in str(error)
            rows.append({'id': 'P01', 'finding': 'content_trial_rejected', 'observed': str(error),
                         'current_unchanged': store.load_document() == doc})
        else:
            raise AssertionError('Content trial behavior changed: re-evaluate gap')
        summary = workbench.workbench_summary(project)
        assert all(p['attention'] == {'status': 'not_recorded'} for p in summary['pages'])
        assert 'prompt' not in summary['pages'][0]['stages']
        rows.append({'id': 'P02', 'finding': 'attention_not_recorded_and_no_prompt_summary',
                     'stage_keys': list(summary['pages'][0]['stages']), 'attention': summary['pages'][0]['attention']})
        # Reuse the existing, explicitly synthetic SVG-result helper.
        import sys
        sys.path.insert(0, str(ROOT / 'tests/rebuild'))  # audit fixtures only
        spec = importlib.util.spec_from_file_location('candidate_fixture', ROOT / 'tests/rebuild/test_candidates.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        cid = helper.candidate(store)
        summary = workbench.workbench_summary(project)
        schema = json.loads((ROOT/'src/deck_master/resources/contracts/workbench-summary.v1.schema.json').read_text())
        errors = [{'path': '/'.join(map(str, e.absolute_path)), 'message': e.message}
                  for e in Draft202012Validator(schema).iter_errors(summary)]
        assert errors and all(e['path'].startswith('candidates') for e in errors)
        rows.append({'id': 'P03', 'finding': 'candidate_summary_violates_active_schema',
                     'candidate_id': cid, 'errors': errors})
        legacy = Path(tmp)/'legacy-core'
        page = {'schema_version': 'deck_page_package.v2', 'page_id': 'one',
                'customer_visible': {'title': 'Old title', 'body_blocks': []},
                'visual_spec': {'intent': 'Synthetic audit', 'reference_mode': 'new_design'}}
        service.create(legacy, brief='Synthetic compatibility audit', draft={'pages': [page]})
        ls = Store(legacy); before = ls.load_document(); old = before['revision_id']
        edit = copy.deepcopy(page); edit['customer_visible']['title'] = 'New title'
        editing.edit_page(legacy, page=edit, base_revision=old,
                          page_hash=before['pages'][0]['page']['sha256'], operation_id='audit-fixed-revision')
        server = WorkbenchServer(legacy)
        try:
            url = server.start().rstrip('/')
            def read(path):
                with urllib.request.urlopen(url+path, timeout=5) as response:
                    return json.load(response)
            historical = read('/api/view?revision='+old)
            assert historical['revision_id'] == old
            rows.append({'id': 'P04', 'finding': 'fixed_revision_HTTP_now_supported', 'revision_matches': True})
            health = read('/api/health'); info = read('/api/project')
            assert 'candidates.v1' in health['ui_capabilities'] and info['project_format'] != 'workbench.v3'
            current = ls.load_document(); target = current['pages'][0]
            old_intent = {**intent, 'project_id':current['project_id'], 'base_revision':current['revision_id'],
                          'mode':'auto', 'targets':[{'page_id':'one','page_ref':target['page'],
                                                   'layer':'content','artifact_ref':target['page']}]}
            try:
                changes.plan(legacy, input=old_intent)
            except Exception as error:
                assert 'explicit workbench.v3' in str(error)
                rows.append({'id':'P05','finding':'server_capability_not_project_action_availability',
                             'project_format':info['project_format'],'advertised_candidates':True,'refusal':str(error)})
            else:
                raise AssertionError('Legacy project behavior changed')
        finally:
            server.stop()
    return {'source_base':'66da345c84de48933a76de577114f08dcebf4f0e', 'synthetic':True,
            'real_host_calls':0, 'production_acceptance':False, 'temporary_projects_cleaned':True, 'observations':rows}

if __name__ == '__main__':
    import sys
    value = run()
    Path(sys.argv[1]).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'observations':len(value['observations']),'all_assertions_passed':True}))
