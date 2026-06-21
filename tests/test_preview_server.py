"""Preview server handler tests — no socket binding required.

Uses mock I/O to test handler logic directly, avoiding ThreadingHTTPServer
which needs socket.bind() and fails in sandboxed environments.
"""
from __future__ import annotations

import io
import os
import json
import shutil
import sys
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "preview"))
sys.path.insert(0, str(ROOT / "scripts"))

from server import PreviewHandler, _load_narrative_data, build_handler  # noqa: E402
from runtime.setup_status import run_setup  # noqa: E402
from runtime.run_state import write_json  # noqa: E402

SAMPLE_RUN = ROOT / "examples" / "preview-run"


class MockHandler(PreviewHandler):
    """Testable handler with mock I/O — no socket binding."""

    def __init__(self, run_dir: Path | None = None, runs_dir: Path | None = None):
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO()
        self.client_address = ("127.0.0.1", 0)
        self.request_version = "HTTP/1.1"
        self.requestline = ""
        self._headers_buffer: list[bytes] = []
        self.headers: dict[str, str] = {}

        if run_dir is not None:
            self.run_dir = run_dir
        if runs_dir is not None:
            self.runs_dir = runs_dir
        elif not hasattr(self, "runs_dir"):
            self.runs_dir = ROOT / "runs"
        if not hasattr(self, "library_mode"):
            self.library_mode = "fixture"

    def request(self, method: str, path: str, body: dict | None = None):
        self.path = path
        self.command = method
        self.requestline = f"{method} {path} HTTP/1.1"
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO()
        self._headers_buffer = []

        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            self.rfile.write(payload)
            self.rfile.seek(0)
            self.headers = {"Content-Length": str(len(payload))}
        else:
            self.headers = {}

        if method == "GET":
            self.do_GET()
        elif method == "POST":
            self.do_POST()

        return self._parse_response()

    def _parse_response(self) -> tuple[int, dict]:
        self.wfile.seek(0)
        raw = self.wfile.read().decode("utf-8")

        if not raw.strip():
            return 500, {"error": "Empty response"}

        header_part, _, body = raw.partition("\r\n\r\n")
        status_line = header_part.split("\r\n")[0]
        status_code = int(status_line.split(" ")[1])

        if body:
            try:
                return status_code, json.loads(body)
            except json.JSONDecodeError:
                return status_code, {"raw": body}
        return status_code, {}


# ---------------------------------------------------------------------------
# ServerTests — equivalent to the old socket-based ServerTests
# ---------------------------------------------------------------------------
class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runs_dir = self.temp_dir / "runs"
        self.runs_dir.mkdir()
        self.run_dir = self.runs_dir / "sample-preview-run"
        shutil.copytree(SAMPLE_RUN, self.run_dir)
        self.handler = MockHandler(run_dir=self.run_dir, runs_dir=self.runs_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deck_api_returns_pages(self) -> None:
        status, data = self.handler.request("GET", "/api/deck")
        self.assertEqual(200, status)
        self.assertEqual("sample-preview-run", data["run_id"])
        self.assertEqual(3, len(data["pages"]))

    def test_deck_api_returns_quality_reports(self) -> None:
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "draft_gate.json").write_text(
            json.dumps(
                {
                    "run_id": "sample-preview-run",
                    "gate": "draft",
                    "status": "rework_required",
                    "blocks_delivery": True,
                    "score_summary": {"average": 2.5},
                    "findings": [
                        {
                            "finding_id": "page_001_missing_claim",
                            "severity": "P1",
                            "page_id": "page_001",
                            "message": "页面缺少主论点。",
                            "repair_instruction": "补充页面主张。",
                        }
                    ],
                    "page_findings": [
                        {
                            "finding_id": "page_001_missing_claim",
                            "severity": "P1",
                            "page_id": "page_001",
                            "message": "页面缺少主论点。",
                            "repair_instruction": "补充页面主张。",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        status, data = self.handler.request("GET", "/api/deck")

        self.assertEqual(200, status)
        self.assertEqual("rework_required", data["quality"]["draft"]["status"])
        page = next(p for p in data["pages"] if p["page_id"] == "page_001")
        self.assertEqual(1, len(page["quality"]))

    def test_direct_preview_mode_external_runtime_apis_use_active_run_dir(self) -> None:
        external_status, external = self.handler.request("GET", "/api/external-results/sample-preview-run")
        runtime_status, runtime = self.handler.request("GET", "/api/runtime-readiness/sample-preview-run")
        narrative_status, narrative = self.handler.request("GET", "/api/narrative/sample-preview-run")
        asset_status, asset = self.handler.request("GET", "/api/asset-signals/sample-preview-run")
        governance_status, governance = self.handler.request("GET", "/api/quality-governance/sample-preview-run")

        self.assertEqual(HTTPStatus.OK, external_status)
        self.assertEqual("sample-preview-run", external["run_id"])
        self.assertEqual(HTTPStatus.OK, runtime_status)
        self.assertEqual("deck_master_runtime_readiness.v1", runtime["schema_version"])
        self.assertEqual(HTTPStatus.OK, narrative_status)
        self.assertEqual("sample-preview-run", narrative["run_id"])
        self.assertEqual(HTTPStatus.OK, asset_status)
        self.assertEqual("sample-preview-run", asset["run_id"])
        self.assertEqual(HTTPStatus.OK, governance_status)
        self.assertEqual("sample-preview-run", governance["run_id"])

    def test_page_decision_api_writes_manifest(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/page/page_003/decision",
            {"decision": "approved", "notes": "Conclusion is now accepted."},
        )
        self.assertEqual(200, status)
        self.assertEqual("approved", data["decision"])
        self.assertEqual("Conclusion is now accepted.", data["notes"])

        status, page = self.handler.request("GET", "/api/page/page_003")
        self.assertEqual(200, status)
        self.assertEqual("approved", page["decision"])

    def test_page_decision_writes_typed_event(self) -> None:
        self.handler.request(
            "POST",
            "/api/page/page_001/decision",
            {"decision": "keep", "notes": "Looks good."},
        )
        events_path = self.run_dir / "events.jsonl"
        self.assertTrue(events_path.exists())
        lines = [
            line.strip()
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        decision_events = [
            json.loads(line)
            for line in lines
            if json.loads(line).get("event_type") == "decision"
        ]
        self.assertTrue(decision_events)
        last = decision_events[-1]
        self.assertEqual("preview.review.decision", last["step"])
        self.assertIn("page_001", last["refs"])

    def test_narrative_api_returns_empty_when_no_artifacts(self) -> None:
        status, data = self.handler.request("GET", "/api/narrative/sample-preview-run")
        self.assertEqual(200, status)
        self.assertEqual("sample-preview-run", data["run_id"])
        self.assertNotIn("deck_brief", data)
        self.assertNotIn("judgments", data)

    def test_narrative_api_loads_artifacts(self) -> None:
        (self.run_dir / "deck_brief.json").write_text(
            json.dumps(
                {
                    "business_goal": "提升零售客户全渠道体验",
                    "core_points": ["库存可视化", "最后一公里优化"],
                    "audience": "CXO",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.run_dir / "consulting_judgments.json").write_text(
            json.dumps(
                {
                    "judgments": [
                        {"id": "j1", "label": "Market timing", "summary": "Now is right.", "confidence": 0.9},
                        {"id": "j2", "label": "Tech stack", "summary": "Cloud-native.", "confidence": 0.85},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.run_dir / "claim_evidence_graph.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {"claim_id": "c1", "page_id": "page_001", "evidence": [{"source": "report_a"}]},
                        {"claim_id": "c2", "page_id": "page_002", "evidence": []},
                    ],
                    "gaps": [{"gap_id": "g1", "description": "缺少竞品数据支撑"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.run_dir / "claim_map.json").write_text(
            json.dumps(
                {
                    "pages": [
                        {"page_id": "page_001", "core_claim": "库存可见性是转型基础", "evidence_policy": "at_least_one"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        status, data = self.handler.request("GET", "/api/narrative/sample-preview-run")
        self.assertEqual(200, status)
        self.assertEqual("sample-preview-run", data["run_id"])
        self.assertEqual("提升零售客户全渠道体验", data["deck_brief"]["business_goal"])
        self.assertEqual(2, len(data["judgments"]["judgments"]))
        self.assertEqual(2, len(data["claim_graph"]["claims"]))
        self.assertEqual(1, len(data["claim_graph"]["gaps"]))
        self.assertEqual("库存可见性是转型基础", data["claim_map"]["pages"][0]["core_claim"])

    def test_narrative_api_rejects_invalid_run(self) -> None:
        status, data = self.handler.request("GET", "/api/narrative/nonexistent-run")
        self.assertEqual(404, status)
        self.assertIn("not found", data["error"].lower())

    def test_narrative_api_rejects_traversal(self) -> None:
        status, data = self.handler.request("GET", "/api/narrative/../etc")
        self.assertEqual(400, status)

    def test_workspace_api_returns_run_workspace_payload(self) -> None:
        status, data = self.handler.request("GET", "/api/workspace/sample-preview-run")
        self.assertEqual(200, status)
        self.assertEqual("deck_master_workspace.v0.3", data["schema_version"])
        self.assertEqual("sample-preview-run", data["run_id"])
        self.assertEqual("sample-preview-run", data["project_id"])
        self.assertIn("stage", data)
        self.assertIn("queue", data)
        self.assertEqual(3, len(data["queue"]["pages"]))

    def test_workspace_page_api_returns_claims_and_risks(self) -> None:
        (self.run_dir / "claim_evidence_graph.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {
                            "claim_id": "claim_001",
                            "statement": "库存可见性是转型基础",
                            "page_refs": ["page_001"],
                            "supporting_evidence": ["evidence_001"],
                        }
                    ],
                    "evidence": [
                        {
                            "evidence_id": "evidence_001",
                            "source_ref": "src_001",
                            "publication_status": "safe_to_use",
                            "title": "客户访谈纪要",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.run_dir / "claim_map.json").write_text(
            json.dumps(
                {
                    "pages": [
                        {
                            "page_id": "page_001",
                            "core_claim": "库存可见性是转型基础",
                            "evidence_policy": "at_least_one",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        (quality_dir / "draft_gate.json").write_text(
            json.dumps(
                {
                    "gate": "draft",
                    "status": "rework_required",
                    "blocks_delivery": True,
                    "summary": {"p0_count": 0, "p1_count": 1, "p2_count": 0},
                    "findings": [
                        {
                            "finding_id": "page_001_claim_gap",
                            "severity": "P1",
                            "page_id": "page_001",
                            "message": "主论点证据偏弱。",
                            "repair_instruction": "补充客户数据来源。",
                        }
                    ],
                    "page_findings": [
                        {
                            "finding_id": "page_001_claim_gap",
                            "severity": "P1",
                            "page_id": "page_001",
                            "message": "主论点证据偏弱。",
                            "repair_instruction": "补充客户数据来源。",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        status, data = self.handler.request("GET", "/api/workspace/sample-preview-run/page/page_001")
        self.assertEqual(200, status)
        self.assertEqual("page_001", data["hero"]["page_id"])
        self.assertEqual("库存可见性是转型基础", data["summary"]["core_claim"])
        self.assertEqual(1, data["evidence"]["evidence_total"])
        self.assertTrue(data["quality"]["blocking"])

    def test_workspace_approval_actions_write_activity(self) -> None:
        submit_status, approval = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/actions",
            {"action": "submit_approval", "actor": "alice", "note": "Ready for export"},
        )
        self.assertEqual(200, submit_status)
        self.assertEqual("pending", approval["status"])

        page_submit_status, page_approval = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/page/page_001/actions",
            {"action": "submit_approval", "actor": "alice", "note": "Need owner sign-off"},
        )
        self.assertEqual(200, page_submit_status)
        self.assertEqual("page", page_approval["scope_type"])

        page_status, page_payload = self.handler.request("GET", "/api/workspace/sample-preview-run/page/page_001")
        self.assertEqual(200, page_status)
        self.assertEqual(2, page_payload["approvals"]["pending_count"])

        approve_status, approve_payload = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/page/page_001/actions",
            {
                "action": "approve_approval",
                "actor": "bob",
                "approval_id": page_approval["approval_id"],
                "note": "Approved",
            },
        )
        self.assertEqual(200, approve_status)
        self.assertEqual("approved", approve_payload["status"])

        activity_status, activity = self.handler.request("GET", "/api/workspace/sample-preview-run/activity")
        self.assertEqual(200, activity_status)
        titles = [item["title"] for item in activity["items"]]
        self.assertTrue(any("提交审批" in title for title in titles))
        self.assertTrue(any("审批通过" in title for title in titles))

    def test_workspace_run_submit_approval_is_idempotent_while_pending(self) -> None:
        first_status, first_payload = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/actions",
            {"action": "submit_approval", "actor": "alice", "note": "Ready for export"},
        )
        second_status, second_payload = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/actions",
            {"action": "submit_approval", "actor": "alice", "note": "Ready for export"},
        )

        self.assertEqual(200, first_status)
        self.assertEqual(200, second_status)
        self.assertEqual(first_payload["approval_id"], second_payload["approval_id"])

        page_status, page_payload = self.handler.request("GET", "/api/workspace/sample-preview-run/page/page_001")
        self.assertEqual(200, page_status)
        run_approvals = [task for task in page_payload["approvals"]["tasks"] if task["scope_type"] == "run"]
        self.assertEqual(1, len(run_approvals))

    def test_workspace_api_supports_run_without_preview_manifest(self) -> None:
        pending_run = self.runs_dir / "pending-run"
        pending_run.mkdir()
        write_json(
            pending_run / "request.json",
            {
                "run_id": "pending-run",
                "project_name": "Pending Workspace",
                "run_mode": "fixture",
            },
        )

        status, data = self.handler.request("GET", "/api/workspace/pending-run?run_dir=" + str(pending_run))
        self.assertEqual(200, status)
        self.assertEqual("pending-run", data["run_id"])
        self.assertEqual(0, data["header_metrics"]["pages_total"])
        self.assertEqual("待准备", data["stage"]["label"])

    def test_workspace_delivery_preview_endpoint_reports_missing_artifact(self) -> None:
        status, data = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")
        self.assertEqual(200, status)
        self.assertEqual("missing_render_result", data["status"])
        self.assertFalse(data["artifact_ready"])

    def test_workspace_delivery_preview_serves_rendered_html(self) -> None:
        rendered_dir = self.run_dir / "rendered"
        rendered_dir.mkdir(exist_ok=True)
        (rendered_dir / "index.html").write_text("<html><body><h1>Delivery Preview</h1></body></html>", encoding="utf-8")
        result_dir = self.run_dir / "render_results"
        result_dir.mkdir(exist_ok=True)
        (result_dir / "render_result.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_render_result.v1",
                    "run_id": "sample-preview-run",
                    "tool": "ppt-master",
                    "status": "completed",
                    "format": "html",
                    "artifact_path": "rendered/index.html",
                    "created_at": "2026-06-21T10:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        status, payload = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")
        self.assertEqual(200, status)
        self.assertEqual("ready", payload["status"])
        self.assertTrue(payload["artifact_ready"])
        self.assertEqual("/delivery-preview/sample-preview-run?run=sample-preview-run", payload["artifact_url"])

        artifact_status, artifact_payload = self.handler.request("GET", "/delivery-preview/sample-preview-run?run=sample-preview-run")
        self.assertEqual(200, artifact_status)
        self.assertIn("Delivery Preview", artifact_payload["raw"])

    def test_workspace_mark_delivered_is_idempotent_after_delivery_recorded(self) -> None:
        first_status, first_payload = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/actions",
            {"action": "mark_delivered", "actor": "alice", "note": "Delivered"},
        )
        second_status, second_payload = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/actions",
            {"action": "mark_delivered", "actor": "alice", "note": "Delivered again"},
        )

        self.assertEqual(200, first_status)
        self.assertEqual(200, second_status)
        self.assertEqual(first_payload["delivered_at"], second_payload["delivered_at"])

        activity_status, activity = self.handler.request("GET", "/api/workspace/sample-preview-run/activity")
        self.assertEqual(200, activity_status)
        delivered_titles = [item for item in activity["items"] if "交付结果已记录" in item["title"]]
        self.assertEqual(1, len(delivered_titles))


# ---------------------------------------------------------------------------
# StudioServerTests — studio mode (no fixed run_dir)
# ---------------------------------------------------------------------------
class StudioServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runs_dir = self.temp_dir / "runs"
        self.home_dir = self.temp_dir / "home"
        self.home_dir.mkdir()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home_dir)
        from skills import installer as skill_installer

        self.skill_installer = skill_installer
        self.original_skill_dir = skill_installer.INSTALLED_SKILL_DIR
        self.handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.skill_installer.INSTALLED_SKILL_DIR = self.original_skill_dir
        if self.original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.original_home

    def test_build_handler_honors_explicit_runs_dir_in_studio_mode(self) -> None:
        isolated_runs = self.temp_dir / "isolated-runs"
        isolated_runs.mkdir()
        handler_cls = build_handler(None, isolated_runs, use_setup_runs_dir=False)
        self.assertEqual(isolated_runs.resolve(), handler_cls.runs_dir)
        self.assertFalse(handler_cls.use_setup_runs_dir)

    def _write_ready_setup(self) -> Path:
        from skills import installer as skill_installer

        skill_root = self.home_dir / ".deck-master" / "current"
        installed_skill = skill_root / "skills" / "deck-master"
        installed_skill.parent.mkdir(parents=True, exist_ok=True)
        installed_skill.mkdir(parents=True, exist_ok=True)
        (installed_skill / "SKILL.md").write_text(
            "---\nname: deck-master\ndescription: Test Deck Master skill.\n---\n# Deck Master\n",
            encoding="utf-8",
        )
        skill_installer.INSTALLED_SKILL_DIR = installed_skill

        codex_skill_dir = self.home_dir / ".codex" / "skills"
        codex_skill_dir.mkdir(parents=True, exist_ok=True)
        codex_link = codex_skill_dir / "deck-master"
        if not codex_link.exists():
            codex_link.symlink_to(installed_skill)

        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        run_setup(
            workspace=str(workspace),
            runs_dir=str(self.runs_dir / "from_setup"),
            targets=["codex"],
            repair=True,
        )
        return workspace

    def test_studio_can_create_and_load_run(self) -> None:
        status, created = self.handler.request(
            "POST",
            "/api/runs",
            {
                "brief": "零售数字化方案，关注全渠道、库存可视化、最后一公里配送",
                "industry": "retail",
                "target_pages": "auto",
                "library_mode": "fixture",
                "run_id": "studio-test",
            },
        )
        self.assertEqual(201, status)
        self.assertEqual("studio-test", created["run_id"])
        self.assertEqual(12, created["pages"])

        status, runs = self.handler.request("GET", "/api/runs")
        self.assertEqual(200, status)
        self.assertEqual(["studio-test"], [r["run_id"] for r in runs["runs"]])

        status, deck = self.handler.request("GET", "/api/deck?run_id=studio-test")
        self.assertEqual(200, status)
        self.assertEqual("studio-test", deck["run_id"])
        self.assertEqual(12, len(deck["pages"]))

    def test_setup_not_ready_blocks_production_run(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/runs",
            {
                "brief": "需要真实运行的演示",
                "industry": "retail",
                "target_pages": "auto",
                "run_id": "blocked-run",
            },
        )
        self.assertEqual(HTTPStatus.CONFLICT, status)
        self.assertIn("Setup is not ready", data["error"])

    def test_setup_ready_active_workspace_writes_request_workspace(self) -> None:
        workspace = self._write_ready_setup()

        status, created = self.handler.request(
            "POST",
            "/api/runs",
            {
                "brief": "真实run，带 workspace",
                "industry": "retail",
                "target_pages": "auto",
                "run_id": "ready-run",
            },
        )
        self.assertEqual(HTTPStatus.CREATED, status)
        self.assertEqual("ready-run", created["run_id"])
        self.assertEqual("needs_context", created["status"])
        run_request = json.loads((Path(created["run_dir"]) / "request.json").read_text(encoding="utf-8"))
        self.assertEqual("production", run_request["run_mode"])
        self.assertEqual(str(workspace.resolve()), run_request["workspace"])
        self.assertFalse((Path(created["run_dir"]) / "preview_manifest.json").exists())
        self.assertFalse((Path(created["run_dir"]) / "narrative_plan.json").exists())

    def test_production_run_state_uses_setup_runs_dir_across_handler_instances(self) -> None:
        self._write_ready_setup()

        status, created = self.handler.request(
            "POST",
            "/api/runs",
            {
                "brief": "真实 HTTP handler 生命周期",
                "industry": "retail",
                "target_pages": "auto",
                "run_id": "ready-run-http",
            },
        )
        self.assertEqual(HTTPStatus.CREATED, status)

        next_handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)
        next_handler.use_setup_runs_dir = True
        run_state_status, run_state = next_handler.request("GET", "/api/run-state/ready-run-http")
        self.assertEqual(HTTPStatus.OK, run_state_status)
        self.assertEqual("ready-run-http", run_state["run_id"])
        self.assertEqual(created["run_dir"], run_state["run_dir"])

        runs_status, runs = next_handler.request("GET", "/api/runs")
        self.assertEqual(HTTPStatus.OK, runs_status)
        self.assertEqual(str((self.runs_dir / "from_setup").resolve()), runs["runs_dir"])
        self.assertIn("ready-run-http", [run["run_id"] for run in runs["runs"]])

    def test_classic_demo_sets_fixture_mode(self) -> None:
        status, created = self.handler.request(
            "POST",
            "/api/runs",
            {
                "brief": "经典 Demo 演示",
                "industry": "retail",
                "target_pages": "auto",
                "planning_mode": "classic",
                "run_id": "classic-demo",
            },
        )
        self.assertEqual(HTTPStatus.CREATED, status)
        self.assertEqual("classic-demo", created["run_id"])
        run_request = json.loads((Path(created["run_dir"]) / "request.json").read_text(encoding="utf-8"))
        self.assertEqual("fixture", run_request["run_mode"])

    def test_setup_status_api_keeps_cli_compatibility(self) -> None:
        workspace = self._write_ready_setup()
        status, payload = self.handler.request("GET", "/api/setup-status")
        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual("ready", payload["status"])
        self.assertIn("install_ready", payload)
        self.assertIn("workspace_ready", payload)
        self.assertIn("run_ready", payload)
        self.assertIn("production_ready", payload)
        self.assertEqual(str(workspace.resolve()), payload["active_workspace"])
        self.assertIn("suite", payload)
        self.assertIn("task_readiness", payload)

    def test_run_state_api_returns_status(self) -> None:
        status, created = self.handler.request(
            "POST",
            "/api/runs",
            {
                "brief": "检查run状态",
                "industry": "retail",
                "target_pages": "auto",
                "library_mode": "fixture",
                "run_id": "state-run",
            },
        )
        self.assertEqual(HTTPStatus.CREATED, status)

        run_state_status, run_state = self.handler.request("GET", f"/api/run-state/{created['run_id']}")
        self.assertEqual(HTTPStatus.OK, run_state_status)
        self.assertEqual("deck_run_state.v1", run_state["schema_version"])
        self.assertEqual("state-run", run_state["run_id"])
        self.assertEqual("fixture", run_state["run_mode"])
        self.assertIn("status", run_state)
        self.assertIn("stage", run_state)


# ---------------------------------------------------------------------------
# NarrativeDataLoaderTests — pure logic, no handler
# ---------------------------------------------------------------------------
class NarrativeDataLoaderTests(unittest.TestCase):
    """Pure logic tests for _load_narrative_data — no handler needed."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_returns_empty_when_no_artifacts(self) -> None:
        data = _load_narrative_data(self.temp_dir)
        self.assertEqual({}, data)

    def test_loads_all_artifacts(self) -> None:
        (self.temp_dir / "deck_brief.json").write_text(
            json.dumps({"business_goal": "Test goal"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.temp_dir / "consulting_judgments.json").write_text(
            json.dumps({"judgments": [{"id": "j1"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.temp_dir / "claim_evidence_graph.json").write_text(
            json.dumps({"claims": [], "gaps": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.temp_dir / "claim_map.json").write_text(
            json.dumps({"pages": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        data = _load_narrative_data(self.temp_dir)
        self.assertEqual("Test goal", data["deck_brief"]["business_goal"])
        self.assertEqual(1, len(data["judgments"]["judgments"]))
        self.assertIn("claims", data["claim_graph"])
        self.assertIn("pages", data["claim_map"])

    def test_handles_invalid_json_gracefully(self) -> None:
        (self.temp_dir / "deck_brief.json").write_text("{invalid json", encoding="utf-8")
        data = _load_narrative_data(self.temp_dir)
        self.assertEqual({}, data["deck_brief"])


if __name__ == "__main__":
    unittest.main()
