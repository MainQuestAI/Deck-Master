"""Full-draft import: agent-written page packages entering the production chain.

Covers the WP3 integration rules: validated one-pass reception, stable page
identity, add/delete/reorder reflected in the active set, interrupted-import
recovery, downstream pruning, and the stage fast path that drives a
package-complete run straight to the builder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build.manifest import build_manifest_v2  # noqa: E402
from runtime.orchestration import import_plan  # noqa: E402
from runtime.run_state import create_run, read_json, write_json  # noqa: E402
from runtime.run_state_resolver import resolve_run_state  # noqa: E402

BACKEND_OK = {
    "name": "ppt-master",
    "production_capable": True,
    "contract_versions": ["deck_page_package.v1", "deck_build_manifest.v2"],
}


def _make_run(tmp_path: Path) -> Path:
    return create_run(
        tmp_path,
        {
            "run_id": "full-draft-run",
            "project_name": "Full Draft Run",
            "business_goal": "Deliver an imported complete draft",
            "run_mode": "fixture",
        },
        run_id="full-draft-run",
    )


def _beat(index: int, role: str = "solution") -> dict:
    return {
        "beat_id": f"beat_{index:02d}_{role}",
        "page_title": f"Page {index}",
        "role": role,
        "content_goal": f"Goal {index}",
        "reuse_query": f"query {index}",
        "generation_brief": f"Brief {index}",
    }


def _package(beat_id: str, title: str, body: str) -> dict:
    return {
        "beat_id": beat_id,
        "customer_visible": {
            "title": title,
            "body_blocks": [{"type": "text", "text": body}],
        },
    }


def _full_draft(beats: list[dict], packages: list[dict]) -> dict:
    return {
        "narrative_plan": {"title": "Full Draft", "density": "high", "beats": beats},
        "page_packages": packages,
    }


def _write_input(tmp_path: Path, payload: dict, name: str = "draft.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _package_files(run_dir: Path) -> set[str]:
    directory = run_dir / "page_packages"
    if not directory.is_dir():
        return set()
    return {path.name for path in directory.glob("*.json") if path.name != "index.json"}


def _draft_v1() -> tuple[list[dict], list[dict]]:
    beats = [_beat(1, "opener"), _beat(2, "problem"), _beat(3, "solution")]
    packages = [
        _package("beat_01_opener", "开场标题", "开场正文"),
        _package("beat_02_problem", "问题标题", "问题正文"),
        _package("beat_03_solution", "方案标题", "方案正文"),
    ]
    return beats, packages


def test_full_draft_import_writes_packages_index_and_mode(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    payload = _full_draft(beats, packages)

    result = import_plan(run_dir, _write_input(tmp_path, payload), source="agent")

    assert result["status"] == "imported"
    assert result["mode"] == "full_draft"
    assert result["page_packages"] == 3
    narrative = read_json(run_dir / "narrative_plan.json")
    assert narrative["target_pages"] == 3
    assert [beat["order"] for beat in narrative["beats"]] == [1, 2, 3]
    written = read_json(run_dir / "page_packages" / "beat_01_opener.json")
    assert written["status"] == "ready_for_build"
    assert written["beat_id"] == "beat_01_opener"
    assert written["run_id"] == "full-draft-run"
    assert written["customer_visible"]["title"] == "开场标题"
    assert len(written["source_fingerprint"]) == 64
    index = read_json(run_dir / "page_packages" / "index.json")
    assert index["page_count"] == 3
    assert [entry["page_id"] for entry in index["pages"]] == [
        "beat_01_opener",
        "beat_02_problem",
        "beat_03_solution",
    ]
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert '"mode": "full_draft"' in events


def test_json_plan_without_packages_reports_plan_mode(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, _ = _draft_v1()
    payload = {"narrative_plan": {"title": "Plan only", "density": "high", "beats": beats}}

    result = import_plan(run_dir, _write_input(tmp_path, payload), source="agent")

    assert result["mode"] == "plan"
    assert "page_packages" not in result
    assert not (run_dir / "page_packages").is_dir()


def test_missing_page_package_rejected_without_writes(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    payload = _full_draft(beats, packages[:2])  # beat_03 missing

    with pytest.raises(Exception, match="missing page packages for beats"):
        import_plan(run_dir, _write_input(tmp_path, payload), source="agent")

    assert not (run_dir / "page_packages").is_dir()
    assert not (run_dir / "narrative_plan.json").exists()


def test_unknown_beat_and_incomplete_body_rejected(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()

    unknown = _full_draft(beats, packages + [_package("beat_99_extra", "多出来的页", "正文")])
    with pytest.raises(Exception, match="unknown beat_id"):
        import_plan(run_dir, _write_input(tmp_path, unknown), source="agent")

    beats2, _ = _draft_v1()
    no_title = _full_draft(
        beats2,
        [
            _package("beat_01_opener", "", "正文"),
            _package("beat_02_problem", "问题标题", "问题正文"),
            _package("beat_03_solution", "方案标题", "方案正文"),
        ],
    )
    with pytest.raises(Exception, match="no complete customer-visible content"):
        import_plan(run_dir, _write_input(tmp_path, no_title), source="agent")

    assert not (run_dir / "page_packages").is_dir()


def test_duplicate_beat_package_rejected(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    duplicated = packages + [_package("beat_01_opener", "重复页", "重复正文")]

    with pytest.raises(Exception, match="duplicates beat_id"):
        import_plan(run_dir, _write_input(tmp_path, _full_draft(beats, duplicated)), source="agent")

    assert not (run_dir / "page_packages").is_dir()


def test_add_delete_reorder_roundtrip(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    import_plan(run_dir, _write_input(tmp_path, _full_draft(beats, packages), name="v1.json"), source="agent")

    v2_beats = [_beat(3, "solution"), _beat(1, "opener"), _beat(4, "case")]
    v2_packages = [
        _package("beat_03_solution", "方案标题改", "方案正文改"),
        _package("beat_01_opener", "开场标题", "开场正文"),
        _package("beat_04_case", "案例标题", "案例正文"),
    ]
    result = import_plan(run_dir, _write_input(tmp_path, _full_draft(v2_beats, v2_packages), name="v2.json"), source="agent")

    assert result["mode"] == "full_draft"
    assert result["removed_pages"] == ["beat_02_problem"]
    assert result["new_pages"] == ["beat_04_case"]
    assert result["reordered"] is True
    assert _package_files(run_dir) == {
        "beat_01_opener.json",
        "beat_03_solution.json",
        "beat_04_case.json",
    }
    index = read_json(run_dir / "page_packages" / "index.json")
    assert [entry["page_id"] for entry in index["pages"]] == [
        "beat_03_solution",
        "beat_01_opener",
        "beat_04_case",
    ]
    narrative = read_json(run_dir / "narrative_plan.json")
    assert [beat["beat_id"] for beat in narrative["beats"]] == [
        "beat_03_solution",
        "beat_01_opener",
        "beat_04_case",
    ]
    assert narrative["target_pages"] == 3
    tasks = read_json(run_dir / "page_tasks.json")["tasks"]
    assert [task["order"] for task in tasks] == [1, 2, 3]
    # page identity survived: beat_01 keeps its original page_id from v1
    kept = read_json(run_dir / "page_packages" / "beat_01_opener.json")
    assert kept["page_id"] == "beat_01_opener"
    backup = Path(result["backup_dir"])
    assert (backup / "page_packages" / "beat_02_problem.json").exists()


def test_interrupted_import_restores_previous_state(tmp_path: Path, monkeypatch) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    import_plan(run_dir, _write_input(tmp_path, _full_draft(beats, packages), name="v1.json"), source="agent")
    v1_narrative = read_json(run_dir / "narrative_plan.json")

    v2_beats = [_beat(1, "opener"), _beat(2, "problem")]
    v2_packages = [
        _package("beat_01_opener", "开场标题", "开场正文"),
        _package("beat_02_problem", "问题标题", "问题正文"),
    ]

    import runtime.orchestration as orchestration_module

    real_write_json = orchestration_module.write_json

    def failing_write_json(path, payload):
        if Path(path).name == "page_tasks.json" and not getattr(failing_write_json, "armed_done", False):
            failing_write_json.armed_done = True
            raise RuntimeError("simulated crash between writes")
        return real_write_json(path, payload)

    monkeypatch.setattr(orchestration_module, "write_json", failing_write_json)

    with pytest.raises(RuntimeError, match="simulated crash"):
        import_plan(run_dir, _write_input(tmp_path, _full_draft(v2_beats, v2_packages), name="v2.json"), source="agent")

    monkeypatch.undo()
    assert read_json(run_dir / "narrative_plan.json") == v1_narrative
    assert _package_files(run_dir) == {
        "beat_01_opener.json",
        "beat_02_problem.json",
        "beat_03_solution.json",
    }
    index = read_json(run_dir / "page_packages" / "index.json")
    assert index["page_count"] == 3

    recovery = import_plan(run_dir, _write_input(tmp_path, _full_draft(v2_beats, v2_packages), name="v2.json"), source="agent")
    assert recovery["mode"] == "full_draft"
    assert _package_files(run_dir) == {"beat_01_opener.json", "beat_02_problem.json"}


def test_downstream_pruned_on_delete_and_change(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    import_plan(run_dir, _write_input(tmp_path, _full_draft(beats, packages), name="v1.json"), source="agent")
    write_json(
        run_dir / "sourcing_plan.json",
        {
            "run_id": "full-draft-run",
            "pages": [
                {"page_id": "beat_01_opener", "beat_id": "beat_01_opener", "decision": "generate"},
                {"page_id": "beat_02_problem", "beat_id": "beat_02_problem", "decision": "generate"},
                {"page_id": "beat_03_solution", "beat_id": "beat_03_solution", "decision": "generate"},
            ],
        },
    )
    write_json(
        run_dir / "preview_manifest.json",
        {
            "run_id": "full-draft-run",
            "pages": [
                {"page_id": "beat_01_opener", "beat_id": "beat_01_opener", "order": 1},
                {"page_id": "beat_02_problem", "beat_id": "beat_02_problem", "order": 2},
                {"page_id": "beat_03_solution", "beat_id": "beat_03_solution", "order": 3},
            ],
        },
    )

    v2_beats = [_beat(1, "opener"), _beat(3, "solution")]
    v2_packages = [
        _package("beat_01_opener", "开场标题", "开场正文"),
        _package("beat_03_solution", "方案标题改", "方案正文改"),
    ]
    result = import_plan(run_dir, _write_input(tmp_path, _full_draft(v2_beats, v2_packages), name="v2.json"), source="agent")

    assert result["changed_pages"] == ["beat_03_solution"]
    assert result["downstream"].get("sourcing_plan.json") == "pruned"
    sourcing = read_json(run_dir / "sourcing_plan.json")
    assert [page["page_id"] for page in sourcing["pages"]] == ["beat_01_opener"]
    preview = read_json(run_dir / "preview_manifest.json")
    assert [page["page_id"] for page in preview["pages"]] == ["beat_01_opener"]


def test_stage_fast_path_drives_package_run_to_build(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    for name in ("context_manifest.json", "deck_brief.json", "claim_map.json"):
        write_json(run_dir / name, {})
    beats, packages = _draft_v1()
    import_plan(run_dir, _write_input(tmp_path, _full_draft(beats, packages)), source="agent")

    state = resolve_run_state(run_dir, run_mode="fixture")

    assert state["stage"] == "needs_build"
    assert "--profile high-density" in state["next_command"]

    # A deleted package file must block production instead of rebuilding the
    # deliverable without the page.
    (run_dir / "page_packages" / "beat_02_problem.json").unlink()
    blocked = resolve_run_state(run_dir, run_mode="fixture")
    assert blocked["stage"] == "blocked_packages"
    assert "re-import the full draft" in blocked["next_command"] or any(
        "page packages are missing" in entry.get("reason", "") for entry in blocked["blocked_actions"]
    )


def test_legacy_pipeline_unaffected_without_packages(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    for name in ("context_manifest.json", "deck_brief.json", "claim_map.json"):
        write_json(run_dir / name, {})
    beats, _ = _draft_v1()
    write_json(
        run_dir / "narrative_plan.json",
        {"run_id": "full-draft-run", "title": "Plan only", "target_pages": 3, "density": "high", "beats": beats},
    )
    write_json(run_dir / "page_tasks.json", {"run_id": "full-draft-run", "tasks": []})

    state = resolve_run_state(run_dir, run_mode="fixture")

    assert state["stage"] == "needs_sourcing"


def test_build_manifest_v2_carries_imported_content(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    beats, packages = _draft_v1()
    import_plan(run_dir, _write_input(tmp_path, _full_draft(beats, packages)), source="agent")

    from build.manifest import package_sha256, whitelist_project
    from production.page_package import PagePackageIndex

    loaded = PagePackageIndex(run_dir).list_packages()
    manifest = build_manifest_v2(
        run_id="full-draft-run",
        packages=loaded,
        builder_backend=BACKEND_OK,
        output_profile="production_pptx",
        builder_profile="high_density",
    )
    assert [page["order"] for page in manifest["pages"]] == [1, 2, 3]
    assert manifest["pages"][0]["page_id"] == "beat_01_opener"
    # The build input is bound to the exact imported package file, and the
    # received body text is part of the customer payload projection — not just
    # an "imported" status.
    changed_package = read_json(run_dir / "page_packages" / "beat_03_solution.json")
    assert manifest["pages"][2]["page_package_sha256"] == package_sha256(changed_package)
    projected = whitelist_project(changed_package)
    assert projected["customer_visible"]["title"] == "方案标题"
    assert any("方案正文" in str(block) for block in projected["customer_visible"]["body_blocks"])
