from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from team.identity import (
    add_user,
    assign_role,
    list_audit,
    list_users,
    team_dir,
)


class TeamIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_add_user_success(self) -> None:
        user = add_user(self.temp_dir, "u1", "Alice", email="a@x.com", role="editor")
        self.assertEqual(user["user_id"], "u1")
        self.assertEqual(user["name"], "Alice")
        self.assertEqual(user["email"], "a@x.com")
        self.assertEqual(user["role"], "editor")
        self.assertIn("created_at", user)

        saved = list_users(self.temp_dir)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["user_id"], "u1")

    def test_add_user_duplicate_raises(self) -> None:
        add_user(self.temp_dir, "u1", "Alice")
        with self.assertRaises(ValueError) as ctx:
            add_user(self.temp_dir, "u1", "Bob")
        self.assertIn("u1", str(ctx.exception))

    def test_assign_role_success(self) -> None:
        add_user(self.temp_dir, "u1", "Alice", role="member")
        updated = assign_role(self.temp_dir, "u1", "admin")
        self.assertEqual(updated["role"], "admin")
        self.assertIn("role_updated_at", updated)

        users = list_users(self.temp_dir)
        self.assertEqual(users[0]["role"], "admin")

    def test_assign_role_unknown_user_raises(self) -> None:
        with self.assertRaises(ValueError):
            assign_role(self.temp_dir, "no-such", "admin")

    def test_list_users_empty_when_no_team_dir(self) -> None:
        # 个人模式：team dir 不存在时返回空列表，不报错
        ws = self.temp_dir / "fresh-workspace"
        ws.mkdir()
        self.assertFalse(team_dir(ws).exists())
        self.assertEqual(list_users(ws), [])

    def test_list_audit_records_actions(self) -> None:
        add_user(self.temp_dir, "u1", "Alice", role="member")
        assign_role(self.temp_dir, "u1", "admin")

        audit = list_audit(self.temp_dir)
        actions = [e["action"] for e in audit]
        self.assertIn("user.added", actions)
        self.assertIn("role.assigned", actions)

        added = next(e for e in audit if e["action"] == "user.added")
        self.assertEqual(added["user_id"], "u1")
        self.assertEqual(added["name"], "Alice")
        self.assertIn("timestamp", added)

    def test_list_audit_empty_when_no_log(self) -> None:
        ws = self.temp_dir / "empty-ws"
        ws.mkdir()
        self.assertEqual(list_audit(ws), [])


if __name__ == "__main__":
    unittest.main()
