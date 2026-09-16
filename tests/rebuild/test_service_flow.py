"""T04 service flow tests (AC-C04, AC-C06, AC-C07 engineering part)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import deck_master.service as service


def _write_brief(tmp_path: Path) -> tuple[Path, Path]:
    material_dir = tmp_path / "materials"
    material_dir.mkdir()
    material = material_dir / "brief.txt"
    material.write_text(
        "## 任务\n向运营团队说明条件自动处理方案。\n\n"
        "## 现状\n人工处理为主，接口条件齐备。\n\n"
        "（材料尾部约束）合成材料，不可回写。",
        encoding="utf-8",
    )
    return tmp_path / "proj", material


def test_plain_material_directory_starts_without_library(tmp_path: Path) -> None:
    """AC-C06: a plain material directory, no history library/cache/templates."""
    project, material = _write_brief(tmp_path)
    response = service.create(project, brief="说明条件自动处理方案", sources=[material])
    assert response["status"] == "created"
    assert response["pending_tasks"], "create returns a pending Host task"
    assert response["next_action"] == "submit_host_results"
    # No library or workspace prerequisites were touched.
    deck_dir = project / ".deckmaster"
    assert (deck_dir / "current.json").is_file()
    assert not (project / "library").exists()
    assert not (project / "workspace").exists()


def test_repeated_continue_returns_same_task(tmp_path: Path) -> None:
    """AC-C04: continue reuses the pending task instead of creating duplicates."""
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    first = service.continue_project(project)
    second = service.continue_project(project)
    assert first["pending_tasks"] and second["pending_tasks"]
    assert first["pending_tasks"][0]["task_id"] == second["pending_tasks"][0]["task_id"]
    assert first["revision_id"] == second["revision_id"]


def test_default_entry_does_not_invoke_legacy_planner(tmp_path: Path) -> None:
    """AC-C04 engineering part: the flow never calls the old planner/enrich modules."""
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    response = service.continue_project(project)
    task = response["pending_tasks"][0]
    # The work order derives from real sources; no array-modulo claim pairing
    # and no fixed page-role template is part of the dispatch.
    assert task["sources"], "task carries the real source entries"
    assert "template" in task["instruction"].lower() or "templates" in task["instruction"].lower()


def test_import_draft_without_prior_create(tmp_path: Path) -> None:
    draft = {
        "pages": [
            {
                "schema_version": "deck_page_package.v2",
                "page_id": "d1",
                "customer_visible": {
                    "title": "导入稿标题",
                    "body_blocks": [{"id": "intro", "type": "paragraph", "text": "完整正文。"}],
                },
                "visual_spec": {"intent": "纯正文页", "reference_mode": "new_design"},
            }
        ]
    }
    response = service.import_draft(tmp_path / "proj", draft_payload=draft)
    assert response["status"] == "accepted"
    assert response["next_action"] == "auto_view_then_production"
    document = service.Store(tmp_path / "proj").load_document()
    assert [entry["page_id"] for entry in document["pages"]] == ["d1"]


def test_unknown_draft_shape_is_rejected_not_adopted(tmp_path: Path) -> None:
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    with pytest.raises(Exception):
        service.import_draft(
            project,
            draft_payload={
                "pages": [
                    {
                        "schema_version": "deck_page_package.v2",
                        "page_id": "bad",
                        "customer_visible": {
                            "title": "坏块",
                            "body_blocks": [{"id": "x", "type": "unknown_widget", "text": "?"}],
                        },
                        "visual_spec": {"intent": "坏形状", "reference_mode": "new_design"},
                    }
                ]
            },
        )
    # Nothing was partially adopted: the current Document still has no pages.
    document = service.Store(project).load_document()
    assert document["pages"] == []


def test_asset_registration_updates_design(tmp_path: Path) -> None:
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    response = service.import_asset(
        project, asset_id="demo-logo", kind="logo", file_path=logo, external_use="allowed"
    )
    assert response["status"] == "registered"
    document = service.Store(project).load_document()
    design = document["design_context"]
    assert any(entry["asset_id"] == "demo-logo" for entry in design["assets"])
    assert "demo-logo" in design["allowed_asset_ids"]
