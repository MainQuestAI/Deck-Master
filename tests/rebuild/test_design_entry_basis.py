"""RP-21 real service boundaries with synthetic projects, no model execution."""

import uuid
import pytest
from deck_master import changes, design_entry, generation, styles
from deck_master.models import bump_revision
from deck_master.operations import OperationError
from test_styles import flow, confirm  # noqa: F401


def without_original(flow):
    doc = flow.store.load_document()
    new = bump_revision(
        doc, {"operation_id": "initial-fixture", "kind": "task_update", "description": "Synthetic no-reference input", "read_set": []}
    )
    entry = new["pages"][1]
    for key in ("blueprint", "svg", "svg_preview", "ppt_preview"):
        entry[key] = None
    flow.store.commit_change(base_revision=doc["revision_id"], document=new, operation_id="initial-fixture")
    return new


def test_initial_without_reference_previews_and_dispatches_same_basis(flow):
    doc = without_original(flow)
    result = design_entry.initial_plan(
        flow.project,
        input={"page_id": "p02", "base_revision": doc["revision_id"], "instruction": "Preserve all fixed text and directed relationships."},
    )
    assert result["eligibility"]["allowed"]
    assert flow.store.load_document() == doc
    assert result["plan"]["input"]["references"] == []
    outcome = changes.commit(flow.project, plan_id=result["plan_id"], base_revision=doc["revision_id"], operation_id=str(uuid.uuid4()))
    task = flow.task(outcome["operation_result"]["task_ids"][0])
    assert task["scope_pages"] == ["p02"] and task["stage_request"]["references"] == []
    prepared = generation.prepared_input(flow.store, flow.store.load_document(), task)
    assert prepared["design_context"] == result["production_basis"][0]["resolved_design_context"]
    assert flow.store.load_document()["pages"][1]["blueprint"] is None


def test_initial_does_not_silently_replace_existing_direction_or_allow_stale_scope(flow):
    doc = flow.store.load_document()
    with pytest.raises(OperationError, match="existing direction"):
        design_entry.initial_plan(flow.project, input={"page_id": "p02", "base_revision": doc["revision_id"], "instruction": "new"})
    without_original(flow)
    with pytest.raises(OperationError, match="project changed"):
        design_entry.initial_plan(flow.project, input={"page_id": "p02", "base_revision": doc["revision_id"], "instruction": "new"})


@pytest.mark.parametrize("recipe_version", [1, 3])
def test_selected_recipe_basis_matches_task_and_historical_is_not_implicit(flow, recipe_version):
    from test_rc3_design_recipes import input_value

    selected = confirm(flow, input_value(flow.store.load_document(), ids=["p02", "p03"])) if recipe_version == 3 else confirm(flow)
    result = styles.plan(flow.project, input={"recipe_id": selected["recipe_id"], "page_ids": ["p02"], "max_calls": 1})
    row = result["production_basis"][0]
    assert row["recipe_ref"] == result["plan"]["input"]["style_recipe_ref"]
    outcome = changes.commit(
        flow.project, plan_id=result["plan_id"], base_revision=result["plan"]["base_revision"], operation_id=str(uuid.uuid4())
    )
    prepared = generation.prepared_input(flow.store, flow.store.load_document(), flow.task(outcome["operation_result"]["task_ids"][0]))
    assert prepared["design_context"] == row["resolved_design_context"]


def test_preview_eligibility_matches_commit_refusal_and_does_not_grant(flow):
    doc = without_original(flow)
    from deck_master import collaboration

    collaboration.pause_request(flow.project, reason="Synthetic pause", base_revision=doc["revision_id"], operation_id=str(uuid.uuid4()))
    new = flow.store.load_document()
    result = design_entry.initial_plan(flow.project, input={"page_id": "p02", "base_revision": new["revision_id"], "instruction": "new"})
    assert not result["eligibility"]["allowed"]
    before = flow.store.load_document()
    with pytest.raises(OperationError):
        changes.commit(flow.project, plan_id=result["plan_id"], base_revision=new["revision_id"], operation_id=str(uuid.uuid4()))
    assert flow.store.load_document() == before


def test_initial_plan_http_requires_session_authority(flow):
    from deck_master.web import WorkbenchServer
    from test_web import _post_json, _session_token

    doc = without_original(flow)
    server = WorkbenchServer(flow.project)
    try:
        url = server.start().rstrip("/")
        payload = {"input": {"page_id": "p02", "base_revision": doc["revision_id"], "instruction": "Preserve all text"}}
        assert _post_json(url + "/api/design/initial-plan", payload, None, None)[0] == 403
        code, result = _post_json(url + "/api/design/initial-plan", payload, _session_token(url), url)
        assert code == 200 and result["production_basis"][0]["page_id"] == "p02"
        assert flow.store.load_document() == doc
    finally:
        server.stop()
