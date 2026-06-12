"""Tests for scripts.team.approval — P5A-C Approval Flow."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.team.approval import (
    approve,
    is_approved,
    list_approvals,
    reject,
    submit_approval,
)


class TestApprovalFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        self.ws.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # ── submit / approve / reject 基本流程 ──────────────────────

    def test_submit_creates_pending_approval(self) -> None:
        result = submit_approval(self.ws, "run_001", "alice", notes="ready for review")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["run_id"], "run_001")
        self.assertEqual(result["submitted_by"], "alice")
        self.assertTrue(result["approval_id"].startswith("approval_"))

    def test_approve_transitions_to_approved(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        flow = approve(self.ws, req["approval_id"], "bob", notes="LGTM")
        self.assertEqual(flow["status"], "approved")
        self.assertEqual(flow["approved_by"], "bob")
        self.assertIn("approved_at", flow)

    def test_reject_transitions_to_rejected(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        flow = reject(self.ws, req["approval_id"], "carol", reason="missing data")
        self.assertEqual(flow["status"], "rejected")
        self.assertEqual(flow["rejected_by"], "carol")
        self.assertEqual(flow["rejection_reason"], "missing data")

    # ── audit log ────────────────────────────────────────────────

    def test_submit_writes_audit_log(self) -> None:
        submit_approval(self.ws, "run_001", "alice")
        audit_path = self.ws / "team" / "audit_log.jsonl"
        self.assertTrue(audit_path.exists())
        lines = [json.loads(l) for l in audit_path.read_text().splitlines() if l.strip()]
        actions = [e["action"] for e in lines]
        self.assertIn("approval.submitted", actions)

    def test_approve_writes_audit_log(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        approve(self.ws, req["approval_id"], "bob")
        audit_path = self.ws / "team" / "audit_log.jsonl"
        lines = [json.loads(l) for l in audit_path.read_text().splitlines() if l.strip()]
        actions = [e["action"] for e in lines]
        self.assertIn("approval.approved", actions)

    def test_reject_writes_audit_log(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        reject(self.ws, req["approval_id"], "carol", reason="bad")
        audit_path = self.ws / "team" / "audit_log.jsonl"
        lines = [json.loads(l) for l in audit_path.read_text().splitlines() if l.strip()]
        actions = [e["action"] for e in lines]
        self.assertIn("approval.rejected", actions)

    # ── 重复操作报错 ─────────────────────────────────────────────

    def test_double_approve_raises(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        approve(self.ws, req["approval_id"], "bob")
        with self.assertRaises(ValueError) as ctx:
            approve(self.ws, req["approval_id"], "bob")
        self.assertIn("not pending", str(ctx.exception))

    def test_approve_after_reject_raises(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        reject(self.ws, req["approval_id"], "carol", reason="no")
        with self.assertRaises(ValueError):
            approve(self.ws, req["approval_id"], "bob")

    def test_approve_nonexistent_raises(self) -> None:
        with self.assertRaises(ValueError):
            approve(self.ws, "approval_nonexistent", "bob")

    # ── is_approved ──────────────────────────────────────────────

    def test_is_approved_false_when_pending(self) -> None:
        submit_approval(self.ws, "run_001", "alice")
        self.assertFalse(is_approved(self.ws, "run_001"))

    def test_is_approved_true_after_approve(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        approve(self.ws, req["approval_id"], "bob")
        self.assertTrue(is_approved(self.ws, "run_001"))

    def test_is_approved_false_after_reject(self) -> None:
        req = submit_approval(self.ws, "run_001", "alice")
        reject(self.ws, req["approval_id"], "carol", reason="no")
        self.assertFalse(is_approved(self.ws, "run_001"))

    def test_is_approved_false_for_unknown_run(self) -> None:
        self.assertFalse(is_approved(self.ws, "run_never_submitted"))

    # ── list_approvals ───────────────────────────────────────────

    def test_list_approvals_returns_all(self) -> None:
        submit_approval(self.ws, "run_001", "alice")
        submit_approval(self.ws, "run_002", "alice")
        approvals = list_approvals(self.ws)
        self.assertEqual(len(approvals), 2)

    def test_list_approvals_empty_workspace(self) -> None:
        self.assertEqual(list_approvals(self.ws), [])


if __name__ == "__main__":
    unittest.main()
