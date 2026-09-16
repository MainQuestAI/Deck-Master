"""Real CLI acceptance chain (review-repair verification, 2026-09-16).

Drives the rebuilt core through its public CLI exactly as a Host would:
create → continue → task start → task accept (compose envelope) →
view --open with a detached service that outlives the CLI → continue
without re-composing. Both draft import entries are covered. Exit codes
follow spec 09.3.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from deck_master.cli import main as cli_main

REPO = Path(__file__).resolve().parents[2]
ENVELOPE = REPO / "docs" / "specs" / "deck-master-rebuild-v1" / "examples" / "roundtrips" / "result-envelope" / "compose.json"


def cli_main(argv: list[str]) -> int:
    """Run one CLI command in-process and return its exit code."""
    from deck_master.cli import main

    return main(argv)


def _material(tmp_path: Path) -> Path:
    material = tmp_path / "materials" / "brief.txt"
    material.parent.mkdir()
    material.write_text(
        "## 任务\n向运营团队说明条件自动处理方案。\n\n"
        "（材料尾部约束）合成材料，不可回写。",
        encoding="utf-8",
    )
    return material


def _draft_payload() -> dict:
    return {
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


def test_full_cli_chain_create_start_accept_view_continue(tmp_path: Path) -> None:
    """创建 → 领取 → 接收完整稿 → 打开且持续访问工作台 → continue 不重复成稿."""
    project = tmp_path / "proj"
    material = _material(tmp_path)

    assert cli_main(["create", "--brief", "说明条件自动处理方案", "--source", str(material), "--out", str(project)]) == 0

    assert cli_main(["continue", "--project", str(project)]) == 0
    from deck_master.service import continue_project

    pending = continue_project(project)["pending_tasks"]
    assert pending, "continue must hand the Host a pending task"
    task_id = pending[0]["task_id"]
    operation_id = pending[0]["operation_id"]
    produced_against = pending[0]["produced_against"]

    assert cli_main(["task", "start", "--project", str(project), "--task-id", task_id, "--execution-ref", "exec-real-1"]) == 0
    assert cli_main([
        "task", "accept",
        "--project", str(project),
        "--task-id", task_id,
        "--operation-id", operation_id,
        "--produced-against", produced_against,
        "--result", str(ENVELOPE),
    ]) == 0

    document = _read_document(project)
    assert [entry["page_id"] for entry in document["pages"]] == ["p09"]

    # Workbench opens with a detached service that keeps serving.
    from deck_master.web import ensure_service, stop_service

    state = ensure_service(project)
    url = state["url"]
    assert state["reused"] is False
    with urllib.request.urlopen(url.rstrip("/") + "/api/view", timeout=5) as response:
        view = json.loads(response.read().decode("utf-8"))
    assert view["page_count"] == 1
    assert view["pages"][0]["slots"]["content"]["path"].startswith(".deckmaster/objects/")

    # Reuse: a second ensure_service returns the same healthy URL.
    again = ensure_service(project)
    assert again["reused"] is True
    assert again["url"] == url

    # continue after adoption must dispatch blueprint, not re-open compose.
    from deck_master.service import continue_project

    follow_up = continue_project(project)
    assert follow_up["status"] == "awaiting_host"
    assert follow_up["pending_tasks"][0]["kind"] == "blueprint"
    assert follow_up["next_action"] == "codex_generate_blueprint"

    stop_service(project)


def test_import_draft_cli_entry(tmp_path: Path) -> None:
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps(_draft_payload(), ensure_ascii=False), encoding="utf-8")
    project = tmp_path / "proj-draft"
    assert cli_main(["import-draft", "--project", str(project), "--input", str(draft_file)]) == 0
    view = _load_view(project)
    assert view["page_count"] == 1
    assert view["pages"][0]["page_id"] == "d1"
    from deck_master.service import continue_project

    follow_up = continue_project(project)
    assert follow_up["status"] == "awaiting_host"
    assert follow_up["next_action"] == "codex_generate_blueprint"


def test_create_with_draft_adopts_pages(tmp_path: Path) -> None:
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps(_draft_payload(), ensure_ascii=False), encoding="utf-8")
    project = tmp_path / "proj-draft2"
    assert cli_main([
        "create", "--brief", "带稿创建", "--draft", str(draft_file), "--out", str(project)
    ]) == 0
    view = _load_view(project)
    assert view["page_count"] == 1
    from deck_master.service import continue_project

    follow_up = continue_project(project)
    assert follow_up["status"] == "awaiting_host"
    assert follow_up["next_action"] == "codex_generate_blueprint"


def test_invalid_result_json_exits_2(tmp_path: Path) -> None:
    from deck_master.service import continue_project

    project = tmp_path / "proj"
    material = _material(tmp_path)
    cli_main(["create", "--brief", "简报", "--source", str(material), "--out", str(project)])
    pending = continue_project(project)["pending_tasks"]
    assert pending, "continue must hand the Host a pending task"
    task_id = pending[0]["task_id"]
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    code = cli_main([
        "task", "accept",
        "--project", str(project),
        "--task-id", task_id,
        "--operation-id", pending[0]["operation_id"],
        "--produced-against", pending[0]["produced_against"],
        "--result", str(bad),
    ])
    assert code == 2, "unreadable JSON must map to exit code 2, not a traceback"


def _load_view(project: Path) -> dict:
    from deck_master.view import project_view

    return project_view(project)


def _read_document(project: Path) -> dict:
    from deck_master.store import Store

    return Store(project).load_document()


def _read_view(project: Path) -> dict:
    return _load_view(project)
