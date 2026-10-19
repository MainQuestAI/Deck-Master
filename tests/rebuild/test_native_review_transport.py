"""Synthetic JSON-RPC event sequences; these are not actual native reviews."""
import json
import queue
import subprocess

import pytest

from deck_master import native_review_transport as transport
from deck_master.review_evidence import EvidenceRejected, ProviderUnavailable


class _Pipe:
    def __init__(self):
        self.lines = queue.Queue()

    def put(self, value):
        self.lines.put(json.dumps(value).encode() + b'\n')

    def readline(self, limit):
        return self.lines.get()

    def close(self):
        pass


class _Input:
    def __init__(self, process):
        self.process = process

    def write(self, raw):
        message = json.loads(raw)
        self.process.sent.append(message)
        method = message.get('method')
        if method == 'initialize':
            self.process.response(message, {})
        elif method == 'config/read':
            self.process.response(message, {'config': {'mcp_servers': {
                name: {'command': '/fixture/must-not-run', 'args': []}
                for name in ('ordinary', 'name.with.dots', 'name"quoted', '名称 with space')}}})
        elif method == 'thread/start':
            self.process.response(message, {'thread': {'id': 'fixture-native-thread'},
                'modelProvider': self.process.provider, 'model': 'fixture-model',
                'sandbox': {'type': 'readOnly', 'networkAccess': False}, 'approvalPolicy': 'never'})
        elif method == 'turn/start':
            self.process.response(message, {'turn': {'id': 'fixture-native-turn'}})
            for event in self.process.events:
                self.process.stdout.put(event)

    def flush(self):
        pass

    def close(self):
        pass


class _Process:
    provider = 'openai'

    def __init__(self, *args, **kwargs):
        self.stdout = _Pipe()
        self.stdin = _Input(self)
        self.sent = []
        self.code = None
        self.arguments = args[0]
        self.options = kwargs
        self.events = []

    def response(self, request, result):
        self.stdout.put({'id': request['id'], 'result': result})

    def poll(self):
        return self.code

    def terminate(self):
        self.code = 0
        self.stdout.lines.put(b'')

    def wait(self, timeout):
        return self.code


@pytest.fixture
def native_process(monkeypatch):
    process = _Process(['fixture'])
    monkeypatch.setattr(transport.shutil, 'which', lambda _: '/fixture/codex')
    monkeypatch.setattr(transport.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess(a, 0, b'', b'Logged in using ChatGPT'))
    def start(*a, **k):
        process.arguments, process.options = a[0], k
        return process
    monkeypatch.setattr(transport.subprocess, 'Popen', start)
    return process


def _final(*, thread='fixture-native-thread', turn='fixture-native-turn', phase='final_answer'):
    return {'method': 'item/completed', 'params': {'threadId': thread, 'turnId': turn,
            'item': {'type': 'agentMessage', 'id': 'fixture-message', 'phase': phase, 'text': '{"reviews":[]}'}}}


def _completed(*, status='completed'):
    return {'method': 'turn/completed', 'params': {'threadId': 'fixture-native-thread',
            'turn': {'id': 'fixture-native-turn', 'status': status, 'error': None}}}


def test_owned_transport_starts_fresh_restricted_thread_and_observes_final(native_process):
    native_process.events = [_final(), _completed()]
    with transport.CodexReviewSession() as session:
        assert session.execution_ref == 'codex-native:fixture-native-thread'
        result = session.review('complete packet and frozen methods', {'type': 'object'})
        assert result['raw_final_message'] == '{"reviews":[]}'
        assert result['turn_id'] == 'fixture-native-turn'
        assert session.ready
    assert not session.ready
    thread = next(item['params'] for item in native_process.sent if item.get('method') == 'thread/start')
    assert thread['sandbox'] == 'read-only'
    assert thread['approvalPolicy'] == 'never'
    assert thread['ephemeral'] is True
    assert thread['config']['mcp_servers'] == {
        name: {'enabled': False}
        for name in ('ordinary', 'name.with.dots', 'name"quoted', '名称 with space')}
    assert not any(key.startswith('mcp_servers.') for key in thread['config'])
    for key in ('shell_tool', 'unified_exec', 'apps', 'multi_agent', 'hooks', 'plugins', 'browser_use', 'computer_use'):
        assert thread['config']['features.' + key] is False
    assert 'modelProvider' not in thread and 'model' not in thread
    assert native_process.arguments == ['/fixture/codex', 'app-server', '--listen', 'stdio://']


@pytest.mark.parametrize('events', [
    [_final(thread='another-thread'), _completed()],
    [_final(turn='another-turn'), _completed()],
    [_final(phase='commentary'), _completed()],
    [_final(), _completed(status='failed')],
    [_final(), _completed(status='interrupted')],
])
def test_unrelated_or_incomplete_native_execution_is_never_accepted(native_process, events):
    native_process.events = events
    with transport.CodexReviewSession() as session:
        with pytest.raises(ProviderUnavailable):
            session.review('fixture', {})


def test_tool_approval_request_is_denied_and_no_receipt_is_returned(native_process):
    native_process.events = [{'id': 100, 'method': 'item/commandExecution/requestApproval', 'params': {}}]
    with transport.CodexReviewSession() as session:
        with pytest.raises(EvidenceRejected, match='requested an action'):
            session.review('fixture', {})
    assert native_process.sent[-1]['error']['code'] == -32601


def test_tool_completion_is_not_a_readonly_model_review(native_process):
    native_process.events = [{'method': 'item/completed', 'params': {'threadId': 'fixture-native-thread',
        'turnId': 'fixture-native-turn', 'item': {'type': 'mcpToolCall', 'id': 'fixture-tool'}}}]
    with transport.CodexReviewSession() as session:
        with pytest.raises(EvidenceRejected, match='used a tool'):
            session.review('fixture', {})


def test_no_api_login_or_external_model_provider_is_selected(native_process, monkeypatch):
    monkeypatch.setattr(transport.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess(a, 0, b'', b'Logged in using an API key'))
    with pytest.raises(ProviderUnavailable, match='ChatGPT-authenticated'):
        with transport.CodexReviewSession():
            pass
    assert not native_process.sent


def test_custom_provider_cannot_be_silently_called(native_process):
    native_process.provider = 'custom-external'
    with pytest.raises(ProviderUnavailable, match='native OpenAI provider'):
        with transport.CodexReviewSession():
            pass
    assert all(item.get('method') != 'turn/start' for item in native_process.sent)
