from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from quality.overrides import (
    create_override,
    has_active_override,
    list_active_overrides,
    load_overrides,
    revoke_override,
)


class OverrideGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.run_dir = temp_dir / "run_test"
        self.run_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

    # ---- P0 override rejected ----
    def test_p0_override_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            create_override(
                self.run_dir, "finding_001", "P0",
                reason="test", approver="alice",
            )
        self.assertIn("P0", str(ctx.exception))

    # ---- P1 missing approver rejected ----
    def test_p1_missing_approver_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            create_override(
                self.run_dir, "finding_001", "P1",
                reason="test", approver="",
            )
        self.assertIn("approver", str(ctx.exception).lower())

    # ---- P1 missing reason rejected ----
    def test_p1_missing_reason_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            create_override(
                self.run_dir, "finding_001", "P1",
                reason="", approver="alice",
            )
        self.assertIn("reason", str(ctx.exception).lower())

    # ---- P1 override created successfully ----
    def test_p1_override_created(self) -> None:
        override = create_override(
            self.run_dir, "finding_001", "P1",
            reason="Accepted risk for demo", approver="alice",
        )
        self.assertEqual(override["status"], "active")
        self.assertEqual(override["severity"], "P1")
        self.assertEqual(override["target_id"], "finding_001")
        self.assertEqual(override["approver"], "alice")
        self.assertIn("expires_at", override)
        self.assertEqual(override["override_id"], "override_001")

    # ---- List returns active overrides ----
    def test_list_returns_active_overrides(self) -> None:
        create_override(self.run_dir, "f1", "P1", reason="r1", approver="a")
        create_override(self.run_dir, "f2", "P2", reason="r2", approver="a")
        active = list_active_overrides(self.run_dir)
        self.assertEqual(len(active), 2)

    # ---- Expired override not in active list ----
    def test_expired_override_not_in_active_list(self) -> None:
        override = create_override(
            self.run_dir, "f1", "P1", reason="r1", approver="a", expires_days=14,
        )
        # Manually set expires_at to past
        overrides = load_overrides(self.run_dir)
        overrides[0]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        from quality.overrides import save_overrides
        save_overrides(self.run_dir, overrides)

        active = list_active_overrides(self.run_dir)
        self.assertEqual(len(active), 0)

    # ---- Revoke changes status to revoked ----
    def test_revoke_changes_status(self) -> None:
        create_override(self.run_dir, "f1", "P1", reason="r1", approver="a")
        revoked = revoke_override(self.run_dir, "override_001", reason="No longer needed")
        self.assertEqual(revoked["status"], "revoked")
        self.assertIn("revoked_at", revoked)
        self.assertEqual(revoked["revoke_reason"], "No longer needed")

    # ---- Revoked override not in active list ----
    def test_revoked_not_in_active_list(self) -> None:
        create_override(self.run_dir, "f1", "P1", reason="r1", approver="a")
        revoke_override(self.run_dir, "override_001")
        active = list_active_overrides(self.run_dir)
        self.assertEqual(len(active), 0)
        self.assertFalse(has_active_override(self.run_dir, "f1"))

    # ---- Override writes typed event ----
    def test_override_writes_typed_event(self) -> None:
        create_override(self.run_dir, "f1", "P1", reason="risk accepted", approver="alice")
        events_path = self.run_dir / "events.jsonl"
        self.assertTrue(events_path.exists(), "events.jsonl should exist after override creation")
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 1)
        event = json.loads(lines[-1])
        self.assertEqual(event["event_type"], "manual_action")
        self.assertEqual(event["step"], "override.create")
        self.assertIn("f1", event["message"])


if __name__ == "__main__":
    unittest.main()
