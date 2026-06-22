"""Tests for Package F2/F3 — Page Workbench actions and External Result Visibility."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "preview"))
sys.path.insert(0, str(ROOT / "scripts"))

from server import PreviewHandler  # noqa: E402
from orchestrate.export_queue import export_queue  # noqa: E402
from review.workbench import WorkbenchError, execute_review_action  # noqa: E402
from runtime.run_state import create_run, read_json, write_json  # noqa: E402
from runtime.events import read_events  # noqa: E402
from runtime.import_log import append_import_log  # noqa: E402
from feedback.library_feedback import record_library_feedback  # noqa: E402


def _setup_run(tmp: Path) -> Path:
    runs_dir = tmp / "runs"
    runs_dir.mkdir()
    run_dir = create_run(runs_dir, {"project_name": "WbTest"}, run_id="wb-test")
    write_json(run_dir / "page_tasks.json", {
        "tasks": [
            {"beat_id": "beat_001", "source_decision": "reuse",
             "planning": {"core_claim": "Test claim", "decision_intent": "reuse"}},
            {"beat_id": "beat_002", "source_decision": "generate",
             "planning": {"core_claim": "ROI", "decision_intent": "generate"}},
        ]
    })
    links_dir = run_dir / "links"
    links_dir.mkdir(exist_ok=True)
    (links_dir / "beat_001.svg").write_text("<svg></svg>\n", encoding="utf-8")
    (links_dir / "beat_002.svg").write_text("<svg></svg>\n", encoding="utf-8")
    write_json(run_dir / "preview_manifest.json", {
        "run_id": "wb-test",
        "title": "WbTest",
        "status": "ready",
        "pages": [
            {
                "page_id": "beat_001",
                "beat_id": "beat_001",
                "order": 1,
                "title": "Test claim",
                "source_type": "library_slide",
                "preview_path": "links/beat_001.svg",
                "narrative_role": "test",
                "decision": "needs_review",
            },
            {
                "page_id": "beat_002",
                "beat_id": "beat_002",
                "order": 2,
                "title": "ROI",
                "source_type": "placeholder",
                "preview_path": "links/beat_002.svg",
                "narrative_role": "test",
                "decision": "needs_review",
            },
        ],
    })
    quality_dir = run_dir / "quality_reports"
    quality_dir.mkdir(exist_ok=True)
    write_json(quality_dir / "draft_gate.json", {
        "schema_version": "deck_quality_report.v1",
        "gate": "draft",
        "status": "pass",
        "blocks_delivery": False,
        "summary": {"p0_count": 0, "p1_count": 0, "p2_count": 0},
        "findings": [],
    })
    return run_dir


class MockHandler(PreviewHandler):
    def __init__(self, runs_dir: Path):
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO()
        self.client_address = ("127.0.0.1", 0)
        self.request_version = "HTTP/1.1"
        self.requestline = ""
        self._headers_buffer: list[bytes] = []
        self.headers: dict[str, str] = {}
        self.runs_dir = runs_dir
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
        try:
            return status_code, json.loads(body)
        except json.JSONDecodeError:
            return status_code, {"raw": body}


class WorkbenchDirectTest(unittest.TestCase):
    """Test workbench actions directly."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_wb_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_approve_page(self) -> None:
        result = execute_review_action(self.run_dir, "beat_001", "approve")
        self.assertEqual(result["status"], "ok")
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(task["review_status"], "approved")
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_001")
        self.assertEqual(page["review_status"], "approved")
        self.assertEqual(page["decision"], "approved")
        queue = export_queue(self.run_dir, {"approved"})
        self.assertEqual([p["page_id"] for p in queue["pages"]], ["beat_001"])

    def test_reject_page(self) -> None:
        result = execute_review_action(self.run_dir, "beat_001", "reject", reason="Weak evidence")
        self.assertEqual(result["status"], "ok")
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(task["review_status"], "rejected")
        self.assertEqual(task["rejection_reason"], "Weak evidence")
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_001")
        self.assertEqual(page["review_status"], "rejected")
        self.assertEqual(page["decision"], "rejected")
        queue = export_queue(self.run_dir, {"approved"})
        self.assertEqual(queue["pages"], [])

    def test_request_evidence_updates_review_state(self) -> None:
        result = execute_review_action(
            self.run_dir,
            "beat_001",
            "request_evidence",
            reason="Need customer evidence",
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("finding_id", result)
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(task["review_status"], "needs_evidence")
        self.assertEqual(task["action_intent"], "request_evidence")
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_001")
        self.assertEqual(page["review_status"], "needs_evidence")
        self.assertEqual(page["action_intent"], "request_evidence")
        self.assertTrue((self.run_dir / "evidence_requests" / "ev_req_beat_001.json").exists())

    def test_approve_requires_preview_manifest(self) -> None:
        (self.run_dir / "preview_manifest.json").unlink()
        with self.assertRaises(WorkbenchError) as ctx:
            execute_review_action(self.run_dir, "beat_001", "approve")
        self.assertIn("preview_manifest.json", str(ctx.exception))

    def test_add_note(self) -> None:
        execute_review_action(self.run_dir, "beat_001", "add_note", note="Looks good overall")
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(len(task["review_notes"]), 1)
        self.assertEqual(task["review_notes"][0]["note"], "Looks good overall")
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_001")
        self.assertEqual("Looks good overall", page["notes"])

    def test_bootstraps_page_tasks_from_preview_manifest_when_missing(self) -> None:
        # Regression: ISSUE-001 — direct preview fixtures can act without page_tasks.json.
        # Found by /qa on 2026-06-22
        # Report: .gstack/qa-reports/qa-report-deck-master-main-2026-06-22.md
        (self.run_dir / "page_tasks.json").unlink()

        result = execute_review_action(self.run_dir, "beat_001", "approve")

        self.assertEqual(result["status"], "ok")
        page_tasks = read_json(self.run_dir / "page_tasks.json")
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(task["review_status"], "approved")

    def test_add_note_preserves_legacy_approved_status(self) -> None:
        # Regression: ISSUE-001 — legacy keep pages must stay approved after add_note.
        # Found by /qa on 2026-06-22
        # Report: .gstack/qa-reports/qa-report-deck-master-main-2026-06-22.md
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_002")
        page["decision"] = "keep"
        page.pop("review_status", None)
        page.pop("action_intent", None)
        write_json(self.run_dir / "preview_manifest.json", preview)

        execute_review_action(self.run_dir, "beat_002", "add_note", note="Keep continuity")

        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_002")
        self.assertEqual("approved", page["review_status"])
        self.assertEqual("keep", page["decision"])
        self.assertEqual("Keep continuity", page["notes"])

    def test_lock_source(self) -> None:
        execute_review_action(self.run_dir, "beat_001", "lock_source", actor="user")
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertTrue(task["locked"])

    def test_convert_to_generate(self) -> None:
        execute_review_action(self.run_dir, "beat_001", "convert_to_generate")
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(task["source_decision"], "generate")
        self.assertEqual(task["planning"]["decision_intent"], "generate")
        preview = read_json(self.run_dir / "preview_manifest.json")
        page = next(p for p in preview["pages"] if p["page_id"] == "beat_001")
        self.assertEqual(page["source_decision"], "generate")
        self.assertEqual(page["review_status"], "needs_review")
        self.assertEqual(page["action_intent"], "generate")

    def test_move_to_appendix(self) -> None:
        execute_review_action(self.run_dir, "beat_001", "move_to_appendix")
        page_tasks = json.loads((self.run_dir / "page_tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in page_tasks["tasks"] if t["beat_id"] == "beat_001")
        self.assertEqual(task["section"], "appendix")

    def test_invalid_action_raises(self) -> None:
        with self.assertRaises(WorkbenchError):
            execute_review_action(self.run_dir, "beat_001", "invalid_action")

    def test_unknown_page_raises(self) -> None:
        with self.assertRaises(WorkbenchError):
            execute_review_action(self.run_dir, "beat_999", "approve")

    def test_p0_blocks_approval(self) -> None:
        # Add P0 finding.
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        write_json(quality_dir / "draft_gate.json", {
            "gate": "draft",
            "findings": [
                {"finding_id": "p0_test", "severity": "P0", "page_id": "beat_001",
                 "message": "P0 blocking"},
            ],
        })
        with self.assertRaises(WorkbenchError) as ctx:
            execute_review_action(self.run_dir, "beat_001", "approve")
        self.assertIn("P0", str(ctx.exception))

    def test_event_written(self) -> None:
        execute_review_action(self.run_dir, "beat_001", "approve")
        events = read_events(self.run_dir)
        wb_events = [e for e in events if "page_review" in str(e.get("step", ""))]
        self.assertTrue(len(wb_events) >= 1)


class WorkbenchAPITest(unittest.TestCase):
    """Test via HTTP handler."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_wb_api_")
        self.run_dir = _setup_run(Path(self._tmp))
        self.handler = MockHandler(Path(self._tmp) / "runs")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_review_action_api(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/page/beat_001/review-action?run_id=wb-test",
            body={"action": "approve", "actor": "user"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_review_action_add_note_updates_deck_api(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/page/beat_001/review-action?run_id=wb-test",
            body={"action": "add_note", "actor": "user", "note": "Keep this proof point."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

        deck_status, deck = self.handler.request("GET", "/api/deck?run_id=wb-test")
        self.assertEqual(deck_status, 200)
        page = next(p for p in deck["pages"] if p["page_id"] == "beat_001")
        self.assertEqual("Keep this proof point.", page["notes"])

    def test_review_action_missing_action(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/page/beat_001/review-action?run_id=wb-test",
            body={"actor": "user"},
        )
        self.assertEqual(status, 400)

    def test_review_action_approve_keeps_queue_summary_and_metrics_consistent(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/page/beat_001/review-action?run_id=wb-test",
            body={"action": "approve", "actor": "user"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

        queue_status, queue = self.handler.request("GET", "/api/export-queue/wb-test")
        self.assertEqual(queue_status, 200)
        self.assertEqual([p["page_id"] for p in queue["pages"]], ["beat_001"])
        self.assertEqual(queue["blocked_pages"], [])

        summary_status, summary = self.handler.request("GET", "/api/review-summary/wb-test")
        self.assertEqual(summary_status, 200)
        self.assertEqual(summary["counts"]["approved"], 1)
        self.assertEqual(summary["counts"]["needs_review"], 1)

        metrics_status, metrics = self.handler.request("GET", "/api/run-metrics/wb-test")
        self.assertEqual(metrics_status, 200)
        self.assertEqual(metrics["counts"]["approved"], summary["counts"]["approved"])
        self.assertEqual(metrics["counts"]["needs_review"], summary["counts"]["needs_review"])

    def test_review_action_reject_excludes_page_from_export_queue(self) -> None:
        status, data = self.handler.request(
            "POST",
            "/api/page/beat_001/review-action?run_id=wb-test",
            body={"action": "reject", "actor": "user", "reason": "Weak evidence"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

        queue_status, queue = self.handler.request("GET", "/api/export-queue/wb-test")
        self.assertEqual(queue_status, 200)
        self.assertEqual(queue["pages"], [])
        self.assertEqual(queue["blocked_pages"], [])


class ExternalResultsVisibilityTest(unittest.TestCase):
    """Test F3 external result visibility API."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_f3_")
        self.run_dir = _setup_run(Path(self._tmp))
        self.handler = MockHandler(Path(self._tmp) / "runs")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_external_results_empty(self) -> None:
        status, data = self.handler.request("GET", "/api/external-results/wb-test")
        self.assertEqual(status, 200)
        self.assertIsNone(data["narrative_advice"])
        self.assertEqual(data["external_reviews"], [])
        self.assertEqual(data["generation_results"], [])

    def test_external_results_with_narrative_advice(self) -> None:
        results_dir = self.run_dir / "advisor_results"
        results_dir.mkdir()
        write_json(results_dir / "narrative_advice.json", {
            "schema_version": "deck_narrative_advice.v1",
            "run_id": "wb-test",
            "advisor": "codex",
            "core_thesis_rewrite": "Test thesis",
        })
        status, data = self.handler.request("GET", "/api/external-results/wb-test")
        self.assertEqual(status, 200)
        self.assertIsNotNone(data["narrative_advice"])
        self.assertEqual(data["narrative_advice"]["advisor"], "codex")

    def test_external_results_with_quality_reviews(self) -> None:
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir(exist_ok=True)
        write_json(quality_dir / "external_semantic_codex_gate.json", {
            "gate": "external_semantic",
            "reviewer": "codex",
            "findings": [{"finding_id": "f1", "severity": "P1", "message": "Test"}],
        })
        status, data = self.handler.request("GET", "/api/external-results/wb-test")
        self.assertEqual(len(data["external_reviews"]), 1)
        self.assertEqual(data["external_reviews"][0]["reviewer"], "codex")

    def test_external_results_include_runtime_readiness_summary(self) -> None:
        append_import_log(
            self.run_dir,
            import_type="ppt_library_selection",
            source="ppt-library",
            status="imported",
            canonical_refs=["external/ppt_library/library_results.json"],
        )
        record_library_feedback(
            self.run_dir,
            run_id="wb-test",
            page_task_id="page-001",
            beat_id="beat-001",
            candidate_id="slide-001",
            outcome="approved",
        )
        write_json(self.run_dir / "quality_reports" / "external_visual_codex_gate.json", {
            "gate": "external_visual",
            "reviewer": "codex",
            "status": "rework_required",
            "blocks_delivery": True,
            "summary": {"p0_count": 0, "p1_count": 1, "p2_count": 0},
            "findings": [{"finding_id": "f1", "severity": "P1", "message": "Test"}],
        })

        status, data = self.handler.request("GET", "/api/external-results/wb-test")

        self.assertEqual(200, status)
        readiness = data["runtime_readiness"]
        self.assertIn("suite_readiness", readiness)
        self.assertEqual(2, readiness["imports_summary"]["total"])
        self.assertTrue(readiness["quality_blocking_summary"]["delivery_blocked"])
        self.assertEqual(1, readiness["feedback_pending_summary"]["pending"])

    def test_runtime_readiness_api_returns_summary(self) -> None:
        status, data = self.handler.request("GET", "/api/runtime-readiness/wb-test")

        self.assertEqual(200, status)
        self.assertEqual("deck_master_runtime_readiness.v1", data["schema_version"])
        self.assertIn("suite_readiness", data)
        self.assertIn("imports_summary", data)


if __name__ == "__main__":
    unittest.main()
