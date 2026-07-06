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

import server as preview_server
import workspace_api
from server import PreviewHandler, _load_narrative_data, build_handler  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402
from runtime.setup_status import run_setup  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover - optional local dev dependency.
    jsonschema = None

SAMPLE_RUN = ROOT / "examples" / "preview-run"


def _schema_type_matches(value: object, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return True


def _validate_schema_subset(payload: object, schema: dict, root_schema: dict, path: str = "$") -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        ref = str(schema["$ref"])
        if ref.startswith("#/$defs/"):
            schema = root_schema.get("$defs", {}).get(ref.removeprefix("#/$defs/"), {})

    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _schema_type_matches(payload, expected_type):
        return [f"{path}: expected {expected_type}"]

    if "const" in schema and payload != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and payload not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")
    if isinstance(payload, int) and not isinstance(payload, bool) and "minimum" in schema and payload < schema["minimum"]:
        errors.append(f"{path}: expected >= {schema['minimum']}")

    if isinstance(payload, dict):
        for key in schema.get("required", []):
            if key not in payload:
                errors.append(f"{path}.{key}: missing required field")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in payload and isinstance(child_schema, dict):
                errors.extend(_validate_schema_subset(payload[key], child_schema, root_schema, f"{path}.{key}"))
    elif isinstance(payload, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(payload):
            errors.extend(_validate_schema_subset(item, schema["items"], root_schema, f"{path}[{index}]"))
    return errors


def _setup_status_schema_errors(payload: dict) -> list[str]:
    schema = json.loads((ROOT / "docs" / "contracts" / "setup-status.v2.schema.json").read_text(encoding="utf-8"))
    if jsonschema is not None:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        return [
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
        ]
    return _validate_schema_subset(payload, schema, schema)


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
        self.assertGreaterEqual(len(data["pages"]), 10)

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

    def test_readiness_and_metrics_aliases_match_canonical_routes(self) -> None:
        readiness_status, readiness = self.handler.request("GET", "/api/readiness/sample-preview-run")
        review_status, review = self.handler.request("GET", "/api/review-summary/sample-preview-run")
        metrics_status, metrics = self.handler.request("GET", "/api/metrics/sample-preview-run")
        run_metrics_status, run_metrics = self.handler.request("GET", "/api/run-metrics/sample-preview-run")

        self.assertEqual(HTTPStatus.OK, readiness_status)
        self.assertEqual(HTTPStatus.OK, review_status)
        self.assertEqual(readiness, review)
        self.assertEqual(HTTPStatus.OK, metrics_status)
        self.assertEqual(HTTPStatus.OK, run_metrics_status)
        self.assertEqual(metrics, run_metrics)

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
        self.assertGreaterEqual(len(data["queue"]["pages"]), 10)

    def test_workspace_api_exposes_safe_backend_dependency_summary(self) -> None:
        original = workspace_api.setup_status

        def fake_setup_status(**kwargs):
            return {
                "config": {"install_root": str(self.runs_dir)},
                "install_ready": True,
                "workspace_ready": True,
                "run_ready": True,
                "production_ready": True,
                "external_dependency_status": [
                    {
                        "name": "ppt-master",
                        "repo_label": "deck-master/ppt-master",
                        "git_remote": "https://github.com/example/ppt-master.git",
                        "repo_path": "/Users/example/.deck-master/backend/ppt-master",
                        "skill_path": "/Users/example/.deck-master/backend/ppt-master/skills/ppt-master",
                        "binding_status": "bound_verified",
                        "short_sha": "feedcafe",
                        "git_sha": "feedcafe1234",
                        "git_branch": "main",
                        "verified": True,
                        "verified_at": "2026-01-01T00:00:00Z",
                        "summary": "PPT Master 已绑定且已完成验证。",
                    }
                ],
                "workspace": {},
            }

        workspace_api.setup_status = fake_setup_status
        try:
            status, payload = self.handler.request("GET", "/api/workspace/sample-preview-run")
            self.assertEqual(HTTPStatus.OK, status)
            dependencies = payload["run_summary"].get("external_dependencies")
            self.assertIsInstance(dependencies, list)
            self.assertEqual("ppt-master", dependencies[0]["name"])
            self.assertEqual("deck-master/ppt-master", dependencies[0]["repo_label"])
            self.assertEqual("feedcafe", dependencies[0]["short_sha"])
            self.assertIn("summary", dependencies[0])
            self.assertNotIn("repo_path", dependencies[0])
            self.assertNotIn("skill_path", dependencies[0])
            runtime_dependencies = payload["runtime"].get("external_dependencies", [])
            self.assertIsInstance(runtime_dependencies, list)
            self.assertEqual(dependencies, runtime_dependencies)
        finally:
            workspace_api.setup_status = original

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

    def test_workspace_page_actions_bootstrap_page_tasks_for_preview_fixture(self) -> None:
        """Regression: ISSUE-001 — sample preview fixture should allow page actions."""

        status, payload = self.handler.request(
            "POST",
            "/api/workspace/sample-preview-run/page/page_001/actions",
            {"action": "approve", "actor": "qa"},
        )

        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])
        self.assertTrue((self.run_dir / "page_tasks.json").exists())
        deck_status, deck = self.handler.request("GET", "/api/deck")
        self.assertEqual(200, deck_status)
        page = next(item for item in deck["pages"] if item["page_id"] == "page_001")
        self.assertEqual("approved", page["review_status"])

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
        self.assertIn("display_next_step_detail", data["stage"])
        self.assertIn("display_blocker_summary", data["stage"])
        visible_stage_text = json.dumps(
            {
                "display_next_step_detail": data["stage"]["display_next_step_detail"],
                "display_blocker_summary": data["stage"]["display_blocker_summary"],
                "display_primary_action_label": data["stage"]["display_primary_action_label"],
            },
            ensure_ascii=False,
        )
        self.assertNotIn(str(pending_run), visible_stage_text)
        self.assertNotIn("/Users/", visible_stage_text)
        self.assertNotIn("/private/", visible_stage_text)
        self.assertNotIn("--run-dir", visible_stage_text)
        self.assertNotIn("deck-master ", visible_stage_text)

    def test_workspace_translates_preparation_stage_and_readiness_reason(self) -> None:
        pending_run = self.runs_dir / "needs-context-run"
        (pending_run / "links").mkdir(parents=True)
        (pending_run / "links" / "page_001.svg").write_text("<svg></svg>\n", encoding="utf-8")
        write_json(
            pending_run / "request.json",
            {
                "run_id": "needs-context-run",
                "project_name": "Needs Context",
                "run_mode": "fixture",
            },
        )
        write_json(
            pending_run / "preview_manifest.json",
            {
                "run_id": "needs-context-run",
                "title": "Needs Context",
                "pages": [
                    {
                        "page_id": "page_001",
                        "beat_id": "page_001",
                        "order": 1,
                        "title": "Page 1",
                        "source_type": "library_slide",
                        "preview_path": "links/page_001.svg",
                        "decision": "needs_review",
                    }
                ],
            },
        )
        write_json(
            pending_run / "delivery" / "final_readiness.json",
            {
                "schema_version": "deck_final_readiness.v1",
                "run_id": "needs-context-run",
                "ready": False,
                "status": "blocked",
                "blockers": [
                    {
                        "code": "final_run_state_not_ready",
                        "severity": "P0",
                        "message": "Run state is needs_context.",
                    }
                ],
            },
        )

        status, data = self.handler.request("GET", "/api/workspace/needs-context-run?run_dir=" + str(pending_run))

        self.assertEqual(200, status)
        self.assertEqual("待准备", data["stage"]["label"])
        self.assertIn("项目背景与输入资料", data["stage"]["blocking_reason"])
        self.assertIn("项目背景与输入资料", data["stage"]["display_blocker_summary"])
        self.assertIn("项目背景与输入资料", data["health"]["blocking_reasons"][0])
        self.assertIn("项目背景与输入资料", data["runtime"]["final_readiness"]["reason"])
        self.assertNotIn("Run state is", json.dumps(data, ensure_ascii=False))
        self.assertNotIn("generation session status is missing", json.dumps(data, ensure_ascii=False))

    def test_workspace_delivery_preview_endpoint_reports_missing_artifact(self) -> None:
        status, data = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")
        self.assertEqual(200, status)
        self.assertEqual("missing_render_result", data["status"])
        self.assertFalse(data["artifact_ready"])

    def test_workspace_delivery_preview_detail_does_not_expose_internal_files(self) -> None:
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
                }
            ),
            encoding="utf-8",
        )
        status, payload = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")
        self.assertEqual(200, status)
        self.assertEqual("missing_artifact_path", payload["status"])
        self.assertNotIn("render_result.json", payload["detail"])
        self.assertNotIn("artifact_path", payload["detail"])
        self.assertNotIn("rendered/index.html", payload["detail"])

        (result_dir / "render_result.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_render_result.v1",
                    "run_id": "sample-preview-run",
                    "tool": "ppt-master",
                    "status": "completed",
                    "format": "html",
                    "artifact_path": "rendered/index.html",
                }
            ),
            encoding="utf-8",
        )
        status, payload = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")
        self.assertEqual(200, status)
        self.assertEqual("artifact_missing", payload["status"])
        self.assertNotIn("render_result.json", payload["detail"])
        self.assertNotIn("artifact_path", payload["detail"])
        self.assertNotIn("rendered/index.html", payload["detail"])

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
        write_json(self.run_dir / "delivery" / "final_readiness.json", {
            "schema_version": "deck_final_readiness.v1",
            "run_id": "sample-preview-run",
            "ready": True,
            "status": "ready",
            "blockers": [],
        })

        status, payload = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")
        self.assertEqual(200, status)
        self.assertEqual("ready", payload["status"])
        self.assertTrue(payload["artifact_ready"])
        self.assertEqual("/delivery-preview/sample-preview-run?run=sample-preview-run", payload["artifact_url"])

        artifact_status, artifact_payload = self.handler.request("GET", "/delivery-preview/sample-preview-run?run=sample-preview-run")
        self.assertEqual(200, artifact_status)
        self.assertIn("Delivery Preview", artifact_payload["raw"])

    def test_workspace_api_exposes_build_and_render_metadata(self) -> None:
        build_dir = self.run_dir / "build"
        pages_dir = build_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "deck.html").write_text("<html><body>A4</body></html>", encoding="utf-8")
        (pages_dir / "page_001.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        result_dir = self.run_dir / "render_results"
        result_dir.mkdir(exist_ok=True)
        artifacts = [
            {
                "artifact_id": "deck_html",
                "kind": "deck_html",
                "path": "build/deck.html",
                "media_type": "text/html",
                "sha256": "a" * 64,
                "bytes": 28,
                "validation_status": "validated",
                "editability": "native",
            },
            {
                "artifact_id": "page_001_png",
                "kind": "page_png",
                "path": "build/pages/page_001.png",
                "media_type": "image/png",
                "sha256": "b" * 64,
                "bytes": 12,
                "validation_status": "validated",
                "editability": "flat_image",
            },
        ]
        (build_dir / "artifact_manifest.json").write_text(
            json.dumps({"schema_version": "deck_artifact_manifest.v1", "run_id": "sample-preview-run", "artifacts": artifacts}),
            encoding="utf-8",
        )
        (result_dir / "render_result.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_render_result.v2",
                    "run_id": "sample-preview-run",
                    "tool": "ppt-master",
                    "status": "completed",
                    "artifact_path": "build/deck.html",
                    "artifact_manifest": "build/artifact_manifest.json",
                    "source_fingerprint": "c" * 64,
                    "artifacts": artifacts,
                    "page_count": 1,
                    "created_at": "2026-06-22T10:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        status, workspace = self.handler.request("GET", "/api/workspace/sample-preview-run")
        delivery_status, delivery = self.handler.request("GET", "/api/workspace/sample-preview-run/delivery-preview")

        self.assertEqual(200, status)
        self.assertEqual(200, delivery_status)
        self.assertEqual("completed", workspace["runtime"]["render"]["status"])
        self.assertEqual(2, workspace["runtime"]["build"]["artifact_count"])
        self.assertIn("native", workspace["runtime"]["build"]["editability"])
        self.assertEqual("real", delivery["source_mode"])
        self.assertEqual(2, delivery["artifact_count"])
        self.assertIn("deck_html", delivery["formats"])

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
        self.assertNotIn("deck-master ", data["error"])
        self.assertNotIn("--workspace", data["error"])
        self.assertNotIn("/Users/", data["error"])

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

    def test_studio_runs_dir_cli_explicit_overrides_setup_default(self) -> None:
        self._write_ready_setup()
        create_run(self.runs_dir, {"project_name": "Explicit"}, run_id="explicit-run")
        create_run(self.runs_dir / "from_setup", {"project_name": "Setup"}, run_id="setup-run")

        explicit_handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)
        explicit_handler.use_setup_runs_dir = False
        explicit_status, explicit_runs = explicit_handler.request("GET", "/api/runs")

        self.assertEqual(HTTPStatus.OK, explicit_status)
        self.assertEqual(str(self.runs_dir.resolve()), explicit_runs["runs_dir"])
        self.assertIn("explicit-run", [run["run_id"] for run in explicit_runs["runs"]])
        self.assertNotIn("setup-run", [run["run_id"] for run in explicit_runs["runs"]])

        setup_handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)
        setup_handler.use_setup_runs_dir = True
        setup_status, setup_runs = setup_handler.request("GET", "/api/runs")

        self.assertEqual(HTTPStatus.OK, setup_status)
        self.assertEqual(str((self.runs_dir / "from_setup").resolve()), setup_runs["runs_dir"])
        self.assertIn("setup-run", [run["run_id"] for run in setup_runs["runs"]])
        self.assertNotIn("explicit-run", [run["run_id"] for run in setup_runs["runs"]])

    def test_planned_run_apis_return_empty_contract_without_manifest_path(self) -> None:
        planned = create_run(self.runs_dir, {"project_name": "Planned"}, run_id="planned-run")
        write_json(planned / "narrative_plan.json", {"run_id": "planned-run", "beats": []})
        handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)

        checks = [
            ("GET", "/api/deck?run_id=planned-run"),
            ("GET", "/api/narrative/planned-run"),
            ("GET", "/api/asset-signals/planned-run"),
            ("GET", "/api/quality-governance/planned-run"),
            ("GET", "/api/export-queue/planned-run?queue_type=client"),
        ]
        for method, path in checks:
            with self.subTest(path=path):
                status, data = handler.request(method, path)
                body = json.dumps(data, ensure_ascii=False)
                self.assertEqual(HTTPStatus.OK, status)
                self.assertNotIn(str(planned), body)
                self.assertNotIn("preview_manifest.json", body)

        deck_status, deck = handler.request("GET", "/api/deck?run_id=planned-run")
        self.assertEqual(HTTPStatus.OK, deck_status)
        self.assertFalse(deck["preview_ready"])
        self.assertEqual("planned-run", deck["run_id"])
        self.assertEqual([], deck["pages"])

    def test_invalid_run_error_does_not_leak_absolute_path(self) -> None:
        handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)

        status, data = handler.request("GET", "/api/deck?run_id=missing-run")

        self.assertIn(status, {HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND})
        error = data["error"]
        self.assertIn("Run not found", error)
        self.assertNotIn(str(self.runs_dir), error)
        self.assertNotIn("/Users/", error)

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
        self.assertIn("workspace_entry_ready", payload)
        self.assertIn("production_ready", payload)
        self.assertEqual(str(workspace.resolve()), payload["active_workspace"])
        self.assertIn("suite", payload)
        self.assertIn("task_readiness", payload)
        self.assertIn("production_backend_ready", payload)
        self.assertIn("client_delivery_ready", payload)
        self.assertIn("repair_items_count", payload)
        self.assertIn("blocking_summary", payload)
        self.assertIn("setup_blocking_summary", payload)
        self.assertIn("workspace_blocking_summary", payload)
        self.assertIn("suite_blocking_summary", payload)
        self.assertIn("client_delivery_blocking_summary", payload)
        self.assertIn("readiness_layers", payload)
        self.assertFalse(payload["production_backend_ready"])
        self.assertFalse(payload["client_delivery_ready"])

    def test_setup_status_api_payload_matches_v2_schema(self) -> None:
        self._write_ready_setup()
        status, payload = self.handler.request("GET", "/api/setup-status")
        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual("deck_master_setup_status.v2", payload["schema_version"])
        self.assertEqual([], _setup_status_schema_errors(payload))

    def test_setup_status_blocked_payload_matches_v2_schema(self) -> None:
        status, payload = self.handler.request("GET", "/api/setup-status")
        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual("deck_master_setup_status.v2", payload["schema_version"])
        self.assertEqual("blocked", payload["status"])
        self.assertEqual([], _setup_status_schema_errors(payload))

    def test_setup_status_api_separates_workspace_entry_from_client_delivery(self) -> None:
        workspace = self._write_ready_setup()
        original_setup_status = preview_server.setup_status

        fake_payload = {
            "schema_version": "deck_master_setup_status.v2",
            "status": "ready",
            "install_ready": True,
            "workspace_ready": True,
            "run_ready": True,
            "workspace_entry_ready": True,
            "production_ready": False,
            "production_backend_ready": True,
            "client_delivery_ready": False,
            "config": {
                "install_root": str(self.home_dir / ".deck-master"),
                "active_workspace": str(workspace.resolve()),
                "default_runs_dir": str(self.runs_dir),
            },
            "workspace": {"status": "valid", "workspace_dir": str(workspace.resolve())},
            "blocking_summary": [
                {
                    "code": "client_delivery_blocked",
                    "blocking_type": "delivery",
                    "message": "客户版交付仍被阻断。",
                    "repair_owner": "backend",
                    "next_command": "deck-master suite-status --output json",
                },
            ],
            "client_delivery_blocking_summary": [
                {
                    "code": "client_delivery_blocked",
                    "blocking_type": "delivery",
                    "message": "客户版交付仍被阻断。",
                    "repair_owner": "backend",
                },
            ],
            "suite": {"status": "ready", "full_suite_ready": True},
        }

        def fake_setup_status(**kwargs):
            return fake_payload

        preview_server.setup_status = fake_setup_status
        try:
            status, payload = self.handler.request("GET", "/api/setup-status")
            self.assertEqual(HTTPStatus.OK, status)
            self.assertTrue(payload["workspace_entry_ready"])
            self.assertTrue(payload["workspace_access_ready"])
            self.assertFalse(payload["production_ready"])
            self.assertFalse(payload["client_delivery_ready"])
            self.assertEqual([], payload["workspace_blocking_summary"])
            self.assertEqual(
                fake_payload["client_delivery_blocking_summary"],
                payload["client_delivery_blocking_summary"],
            )
            self.assertTrue(payload["readiness_layers"]["workspace"]["ready"])
            self.assertFalse(payload["readiness_layers"]["client_delivery"]["ready"])
        finally:
            preview_server.setup_status = original_setup_status

    def test_setup_status_api_uses_backend_truth_without_recompute(self) -> None:
        workspace = self._write_ready_setup()
        original_setup_status = preview_server.setup_status

        fake_payload = {
            "schema_version": "deck_master_setup_status.v2",
            "status": "ready",
            "missing_items": ["suite item"],
            "repair_items": ["backend item"],
            "warnings": ["警告: 仅测试"],
            "repair_items_count": 99,
            "install_ready": False,
            "workspace_ready": True,
            "run_ready": True,
            "production_ready": False,
            "active_workspace_required_for_production": True,
            "dev_mode_allowed": False,
            "fixture_mode_allowed": True,
            "config": {
                "install_root": str(ROOT),
                "active_workspace": str(workspace.resolve()),
                "default_runs_dir": str(self.runs_dir),
            },
            "config_path": str(self.runs_dir / "config.json"),
            "workspace": {
                "status": "valid",
                "workspace_path": str(workspace),
            },
            "next_command": "--run-dir should_not_recompute",
            "next_agent_action": "继续",
            "external_dependency_status": [
                {
                    "repo_label": "deck-master/ppt-master",
                    "status": "ready",
                    "short_sha": "0123456789abcdef",
                    "summary": "PPT Master 已就绪",
                },
            ],
            "production_backend_ready": False,
            "client_delivery_ready": True,
            "blocking_summary": [
                {"code": "suite_blocked", "message": "当前依赖链阻断后端绑定。"},
            ],
            "suite": {
                "status": "ready",
                "full_suite_ready": True,
                "production_backend_ready": True,
                "client_delivery_ready": False,
                "external_dependency_status": [
                    {
                        "repo_label": "suite-ppt-master",
                        "status": "ready",
                        "short_sha": "fedcba987654",
                    },
                ],
            },
            "capabilities": {"deck_master.build.v1": "ready"},
            "task_readiness": {"delivery": "ready"},
            "full_suite_ready": False,
            "agent_targets": ["codex"],
        }

        def fake_setup_status(**kwargs):
            return fake_payload

        preview_server.setup_status = fake_setup_status
        try:
            status, payload = self.handler.request("GET", "/api/setup-status")
            self.assertEqual(HTTPStatus.OK, status)
            self.assertFalse(payload["install_ready"])
            self.assertTrue(payload["workspace_ready"])
            self.assertTrue(payload["run_ready"])
            self.assertFalse(payload["production_ready"])
            self.assertFalse(payload["production_backend_ready"])
            self.assertTrue(payload["client_delivery_ready"])
            self.assertEqual(payload["next_agent_action"], fake_payload["next_agent_action"])
            self.assertEqual(payload["repair_items_count"], 99)
            self.assertEqual(payload["external_dependency_status"], fake_payload.get("external_dependency_status"))
            self.assertEqual(payload["suite_external_dependency_status"], fake_payload["suite"]["external_dependency_status"])
            self.assertEqual(payload["blocking_summary"], fake_payload.get("blocking_summary"))
            self.assertEqual(payload["suite"], fake_payload.get("suite"))
            self.assertEqual(payload["next_command"], fake_payload["next_command"])
            self.assertEqual(payload["active_workspace_required_for_production"], fake_payload["active_workspace_required_for_production"])
        finally:
            preview_server.setup_status = original_setup_status

    def test_setup_status_api_falls_back_suite_dependency_summary_when_top_level_missing(self) -> None:
        workspace = self._write_ready_setup()
        original_setup_status = preview_server.setup_status

        suite_dependencies = [
            {
                "repo_label": "suite-ppt-master",
                "status": "ready",
                "short_sha": "fedcba987654",
            },
        ]
        fake_payload = {
            "schema_version": "deck_master_setup_status.v2",
            "status": "ready",
            "install_ready": True,
            "workspace_ready": True,
            "run_ready": True,
            "production_ready": True,
            "active_workspace_required_for_production": True,
            "config": {
                "install_root": str(ROOT),
                "active_workspace": str(workspace.resolve()),
                "default_runs_dir": str(self.runs_dir),
            },
            "suite": {
                "status": "ready",
                "full_suite_ready": True,
                "external_dependency_status": suite_dependencies,
            },
        }

        def fake_setup_status(**kwargs):
            return fake_payload

        preview_server.setup_status = fake_setup_status
        try:
            status, payload = self.handler.request("GET", "/api/setup-status")
            self.assertEqual(HTTPStatus.OK, status)
            self.assertEqual(payload["external_dependency_status"], suite_dependencies)
            self.assertEqual(payload["suite_external_dependency_status"], suite_dependencies)
            self.assertIn("blocking_summary", payload)
            self.assertEqual(payload["blocking_summary"], [])
            self.assertEqual(payload["run_ready"], True)
            self.assertEqual(payload["production_ready"], True)
        finally:
            preview_server.setup_status = original_setup_status

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
