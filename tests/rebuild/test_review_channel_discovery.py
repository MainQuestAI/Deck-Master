"""RP-01 synthetic discovery checks; no native model turn is executed."""
import json
import subprocess

import pytest

from deck_master import capabilities, cli, native_review_transport, review_channels, review_evidence


class Provider:
    provider_id = 'synthetic-review-provider'
    adapter_version = 'test.v1'
    authentication = 'protected_transport'
    channels = ('independent_review_receipts', 'human_review_receipts')
    ready = True

    def health(self):
        return self.ready

    def fetch(self, _):
        raise AssertionError('discovery must not fetch evidence')

    def verify(self, _):
        raise AssertionError('discovery must not mint evidence')


def native_stage(result):
    return result['stages'][0]['channels'][0]


def test_discovery_lists_native_route_even_without_registered_receipts(monkeypatch):
    monkeypatch.setattr(native_review_transport.shutil, 'which', lambda _: '/synthetic/codex')
    monkeypatch.setattr(native_review_transport.subprocess, 'run', lambda *a, **k:
                        (_ for _ in ()).throw(AssertionError('default discovery must not run login/model')))
    result = review_channels.describe()
    assert native_stage(result)['supported']
    assert native_stage(result)['status'] == 'not_verified'
    assert all(stage['channels'][0]['status'] == 'unsupported' for stage in result['stages'][1:])
    assert result['stages'][0]['channels'][1]['status'] == 'receipt_not_configured'
    assert not result['native_client']['model_called']
    assert not result['native_client']['session_verified']


@pytest.mark.parametrize('outcome, expected', [
    ('missing', 'tool_missing'), ('timeout', 'tool_failed'), ('oserror', 'tool_failed'),
    ('api', 'login_required'), ('loggedout', 'login_required'), ('chatgpt', 'prerequisites_ready'),
])
def test_native_probe_distinguishes_failures_without_exposing_login_output(monkeypatch, outcome, expected):
    calls = []
    monkeypatch.setattr(native_review_transport.shutil, 'which', lambda _: None if outcome == 'missing' else '/synthetic/codex')
    def run(args, **kwargs):
        calls.append(args)
        assert args == ['/synthetic/codex', 'login', 'status']
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired(args, 3, output=b'secret-marker')
        if outcome == 'oserror':
            raise OSError('secret-marker')
        return subprocess.CompletedProcess(args, 1 if outcome == 'loggedout' else 0,
            b'secret-marker', b'Logged in using ChatGPT' if outcome == 'chatgpt' else b'API key secret-marker')
    monkeypatch.setattr(native_review_transport.subprocess, 'run', run)
    result = review_channels.describe(check_native=True)
    assert native_stage(result)['status'] == expected
    assert 'secret-marker' not in json.dumps(result)
    assert len(calls) == (0 if outcome == 'missing' else 1)
    assert all(not row['execution_verified'] for row in result['stages'])


@pytest.mark.parametrize('ready, expected', [(True, 'receipt_available'), (False, 'provider_unavailable')])
def test_registered_receipts_are_not_an_observed_reviewer_or_image_support(ready, expected):
    provider = Provider()
    provider.ready = ready
    registry = review_evidence.ProviderRegistry()
    registry.register(provider)
    with review_evidence.ProviderRuntime(registry).bound():
        result = review_channels.describe()
    for stage in result['stages']:
        for channel in stage['channels'][1:]:
            assert channel['receipt_status'] == expected
            assert channel['status'] == ('unsupported' if stage['stage'] == 'original_image_expression' else expected)
            assert not channel['execution_verified']


def test_capabilities_embeds_discovery_without_upgrading_receipt_flags(monkeypatch):
    monkeypatch.setattr(native_review_transport.shutil, 'which', lambda _: '/synthetic/codex')
    result = capabilities.describe()
    assert result['review_channels']['stages'][0]['channels'][0]['status'] == 'not_verified'
    assert not result['independent_review_receipts']
    assert result['review_channel_status'] == 'needs_reviewer'
    assert result['review_channel_status_scope'].startswith('registered_receipts_only')


def test_cli_discovery_is_read_only_and_never_starts_a_session(monkeypatch, capsys):
    from deck_master import native_review
    monkeypatch.setattr(native_review, 'run', lambda *a, **k:
                        (_ for _ in ()).throw(AssertionError('no review during discovery')))
    assert cli.main(['review', 'channels']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['schema_version'] == 'review_channel_discovery.v1'
    assert result['status'] == 'described'


def test_failed_execution_is_preserved_separately_from_channel_health(tmp_path, monkeypatch):
    from deck_master import native_review
    from test_native_review import FixtureSession
    from test_content_preproduction_review import _deck
    project, store = _deck(tmp_path)
    FixtureSession.calls = []
    FixtureSession.status = 'pass'
    FixtureSession.corrupt = True
    FixtureSession.before_finish = None
    monkeypatch.setattr(native_review, 'CodexReviewSession', FixtureSession)
    try:
        with pytest.raises(review_evidence.EvidenceRejected):
            native_review.run(project)
    finally:
        FixtureSession.corrupt = False
    before = store.load_document()
    result = review_channels.describe(project=project)
    assert store.load_document() == before
    assert len(result['native_executions']) == 1
    assert result['native_executions'][0]['status'] == 'failed'
    assert result['native_executions'][0]['error_code'] == 'native_review_failed'
    assert len(FixtureSession.calls) == 1
