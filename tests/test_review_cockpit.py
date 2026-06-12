"""Tests for Package F1 — Review Cockpit 2.0 read-only APIs."""

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
from review.readiness import compute_claim_coverage, compute_deck_readiness, compute_next_actions  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402


def _setup_run(tmp: Path) -> Path:
    runs_dir = tmp / "runs"
    runs_dir.mkdir()
    run_dir = create_run(runs_dir, {"project_name": "ReviewTest"}, run_id="review-test")
    write_json(run_dir / "deck_brief.json", {"run_id": "review-test", "objective": "Test"})
    write_json(run_dir / "claim_map.json", {
        "run_id": "review-test",
        "claims": [
            {"claim_id": "claim_01", "claim": "客户需要统一运营闭环"},
            {"claim_id": "claim_02", "claim": "ROI 可量化"},
        ],
    })
    write_json(run_dir / "page_tasks.json", {
        "tasks": [
            {"beat_id": "beat_001", "source_decision": "reuse",
             "planning": {"core_claim": "客户需要统一运营闭环", "decision_intent": "reuse"}},
            {"beat_id": "beat_002", "source_decision": "generate",
             "planning": {"core_claim": "ROI 可量化", "decision_intent": "generate"}},
            {"beat_id": "beat_003", "source_decision": "manual_placeholder",
             "planning": {"core_claim": "", "decision_intent": "manual_placeholder"}},
        ]
    })
    write_json(run_dir / "claim_evidence_graph.json", {
        "schema_version": "deck_claim_evidence_graph.v1",
        "run_id": "review-test",
        "claims": [
            {"claim_id": "claim_01", "statement": "客户需要统一运营闭环",
             "page_refs": ["beat_001"], "supporting_evidence": ["evidence_001"]},
            {"claim_id": "claim_02", "statement": "ROI 可量化",
             "page_refs": ["beat_002"], "supporting_evidence": []},
        ],
        "evidence": [
            {"evidence_id": "evidence_001", "source_ref": "src_001",
             "evidence_type": "customer_material", "publication_status": "safe_to_use"},
        ],
        "gaps": [
            {"gap_id": "gap_001", "claim_id": "claim_02",
             "description": "ROI 缺少客户指标证据"},
        ],
    })
    write_json(run_dir / "preview_manifest.json", {
        "run_id": "review-test",
        "pages": [
            {"beat_id": "beat_001", "preview_image": "img/beat_001.png", "source_type": "reuse"},
            {"beat_id": "beat_002", "preview_image": "", "source_type": "generate"},
            {"beat_id": "beat_003", "preview_image": "", "source_type": "placeholder"},
        ],
    })
    # Create quality reports with P1 findings.
    quality_dir = run_dir / "quality_reports"
    quality_dir.mkdir(exist_ok=True)
    write_json(quality_dir / "draft_v2_gate.json", {
        "schema_version": "deck_quality_report.v1",
        "gate": "draft_v2",
        "status": "rework_required",
        "blocks_delivery": False,
        "summary": {"p0_count": 0, "p1_count": 1, "p2_count": 2},
        "findings": [
            {"finding_id": "draft_001", "severity": "P1", "page_id": "beat_002",
             "message": "ROI 页面缺指标", "repair_instruction": "补充客户指标"},
        ],
    })
    return run_dir


class MockHandler(PreviewHandler):
    """Testable handler with mock I/O."""

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


class ReviewSummaryAPITest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_review_")
        self.run_dir = _setup_run(Path(self._tmp))
        self.handler = MockHandler(Path(self._tmp) / "runs")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_review_summary_api(self) -> None:
        status, data = self.handler.request("GET", "/api/review-summary/review-test")
        self.assertEqual(status, 200)
        self.assertEqual(data["run_id"], "review-test")
        self.assertIn("deck_readiness", data)
        self.assertIn("counts", data)

    def test_deck_readiness_overall(self) -> None:
        status, data = self.handler.request("GET", "/api/review-summary/review-test")
        readiness = data["deck_readiness"]
        self.assertIn(readiness["overall"], {"ready", "blocked", "needs_review"})

    def test_deck_readiness_counts(self) -> None:
        status, data = self.handler.request("GET", "/api/review-summary/review-test")
        counts = data["counts"]
        self.assertEqual(counts["pages"], 3)
        self.assertEqual(counts["p1"], 1)

    def test_deck_readiness_uses_preview_and_sourcing_plan(self) -> None:
        write_json(self.run_dir / "preview_manifest.json", {
            "run_id": "review-test",
            "pages": [
                {"page_id": "beat_001", "decision": "approved", "review_status": "approved"},
                {"page_id": "beat_002", "decision": "rejected", "review_status": "rejected"},
                {"page_id": "beat_003", "decision": "needs_review"},
            ],
        })
        write_json(self.run_dir / "sourcing_plan.json", {
            "run_id": "review-test",
            "decisions": [
                {"beat_id": "beat_001", "source_decision": "adapt"},
                {"beat_id": "beat_002", "source_decision": "adapt"},
                {"beat_id": "beat_003", "source_decision": "generate"},
            ],
        })
        result = compute_deck_readiness(self.run_dir)
        counts = result["counts"]
        self.assertEqual(counts["approved"], 1)
        self.assertEqual(counts["rejected"], 1)
        self.assertEqual(counts["needs_review"], 1)
        self.assertEqual(counts["reuse"], 0)
        self.assertEqual(counts["adapt"], 2)
        self.assertEqual(counts["generate"], 1)

    def test_review_summary_not_found(self) -> None:
        status, data = self.handler.request("GET", "/api/review-summary/nonexistent")
        self.assertEqual(status, 404)


class ClaimCoverageAPITest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_claim_cov_")
        self.run_dir = _setup_run(Path(self._tmp))
        self.handler = MockHandler(Path(self._tmp) / "runs")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_claim_coverage_api(self) -> None:
        status, data = self.handler.request("GET", "/api/claim-coverage/review-test")
        self.assertEqual(status, 200)
        self.assertIn("claims", data)

    def test_claim_coverage_evidence_gap(self) -> None:
        status, data = self.handler.request("GET", "/api/claim-coverage/review-test")
        claims = data["claims"]
        # claim_02 has no evidence -> evidence_gap.
        claim_02 = next(c for c in claims if c["claim_id"] == "claim_02")
        self.assertEqual(claim_02["status"], "evidence_gap")

    def test_claim_coverage_covered(self) -> None:
        status, data = self.handler.request("GET", "/api/claim-coverage/review-test")
        claims = data["claims"]
        claim_01 = next(c for c in claims if c["claim_id"] == "claim_01")
        self.assertEqual(claim_01["status"], "covered")


class NextActionsAPITest(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_next_act_")
        self.run_dir = _setup_run(Path(self._tmp))
        self.handler = MockHandler(Path(self._tmp) / "runs")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_next_actions_api(self) -> None:
        status, data = self.handler.request("GET", "/api/next-actions/review-test")
        self.assertEqual(status, 200)
        self.assertIn("actions", data)

    def test_next_actions_max_5(self) -> None:
        status, data = self.handler.request("GET", "/api/next-actions/review-test")
        self.assertLessEqual(len(data["actions"]), 5)

    def test_next_actions_includes_p1_finding(self) -> None:
        status, data = self.handler.request("GET", "/api/next-actions/review-test")
        actions = data["actions"]
        quality_actions = [a for a in actions if a["action_type"] == "fix_quality_finding"]
        self.assertTrue(len(quality_actions) >= 1)

    def test_next_actions_includes_evidence_gap(self) -> None:
        status, data = self.handler.request("GET", "/api/next-actions/review-test")
        actions = data["actions"]
        gap_actions = [a for a in actions if a["action_type"] == "fix_evidence_gap"]
        self.assertTrue(len(gap_actions) >= 1)

    def test_next_actions_includes_placeholder(self) -> None:
        status, data = self.handler.request("GET", "/api/next-actions/review-test")
        actions = data["actions"]
        placeholder_actions = [a for a in actions if a["action_type"] == "resolve_placeholder"]
        self.assertTrue(len(placeholder_actions) >= 1)

    def test_next_actions_includes_failed_generation_task_from_tasks_array(self) -> None:
        tasks_dir = self.run_dir / "generation_tasks"
        tasks_dir.mkdir(exist_ok=True)
        write_json(tasks_dir / "index.json", {
            "run_id": "review-test",
            "tasks": [
                {
                    "task_id": "generation_001_beat_002",
                    "beat_id": "beat_002",
                    "status": "failed",
                },
            ],
        })
        result = compute_next_actions(self.run_dir)
        rerun_actions = [a for a in result["actions"] if a["action_type"] == "rerun_generation"]
        self.assertEqual(len(rerun_actions), 1)
        self.assertEqual(rerun_actions[0]["target"], "beat_002")


class ReviewCockpitDirectTest(unittest.TestCase):
    """Test readiness/coverage/actions functions directly."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dm_review_direct_")
        self.run_dir = _setup_run(Path(self._tmp))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_readiness_returns_valid_structure(self) -> None:
        result = compute_deck_readiness(self.run_dir)
        self.assertIn("deck_readiness", result)
        self.assertIn("counts", result)
        self.assertIn("overall", result["deck_readiness"])

    def test_coverage_returns_valid_structure(self) -> None:
        result = compute_claim_coverage(self.run_dir)
        self.assertIn("claims", result)
        for claim in result["claims"]:
            self.assertIn("claim_id", claim)
            self.assertIn("status", claim)

    def test_next_actions_returns_valid_structure(self) -> None:
        result = compute_next_actions(self.run_dir)
        self.assertIn("actions", result)
        for action in result["actions"]:
            self.assertIn("action_type", action)
            self.assertIn("message", action)


if __name__ == "__main__":
    unittest.main()
