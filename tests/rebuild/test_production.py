"""T06 prompt projection and Codex blueprint dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from deck_master import service
from deck_master import tasks as tasks_mod
from deck_master.models import default_design_context
from deck_master.production import project_prompt

SPEC = Path(__file__).resolve().parents[2] / "docs/specs/deck-master-rebuild-v1"
COMPOSE = SPEC / "examples/roundtrips/result-envelope/compose.json"


def _page() -> dict:
    return json.loads(COMPOSE.read_text("utf-8"))["pages"][0]


def test_prompt_projects_all_visible_fields_and_excludes_internal_notes() -> None:
    design = default_design_context()
    request = project_prompt(_page(), design, [])
    prompt = request["prompt"]
    for marker in (
        "将设备条件收集前移",
        "建议在现有售后门户嵌入",
        "填写设备型号与问题现象",
        "120条",
        "45%",
        "本期只读接口",
        "54÷120=45%",
        "先改变信息收集环节",
        "提交完整设备条件",
        "转交需进一步判断的问题",
    ):
        assert marker in prompt
    assert "不要把这一段加入图中" not in prompt
    assert "所有企业与数字均为合成输入" not in prompt


def test_only_allowed_assets_enter_prompt() -> None:
    design = default_design_context()
    design["allowed_asset_ids"] = ["brand-logo"]
    permitted = [
        {"asset_id": "brand-logo", "kind": "logo", "external_use": "allowed"},
        {"asset_id": "private-photo", "kind": "image", "external_use": "forbidden"},
    ]
    request = project_prompt(_page(), design, permitted)
    assets = request["projection"]["permitted_assets"]
    assert [asset["asset_id"] for asset in assets] == ["brand-logo"]
    assert "private-photo" not in request["prompt"]


def test_blueprint_task_exposes_only_allowed_asset_bytes(tmp_path: Path) -> None:
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='80' height='20'/>")
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.create(
        project,
        brief="brand test",
        draft=draft,
        design={
            "assets": [
                {"asset_id": "brand-logo", "kind": "logo", "file": str(logo), "external_use": "allowed"}
            ],
            "allowed_asset_ids": ["brand-logo"],
        },
    )
    task = service.continue_project(project)["pending_tasks"][0]
    files = task["production_request"]["permitted_asset_files"]
    assert len(files) == 1
    assert files[0]["asset_id"] == "brand-logo"
    assert files[0]["media_type"] == "image/svg+xml"
    assert files[0]["file"]["path"].startswith(".deckmaster/objects/")


def test_continue_dispatches_one_codex_blueprint_with_allowance(tmp_path: Path) -> None:
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.import_draft(project, draft_payload=draft)
    response = service.continue_project(project)
    assert response["status"] == "awaiting_host"
    assert response["next_action"] == "codex_generate_blueprint"
    assert len(response["pending_tasks"]) == 1
    task = response["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    assert task["scope_pages"] == ["p09"]
    assert task["production_request"]["host"] == "codex_imagegen"
    assert task["call_allowances"][0]["state"] == "reserved"

    repeated = service.continue_project(project)
    assert repeated["pending_tasks"][0]["task_id"] == task["task_id"]


def test_prompt_is_stable_and_page_specific() -> None:
    design = default_design_context()
    first = project_prompt(_page(), design, [])
    changed = _page()
    changed["customer_visible"]["title"] = "另一页的独立标题"
    second = project_prompt(changed, design, [])
    assert first["prompt_sha256"] != second["prompt_sha256"]
    assert first == project_prompt(_page(), design, [])


def test_settle_records_invocation_ref_and_can_enrich_old_consumed_fact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.import_draft(project, draft_payload=draft)
    task = service.continue_project(project)["pending_tasks"][0]
    store = service.Store(project)
    service.task_start(project, task_id=task["task_id"], execution_ref="codex-test")
    tasks_mod.call_begin(
        store, task_id=task["task_id"], allowance_id="call-1", execution_ref="codex-test"
    )
    tasks_mod.call_settle(
        store,
        task_id=task["task_id"],
        allowance_id="call-1",
        outcome="consumed",
        report_bytes=b"{}",
        invocation_ref="exec-test-1",
    )
    current = store.load_document()
    saved = tasks_mod._lookup_task(current, task["task_id"], store)
    assert saved["call_allowances"][0]["invocation_ref"] == "exec-test-1"


def test_call_operation_ids_include_task_identity(tmp_path: Path) -> None:
    """Two pages/tasks may both own call-1 without transaction collisions."""
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.import_draft(project, draft_payload=draft)
    first = service.continue_project(project)["pending_tasks"][0]
    store = service.Store(project)
    service.task_start(project, task_id=first["task_id"], execution_ref="exec-1")
    tasks_mod.call_begin(store, task_id=first["task_id"], allowance_id="call-1", execution_ref="exec-1")
    tasks_mod.call_settle(
        store, task_id=first["task_id"], allowance_id="call-1", outcome="consumed",
        report_bytes=b"{}", invocation_ref="inv-1"
    )
    service.task_cancel(project, task_id=first["task_id"])
    # A second task deliberately reuses the allowance's local name.
    document = store.load_document()
    page_entry = document["pages"][0]
    second_obj = service.open_blueprint_task(store, document, page_entry)
    service.task_start(project, task_id=second_obj["task_id"], execution_ref="exec-2")
    tasks_mod.call_begin(store, task_id=second_obj["task_id"], allowance_id="call-1", execution_ref="exec-2")
    result = tasks_mod.call_settle(
        store, task_id=second_obj["task_id"], allowance_id="call-1", outcome="consumed",
        report_bytes=b"{}", invocation_ref="inv-2"
    )
    assert result["status"] == "settled"
