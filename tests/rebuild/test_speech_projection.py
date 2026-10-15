"""T03 slice 5: speech policy projection (CONTRACTS §1.7, §10.1; ACCEPTANCE AC-M02).

A default `live` value is a technical compatibility value, not a user request:
it may recommend cues but never requires them. `verbatim` needs an explicit
request; `read_alone` defaults to none; `mixed` needs a primary use from an
explicit instruction or an effective delegation, otherwise the Runtime offers
the read-primary + cues recommendation instead of choosing silently.
"""
import pytest

from deck_master import content_production, service
from deck_master.content_production import speech_policy
from deck_master.store import Store
from rc3_fixtures import claim_fixture_task

from test_content_preproduction_review import _page, _plan_input, _project, _source_link


def _document(presentation_mode=None, source=None):
    task = {"presentation_mode": presentation_mode or "live"}
    if source:
        task["presentation_mode_source"] = source
    return {"task": task}


def test_live_default_is_a_compatibility_value_not_a_request():
    policy = speech_policy(_document("live", "default"))
    assert policy["mode"] == "cues"
    assert policy["required"] is False and policy["source"] == "default"
    assert "not a user request" in policy["reason"]
    provided = speech_policy(_document("live", "provided"))
    assert provided["mode"] == "cues" and provided["required"] is True


def test_read_alone_defaults_to_none_and_explicit_none_is_respected():
    read = speech_policy(_document("read_alone", "provided"))
    assert read["mode"] == "none" and read["output"] == "none"
    explicit_none = speech_policy(_document("live", "provided"), explicit_mode="none")
    assert explicit_none["mode"] == "none" and explicit_none["required"] is False
    assert explicit_none["source"] == "provided"


def test_verbatim_needs_an_explicit_request_or_a_delegated_plan_policy():
    assert speech_policy(_document("live", "provided"))["mode"] == "cues"
    explicit = speech_policy(_document("live", "provided"), explicit_mode="verbatim")
    assert explicit["mode"] == "verbatim"
    delegated = speech_policy(_document("live", "default"), plan_input={
        "speech_policy": {"mode": "verbatim", "source": "delegated", "output": "both"}})
    assert delegated["mode"] == "verbatim" and delegated["output"] == "both"
    # A plan that claims verbatim only by default is downgraded to cues.
    downgraded = speech_policy(_document("live", "default"), plan_input={
        "speech_policy": {"mode": "verbatim", "source": "default", "output": "pptx_notes"}})
    assert downgraded["mode"] == "cues"


def test_mixed_without_a_primary_use_recommends_instead_of_choosing():
    undecided = speech_policy(_document("mixed", "provided"))
    assert undecided["requires_decision"] is True
    assert undecided["primary_use"] is None
    assert undecided["mode"] == "cues" and undecided["required"] is False
    assert undecided["recommendation"] == {"primary_use": "read_alone", "speech_mode": "cues"}
    live_primary = speech_policy(_document("mixed", "provided"), primary_use="live")
    assert live_primary["mode"] == "cues" and live_primary["required"] is True
    read_primary = speech_policy(_document("mixed", "provided"), primary_use="read_alone")
    assert read_primary["mode"] == "none" and read_primary["primary_use"] == "read_alone"


def test_speech_dispatch_follows_the_policy(tmp_path):
    """A default live value dispatches no speech production."""
    project, store = _project(tmp_path / "default")
    document = store.load_document()
    status = content_production.content_phase_status(store, document)
    assert status["phase"] == "framing"
    # read_alone never asks for speech production even when pages lack notes.
    project, store = _project(tmp_path / "read", presentation_mode="read_alone")
    document = store.load_document()
    assert content_production.content_phase_status(store, document)["phase"] == "framing"


def test_none_never_deletes_user_notes(tmp_path):
    """`none` means "produce nothing new", not "remove what exists"."""
    from test_content_preproduction_review import _deck
    project, store = _deck(tmp_path)
    document = store.load_document()
    before = [(e["page_id"], store.read_object_json(e["page"])["speaker_notes"])
              for e in document["pages"]]
    policy = speech_policy({**document, "task": {**document["task"],
                                                 "presentation_mode": "read_alone",
                                                 "presentation_mode_source": "provided"}})
    assert policy["mode"] == "none"
    document = store.load_document()
    after = [(e["page_id"], store.read_object_json(e["page"])["speaker_notes"])
             for e in document["pages"]]
    assert before == after and all(notes for _, notes in after)


def test_speech_phase_is_dispatched_only_when_notes_are_missing(tmp_path):
    from test_content_preproduction_review import _deck
    project, store = _deck(tmp_path)
    document = store.load_document()
    # The fixture pages carry notes and the plan asks for cues -> nothing due.
    status = content_production.content_phase_status(store, document)
    assert status["action"] == "complete"
    # A page without notes plus a provided live request asks for the speech phase.
    task = content_production.open_phase_task(store, document, operation_id="pc-empty",
                                              phase="page_copy")
    page = _page(store, document, "p1", notes="")
    claim_fixture_task(project, task)
    service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose",
                        "variant": "page_copy", "task_id": task["task_id"],
                        "operation_id": task["operation_id"],
                        "produced_against": task["produced_against"],
                        "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
                        "payload": {"pages": [page], "page_order": ["p1"],
                                    "plan_input": _plan_input(
                                        store.load_document(), ["p1"],
                                        [_source_link(store, store.load_document(), "L1")])},
                        "usage_events": []})
    store = Store(project)
    document = store.load_document()
    status = content_production.content_phase_status(store, document)
    assert status["action"] == "dispatch" and status["phase"] == "speech"
    assert status["page_ids"] == ["p1"] and status["speech_mode"] == "cues"
    task = content_production.next_phase_task(store, document)
    assert task["collaboration_binding"]["phase"] == "speech"
    assert task["stage_request"]["speech_kind"] == "cue"
