from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "scripts"))

from runtime.run_state import (  # noqa: E402
    CLAIM_MAP_NAME,
    CONTEXT_MANIFEST_NAME,
    DECK_BRIEF_NAME,
    NARRATIVE_PLAN_NAME,
    PAGE_TASKS_NAME,
    PREVIEW_MANIFEST_NAME,
    REQUEST_NAME,
    SOURCING_PLAN_NAME,
)
from runtime.run_state_resolver import resolve_run_state
from runtime.setup_status import setup_status
from workspace.foundation import init_workspace


class RunStateResolverAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_root = Path(tempfile.mkdtemp(prefix="dm_run_state_test_"))
        self.home = self.tmp_root / "home"
        self.home.mkdir()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.addCleanup(self._restore_env)
        self.run_dir = self.tmp_root / "run"
        self.run_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(self.tmp_root, ignore_errors=True))

    def tearDown(self) -> None:
        self._restore_env()

    def _restore_env(self) -> None:
        if self.original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.original_home

    def _write_json(self, filename: str, payload: dict[str, object]) -> None:
        (self.run_dir / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _write_full_pipeline(self, include_preview: bool = False) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1", "run_mode": "production", "workspace": ""})
        self._write_json(CONTEXT_MANIFEST_NAME, {"run_id": "r1"})
        self._write_json(DECK_BRIEF_NAME, {"run_id": "r1"})
        self._write_json(CLAIM_MAP_NAME, {"run_id": "r1", "claims": []})
        self._write_json(NARRATIVE_PLAN_NAME, {"run_id": "r1", "beats": []})
        self._write_json(PAGE_TASKS_NAME, {"run_id": "r1", "tasks": []})
        self._write_json(SOURCING_PLAN_NAME, {"run_id": "r1", "tasks": []})
        if include_preview:
            self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": []})

    def test_setup_status_without_workspace_still_reports_not_production_ready(self) -> None:
        install_root = self.home / ".deck-master"
        install_root.mkdir(parents=True, exist_ok=True)
        config_path = install_root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": "deck_master_setup.v1",
                    "setup_completed_at": datetime.now(timezone.utc).isoformat(),
                    "install_root": str(install_root),
                    "active_workspace": "",
                    "default_runs_dir": str(install_root / "runs"),
                    "review_cockpit_url": "http://127.0.0.1:5050",
                    "agent_targets": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (install_root / "runs").mkdir(exist_ok=True)

        status = setup_status(run_mode="production")
        self.assertFalse(status["production_ready"])

    def test_production_run_without_workspace_is_blocked(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {})
        state = resolve_run_state(self.run_dir, run_mode="production")
        self.assertEqual("blocked_workspace", state["stage"])

    def test_fixture_and_dev_can_bypass_workspace(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1"})
        self._write_json(CONTEXT_MANIFEST_NAME, {})
        for mode, allow in (("fixture", False), ("dev", True)):
            with self.subTest(run_mode=mode):
                state = resolve_run_state(self.run_dir, run_mode=mode, dev_allow_unsetup=allow)
                self.assertNotEqual("blocked_workspace", state["stage"])

    def test_request_workspace_vs_cli_workspace_conflict_is_blocked(self) -> None:
        request_workspace = self.tmp_root / "request_workspace"
        cli_workspace = self.tmp_root / "cli_workspace"
        self._write_json(REQUEST_NAME, {"run_id": "r1", "workspace": str(request_workspace)})
        self._write_json(CONTEXT_MANIFEST_NAME, {})
        state = resolve_run_state(self.run_dir, run_mode="production", cli_workspace=str(cli_workspace))
        self.assertEqual("blocked_workspace", state["stage"])

    def test_needs_request_next_command_uses_start_entrypoint(self) -> None:
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_request", state["stage"])
        self.assertIn("deck-master start", state["next_command"])
        self.assertIn("--run-dir", state["next_command"])
        self.assertNotIn("start-conversation --run-dir", state["next_command"])

    def test_needs_context_next_command_uses_context_pack_import(self) -> None:
        self._write_json(REQUEST_NAME, {"run_id": "r1", "run_mode": "fixture"})
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_context", state["stage"])
        self.assertIn("deck-master import-context-pack", state["next_command"])
        self.assertIn("--input <context_pack.json>", state["next_command"])
        self.assertNotIn("start-conversation --run-dir", state["next_command"])

    def test_preview_review_status_takes_precedence_over_page_tasks(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(
            PREVIEW_MANIFEST_NAME,
            {
                "pages": [
                    {"page_id": "p1", "review_status": "needs_review", "decision": "approved"},
                ]
            },
        )
        page_tasks = {"run_id": "r1", "review_status": "approved"}
        self._write_json(PAGE_TASKS_NAME, page_tasks)
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_review", state["stage"])

    def test_generation_tasks_without_session_returns_generation_step(self) -> None:
        self._write_full_pipeline()
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_generation_session", state["stage"])
        self.assertIn("generation-session create", state["next_command"])

    def test_mixed_review_pages_require_review(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(
            PREVIEW_MANIFEST_NAME,
            {
                "run_id": "r1",
                "pages": [
                    {"page_id": "p1", "decision": "approved"},
                    {"page_id": "p2", "decision": "pending"},
                ],
            },
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_review", state["stage"])
        self.assertEqual(1, state["readiness"]["artifacts"]["preview_review_summary"]["pending_count"])

    def test_approved_and_rejected_pages_can_continue_to_quality_gate(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(
            PREVIEW_MANIFEST_NAME,
            {
                "run_id": "r1",
                "pages": [
                    {"page_id": "p1", "decision": "approved"},
                    {"page_id": "p2", "decision": "rejected"},
                ],
            },
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False}),
            encoding="utf-8",
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("ready_for_client_export", state["stage"])

    def test_completed_generation_session_requires_result_import(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json("generation_session.json", {"run_id": "r1", "status": "completed"})
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False}),
            encoding="utf-8",
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_generation_import", state["stage"])
        self.assertIn("generation-session import-results", state["next_command"])

    def test_awaiting_agent_execution_reports_agent_wait_state(self) -> None:
        self._write_full_pipeline(include_preview=True)
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json("generation_session.json", {"run_id": "r1", "status": "awaiting_agent_execution"})

        state = resolve_run_state(self.run_dir, run_mode="fixture")

        self.assertEqual("awaiting_agent_execution", state["stage"])
        self.assertIn("generation-session status", state["next_command"])

    def test_quality_required_generation_session_needs_quality_gate(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False, "created_at": "2026-06-17T09:59:00+00:00"}),
            encoding="utf-8",
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_draft_gate", state["stage"])
        self.assertIn("quality-gate draft", state["next_command"])

    def test_quality_required_generation_session_accepts_fresh_quality_gate(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False, "created_at": "2026-06-17T10:01:00+00:00"}),
            encoding="utf-8",
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_build", state["stage"])
        self.assertIn("deck-master build prepare", state["next_command"])

    def test_production_ready_for_build_requires_certified_builder_backend(self) -> None:
        workspace = self.tmp_root / "workspace"
        init_workspace(workspace, "Production Workspace")
        self._write_full_pipeline(include_preview=True)
        self._write_json(REQUEST_NAME, {"run_id": "r1", "run_mode": "production", "workspace": str(workspace)})
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False, "created_at": "2026-06-17T10:01:00+00:00"}),
            encoding="utf-8",
        )

        state = resolve_run_state(self.run_dir, run_mode="production")

        self.assertEqual("needs_builder_backend", state["stage"])
        self.assertEqual("deck-builder", state["recommended_skill"])
        self.assertIn("suite-status", state["next_command"])

    def test_build_manifest_without_render_needs_render(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False, "created_at": "2026-06-17T10:01:00+00:00"}),
            encoding="utf-8",
        )
        build_dir = self.run_dir / "build"
        build_dir.mkdir()
        (build_dir / "build_manifest.json").write_text(
            json.dumps({"schema_version": "deck_build_manifest.v1", "run_id": "r1", "status": "prepared"}),
            encoding="utf-8",
        )

        state = resolve_run_state(self.run_dir, run_mode="fixture")

        self.assertEqual("needs_render", state["stage"])
        self.assertIn("deck-master build run", state["next_command"])

    def test_quality_required_generation_session_with_render_can_export(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps({"status": "pass", "blocks_delivery": False, "created_at": "2026-06-17T10:01:00+00:00"}),
            encoding="utf-8",
        )
        render_dir = self.run_dir / "render_results"
        render_dir.mkdir()
        (render_dir / "render_result.json").write_text(
            json.dumps({"status": "rendered", "artifact_path": "rendered/index.html"}),
            encoding="utf-8",
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("ready_for_client_export", state["stage"])

    def test_quality_required_generation_session_blocks_on_fresh_blocking_gate(self) -> None:
        self._write_full_pipeline(include_preview=True)
        self._write_json(PREVIEW_MANIFEST_NAME, {"run_id": "r1", "pages": [{"page_id": "p1", "decision": "approved"}]})
        generation_tasks = self.run_dir / "generation_tasks"
        generation_tasks.mkdir()
        (generation_tasks / "index.json").write_text(json.dumps({"tasks": [{"id": "task-1"}]}), encoding="utf-8")
        self._write_json(
            "generation_session.json",
            {"run_id": "r1", "status": "quality_required", "quality_required_at": "2026-06-17T10:00:00+00:00"},
        )
        quality_dir = self.run_dir / "quality_reports"
        quality_dir.mkdir()
        (quality_dir / "draft_gate.json").write_text(
            json.dumps(
                {
                    "status": "rework_required",
                    "blocks_delivery": True,
                    "blocking_issue": "draft gate blocks delivery",
                    "created_at": "2026-06-17T10:01:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        state = resolve_run_state(self.run_dir, run_mode="fixture")
        self.assertEqual("needs_draft_gate", state["stage"])
        reasons = [item.get("reason", "") for item in state["blocked_actions"]]
        self.assertTrue(any("draft gate blocks delivery" in reason for reason in reasons))


if __name__ == "__main__":
    unittest.main()
