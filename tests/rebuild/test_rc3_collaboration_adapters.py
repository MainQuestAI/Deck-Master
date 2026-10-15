"""L1 synthetic public SDK/CLI/HTTP flows with real CAS and scope gates."""
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import json
import threading
import urllib.error
import urllib.request

import pytest

from deck_master import cli, collaboration_api, content_production, eligibility, models, registry, service
from deck_master.launcher import LauncherHandler
from deck_master.store import Store
from deck_master.web import WorkbenchHandler, _static_dir
from rc3_fixtures import historical_snapshot, public_project, source_snapshot, submit_host_fixture


def scope():
    return {'subject': 'deck', 'page_ids': [], 'page_manifest_ref': None,
            'external_artifact_ref': None, 'layers': ['narrative', 'plan', 'review'],
            'allow_page_membership_change': True, 'allow_page_order_change': False, 'purpose': 'working'}


def instruction(text='Explicit synthetic user instruction', locator='synthetic:adapter'):
    return {'kind': 'host_attested_instruction', 'text': text, 'source_locator': locator}


def request(**over):
    return {'intent': 'content_only', 'content_intent': 'plan_only', 'scope': scope(),
            'instruction_evidence': instruction(), **over}


def new_project(tmp_path):
    return public_project(tmp_path, create_input={'brief': 'Explicit synthetic scope test', 'audience': 'test reader'},
                          request_input=request())['project']


def write(project, action, operation, **body):
    return collaboration_api.invoke(project, action, {'base_revision': Store(project).current_revision_id(),
        'operation_id': operation, **body})


@contextmanager
def http_server(project, *, registry_file=None):
    # Transport-only in-process server: no extra source state/cache/log writes.
    base = LauncherHandler if registry_file is not None else WorkbenchHandler
    handler = type('SyntheticAdapterHandler', (base,), {'store': Store(project), 'static_dir': _static_dir(),
        'write_token': 'explicit-synthetic-session', 'runtime_state': {'identity': 'L1-synthetic-adapter-server'},
        'registry_path': registry_file})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def http(url, path, payload=None):
    headers = {'Origin': url, 'X-Deck-Token': 'explicit-synthetic-session', 'Content-Type': 'application/json'}
    req = urllib.request.Request(url + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_public_create_and_show_have_one_current_request_and_no_grants(tmp_path):
    project = new_project(tmp_path)
    store = Store(project)
    before = source_snapshot(project)
    result, status, code = collaboration_api.invoke(project, 'show')
    assert (status, code) == (200, 0)
    assert result['result']['request']['intent'] == 'content_only'
    assert result['result']['request']['instruction_evidence']['assurance'] == 'host_attested'
    assert result['result']['authorizations'] == []
    assert result['result']['completion']['request_id'] == result['result']['request']['request_id']
    assert models.writer_at_least(store.load_document(), 'rc3.v1')
    assert source_snapshot(project) == before


def test_request_replace_replay_stale_and_same_operation_different_payload(tmp_path):
    project = new_project(tmp_path)
    store = Store(project)
    current = store.load_document()['collaboration']['request']['request_id']
    payload = {'base_revision': store.current_revision_id(), 'operation_id': 'explicit-replace',
               'request': request(replace_request_id=current, instruction_evidence=instruction('Replace with a new planning instruction', 'synthetic:replace'))}
    response, http_status, code = collaboration_api.invoke(project, 'request.replace', payload)
    assert (http_status, code) == (200, 0), response
    revision = store.current_revision_id()
    replay, http_status, code = collaboration_api.invoke(project, 'request.replace', payload)
    assert (http_status, code) == (200, 0) and replay['status'] == 'already_applied'
    assert store.current_revision_id() == revision
    changed = {**payload, 'request': request(replace_request_id=current, content_intent='content_full')}
    rejected, status, code = collaboration_api.invoke(project, 'request.replace', changed)
    assert (status, code) == (409, 5) and rejected['error']['path'] == 'operation_id'
    rejected, status, code = collaboration_api.invoke(project, 'request.start', {**payload, 'operation_id': 'stale-operation'})
    assert (status, code) == (409, 5) and rejected['error']['path'] == 'base_revision'
    assert store.current_revision_id() == revision


def test_grant_pause_resume_and_revoke_use_real_request_and_preserve_scope(tmp_path):
    project = new_project(tmp_path)
    store = Store(project)
    request_id = store.load_document()['collaboration']['request']['request_id']
    authorization = {'mode': 'execute', 'actions': ['content.compose'], 'scope': scope(),
        'max_external_calls': 0, 'max_candidate_count': 0, 'adoption_policy': 'candidate_only',
        'instruction_evidence': instruction('Authorize exactly the content scope')}
    granted, status, code = write(project, 'grant', 'explicit-grant', authorization=authorization)
    assert (status, code) == (200, 0), granted
    authorization_id = granted['result']['authorization_id']
    rejected, status, code = write(project, 'pause', 'wrong-request', request_id='missing-request', reason='Hold', evidence=instruction())
    assert (status, code) == (409, 5), rejected
    paused, status, code = write(project, 'pause', 'explicit-pause', request_id=request_id, reason='User holds work', evidence=instruction())
    assert (status, code) == (200, 0), paused
    assert store.load_document()['collaboration']['request']['paused'] is True
    denied, status, code = collaboration_api.invoke(project, 'eligibility', {'action': 'dispatch.compose', 'targets': scope()})
    assert (status, code) == (200, 0)
    assert denied['result']['allowed'] is False and 'request_paused' in denied['result']['reason_codes']
    resumed, status, code = write(project, 'resume', 'explicit-resume', request_id=request_id, evidence=instruction('Resume same scope'))
    assert (status, code) == (200, 0), resumed
    assert store.load_document()['collaboration']['request']['scope'] == scope()
    revoked, status, code = write(project, 'revoke', 'explicit-revoke', authorization_id=authorization_id,
        reason='Withdraw this authorization', evidence=instruction())
    assert (status, code) == (200, 0), revoked
    assert all(store.read_object_json(ref)['status'] in ('active', 'revoked') for ref in store.load_document()['collaboration']['authorizations'])


@pytest.mark.parametrize('action,body', [
    ('show', {'unknown': True}), ('request.start', {'request': {'unknown': True}}),
    ('decision', {'decision': {'unknown': True}}), ('grant', {'authorization': {'unknown': True}}),
    ('resume', {'scope': scope()}), ('eligibility', {'action': 'dispatch.compose', 'targets': {'unknown': True}}),
])
def test_unknown_arguments_are_rejected_without_any_project_writes(tmp_path, action, body):
    project = new_project(tmp_path)
    before = source_snapshot(project)
    response, status, code = collaboration_api.invoke(project, action, body)
    assert (status, code) == (400, 2), response
    assert source_snapshot(project) == before


@pytest.mark.parametrize('payload', [
    {'adapter_context': {}}, {'request': {'verified_user_events': []}},
    {'request': {'instruction_evidence': {**instruction(), 'assurance': 'verified_user'}}},
])
def test_json_cannot_supply_trusted_transport_or_assurance(tmp_path, payload):
    project = new_project(tmp_path)
    before = source_snapshot(project)
    response, status, code = collaboration_api.invoke(project, 'request.start', payload)
    assert (status, code) == (403, 4), response
    assert source_snapshot(project) == before


@pytest.mark.parametrize('launcher', [False, True])
def test_real_http_binds_url_body_registry_and_fixed_project(tmp_path, launcher):
    project = new_project(tmp_path)
    other = new_project(tmp_path)
    project_id = Store(project).load_document()['project_id']
    other_id = Store(other).load_document()['project_id']
    registry_file = tmp_path / 'registry.json' if launcher else None
    if launcher:
        registry.register(registry_file, project)
    with http_server(project, registry_file=registry_file) as url:
        base = f'/api/projects/{project_id}'
        status, response = http(url, base + '/collaboration')
        assert status == 200 and response['project_id'] == project_id
        status, response = http(url, f'/api/projects/{other_id}/collaboration')
        assert status == 404 and response['error']['path'] == 'project_id'
        before = source_snapshot(project)
        status, response = http(url, base + '/eligibility', {'action': 'dispatch.compose', 'project_id': other_id})
        assert status == 400 and response['error']['path'] == 'project_id'
        status, response = http(url, base + '/eligibility', {'action': 'dispatch.compose', 'targets': {'page_ids': []}})
        assert status == 200
        assert response['result']['artifact_revision_id'] == response['result']['control_revision_id']
        status, response = http(url, base + '/collaboration?unknown=1')
        assert status == 400 and response['error']['path'] == 'query'
        status, response = http(url, base + '/collaboration/request/pause', {'request_id': 'wrong',
            'reason': 'Hold', 'evidence': instruction(), 'base_revision': Store(project).current_revision_id(), 'operation_id': 'http-wrong'})
        assert status == 409 and response['error']['code'] == 'conflict'
        assert source_snapshot(project) == before
        source = tmp_path / 'external.txt'
        source.write_text('HTTP external copy')
        external_scope = {**scope(), 'layers': ['review'], 'allow_page_membership_change': False}
        status, response = http(url, '/api/reviews/evaluate', {'source': str(source), 'scope': external_scope, 'persistence': 'none'})
        assert status == 409 and response['status'] == 'needs_reviewer'
        assert response['error']['code'] == 'needs_reviewer'
        assert response['result']['external_report']['report']['engineering_observations'][0]['text'] == 'HTTP external copy'
        assert source_snapshot(project) == before


def test_cli_missing_input_unknown_action_and_cas_errors_keep_shared_envelope(tmp_path, capsys):
    project = new_project(tmp_path)
    body = tmp_path / 'input.json'
    body.write_text('{invalid json')
    assert cli.main(['collaboration', 'grant', str(project), '--input', str(body)]) == 2
    assert json.loads(capsys.readouterr().err)['schema_version'] == 'collaboration_response.v1'
    body.write_text(json.dumps({'base_revision': 'stale', 'operation_id': 'cli-stale', 'request': request()}))
    assert cli.main(['collaboration', 'request', 'start', str(project), '--input', str(body)]) == 5
    assert json.loads(capsys.readouterr().err)['error']['code'] == 'conflict'
    body.write_text(json.dumps({'targets': {'page_ids': []}}))
    assert cli.main(['eligibility', str(project), '--action', 'dispatch.compose', '--input', str(body)]) == 0
    assert json.loads(capsys.readouterr().out)['result']['action'] == 'dispatch.compose'


def test_migration_describe_apply_and_replay_use_historical_fixture(tmp_path):
    fixture = historical_snapshot(tmp_path, scenario='unmigrated reader and formal migration')
    project = fixture['project']
    before = source_snapshot(project)
    result, status, code = collaboration_api.invoke(project, 'migration.describe')
    assert (status, code) == (200, 0)
    assert source_snapshot(project) == before
    payload = {'base_revision': fixture['revision_id'], 'operation_id': 'migration-adapter',
               'plan_digest': result['result']['plan_digest']}
    accepted, status, code = collaboration_api.invoke(project, 'migration.apply', payload)
    assert (status, code) == (200, 0), accepted
    assert Store(project).load_document()['collaboration']['request'] is None
    replay, status, code = collaboration_api.invoke(project, 'migration.apply', payload)
    assert (status, code) == (200, 0) and replay['status'] == 'already_applied'


def test_every_contract_http_route_resolves_to_the_shared_adapter():
    routes = {'collaboration': ('GET', 'show'), 'collaboration/migration': ('GET', 'migration.describe'),
        'collaboration/requests': ('POST', 'request.start'), 'eligibility': ('POST', 'eligibility'),
        'collaboration/decisions': ('POST', 'decision'), 'collaboration/authorizations': ('POST', 'grant'),
        'collaboration/proposal-adoptions': ('POST', 'adopt-proposal'), 'collaboration/request/pause': ('POST', 'pause'),
        'collaboration/request/resume': ('POST', 'resume'), 'reviews/import': ('POST', 'review.import')}
    for tail, (method, action) in routes.items():
        assert collaboration_api.http_action(method, '/api/projects/fixed/' + tail) == ('fixed', action, {})
    assert collaboration_api.http_action('POST', '/api/projects/fixed/collaboration/migration') == ('fixed', 'migration.apply', {})
    assert collaboration_api.http_action('POST', '/api/projects/fixed/collaboration/authorizations/auth/revoke') == ('fixed', 'revoke', {'authorization_id': 'auth'})


def test_formal_host_framing_proposal_decision_and_adoption_via_cli(tmp_path, capsys):
    project = new_project(tmp_path)
    store = Store(project)
    document = store.load_document()
    task = next(store.read_object_json(ref) for ref in document['tasks']
                if store.read_object_json(ref)['status'] == 'awaiting_host')
    assert task['protocol_version'] == 'compose.v2' and task['collaboration_binding']['phase'] == 'framing'
    # Missing capability is refused by the actual SDK before the valid claim.
    with pytest.raises(Exception, match='capabilit|protocol'):
        service.task_start(project, task_id=task['task_id'], execution_ref='L1-obsolete-host',
                           supported_protocols=['compose.v1'], capabilities=[])
    narrative = {'schema_version': 'narrative.v1', 'narrative_id': 'synthetic-frame', 'version': 1,
        'project_id': document['project_id'], 'origin': 'host_composed', 'maturity': 'framing', 'input_basis': [],
        'communication_job': {'mode': 'train', 'audience_fact_key': 'task.audience',
            'audience_question': 'What should the reader do?', 'desired_outcome': 'Make the bounded choice',
            'observable_success': 'Reader identifies the next action', 'use_mode': 'live', 'primary_use': 'live'},
        'central_node_id': None, 'nodes': [], 'edges': [], 'issues': [], 'alternatives': [], 'previous_ref': None}
    result_payload = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'framing',
        'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
        'payload': {'narrative': narrative}, 'usage_events': []}
    accepted = submit_host_fixture(project, task_id=task['task_id'], result_payload=result_payload,
        execution_ref='L1-synthetic-framing-author', host_declaration={'supported_protocols': ['compose.v2'],
            'capabilities': task['required_capabilities']})
    proposal = accepted['result_refs'][0]
    path = tmp_path / 'decision.json'
    path.write_text(json.dumps({'base_revision': store.current_revision_id(), 'operation_id': 'cli-framing-decision',
        'decision': {'topic': 'direction', 'disposition': 'accepted', 'authority_mode': 'direct_user',
            'value': {'selected': 'the actual framing proposal'}, 'scope': {**scope(), 'layers': ['narrative']},
            'instruction_evidence': instruction('Accept this framing proposal'),
            'subject_refs': [{'artifact_kind': 'narrative', 'artifact_ref': proposal, 'projection': 'direction'}]}}))
    assert cli.main(['collaboration', 'decision', str(project), '--input', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['result']['decision_ref']
    # Framing is not an argument. The real approved-direction gate permits an
    # argument task; its distinct proposal then gets its own precise decision.
    task = content_production.open_phase_task(store, store.load_document(), operation_id='L1-argument', phase='argument')
    argument = {**narrative, 'maturity': 'argument', 'central_node_id': 'claim',
        'nodes': [{'node_id': 'claim', 'role': 'claim', 'statement': 'Use an explicit bounded planning scope',
            'authority': 'instruction', 'source_links': [], 'qualification_node_ids': [], 'unresolved_issue_ids': []}],
        'previous_ref': proposal}
    result_payload = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'narrative',
        'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
        'payload': {'narrative': argument}, 'usage_events': []}
    accepted = submit_host_fixture(project, task_id=task['task_id'], result_payload=result_payload,
        execution_ref='L1-synthetic-argument-author', host_declaration={'supported_protocols': ['compose.v2'],
            'capabilities': task['required_capabilities']})
    proposal = accepted['result_refs'][0]
    path.write_text(json.dumps({'base_revision': store.current_revision_id(), 'operation_id': 'cli-argument-decision',
        'decision': {'topic': 'direction', 'disposition': 'accepted', 'authority_mode': 'direct_user',
            'value': {'selected': 'the actual argument proposal'}, 'scope': {**scope(), 'layers': ['narrative']},
            'instruction_evidence': instruction('Accept this argument proposal'),
            'subject_refs': [{'artifact_kind': 'narrative', 'artifact_ref': proposal, 'projection': 'direction'}]}}))
    assert cli.main(['collaboration', 'decision', str(project), '--input', str(path)]) == 0
    decision = json.loads(capsys.readouterr().out)['result']['decision_ref']
    payload = {'base_revision': store.current_revision_id(), 'operation_id': 'cli-framing-adopt',
               'proposal_ref': proposal, 'decision_ref': decision, 'write_scope': {**scope(), 'layers': ['narrative']}}
    path.write_text(json.dumps(payload))
    assert cli.main(['collaboration', 'adopt-proposal', str(project), '--input', str(path)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response['result']['adopted_refs'] == [proposal]
    assert store.load_document()['narrative'] == proposal
    assert not store.load_document()['collaboration']['authorizations']
    assert cli.main(['collaboration', 'adopt-proposal', str(project), '--input', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'already_applied'


def test_real_http_request_grant_pause_resume_revoke_and_migration_transactions(tmp_path):
    project = new_project(tmp_path)
    store = Store(project)
    project_id = store.load_document()['project_id']
    with http_server(project) as url:
        base = f'/api/projects/{project_id}/collaboration'
        old_id = store.load_document()['collaboration']['request']['request_id']
        payload = {'base_revision': store.current_revision_id(), 'operation_id': 'http-request',
            'request': request(replace_request_id=old_id, instruction_evidence=instruction('New HTTP request', 'synthetic:http-request'))}
        status, response = http(url, base + '/requests', payload)
        assert status == 200, response
        new_id = response['result']['request_id']
        status, replay = http(url, base + '/requests', payload)
        assert status == 200 and replay['status'] == 'already_applied'
        status, response = http(url, base + '/authorizations', {'base_revision': store.current_revision_id(),
            'operation_id': 'http-grant', 'authorization': {'mode': 'execute', 'actions': ['content.compose'],
            'scope': scope(), 'max_external_calls': 0, 'max_candidate_count': 0,
            'adoption_policy': 'candidate_only', 'instruction_evidence': instruction('HTTP scope authorization')}})
        assert status == 200, response
        authorization_id = response['result']['authorization_id']
        for action, extra in [('pause', {'reason': 'Hold scope'}), ('resume', {})]:
            status, response = http(url, base + '/request/' + action, {'base_revision': store.current_revision_id(),
                'operation_id': 'http-' + action, 'request_id': new_id, 'evidence': instruction(action), **extra})
            assert status == 200, response
        status, response = http(url, base + '/authorizations/' + authorization_id + '/revoke', {
            'authorization_id': 'another-authorization', 'base_revision': store.current_revision_id(),
            'operation_id': 'http-revoke-alias', 'reason': 'Withdraw', 'evidence': instruction()})
        assert status == 400 and response['error']['path'] == 'authorization_id'
        status, response = http(url, base + '/authorizations/' + authorization_id + '/revoke', {
            'base_revision': store.current_revision_id(), 'operation_id': 'http-revoke',
            'reason': 'Withdraw', 'evidence': instruction()})
        assert status == 200, response
    old = historical_snapshot(tmp_path, scenario='HTTP explicit migration')
    store = Store(old['project'])
    with http_server(old['project']) as url:
        route = '/api/projects/' + store.load_document()['project_id'] + '/collaboration/migration'
        status, response = http(url, route)
        assert status == 200
        status, response = http(url, route, {'base_revision': store.current_revision_id(),
            'operation_id': 'http-migration', 'plan_digest': response['result']['plan_digest']})
        assert status == 200 and store.load_document()['collaboration']['request'] is None, response


def imported_project(tmp_path):
    page = {'schema_version': 'deck_page_package.v2', 'page_id': 'p1',
        'customer_visible': {'title': 'Synthetic imported copy', 'body_blocks': [
            {'id': 'body', 'type': 'paragraph', 'text': 'Fixed manuscript bytes for an explicit review.'}]},
        'speaker_notes': 'Existing notes are preserved.',
        'visual_spec': {'intent': 'Read the copy', 'reference_mode': 'new_design'}}
    return public_project(tmp_path, create_input={'brief': 'Import this confirmed manuscript', 'audience': 'test reader'},
        manuscript={'pages': [page], 'page_order': ['p1']})['project']


def external_packet_for_page(tmp_path, project):
    from deck_master import external_review
    from deck_master.models import canonical_json_bytes, sha256_bytes
    store = Store(project)
    doc = store.load_document()
    ref = doc['pages'][0]['page']
    source = tmp_path / 'fixed-external-page.json'
    source.write_bytes(store.read_object_bytes(ref))
    plan_source = tmp_path / 'fixed-external-plan.json'
    plan_source.write_bytes(store.read_object_bytes(doc['content_plan']))
    review_scope = {**scope(), 'page_ids': [], 'layers': ['review'], 'allow_page_membership_change': False}
    external = external_review.evaluate([source, plan_source], scope=review_scope)['external_report']
    report = external['report']
    report['reviews'] = [{'schema_version': 'deck_review.v2', 'review_id': 'L1-external-copy-review',
        'kind': 'page_copy', 'review_stage': 'preproduction', 'status': 'needs_review',
        'subjects': [{'source_uri': source.as_uri(), 'sha256': ref['sha256']},
                     {'source_uri': plan_source.as_uri(), 'sha256': doc['content_plan']['sha256']}],
        'dependencies': [{'kind': 'content', 'identity': 'page:p1', 'sha256': ref['sha256']},
            {'kind': 'content', 'identity': 'content_plan', 'sha256': doc['content_plan']['sha256']}],
        'reviewer': {'type': 'host_self', 'id': 'L1-synthetic-report-reader', 'execution_ref': 'L1-synthetic-reader',
            'independence_confirmed': False, 'identity_receipt': None, 'evidence_ref': None, 'assurance': 'host_attested'},
        'observations': ['L1 synthetic reader observed fixed manuscript text; further review is required.'],
        'findings': [], 'created_at': '2026-10-15T00:00:00Z', 'replaces': None}]
    report['evidence_level'] = 'L1_SYNTHETIC'
    report['provenance']['reviewer_executed'] = True
    report['provenance']['limitations'] = 'Synthetic protocol test, no independent model or human execution'
    external['report_sha256'] = sha256_bytes(canonical_json_bytes(report))
    return external


def test_external_report_describe_import_replay_cli_and_http_preserve_original_identity(tmp_path, capsys):
    from deck_master import review_import
    project = imported_project(tmp_path)
    store = Store(project)
    external = external_packet_for_page(tmp_path, project)
    before = source_snapshot(project)
    binding = review_import.describe_bindings(project, external_report=external)
    assert source_snapshot(project) == before
    assert len(binding['source_bindings']) == 2
    payload = {'base_revision': store.current_revision_id(), 'operation_id': 'L1-explicit-report-import',
        'external_report': external, 'source_bindings': binding['source_bindings'],
        'evidence': instruction('Explicitly import the fixed review of this manuscript')}
    path = tmp_path / 'import-report.json'
    path.write_text(json.dumps(payload))
    assert cli.main(['review', 'import', str(project), '--input', str(path)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert len(response['result']['review_refs']) == 1
    review = store.read_object_json(response['result']['review_refs'][0])
    assert review['status'] == 'needs_review'
    assert review['reviewer']['type'] == 'host_self'
    assert review['reviewer']['independence_confirmed'] is False
    assert review['reviewer']['identity_receipt'] is None
    with http_server(project) as url:
        route = '/api/projects/' + store.load_document()['project_id'] + '/reviews/import'
        status, replay = http(url, route, payload)
        assert status == 200 and replay['status'] == 'already_applied', replay
        bindings_route = route.removesuffix('/import') + '/bindings'
        before = source_snapshot(project)
        status, described = http(url, bindings_route, {'external_report': external})
        assert status == 200 and described['result']['source_bindings'] == binding['source_bindings']
        assert source_snapshot(project) == before


def test_project_report_import_exact_retry_ignores_later_control_pointer(tmp_path):
    from deck_master import external_review, review_import
    project = imported_project(tmp_path)
    store = Store(project)
    fixed = store.current_revision_id()
    review_scope = {**scope(), 'layers': ['review'], 'allow_page_membership_change': False}
    external = external_review.evaluate({'kind': 'project', 'path': str(project), 'revision': fixed}, scope=review_scope)['external_report']
    bindings = review_import.describe_bindings(project, external_report=external)['source_bindings']
    payload = {'base_revision': fixed, 'operation_id': 'project-report-import', 'external_report': external,
        'source_bindings': bindings, 'evidence': instruction('Import this fixed project packet'), 'artifact_revision': fixed}
    response, status, code = collaboration_api.invoke(project, 'review.import', payload)
    assert (status, code) == (200, 0), response
    assert response['result']['review_refs'] == [] and response['result']['next_action'] == 'provide_reviewer'
    replay, status, code = collaboration_api.invoke(project, 'review.import', payload)
    assert (status, code) == (200, 0) and replay['status'] == 'already_applied', replay


@pytest.mark.parametrize('mutation,expected', [('wrong_digest', 400), ('wrong_binding', 409),
    ('empty_bindings', 400), ('empty_dependencies', 409), ('trusted_identity', 403), ('stale_base', 409)])
def test_external_import_risk_rejections_do_not_adopt_business_reviews(tmp_path, mutation, expected):
    from deck_master import review_import
    from deck_master.models import canonical_json_bytes, sha256_bytes
    project = imported_project(tmp_path)
    store = Store(project)
    external = external_packet_for_page(tmp_path, project)
    bindings = review_import.describe_bindings(project, external_report=external)['source_bindings']
    payload = {'base_revision': store.current_revision_id(), 'operation_id': 'L1-rejected-import',
        'external_report': external, 'source_bindings': bindings, 'evidence': instruction()}
    if mutation == 'wrong_digest':
        external['report_sha256'] = '0' * 64
    elif mutation == 'wrong_binding':
        bindings[0]['source_sha256'] = '0' * 64
    elif mutation == 'empty_bindings':
        payload['source_bindings'] = []
    elif mutation in ('empty_dependencies', 'trusted_identity'):
        if mutation == 'empty_dependencies':
            external['report']['reviews'][0]['dependencies'] = []
        else:
            external['report']['reviews'][0]['reviewer']['assurance'] = 'verified_user'
        external['report_sha256'] = sha256_bytes(canonical_json_bytes(external['report']))
    else:
        payload['base_revision'] = 'stale'
    before = store.load_document()
    response, status, code = collaboration_api.invoke(project, 'review.import', payload)
    assert status == expected, response
    assert code == (5 if expected == 409 else 4 if expected == 403 else 2)
    assert store.load_document() == before


def test_readiness_cli_http_and_sdk_share_selected_current_control_predicate(tmp_path, capsys):
    from deck_master.delivery_eligibility import describe
    project = imported_project(tmp_path)
    store = Store(project)
    before = source_snapshot(project)
    expected = describe(project)
    assert expected['status'] == 'blocked'
    assert cli.main(['final-readiness', '--project', str(project), '--json']) == 0
    actual = json.loads(capsys.readouterr().out)
    for key in ('status', 'eligibility', 'engineering_ready', 'professional', 'artifact_revision_id', 'control_revision_id', 'selected_output'):
        assert actual[key] == expected[key]
    with http_server(project) as url:
        route = '/api/projects/' + store.load_document()['project_id'] + '/delivery-eligibility'
        status, response = http(url, route)
        assert status == 200 and response['result'] == expected
        status, response = http(url, route + '?unknown=1')
        assert status == 400
    assert source_snapshot(project) == before


def test_http_missing_session_is_a_shared_transport_error_without_writes(tmp_path):
    project = new_project(tmp_path)
    before = source_snapshot(project)
    with http_server(project) as url:
        path = '/api/projects/' + Store(project).load_document()['project_id'] + '/eligibility'
        req = urllib.request.Request(url + path, data=b'{"action":"dispatch.compose"}',
                                     headers={'Content-Type': 'application/json'})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req, timeout=5)
        response = json.loads(error.value.read())
        assert error.value.code == 403
        assert response['schema_version'] == 'collaboration_response.v1'
        assert response['error']['code'] == 'session_required'
        assert response['error']['path'] == 'transport'
    assert source_snapshot(project) == before


def test_http_current_manuscript_import_cas_and_replay_use_shared_atomic_service(tmp_path):
    project = imported_project(tmp_path)
    store = Store(project)
    before = store.load_document()
    page = store.read_object_json(before['pages'][0]['page'])
    page['customer_visible']['title'] = 'Explicit imported revision'
    payload = {'base_revision': before['revision_id'], 'operation_id': 'http-import-manuscript',
        'draft_payload': {'pages': [page], 'page_order': ['p1']},
        'instruction_evidence': instruction('Import this exact corrected manuscript'), 'preserve_mainline': True}
    with http_server(project) as url:
        path = '/api/projects/' + before['project_id'] + '/draft/import'
        status, response = http(url, path, {**payload, 'base_revision': 'stale'})
        assert status == 409 and response['error']['path'] == 'base_revision'
        assert store.load_document() == before
        status, response = http(url, path, payload)
        assert status == 200, response
        doc = store.load_document()
        imported = store.read_object_json(doc['pages'][0]['page'])
        assert imported['customer_visible']['title'] == 'Explicit imported revision'
        assert imported['speaker_notes'] == page['speaker_notes']
        assert doc['narrative'] is None
        plan = store.read_object_json(doc['content_plan'])
        assert plan['mode'] == 'imported_mapping'
        assert plan['page_links'][0]['page_ref'] == doc['pages'][0]['page']
        status, replay = http(url, path, payload)
        assert status == 200 and replay['status'] == 'already_applied', replay
        assert store.current_revision_id() == doc['revision_id']


@pytest.mark.parametrize('mode', [None, 'read_alone'])
def test_launcher_http_create_preserves_mode_origin_and_real_instruction_without_grants(tmp_path, mode):
    seed = new_project(tmp_path)
    registry_file = tmp_path / 'projects.json'
    target = tmp_path / 'http-created'
    values = {'path': str(target), 'title': 'Synthetic launcher project', 'brief': 'Explicit HTTP input',
              'audience': 'Synthetic reader', 'scenario': 'read the supplied content'}
    if mode is not None:
        values['presentation_mode'] = mode
    with http_server(seed, registry_file=registry_file) as url:
        status, response = http(url, '/api/projects/create', values)
        assert status == 200, response
        assert response['registered'] is True
        doc = Store(target).load_document()
        assert doc['task']['presentation_mode'] == (mode or 'live')
        assert doc['task']['presentation_mode_source'] == ('provided' if mode else 'default')
        assert doc['collaboration']['request']['instruction_evidence']['assurance'] == 'host_attested'
        assert doc['collaboration']['authorizations'] == []
        assert len(doc['tasks']) == 1
        bad_target = tmp_path / 'untrusted-create'
        status, response = http(url, '/api/projects/create', {**values, 'path': str(bad_target),
            'request_input': {'adapter_context': {'verified_user_events': []}}})
        assert status == 403 and response['error']['code'] == 'untrusted_adapter_context'
        assert not bad_target.exists()


def test_cli_explicit_fileset_descriptor_needs_no_unused_source_argument(tmp_path, capsys):
    a, b = tmp_path / 'copy.txt', tmp_path / 'speech.txt'
    a.write_text('Copy')
    b.write_text('Speech')
    descriptor = tmp_path / 'source.json'
    descriptor.write_text(json.dumps({'kind': 'fileset', 'files': [str(a), str(b)]}))
    assert cli.main(['review', 'evaluate', '--source-input', str(descriptor)]) == 4
    captured = capsys.readouterr()
    assert captured.out == ''
    response = json.loads(captured.err)
    assert response['error']['code'] == 'needs_reviewer'
    report = response['result']['external_report']['report']
    assert report['source_manifest']['source_kind'] == 'fileset'
    assert len(report['subjects']) == 2 and report['reviews'] == []


def test_external_review_cli_gap_keeps_readable_report_and_bad_hash_writes_nothing(tmp_path, capsys):
    source_root = tmp_path / 'external-source'
    source_root.mkdir()
    source = source_root / 'manuscript.txt'
    source.write_text('A real local manuscript read without a Document or reviewer.')
    before = source_snapshot(source_root)
    report_path = tmp_path / 'reports' / 'cli-review.json'
    assert cli.main(['review', 'evaluate', str(source), '--report-output', str(report_path)]) == 4
    captured = capsys.readouterr()
    assert captured.out == ''
    response = json.loads(captured.err)
    assert response['status'] == response['result']['status'] == response['error']['code'] == 'needs_reviewer'
    assert response['error']['recoverable'] is True
    assert response['next_action'] == response['result']['next_action'] == 'review_the_readable_packet'
    packet = response['result']['external_report']
    assert json.loads(report_path.read_text()) == packet
    assert packet['report_sha256'] == models.sha256_bytes(models.canonical_json_bytes(packet['report']))
    assert packet['report']['engineering_observations'][0]['text'] == source.read_text()
    assert packet['report']['provenance']['reviewer_executed'] is False
    assert packet['report']['reviews'] == []
    rejected_output = tmp_path / 'reports' / 'invalid-hash.json'
    assert cli.main(['review', 'evaluate', str(source), '--source-sha256', '0' * 64,
        '--report-output', str(rejected_output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    rejected = json.loads(captured.err)
    assert rejected['error']['code'] == 'invalid_input' and rejected['error']['path'] == 'source_sha256'
    assert rejected['result'] is None
    assert not rejected_output.exists()
    assert source_snapshot(source_root) == before


@pytest.mark.parametrize('launcher', [False, True])
def test_external_review_real_http_gap_keeps_report_and_invalid_hash_is_separate(tmp_path, launcher):
    project = new_project(tmp_path)
    registry_file = tmp_path / 'projects.json' if launcher else None
    before_project = source_snapshot(project)
    source_root = tmp_path / 'external-source'
    source_root.mkdir()
    source = source_root / 'manuscript.txt'
    source.write_text('Actual HTTP manuscript text, with no reviewer execution.')
    before_source = source_snapshot(source_root)
    report_path = tmp_path / 'reports' / 'http-review.json'
    external_scope = {**scope(), 'subject': 'external_artifact', 'layers': ['review'],
                      'allow_page_membership_change': False, 'purpose': 'review'}
    payload = {'source': str(source), 'scope': external_scope, 'persistence': 'none',
               'report_output': str(report_path)}
    with http_server(project, registry_file=registry_file) as url:
        status, response = http(url, '/api/reviews/evaluate', payload)
        assert status == 409, response
        assert response['status'] == response['result']['status'] == response['error']['code'] == 'needs_reviewer'
        assert response['error']['recoverable'] is True
        assert response['error']['details']['affected_scope'] == external_scope
        assert response['project_id'] is None
        packet = response['result']['external_report']
        assert json.loads(report_path.read_text()) == packet
        assert packet['report_sha256'] == models.sha256_bytes(models.canonical_json_bytes(packet['report']))
        assert packet['report']['engineering_observations'][0]['text'] == source.read_text()
        assert packet['report']['source_unchanged'] is True and packet['report']['reviews'] == []
        assert response['next_action'] == 'review_the_readable_packet'
        rejected_output = tmp_path / 'reports' / 'invalid-http-hash.json'
        status, rejected = http(url, '/api/reviews/evaluate', {**payload,
            'source_sha256': '0' * 64, 'report_output': str(rejected_output)})
        assert status == 400 and rejected['error']['path'] == 'source_sha256'
        assert rejected['result'] is None and not rejected_output.exists()
    assert source_snapshot(source_root) == before_source
    assert source_snapshot(project) == before_project


def test_http_explicit_continue_returns_actual_work_order_without_duplicate_dispatch(tmp_path):
    project = new_project(tmp_path)
    store = Store(project)
    doc = store.load_document()
    with http_server(project) as url:
        route = '/api/projects/' + doc['project_id'] + '/continue'
        status, response = http(url, route, {'project_id': doc['project_id']})
        assert status == 200 and response['status'] == 'awaiting_host', response
        order = response['result']['pending_tasks'][0]
        assert order['collaboration_binding']['request_id'] == doc['collaboration']['request']['request_id']
        assert {'collaboration.v1', 'rc3-entry.v1'} <= set(order['required_capabilities'])
        assert order['protocol_version'] == 'compose.v2'
        revision = store.current_revision_id()
        status, repeated = http(url, route, {})
        assert status == 200 and repeated['result']['pending_tasks'][0]['task_id'] == order['task_id']
        assert store.current_revision_id() == revision
        status, rejected = http(url, route, {'base_revision': revision, 'operation_id': 'not-consumed'})
        assert status == 400 and rejected['error']['path'] == 'request'
        paused, status, code = write(project, 'pause', 'http-continue-pause',
            request_id=doc['collaboration']['request']['request_id'], reason='Hold this request', evidence=instruction())
        assert (status, code) == (200, 0), paused
        paused_revision = store.current_revision_id()
        status, reading = http(url, route, {})
        assert status == 200 and reading['result']['pending_tasks'][0]['task_id'] == order['task_id']
        assert store.current_revision_id() == paused_revision
        # Existing work orders stay readable while paused; the actual execution
        # boundary refuses a claim, so reading one confers no permission.
        with pytest.raises(eligibility.EligibilityBlocked) as error:
            service.task_start(project, task_id=order['task_id'], execution_ref='L1-paused-host',
                supported_protocols=[order['protocol_version']], capabilities=order['required_capabilities'])
        assert 'request_paused' in error.value.decision['reason_codes']


@pytest.mark.parametrize('launcher', [False, True])
def test_health_and_current_capabilities_advertise_actual_rc3_entry_protocol(tmp_path, capsys, launcher):
    project = new_project(tmp_path)
    registry_file = tmp_path / 'health-registry.json' if launcher else None
    with http_server(project, registry_file=registry_file) as url:
        status, health = http(url, '/api/health')
        assert status == 200
        assert {'collaboration.v1', 'rc3-entry.v1'} <= set(health['ui_capabilities'])
        assert {'collaboration.v1', 'rc3-entry.v1'} <= set(health['protocol_capabilities'])
    assert cli.main(['capabilities']) == 0
    current = json.loads(capsys.readouterr().out)
    assert current['protocol_capabilities'] == ['collaboration.v1', 'rc3-entry.v1']
    assert current['assurance'] == 'host_attested'
