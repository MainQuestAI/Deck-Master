from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tools.ppt_library_client import (  # noqa: E402
    PPTLibraryClientError,
    build_bridge_plan,
    import_library_selection,
    normalize_candidate,
    run_library_selection,
    validate_library_selection,
)
from runtime.run_state import create_run, read_json  # noqa: E402


def _plan(*beats: dict[str, object]) -> dict[str, object]:
    return {"run_id": "bridge-run", "beats": list(beats)}


def _beat(beat_id: str, role: str, order: int, **extra: object) -> dict[str, object]:
    return {
        "beat_id": beat_id,
        "section_id": "section-01",
        "order": order,
        "role": role,
        "page_title": f"Title {order}",
        "content_goal": f"Goal {order}",
        **extra,
    }


def _valid_v2_payload() -> dict[str, object]:
    return {
        "schema_version": "deck_master_ppt_library_selection.v2",
        "run_id": "bridge-run",
        "status": "library_ready",
        "source": "ppt_library",
        "preview_degraded": False,
        "warnings": [],
        "by_beat": {},
        "selections": [
            {
                "beat_id": "beat-001",
                "page_task_id": "page-001",
                "query_trace_id": hashlib.sha256(b"trace").hexdigest(),
                "role_original": "opener",
                "role_strategy": "passthrough",
                "role_mapped": "opener",
                "retrieval_method": "role_selection",
                "fallback_reason": "",
                "preview_status": "ready",
                "preview_degraded": False,
                "candidates": [
                    {
                        "candidate_id": "candidate-001",
                        "slide_id": "slide-001",
                        "asset_key": "canonical:slide-001",
                        "title": "Title",
                        "text_summary": "Summary",
                        "page_number": 1,
                        "score": 0.8,
                        "confidence": 0.8,
                        "source_asset_id": hashlib.sha256(b"source").hexdigest(),
                        "source_display_name": "Safe Deck.pptx",
                        "screenshot_ref": "preview_assets/ppt_library/preview.png",
                        "candidate_origin": "ppt_library",
                        "reuse_policy": "reuse_or_adapt",
                    }
                ],
            }
        ],
    }


class PPTLibraryBridgeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_bridge_plan_preserves_narrative_and_stable_identities(self) -> None:
        narrative = _plan(
            _beat("beat-001", "solution_detail", 1, reuse_query="  reusable   solution "),
            _beat("beat-002", "executive_summary", 2),
            _beat("beat-003", "section_handoff", 3),
        )
        before = copy.deepcopy(narrative)
        page_tasks = {
            "tasks": [
                {"beat_id": "beat-001", "page_task_id": "page-task-001"},
                {"beat_id": "beat-002", "task_id": "legacy-task-002"},
            ]
        }

        first = build_bridge_plan(narrative, page_tasks, run_id="bridge-run", run_mode="dev")
        second = build_bridge_plan(narrative, page_tasks, run_id="bridge-run", run_mode="dev")

        self.assertEqual(before, narrative)
        self.assertEqual(first, second)
        requests = first["requests"]
        self.assertEqual(["beat-001", "beat-002", "beat-003"], [item["beat_id"] for item in requests])
        self.assertEqual("page-task-001", requests[0]["page_task_id"])
        self.assertEqual("legacy-task-002", requests[1]["page_task_id"])
        self.assertEqual("beat-003", requests[2]["page_task_id"])
        self.assertEqual(("mapped", "solution"), (requests[0]["role_strategy"], requests[0]["role_mapped"]))
        self.assertEqual(("semantic_only", None), (requests[1]["role_strategy"], requests[1]["role_mapped"]))
        self.assertEqual("adapt_only", requests[2]["reuse_policy"])
        self.assertIn("Title 2", requests[2]["query"])
        self.assertIn("LEGACY_PAGE_TASK_ID_DERIVED", first["warnings"])

        changed = copy.deepcopy(narrative)
        changed["beats"][0]["reuse_query"] = "changed"
        changed_plan = build_bridge_plan(changed, page_tasks, run_id="bridge-run", run_mode="dev")
        self.assertNotEqual(requests[0]["query_trace_id"], changed_plan["requests"][0]["query_trace_id"])

    def test_unknown_role_semantic_fallback_in_dev_and_blocks_strict_modes(self) -> None:
        narrative = _plan(_beat("beat-001", "new_role", 1))

        dev = build_bridge_plan(narrative, {"tasks": []}, run_id="bridge-run", run_mode="dev")
        self.assertEqual("semantic_only", dev["requests"][0]["role_strategy"])
        self.assertEqual("UNKNOWN_ROLE_SEMANTIC_FALLBACK", dev["requests"][0]["fallback_reason"])

        for run_mode in ("production", "benchmark"):
            with self.subTest(run_mode=run_mode), self.assertRaises(PPTLibraryClientError):
                build_bridge_plan(narrative, {"tasks": []}, run_id="bridge-run", run_mode=run_mode)

    def test_all_current_narrative_roles_have_explicit_strategies(self) -> None:
        roles = [
            "opener",
            "executive_summary",
            "business_context",
            "problem",
            "solution_overview",
            "capability_matrix",
            "architecture",
            "capability_detail",
            "process_flow",
            "section_handoff",
            "solution_detail",
            "cta",
        ]
        narrative = _plan(*[_beat(f"beat-{index:03d}", role, index) for index, role in enumerate(roles, start=1)])
        page_tasks = {
            "tasks": [
                {"beat_id": f"beat-{index:03d}", "page_task_id": f"page-{index:03d}"}
                for index in range(1, len(roles) + 1)
            ]
        }

        plan = build_bridge_plan(narrative, page_tasks, run_id="bridge-run", run_mode="production")

        self.assertEqual(len(roles), len(plan["requests"]))
        self.assertNotIn("UNKNOWN_ROLE_SEMANTIC_FALLBACK", json.dumps(plan))

    def test_candidate_sanitizes_paths_copies_preview_and_dedupes_identity(self) -> None:
        screenshot = self.temp_dir / "private" / "shot.png"
        screenshot.parent.mkdir()
        screenshot.write_bytes(b"png")
        source = "/Users/acme/private/Customer Secret Deck.pptx"
        candidate, preview_status = normalize_candidate(
            {
                "canonical_slide_id": "canonical-001",
                "slide_id": "slide-001",
                "title": "A",
                "score": 1.7,
                "source_file": source,
                "screenshot_path": str(screenshot),
                "page_number": 4,
            },
            run_dir=self.temp_dir,
            reuse_policy="reuse_or_adapt",
            index=1,
        )

        self.assertEqual("canonical:canonical-001", candidate["asset_key"])
        self.assertEqual(1.0, candidate["confidence"])
        self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(), candidate["source_asset_id"])
        self.assertEqual("Customer Secret Deck.pptx", candidate["source_display_name"])
        self.assertEqual("ready", preview_status)
        self.assertFalse(Path(candidate["screenshot_ref"]).is_absolute())
        self.assertTrue((self.temp_dir / candidate["screenshot_ref"]).is_file())
        serialized = json.dumps(candidate)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("/private/", serialized)
        self.assertNotIn("source_file", candidate)
        self.assertNotIn("screenshot_path", candidate)

    def test_candidate_uses_safe_display_fallback_and_source_page_identity(self) -> None:
        source = "/private/客户机密方案.pptx"
        candidate, preview_status = normalize_candidate(
            {"slide_id": None, "source_file": source, "page_number": 7, "screenshot_path": "/missing.png"},
            run_dir=self.temp_dir,
            reuse_policy="adapt",
            index=1,
        )

        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        self.assertEqual(f"source-page:{source_hash}:7", candidate["asset_key"])
        self.assertEqual(f"PPT Library asset {source_hash[:8]}", candidate["source_display_name"])
        self.assertEqual("invalid", preview_status)
        self.assertEqual("", candidate["screenshot_ref"])

    def test_candidate_without_any_stable_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(PPTLibraryClientError, "CANDIDATE_IDENTITY_MISSING"):
            normalize_candidate({}, run_dir=self.temp_dir, reuse_policy="adapt", index=1)

    def test_v2_validation_requires_full_selection_contract(self) -> None:
        invalid = {
            "schema_version": "deck_master_ppt_library_selection.v2",
            "run_id": "bridge-run",
            "status": "library_ready",
            "source": "ppt_library",
            "preview_degraded": False,
            "warnings": [],
            "by_beat": {},
            "selections": [{"beat_id": "beat-001", "candidates": []}],
        }

        result = validate_library_selection(invalid)

        self.assertFalse(result["valid"])
        self.assertTrue(any("page_task_id" in error for error in result["errors"]))
        self.assertTrue(any("query_trace_id" in error for error in result["errors"]))

    def test_v2_validation_rejects_enum_format_path_and_shape_drift(self) -> None:
        mutations = [
            ("status", lambda payload: payload.__setitem__("status", "ready")),
            ("source", lambda payload: payload.__setitem__("source", "external")),
            ("retrieval_method", lambda payload: payload["selections"][0].__setitem__("retrieval_method", "search")),
            ("role_strategy", lambda payload: payload["selections"][0].__setitem__("role_strategy", "guessed")),
            ("role_mapped", lambda payload: payload["selections"][0].__setitem__("role_mapped", "executive_summary")),
            ("preview_status", lambda payload: payload["selections"][0].__setitem__("preview_status", "unknown")),
            ("candidate_origin", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("candidate_origin", "external")),
            ("reuse_policy", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("reuse_policy", "copy")),
            ("query_trace_id", lambda payload: payload["selections"][0].__setitem__("query_trace_id", "trace")),
            ("source_asset_id", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("source_asset_id", "source")),
            ("absolute screenshot_ref", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("screenshot_ref", "/Users/reviewer/preview.png")),
            ("non-run screenshot_ref", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("screenshot_ref", "screens/preview.png")),
            ("escaping screenshot_ref", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("screenshot_ref", "preview_assets/../private.png")),
            ("top required field", lambda payload: payload.pop("status")),
            ("selection required field", lambda payload: payload["selections"][0].pop("preview_status")),
            ("top additional field", lambda payload: payload.__setitem__("unexpected", True)),
            ("selection additional field", lambda payload: payload["selections"][0].__setitem__("unexpected", True)),
            ("candidate additional field", lambda payload: payload["selections"][0]["candidates"][0].__setitem__("unexpected", True)),
            ("candidate required field", lambda payload: payload["selections"][0]["candidates"][0].pop("title")),
        ]

        for label, mutate in mutations:
            with self.subTest(label=label):
                payload = _valid_v2_payload()
                mutate(payload)
                result = validate_library_selection(payload)
                self.assertFalse(result["valid"], result)

    def test_real_candidates_hash_three_malicious_identity_values(self) -> None:
        attacks = [
            {"canonical_slide_id": "/Users/reviewer/customer.pptx", "slide_id": "safe-slide"},
            {"slide_id": "/private/reviewer/secret"},
            {"slide_id": "../escape"},
        ]

        for attack in attacks:
            with self.subTest(attack=attack):
                raw = {**attack, "score": 0.8}
                first, _ = normalize_candidate(raw, run_dir=self.temp_dir, reuse_policy="adapt", index=1)
                second, _ = normalize_candidate(raw, run_dir=self.temp_dir, reuse_policy="adapt", index=1)
                self.assertEqual(first["asset_key"], second["asset_key"])
                self.assertEqual(first["candidate_id"], second["candidate_id"])
                serialized = json.dumps(first)
                for value in attack.values():
                    if "/" in value or "\\" in value:
                        self.assertNotIn(value, serialized)
                self.assertNotIn("/", first["candidate_id"])
                self.assertNotIn("\\", first["candidate_id"])

    def test_v2_import_rejects_unsafe_identity_fields(self) -> None:
        run_dir = create_run(self.temp_dir / "runs", {"project_name": "Bridge", "run_id": "bridge-run"}, force=True)
        attacks = [
            ("asset_key", "/Users/reviewer/asset"),
            ("candidate_id", "/private/reviewer/candidate"),
            ("slide_id", "../escape"),
        ]

        for index, (field, value) in enumerate(attacks):
            with self.subTest(field=field, value=value):
                payload = _valid_v2_payload()
                payload["selections"][0]["candidates"][0][field] = value
                selection_path = self.temp_dir / f"unsafe-{index}.json"
                selection_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(PPTLibraryClientError):
                    import_library_selection(run_dir, selection_path)
        self.assertFalse((run_dir / "library_results" / "selection.json").exists())

    def test_bridge_contract_schemas_are_valid_and_accept_built_plan(self) -> None:
        plan_schema = json.loads(
            (ROOT / "docs" / "contracts" / "ppt-library-bridge-plan.v1.schema.json").read_text(encoding="utf-8")
        )
        selection_schema = json.loads(
            (ROOT / "docs" / "contracts" / "ppt-library-selection.v2.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", plan_schema["$schema"])
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", selection_schema["$schema"])
        self.assertIn("requests", plan_schema["required"])
        self.assertIn("selections", selection_schema["required"])
        self.assertIn("asset_key", selection_schema["$defs"]["candidate"]["required"])
        plan = build_bridge_plan(
            _plan(_beat("beat-001", "opener", 1)),
            {"tasks": [{"beat_id": "beat-001", "page_task_id": "page-001"}]},
            run_id="bridge-run",
            run_mode="dev",
        )
        self.assertEqual(set(plan_schema["required"]), set(plan))
        self.assertEqual(
            set(plan_schema["$defs"]["request"]["required"]),
            set(plan["requests"][0]),
        )

    def test_v2_import_preserves_normalized_identity_and_rejects_raw_paths(self) -> None:
        run_dir = create_run(self.temp_dir / "runs", {"project_name": "Bridge", "run_id": "bridge-run"}, force=True)
        preview = run_dir / "preview_assets" / "ppt_library" / "preview.png"
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b"png")
        source_asset_id = hashlib.sha256(b"source").hexdigest()
        trace_id = hashlib.sha256(b"trace").hexdigest()
        payload = {
            "schema_version": "deck_master_ppt_library_selection.v2",
            "run_id": "bridge-run",
            "status": "library_ready",
            "source": "ppt_library",
            "preview_degraded": False,
            "warnings": [],
            "by_beat": {},
            "selections": [
                {
                    "beat_id": "beat-001",
                    "page_task_id": "page-001",
                    "query_trace_id": trace_id,
                    "role_original": "opener",
                    "role_strategy": "passthrough",
                    "role_mapped": "opener",
                    "retrieval_method": "role_selection",
                    "fallback_reason": "",
                    "preview_status": "ready",
                    "preview_degraded": False,
                    "candidates": [
                        {
                            "candidate_id": "slide-001",
                            "slide_id": "slide-001",
                            "asset_key": "canonical:slide-001",
                            "title": "Title",
                            "text_summary": "Summary",
                            "page_number": 1,
                            "score": 0.8,
                            "confidence": 0.8,
                            "source_asset_id": source_asset_id,
                            "source_display_name": "Safe Deck.pptx",
                            "screenshot_ref": "preview_assets/ppt_library/preview.png",
                            "candidate_origin": "ppt_library",
                            "reuse_policy": "reuse_or_adapt",
                        }
                    ],
                }
            ],
        }
        selection_path = self.temp_dir / "selection-v2.json"
        selection_path.write_text(json.dumps(payload), encoding="utf-8")

        import_library_selection(run_dir, selection_path)

        normalized = read_json(run_dir / "external" / "ppt_library" / "library_results.v2.json")
        candidate = normalized["selections"][0]["candidates"][0]
        self.assertEqual("canonical:slide-001", candidate["asset_key"])
        self.assertEqual("preview_assets/ppt_library/preview.png", candidate["screenshot_ref"])
        before = (run_dir / "library_results" / "selection.json").read_text(encoding="utf-8")
        payload["selections"][0]["candidates"][0]["screenshot_ref"] = "/Users/private/preview.png"
        invalid_path = self.temp_dir / "invalid-v2.json"
        invalid_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(PPTLibraryClientError):
            import_library_selection(run_dir, invalid_path)

        self.assertEqual(before, (run_dir / "library_results" / "selection.json").read_text(encoding="utf-8"))

    def test_import_rejects_path_escaping_beat_id(self) -> None:
        payload = {
            "schema_version": "deck_master_ppt_library_selection.v1",
            "run_id": "bridge-run",
            "by_beat": {"../escape": []},
        }

        result = validate_library_selection(payload)

        self.assertFalse(result["valid"])
        self.assertTrue(any("path-safe" in error for error in result["errors"]))


class PPTLibraryBridgeRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.narrative = _plan(
            _beat("beat-001", "solution_detail", 1, reuse_query="query one"),
            _beat("beat-002", "solution_detail", 2, reuse_query="query two"),
        )
        (self.temp_dir / "narrative_plan.json").write_text(json.dumps(self.narrative), encoding="utf-8")
        (self.temp_dir / "page_tasks.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {"beat_id": "beat-001", "page_task_id": "page-001"},
                        {"beat_id": "beat-002", "page_task_id": "page-002"},
                    ]
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    def test_role_gap_searches_each_beat_and_writes_private_raw_v2(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[1] == "select-slides":
                output = Path(command[command.index("--output") + 1])
                output.write_text(json.dumps({"report": {"roles": [{"role": "solution", "slides": []}]}}), encoding="utf-8")
                return self._completed()
            query = command[2]
            page = 1 if query == "query one" else 2
            payload = {
                "results": [
                    {"slide_id": f"slide-{page}", "source_file": f"/Users/private/deck-{page}.pptx", "page_number": page, "score": 0.8}
                ]
            }
            return self._completed(json.dumps(payload))

        with mock.patch("tools.ppt_library_client.subprocess.run", side_effect=fake_run):
            result = run_library_selection(
                narrative_plan=self.narrative,
                narrative_plan_path=self.temp_dir / "narrative_plan.json",
                request={"run_id": "bridge-run", "run_mode": "dev", "brief": "brief"},
                run_dir=self.temp_dir,
                mode="real",
            )

        self.assertEqual("library_degraded", result["status"])
        self.assertEqual(2, sum(command[1] == "select-slides" for command in calls))
        self.assertEqual(2, sum(command[1] == "search" for command in calls))
        self.assertTrue((self.temp_dir / "external" / "ppt_library" / "private" / "bridge_plan.v1.json").is_file())
        self.assertTrue((self.temp_dir / "external" / "ppt_library" / "library_results.v2.json").is_file())
        self.assertFalse((self.temp_dir / "library_results" / "selection.raw.json").exists())
        normalized = (self.temp_dir / "library_results" / "selection.json").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", normalized)
        self.assertNotIn("/private/", normalized)
        self.assertTrue(all(item["retrieval_method"] == "semantic_fallback" for item in result["selections"]))

    def test_semantic_gap_never_uses_fixture_and_reports_library_gap(self) -> None:
        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if command[1] == "select-slides":
                output = Path(command[command.index("--output") + 1])
                output.write_text(json.dumps({"report": {"roles": []}}), encoding="utf-8")
                return self._completed()
            return self._completed(json.dumps({"results": []}))

        with mock.patch("tools.ppt_library_client.subprocess.run", side_effect=fake_run):
            result = run_library_selection(
                narrative_plan=self.narrative,
                narrative_plan_path=self.temp_dir / "narrative_plan.json",
                request={"run_id": "bridge-run", "run_mode": "dev"},
                run_dir=self.temp_dir,
                mode="real",
                allow_fixture_fallback=True,
            )

        self.assertEqual("library_gap", result["status"])
        self.assertTrue(all(item["retrieval_method"] == "none" for item in result["selections"]))
        self.assertFalse(any(candidate.get("candidate_origin") == "fixture" for values in result["by_beat"].values() for candidate in values))

    def test_real_command_failure_writes_library_blocked_without_fixture(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="contract failure")
        with mock.patch("tools.ppt_library_client.subprocess.run", return_value=completed):
            with self.assertRaises(PPTLibraryClientError):
                run_library_selection(
                    narrative_plan=self.narrative,
                    narrative_plan_path=self.temp_dir / "narrative_plan.json",
                    request={"run_id": "bridge-run", "run_mode": "production"},
                    run_dir=self.temp_dir,
                    mode="real",
                )

        result = read_json(self.temp_dir / "external" / "ppt_library" / "library_results.v2.json")
        self.assertEqual("library_blocked", result["status"])
        self.assertFalse(any(candidate.get("candidate_origin") == "fixture" for values in result["by_beat"].values() for candidate in values))

    def test_page_local_dedupe_keeps_highest_score_without_cross_page_allocation(self) -> None:
        shared = {"canonical_slide_id": "same", "slide_id": "slide", "source_file": "/tmp/deck.pptx", "page_number": 1}

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            output = Path(command[command.index("--output") + 1])
            output.write_text(
                json.dumps({"report": {"roles": [{"role": "solution", "slides": [{**shared, "score": 0.4}, {**shared, "score": 0.9}]}]}}),
                encoding="utf-8",
            )
            return self._completed()

        with mock.patch("tools.ppt_library_client.subprocess.run", side_effect=fake_run):
            result = run_library_selection(
                narrative_plan=self.narrative,
                narrative_plan_path=self.temp_dir / "narrative_plan.json",
                request={"run_id": "bridge-run", "run_mode": "dev"},
                run_dir=self.temp_dir,
                mode="real",
            )

        self.assertEqual([0.9], [item["score"] for item in result["by_beat"]["beat-001"]])
        self.assertEqual([0.9], [item["score"] for item in result["by_beat"]["beat-002"]])


if __name__ == "__main__":
    unittest.main()
