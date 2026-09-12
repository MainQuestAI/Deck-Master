"""SC-1 PR-06 tests: external review v2, Q-13 semantic pre-checks.

Acceptance mapping:
- Q-01: v2 report validation is fail-closed — missing dimensions, incomplete
  coverage without skips, self-review (reviewer == producer session), pass
  with findings, and pass with incomplete coverage are all rejected.
- Q-04: reviewer string alone is not independence — reviewer_session_id must
  differ from producer_session_id.
- Q-05: the v2 task binds reviewed inputs to current page package index sha.
- Q-13: numbers in client-visible text without a resolvable evidence binding
  or design basis are found; supported pages are clean; internal label leaks
  are found.
- Prompt upgrade: quality_reviewer.prompt.md carries the v2 six-dimension
  vocabulary matching the schema enum.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from quality.external_review import (  # noqa: E402
    RESULT_SCHEMA_VERSION_V2,
    REVIEW_DIMENSIONS_V2,
    prepare_quality_review_v2,
    validate_external_review,
    validate_external_review_v2,
)
from quality.semantic_checks import (  # noqa: E402
    find_internal_label_leak,
    find_unsupported_numbers,
    scan_delivery_pptx,
)

ROOT = Path(__file__).resolve().parents[1]


def _v2_report(**overrides) -> dict:
    from quality_review_v2_helpers import canonical_report
    report = canonical_report()
    report.update(overrides)
    return report


class ExternalReviewV2Tests(unittest.TestCase):
    def test_valid_v2_report_passes(self) -> None:
        result = validate_external_review_v2(_v2_report())
        self.assertTrue(result["valid"], result["errors"])

    def test_self_review_rejected(self) -> None:
        report = _v2_report(producer_session_id="session-reviewer")
        result = validate_external_review_v2(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("independence" in item for item in result["errors"]))

    def test_missing_dimension_observation_rejected(self) -> None:
        report = _v2_report()
        report["observations"] = report["observations"][:-1]
        result = validate_external_review_v2(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("observation" in item or "too short" in item for item in result["errors"]))

    def test_incomplete_coverage_needs_skip_reason(self) -> None:
        report = _v2_report()
        report["coverage"]["reviewed_page_ids"] = ["P001"]
        result = validate_external_review_v2(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("coverage incomplete" in item for item in result["errors"]))
        report["coverage"]["skipped"] = [{"ref": "P002"}]
        result = validate_external_review_v2(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("reason" in item for item in result["errors"]))

    def test_pass_with_findings_rejected(self) -> None:
        report = _v2_report()
        report["findings"] = [{"finding_id": "f1", "severity": "P1", "page_id": "P001", "message": "weak evidence"}]
        result = validate_external_review_v2(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("findings" in item for item in result["errors"]))

    def test_v1_reports_still_validate_under_v1_semantics(self) -> None:
        v1 = {
            "schema_version": "deck_external_quality_review.v1",
            "run_id": "run-q",
            "reviewer": "external-reviewer",
            "scope": "semantic",
            "findings": [],
        }
        result = validate_external_review(v1)
        self.assertTrue(result["valid"])

    def test_v2_task_binds_current_input_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run-q"
            (root / "page_packages").mkdir(parents=True)
            (root / "page_packages" / "index.json").write_text("{}\n", encoding="utf-8")
            (root / "page_packages" / "P001.json").write_text('{"page_id":"P001"}')
            task = prepare_quality_review_v2(root, scope="semantic", required_page_ids=["P001"])
            self.assertEqual(64, len(task["based_on"]["input_fingerprint"]))
            self.assertEqual(REVIEW_DIMENSIONS_V2, tuple(task["review_dimensions"]))


class UnsupportedNumberTests(unittest.TestCase):
    def test_unsupported_number_found(self) -> None:
        package = {
            "page_id": "P001",
            "evidence_bindings": [],
            "internal_only": {},
            "customer_visible": {"body_blocks": [{"type": "conclusion", "text": "审批周期可缩短 45%。"}], "labels": []},
        }
        findings = find_unsupported_numbers([package])
        self.assertTrue(any(item["page_id"] == "P001" and "45%" in item["message"] for item in findings))

    def test_source_id_alone_does_not_support_numeric_claim(self) -> None:
        package = {
            "page_id": "P001",
            "evidence_bindings": ["src_meeting"],
            "internal_only": {},
            "customer_visible": {"body_blocks": [{"type": "conclusion", "text": "审批周期可缩短 45%。"}], "labels": []},
        }
        manifest = {"sources": [{"source_id": "src_meeting"}]}
        self.assertTrue(find_unsupported_numbers([package], context_manifest=manifest))

    def test_design_basis_alone_does_not_support_numeric_claim(self) -> None:
        package = {
            "page_id": "P002",
            "evidence_bindings": [],
            "internal_only": {"design_basis_ref": "solution_model#capability:C1"},
            "customer_visible": {"body_blocks": [{"type": "conclusion", "text": "并行后 20 天内完成。"}], "labels": []},
        }
        self.assertTrue(find_unsupported_numbers([package]))

    def test_internal_label_leak_found(self) -> None:
        package = {
            "page_id": "P001",
            "customer_visible": {
                "body_blocks": [{"type": "text", "text": "SO WHAT: 客户应当立即行动。"}],
                "labels": [],
            },
        }
        findings = find_internal_label_leak([package])
        self.assertTrue(any("SO WHAT" in item["message"] for item in findings))


class PromptUpgradeTests(unittest.TestCase):
    def test_prompt_carries_v2_dimension_vocabulary(self) -> None:
        text = (ROOT / "skills" / "deck-master" / "prompts" / "quality_reviewer.prompt.md").read_text(encoding="utf-8")
        for dimension in REVIEW_DIMENSIONS_V2:
            self.assertIn(dimension, text)
        self.assertIn("deck_external_quality_review.v2", text)
        self.assertNotIn("claim_evidence_alignment", text)
        schema = json.loads((ROOT / "docs" / "contracts" / "external-quality-review.v2.schema.json").read_text(encoding="utf-8"))
        enum = schema["properties"]["observations"]["items"]["properties"]["dimension"]["enum"]
        self.assertEqual(sorted(enum), sorted(REVIEW_DIMENSIONS_V2))


class DeliveryPptxScanTests(unittest.TestCase):
    def _pptx_with(self, tmp: Path, *, notes: bool = False, metadata: bool = False, hidden: bool = False) -> Path:
        from pptx import Presentation
        from pptx.util import Inches

        presentation = Presentation()
        presentation.core_properties.author = ""
        presentation.core_properties.last_modified_by = ""
        presentation.core_properties.comments = ""
        presentation.core_properties.keywords = ""
        presentation.core_properties.category = ""
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        box = slide.shapes.add_textbox(0, 0, 100, 50)
        box.text = "结论：审批周期可缩短。"
        if notes:
            slide.notes_slide.notes_text_frame.text = "内部提示：下一版补案例"
        if hidden:
            slide._element.set('show', '0')
        if metadata:
            presentation.core_properties.author = "internal-agent"
        path = Path(tmp) / "deck.pptx"
        presentation.save(str(path))
        return path

    def test_clean_pptx_has_no_findings(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._pptx_with(Path(tmp))
            self.assertEqual([], scan_delivery_pptx(path))

    def test_notes_metadata_hidden_detected(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._pptx_with(Path(tmp), notes=True, metadata=True, hidden=True)
            checks = {item["check"] for item in scan_delivery_pptx(path)}
            self.assertIn("speaker_notes", checks)
            self.assertIn("metadata_leak", checks)
            self.assertIn("hidden_slide", checks)


if __name__ == "__main__":
    unittest.main()
