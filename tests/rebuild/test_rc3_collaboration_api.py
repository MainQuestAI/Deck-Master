"""CLI/HTTP use the same transaction identities and never trust JSON channels."""

import hashlib
import json
import uuid

import pytest

from test_eligibility_enforcement import _project, _scope, _declared
from test_web import _get_json, _post_json, _session_token
from deck_master import cli, collaboration_api
from deck_master.web import WorkbenchServer


def _files(project):
    return {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest() for p in project.rglob("*") if p.is_file()}


def _request(store):
    return {
        "base_revision": store.current_revision_id(),
        "operation_id": str(uuid.uuid4()),
        "request": {
            "intent": "edit",
            "content_intent": "write_only",
            "scope": _scope(page_ids=["p1"], layers=["page_copy", "review"]),
            "instruction_evidence": _declared(store),
        },
    }


def test_cli_read_and_readonly_post_eligibility_preserve_all_project_bytes(tmp_path, capsys):
    project, store = _project(tmp_path)
    before = _files(project)
    assert cli.main(["collaboration", "show", "--project", str(project)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["schema_version"] == "collaboration_response.v1"
    assert shown["result"]["capabilities"]["verified_user_events"] is False
    result, http, code = collaboration_api.invoke(project, "eligibility", {"action": "dispatch.blueprint", "targets": {"page_ids": ["p1"]}})
    assert http == 200 and code == 0
    assert not result["result"]["allowed"]
    assert _files(project) == before


def test_cli_request_and_python_replay_share_exact_operation_and_current_control(tmp_path, capsys):
    project, store = _project(tmp_path)
    data = _request(store)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(data))
    assert cli.main(["collaboration", "request", "start", str(project), "--input", str(path)]) == 0
    first = json.loads(capsys.readouterr().out)
    before = _files(project)
    replay, http, code = collaboration_api.invoke(project, "request.start", data)
    assert (http, code) == (200, 0)
    assert replay["status"] == "already_applied"
    assert replay["result"]["request_id"] == first["result"]["request_id"]
    assert replay["control_revision_id"] == store.current_revision_id()
    assert _files(project) == before


@pytest.mark.parametrize("field", ["adapter_context", "verified_user_events", "independent_review_receipts"])
def test_a_json_payload_cannot_advertise_a_trusted_transport(tmp_path, field):
    project, _ = _project(tmp_path)
    before = _files(project)
    result, http, code = collaboration_api.invoke(project, "show", {field: True})
    assert (http, code) == (403, 4)
    assert result["error"]["code"] == "untrusted_adapter_context"
    assert _files(project) == before


def test_http_project_alias_and_cli_write_return_the_same_facts(tmp_path, capsys):
    project, store = _project(tmp_path)
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        token = _session_token(url)
        data = _request(store)
        endpoint = url + "/api/projects/" + store.load_document()["project_id"] + "/collaboration/requests"
        code, created = _post_json(endpoint, data, token, url)
        assert code == 200, created
        assert created["schema_version"] == "collaboration_response.v1"
        code, _, shown = _get_json(url + "/api/collaboration")
        assert code == 200
        assert shown["result"]["request"]["request_id"] == created["result"]["request_id"]
        assert cli.main(["collaboration", "show", str(project)]) == 0
        from_cli = json.loads(capsys.readouterr().out)
        assert from_cli["result"]["request"] == shown["result"]["request"]
        before = _files(project)
        code, forged = _post_json(url + "/api/collaboration/decisions", {"adapter_context": {"verified_user_events": True}}, token, url)
        assert code == 403 and forged["error"]["code"] == "untrusted_adapter_context"
        assert _files(project) == before
    finally:
        server.stop()
