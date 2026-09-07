"""Task routing must remain read-only and preserve selected-page intent."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("task", "profile", "expected"), [
    ("new_deck", "standard", "deck-brief"),
    ("local_edit", "standard", "deck-producer"),
    ("local_edit", "high_density", "deck-builder-high-density"),
    ("diagnosis", "high_density", "deck-doctor"),
    ("client_delivery", "standard", "deck-review"),
    ("software_release", "standard", "deck-upgrade"),
])
def test_task_route_with_incomplete_run_preserves_intent(tmp_path, task, profile, expected):
    run = tmp_path / "existing-run"
    run.mkdir()
    request = run / "request.json"
    request.write_text(json.dumps({"run_id": "existing-run", "builder_profile": profile}))
    original = request.read_bytes()
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/deck_master.py"), "route-skill", "--input-type", task, "--run-dir", str(run)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["recommended_skill"] == expected
    assert payload["read_only"] is (task == "diagnosis")
    assert len(payload["read_refs"]) == 1
    assert (ROOT / payload["read_refs"][0]).is_file()
    assert list(run.iterdir()) == [request]
    assert request.read_bytes() == original


def test_selected_page_retry_preserves_style_storyline_and_other_page(tmp_path, monkeypatch):
    from tests.test_high_density_builder_v2 import (
        _make_run, _blueprint, prepare_high_density, run_high_density,
        retry_high_density, svg_path, read_json, pptx_path,
    )
    from pptx import Presentation

    monkeypatch.setenv("DECK_MASTER_RUNTIME_INTEGRITY_KEY", "a" * 64)
    run, _ = _make_run(tmp_path, page_count=2)
    _blueprint(run, "P001")
    _blueprint(run, "P002")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    hd = run / "high_density_build"
    preserve = [
        run / "page_packages/P001.json", run / "page_packages/P002.json",
        hd / "mbb/selection_receipt.json", hd / "style/style_lock.json",
        hd / "scenes/P002.page_scene.json", svg_path(run, "P002"),
    ]
    before = {path: path.read_bytes() for path in preserve}
    # A real rendering retry reconstructs P001 after loss of its SVG.
    svg_path(run, "P001").unlink()
    result = retry_high_density(run, page_id="P001", stage="svg")
    assert result["status"] == "completed"
    assert svg_path(run, "P001").is_file()
    assert {path: path.read_bytes() for path in preserve} == before
    assert read_json(hd / "status.json")["status"] == "completed"
    assert len(Presentation(pptx_path(run)).slides) == 2
