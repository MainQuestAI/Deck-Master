"""W05 fixed text/production proofs. All reports and images here are synthetic."""
import copy
import json

import pytest

from deck_master import editing, service, text_ranges, ui_journal, workbench
from deck_master.models import ModelError, canonical_json_bytes, sha256_bytes
from deck_master.pipeline import artifact
from deck_master.production import project_prompt
from deck_master.text_sources import prompt_sections
from deck_master.web import WorkbenchServer
from test_workbench_reads import make_project, mixed_project, commit
from test_workbench_services import http, auth
from test_generation_protocol import flow, start, freeze, begin, settle, accept

TEXT = 'A🙂e\u0301\r\n中'


def selected(source, start=1, end=4):
    return {'schema_version': 'text_range.v1', **{k: source[k] for k in ('ref', 'locator', 'text_sha256')},
            'start': start, 'end': end, 'excerpt': source['text'][start:end]}


@pytest.fixture
def text_project(tmp_path):
    project, store = make_project(tmp_path, 2)
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] = TEXT
    editing.edit_page(project, page=page, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='unicode')
    lineage = workbench.page_lineage(project, 'p01')
    source = lineage['text_sources']['content'][0]
    return project, store, lineage, source


def validate_content(fixture, selection=None, **overrides):
    project, _, lineage, source = fixture
    args = {'page_id': 'p01', 'layer': 'content', 'revision_id': lineage['revision_id'], 'selection': selection or selected(source)}
    args.update(overrides)
    return text_ranges.validate(project, **args)


def test_exact_unicode_crlf_and_read_only_snapshot(text_project):
    project, store, lineage, source = text_project
    before = {str(p): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()}
    result = validate_content(text_project)
    assert result['code_point_length'] == 7
    assert result['selection']['excerpt'] == '🙂e\u0301'
    assert source['text_sha256'] == sha256_bytes(TEXT.encode('utf-8'))
    assert validate_content(text_project, selected(source, 4, 6))['selection']['excerpt'] == '\r\n'
    assert before == {str(p): p.read_bytes() for p in store.deck_root.rglob('*') if p.is_file()}
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    page['customer_visible']['title'] = 'changed'
    editing.edit_page(project, page=page, base_revision=doc['revision_id'], page_hash=doc['pages'][0]['page']['sha256'], operation_id='later')
    assert validate_content(text_project)['selection'] == result['selection']
    with pytest.raises(text_ranges.TextRangeError):
        validate_content(text_project, revision_id=store.current_revision_id())
    assert workbench.page_lineage(project, 'p01', revision=lineage['revision_id'])['text_sources']['content'] == lineage['text_sources']['content']


@pytest.mark.parametrize('change', [
    {'text_sha256': '0' * 64}, {'start': 2, 'end': 5}, {'end': 50}, {'start': 4, 'end': 1},
    {'excerpt': '🙂é'}, {'locator': '/internal_only'}, {'start': True}, {'locator': '/customer_visible/body_blocks'},
])
def test_text_range_rejects_normalized_or_wrong_binding(text_project, change):
    source = text_project[3]
    with pytest.raises((ModelError, text_ranges.TextRangeError)):
        validate_content(text_project, {**selected(source), **change})


@pytest.mark.parametrize('overrides', [{'page_id': 'p02'}, {'layer': 'original_image'}, {'revision_id': None}, {'revision_id': ''}])
def test_text_range_requires_page_text_and_fixed_version(text_project, overrides):
    with pytest.raises((ModelError, text_ranges.TextRangeError)):
        validate_content(text_project, **overrides)


def test_http_text_range_auth_errors_and_cli_lineage_match(text_project, capsys):
    from deck_master.cli import main
    project, store, lineage, source = text_project
    server = WorkbenchServer(project)
    url = server.start()
    try:
        data = {'page_id': 'p01', 'layer': 'content', 'revision_id': lineage['revision_id'], 'selection': selected(source)}
        assert http(url, '/api/text-ranges/validate', data)[0] == 403
        headers = auth(url)
        assert http(url, '/api/text-ranges/validate', data, headers=headers)[1] == validate_content(text_project)
        assert http(url, '/api/text-ranges/validate', data, headers={**headers, 'Origin': 'https://foreign.invalid'})[0] == 403
        code, error = http(url, '/api/text-ranges/validate', {**data, 'layer': 'svg'}, headers=headers)
        assert code == 422 and error['error']['code'] == 'text_range_invalid'
        assert str(project) not in json.dumps(error)
        assert main(['view', '--project', str(project), '--page-id', 'p01', '--lineage', '--revision', lineage['revision_id'], '--json']) == 0
        cli = json.loads(capsys.readouterr().out)
        assert cli == http(url, '/api/pages/p01/lineage?revision=' + lineage['revision_id'])[1]
    finally:
        server.stop()


def test_prepared_segments_only_with_exact_recorded_projection(tmp_path):
    project, store = make_project(tmp_path, 1)
    doc = store.load_document()
    page = store.read_object_json(doc['pages'][0]['page'])
    request = project_prompt(page, doc['design_context'], [])
    proof = prompt_sections(request)
    assert proof['state'] == 'verified_core_projection'
    assert ''.join(request['prompt'][s['start']:s['end']] for s in proof['segments']) == request['prompt']
    for broken in ({'projection_sha256': '0' * 64}, {'prompt': 'arbitrary old prose'}, {'prompt': request['prompt'] + '\n'}, {'schema_version': 'other'}):
        assert prompt_sections({**request, **broken}) == {'state': 'unstructured', 'segments': []}
    # A familiar-looking header alone never proves a recorded structured request.
    assert prompt_sections({'prompt': request['prompt']})['state'] == 'unstructured'


def test_new_generation_request_exact_text_can_be_selected_and_drafted(tmp_path):
    from deck_master import generation
    from deck_master.store import Store
    project = tmp_path / 'generation'
    service.create(project, brief='synthetic', draft={'pages': [{'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
                   'customer_visible': {'title': 'synthetic', 'body_blocks': []},
                   'visual_spec': {'intent': 'test', 'reference_mode': 'new_design'}}]}, project_format='workbench.v3')
    task = service.continue_project(project)['pending_tasks'][0]
    service.task_start(project, task_id=task['task_id'], execution_ref='test:synthetic', supported_protocols=[generation.PROTOCOL], capabilities=generation.CAPABILITIES)
    store = Store(project)
    generation.freeze(project, task_id=task['task_id'], input=task['generation_input'], base_revision=store.current_revision_id(), operation_id='freeze')
    lineage = workbench.page_lineage(project, 'p1')
    source = next(s for s in lineage['text_sources']['prepared_prompt'] if s['locator'] == '/input/prompt')
    assert text_ranges.validate(project, page_id='p1', layer='prepared_prompt', revision_id=lineage['revision_id'], selection=selected(source))['status'] == 'valid'
    info = ui_journal.project_info(project)
    draft = {'schema_version': 'ui_draft.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
             'draft_id': 'prompt-draft', 'target': {'scope': 'page', 'page_id': 'p1', 'layer': 'prepared_prompt'},
             'base_revision': lineage['revision_id'], 'base_ref': source['ref'], 'content': {'text': 'local idea'}, 'pending': None}
    before = store.current_revision_id()
    assert ui_journal.save(project, draft=draft)['status'] == 'saved'
    assert store.current_revision_id() == before


def production_fixture(tmp_path):
    project, store = mixed_project(tmp_path)
    doc = copy.deepcopy(store.load_document())
    entry = doc['pages'][0]
    deps = [{'kind': 'svg', 'identity': e['page_id'], 'sha256': e['svg']['sha256']} for e in doc['pages'] if e.get('svg')]
    # Limit to the compiled synthetic page to establish exact whole-deck input scope.
    doc['pages'] = [entry]
    ppt = tmp_path / 'synthetic.pptx'; ppt.write_bytes(b'SYNTHETIC metadata test; not a PPT file')
    report_file = tmp_path / 'report.json'
    report_file.write_text(json.dumps({'status': 'pass', 'pages': [{'page_id': 'p01', 'text_runs': 7, 'native_shapes': 9}], 'findings': [{'page_id': 'p01', 'code': 'synthetic'}, {'page_id': 'p02', 'code': 'other'}]}))
    trace_file = tmp_path / 'trace.json'
    trace_file.write_text(json.dumps({'pages': [{'page_id': 'p01', 'sha256': store.read_object_json(entry['svg'])['file']['sha256'], 'shapes': [{'kind': 'image'}, {'kind': 'text'}]}], 'fonts': {'TestFont': {'sha256': 'a' * 64}}, 'diagnostics': []}))
    doc['outputs'] = {'pptx': artifact(store, ppt, 'pptx', dependencies=deps), 'trace': artifact(store, trace_file, 'object_trace', dependencies=deps), 'render_report': artifact(store, report_file, 'render_report', dependencies=deps)}
    return project, store, commit(store, doc, 'synthetic-production')


def test_production_counts_and_fonts_are_source_bound_not_overclaimed(tmp_path):
    project, store, doc = production_fixture(tmp_path)
    result = workbench.page_lineage(project, 'p01')['production']
    assert result['revision_id'] == doc['revision_id']
    assert result['pptx']['editability'] == 'editable_shapes_and_text'
    assert result['pptx']['applicability'] == 'current'
    assert result['render_report']['text_runs'] == 7 and result['render_report']['native_shapes'] == 9
    assert result['render_report']['findings'] == [{'page_id': 'p01', 'code': 'synthetic'}]
    assert result['render_report']['pptx_relation'] == 'shared_inputs'
    assert result['object_trace']['svg_input_image_elements'] == 1
    assert result['object_trace']['compiler_fonts'] == [{'family_key': 'TestFont', 'sha256': 'a' * 64}]
    assert result['font_substitution'] == 'not_recorded' and result['ppt_raster_ratio'] is None
    assert result['evaluations']['desktop_editing']['status'] == 'not_evaluated'
    assert result['evaluations']['professional_use']['status'] == 'not_evaluated'
    assert result['ocr_text_layer'] == 'not_recorded'
    older = doc['revision_id']
    doc['pages'][0]['svg'] = None
    commit(store, doc, 'remove-svg')
    newer = workbench.page_lineage(project, 'p01')['production']
    assert newer['pptx']['applicability'] == 'basis_changed'
    assert newer['object_trace']['svg_input_image_elements'] is None
    assert workbench.page_lineage(project, 'p01', revision=older)['production'] == result


def test_absent_and_corrupt_production_are_local_errors(tmp_path):
    project, store, doc = production_fixture(tmp_path)
    report = store.read_object_json(doc['outputs']['render_report'])
    store._resolve_object_path(report['file']['path']).write_bytes(b'corrupt')
    result = workbench.page_lineage(project, 'p01')
    assert result['production']['render_report']['state'] == 'unreadable'
    assert result['production']['render_report']['text_runs'] is None
    assert result['page'] and result['production']['object_trace']['svg_input_image_elements'] == 1
    doc['outputs'] = {'pptx': None, 'trace': None, 'render_report': None}
    commit(store, doc, 'no-output')
    result = workbench.page_lineage(project, 'p01')['production']
    assert result['render_report']['state'] == 'not_recorded' and result['render_report']['text_runs'] is None
    assert result['pptx']['editability'] == 'unknown'
    assert result['object_trace']['svg_input_image_elements'] is None


def test_submitted_prompt_selection_preserves_original_bytes(tmp_path):
    project, store = mixed_project(tmp_path)
    doc = copy.deepcopy(store.load_document())
    entry = doc['pages'][0]
    blueprint = store.read_object_json(entry['blueprint'])
    blueprint['provenance']['submitted_prompt'] = store.put_blob(TEXT.encode('utf-8'), ext='txt')
    entry['blueprint'] = store.put_json_object(blueprint)
    doc = commit(store, doc, 'record-text')
    lineage = workbench.page_lineage(project, 'p01')
    assert lineage['prompts']['submitted']['observer'] == 'host_reported'
    source = lineage['text_sources']['submitted_prompt'][0]
    assert source['text'] == TEXT
    kwargs = {'page_id': 'p01', 'layer': 'submitted_prompt', 'revision_id': doc['revision_id']}
    assert text_ranges.validate(project, selection=selected(source), **kwargs)['status'] == 'valid'
    with pytest.raises(text_ranges.TextRangeError):
        text_ranges.validate(project, selection={**selected(source), 'locator': '/prompt'}, **kwargs)


def test_old_prepared_text_has_its_own_recorded_locator(tmp_path):
    project, store = make_project(tmp_path, 1)
    task = service.continue_project(project)['pending_tasks'][0]
    assert task['kind'] == 'blueprint'
    lineage = workbench.page_lineage(project, 'p01')
    assert lineage['prompts']['prepared']
    source = lineage['text_sources']['prepared_prompt'][0]
    assert source['locator'] == '/prompt'
    assert text_ranges.validate(project, page_id='p01', layer='prepared_prompt', revision_id=lineage['revision_id'], selection=selected(source))['status'] == 'valid'


@pytest.mark.parametrize('kind', ['professional_use', 'desktop_editing'])
def test_reviews_only_describe_recorded_output_subject_and_reviewer(tmp_path, kind):
    project, store, doc = production_fixture(tmp_path)
    review = {'schema_version': 'deck_review.v1', 'review_id': 'synthetic-review', 'kind': kind, 'status': 'pass',
              'subjects': [doc['outputs']['pptx']], 'dependencies': [],
              'reviewer': {'type': 'human_internal', 'id': 'synthetic', 'execution_ref': None, 'independence_confirmed': False},
              'observations': ['Synthetic fixture; no human actually tested this file'], 'findings': [],
              'created_at': '2026-09-28T00:00:00Z', 'replaces': None}
    ref = store.put_json_object(review)
    doc['reviews'] = [ref]
    doc = commit(store, doc, 'synthetic-review')
    record = workbench.page_lineage(project, 'p01')['production']['evaluations'][kind]
    assert record == {'status': 'pass', 'ref': ref, 'reviewer_type': 'human_internal', 'subject': doc['outputs']['pptx']}
    ppt = store.read_object_json(doc['outputs']['pptx']); ppt['artifact_id'] = 'other-output'
    doc['outputs']['pptx'] = store.put_json_object(ppt)
    commit(store, doc, 'different-output')
    assert workbench.page_lineage(project, 'p01')['production']['evaluations'][kind]['status'] == 'not_evaluated'
    store._resolve_object_path(ref['path']).write_bytes(b'broken')
    result = workbench.page_lineage(project, 'p01')['production']
    assert result['unreadable_reviews'] and result['evaluations'][kind]['status'] == 'not_evaluated'


@pytest.mark.parametrize('bad', ['duplicate_page', 'negative', 'non_integer', 'wrong_role', 'different_inputs'])
def test_report_malformed_and_unbound_never_invents_current_counts(tmp_path, bad):
    project, store, doc = production_fixture(tmp_path)
    record = store.read_object_json(doc['outputs']['render_report'])
    payload = store.read_object_json(record['file'])
    if bad == 'duplicate_page':
        payload['pages'].append(payload['pages'][0])
    elif bad == 'negative':
        payload['pages'][0]['text_runs'] = -1
    elif bad == 'non_integer':
        payload['pages'][0]['native_shapes'] = True
    elif bad == 'wrong_role':
        record['role'] = 'object_trace'
    else:
        record['dependencies'] = []
    record['file'] = store.put_blob(canonical_json_bytes(payload), ext='json')
    doc['outputs']['render_report'] = store.put_json_object(record)
    commit(store, doc, 'malformed-report')
    report = workbench.page_lineage(project, 'p01')['production']['render_report']
    if bad == 'different_inputs':
        assert report['text_runs'] == 7 and report['pptx_relation'] == 'unknown'
    else:
        assert report['state'] == 'unreadable' and report['text_runs'] is None and report['native_shapes'] is None


def test_adopted_request_and_attempt_are_explicit_not_latest_guess(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    other = freeze(flow, prompt='different request on the same page')
    attempt = begin(flow, frozen)
    locator, raw = native()
    settle(flow, attempt, locator)
    accept(flow, frozen, attempt, raw)
    result = workbench.page_lineage(project, 'p1')['generation']
    assert result['adopted_request_ref'] == next(r['ref'] for r in result['requests'] if r['request_id'] == frozen['request_id'])
    assert result['adopted_request_ref'] != next(r['ref'] for r in result['requests'] if r['request_id'] == other['request_id'])
    assert result['adopted_attempt_ref'] == result['attempts'][0]['ref']
    assert result['attempts'][0]['request_ref'] == result['adopted_request_ref']
