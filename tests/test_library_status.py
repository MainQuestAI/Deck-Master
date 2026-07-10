from __future__ import annotations

import json
import shutil
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
import runtime.library_status as library_status_module  # noqa: E402
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
                "contracts": {
                    "outputs": [
                        "deck_master_ppt_library_selection.v1",
                        "deck_master_ppt_library_selection.v2",
                    ],
                    "canonical_output": "deck_master_ppt_library_selection.v2",
                    "readiness_output": "deck_master_library_status.v2",
                },
                "state_policy": {
                    "canonical_artifact": "external/ppt_library/library_results.v2.json"
                },
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
    (contracts / "library-status.v2.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "schema_version": {"const": "deck_master_library_status.v2"}
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


def _runner(
    status_payload: dict[str, object],
    *,
    search_payload: dict[str, object] | None = None,
    search_returncode: int = 0,
    status_timeout: bool = False,
    search_timeout: bool = False,
) -> mock.Mock:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "status" in command:
            if status_timeout:
                raise subprocess.TimeoutExpired(command, 15)
            return _completed(status_payload)
        if "search" in command:
            if search_timeout:
                raise subprocess.TimeoutExpired(command, 15)
            return subprocess.CompletedProcess(
                args=command,
                returncode=search_returncode,
                stdout=json.dumps(search_payload if search_payload is not None else {"results": []}),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    return mock.Mock(side_effect=run)


class LibraryStatusV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        library_status_module._clear_library_status_cache()

    def test_all_required_dimensions_ready_aggregates_to_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = _runner(
                {
                    "semantic_search_ready": True,
                    "role_selection_ready": True,
                    "preview_ready": True,
                    "business_ranking_ready": "ready",
                    "data_hygiene_status": "ready",
                },
                search_payload={"results": [{"slide_id": "probe-result"}]},
            )
            result = inspect_library_status(
                repo_root=_contract_root(Path(tmp)),
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(Path(tmp)),
                snapshotter=lambda source, target: True,
                runner=runner,
            )

        self.assertEqual("ready", result["status"])
        self.assertEqual([], result["blocking_summary"])
        self.assertEqual([], result["warnings"])

    def test_zero_annotation_library_is_degraded_ready_with_semantic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            runner = _runner(
                {
                    "status": "ready",
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
                },
                search_payload={"results": [{"slide_id": "probe-result"}]},
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
            self.assertEqual(2, runner.call_count)
            status_command = runner.call_args_list[0].args[0]
            search_command = runner.call_args_list[1].args[0]
            self.assertEqual(["status", "--output", "json"], status_command[3:])
            self.assertEqual("search", search_command[3])
            self.assertEqual("business solution architecture", search_command[4])
            self.assertEqual("--top-k", search_command[5])
            self.assertEqual("1", search_command[6])
            self.assertEqual("--threshold", search_command[7])
            self.assertEqual("0", search_command[8])
            self.assertEqual(["--output", "json"], search_command[9:])

    def test_slide_count_without_nonempty_search_result_is_not_semantic_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            result = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(root),
                snapshotter=lambda source, target: True,
                runner=_runner({"stats": {"slide_count": 1200}}),
            )

        self.assertFalse(result["semantic_search_ready"])
        self.assertEqual("blocked", result["status"])

    def test_empty_or_failed_search_probe_is_not_semantic_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for label, runner in (
                ("empty", _runner({}, search_payload={"results": []})),
                ("failed", _runner({}, search_returncode=2)),
                ("timeout", _runner({}, search_timeout=True)),
            ):
                with self.subTest(label=label):
                    root = _contract_root(Path(tmp) / label)
                    result = inspect_library_status(
                        repo_root=root,
                        which=lambda _: "/opt/tools/ppt-lib",
                        library_home=_library_home(root),
                        snapshotter=lambda source, target: True,
                        runner=runner,
                    )
                    self.assertFalse(result["semantic_search_ready"])
                    self.assertEqual("blocked", result["status"])

    def test_status_timeout_is_runtime_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            result = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(root),
                snapshotter=lambda source, target: True,
                runner=_runner({}, status_timeout=True),
            )

        self.assertFalse(result["runtime_ready"])
        self.assertIn("PPT_LIBRARY_STATUS_FAILED", result["blocking_summary"])

    def test_explicit_status_semantic_false_overrides_successful_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            result = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(root),
                snapshotter=lambda source, target: True,
                runner=_runner(
                    {"semantic_search_ready": False},
                    search_payload={"results": [{"slide_id": "probe-result"}]},
                ),
            )

        self.assertFalse(result["semantic_search_ready"])

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

    def test_reflink_failure_falls_back_to_regular_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _library_home(root)
            target = root / "snapshot"
            target.mkdir()
            calls: list[list[str]] = []

            def copy_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                calls.append(command)
                if len(calls) % 2 == 1:
                    return subprocess.CompletedProcess(command, 1, "", "reflink unavailable")
                shutil.copyfile(command[-2], command[-1])
                return subprocess.CompletedProcess(command, 0, "", "")

            copied = library_status_module._clone_library_state(
                source,
                target,
                copy_runner=copy_runner,
            )

            self.assertTrue(copied)
            self.assertEqual(source.joinpath("index.db").read_bytes(), target.joinpath("index.db").read_bytes())
            self.assertEqual(4, len(calls))
            self.assertEqual("cp", calls[1][0])
            self.assertEqual(3, len(calls[1]))

    def test_regular_copy_timeout_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = _library_home(root)
            target = root / "snapshot"
            target.mkdir()
            calls = 0

            def copy_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return subprocess.CompletedProcess(command, 1, "", "reflink unavailable")
                raise subprocess.TimeoutExpired(command, 15)

            copied = library_status_module._clone_library_state(
                source,
                target,
                copy_runner=copy_runner,
            )

            self.assertFalse(copied)
            self.assertEqual(2, calls)

    def test_v1_only_capability_is_contract_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            capability_path = root / "product_capabilities" / "ppt-library" / "capability.json"
            capability = json.loads(capability_path.read_text(encoding="utf-8"))
            capability["contracts"]["outputs"] = ["deck_master_ppt_library_selection.v1"]
            capability_path.write_text(json.dumps(capability), encoding="utf-8")

            result = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=_library_home(root),
                snapshotter=lambda source, target: True,
                runner=_runner({}, search_payload={"results": [{"slide_id": "probe-result"}]}),
            )

        self.assertFalse(result["contract_ready"])
        self.assertIn("PPT_LIBRARY_CONTRACT_MISSING", result["blocking_summary"])

    def test_cache_hit_and_source_change_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            library_home = _library_home(root)
            snapshotter = mock.Mock(return_value=True)
            runner = _runner({}, search_payload={"results": [{"slide_id": "probe-result"}]})

            first = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=library_home,
                snapshotter=snapshotter,
                runner=runner,
                cache_ttl_seconds=30,
            )
            second = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=library_home,
                snapshotter=snapshotter,
                runner=runner,
                cache_ttl_seconds=30,
            )

            self.assertEqual(first, second)
            self.assertEqual(2, runner.call_count)
            self.assertEqual(1, snapshotter.call_count)

            (library_home / "index.db").write_bytes(b"database fixture changed")
            third = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=library_home,
                snapshotter=snapshotter,
                runner=runner,
                cache_ttl_seconds=30,
            )

            self.assertEqual(first, third)
            self.assertEqual(4, runner.call_count)
            self.assertEqual(2, snapshotter.call_count)

    def test_contract_fingerprint_change_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _contract_root(Path(tmp))
            library_home = _library_home(root)
            snapshotter = mock.Mock(return_value=True)
            runner = _runner({}, search_payload={"results": [{"slide_id": "probe-result"}]})

            first = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=library_home,
                snapshotter=snapshotter,
                runner=runner,
                cache_ttl_seconds=30,
            )
            capability_path = root / "product_capabilities" / "ppt-library" / "capability.json"
            capability = json.loads(capability_path.read_text(encoding="utf-8"))
            capability["contracts"]["readiness_output"] = "legacy_status"
            capability_path.write_text(json.dumps(capability), encoding="utf-8")
            second = inspect_library_status(
                repo_root=root,
                which=lambda _: "/opt/tools/ppt-lib",
                library_home=library_home,
                snapshotter=snapshotter,
                runner=runner,
                cache_ttl_seconds=30,
            )

            self.assertTrue(first["contract_ready"])
            self.assertFalse(second["contract_ready"])
            self.assertEqual(4, runner.call_count)
            self.assertEqual(2, snapshotter.call_count)

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
                runner=_runner(
                    {
                        "role_selection_ready": False,
                        "preview_ready": False,
                        "business_ranking_ready": "cold_start",
                        "data_hygiene_status": "degraded",
                    },
                    search_payload={"results": [{"slide_id": "probe-result"}]},
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
