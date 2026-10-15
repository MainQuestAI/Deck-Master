"""Explicit M02 ledger profile seam; no native/model/image execution."""
from copy import deepcopy
from pathlib import Path

import pytest

from test_rc3_m02_recorder import setup as m02_setup, m
from test_rc3_image_events import setup as event_setup, e


def event_profile(tmp_path, monkeypatch):
    journal, state, config, _ = m02_setup(tmp_path, monkeypatch)
    directory = tmp_path / "event-profile"; directory.mkdir()
    for phase in ("live", "read"): config["scopes"][phase]["max_candidates"] = 1
    parent = {"parent_id": "original-flow", "matrix_slot": "M02", "case": "M02", "whole_run_id": config["experiment_id"], "repetition": 1, "arm": "B", "max_calls": 2}
    specs = [(phase, phase, config["scopes"][phase]["page_ids"], Path(config["scopes"][phase]["instruction"]["path"]).read_text()) for phase in ("live", "read")]
    ledger, event, _ = event_setup(directory, monkeypatch, parent=parent, scope_specs=specs, protocol_ref=config["protocol"], installation=config["installation"])
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
