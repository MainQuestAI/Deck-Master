"""T03 slice 4: claim -> evidence -> page mapping, the time budget and fact-source
change impact analysis (CONTRACTS §11.3, ACCEPTANCE AC-M03).

The Runtime checks what is structurally checkable — every visible atom mapped,
every node and locator real, budget items that add up — and says so honestly:
estimates stay estimates, and the semantic support question stays with the
content review.
"""
import pathlib

import pytest

from deck_master import content_impact, content_production, content_review, models, service
from deck_master.content_plan import check_time_budget, timing_budget
from deck_master.models import ModelError, bump_revision, require_writer
from deck_master.store import Store
from deck_master.tasks import EnvelopeError

from test_content_preproduction_review import (  # noqa: E402 - shared slice fixtures
    _argument_narrative, _deck, _independent_adapter, _page, _plan_input, _project,
    _source_link, _stored)


def _submit_page_copy(project, store, *, pages, order, plan_input, page_task=None, node="n1"):
    document = store.load_document()
    task = page_task or content_production.open_phase_task(
        store, document, operation_id=f"pc-{order[0]}", phase="page_copy")
    return service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                        "variant": "page_copy", "task_id": task["task_id"],
                        "operation_id": task["operation_id"],
                        "produced_against": task["produced_against"],
                        "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                        "payload": {"pages": pages, "page_order": order,
                                    "plan_input": plan_input},
                        "usage_events": []})


# ---------------------------------------------------------------------------
# Mapping checks on the page_copy path


def test_mapping_must_cover_atoms_nodes_and_sources(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="pc-map",
                                              phase="page_copy")
    good = _page(store, document, "p1")
    plan_input = _plan_input(document, ["p1"], [_source_link(store, document, "L1")])
    # A visible atom left out of the mapping is refused (nothing is written).
    missing_atom = {**good, "content_mapping": {
        **good["content_mapping"],
        "visible_links": good["content_mapping"]["visible_links"][:1]}}
    with pytest.raises(EnvelopeError, match="every visible atom needs exactly one mapping"):
        _submit_page_copy(project, store, pages=[missing_atom], order=["p1"],
                          plan_input=plan_input, page_task=task)
    # A claim reference that is not in the adopted Narrative is refused.
    ghost = {**good, "content_mapping": {
        **good["content_mapping"],
        "visible_links": [{**link, "narrative_node_ids": ["n7"]}
                          for link in good["content_mapping"]["visible_links"]]}}
    with pytest.raises(EnvelopeError, match="narrative nodes not present"):
        _submit_page_copy(project, store, pages=[ghost], order=["p1"],
                          plan_input=plan_input, page_task=task)
    # A locator outside the stored source version is refused.
    wrong = {**good, "content_mapping": {
        **good["content_mapping"],
        "visible_links": [good["content_mapping"]["visible_links"][0],
                          {**good["content_mapping"]["visible_links"][1],
                           "source_links": [_source_link(store, document, "L404")]}]}}
    with pytest.raises(EnvelopeError, match="locator"):
        _submit_page_copy(project, store, pages=[wrong], order=["p1"],
                          plan_input=plan_input, page_task=task)
    out = _submit_page_copy(project, store, pages=[good], order=["p1"], plan_input=plan_input,
                            page_task=task)
    assert out["status"] == "accepted"
    page = store.read_object_json(
        next(e for e in store.load_document()["pages"] if e["page_id"] == "p1")["page"])
    assert page["content_mapping"]["visible_links"][1]["source_links"][0]["locator"] == "L1"


def test_a_reported_fact_claim_needs_a_source_or_a_blocker(tmp_path):
    project, store = _deck(tmp_path, plan_mode="planned")
    document = store.load_document()
    task = content_production.open_phase_task(store, document, operation_id="pc-fact",
                                              phase="page_copy")
    narrative = {**_argument_narrative(document["project_id"]), "nodes": [
        {"node_id": "n1", "role": "claim",
         "statement": "54/120 缺型号，因此可节省 45% 时间", "authority": "reported_fact",
         "source_links": [], "qualification_node_ids": [], "unresolved_issue_ids": []}],
        "edges": []}
    with pytest.raises(ModelError, match="verifiable source locator or an explicit blocker"):
        models.validate_narrative_semantics(narrative)
    # The same claim expressed as a hypothesis is structurally acceptable and
    # keeps the limiting condition as its own node.
    hypothesis = {**narrative, "nodes": [
        {"node_id": "n1", "role": "claim", "statement": "字段前移可能减少再次确认（待验假设）",
         "authority": "hypothesis", "source_links": [], "qualification_node_ids": ["q1"],
         "unresolved_issue_ids": []},
        {"node_id": "q1", "role": "qualification",
         "statement": "54/120 只是样本占比，本次未测量补问轮次", "authority": "instruction",
         "source_links": [], "qualification_node_ids": [], "unresolved_issue_ids": []}]}
    models.validate_narrative_semantics(hypothesis)


# ---------------------------------------------------------------------------
# Time budget (AC-M03)


def test_timing_budget_adds_items_and_labels_estimates(tmp_path):
    project, store = _deck(tmp_path)
    store = Store(project)
    document = store.load_document()
    budget = timing_budget(store, document)
    assert budget["estimated"] is True and budget["measured"] is False
    # Per-page items are separated and their sum is the estimated total.
    speaking = sum(page["items"]["speaking"] for page in budget["per_page"])
    assert budget["totals"]["speaking"] == speaking
    assert budget["per_page"][0]["speaking_source"] == "speech_segments"
    # The declared plan budget (480s) is compared item by item, never inferred
    # from the page count.
    assert budget["declared"]["total_seconds"] == 480
    assert budget["declared"]["page_count"] == 2
    assert timing_budget(store, document, items={"p1": {"speaking": 300},
                                                 "p2": {"speaking": 300}})["status"] == "over_budget"
    over = check_time_budget(store, document, items={"p1": {"speaking": 300},
                                                     "p2": {"speaking": 300}})
    # Speaking (600) plus the declared interaction budget (100) exceeds 480s.
    assert over["allows"] is False and over["over_by"] == 700 - 480
    assert over["next_action"] == "present_a_real_keep_drop_tradeoff"
    assert "estimates" in over["note"]


def test_timing_budget_passes_when_the_items_really_add_up(tmp_path):
    project, store = _deck(tmp_path)
    store = Store(project)
    document = store.load_document()
    # Explicit per-page items that fit the declared 480s budget, with practice
    # and pauses counted separately from speaking.
    items = {"p1": {"speaking": 150, "pause": 20, "exercise": 40, "qa": 10},
             "p2": {"speaking": 180, "pause": 20, "exercise": 50, "qa": 10}}
    budget = timing_budget(store, document, items=items)
    assert budget["totals"]["speaking"] == 330
    assert budget["totals"]["interaction"] == 150
    assert budget["totals"]["estimated_total"] == 480
    assert budget["status"] == "within_budget"
    assert check_time_budget(store, document, items=items)["allows"] is True
    # A different constraint is reported as declared, not silently tightened.
    assert timing_budget(store, document)["declared"]["constraint"] == "hard"


def test_timing_budget_never_invents_a_measurement(tmp_path):
    project, store = _deck(tmp_path)
    store = Store(project)
    budget = timing_budget(store, Store(project).load_document())
    assert budget["measured"] is False
    assert all(page["speaking_source"] in ("speech_segments", "plan_role_estimate", "absent")
               for page in budget["per_page"])


# ---------------------------------------------------------------------------
# Fact-source change impact


def _replace_source(project, store, tmp_path, *, name="S1-material.txt", text=None):
    path = tmp_path / name
    path.write_text(text or "第一行：版本未知时先记录未知。\n第二行：紧急程度与可得性是两个维度（修订）。\n",
                    encoding="utf-8")
    document = store.load_document()
    return service.inputs_update(
        project, patch={"reason": "材料修订", "mode": "auto",
                        "source_changes": {"replace": [
                            {"source_id": document["sources"][0]["source_id"], "path": str(path)}],
                            "add": [], "remove": [], "metadata": []}},
        base_revision=document["revision_id"], operation_id="op-replace-source")


def test_impact_analysis_names_affected_claims_and_pages_first(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    before = document
    after = {**document,
             "sources": [{**document["sources"][0],
                          "extract": {**document["sources"][0]["extract"], "sha256": "f" * 64}}]}
    impact = content_impact.analyze_input_change(store, before, after)
    assert impact["changed_sources"]["changed"] == [document["sources"][0]["source_id"]]
    # The pages whose mapping cites the changed source are named, with atoms.
    assert impact["affected_pages"] == ["p1", "p2"]
    assert impact["page_links"][0]["atoms"][0]["locator"] == "L1"
    assert impact["unaffected_pages"] == []
    assert impact["has_impact"] is True
    assert impact["estimated"] is False and impact["impact_digest"]


def test_impact_keeps_unrelated_pages_and_uses_existing_channels(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    # A source nothing references: pages stay unaffected, and the unresolved
    # issues / review findings channels are the ones reused.
    before = {**document, "sources": []}
    after = {**document, "sources": []}
    impact = content_impact.analyze_input_change(store, before, after)
    assert impact["has_impact"] is False
    assert impact["affected_pages"] == []
    assert set(impact["unaffected_pages"]) == {"p1", "p2"}
    assert impact["unresolved_items"] == [] and impact["open_findings"] == []
    assert "本次没有材料或任务事实变化" in content_impact.impact_summary_text(impact)


def test_inputs_update_reports_the_impact_and_the_revision_carries_it(tmp_path):
    project, store = _deck(tmp_path)
    outcome = _replace_source(project, store, tmp_path)
    impact = outcome["content_impact"]
    assert impact["changed_sources"]["changed"]
    assert impact["affected_pages"] == ["p1", "p2"]
    task = outcome["pending_tasks"][0]
    assert task["intent"] == "input_revision"
    assert "影响分析" in task["instruction"]
    assert "p1" in task["instruction"] and "p2" in task["instruction"]
    # The label stays honest: the task is a revision, not a silent rewrite.
    assert outcome["input_alignment"] == "needs_reconciliation"


def test_impact_of_a_task_fact_change_lists_the_field(tmp_path):
    project, store = _deck(tmp_path)
    document = store.load_document()
    outcome = service.inputs_update(
        project, patch={"reason": "受众变化", "mode": "auto",
                        "task_patch": {"audience": "现场主管"},
                        "source_changes": {"add": [], "replace": [], "remove": [], "metadata": []}},
        base_revision=document["revision_id"], operation_id="op-audience")
    impact = outcome["content_impact"]
    assert impact["changed_task_fields"] == ["audience"]
    assert "audience" in content_impact.impact_summary_text(impact)
