from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from generation.session import (
    GenerationSessionError,
    create_generation_session,
    generation_session_status,
    import_generation_results,
    run_generation,
)
from generation.task_builder import create_generation_tasks
from generation.handback import DECK_PRO_MAX_RESULT_SCHEMA_VERSION, RESULT_SCHEMA_VERSION
from runtime.events import read_events
from runtime.import_log import read_import_log
from runtime.run_state import create_run, read_json, write_json
from runtime.tool_registry import resolve_tool_command


class GenerationSessionBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dm-gensess-"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.runs_dir = self.temp_dir / "runs"
        self.workspace = self.temp_dir / "workspace"
        self.workspace.mkdir()

        self.run_dir = create_run(
            self.runs_dir,
            {
                "project_name": "Session Bridge",
                "run_id": "session-bridge-run",
                "workspace": str(self.workspace),
            },
            force=True,
        )

        create_generation_tasks(
            {
                "run_id": "session-bridge-run",
                "decisions": [
                    {
                        "beat_id": "beat-001",
                        "page_title": "适配页",
                        "source_decision": "adapt",
                        "selected_candidate": {"id": "slide-legacy"},
                    },
                    {
                        "beat_id": "beat-002",
                        "page_title": "生成页",
                        "source_decision": "generate",
                    },
                ],
            },
            self.run_dir,
        )

        self.task_index = read_json(self.run_dir / "generation_tasks" / "index.json")
        self.tasks = self.task_index["tasks"]

    def _tool_registry(self, *, command: str) -> None:
        payload = {
            "schema_version": "deck_tool_registry.v1",
            "tools": {
                "ppt-deck-pro-max": {
                    "type": "cli",
                    "command": command,
                    "args_template": [
                        "generate",
                        "--task-dir",
                        "{run_dir}/generation_tasks",
                        "--output-dir",
                        "{run_dir}/generation_results",
                    ],
                    "availability_check": [command, "--version"],
                }
            },
        }
        (self.workspace / "tool_registry.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _create_preview_manifest(self) -> None:
        write_json(
            self.run_dir / "preview_manifest.json",
            {
                "run_id": "session-bridge-run",
                "title": "Session Bridge",
                "status": "ready",
                "pages": [
                    {
                        "page_id": "beat-001",
                        "beat_id": "beat-001",
                        "order": 1,
                        "title": "适配页",
                        "narrative_role": "adapt",
                        "source_type": "placeholder",
                        "preview_path": "links/beat-001.svg",
                        "decision": "needs_review",
                        "review_status": "needs_review",
                    },
                    {
                        "page_id": "beat-002",
                        "beat_id": "beat-002",
                        "order": 2,
                        "title": "生成页",
                        "narrative_role": "generate",
                        "source_type": "placeholder",
                        "preview_path": "links/beat-002.svg",
                        "decision": "needs_review",
                        "review_status": "needs_review",
                    },
                ],
            },
        )
        links = self.run_dir / "links"
        links.mkdir(exist_ok=True)
        (links / "beat-001.svg").write_bytes(b"svg")
        (links / "beat-002.svg").write_bytes(b"svg")

    def _write_result(
        self,
        *,
        status: str = "completed",
        run_id: str = "session-bridge-run",
        session_id: str | None = None,
    ) -> Path:
        task_id = self.tasks[0]["task_id"]
        preview_dir = self.run_dir / "generated_assets" / "beat-001"
        preview_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = preview_dir / "slide.pptx"
        preview_path = preview_dir / "preview.png"
        artifact_path.write_bytes(b"ppt")
        preview_path.write_bytes(b"png")

        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "run_id": run_id,
            "tool": "ppt-deck-pro-max",
            "task_id": task_id,
            "beat_id": "beat-001",
            "status": status,
            "artifact_path": "generated_assets/beat-001/slide.pptx",
            "preview_path": "generated_assets/beat-001/preview.png",
            "errors": [],
        }
        if session_id is not None:
            result["session_id"] = session_id
        results_dir = self.run_dir / "generation_results"
        results_dir.mkdir(exist_ok=True)
        result_path = results_dir / f"{task_id}.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result_path

    def _write_deck_pro_max_result(
        self,
        *,
        session_id: str,
        status: str = "success",
        run_id: str = "session-bridge-run",
    ) -> Path:
        task_id = self.tasks[0]["task_id"]
        preview_dir = self.run_dir / "generated_assets" / "beat-001"
        preview_dir.mkdir(parents=True, exist_ok=True)
        (preview_dir / "slide.pptx").write_bytes(b"ppt")
        (preview_dir / "preview.png").write_bytes(b"png")
        result = {
            "schema_version": DECK_PRO_MAX_RESULT_SCHEMA_VERSION,
            "run_id": run_id,
            "session_id": session_id,
            "tool": "ppt-deck-pro-max",
            "task_id": task_id,
            "beat_id": "beat-001",
            "status": status,
            "outputs": {
                "artifact_path": "generated_assets/beat-001/slide.pptx",
                "preview_path": "generated_assets/beat-001/preview.png",
            },
            "errors": [],
        }
        result_path = self.run_dir / "generation_results" / f"{task_id}.deck-pro-max.json"
        result_path.parent.mkdir(exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result_path

    @patch("runtime.tool_registry._bundled_tool_entry", return_value=None)
    def test_tool_unavailable_marks_session_status_blocked(self, _bundled: unittest.mock.Mock) -> None:
        self._tool_registry(command="definitely_missing_tool")
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )

        status = generation_session_status(self.run_dir, tool="ppt-deck-pro-max")

        self.assertEqual("session-bridge-run", status["run_id"])
        self.assertEqual("blocked", status["status"])
        self.assertTrue(status["errors"])

    @patch("scripts.generation.session.subprocess.run")
    def test_dry_run_prepares_command_without_execution(self, mocked_run: unittest.mock.Mock) -> None:
        self._tool_registry(command="python3")
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
        )

        result = run_generation(self.run_dir, tool="ppt-deck-pro-max", dry_run=True)

        self.assertEqual("dispatched", result["status"])
        self.assertIsInstance(result["command"], list)
        self.assertEqual(sys.executable, result["command"][0])
        self.assertEqual("ppt_deck_pro_max.py", Path(result["command"][1]).name)
        self.assertIn("--session-id", result["command"])
        mocked_run.assert_not_called()

    @patch("scripts.generation.session.subprocess.run")
    def test_no_execute_records_handoff_command_and_no_launch(self, mocked_run: unittest.mock.Mock) -> None:
        self._tool_registry(command="python3")
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )

        result = run_generation(self.run_dir, tool="ppt-deck-pro-max", no_execute=True)

        self.assertEqual("dispatched", result["status"])
        mocked_run.assert_not_called()
        events = read_events(self.run_dir)
        self.assertTrue(
            any(
                event.get("event_type") == "tool_call"
                and event.get("step") == "generation.run.prepared"
                for event in events
            )
        )

    @patch("scripts.generation.session.subprocess.run")
    def test_result_import_rejects_run_id_mismatch(self, mocked_run: unittest.mock.Mock) -> None:
        self._tool_registry(command="python3")
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )
        result_path = self._write_result(run_id="other-run")

        with self.assertRaises(GenerationSessionError):
            import_generation_results(self.run_dir, result_path)

        mocked_run.assert_not_called()

    @patch("scripts.generation.session.subprocess.run")
    def test_result_import_refreshes_preview_and_marks_quality_required(self, mocked_run: unittest.mock.Mock) -> None:
        self._tool_registry(command=sys.executable)
        session = create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )
        self._create_preview_manifest()
        result_path = self._write_result(session_id=session["session_id"])

        imported = import_generation_results(self.run_dir, result_path)

        self.assertEqual("quality_required", imported["status"])
        self.assertTrue(imported["needs_quality_gate"])
        status = generation_session_status(self.run_dir, tool="ppt-deck-pro-max")
        self.assertEqual("quality_required", status["status"])
        self.assertTrue(status["needs_quality_gate"])

        preview = read_json(self.run_dir / "preview_manifest.json")
        first_page = next(
            (page for page in preview.get("pages", []) if page.get("beat_id") == "beat-001"),
            {},
        )
        self.assertEqual("generated_assets/beat-001/preview.png", first_page.get("preview_path"))

    def test_canonical_result_rejects_missing_session_id(self) -> None:
        self._tool_registry(command=sys.executable)
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )
        result_path = self._write_result()

        with self.assertRaisesRegex(GenerationSessionError, "session_id mismatch"):
            import_generation_results(self.run_dir, result_path)

        logs = read_import_log(self.run_dir)
        self.assertEqual("rejected", logs[-1]["status"])

    def test_canonical_result_rejects_session_mismatch(self) -> None:
        self._tool_registry(command=sys.executable)
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )
        result_path = self._write_result(session_id="other-session")

        with self.assertRaisesRegex(GenerationSessionError, "session_id mismatch"):
            import_generation_results(self.run_dir, result_path)

        logs = read_import_log(self.run_dir)
        self.assertEqual("rejected", logs[-1]["status"])

    def test_deck_pro_max_result_adapter_refreshes_preview_and_logs_import(self) -> None:
        self._tool_registry(command=sys.executable)
        session = create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )
        self._create_preview_manifest()
        result_path = self._write_deck_pro_max_result(session_id=session["session_id"])

        imported = import_generation_results(self.run_dir, result_path)

        self.assertEqual("quality_required", imported["status"])
        written = read_json(self.run_dir / "generation_results" / f"{self.tasks[0]['task_id']}.json")
        self.assertEqual(RESULT_SCHEMA_VERSION, written["schema_version"])
        self.assertEqual("deck_generation_result.v1", written["schema_version"])
        logs = read_import_log(self.run_dir)
        self.assertEqual("generation_result", logs[-1]["import_type"])
        self.assertEqual("imported", logs[-1]["status"])

    def test_deck_pro_max_result_rejects_session_mismatch(self) -> None:
        self._tool_registry(command=sys.executable)
        create_generation_session(
            self.run_dir,
            tool="ppt-deck-pro-max",
            workspace=str(self.workspace),
            force=True,
        )
        result_path = self._write_deck_pro_max_result(session_id="other-session")

        with self.assertRaises(GenerationSessionError):
            import_generation_results(self.run_dir, result_path)

        logs = read_import_log(self.run_dir)
        self.assertEqual("rejected", logs[-1]["status"])

    def test_bundled_tool_precedes_workspace_registry(self) -> None:
        self._tool_registry(command="workspace-tool")

        command, _, source = resolve_tool_command(
            "ppt-deck-pro-max",
            self.run_dir,
            workspace=self.workspace,
            cli_tool_command=None,
        )

        self.assertEqual(sys.executable, command[0])
        self.assertEqual("ppt_deck_pro_max.py", Path(command[1]).name)
        self.assertEqual("bundled capability", source)

    @patch("runtime.tool_registry._bundled_tool_entry", return_value=None)
    def test_tool_registry_precedence_workspace_over_global(self, _bundled: unittest.mock.Mock) -> None:
        global_home = self.temp_dir / "home"
        (global_home / ".deck-master").mkdir(parents=True)
        (global_home / ".deck-master" / "tools.json").write_text(
            json.dumps(
                {
                    "schema_version": "deck_tool_registry.v1",
                    "tools": {
                        "ppt-deck-pro-max": {
                            "type": "cli",
                            "command": "global-tool",
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self._tool_registry(command="workspace-tool")

        with patch.dict(os.environ, {"HOME": str(global_home)}):
            command, _, source = resolve_tool_command(
                "ppt-deck-pro-max",
                self.run_dir,
                workspace=self.workspace,
                cli_tool_command=None,
        )

        self.assertEqual("workspace-tool", command[0])
        self.assertEqual(str((self.workspace / "tool_registry.json").resolve()), source)

    def test_tool_command_cli_overrides_registry(self) -> None:
        self._tool_registry(command="workspace-tool")

        command, entry, source = resolve_tool_command(
            "ppt-deck-pro-max",
            self.run_dir,
            workspace=self.workspace,
            cli_tool_command="custom-tool --flag",
        )

        self.assertEqual(["custom-tool", "--flag", "generate", "--task-dir", f"{self.run_dir}/generation_tasks", "--output-dir", f"{self.run_dir}/generation_results"], command)
        self.assertEqual("cli_override", source)
        self.assertEqual("cli_override", entry["source"])
        self.assertIn("warning", entry)
