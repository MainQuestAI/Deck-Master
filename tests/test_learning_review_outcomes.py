"""Delivery events must never become reviewed outcomes in the public CLI."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from learning.pack import build_learning_pack


def test_cli_exports_cannot_overwrite_rejection_or_invent_acceptance(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    events = [
        {"event_type": "preview_rejected", "canonical_slide_id": "rejected", "run_id": "r", "reviewed_revision": "v1"},
        {"event_type": "exported_client", "canonical_slide_id": "rejected", "run_id": "r", "reviewed_revision": "v1"},
        {"event_type": "exported_internal", "canonical_slide_id": "export_only", "run_id": "r", "reviewed_revision": "v1"},
        {"event_type": "preview_approved", "canonical_slide_id": "no_revision", "run_id": "r"},
        {"event_type": "preview_approved", "canonical_slide_id": "no_run", "reviewed_revision": "v1"},
    ]
    source = assets / "asset_feedback.jsonl"
    original = "".join(json.dumps(event) + "\n" for event in events)
    source.write_text(original)
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/deck_master.py"),
               "build-learning-pack", "--workspace", str(tmp_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    pack = json.loads(result.stdout)
    assert [(a["canonical_slide_id"], a["acceptance_rate"], a["rejected_count"], a["delivered_count"])
            for a in pack["strong_assets"]] == [("rejected", 0.0, 1, 1)]
    assert pack["legacy_feedback_unknown"] == 2
    assert source.read_text() == original
    assert json.loads((tmp_path / "learning/workspace_learning_pack.json").read_text()) == pack


def test_delivery_count_cannot_break_equal_review_ranking(tmp_path):
    (tmp_path / "assets").mkdir()
    events = [{"event_type": "preview_approved", "canonical_slide_id": slide,
               "run_id": "r", "reviewed_revision": "v1"} for slide in ["first", "second"]]
    events.extend({"event_type": "exported_client", "canonical_slide_id": "second",
                   "run_id": "r", "reviewed_revision": "v1"} for _ in range(5))
    (tmp_path / "assets/asset_feedback.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    pack = build_learning_pack(tmp_path)
    assert [a["canonical_slide_id"] for a in pack["strong_assets"]] == ["first", "second"]
    assert pack["strong_assets"][1]["delivered_count"] == 5
