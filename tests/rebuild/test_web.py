"""T14 web-layer evidence: one current revision across entries (AC-U02),
local service behaviour (AC-U03), and write-interface safety (AC-U06)."""
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import deck_master.cli as cli
import deck_master.service as service
from deck_master.editing import edit_page, review_status
from deck_master.models import bump_revision
from deck_master.store import Store
from deck_master.web import WorkbenchServer, open_view, stop_service

SPEC_DIR = Path(__file__).resolve().parents[2] / "docs" / "specs" / "deck-master-rebuild-v1"
ENVELOPES = SPEC_DIR / "examples" / "roundtrips" / "result-envelope"


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, dict(response.headers), response.read()


def _get_json(url):
    try:
        status, headers, body = _get(url)
        return status, headers, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, {}, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, {}, {"error": str(exc)}


def _post_json(url, payload, token=None, origin=None):
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    if token is not None:
        request.add_header("X-Deck-Token", token)
    if origin is not None:
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _session_token(url):
    return _get_json(f"{url}/api/session")[2]["token"]


def _compose_pending_project(tmp_path):
    material = tmp_path / "material.txt"
    material.write_text("工作台材料\n(尾部约束)合成数据不可回写。", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="工作台", sources=[material])
    response = service.continue_project(project)
    return project, response["pending_tasks"][0]


def _adopted_project(tmp_path):
    project, task = _compose_pending_project(tmp_path)
    envelope = json.loads((ENVELOPES / "compose.json").read_text())
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload=envelope)
    return project, Store(project)


def _fabricate_fail_review(store, document):
    review = {
        "schema_version": "deck_review.v1", "review_id": "rv-web-fail", "kind": "conversion",
        "status": "fail",
        "subjects": [document["outputs"]["pptx"], document["pages"][0]["page"]],
        "dependencies": [{"kind": "content", "identity": "page:p09",
                          "sha256": document["pages"][0]["page"]["sha256"]}],
        "reviewer": {"type": "host_self", "id": "host-1", "execution_ref": None,
                     "independence_confirmed": False},
        "observations": ["工程测试"],
        "findings": [{"finding_id": "f-web-1", "kind": "conversion", "impact": "must_fix",
                      "page_id": "p09", "element_refs": ["atom:p09:title"],
                      "message": "标题缺失", "expected": "有标题", "actual": "空",
                      "evidence": [], "resolution": "open"}],
        "created_at": "2026-09-21T00:00:00Z", "replaces": None,
    }
    ref = store.put_json_object(review)
    bumped = bump_revision(document, {"operation_id": "add-fail-review", "kind": "task_update",
                                      "description": "fail review", "read_set": []})
    bumped["reviews"] = list(bumped.get("reviews") or []) + [ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped,
                        operation_id="add-fail-review")


@pytest.fixture()
def server(tmp_path):
    project, store = _adopted_project(tmp_path)
    instance = WorkbenchServer(project)
    url = instance.start().rstrip("/")
    try:
        yield url, project, store
    finally:
        instance.stop()


# ---------------------------------------------------------------------------
# AC-U02: one current revision and one check interpretation everywhere.


def test_view_revision_matches_document_and_follows_edits(server):
    url, project, store = server
    _, _, view = _get_json(f"{url}/api/view")
    assert view["revision_id"] == store.load_document()["revision_id"]

    document = store.load_document()
    page = store.read_object_json(document["pages"][0]["page"])
    page["customer_visible"]["title"] = "工作台修订标题"
    edit_page(store.project_root, page=page, base_revision=document["revision_id"],
              page_hash=document["pages"][0]["page"]["sha256"], operation_id="web-edit-1")
    _, _, updated = _get_json(f"{url}/api/view")
    assert updated["revision_id"] == store.load_document()["revision_id"]
    assert updated["revision_id"] != view["revision_id"]
    assert updated["pages"][0]["title"] == "工作台修订标题"
    # The web status uses the same review interpretation as editing/export.
    assert (updated["view_status"] == "ready_for_export") == \
        (review_status(store, store.load_document()) == "pass")


def test_view_status_tracks_review_interpretation(server):
    url, project, store = server
    work = store.staging_dir / "web-pptx"
    work.mkdir(parents=True, exist_ok=True)
    pptx_file = work / "deck.pptx"
    pptx_file.write_bytes(b"web-pptx")
    from deck_master.pipeline import artifact as adopt_artifact
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "attach-pptx", "kind": "task_update",
                                      "description": "outputs", "read_set": []})
    bumped["outputs"]["pptx"] = adopt_artifact(store, pptx_file, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-pptx")
    _fabricate_fail_review(store, store.load_document())

    _, _, view = _get_json(f"{url}/api/view")
    document = store.load_document()
    assert review_status(store, document) == "fail"
    assert view["view_status"] == "awaiting_review", \
        "web must not show ready while the shared interpretation says fail"
    assert view["reviews"][0]["findings"][0]["page_id"] == "p09"
    assert view["reviews"][0]["findings"][0]["element_refs"] == ["atom:p09:title"]
    assert view["reviews"][0]["page_ids"] == ["p09"], "findings are addressable per page"


# ---------------------------------------------------------------------------
# AC-U03: local service — auto open, reuse, real URL without a browser,
# failure as null plus reason.


def test_cli_accept_auto_opens_workbench_after_first_content(tmp_path, monkeypatch, capsys):
    project, task = _compose_pending_project(tmp_path)
    result_file = tmp_path / "compose-result.json"
    result_file.write_text((ENVELOPES / "compose.json").read_text())
    opened = []
    monkeypatch.setattr("deck_master.web.webbrowser.open", lambda url, new=0: opened.append(url))
    try:
        exit_code = cli.main([
            "task", "accept", "--project", str(project),
            "--task-id", task["task_id"], "--operation-id", task["operation_id"],
            "--produced-against", task["produced_against"], "--result", str(result_file),
        ])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["review_url"], "first content triggers the automatic workbench URL"
        assert payload["view_status"] == "opened"
        assert opened and opened[0] == payload["review_url"]
        # The service is real and healthy without any further user command.
        status, _, health = _get_json(payload["review_url"].rstrip("/") + "/api/health")
        assert status == 200 and health["status"] == "ok"
    finally:
        stop_service(project)


def test_open_view_returns_real_url_without_browser(tmp_path, monkeypatch):
    project, _ = _compose_pending_project(tmp_path)
    monkeypatch.setattr("deck_master.web.webbrowser.open",
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no browser")))
    try:
        info = open_view(project, open_browser=True)
        assert info["review_url"], "a missing browser must not lose the real local URL"
        assert info["view_status"] == "opened"
    finally:
        stop_service(project)


def test_open_view_service_failure_is_null_with_reason(tmp_path, monkeypatch):
    project, _ = _compose_pending_project(tmp_path)

    def _boom(*args, **kwargs):
        raise OSError("spawn refused")

    monkeypatch.setattr("subprocess.Popen", _boom)
    info = open_view(project, open_browser=False)
    assert info["review_url"] is None
    assert info["view_status"] == "unavailable"
    assert "spawn refused" in info["detail"]


def test_web_server_layer_reuses_running_service_url(tmp_path):
    project, _ = _adopted_project(tmp_path)
    first = WorkbenchServer(project)
    second = WorkbenchServer(project)
    try:
        first_url = first.start().rstrip("/")
        second_url = second.start().rstrip("/")
        assert second_url == first_url, "web layer reuses the healthy same-project service"
    finally:
        first.stop()


# ---------------------------------------------------------------------------
# AC-U06: write safety — same-origin token, path whitelist, XSS handling.


def test_writes_require_same_origin_session_token(server):
    url, project, store = server
    token = _session_token(url)
    payload = {"page_id": "p09", "instruction": "把标题改短", "base_revision": store.load_document()["revision_id"]}

    status, _ = _post_json(f"{url}/api/feedback", payload)
    assert status == 403, "write without the session token is refused"
    status, _ = _post_json(f"{url}/api/feedback", payload, token=token, origin="http://evil.example")
    assert status == 403, "cross-origin write is refused"
    status, body = _post_json(f"{url}/api/feedback", payload, token=token,
                              origin=f"http://127.0.0.1:{url.rsplit(':', 1)[1]}")
    assert status == 200 and body["status"] == "awaiting_host"
    # Read-only browsing needs no account and no token.
    status, _, _ = _get(f"{url}/api/view")
    assert status == 200


def test_file_route_whitelists_registered_project_objects(server):
    url, project, store = server
    _, _, view = _get_json(f"{url}/api/view")
    ref = view["pages"][0]["slots"]["content"]
    status, headers, body = _get(f"{url}/api/file?path={ref['path']}&sha256={ref['sha256']}")
    assert status == 200 and json.loads(body)["page_id"] == "p09"
    # Traversal and absolute paths never resolve.
    for bad in ("../../etc/passwd", "/etc/passwd", ".deckmaster/objects/../revisions/x.json"):
        status, _, body = _get_json(f"{url}/api/file?path={urllib.parse.quote(bad)}&sha256=x")
        assert status in (403, 404), (bad, status, body)
    # A registered-object path with a wrong hash is refused (no byte guessing).
    status, _, _ = _get_json(f"{url}/api/file?path={ref['path']}&sha256={'0' * 64}")
    assert status == 404


def test_user_text_is_served_as_data_not_markup(server):
    url, project, store = server
    document = store.load_document()
    page = store.read_object_json(document["pages"][0]["page"])
    page["customer_visible"]["title"] = "<img src=x onerror=alert(1)>"
    edit_page(store.project_root, page=page, base_revision=document["revision_id"],
              page_hash=document["pages"][0]["page"]["sha256"], operation_id="xss-title")
    status, headers, body = _get(f"{url}/api/view")
    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    assert headers["X-Content-Type-Options"] == "nosniff"
    payload = json.loads(body.decode("utf-8"))
    assert payload["pages"][0]["title"] == "<img src=x onerror=alert(1)>"
    # The served UI renders user text through textContent, not HTML injection.
    _, _, app_js = _get(f"{url}/app.js")
    script = app_js.decode("utf-8")
    assert "textContent" in script
    assert "insertAdjacentHTML" not in script
    for line in script.splitlines():
        if "innerHTML" in line and "=" in line:
            assert '""' in line or "''" in line or "replaceChildren" in line, \
                "innerHTML is only used to clear containers, never to inject user text"
    # SVG previews are served sandboxed.
    work = store.staging_dir / "svg-xss"
    work.mkdir(parents=True, exist_ok=True)
    svg_file = work / "page.svg"
    svg_file.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>')
    from deck_master.pipeline import artifact as adopt_artifact
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "attach-svg", "kind": "task_update",
                                      "description": "svg", "read_set": []})
    bumped["pages"][0]["svg"] = adopt_artifact(store, svg_file, "svg", page_id="p09")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-svg")
    _, _, view = _get_json(f"{url}/api/view")
    status, headers, body = _get(f"{url}/api/file?path={view['pages'][0]['slots']['svg']['path']}"
                                 f"&sha256={view['pages'][0]['slots']['svg']['sha256']}")
    assert status == 200
    assert "sandbox" in headers.get("Content-Security-Policy", "")


import urllib.parse  # noqa: E402  (used by the whitelist test above)
