"""SC-1 PR-02 tests: managed capability lock, backend hosting, library hosting.

Acceptance mapping (docs/specs/sc1-solution-core-independence/acceptance/cases.json):
- A-01: managed component lock pins sources/versions/hashes; no floating latest.
- A-02: same lock reinstalls identically (idempotent managed install).
- A-04: runtime_ready cannot be faked via environment variable.
- A-05: managed library CLI resolves ahead of PATH.
- A-06: PATH fallback keeps working; missing CLI reports honestly.
- A-11: PPT-Deck-Pro-Max generation bridge is retired (env var ignored).
- P-02: task readiness exposes library_none_sourcing / standard_build
  separation (missing ImageGen does not block standard build path).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from runtime.builder_backend import (  # noqa: E402
    backend_render_runtime_ready,
    backend_render_runtime_status,
    binding_smoke_evidence_ready,
    generation_bridge_status,
)
from skills import capability_lock as cl  # noqa: E402


class CapabilityLockTests(unittest.TestCase):
    """A-01 / A-02: pinned, verifiable, reinstallable component lock."""

    def _build_release_tree(self, release_root: Path) -> None:
        from skills.installer import build_release_tree

        result = build_release_tree(release_root, force=True)
        self.assertEqual("built", result["status"])

    def test_capability_lock_pins_bundled_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_root = Path(tmp) / "release"
            self._build_release_tree(release_root)
            lock = json.loads((release_root / "deck_capability_lock.json").read_text(encoding="utf-8"))
            components = lock.get("components")
            self.assertIsInstance(components, list)
            self.assertTrue(components, "bundled ppt-* capability components must be pinned")
            names = {item["name"] for item in components}
            self.assertIn("ppt-master", names)
            for item in components:
                self.assertRegex(item["content_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(cl.DEFAULT_LICENSE, item["license"])
            policy = lock.get("pinning_policy", {})
            self.assertFalse(policy.get("floating_versions_allowed", True))

    def test_capability_lock_verification_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            release_root = Path(tmp) / "release"
            self._build_release_tree(release_root)
            verified = cl.verify_capability_lock(release_root)
            self.assertTrue(verified["verified"])
            self.assertEqual([], verified["failures"])

            target = release_root / "capabilities" / "ppt-master"
            (target / "drift.txt").write_text("tampered", encoding="utf-8")
            drifted = cl.verify_capability_lock(release_root)
            self.assertFalse(drifted["verified"])
            self.assertTrue(any("ppt-master" in failure for failure in drifted["failures"]))

    def test_managed_component_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)):
            source = Path(outer) / "src"
            (source / "scripts").mkdir(parents=True)
            (source / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
            first = cl.install_managed_component("ppt-master", source)
            second = cl.install_managed_component("ppt-master", source)
            self.assertEqual(first["content_sha256"], second["content_sha256"])
            self.assertEqual(first["installed_path"], second["installed_path"])
            current = cl.managed_component_current("ppt-master")
            self.assertIsNotNone(current)
            self.assertTrue((current / "managed_component_manifest.json").exists())

    def test_runtime_component_records_reflect_missing_install(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)):
            records = cl.runtime_component_records()
            by_name = {item["name"]: item for item in records}
            self.assertFalse(by_name["ppt-master"]["installed"])
            self.assertFalse(by_name["ppt-library"]["installed"])


class ManagedBackendRuntimeTests(unittest.TestCase):
    """A-04: runtime readiness only from real smoke evidence."""

    def _binding_file(self, outer: Path) -> Path:
        return Path(outer) / ".deck-master" / "backend_bindings.json"

    def _write_binding(self, outer: Path, *, verified: bool, smoke_passed: bool) -> None:
        payload = {
            "schema_version": "deck_backend_bindings.v1",
            "bindings": [
                {
                    "name": "ppt-master",
                    "dependency_kind": "external_repo",
                    "repo_path": str(outer / "backend"),
                    "skill_path": str(outer / "backend" / "skills" / "ppt-master"),
                    "verified": verified,
                    "verified_at": "2026-09-07T00:00:00+00:00",
                    "smoke_evidence": (
                        {
                            "passed": smoke_passed,
                            "recorded_at": "2026-09-07T00:00:00+00:00",
                            "smoke_command": "scripts/smoke.py",
                            "backend_content_sha256": "a" * 64,
                            "render_result_sha256": "b" * 64,
                        }
                        if smoke_passed
                        else {}
                    ),
                }
            ],
        }
        path = self._binding_file(outer)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_env_true_cannot_fake_runtime_ready(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)), mock.patch.dict(
            os.environ, {"DECK_MASTER_PPT_MASTER_RUNTIME_WIRED": "1"}, clear=False
        ):
            self._write_binding(Path(outer), verified=True, smoke_passed=True)
            status = backend_render_runtime_status()
            self.assertFalse(status["runtime_ready"])
            self.assertEqual("env_override", status["runtime_ready_source"])

    def test_smoke_evidence_drives_runtime_ready(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)), mock.patch.dict(
            os.environ, {}, clear=True
        ):
            self._write_binding(Path(outer), verified=True, smoke_passed=True)
            self.assertTrue(binding_smoke_evidence_ready())
            self.assertTrue(backend_render_runtime_ready())
            status = backend_render_runtime_status()
            self.assertEqual("external_backend_smoke", status["runtime_ready_source"])
            self.assertTrue(status["runtime_ready_trusted_for_rc"])

    def test_failed_or_unverified_smoke_keeps_runtime_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)), mock.patch.dict(
            os.environ, {}, clear=True
        ):
            self._write_binding(Path(outer), verified=False, smoke_passed=False)
            self.assertFalse(binding_smoke_evidence_ready())
            status = backend_render_runtime_status()
            self.assertEqual("smoke_evidence_missing", status["runtime_ready_source"])
            self.assertFalse(backend_render_runtime_ready())


class GenerationBridgeRetirementTests(unittest.TestCase):
    """A-11: the pinned third-party branch bridge is retired."""

    def test_bridge_status_reports_retired_without_env(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            status = generation_bridge_status()
        self.assertEqual("retired", status["binding_status"])
        self.assertFalse(status["verified"])

    def test_bridge_env_config_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {"DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE": str(tmp)},
            clear=False,
        ):
            status = generation_bridge_status()
        self.assertEqual("retired", status["binding_status"])
        self.assertEqual("", status["repo_path"])


class ManagedLibraryCommandTests(unittest.TestCase):
    """A-05 / A-06: managed-first resolution with honest PATH fallback."""

    def test_managed_root_wins_over_path(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)):
            managed_bin = Path(outer) / ".deck-master" / "backends" / "ppt-library" / "current" / "bin"
            managed_bin.mkdir(parents=True)
            executable = managed_bin / "ppt-lib"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)
            command, source = _resolve()
            self.assertEqual("managed", source)
            self.assertEqual(str(executable), command)

    def test_path_fallback_and_missing_reported_honestly(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)), mock.patch(
            "tools.ppt_library_client.shutil.which", return_value=None
        ):
            command, source = _resolve()
            self.assertEqual("ppt-lib", command)
            self.assertEqual("missing", source)


def _resolve():
    from tools.ppt_library_client import resolve_library_command

    return resolve_library_command()


class TaskReadinessSeparationTests(unittest.TestCase):
    """P-02: none-mode sourcing and standard build have their own entries."""

    def test_task_readiness_contains_none_and_standard_entries(self) -> None:
        with tempfile.TemporaryDirectory() as outer, mock.patch.object(Path, "home", return_value=Path(outer)):
            from skills.installer import inspect_suite_status

            projection = inspect_suite_status(targets=["codex"], agent_skill_dir=str(Path(outer) / "skills"))
            readiness = projection.get("task_readiness") or {}
            self.assertIn("library_none_sourcing", readiness)
            self.assertIn("standard_build", readiness)
            self.assertIn("imagegen_host", readiness)


class LibraryNoneSourcingTests(unittest.TestCase):
    """A-07: library_mode=none produces a real generate decision for every page."""

    def test_none_library_results_decide_generate_with_full_coverage(self) -> None:
        from sourcing.plan import build_sourcing_plan_v2

        page_tasks = {
            "schema_version": "deck_page_tasks.v1",
            "run_id": "run-none",
            "tasks": [
                {
                    "task_id": "task-1",
                    "page_id": "P001",
                    "order": 1,
                    "title": "现状与问题",
                    "role": "context",
                    "content_goal": "说明现状",
                    "generation_brief": "写清楚现状与问题",
                    "claim_ids": [],
                    "evidence_need": [],
                },
                {
                    "task_id": "task-2",
                    "page_id": "P002",
                    "order": 2,
                    "title": "解决方案",
                    "role": "solution",
                    "content_goal": "说明方案机制",
                    "generation_brief": "写清楚方案机制",
                    "claim_ids": [],
                    "evidence_need": [],
                },
            ],
        }
        plan = build_sourcing_plan_v2(run_id="run-none", page_tasks=page_tasks, library_results=None)
        self.assertEqual([], plan["warnings"])
        decisions = {page["page_id"]: page for page in plan["pages"]}
        self.assertEqual({"P001", "P002"}, set(decisions))
        for page in decisions.values():
            self.assertEqual("generate", page["decision"])
            self.assertEqual("NO_CANDIDATE_GENERATE", page["reason"])
            self.assertEqual([], page["selected_sources"], "none mode must not fabricate fixture candidates")
        self.assertEqual(2, plan["coverage"]["total_pages"])
        self.assertEqual(0, plan["coverage"]["blocked_pages"])
        self.assertTrue(plan["coverage"]["complete"])


if __name__ == "__main__":
    unittest.main()
