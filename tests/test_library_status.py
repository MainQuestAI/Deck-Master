from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import deck_master  # noqa: E402
from runtime.library_status import inspect_library_status  # noqa: E402
from runtime.setup_status import setup_status  # noqa: E402
from skills.installer import inspect_suite_status  # noqa: E402


EXPECTED_KEYS = {
    "schema_version",
    "status",
    "runtime_ready",
    "contract_ready",
    "semantic_search_ready",
    "role_selection_ready",
    "fallback_ready",
    "preview_ready",
    "business_ranking_ready",
    "data_hygiene_status",
    "blocking_summary",
    "warnings",
}


def _contract_root(root: Path) -> Path:
    capability = root / "product_capabilities" / "ppt-library" / "capability.json"
    capability.parent.mkdir(parents=True)
    capability.write_text(
        json.dumps(
            {
                "schema_version": "deck_master_capability_package.v1",
                "name": "ppt-library",
                "runtime": {"operations": ["status", "search", "select-slides"]},
            }
        ),
        encoding="utf-8",
    )
    contracts = root / "docs" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "ppt-library-selection.v2.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "schema_version": {"const": "deck_master_ppt_library_selection.v2"}
                },
            }
        ),
        encoding="utf-8",
    )
    (contracts / "ppt-library-bridge-plan.v1.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "schema_version": {"const": "deck_master_ppt_library_bridge_plan.v1"}
                },
            }
        ),
        encoding="utf-8",
    )
    bridge = root / "scripts" / "tools" / "ppt_library_client.py"
    bridge.parent.mkdir(parents=True)
    bridge.write_text("# bridge fixture\n", encoding="utf-8")
    return root


def _completed(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["ppt-lib", "status", "--output", "json"],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )


def _library_home(root: Path) -> Path:
    home = root / "library-home"
    home.mkdir()
    (home / "index.db").write_bytes(b"database fixture")
    (home / "config.yml").write_text("schema_version: '1.0'\n", encoding="utf-8")
    return home


class LibraryStatusV2Tests(unittest.TestCase):
    def test_all_required_dimensions_ready_aggregates_to_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_library_status(
                repo_root=_contract_root(Path(tmp)),
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(Path(tmp)),
                snapshotter=lambda source, target: True,
                runner=lambda *args, **kwargs: _completed(
                    {
                        "semantic_search_ready": True,
                        "role_selection_ready": True,
                        "preview_ready": True,
                        "business_ranking_ready": "ready",
                        "data_hygiene_status": "ready",
                    }
                ),
            )

        self.assertEqual("ready", result["status"])
        self.assertEqual([], result["blocking_summary"])
        self.assertEqual([], result["warnings"])

    def test_zero_annotation_library_is_degraded_ready_with_semantic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            runner = mock.Mock(
                return_value=_completed(
                    {
                        "status": "ready",
                        "capabilities": {"semantic_search_ready": True},
                        "counts": {
                            "presentations_count": 84,
                            "slides_count": 1200,
                            "annotated_count": 0,
                            "screenshots_count": 24996,
                            "deals_count": 0,
                            "slide_usage_count": 0,
                            "failed_jobs_count": 33,
                            "orphan_presentations_count": 34,
                        },
                    }
                )
            )

            result = inspect_library_status(
                repo_root=root,
                command="ppt-lib",
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(root),
                snapshotter=lambda source, target: True,
                runner=runner,
            )

            self.assertEqual(EXPECTED_KEYS, set(result))
            self.assertEqual("deck_master_library_status.v2", result["schema_version"])
            self.assertEqual("degraded_ready", result["status"])
            self.assertTrue(result["runtime_ready"])
            self.assertTrue(result["contract_ready"])
            self.assertTrue(result["semantic_search_ready"])
            self.assertFalse(result["role_selection_ready"])
            self.assertTrue(result["fallback_ready"])
            self.assertFalse(result["preview_ready"])
            self.assertEqual("cold_start", result["business_ranking_ready"])
            self.assertEqual("degraded", result["data_hygiene_status"])
            self.assertEqual([], result["blocking_summary"])
            runner.assert_called_once()
            command = runner.call_args.args[0]
            self.assertEqual("ppt-lib", command[0])
            self.assertEqual("--home-dir", command[1])
            self.assertEqual(["status", "--output", "json"], command[3:])
            self.assertEqual(
                {
                    "capture_output": True,
                    "text": True,
                    "check": False,
                    "timeout": 15,
                },
                runner.call_args.kwargs,
            )

    def test_missing_cli_blocks_without_invoking_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = mock.Mock()
            result = inspect_library_status(
                repo_root=_contract_root(Path(tmp)),
                command="ppt-lib",
                which=lambda _: None,
                runner=runner,
            )

            self.assertEqual("blocked", result["status"])
            self.assertFalse(result["runtime_ready"])
            self.assertFalse(result["semantic_search_ready"])
            self.assertFalse(result["fallback_ready"])
            self.assertIn("PPT_LIBRARY_CLI_MISSING", result["blocking_summary"])
            runner.assert_not_called()

    def test_missing_library_state_blocks_without_starting_cli_or_creating_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            runner = mock.Mock()
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))

            result = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=root / "missing-library-home",
                runner=runner,
            )

            after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            self.assertEqual("blocked", result["status"])
            self.assertIn("PPT_LIBRARY_STATE_MISSING", result["blocking_summary"])
            self.assertEqual(before, after)
            runner.assert_not_called()

    def test_snapshot_failure_blocks_without_running_status_on_source_library(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            runner = mock.Mock()

            result = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(root),
                snapshotter=lambda source, target: False,
                runner=runner,
            )

            self.assertEqual("blocked", result["status"])
            self.assertIn(
                "PPT_LIBRARY_READ_ONLY_SNAPSHOT_UNAVAILABLE",
                result["blocking_summary"],
            )
            runner.assert_not_called()

    def test_inspection_does_not_mutate_checked_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            library_home = _library_home(root)
            before = {
                path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
                for path in root.rglob("*")
                if path.is_file()
            }

            inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=library_home,
                snapshotter=lambda source, target: True,
                runner=lambda *args, **kwargs: _completed(
                    {
                        "semantic_search_ready": True,
                        "role_selection_ready": False,
                        "preview_ready": False,
                        "business_ranking_ready": "cold_start",
                        "data_hygiene_status": "degraded",
                    }
                ),
            )

            after = {
                path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_library_status_schema_matches_exact_public_dimensions(self) -> None:
        schema = json.loads(
            (ROOT / "docs" / "contracts" / "library-status.v2.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(EXPECTED_KEYS, set(schema["required"]))
        self.assertEqual(
            "deck_master_library_status.v2",
            schema["properties"]["schema_version"]["const"],
        )


class LibraryStatusProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = {
            "schema_version": "deck_master_library_status.v2",
            "status": "degraded_ready",
            "runtime_ready": True,
            "contract_ready": True,
            "semantic_search_ready": True,
            "role_selection_ready": False,
            "fallback_ready": True,
            "preview_ready": False,
            "business_ranking_ready": "cold_start",
            "data_hygiene_status": "degraded",
            "blocking_summary": [],
            "warnings": ["ROLE_SELECTION_UNAVAILABLE"],
        }

    def test_cli_returns_canonical_status_without_workspace_path(self) -> None:
        with mock.patch("deck_master.inspect_library_status", return_value=self.summary) as inspect:
            result = deck_master.command_library_status(
                SimpleNamespace(workspace="/Users/private/customer-workspace", output="json")
            )

        self.assertEqual(self.summary, result)
        self.assertNotIn("/Users/", json.dumps(result))
        inspect.assert_called_once_with()

    def test_suite_embeds_canonical_library_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "skills.installer.inspect_library_status", return_value=self.summary
        ) as inspect:
            result = inspect_suite_status(
                targets=["codex"],
                agent_skill_dir=str(Path(tmp) / "skills"),
            )

        self.assertEqual(self.summary, result["library_status"])
        inspect.assert_called_once_with()

    def test_setup_passes_through_suite_library_summary(self) -> None:
        suite = {
            "status": "degraded_ready",
            "full_suite_ready": False,
            "production_backend_ready": False,
            "client_delivery_ready": False,
            "external_dependency_status": [],
            "capabilities": {},
            "task_readiness": {},
            "blocking_summary": [],
            "library_status": self.summary,
        }
        with mock.patch("runtime.setup_status._read_config", return_value=None), mock.patch(
            "runtime.setup_status.inspect_suite_status", return_value=suite
        ) as inspect:
            result = setup_status(run_mode="dev", include_suite=True)

        self.assertEqual(self.summary, result["library_status"])
        self.assertEqual(self.summary, result["suite"]["library_status"])
        inspect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
