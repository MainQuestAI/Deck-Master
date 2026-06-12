"""Preview server handler tests — no socket binding required.

Uses mock I/O to test handler logic directly, avoiding ThreadingHTTPServer
which needs socket.bind() and fails in sandboxed environments.
"""
from __future__ import annotations

import io
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


# ---------------------------------------------------------------------------
# StudioServerTests — studio mode (no fixed run_dir)
# ---------------------------------------------------------------------------
class StudioServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runs_dir = self.temp_dir / "runs"
        self.handler = MockHandler(run_dir=None, runs_dir=self.runs_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

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
