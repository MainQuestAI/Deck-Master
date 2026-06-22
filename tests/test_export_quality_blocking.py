from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "orchestrate"))
sys.path.insert(0, str(ROOT / "scripts" / "preview"))

from export_queue import check_page_quality_blocking, export_queue


def _make_manifest(pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run_id": "run-test",
        "title": "Test Run",
        "status": "ready",
        "pages": pages,
    }


def _base_page(
    page_id: str = "page_001",
    *,
    decision: str = "approved",
    review_status: str | None = None,
    action_intent: str | None = None,
) -> dict[str, Any]:
    page: dict[str, Any] = {
        "page_id": page_id,
        "order": 1,
        "source_type": "generated",
        "preview_path": f"previews/{page_id}.png",
        "narrative_role": "intro",
        "decision": decision,
    }
    if review_status is not None:
        page["review_status"] = review_status
    if action_intent is not None:
        page["action_intent"] = action_intent
    return page


def _write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    (run_dir / "preview_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_final_readiness(run_dir, ready=True)


def _write_final_readiness(run_dir: Path, *, ready: bool, reason: str = "") -> None:
    delivery_dir = run_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "deck_final_readiness.v1",
        "run_id": run_dir.name,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "blockers": [] if ready else [{"code": "fixture_block", "severity": "P0", "message": reason or "blocked"}],
    }
    (delivery_dir / "final_readiness.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_gate(
    run_dir: Path,
    gate: str,
    findings: list[dict[str, Any]],
    *,
    status: str | None = None,
    blocks_delivery: bool | None = None,
) -> None:
    quality_dir = run_dir / "quality_reports"
    quality_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "gate": gate,
        "status": status or ("rework_required" if findings else "pass"),
        "blocks_delivery": bool(findings) if blocks_delivery is None else blocks_delivery,
        "findings": findings,
        "page_findings": [],
    }
    (quality_dir / f"{gate}_gate.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class ExportQualityBlockingTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = temp_dir / "run"
        self.run_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

    # ---- approved page without findings enters client queue ----
    def test_approved_page_without_findings_enters_client_queue(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual(["p1"], [p["page_id"] for p in result["pages"]])
        self.assertEqual([], result["blocked_pages"])
        self.assertEqual(0, result["blocked_count"])
        self.assertEqual("client", result["queue_type"])

    def test_missing_final_readiness_blocks_client_queue(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        (self.run_dir / "delivery" / "final_readiness.json").unlink()
        _write_gate(self.run_dir, "draft", [])

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual([], result["pages"])
        self.assertEqual(1, result["blocked_count"])
        self.assertTrue(result["blocked_pages"][0]["final_readiness_blocked"])
        self.assertIn("Final readiness", result["blocked_pages"][0]["final_readiness_reason"])

    def test_internal_queue_marks_degraded_without_final_readiness(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        (self.run_dir / "delivery" / "final_readiness.json").unlink()
        _write_gate(self.run_dir, "draft", [])

        result = export_queue(self.run_dir, {"approved"}, queue_type="internal")

        self.assertEqual(["p1"], [p["page_id"] for p in result["pages"]])
        self.assertTrue(result["final_readiness"]["degraded"])

    # ---- P0 finding blocks client queue unconditionally ----
    def test_p0_finding_blocks_client_queue(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(
            self.run_dir,
            "draft",
            [{"page_id": "p1", "severity": "P0", "finding_id": "F-P0-1", "message": "critical"}],
        )

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual([], [p["page_id"] for p in result["pages"]])
        self.assertEqual(1, result["blocked_count"])
        blocked = result["blocked_pages"][0]
        self.assertTrue(blocked["quality_blocked"])
        self.assertIn("P0", blocked["quality_block_reason"])
        self.assertIn("F-P0-1", blocked["quality_block_reason"])

    # ---- P0 cannot be overridden ----
    def test_p0_not_overridden_by_allow_override(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(
            self.run_dir,
            "draft",
            [{"page_id": "p1", "severity": "P0", "finding_id": "F-P0-2", "message": "x"}],
        )

        result = export_queue(
            self.run_dir,
            {"approved"},
            queue_type="client",
            allow_quality_override=True,
        )

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])

    # ---- P1 without override blocks ----
    def test_p1_finding_blocks_without_override(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])
        _write_gate(
            self.run_dir,
            "render",
            [{"page_id": "p1", "severity": "P1", "finding_id": "F-P1-1", "message": "warn"}],
        )

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual([], [p["page_id"] for p in result["pages"]])
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("P1", result["blocked_pages"][0]["quality_block_reason"])

    # ---- P1 with active override for matching finding_id passes client queue ----
    def test_p1_passes_with_active_override_for_finding(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])
        _write_gate(
            self.run_dir,
            "render",
            [{"page_id": "p1", "severity": "P1", "finding_id": "F-P1-2", "message": "y"}],
        )
        # 写入 active override（target_id 必须匹配 finding_id）
        quality_dir = self.run_dir / "quality_reports"
        overrides = [
            {
                "schema_version": "deck_quality_override.v1",
                "override_id": "override_001",
                "target_id": "F-P1-2",
                "severity": "P1",
                "status": "active",
                "expires_at": "2099-12-31T00:00:00+00:00",
                "reason": "approved",
                "approver": "qa",
            }
        ]
        (quality_dir / "overrides.json").write_text(
            json.dumps(overrides), encoding="utf-8"
        )

        result = export_queue(
            self.run_dir,
            {"approved"},
            queue_type="client",
            allow_quality_override=True,
        )

        self.assertEqual(["p1"], [p["page_id"] for p in result["pages"]])
        self.assertEqual(0, result["blocked_count"])
        self.assertTrue(result["pages"][0].get("quality_override_active"))

    # ---- P1 with active override for DIFFERENT finding_id still blocks ----
    def test_p1_active_override_mismatch_blocks(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])
        _write_gate(
            self.run_dir,
            "render",
            [{"page_id": "p1", "severity": "P1", "finding_id": "F-P1-2", "message": "y"}],
        )
        # Override 的 target_id 与 finding_id 不匹配
        quality_dir = self.run_dir / "quality_reports"
        overrides = [
            {
                "override_id": "override_001",
                "target_id": "DIFFERENT_FINDING",
                "status": "active",
                "expires_at": "2099-12-31T00:00:00+00:00",
            }
        ]
        (quality_dir / "overrides.json").write_text(
            json.dumps(overrides), encoding="utf-8"
        )

        result = export_queue(
            self.run_dir,
            {"approved"},
            queue_type="client",
            allow_quality_override=True,
        )

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("F-P1-2", result["blocked_pages"][0]["quality_block_reason"])

    # ---- needs_review cannot enter client queue ----
    def test_needs_review_blocked_in_client_queue(self) -> None:
        page = _base_page("p1", decision="needs_review", review_status="needs_review")
        _write_manifest(self.run_dir, _make_manifest([page]))

        result = export_queue(self.run_dir, {"needs_review"}, queue_type="client")

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("needs_review", result["blocked_pages"][0]["quality_block_reason"])

    # ---- internal queue ignores quality blocking ----
    def test_internal_queue_keeps_all_matched_pages(self) -> None:
        pages = [
            _base_page("p1", decision="approved", review_status="approved"),
            _base_page("p2", decision="needs_review", review_status="needs_review"),
            _base_page(
                "p3",
                decision="approved",
                review_status="approved",
                action_intent="manual_placeholder",
            ),
        ]
        _write_manifest(self.run_dir, _make_manifest(pages))
        _write_gate(
            self.run_dir,
            "draft",
            [
                {"page_id": "p1", "severity": "P0", "finding_id": "F-X", "message": "m"},
            ],
        )

        result = export_queue(
            self.run_dir,
            {"approved", "needs_review"},
            queue_type="internal",
        )

        self.assertEqual({"p1", "p2", "p3"}, {p["page_id"] for p in result["pages"]})
        self.assertEqual(0, result["blocked_count"])
        self.assertEqual("internal", result["queue_type"])
        # no override flag in internal mode
        for p in result["pages"]:
            self.assertNotIn("quality_override_active", p)

    # ---- manual_placeholder only allowed in internal queue ----
    def test_manual_placeholder_blocked_in_client_queue(self) -> None:
        page = _base_page(
            "p1",
            decision="approved",
            review_status="approved",
            action_intent="manual_placeholder",
        )
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("manual_placeholder", result["blocked_pages"][0]["quality_block_reason"])

    # ---- missing quality reports blocks approved pages (needs_quality_review) ----
    def test_missing_quality_reports_blocks_approved(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        # No quality_reports/ directory created.

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("needs_draft_gate", result["blocked_pages"][0]["quality_block_reason"])

    def test_empty_quality_reports_blocks_approved(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        (self.run_dir / "quality_reports").mkdir(parents=True, exist_ok=True)

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("needs_draft_gate", result["blocked_pages"][0]["quality_block_reason"])

    def test_run_level_p1_finding_blocks_client_queue(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(
            self.run_dir,
            "draft",
            [{"severity": "P1", "finding_id": "F-RUN-P1", "message": "business goal missing"}],
            status="rework_required",
            blocks_delivery=True,
        )

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("F-RUN-P1", result["blocked_pages"][0]["quality_block_reason"])

    def test_draft_v2_claim_level_gap_blocks_all_pages(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(
            self.run_dir,
            "draft_v2",
            [{"page_id": "claim_001", "severity": "P1", "finding_id": "F-CLAIM-GAP", "message": "evidence gap"}],
            status="rework_required",
            blocks_delivery=True,
        )

        result = export_queue(self.run_dir, {"approved"}, queue_type="client")

        self.assertEqual(0, len(result["pages"]))
        self.assertEqual(1, result["blocked_count"])
        self.assertIn("F-CLAIM-GAP", result["blocked_pages"][0]["quality_block_reason"])

    # ---- backward-compatible call signature still works ----
    def test_legacy_positional_signature_still_works(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])

        # Old callers pass only positional args; defaults must keep working.
        result = export_queue(self.run_dir, {"approved"})

        self.assertEqual("client", result["queue_type"])
        self.assertIn("blocked_pages", result)
        self.assertIn("blocked_count", result)

    # ---- check_page_quality_blocking helper directly ----
    def test_check_helper_returns_structured_result(self) -> None:
        page = _base_page("p1", decision="approved", review_status="approved")
        _write_manifest(self.run_dir, _make_manifest([page]))
        _write_gate(self.run_dir, "draft", [])
        _write_gate(
            self.run_dir,
            "delivery",
            [{"page_id": "p1", "severity": "P1", "finding_id": "F-D-1", "message": "z"}],
        )

        blocked = check_page_quality_blocking(
            self.run_dir, page, queue_type="client", allow_override=False
        )
        self.assertTrue(blocked["blocked"])
        self.assertEqual("P1", blocked["severity"])
        self.assertFalse(blocked["has_override"])

        # allow_override=True 需要 active override 匹配 finding_id 才能放行
        quality_dir = self.run_dir / "quality_reports"
        overrides = [
            {
                "override_id": "override_001",
                "target_id": "F-D-1",
                "severity": "P1",
                "status": "active",
                "expires_at": "2099-12-31T00:00:00+00:00",
                "reason": "ok",
                "approver": "qa",
            }
        ]
        (quality_dir / "overrides.json").write_text(
            json.dumps(overrides), encoding="utf-8"
        )

        allowed = check_page_quality_blocking(
            self.run_dir, page, queue_type="client", allow_override=True
        )
        self.assertFalse(allowed["blocked"])
        self.assertTrue(allowed["has_override"])

        blocked_without_flag = check_page_quality_blocking(
            self.run_dir, page, queue_type="client", allow_override=False
        )
        self.assertTrue(blocked_without_flag["blocked"])
        self.assertFalse(blocked_without_flag["has_override"])


if __name__ == "__main__":
    unittest.main()
