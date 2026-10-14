"""V3 initial proposals dispatch bounded real protocol tasks without fake originals.

Synthetic project fixture and no image call: these are engineering evidence.
"""

from copy import deepcopy
import uuid

import pytest

from test_styles import Flow
from deck_master import changes, generation, models, styles
from deck_master.operations import OperationError


@pytest.fixture
def flow(tmp_path):
    flow = Flow(tmp_path)
    doc = flow.store.load_document()
    updated = deepcopy(doc)
    target = next(e for e in updated["pages"] if e["page_id"] == "p02")
    for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
        target[slot] = None
    updated = models.bump_revision(
        updated, {"operation_id": "without-original", "kind": "task_update", "description": "initial-design fixture", "read_set": []}
    )
    flow.store.commit_change(base_revision=doc["revision_id"], document=updated, operation_id="without-original")
    return flow


def _input(flow, **extra):
    doc = flow.store.load_document()
    style = doc["design_context"]["styles"][0]
    return {
        "schema_version": "style_input.v3",
        "project_id": doc["project_id"],
        "base_revision": doc["revision_id"],
        "intent": "initial_design",
        "target_page_ids": ["p02", "p03"],
        "reference_refs": [],
        "instruction": "保留正文，建立初始视觉规则",
        "recipe_draft": {
            "palette": {"background": "#FFFFFF", "text": "#111111", "accent": "#3366AA"},
            "typography": deepcopy(style["typography"]),
            "density": "保留完整正文和关系，不缩字",
            "composition": "先主结论后完整机制",
            "spacing": {"margin_px": 48, "gap_px": 24},
            "lines": {"width_px": 2, "color": "#333333"},
            "icons": "仅语义必要的图标",
        },
        **extra,
    }


def _confirm(flow, value):
    proposed = styles.propose(flow.project, input=value)
    return styles.confirm(
        flow.project, proposal_id=proposed["proposal_id"], base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4())
    )["operation_result"]


def test_initial_design_without_original_preserves_full_content_and_real_reference_absence(flow):
    before = flow.store.load_document()
    value = _input(flow)
    proposed = styles.propose(flow.project, input=value)
    assert proposed["proposal"]["schema_version"] == "style_proposal.v3"
    assert flow.store.load_document() == before
    target = next(t for t in proposed["proposal"]["targets"] if t["page_id"] == "p02")
    assert target["blueprint_ref"] is None
    recipe = _confirm(flow, value)
    plan = styles.plan(flow.project, input={"recipe_id": recipe["recipe_id"], "page_ids": ["p02"], "max_calls": 1})
    committed = changes.commit(
        flow.project, plan_id=plan["plan_id"], base_revision=flow.store.current_revision_id(), operation_id=str(uuid.uuid4())
    )
    task = flow.task(committed["operation_result"]["task_ids"][0])
    assert task["stage_request"]["references"] == []
    assert len(task["call_allowances"]) == 1
    dispatched = flow.store.load_document()
    assert dispatched["pages"] == before["pages"]
    assert dispatched["design_context"] == before["design_context"]
    prepared = generation.prepared_input(flow.store, dispatched, task)
    assert prepared["references"] == []
    assert prepared["design_context"]["styles"][0]["colors"] == value["recipe_draft"]["palette"]
    assert prepared["design_context"]["content_requirements"]["mode"] == "fidelity"
    assert prepared["design_context"]["content_basis"]["recipe_ref"] == recipe["recipe_ref"]
    assert "完整正文" in prepared["prompt"]
    flow.start(task)
    frozen = generation.freeze(
        flow.project,
        task_id=task["task_id"],
        input=prepared,
        base_revision=flow.store.current_revision_id(),
        operation_id=str(uuid.uuid4()),
    )
    assert frozen["status"] == "frozen"


def test_zero_call_feasibility_does_not_become_a_sample(flow):
    before = flow.store.load_document()
    recipe = _confirm(flow, _input(flow, intent="feasibility", target_page_ids=[]))
    assert flow.store.load_document()["tasks"] == before["tasks"]
    with pytest.raises(OperationError, match="zero-call"):
        styles.plan(flow.project, input={"recipe_id": recipe["recipe_id"], "page_ids": ["p02"], "max_calls": 1})


def test_unknown_font_and_first_trial_expansion_are_refused_before_calls(flow):
    value = _input(flow)
    value["recipe_draft"]["typography"]["body_font_id"] = "missing-font"
    with pytest.raises(OperationError, match="registered"):
        styles.propose(flow.project, input=value)
    recipe = _confirm(flow, _input(flow))
    before = flow.store.load_document()
    with pytest.raises(OperationError, match="exactly one page"):
        styles.plan(flow.project, input={"recipe_id": recipe["recipe_id"], "page_ids": ["p02", "p03"], "max_calls": 2})
    assert flow.store.load_document() == before
