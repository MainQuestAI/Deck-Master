"""Synthetic L1 transport/normal-entry regressions, not live model evidence."""
from copy import deepcopy
import fcntl
import json
import os
import subprocess
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from deck_master import cli, content_review, native_review, review_evidence, service, tasks
from deck_master.store import Store
from deck_master.web import WorkbenchServer
from test_content_preproduction_review import _deck


class FixtureSession:
    calls = []
    status = "pass"
    corrupt = False
    before_finish = None

    def __init__(self):
        self.thread_id = str(uuid.uuid4())
        self.turn_id = None
        self.ready = True

    @property
    def execution_ref(self):
        return "codex-native:" + self.thread_id

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.ready = False

    def review(self, prompt, schema):
        self.calls.append(json.loads(prompt.split("JSON input follows:\n")[1]))
        if type(self).before_finish:
            type(self).before_finish()
        self.turn_id = str(uuid.uuid4())
        rows = [{"kind": unit, "status": self.status, "observations": ["Synthetic L1 judgment"],
                 "findings": [], "replaces": None} for unit in self.calls[-1]["packet"]["required_units"]]
        return {"schema_version": "native_review_observation.v1", "thread_id": self.thread_id,
                "turn_id": self.turn_id, "status": "completed", "model": "synthetic-fixture",
                "item_id": "fixture-item", "transport": "synthetic-L1-only",
                "raw_final_message": "not-json" if self.corrupt else json.dumps({"reviews": rows})}


@pytest.fixture
def native(monkeypatch):
    FixtureSession.calls = []
    FixtureSession.status = "pass"
    FixtureSession.corrupt = False
    FixtureSession.before_finish = None
    monkeypatch.setattr(native_review, "CodexReviewSession", FixtureSession)
    return FixtureSession


def _review_task(store):
    return next(task for ref in reversed(store.load_document()["tasks"])
                if (task := store.read_object_json(ref)).get("review_stage") == "preproduction")


def test_normal_runner_receipt_survives_native_process_and_replay_is_no_call(tmp_path, native):
    project, store = _deck(tmp_path)
    assert content_review.qualify_for_production(store, store.load_document())["needs_reviewer"]
    before = deepcopy(store.load_document())
    result = native_review.run(project)
    assert result["status"] == "reviewed"
    assert result["preproduction"]["status"] == "pass"
    after = store.load_document()
    for key in ("narrative", "content_plan", "pages", "outputs", "design_context"):
        assert after.get(key) == before.get(key)
    sent = native.calls[0]
    assert len(sent["packet"]["manuscript"]["pages"]) == 2
    assert sent["packet"]["materials"][0]["extract"]
    assert sent["methods"] and all(item["content"] for item in sent["methods"])
    task = _review_task(store)
    assert task["status"] == "completed"
    proof = next(obj for ref in task["result_refs"]
                 if (obj := store.read_object_json(ref)).get("schema_version") == "authenticated_review_receipt.v1")
    assert proof["claims"]["executor_ref"] == result["execution_ref"]
    assert proof["claims"]["packet_sha256"]
    assert proof["claims"]["author_execution_refs"]
    assert proof["claims"]["assurance"] == "host_attested"
    assert not review_evidence.current_registry().capabilities()["independent_review_receipts"]
    assert content_review.qualify_for_production(store, store.load_document())["status"] == "pass"
    continued = subprocess.run([sys.executable, '-I', '-m', 'deck_master', 'continue', '--project', str(project), '--json'],
                               capture_output=True, text=True, cwd=tmp_path, timeout=30)
    assert continued.returncode in (0, 3), continued.stderr
    current = json.loads(continued.stdout)
    assert 'needs_reviewer' not in current.get('reason_codes', [])
    assert current['status'] != 'needs_reviewer'
    assert native_review.run(project)["status"] == "already_reviewed"
    assert len(native.calls) == 1


def test_cli_normal_native_entry(tmp_path, native, capsys):
    project, _ = _deck(tmp_path)
    assert cli.main(["review", "native", "--project", str(project)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["preproduction"]["status"] == "pass"


def test_failed_judgments_do_not_become_pass(tmp_path, native):
    project, store = _deck(tmp_path)
    native.status = "fail"
    result = native_review.run(project)
    assert result["preproduction"]["status"] != "pass"
    assert _review_task(store)["status"] == "completed"
    assert content_review.qualify_for_production(store, store.load_document())["status"] != "pass"


def test_invalid_output_marks_failure_and_only_explicit_retry_calls_again(tmp_path, native):
    project, store = _deck(tmp_path)
    native.corrupt = True
    with pytest.raises(review_evidence.EvidenceRejected, match="native final output"):
        native_review.run(project)
    assert _review_task(store)["status"] == "failed"
    assert content_review.preproduction_status(store, store.load_document())["status"] != "pass"
    native.corrupt = False
    assert native_review.run(project)["preproduction"]["status"] == "pass"
    assert len(native.calls) == 2


def test_cancellation_during_native_turn_never_adopts_output(tmp_path, native):
    project, store = _deck(tmp_path)
    native.before_finish = lambda: service.task_cancel(project, task_id=_review_task(store)["task_id"])
    with pytest.raises(tasks.TaskConflict):
        native_review.run(project)
    assert _review_task(store)["status"] == "cancelled"
    assert not store.load_document().get("reviews")


def test_running_task_and_concurrent_operation_cannot_launch_again(tmp_path, native):
    project, store = _deck(tmp_path)
    handle = os.open(store.deck_root / "native-review.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert native_review.run(project)["status"] == "running"
        assert not native.calls
    finally:
        os.close(handle)
    native.before_finish = lambda: (_ for _ in ()).throw(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        native_review.run(project)
    assert _review_task(store)["status"] == "running"
    assert native_review.run(project)["status"] == "running"
    assert len(native.calls) == 1


def test_unavailable_native_never_creates_fake_task_or_receipt(tmp_path, monkeypatch):
    project, store = _deck(tmp_path)
    before = store.current_revision_id()
    def unavailable():
        raise review_evidence.ProviderUnavailable("native_review", "not connected")
    monkeypatch.setattr(native_review, "CodexReviewSession", unavailable)
    with pytest.raises(review_evidence.ProviderUnavailable):
        native_review.run(project)
    assert store.current_revision_id() == before


def test_workbench_requires_token_and_rejects_claims_or_caller_paths(tmp_path, native):
    project, store = _deck(tmp_path)
    server = WorkbenchServer(project)
    base = server.start().rstrip('/')
    try:
        token = json.load(urlopen(base + '/api/session'))['token']
        def post(body, token_value=token):
            req = Request(base + '/api/reviews/native', json.dumps(body).encode(),
                          {'Content-Type': 'application/json', 'X-Deck-Token': token_value, 'Origin': base})
            return json.load(urlopen(req))
        with pytest.raises(HTTPError) as missing:
            post({}, 'invalid')
        assert missing.value.code == 403
        for body in ({'raw_final_message': '{}'}, {'project': '/tmp/elsewhere'}, {'claims': {'verified': True}},
                     *({'force_units': value} for value in ([], ['unknown'], ['argument', 'argument'], 'argument', [None]))):
            with pytest.raises(HTTPError) as rejected:
                post(body)
            assert rejected.value.code == 422
        assert not native.calls
        assert post({})['preproduction']['status'] == 'pass'
        assert content_review.qualify_for_production(store, store.load_document())['status'] == 'pass'
    finally:
        server.stop()


def test_full_forced_review_does_not_reuse_live_single_page_task(tmp_path, native):
    from synthetic_review_provider import dispatch_with_synthetic_provider
    from test_content_preproduction_review import _independent_adapter
    project, store = _deck(tmp_path)
    narrow = dispatch_with_synthetic_provider(project, page_ids=['p1'],
        adapter_context=_independent_adapter(store, store.load_document()), force_units=['argument'])['task']
    assert narrow['scope_pages'] == ['p1']
    assert native_review.run(project, task_id=narrow['task_id'])['status'] == 'running'
    assert not native.calls
    result = native_review.run(project, force_units=['argument'])
    assert result['status'] == 'reviewed'
    full = _review_task(store)
    assert full['task_id'] != narrow['task_id']
    assert set(full['scope_pages']) == {'p1', 'p2'}
    assert {page['page_id'] for page in native.calls[0]['packet']['manuscript']['pages']} == {'p1', 'p2'}
    assert tasks._lookup_task(store.load_document(), narrow['task_id'], store)['status'] == 'running'


@pytest.mark.parametrize('selection', [['unknown'], ['argument', 'argument']])
def test_cli_rejects_invalid_forced_units_before_native_call(tmp_path, native, capsys, selection):
    project, store = _deck(tmp_path)
    before = store.read_current()
    args = ['review', 'native', '--project', str(project)]
    for unit in selection:
        args.extend(['--force-unit', unit])
    assert cli.main(args) != 0
    assert not native.calls
    assert store.read_current() == before
    capsys.readouterr()
