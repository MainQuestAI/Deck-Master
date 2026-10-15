"""Explicit M02 ledger profile seam; no native/model/image execution."""
from copy import deepcopy
from pathlib import Path

import pytest

from test_rc3_m02_recorder import setup as m02_setup, m
from test_rc3_image_events import setup as event_setup, e
from test_generation_protocol import flow, start, freeze, begin, EXECUTION  # noqa: F401


def event_profile(tmp_path, monkeypatch, *, page_id_bindings=None):
    journal, state, config, _ = m02_setup(tmp_path, monkeypatch)
    directory = tmp_path / "event-profile"; directory.mkdir()
    for phase in ("live", "read"): config["scopes"][phase]["max_candidates"] = 1
    parent = {"parent_id": "original-flow", "matrix_slot": "M02", "case": "M02", "whole_run_id": config["experiment_id"], "repetition": 1, "arm": "B", "max_calls": 2}
    specs = [(phase, phase, config["scopes"][phase]["page_ids"], Path(config["scopes"][phase]["instruction"]["path"]).read_text()) for phase in ("live", "read")]
    ledger, event, _ = event_setup(directory, monkeypatch, parent=parent, scope_specs=specs, protocol_ref=config["protocol"], installation=config["installation"], page_id_bindings=page_id_bindings)
    config.pop("global_image_budget")
    config.update(image_ledger_profile="scope-events-v1", image_event_controller=e.reference(Path(e.__file__)),
        image_event_registration=e.reference(directory / "config.json"), global_image_policy=event["policy"])
    return journal, state, config, ledger


def test_omitted_and_explicit_legacy_profiles_share_exact_default_validation(tmp_path, monkeypatch):
    _, _, config, _ = m02_setup(tmp_path, monkeypatch)
    assert m.validate(config) == config
    explicit = {**config, "image_ledger_profile": "legacy-bf-v1"}
    assert m.validate(explicit) == explicit
    with pytest.raises(m.Error, match="unknown"): m.validate({**config, "image_ledger_profile": "automatic"})


def test_new_profile_uses_same_root_typed_policy_and_preserves_original_business(tmp_path, monkeypatch):
    _, state, config, ledger = event_profile(tmp_path, monkeypatch)
    assert m.validate(config) == config
    task = {"task_id": "synthetic-before-own-SDK", "scope_pages": ["p1"]}
    assert m.guard_image_policy(None, state, config, task, "live", {"task_id": task["task_id"]})["ledger_root"] == str(ledger)
    assert e.inspect_accounting(ledger)["total_charged"] == 0
    with pytest.raises(ValueError): m.guard_image_policy(None, state, config, task, "live_notes_edit", {"task_id": task["task_id"]})


@pytest.mark.parametrize("fault", ["helper", "policy", "registration", "mixed-profile", "extra-page", "wrong-use", "candidate"])
def test_event_profile_bindings_reject_before_any_call(tmp_path, monkeypatch, fault):
    _, _, config, ledger = event_profile(tmp_path, monkeypatch)
    bad = deepcopy(config)
    if fault == "helper": bad["image_event_controller"]["sha256"] = "0" * 64
    if fault == "policy": bad["global_image_policy"]["sha256"] = "0" * 64
    if fault == "registration": bad["image_event_registration"]["sha256"] = "0" * 64
    if fault == "mixed-profile": bad["global_image_budget"] = bad["global_image_policy"]
    if fault == "extra-page": bad["scopes"]["read"]["page_ids"].append("outside")
    if fault == "wrong-use": bad["scopes"]["read"]["page_ids"] = ["other"]
    if fault == "candidate": bad["scopes"]["read"]["max_candidates"] = 3
    with pytest.raises(ValueError): m.validate(bad)
    assert e.inspect_accounting(ledger)["total_charged"] == 0


@pytest.mark.parametrize("bindings", [{}, {"p1": None, "r1": None}, {"r1": None}])
def test_m02_metadata_freeze_and_init_before_actual_pages(tmp_path, monkeypatch, bindings):
    _, state, config, ledger = event_profile(tmp_path, monkeypatch, page_id_bindings=bindings)
    assert m.c.store_for(state).load_document()["pages"] == []
    assert m.validate(config) == config
    actual_config = m.c.save(tmp_path / "planned-event-profile.json", config)
    campaign, run, project = tmp_path / "planned-campaign", tmp_path / "planned-run", tmp_path / "future-project"
    m.freeze(actual_config["path"], campaign)
    initialized = m.init(campaign, run, project)
    assert initialized["case"] == "M02" and not project.exists()
    assert e.inspect_accounting(ledger)["total_charged"] == 0


@pytest.mark.parametrize("bindings", [{"p1": "wrong"}, {"p1": "r1", "r1": "p1"}])
def test_m02_nonnull_binding_cannot_rename_its_planned_page(tmp_path, monkeypatch, bindings):
    _, _, config, ledger = event_profile(tmp_path, monkeypatch, page_id_bindings=bindings)
    with pytest.raises(ValueError):
        m.validate(config)
    assert e.inspect_accounting(ledger)["total_charged"] == 0


def test_null_m02_leaves_cannot_borrow_the_other_use(tmp_path, monkeypatch):
    _, _, config, ledger = event_profile(tmp_path, monkeypatch, page_id_bindings={"p1": None, "r1": None})
    config["scopes"]["live"]["page_ids"], config["scopes"]["read"]["page_ids"] = ["r1"], ["p1"]
    with pytest.raises(ValueError):
        e.validate_m02_policy(config)
    assert e.inspect_accounting(ledger)["total_charged"] == 0


def test_unbound_policy_still_requires_real_sdk_page_attempt_and_right(flow, tmp_path, monkeypatch):
    from test_rc3_image_events import fixture_request_instruction, handoff
    text = fixture_request_instruction(flow)
    parent = {"parent_id": "original-flow", "matrix_slot": "M02", "case": "M02", "whole_run_id": "synthetic-one-page-right", "repetition": 1, "arm": "B", "max_calls": 1}
    ledger, config, boot = event_setup(tmp_path, monkeypatch, parent=parent,
        scope_specs=[("live", "live", ["p1"], text)], page_id_bindings={"p1": None})
    start(flow); frozen = freeze(flow)
    binding = handoff(tmp_path, config, flow, {"allowance_id": "call-1"}, slot="live")
    binding.update(page_id="p1", leaf_id="live-p1")
    task = flow[2]; args = {"task_id": task["task_id"], "allowance_id": "call-1", "execution_ref": EXECUTION, "request_id": frozen["request_id"]}
    assert e.guard_call_begin(config, binding, "p1", args)["attempt_id"] is None
    attempt = begin(flow, frozen); binding["attempt_id"] = attempt["attempt_id"]
    for page_id in (None, "other"):
        wrong = {**binding, "page_id": page_id}
        with pytest.raises(ValueError):
            e.prepare_page_call(ledger, wrong, "live-p1", attempt["attempt_id"])
        assert e.inspect_accounting(ledger)["total_charged"] == 0
    e.prepare_page_call(ledger, binding, "live-p1", attempt["attempt_id"])
    e.mark_dispatch(ledger, "live-p1", boot["path"])
    row = e.inspect_accounting(ledger)["all_rows"][0]
    assert row["page_id"] == "p1" and row["attempt_id"] == attempt["attempt_id"]
