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
