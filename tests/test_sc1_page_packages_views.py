"""SC-1 PR-05 tests: page package production writer, standard build
consumption, and diagram views.

Acceptance mapping:
- P-04 (engineering): one complete package per narrative beat; production
  instructions never enter customer text; index coverage is honest; pages
  without evidence or design basis stay draft (no source self-certification).
- P-01/P-05 (engineering): prepare_build consumes page packages — page
  entries are anchored to package shas and body content; production builds
  require approved packages (no packages / draft packages → blocked); the
  fixture HTML renders package conclusions.
- D-01/D-02/D-03 (engineering): all four view types build; views referencing
  model objects or relations that do not exist are rejected; component
  changes report affected views and pages.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from production.diagram_views import build_diagram_view, impact_of_component_change, validate_diagram_view  # noqa: E402
from production.page_builder import build_packages_from_narrative, write_page_packages  # noqa: E402
from production.page_package import PagePackageError, PagePackageIndex  # noqa: E402
from runtime.build import BuildError, prepare_build  # noqa: E402
from runtime.run_state import create_run, write_json  # noqa: E402


def _narrative(run_id: str = "run-pp", *, with_evidence: bool = True) -> dict:
    beats = [
        {
            "beat_id": "beat_01_opener",
            "order": 1,
            "page_title": "核心问题",
            "role": "opener",
            "conclusion": "审批串行流转是周期过长的根因。",
            "page_job": "对齐客户决策与衡量标准",
            "business_implication": "压缩并行等待即可压缩周期。",
            "evidence_refs": ["src_meeting"] if with_evidence else [],
            "claim_refs": [],
            "required_components": [],
            "expected_visual": "文字+结构化图形",
        },
        {
            "beat_id": "beat_02_solution",
            "order": 2,
            "page_title": "并行审批工作流",
            "role": "solution",
            "conclusion": "并行分派替代串行签核。",
            "page_job": "说明能力机制",
            "required_components": ["comp_workflow"],
            "expected_visual": "流程图",
        },
    ]
    return {"run_id": run_id, "beats": beats}


def _manifest() -> dict:
    return {"sources": [{"source_id": "src_meeting", "name": "会议记录"}]}


def _solution_model() -> dict:
    return {
        "components": [
            {"component_id": "comp_workflow", "title": "审批引擎", "status": "proposed"},
            {"component_id": "comp_repo", "title": "资料库", "status": "existing"},
        ],
        "capabilities": [
            {"capability_id": "C1", "title": "并行审批", "mechanism": "并行分派", "problem_ids": ["P1"], "component_ids": ["comp_workflow"]}
        ],
        "problems": [{"problem_id": "P1", "title": "周期长", "statement": "45 天"}],
        "relations": [{"relation_id": "relation_01", "source": "comp_repo", "target": "comp_workflow", "kind": "feeds"}],
    }


class PagePackageWriterTests(unittest.TestCase):
    def test_one_complete_package_per_beat(self) -> None:
        packages = build_packages_from_narrative(
            run_id="run-pp", narrative_plan=_narrative(), context_manifest=_manifest(), solution_model=_solution_model()
        )
        self.assertEqual(2, len(packages))
        opener, solution = packages
        self.assertIn("conclusion", opener["customer_visible"]["body_blocks"][0]["type"])
        self.assertEqual("solution_model#capability:C1", solution["internal_only"]["design_basis_ref"])
        self.assertEqual("ready_for_build", solution["status"])

    def test_source_reference_is_design_provenance_not_verified_evidence(self) -> None:
        packages = build_packages_from_narrative(run_id="run-pp", narrative_plan=_narrative(), context_manifest=_manifest())
        self.assertEqual("design_basis", packages[0]["internal_only"]["evidence_state"])
        self.assertEqual([], packages[0]["evidence_bindings"])
        self.assertTrue(packages[0]["provenance"]["source_refs"])
        self.assertEqual("ready_for_build", packages[0]["status"])

    def test_missing_evidence_and_design_basis_stays_draft(self) -> None:
        packages = build_packages_from_narrative(run_id="run-pp", narrative_plan=_narrative(with_evidence=False))
        self.assertEqual("insufficient", packages[0]["internal_only"]["evidence_state"])
        self.assertEqual("draft", packages[0]["status"])

    def test_production_instruction_in_body_rejected(self) -> None:
        plan = _narrative()
        plan["beats"][0]["conclusion"] = "核心结论：请补充客户数据。"
        with self.assertRaises(PagePackageError):
            build_packages_from_narrative(run_id="run-pp", narrative_plan=plan)

    def test_write_creates_index_and_reports_honestly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-pp"
            create_run(str(run_dir.parent), {"run_id": "run-pp", "project_name": "P"}, run_id="run-pp")
            report = write_page_packages(
                run_dir,
                narrative_plan=_narrative(),
                context_manifest=_manifest(),
                solution_model=_solution_model(),
            )
            self.assertEqual(2, report["page_count"])
            self.assertTrue(report["coverage"]["complete"])
            index = json.loads((run_dir / "page_packages" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(2, index["page_count"])
            self.assertEqual({"beat_01_opener": "generate", "beat_02_solution": "generate"}, report["sourcing_strategies"])

    def test_none_sourcing_strategy_from_plan(self) -> None:
        sourcing = {"pages": [{"page_id": "beat_01_opener", "decision": "generate", "reason": "NO_CANDIDATE_GENERATE"}]}
        packages = build_packages_from_narrative(run_id="run-pp", narrative_plan=_narrative(), sourcing_plan=sourcing)
        self.assertEqual("generate", packages[0]["internal_only"]["sourcing"]["strategy"])


class StandardBuildConsumptionTests(unittest.TestCase):
    def _run(self, tmp: Path) -> Path:
        run_dir = Path(tmp) / "build-run"
        create_run(str(tmp), {"run_id": "build-run", "project_name": "B"}, run_id="build-run")
        return run_dir

    def test_prepare_build_consumes_packages_in_dev(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            write_json(run_dir / "request.json", {"run_id": "build-run", "run_mode": "fixture"})
            write_page_packages(run_dir, narrative_plan={**_narrative("build-run")}, context_manifest=_manifest())
            result = prepare_build(run_dir)
            self.assertEqual("page_packages", result["source_mode"])
            manifest = json.loads((run_dir / "build" / "build_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(2, manifest["page_count"])
            page = manifest["pages"][0]
            self.assertEqual("page_packages/beat_01_opener.json", page["source_path"])
            self.assertTrue(page["customer_payload_sha256"])
            self.assertTrue(page["body_blocks"])

    def test_production_without_packages_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            request = {"run_id": "build-run", "run_mode": "production"}
            write_json(run_dir / "request.json", request)
            with self.assertRaises(BuildError) as ctx:
                prepare_build(run_dir)
            self.assertIn("page_packages", str(ctx.exception))

    def test_production_with_draft_package_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            write_page_packages(run_dir, narrative_plan=_narrative(with_evidence=False), context_manifest=_manifest())
            request = {"run_id": "build-run", "run_mode": "production"}
            write_json(run_dir / "request.json", request)
            with self.assertRaises(BuildError) as ctx:
                prepare_build(run_dir)
            self.assertIn("not approved", str(ctx.exception))

    def test_html_renders_package_conclusions(self) -> None:
        from deck_master import command_render

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run(Path(tmp))
            write_json(run_dir / "request.json", {"run_id": "build-run", "run_mode": "fixture"})
            write_page_packages(run_dir, narrative_plan={**_narrative("build-run")}, context_manifest=_manifest())
            command_render(
                __import__("argparse").Namespace(run_dir=str(run_dir), run_id=None, runs_dir=None, fixture_safe=False, format="html")
            )
            html = (run_dir / "build" / "deck.html").read_text(encoding="utf-8")
            self.assertIn("审批串行流转是周期过长的根因。", html)


class DiagramViewTests(unittest.TestCase):
    def _view_nodes(self) -> tuple[list[dict], list[dict]]:
        nodes = [
            {"node_id": "n1", "model_ref": "comp_workflow", "status": "proposed", "label": "审批引擎"},
            {"node_id": "n2", "model_ref": "comp_repo", "aggregates": ["comp_repo"], "status": "existing", "label": "资料库"},
        ]
        edges = [{"edge_id": "e1", "source_node": "n2", "target_node": "n1", "relation_ref": "relation_01"}]
        return nodes, edges

    def test_all_four_view_types_build(self) -> None:
        nodes, edges = self._view_nodes()
        for view_type in ("business_architecture", "application_architecture", "data_flow", "implementation_roadmap"):
            view = build_diagram_view(
                view_id=f"v-{view_type}",
                view_type=view_type,
                solution_model=_solution_model(),
                target_page_id="beat_02_solution",
                nodes=nodes,
                edges=edges,
            )
            self.assertEqual("deck_diagram_view.v1", view["schema_version"])
            self.assertTrue(view["solution_model_sha256"])

    def test_unknown_model_reference_rejected(self) -> None:
        nodes = [{"node_id": "n1", "model_ref": "comp_ghost", "label": "幽灵组件"}]
        edges: list[dict] = []
        with self.assertRaises(ValueError) as ctx:
            build_diagram_view(
                view_id="v1", view_type="business_architecture", solution_model=_solution_model(),
                target_page_id="p1", nodes=nodes, edges=edges,
            )
        self.assertIn("does not exist", str(ctx.exception))

    def test_edge_without_model_relation_rejected(self) -> None:
        nodes = [
            {"node_id": "n1", "model_ref": "comp_workflow", "label": "审批"},
            {"node_id": "n2", "model_ref": "comp_repo", "label": "资料"},
        ]
        edges = [{"edge_id": "e1", "source_node": "n1", "target_node": "n2"}]
        problems = validate_diagram_view({"nodes": nodes, "edges": edges}, solution_model=_solution_model())
        self.assertTrue(any("cannot invent" in item for item in problems))

    def test_aggregation_must_list_members(self) -> None:
        nodes = [{"node_id": "n1", "label": "神秘聚合"}]
        problems = validate_diagram_view({"nodes": nodes, "edges": []}, solution_model=_solution_model())
        self.assertTrue(any("neither a model_ref" in item for item in problems))

    def test_component_change_impact_reports_views_and_pages(self) -> None:
        nodes, edges = self._view_nodes()
        view = build_diagram_view(
            view_id="v1", view_type="business_architecture", solution_model=_solution_model(),
            target_page_id="beat_02_solution", nodes=nodes, edges=edges,
        )
        before = _solution_model()
        after = _solution_model()
        after["components"] = [c for c in after["components"] if c["component_id"] != "comp_repo"]
        impact = impact_of_component_change(before, after, [view])
        self.assertIn("comp_repo", impact["removed_components"])
        self.assertIn("v1", impact["affected_views"])
        self.assertIn("beat_02_solution", impact["affected_page_ids"])


if __name__ == "__main__":
    unittest.main()
