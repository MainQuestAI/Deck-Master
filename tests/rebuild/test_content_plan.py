"""W02 ContentPlan behavior. All material and content in this file are synthetic."""
import copy
import json
import urllib.request
import uuid

import pytest

from deck_master import cli, content_plan, editing, generation, service, tasks, workbench
from deck_master.models import ModelError, bump_revision, content_identity, validate_schema
from deck_master.store import Store
from rc3_fixtures import historical_snapshot, claim_fixture_task
from test_content_ops import v2_revision_envelope
from test_compose_v2_phases import (_accept_argument, _adopt_direction, _plan_input, _source_link, _submit, _framing_narrative)
from deck_master import content_production
from deck_master.content import atom_ids
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
    store = Store(project)
    framing = response['pending_tasks'][0]
    claim_fixture_task(project, framing)
    _submit(project, framing, {'narrative': _framing_narrative(store.load_document()['project_id'])}, 'framing')
    _, argument = _accept_argument(project, store)
    _adopt_direction(project, store, argument['result_refs'][0])
    task = content_production.open_phase_task(store, store.load_document(),
        operation_id='L1-initial-pages', phase='page_copy')
    doc = store.load_document()
    plan = _plan_input(doc, ['p1', 'p2'])
    plan['page_roles'][0]['role'] = '解释三个步骤'
    plan['page_roles'][0]['source_links'] = [_source_link(store, doc, 'L2')]
    plan['page_roles'][1]['role'] = '说明需要验证的成效；材料没有成效数据'
    pages = [page('p1', '三个步骤'), page('p2', '成效待验证')]
    for item in pages:
        item['content_mapping'] = {'narrative_ref': doc['narrative'], 'plan_role_page_id': item['page_id'],
            'visible_links': [{'element_ref': atom, 'narrative_node_ids': ['n1'], 'source_links': []}
                              for atom in sorted(atom_ids(item))], 'speech_segments': []}
    envelope = {'kind': 'compose', 'pages': pages, 'page_order': ['p1', 'p2'], 'content_plan': plan}
    return project, Store(project), task, envelope


def start(project, task):
    return claim_fixture_task(project, task, execution_ref='L1-plan-author')


def accept(project, task, envelope):
    store = Store(project)
    if task.get('intent') == 'input_revision':
        value = v2_revision_envelope(store, task, envelope)
    else:
        payload = {'pages': envelope['pages'], 'page_order': envelope['page_order']}
        if 'content_plan' in envelope:
            payload['plan_input'] = envelope['content_plan']
        value = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'page_copy',
            **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')},
            'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
            'payload': payload, 'usage_events': []}
    return service.accept_result(project, result_payload=value,
                                 **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')})


def test_compose_requires_capabilities_and_plan_before_any_page_is_adopted(flow):
    project, store, task, envelope = flow
    before = store.current_revision_id()
    with pytest.raises(generation.GenerationError, match="requires compose.v2"):
        start_args = dict(task_id=task["task_id"], execution_ref="old-host")
        service.task_start(project, **start_args)
    with pytest.raises(tasks.TaskConflict, match="claim"):
        accept(project, task, envelope)
    assert store.current_revision_id() == before
    start(project, task)
    before = store.current_revision_id()
    with pytest.raises(tasks.EnvelopeError, match="plan_input"):
        accept(project, task, {k: v for k, v in envelope.items() if k != "content_plan"})
    assert store.current_revision_id() == before and store.load_document()["pages"] == []


@pytest.mark.parametrize("invalid", ["source", "version", "locator", "page", "goal", "chapter", "missing_basis", "blank_basis", "duplicate_body"])
def test_invalid_plan_is_refused_atomically(flow, invalid):
    project, store, task, envelope = flow
    start(project, task)
    before = store.current_revision_id()
    plan = envelope["content_plan"]
    link = plan["page_roles"][0]["source_links"][0]
    if invalid == "source":
        link["source_id"] = "not-selected"
    elif invalid == "version":
        link["source_version"]["original_sha256"] = "a" * 64
    elif invalid == "locator":
        link["locator"] = "L999"
    elif invalid == "page":
        plan["page_roles"][0]["page_id"] = "not-a-page"
    elif invalid == "goal":
        plan["page_roles"][1]["page_id"] = plan["page_roles"][0]["page_id"]
    elif invalid == "chapter":
        plan["chapters"][0]["page_ids"] = ["p1"]
    elif invalid == "missing_basis":
        plan["page_roles"][1]["narrative_node_ids"] = ["missing-node"]
    elif invalid == "blank_basis":
        plan["page_roles"][1]["source_links"] = [{**link, "locator": " \n "}]
    else:
        plan["page_roles"][0]["body_blocks"] = []
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
    assert "没有成效数据" in fixed["content_plan"]["page_roles"][1]["role"]
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
    assert content_plan.show(project)['content_plan']['applicability'] == 'current'
    fresh_plan = store.read_object_json(store.load_document()['content_plan'])
    assert fresh_plan['previous_ref'] == plan_ref
    assert fresh_plan['page_links'][0]['page_ref'] == store.load_document()['pages'][0]['page']
    lineage = workbench.page_lineage(project, "p1")["content_plan"]
    assert [g["page_id"] for g in lineage["page_roles"]] == ["p1"]
    assert lineage["goals"][0]["page_ref"] == store.load_document()["pages"][0]["page"]
    assert "input_summary" not in workbench.workbench_summary(project)["content_plan"]


def test_input_revision_advances_v2_plan_with_unchanged_page_refs_and_stable_role_ids(flow):
    project, store, task, envelope = flow
    start(project, task)
    accept(project, task, envelope)
    first = store.load_document()
    updated = service.inputs_update(project, patch={"task_patch": {"audience": "新受众"}, "reason": "补充受众"},
                                     base_revision=first["revision_id"], operation_id="audience")
    new_task = next(t for t in updated["pending_tasks"] if t["kind"] == "compose")
    assert new_task["protocol_version"] == "compose.v2" and new_task["intent"] == "input_revision"
    new_task = tasks._lookup_task(store.load_document(), new_task["task_id"], store)
    start(project, new_task)
    plan = copy.deepcopy(envelope["content_plan"])
    plan["page_roles"][0]["intended_takeaway"] += "新受众不影响两页的已有事实。"
    payload = {"kind": "compose", "content_update": {"input_digest": new_task["input_digest"],
               "page_order": ["p1", "p2"], "unchanged_reason": "受众变化不改变当前步骤与缺口说明"}, "content_plan": plan}
    before = store.current_revision_id()
    bad = copy.deepcopy(payload)
    bad["content_plan"]["page_roles"][0]["page_id"] = "renamed-page"
    bad["content_plan"]["page_order"][0] = "renamed-page"
    bad["content_plan"]["chapters"][0]["page_ids"][0] = "renamed-page"
    with pytest.raises(ModelError):
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
    other["input"]["page_roles"][0]["role"] = "另一个执行者已修订大纲。"
    moved = bump_revision(current, {"operation_id": "synthetic-plan-change", "kind": "content_update", "description": "test interleaving", "read_set": []})
    moved["content_plan"] = store.put_json_object(other)
    store.commit_change(base_revision=current["revision_id"], document=moved, operation_id="synthetic-plan-change")
    assert not tasks.task_inputs_current(store, store.load_document(), raw_task)


def test_page_reorder_marks_old_plan_stale(flow):
    project, store, task, envelope = flow
    envelope["page_order"] = ["p2", "p1"]
    envelope["content_plan"]["page_order"] = ["p2", "p1"]
    envelope["content_plan"]["chapters"][0]["page_ids"] = ["p2", "p1"]
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


def test_legacy_outline_is_unwritten_and_current_import_records_actual_mapping(tmp_path):
    old = historical_snapshot(tmp_path, scenario='fixed old draft without a plan',
        pages=[page('p1', '已有正文')])['project']
    current = tmp_path / 'new'
    service.create(current, brief='Synthetic', draft={'pages': [page('p1', '已有正文')]})
    for project in (old, current):
        store = Store(project)
        before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}
        result = content_plan.show(project)['content_plan']
        if project == old:
            assert result['status'] == result['relation'] == 'derived' and result['ref'] is None
            assert result['goals'][0]['title'] == '已有正文' and result['goals'][0]['goal_id'] is None
            assert 'content_plan' not in store.load_document()
        else:
            assert result['status'] == 'recorded' and result['mode'] == 'imported_mapping'
            assert result['imported_manuscript']['source_ref']
            assert result['goals'][0]['goal_id'] is None
        assert before == {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}


def test_explicit_imported_plan_is_adopted_and_restore_does_not_keep_the_wrong_plan(flow):
    project, store, task, envelope = flow
    from deck_master import collaboration
    doc = store.load_document()
    request = doc['collaboration']['request']
    collaboration.start_request(project, input={'intent': 'full_deck', 'content_intent': None,
        'scope': {**request['scope'], 'page_ids': ['p1', 'p2']},
        'replace_request_id': request['request_id'],
        'instruction_evidence': {'kind': 'host_attested_instruction', 'text': 'L1 replace empty content with exactly these two fixed manuscript pages'}},
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    empty_revision = store.current_revision_id()
    service.import_draft(project, draft_payload={"pages": envelope["pages"], "content_plan": envelope["content_plan"]},
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    first = store.load_document()
    assert store.read_object_json(first["content_plan"])["origin"] == "user_imported"
    editing.restore(project, revision_id=empty_revision, base_revision=first["revision_id"], operation_id="restore-empty")
    assert "content_plan" not in store.load_document()
    assert json.loads((store.deck_root / "current.json").read_text())["minimum_writer"] == \
        first['compatibility']['minimum_writer'] == 'method-catalog.v1'
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
