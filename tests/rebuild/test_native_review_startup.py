"""Synthetic startup faults; never model or native acceptance evidence."""
import json
import subprocess

import pytest

from deck_master import native_review, native_review_transport as transport, review_channels
from deck_master.review_evidence import ProviderUnavailable
from test_content_preproduction_review import _deck


def test_startup_failure_is_discoverable_without_creating_a_task(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    before = store.load_document()
    monkeypatch.setattr(transport.shutil, 'which', lambda _: '/synthetic/codex')
    monkeypatch.setattr(transport.subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, b'', b'ChatGPT'))
    monkeypatch.setattr(transport.subprocess, 'Popen', lambda *a, **k:
                        (_ for _ in ()).throw(OSError('private-token-and-path')))
    with pytest.raises(ProviderUnavailable):
        native_review.run(project)
    assert store.load_document() == before
    found = review_channels.describe(project=project, check_native=True)
    assert found['native_client']['status'] == 'prerequisites_ready'
    assert found['native_client']['session_verified'] is False
    assert found['native_executions'] == []
    failure = found['native_startup_failures'][0]
    assert failure['phase'] == 'app_server_start'
    assert failure['category'] == 'tool_failed'
    assert failure['exit_code'] == 3
    assert failure['process_exit_code'] is None
    assert failure['revision_id'] == before['revision_id']
    assert failure['next_action']
    assert 'private-token-and-path' not in json.dumps(found)


@pytest.mark.parametrize('rpc, phase', [
    ('initialize', 'initialize'), ('config/read', 'config_read'), ('thread/start', 'thread_start'),
])
def test_exit_before_task_records_observed_code_and_no_raw_stderr(tmp_path, monkeypatch, native_process, rpc, phase):
    project, store = _deck(tmp_path)
    before = store.load_document()
    respond = native_process.response
    def exit_early(request, result):
        if request['method'] == rpc:
            native_process.code = 17
            native_process.stdout.lines.put(b'')
        else:
            respond(request, result)
    monkeypatch.setattr(native_process, 'response', exit_early)
    from deck_master import cli
    assert cli.main(['review', 'native', '--project', str(project)]) == 3
    failure = review_channels.describe(project=project)['native_startup_failures'][0]
    assert failure['phase'] == phase
    assert failure['process_exit_code'] == 17
    assert failure['category'] == 'tool_failed'
    assert store.load_document() == before
    assert not any(item.get('method') == 'turn/start' for item in native_process.sent)
    assert native_process.options['stderr'] == subprocess.DEVNULL


# Shared synthetic transport only: no native executable or model is launched.
from test_native_review_transport import native_process


@pytest.mark.parametrize('outcome, category, phase, code', [
    ('missing', 'tool_missing', 'client_lookup', None),
    ('login_error', 'tool_failed', 'login_status', None),
    ('logged_out', 'login_required', 'login_status', 1),
    ('provider', 'session_rejected', 'session_validation', None),
])
def test_startup_categories_survive_discovery(tmp_path, monkeypatch, native_process, outcome, category, phase, code):
    project, store = _deck(tmp_path)
    before = store.load_document()
    if outcome == 'missing':
        monkeypatch.setattr(transport.shutil, 'which', lambda _: None)
    elif outcome == 'login_error':
        monkeypatch.setattr(transport.subprocess, 'run', lambda *a, **k:
            (_ for _ in ()).throw(OSError('secret-marker')))
    elif outcome == 'logged_out':
        monkeypatch.setattr(transport.subprocess, 'run', lambda *a, **k:
            subprocess.CompletedProcess(a, 1, b'secret-marker', b'private login details'))
    else:
        native_process.provider = 'custom-external'
    with pytest.raises(ProviderUnavailable) as caught:
        native_review.run(project)
    found = review_channels.describe(project=project)
    row = found['native_startup_failures'][0]
    assert (row['category'], row['phase'], row['process_exit_code']) == (category, phase, code)
    assert caught.value.error_details['startup_history_saved'] is True
    assert 'secret-marker' not in json.dumps(found)
    assert 'secret-marker' not in (store.deck_root / 'native-review-startup-history.json').read_text()
    assert store.load_document() == before
    assert found['native_executions'] == []


def test_later_synthetic_completion_preserves_historical_failure_separately(tmp_path, monkeypatch):
    from test_native_review import FixtureSession
    project, store = _deck(tmp_path)
    monkeypatch.setattr(transport.shutil, 'which', lambda _: None)
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            native_review.run(project)
    failures = review_channels.describe(project=project)['native_startup_failures']
    assert len(failures) == 2
    assert failures[0]['attempt_id'] != failures[1]['attempt_id']
    FixtureSession.calls = []
    FixtureSession.status, FixtureSession.corrupt, FixtureSession.before_finish = 'pass', False, None
    monkeypatch.setattr(native_review, 'CodexReviewSession', FixtureSession)
    assert native_review.run(project)['status'] == 'reviewed'
    before = store.load_document()
    monkeypatch.setattr(transport.shutil, 'which', lambda _: '/synthetic/codex')
    monkeypatch.setattr(transport.subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, b'', b'ChatGPT'))
    found = review_channels.describe(project=project, check_native=True)
    assert found['native_client']['status'] == 'prerequisites_ready'
    assert found['native_startup_failures'] == failures
    assert found['native_executions'][0]['status'] == 'completed'
    assert found['native_client']['session_verified'] is False
    assert store.load_document() == before
    assert len(FixtureSession.calls) == 1


def test_unreadable_history_is_unknown_and_does_not_mask_new_failure(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    path = store.deck_root / 'native-review-startup-history.json'
    path.write_text('private-invalid-json')
    before = store.load_document()
    monkeypatch.setattr(transport.shutil, 'which', lambda _: None)
    with pytest.raises(ProviderUnavailable) as caught:
        native_review.run(project)
    assert caught.value.error_details['startup_history_saved'] is False
    found = review_channels.describe(project=project)
    assert found['native_startup_history']['status'] == 'unavailable'
    assert found['native_startup_failures'] == []
    assert 'private-invalid-json' not in json.dumps(found)
    assert path.read_text() == 'private-invalid-json'
    assert store.load_document() == before


def test_capability_table_has_no_unimplemented_host_stage(monkeypatch):
    monkeypatch.setattr(transport.shutil, 'which', lambda _: None)
    table = review_channels.describe()
    assert [(stage['stage'], stage['task_stage']) for stage in table['stages']] == [
        ('content_preproduction', 'preproduction'), ('original_image_expression', 'original_image'),
        ('svg_conversion', 'page_visual'), ('final_delivery', 'final')]
    for index, stage in enumerate(table['stages']):
        assert [(row['mode'], row['supported']) for row in stage['channels']] == [
            ('native_independent', index == 0), ('independent_host', True), ('human', True)]
        assert stage['execution_verified'] is False
        assert all(row['status'] == 'receipt_not_configured' for row in stage['channels'][1:])


def test_diagnostic_write_failure_preserves_original_startup_error(tmp_path, monkeypatch, capsys):
    from deck_master import cli, native_review_startup
    project, store = _deck(tmp_path)
    before = store.load_document()
    monkeypatch.setattr(transport.shutil, 'which', lambda _: None)
    monkeypatch.setattr(native_review_startup, '_atomic_write_bytes', lambda *a, **k:
                        (_ for _ in ()).throw(OSError('private-filesystem-error')))
    assert cli.main(['review', 'native', '--project', str(project)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ''
    payload = json.loads(captured.err)
    assert payload['error']['code'] == 'needs_reviewer'
    assert 'not installed' in payload['error']['message']
    assert payload['error']['details']['startup_history_saved'] is False
    assert payload['error']['details']['phase'] == 'client_lookup'
    assert 'private-filesystem-error' not in json.dumps(payload)
    assert store.load_document() == before


def test_symlink_diagnostic_is_not_followed_or_overwritten(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    external = tmp_path / 'external-diagnostic'
    external.write_text('private-external-content')
    path = store.deck_root / 'native-review-startup-history.json'
    path.symlink_to(external)
    monkeypatch.setattr(transport.shutil, 'which', lambda _: None)
    with pytest.raises(ProviderUnavailable) as caught:
        native_review.run(project)
    assert caught.value.error_details['startup_history_saved'] is False
    assert path.is_symlink()
    assert external.read_text() == 'private-external-content'
    found = review_channels.describe(project=project)
    assert found['native_startup_history']['status'] == 'unavailable'
    assert 'private-external-content' not in json.dumps(found)


def test_untrusted_startup_details_use_the_same_public_and_disk_whitelist(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    class UnavailableSession:
        startup_failure = {'phase': 'private-path', 'category': ['private-token'],
                           'stderr': 'private-stderr', 'exit_code': 'private-value',
                           'process_exit_code': 'private-value'}
        def __enter__(self):
            raise ProviderUnavailable('native_review', 'synthetic unavailable')
    monkeypatch.setattr(native_review, 'CodexReviewSession', UnavailableSession)
    with pytest.raises(ProviderUnavailable) as caught:
        native_review.run(project)
    details = caught.value.error_details
    assert details['category'] == 'startup_failed'
    assert details['phase'] == 'session_enter'
    assert details['exit_code'] == 3 and details['process_exit_code'] is None
    assert details['startup_history_saved'] is True
    assert 'private-' not in json.dumps(details)
    assert 'private-' not in (store.deck_root / 'native-review-startup-history.json').read_text()
