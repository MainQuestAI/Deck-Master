"""Tests for Review Desk Skill OS view (C1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
if str(REPO_ROOT / "scripts" / "preview") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "preview"))

from skills.manifest import load_registry  # noqa: E402
from workspace_api import (  # noqa: E402
    skill_os_accept_handoff,
    skill_os_projection,
    skill_os_reject_handoff,
)
from workflow.handoff import HandoffRuntime  # noqa: E402

REGISTRY = load_registry()


def _touch(p: Path, content="{}") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _seed_brief(run: Path) -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json"):
        _touch(run / f)
    _touch(run / "deck_brief.json", json.dumps({"thesis": "x"}))
    _touch(run / "claim_map.json", json.dumps({"c": []}))


def test_projection_returns_9_stage_ladder(tmp_path):
    proj = skill_os_projection(tmp_path)
    assert proj["schema_version"] == "deck_review_skill_os_view.v1"
    assert len(proj["stages"]) == 9
    assert proj["current_stage"] == "deck-init"


def test_early_run_no_preview(tmp_path):
    proj = skill_os_projection(tmp_path)
    init = next(s for s in proj["stages"] if s["stage_id"] == "deck-init")
    assert init["status"] in {"ready", "in_progress"}
    # no raw path/command on main view
    body = json.dumps(proj, ensure_ascii=False)
    assert "/Users/" not in body
    assert "deck-master " not in body


def test_awaiting_approval_distinguished_from_blocker(tmp_path):
    _seed_brief(tmp_path)
    proj = skill_os_projection(tmp_path)
    brief = next(s for s in proj["stages"] if s["stage_id"] == "deck-brief")
    assert brief["is_awaiting_approval"] is True
    assert brief["is_blocker"] is False
    assert brief["safe_copy"]["headline"].startswith("需求访谈")


def test_stale_reason_visible(tmp_path):
    import time
    _seed_brief(tmp_path)
    time.sleep(0.02)
    # touch an upstream input to make brief stale via handoff supersede path:
    # we mark the brief handoff stale directly through the runtime
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(tmp_path, "deck-brief", run_id="r")
    h.mark_stale(tmp_path, rec["handoff_id"], reason="upstream changed")
    proj = skill_os_projection(tmp_path)
    # stale reason surfaces somewhere in the projection
    body = json.dumps(proj, ensure_ascii=False)
    assert "上游" in body or "过期" in body or "重新确认" in body


def test_accept_handoff_writes_runtime(tmp_path):
    _seed_brief(tmp_path)
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(tmp_path, "deck-brief", run_id="r")
    assert rec["status"] == "awaiting_approval"
    accepted = skill_os_accept_handoff(tmp_path, rec["handoff_id"], actor="boss")
    assert accepted["status"] == "accepted"


def test_reject_handoff_routes_repair(tmp_path):
    _seed_brief(tmp_path)
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(tmp_path, "deck-brief", run_id="r")
    rejected = skill_os_reject_handoff(
        tmp_path, rec["handoff_id"], actor="boss", reason="bad", repair_owner_stage="deck-brief"
    )
    assert rejected["status"] == "rejected"
    assert rejected["repair_owner_stage"] == "deck-brief"


def test_ready_for_export_stage_present(tmp_path):
    # seed through review
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json",
              "deck_brief.json", "claim_map.json", "narrative_plan.json", "page_tasks.json",
              "sourcing_plan.json", "build_manifest.json", "artifact_manifest.json",
              "render_result.json", "quality_report.json", "customer_visible_safety_gate.json",
              "final_readiness.json", "final_artifact_approval.json"):
        _touch(tmp_path / f)
    _touch(tmp_path / "page_packages" / "p1.json")
    proj = skill_os_projection(tmp_path)
    review = next(s for s in proj["stages"] if s["stage_id"] == "deck-review")
    # review has exit artifacts -> awaiting_approval (non-bypassable)
    assert review["is_awaiting_approval"] is True


def test_no_raw_path_or_command_on_main_surface(tmp_path):
    _seed_brief(tmp_path)
    proj = skill_os_projection(tmp_path)
    main = {k: v for k, v in proj.items() if k != "diagnostic"}
    body = json.dumps(main, ensure_ascii=False)
    assert "deck-master" not in body
    assert "/Users/" not in body
    assert "--run-dir" not in body


def test_diagnostic_drawer_separate(tmp_path):
    proj = skill_os_projection(tmp_path)
    assert "diagnostic" in proj
    # diagnostic is a separate drawer, not in the stages main surface
    for s in proj["stages"]:
        assert "source_fingerprint" not in s  # technical detail kept in diagnostic


# --- HTTP-level tests: real server, POST accept/reject + GET workflow-status ---

import http.client
import socket
import threading
from http.server import ThreadingHTTPServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(runs_dir: Path, port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "preview"))
    from server import build_handler  # noqa: E402

    handler = build_handler(run_dir=None, runs_dir=runs_dir, library_mode="fixture", use_setup_runs_dir=False)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t


def _http(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=payload, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode()
    conn.close()
    return resp.status, (json.loads(data) if data else {})


def _seed_brief_run(run: Path) -> None:
    for f in ("deck_project.json", "material_inventory.json", "workspace_policy.json",
              "deck_brief.json", "claim_map.json", "request.json"):
        (run / f).write_text("{}\n", encoding="utf-8")


def test_http_workflow_status_returns_projection(tmp_path):
    runs = tmp_path / "runs"
    (runs / "demo").mkdir(parents=True)
    _seed_brief_run(runs / "demo")
    port = _free_port()
    httpd, _t = _start_server(runs, port)
    try:
        status, body = _http(port, "GET", "/api/workflow-status/demo")
        assert status == 200
        assert body["schema_version"] == "deck_review_skill_os_view.v1"
        assert body["current_stage"] == "deck-brief"
        assert len(body["stages"]) == 9
    finally:
        httpd.shutdown()


def test_http_handoff_accept_writes_runtime(tmp_path):
    runs = tmp_path / "runs"
    (runs / "demo").mkdir(parents=True)
    _seed_brief_run(runs / "demo")
    # prepare a brief handoff so there is something to accept
    from workflow.handoff import HandoffRuntime  # noqa: E402
    h = HandoffRuntime(registry=REGISTRY)
    rec = h.prepare(runs / "demo", "deck-brief", run_id="demo")
    assert rec["status"] == "awaiting_approval"

    port = _free_port()
    httpd, _t = _start_server(runs, port)
    try:
        status, body = _http(port, "POST", "/api/workflow-handoff/demo/accept",
                             body={"handoff_id": rec["handoff_id"], "actor": "qa-http"})
        assert status == 200
        assert body["status"] == "accepted"
        assert body["accepted_by"] == "qa-http"
        # re-fetch projection: current stage advanced past brief
        _, proj = _http(port, "GET", "/api/workflow-status/demo")
        assert proj["current_stage"] == "deck-planner"
    finally:
        httpd.shutdown()


def test_http_handoff_reject_routes_repair(tmp_path):
    runs = tmp_path / "runs"
    (runs / "demo").mkdir(parents=True)
    _seed_brief_run(runs / "demo")
    from workflow.handoff import HandoffRuntime  # noqa: E402
    rec = HandoffRuntime(registry=REGISTRY).prepare(runs / "demo", "deck-brief", run_id="demo")

    port = _free_port()
    httpd, _t = _start_server(runs, port)
    try:
        status, body = _http(port, "POST", "/api/workflow-handoff/demo/reject",
                             body={"handoff_id": rec["handoff_id"], "actor": "qa-http",
                                   "reason": "narrative wrong", "repair_owner_stage": "deck-planner"})
        assert status == 200
        assert body["status"] == "rejected"
        assert body["repair_owner_stage"] == "deck-planner"
    finally:
        httpd.shutdown()


def test_http_handoff_accept_missing_handoff_id_400(tmp_path):
    runs = tmp_path / "runs"
    (runs / "demo").mkdir(parents=True)
    _seed_brief_run(runs / "demo")
    port = _free_port()
    httpd, _t = _start_server(runs, port)
    try:
        status, body = _http(port, "POST", "/api/workflow-handoff/demo/accept", body={})
        assert status == 400
        assert "handoff_id" in body["error"]
    finally:
        httpd.shutdown()


def test_http_workflow_handoffs_list(tmp_path):
    runs = tmp_path / "runs"
    (runs / "demo").mkdir(parents=True)
    _seed_brief_run(runs / "demo")
    from workflow.handoff import HandoffRuntime  # noqa: E402
    HandoffRuntime(registry=REGISTRY).prepare(runs / "demo", "deck-brief", run_id="demo")
    port = _free_port()
    httpd, _t = _start_server(runs, port)
    try:
        status, body = _http(port, "GET", "/api/workflow-handoffs/demo")
        assert status == 200
        assert len(body["handoffs"]) == 1
    finally:
        httpd.shutdown()
