"""SC-1 PR-07 tests: feedback metric fix (C4), Review Desk writeback (F11).

Acceptance mapping:
- L-01: acceptance_rate = accepted / (accepted + rejected) over final review
  decisions deduped by (asset, run, reviewed revision); 9 approvals + 91
  rejections yield 9%; intermediate superseded decisions do not double count;
  repeated exports do not lift the rate.
- L-02: small samples show counts, not generalization; legacy events without
  a revision identity land in legacy_unknown and never feed the rate.
- L-03: no fabricated high-value patterns when there is no feedback.
- L-04 (F11): Review Desk approve/reject writes back to the workspace
  asset_feedback.jsonl with the reviewed revision; the stats then dedupe.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from learning.pack import build_learning_pack  # noqa: E402
from review.workbench import execute_review_action  # noqa: E402
from runtime.run_state import create_run  # noqa: E402


def _workspace(tmp: Path) -> tuple[Path, Path]:
    ws = tmp / "workspace"
    (ws / "assets").mkdir(parents=True)
    (ws / "runs").mkdir()
    return ws, ws / "assets" / "asset_feedback.jsonl"


def _event(event_type: str, slide: str, run: str, revision: str, **extra) -> dict:
    return {
        "event_type": event_type,
        "canonical_slide_id": slide,
        "run_id": run,
        "payload": {"reviewed_revision": revision, **extra},
    }


class AcceptanceRateTests(unittest.TestCase):
    def test_nine_ninety_one_sample_yields_nine_percent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws, fb_path = _workspace(Path(tmp))
            with fb_path.open("a", encoding="utf-8") as fh:
                for index in range(9):
                    fh.write(json.dumps(_event("preview_approved", "slide_x", f"run-{index}", f"rev-{index}")) + "\n")
                for index in range(91):
                    fh.write(json.dumps(_event("preview_rejected", "slide_x", f"run-r{index}", f"rev-{index}")) + "\n")
            pack = build_learning_pack(ws)
            assets = pack["strong_assets"]
            self.assertEqual(1, len(assets))
            self.assertAlmostEqual(0.09, assets[0]["acceptance_rate"], places=2)
            self.assertEqual(9, assets[0]["accepted_count"])
            self.assertEqual(91, assets[0]["rejected_count"])
            # delivery stays independent: no delivered events at all
            self.assertEqual(0, assets[0]["delivered_count"])

    def test_superseded_intermediate_decision_not_double_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws, fb_path = _workspace(Path(tmp))
            with fb_path.open("a", encoding="utf-8") as fh:
                # same (asset, run, revision): approved then rejected → final
                # decision is rejected; the intermediate approve is superseded
                fh.write(json.dumps(_event("preview_approved", "slide_x", "run-1", "rev-1")) + "\n")
                fh.write(json.dumps(_event("preview_rejected", "slide_x", "run-1", "rev-1")) + "\n")
            pack = build_learning_pack(ws)
            assets = pack["strong_assets"]
            self.assertEqual(1, len(assets))
            self.assertEqual(0, assets[0]["accepted_count"])
            self.assertEqual(1, assets[0]["rejected_count"])
            self.assertAlmostEqual(0.0, assets[0]["acceptance_rate"])

    def test_repeated_exports_do_not_lift_rate_or_rank(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws, fb_path = _workspace(Path(tmp))
            with fb_path.open("a", encoding="utf-8") as fh:
                # the same reviewed revision exported 5 times = ONE accepted unit
                for _ in range(5):
                    fh.write(json.dumps(_event("exported_client", "slide_y", "run-e", "rev-e")) + "\n")
                fh.write(json.dumps(_event("preview_rejected", "slide_y", "run-r", "rev-r")) + "\n")
                for index in range(9):
                    fh.write(json.dumps(_event("preview_approved", "slide_x", f"run-a{index}", f"rev-a{index}")) + "\n")
            pack = build_learning_pack(ws)
            by_id = {a["canonical_slide_id"]: a for a in pack["strong_assets"]}
            # 5 exports of the same unit dedupe to one acceptance; not 5/6
            self.assertAlmostEqual(0.5, by_id["slide_y"]["acceptance_rate"])
            self.assertEqual(1, by_id["slide_y"]["accepted_count"], "repeated exports of one unit must not lift the rate")
            self.assertEqual(5, by_id["slide_y"]["delivered_count"], "delivery counting stays independent of outcome")
            # ranking is outcome-first despite slide_y's higher delivery count
            self.assertEqual("slide_x", pack["strong_assets"][0]["canonical_slide_id"])

    def test_legacy_events_without_revision_are_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws, fb_path = _workspace(Path(tmp))
            with fb_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"event_type": "preview_approved", "canonical_slide_id": "slide_old"}) + "\n")
            pack = build_learning_pack(ws)
            self.assertEqual(1, pack["legacy_feedback_unknown"])
            self.assertEqual([], pack["strong_assets"])

    def test_no_feedback_no_fabricated_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws, _ = _workspace(Path(tmp))
            pack = build_learning_pack(ws)
            self.assertEqual([], pack["strong_assets"])
            self.assertEqual([], pack["high_value_patterns"])
            self.assertEqual([], pack["experience_cards"])

    def test_experience_cards_only_from_real_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws, fb_path = _workspace(Path(tmp))
            with fb_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        _event(
                            "preview_rejected",
                            "slide_x",
                            "run-1",
                            "rev-1",
                            notes="ROI 数字没有来源，客户要求改为区间表述",
                            evidence_source_category="meeting_transcript",
                            applicable_scope="制造业续费方案",
                            not_applicable_scope="已具备可追溯测量的收益结论",
                            adopted_structure="区分测量结果与方案假设",
                            reusable_reason="无测量收益应改为区间表述并注明假设",
                            approval_scope="workspace_feedback",
                        )
                    )
                    + "\n"
                )
            pack = build_learning_pack(ws)
            cards = pack["experience_cards"]
            self.assertEqual(1, len(cards))
            card = cards[0]
            self.assertEqual("modified", card["kept_or_modified"])
            self.assertEqual("run-1", card["source_run_ref"])
            self.assertIn("区间表述", card["user_reason"])
            self.assertEqual("meeting_transcript", card["evidence_source_category"])
            self.assertEqual("workspace_feedback", card["approval_scope"])


from runtime.run_state import write_json  # noqa: E402


def _seed_run(run_dir: Path) -> None:
    links = run_dir / "links"
    links.mkdir(exist_ok=True)
    (links / "beat_001.svg").write_text("<svg></svg>\n", encoding="utf-8")
    write_json(run_dir / "preview_manifest.json", {
        "run_id": "run-f11",
        "title": "T",
        "status": "ready",
        "pages": [
            {"page_id": "P001", "beat_id": "beat_001", "order": 1, "title": "P1",
             "source_type": "generated", "preview_path": "links/beat_001.svg",
             "narrative_role": "solution", "decision": "needs_review"},
        ],
    })


class ReviewDeskWritebackTests(unittest.TestCase):
    def test_approve_writes_workspace_feedback_with_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "workspace"
            (ws / "assets").mkdir(parents=True)
            (ws / "runs").mkdir()
            run_dir = create_run(str(ws / "runs"), {"project_name": "P", "workspace": str(ws)}, run_id="run-f11")
            _seed_run(run_dir)
            execute_review_action(run_dir, "P001", "approve", actor="user", note="结构保留")
            fb_path = ws / "assets" / "asset_feedback.jsonl"
            entries = [json.loads(line) for line in fb_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(1, len(entries))
            entry = entries[0]
            self.assertEqual("preview_approved", entry["event_type"])
            self.assertEqual("P001", entry["canonical_slide_id"])
            self.assertEqual("run-f11", entry["run_id"])
            self.assertEqual("review_desk", entry["payload"]["source"])
            self.assertTrue(entry["payload"]["reviewed_revision"], "reviewed revision must be recorded for dedup")

    def test_reject_writes_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "workspace"
            (ws / "assets").mkdir(parents=True)
            (ws / "runs").mkdir()
            run_dir = create_run(str(ws / "runs"), {"project_name": "P", "workspace": str(ws)}, run_id="run-f11b")
            _seed_run(run_dir)
            execute_review_action(run_dir, "P001", "reject", actor="user", reason="数字无来源")
            fb_path = ws / "assets" / "asset_feedback.jsonl"
            entries = [json.loads(line) for line in fb_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual("preview_rejected", entries[0]["event_type"])
            self.assertEqual("数字无来源", entries[0]["notes"])


if __name__ == "__main__":
    unittest.main()
