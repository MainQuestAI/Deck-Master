"""W02 ContentPlan behavior. All material and content in this file are synthetic."""
import copy
import json
import urllib.request

import pytest

from deck_master import cli, content_plan, editing, generation, service, tasks, workbench
from deck_master.models import ModelError, bump_revision, content_identity, validate_schema
from deck_master.store import Store
from deck_master.web import WorkbenchServer


def page(pid, title):
    return {"schema_version": "deck_page_package.v2", "page_id": pid,
            "customer_visible": {"title": title, "body_blocks": []},
            "visual_spec": {"intent": "Synthetic test", "reference_mode": "new_design"}}


@pytest.fixture
def flow(tmp_path):
    source = tmp_path / "facts.md"
    source.write_text("# 合成材料\n测试流程有三个步骤。\n")
    project = tmp_path / "project"
    response = service.create(project, brief="说明合成流程和待确认事项", sources=[source], project_format="workbench.v3")
    task = response["pending_tasks"][0]
    source_binding = task["content_plan_contract"]["sources"][0]
    plan = {"schema_version": "content_plan_input.v1", "input_summary": "材料说明三个步骤，成效尚无数据。",
            "chapters": [{"chapter_id": "chapter-flow", "title": "流程与待确认项", "goal_ids": ["goal-process", "goal-evidence"]}],
            "goals": [{"goal_id": "goal-process", "page_id": "p1", "purpose": "解释三个步骤",
                       "source_links": [{**source_binding, "locator": "L2"}], "unresolved_facts": []},
                      {"goal_id": "goal-evidence", "page_id": "p2", "purpose": "说明需要验证的成效",
                       "source_links": [], "unresolved_facts": ["材料未提供成效数据，不能承诺提升比例。"]}],
            "unresolved_facts": ["成效指标待实际验证。"]}
    envelope = {"kind": "compose", "pages": [page("p1", "三个步骤"), page("p2", "成效待验证")],
                "page_order": ["p1", "p2"], "content_plan": plan}
    return project, Store(project), task, envelope


def start(project, task):
    return service.task_start(project, task_id=task["task_id"], execution_ref="test-compose",
                              supported_protocols=[content_plan.PROTOCOL], capabilities=content_plan.CAPABILITIES)


def accept(project, task, envelope):
    return service.accept_result(project, result_payload=envelope,
                                 **{k: task[k] for k in ("task_id", "operation_id", "produced_against")})


def test_compose_requires_capabilities_and_plan_before_any_page_is_adopted(flow):
    project, store, task, envelope = flow
    before = store.current_revision_id()
    with pytest.raises(generation.GenerationError, match="requires compose.v1"):
        start_args = dict(task_id=task["task_id"], execution_ref="old-host")
        service.task_start(project, **start_args)
    with pytest.raises(generation.GenerationError):
        accept(project, task, envelope)
    assert store.current_revision_id() == before
    start(project, task)
    before = store.current_revision_id()
    with pytest.raises(content_plan.ContentPlanError, match="requires a content_plan"):
        accept(project, task, {k: v for k, v in envelope.items() if k != "content_plan"})
    assert store.current_revision_id() == before and store.load_document()["pages"] == []


@pytest.mark.parametrize("invalid", ["source", "version", "locator", "page", "goal", "chapter", "missing_basis", "blank_basis", "duplicate_body"])
def test_invalid_plan_is_refused_atomically(flow, invalid):
    project, store, task, envelope = flow
    start(project, task)
    before = store.current_revision_id()
    plan = envelope["content_plan"]
    link = plan["goals"][0]["source_links"][0]
    if invalid == "source":
        link["source_id"] = "not-selected"
    elif invalid == "version":
        link["source_version"]["original_sha256"] = "a" * 64
    elif invalid == "locator":
        link["locator"] = "L999"
    elif invalid == "page":
        plan["goals"][0]["page_id"] = "not-a-page"
    elif invalid == "goal":
        plan["goals"][1]["goal_id"] = plan["goals"][0]["goal_id"]
    elif invalid == "chapter":
        plan["chapters"][0]["goal_ids"] = ["goal-process"]
    elif invalid == "missing_basis":
        plan["goals"][1]["unresolved_facts"] = []
    elif invalid == "blank_basis":
        plan["goals"][1]["unresolved_facts"] = [" \n "]
    else:
        plan["goals"][0]["body_blocks"] = []
    with pytest.raises((content_plan.ContentPlanError, ModelError)):
        accept(project, task, envelope)
    assert store.current_revision_id() == before
    assert store.load_document()["pages"] == []


def test_plan_page_source_navigation_survives_lost_ack_and_later_edits(flow, monkeypatch):
    project, store, task, envelope = flow
    start(project, task)
    write_journal = tasks.write_operation_journal
    def lose_ack(*args, **kwargs):
        raise SystemExit("lost response after pointer swap")
    monkeypatch.setattr(tasks, "write_operation_journal", lose_ack)
    with pytest.raises(SystemExit):
        accept(project, task, envelope)
    adopted = store.load_document()
    plan_ref = adopted["content_plan"]
    stored = store.read_object_json(plan_ref)
    validate_schema("content_plan", stored)
    assert stored["origin"] == "host_composed" and stored["version"] == 1
    assert stored["page_links"][0]["page_ref"] == adopted["pages"][0]["page"]
    assert plan_ref in tasks._lookup_task(adopted, task["task_id"], store)["result_refs"]
    fixed = content_plan.show(project, revision=adopted["revision_id"])
    assert fixed["content_plan"]["goals"][0]["source_links"][0]["relation"] == "current"
    assert fixed["content_plan"]["goals"][1]["unresolved_facts"]
    updated = copy.deepcopy(envelope["pages"][0])
    updated["customer_visible"]["title"] = "更新后的步骤"
    editing.edit_page(project, page=updated, base_revision=adopted["revision_id"],
                      page_hash=adopted["pages"][0]["page"]["sha256"], operation_id="edit-title")
    current = store.current_revision_id()
    monkeypatch.setattr(tasks, "write_operation_journal", write_journal)
    replay = accept(project, task, envelope)
    assert replay["status"] == "already_applied" and plan_ref in replay["result_refs"]
    assert store.current_revision_id() == current
    assert content_plan.show(project, revision=adopted["revision_id"]) == fixed
    assert content_plan.show(project)["content_plan"]["applicability"] == "basis_changed"
    lineage = workbench.page_lineage(project, "p1")["content_plan"]
    assert [g["goal_id"] for g in lineage["goals"]] == ["goal-process"]
    assert lineage["goals"][0]["page_ref"] == adopted["pages"][0]["page"]
    assert "input_summary" not in workbench.workbench_summary(project)["content_plan"]


def test_input_revision_advances_plan_with_unchanged_page_refs_and_stable_goal_ids(flow):
    project, store, task, envelope = flow
    start(project, task)
    accept(project, task, envelope)
    first = store.load_document()
    updated = service.inputs_update(project, patch={"task_patch": {"audience": "新受众"}, "reason": "补充受众"},
                                     base_revision=first["revision_id"], operation_id="audience")
    new_task = next(t for t in updated["pending_tasks"] if t["kind"] == "compose")
    assert new_task["protocol_version"] == "compose.v1" and new_task["intent"] == "input_revision"
    start(project, new_task)
    plan = copy.deepcopy(envelope["content_plan"])
    plan["input_summary"] += "新受众不影响两页的已有事实。"
    payload = {"kind": "compose", "content_update": {"input_digest": new_task["project_context"]["input_digest"],
               "page_order": ["p1", "p2"], "unchanged_reason": "受众变化不改变当前步骤与缺口说明"}, "content_plan": plan}
    before = store.current_revision_id()
    bad = copy.deepcopy(payload)
    bad["content_plan"]["goals"][0]["goal_id"] = "renamed-goal"
    bad["content_plan"]["chapters"][0]["goal_ids"][0] = "renamed-goal"
    with pytest.raises(content_plan.ContentPlanError, match="preserve the goal"):
        accept(project, new_task, bad)
    assert store.current_revision_id() == before
    accept(project, new_task, payload)
    second = store.load_document()
    plan2 = store.read_object_json(second["content_plan"])
    assert plan2["previous_ref"] == first["content_plan"] and plan2["version"] == 2
    assert second["pages"] == first["pages"]
    assert content_plan.show(project)["content_plan"]["applicability"] == "current"
    assert content_identity(second) != content_identity(first)


def test_source_replacement_marks_old_link_without_rewriting_historical_plan(flow, tmp_path):
    project, store, task, envelope = flow
    start(project, task)
    accept(project, task, envelope)
    first = store.load_document()
    before = content_plan.show(project, revision=first["revision_id"])
    replacement = tmp_path / "new-facts.md"
    replacement.write_text("测试流程现在有四个步骤。")
    service.inputs_update(project, patch={"source_changes": {"replace": [{"source_id": first["sources"][0]["source_id"],
                          "path": str(replacement)}]}, "reason": "更新材料"}, base_revision=first["revision_id"], operation_id="new-facts")
    shown = content_plan.show(project)["content_plan"]
    assert shown["applicability"] == "basis_changed"
    assert shown["goals"][0]["source_links"][0]["relation"] == "version_changed"
    assert content_plan.show(project, revision=first["revision_id"]) == before


def test_outline_change_invalidates_compose_even_when_pages_are_unchanged(flow):
    project, store, task, envelope = flow
    start(project, task)
    accept(project, task, envelope)
    first = store.load_document()
    changed = service.inputs_update(project, patch={"task_patch": {"audience": "新受众"}, "reason": "新的说明对象"},
                                     base_revision=first["revision_id"], operation_id="new-audience")
    pending = next(t for t in changed["pending_tasks"] if t["kind"] == "compose")
    current = store.load_document()
    raw_task = tasks._lookup_task(current, pending["task_id"], store)
    assert tasks.task_inputs_current(store, current, raw_task)
    other = store.read_object_json(current["content_plan"])
    other["input"]["input_summary"] = "另一个执行者已修订大纲。"
    moved = bump_revision(current, {"operation_id": "synthetic-plan-change", "kind": "content_update", "description": "test interleaving", "read_set": []})
    moved["content_plan"] = store.put_json_object(other)
    store.commit_change(base_revision=current["revision_id"], document=moved, operation_id="synthetic-plan-change")
    assert not tasks.task_inputs_current(store, store.load_document(), raw_task)


def test_page_reorder_marks_old_plan_stale(flow):
    project, store, task, envelope = flow
    envelope["page_order"] = ["p2", "p1"]
    start(project, task)
    accept(project, task, envelope)
    first = store.load_document()
    plan = store.read_object_json(first["content_plan"])
    assert [p["page_id"] for p in plan["page_links"]] == ["p2", "p1"]
    assert content_plan.show(project)["content_plan"]["applicability"] == "current"
    moved = bump_revision(first, {"operation_id": "synthetic-reorder", "kind": "content_update", "description": "test reorder", "read_set": []})
    moved["pages"].reverse()
    store.commit_change(base_revision=first["revision_id"], document=moved, operation_id="synthetic-reorder")
    assert content_plan.show(project)["content_plan"]["applicability"] == "basis_changed"


def test_legacy_and_imported_drafts_have_labeled_unwritten_outline(tmp_path):
    for fmt in (None, "workbench.v3"):
        project = tmp_path / ("old" if fmt is None else "new")
        service.create(project, brief="Synthetic", draft={"pages": [page("p1", "已有正文")]}, project_format=fmt)
        store = Store(project)
        before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        result = content_plan.show(project)["content_plan"]
        assert result["status"] == result["relation"] == "derived" and result["ref"] is None
        assert result["goals"][0]["title"] == "已有正文" and result["goals"][0]["goal_id"] is None
        assert "content_plan" not in store.load_document()
        assert before == {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}


def test_explicit_imported_plan_is_adopted_and_restore_does_not_keep_the_wrong_plan(flow):
    project, store, task, envelope = flow
    empty_revision = store.current_revision_id()
    service.import_draft(project, draft_payload={"pages": envelope["pages"], "content_plan": envelope["content_plan"]})
    first = store.load_document()
    assert store.read_object_json(first["content_plan"])["origin"] == "user_imported"
    editing.restore(project, revision_id=empty_revision, base_revision=first["revision_id"], operation_id="restore-empty")
    assert "content_plan" not in store.load_document()
    assert json.loads((store.deck_root / "current.json").read_text())["minimum_writer"] == "content-plan.v1"
    assert content_plan.show(project, revision=first["revision_id"])["content_plan"]["status"] == "recorded"


def test_cli_http_fixed_content_plan_and_corrupt_plan_are_local(flow, capsys):
    project, store, task, envelope = flow
    start(project, task)
    accept(project, task, envelope)
    revision = store.current_revision_id()
    expected = content_plan.show(project, revision=revision)
    assert cli.main(["view", "--project", str(project), "--content-plan", "--revision", revision]) == 0
    assert json.loads(capsys.readouterr().out) == expected
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        with urllib.request.urlopen(url + "/api/content-plan?revision=" + revision) as response:
            assert json.loads(response.read()) == expected
    finally:
        server.stop()
    plan_path = store.project_root / store.load_document()["content_plan"]["path"]
    plan_path.write_text("broken")
    assert content_plan.show(project)["content_plan"]["status"] == "unreadable"
    assert workbench.workbench_summary(project)["page_count"] == 2
    assert workbench.page_lineage(project, "p1")["page"]["customer_visible"]["title"] == "三个步骤"
