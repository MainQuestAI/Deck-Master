"""T05 workbench end-to-end tests (AC-U01 engineering part; T14 closes).

A real server against a real project: page counts come from the Document,
missing slots wait explicitly, zero pages show zero, and failed pages stay
visible. No preview manifest exists anywhere in the new core.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

import deck_master.service as service
from deck_master.web import WorkbenchServer, open_view

SPEC_DIR = Path(__file__).resolve().parents[2] / "docs" / "specs" / "deck-master-rebuild-v1"
ENVELOPES = SPEC_DIR / "examples" / "roundtrips" / "result-envelope"


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _prepared_project(tmp_path: Path) -> tuple[Path, str]:
    material = tmp_path / "material.txt"
    material.write_text("正文材料\n(尾部约束)合成数据不可回写。", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="设备运维汇报", sources=[material])
    response = service.continue_project(project)
    task = response["pending_tasks"][0]
    envelope = json.loads((ENVELOPES / "compose.json").read_text())
    service.accept_result(
        project,
        task_id=task["task_id"],
        operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload=envelope,
    )
    return project, "p09"


def test_view_reads_real_pages_without_preview_manifest(tmp_path: Path) -> None:
    """AC-U01: page counts come from the Document, not from any preview manifest."""
    project, page_id = _prepared_project(tmp_path)
    assert not (project / "preview_manifest.json").exists()
    view = _load_view(project)
    assert view["page_count"] == 1
    assert view["pages"][0]["page_id"] == page_id
    assert view["pages"][0]["slots"]["content"]["path"].startswith(".deckmaster/objects/")
    assert view["view_status"] == "content_ready_for_review"


def _load_view(project: Path) -> dict:
    from deck_master.view import project_view

    return project_view(project)


def test_zero_page_project_shows_zero_and_awaiting(tmp_path: Path) -> None:
    material = tmp_path / "brief.txt"
    material.write_text("简报内容", encoding="utf-8")
    project = tmp_path / "proj0"
    service.create(project, brief="空稿项目", sources=[material])
    view = _load_view(project)
    assert view["page_count"] == 0
    assert view["view_status"] == "awaiting_host"
    assert view["pending_tasks"], "the pending compose task stays visible"


def test_missing_slots_wait_explicitly(tmp_path: Path) -> None:
    project, _ = _prepared_project(tmp_path)
    view = _load_view(project)
    slots = view["pages"][0]["slots"]
    assert slots["blueprint"] is None
    assert slots["svg"] is None
    assert slots["ppt_preview"] is None
    assert slots["content"] is not None


def test_server_serves_real_data_and_files(tmp_path: Path) -> None:
    project, _ = _prepared_project(tmp_path)
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        health = _get_json(f"{url}/api/health")
        assert health["status"] == "ok"
        payload = _get_json(f"{url}/api/view")
        assert payload["page_count"] == 1
        assert payload["pages"][0]["slots"]["content"]["path"].startswith(".deckmaster/objects/")
        # File serving verifies the declared hash.
        ref = payload["pages"][0]["slots"]["content"]
        with urllib.request.urlopen(f"{url}/api/file?path={ref['path']}&sha256={ref['sha256']}", timeout=5) as response:
            body = response.read()
        assert json.loads(body)["page_id"] == "p09"
        # Non-object paths are refused.
        try:
            urllib.request.urlopen(f"{url}/api/file?path=../../etc/passwd&sha256=x", timeout=5)
            raised = False
        except Exception:
            raised = True
        assert raised, "path outside .deckmaster/objects must be refused"
    finally:
        server.stop()


def test_service_reuse_returns_same_url(tmp_path: Path) -> None:
    project, _ = _prepared_project(tmp_path)
    try:
        first = open_view(project, open_browser=False)
        second = open_view(project, open_browser=False)
        assert first["review_url"]
        assert second["review_url"] == first["review_url"], "same project reuses the running service"
        assert second["reused"] is True
    finally:
        from deck_master.web import stop_service

        stop_service(project)
        # The detached process must be gone after the explicit stop.
        import urllib.request

        try:
            urllib.request.urlopen(first["review_url"].rstrip("/") + "/api/health", timeout=1)
            still_up = True
        except Exception:
            still_up = False
        assert not still_up, "stop_service must terminate the detached server"


def test_view_without_document_reports_unavailable(tmp_path: Path) -> None:
    response = open_view(tmp_path / "no-such-project", open_browser=False)
    assert response["review_url"] is None
    assert response["view_status"] == "unavailable"


# ---------------------------------------------------------------------------
# T14 additions: four real view slots with addressing (AC-U04), honest
# awaiting_host state (AC-U05), and usable-layout engineering evidence
# (AC-U07; browser screenshots remain the 2026-09-16 manual evidence).


def _four_slot_project(tmp_path: Path):
    from deck_master.store import Store
    project, _ = _prepared_project(tmp_path)
    store = Store(project)
    from deck_master.models import bump_revision
    from deck_master.pipeline import artifact as adopt_artifact
    import io
    from PIL import Image

    work = store.staging_dir / "slots"
    work.mkdir(parents=True, exist_ok=True)
    png = work / "art.png"
    Image.new("RGB", (24, 16), (18, 33, 61)).save(png)
    svg = work / "page.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 16"><rect width="24" height="16"/></svg>')
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "attach-slots", "kind": "task_update",
                                      "description": "four slots", "read_set": []})
    entry = bumped["pages"][0]
    entry["blueprint"] = adopt_artifact(store, png, "blueprint", page_id="p09")
    entry["svg"] = adopt_artifact(store, svg, "svg", page_id="p09")
    entry["svg_preview"] = adopt_artifact(store, png, "svg_preview", page_id="p09")
    entry["ppt_preview"] = adopt_artifact(store, png, "ppt_preview", page_id="p09")
    bumped["outputs"]["pptx"] = adopt_artifact(store, png, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-slots")
    return project, Store(project)


def _fetch_file(url: str, ref: dict):
    with urllib.request.urlopen(
            f"{url}/api/file?path={urllib.parse.quote(ref['path'])}&sha256={ref['sha256']}", timeout=5) as response:
        return response.read()


import urllib.parse  # noqa: E402


def test_four_view_slots_serve_real_files_with_revision(tmp_path: Path) -> None:
    """AC-U04: content/blueprint/svg/ppt slots serve the registered object
    bytes, and the view carries the current revision for every slot."""
    project, store = _four_slot_project(tmp_path)
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        view = _get_json3(f"{url}/api/view")
        document = store.load_document()
        assert view["revision_id"] == document["revision_id"]
        slots = view["pages"][0]["slots"]
        for name in ("content", "blueprint", "svg", "ppt_preview"):
            ref = slots[name]
            assert ref, f"slot {name} must reference a registered object"
            body = _fetch_file(url, ref)
            obj = store.read_object_json(ref)
            expected = store.read_object_bytes(obj["file"]) if "file" in obj else store.read_object_bytes(ref)
            assert body == expected, f"slot {name} serves the real bytes"
        # Problem records carry page/element addressing for UI navigation.
        assert view["reviews"] or view["pages"][0]["visible_atoms"], "addressable content present"
    finally:
        server.stop()


def test_review_findings_are_addressable_to_page_and_element(tmp_path: Path) -> None:
    project, store = _four_slot_project(tmp_path)
    from deck_master.models import bump_revision
    document = store.load_document()
    review = {
        "schema_version": "deck_review.v1", "review_id": "rv-e2e", "kind": "readability",
        "status": "fail",
        "subjects": [document["outputs"]["pptx"], document["pages"][0]["page"]],
        "dependencies": [{"kind": "content", "identity": "page:p09",
                          "sha256": document["pages"][0]["page"]["sha256"]}],
        "reviewer": {"type": "host_self", "id": "host-1", "execution_ref": None,
                     "independence_confirmed": False},
        "observations": ["工程记录"],
        "findings": [{"finding_id": "f-e2e", "kind": "readability", "impact": "must_fix",
                      "page_id": "p09", "element_refs": ["atom:p09:block:service:heading"],
                      "message": "字号过小", "expected": "≥10pt", "actual": "6pt",
                      "evidence": [], "resolution": "open"}],
        "created_at": "2026-09-21T00:00:00Z", "replaces": None,
    }
    ref = store.put_json_object(review)
    bumped = bump_revision(document, {"operation_id": "add-review", "kind": "task_update",
                                      "description": "review", "read_set": []})
    bumped["reviews"] = [ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="add-review")
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        view = _get_json3(f"{url}/api/view")
        finding = view["reviews"][0]["findings"][0]
        assert finding["page_id"] == "p09"
        assert finding["element_refs"] == ["atom:p09:block:service:heading"]
        assert view["reviews"][0]["page_ids"] == ["p09"]
    finally:
        server.stop()


def _get_json3(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(url: str, payload: dict, token: str):
    import json as _json
    request = urllib.request.Request(
        url, data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Deck-Token": token,
                 "Origin": f"http://127.0.0.1:{url.split(':')[2].split('/')[0]}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return _json.loads(response.read().decode("utf-8"))


def test_feedback_stays_awaiting_host_until_real_execution(tmp_path: Path) -> None:
    """AC-U05: UI feedback records a task in awaiting_host (never fake
    running); execution state and the revision move only after a real
    task_start/accept."""
    from deck_master.store import Store
    project, _ = _prepared_project(tmp_path)
    store = Store(project)
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        token = _get_json3(f"{url}/api/session")["token"]
        result = _post(f"{url}/api/feedback",
                       {"page_id": "p09", "instruction": "把辅助说明移到脚注",
                        "base_revision": store.load_document()["revision_id"]}, token)
        assert result["status"] == "awaiting_host"
        view = _get_json3(f"{url}/api/view")
        pending = [t for t in view["pending_tasks"] if t["task_id"] == result["task_id"]]
        assert pending and pending[0]["status"] == "awaiting_host", "no fake running"
        # Real execution claim moves the task to running in the same view.
        service.task_start(project, task_id=result["task_id"], execution_ref="exec-e2e")
        running_view = _get_json3(f"{url}/api/view")
        running = [t for t in running_view["pending_tasks"] if t["task_id"] == result["task_id"]]
        assert running and running[0]["status"] == "running"
        before_revision = running_view["revision_id"]
        # A real repair result advances the revision and clears the pending task.
        page = store.read_object_json(store.load_document()["pages"][0]["page"])
        task = store.load_document()
        import copy
        changed = copy.deepcopy(page)
        changed["customer_visible"]["footnotes"] = [{"id": "fn-1", "text": "辅助说明。"}]
        service.accept_result(project, task_id=result["task_id"],
                              operation_id=next(t["operation_id"] for t in [store.read_object_json(r) for r in task["tasks"]] if t["task_id"] == result["task_id"]),
                              produced_against=next(t["produced_against"] for t in [store.read_object_json(r) for r in task["tasks"]] if t["task_id"] == result["task_id"]),
                              result_payload={"kind": "repair", "files": [], "pages": [changed]})
        after_view = _get_json3(f"{url}/api/view")
        assert after_view["revision_id"] != before_revision
        assert all(t["task_id"] != result["task_id"] for t in after_view["pending_tasks"])
    finally:
        server.stop()


def test_static_assets_carry_keyboard_zoom_and_text_status(tmp_path: Path) -> None:
    """AC-U07 engineering part: keyboard page switching, comparison zoom
    controls and non-colour status text ship in the served assets."""
    project, _ = _prepared_project(tmp_path)
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        _, _, app_js = _get_raw(f"{url}/app.js")
        script = app_js.decode("utf-8")
        assert 'addEventListener("keydown"' in script and "ArrowRight" in script and "ArrowLeft" in script
        assert "zoom-in" in script and "zoom-fit" in script and "applyZoom" in script
        _, _, html = _get_raw(f"{url}/index.html")
        page = html.decode("utf-8")
        assert 'id="zoom-in"' in page and 'id="zoom-fit"' in page and 'id="zoom-out"' in page
        assert 'role="status"' in page and "aria-live" in page
        assert 'role="tablist"' in page and "aria-selected" in page
        _, _, css = _get_raw(f"{url}/style.css")
        assert b".zoom-bar" in css
    finally:
        server.stop()


def _get_raw(url: str) -> tuple:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, dict(response.headers), response.read()
