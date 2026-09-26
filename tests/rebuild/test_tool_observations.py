"""Adapter contract tests use explicit synthetic records, not live acceptance."""
import base64
import copy
import io
import json

import pytest
from PIL import Image

from deck_master import observations
from deck_master.models import sha256_bytes
from deck_master.observations import ObservationUnavailable

THREAD = "11111111-1111-7111-8111-111111111111"
TURN = "22222222-2222-7222-8222-222222222222"
ITEM = "exec-33333333-3333-4333-8333-333333333333"


@pytest.fixture
def native(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    session = root / "sessions/2026/09/26" / ("rollout-2026-09-26T12-00-00-" + THREAD + ".jsonl")
    image_file = root / "generated_images" / THREAD / (ITEM + ".png")
    session.parent.mkdir(parents=True)
    image_file.parent.mkdir(parents=True)
    image = io.BytesIO()
    Image.new("RGB", (4, 3), "red").save(image, "PNG")
    output = image.getvalue()
    image_file.write_bytes(output)
    meta = {"type": "session_meta", "payload": {"id": THREAD, "cli_version": "synthetic-test"}}
    event = {"type": "event_msg", "payload": {"type": "item_completed", "thread_id": THREAD, "turn_id": TURN,
             "started_at_ms": 1000, "completed_at_ms": 2000, "item": {"type": "Extension", "kind": "image_gen.generation",
             "id": ITEM, "status": "completed", "revisedPrompt": "保留  exact\nwhitespace", "result": base64.b64encode(output).decode(),
             "transparentBackground": False, "failure": None, "savedPath": str(image_file)}}}
    def save(events=None, header=None):
        records = [header or meta, *(events or [event])]
        session.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    save()
    monkeypatch.setattr(observations, "_session_root", lambda: root / "sessions")
    return {"root": root, "session": session, "image_file": image_file, "meta": meta, "event": event,
            "output": output, "save": save, "selector": {"source": "codex_session.v1", "thread_id": THREAD, "turn_id": TURN, "item_id": ITEM}}


def test_native_record_preserves_exact_text_output_and_unknown_fields(native):
    observed = observations.collect_codex_image(native["selector"], minimum_started_at_ms=900)
    record = observed.metadata
    assert observed.output_bytes == native["output"]
    assert record["output"]["sha256"] == sha256_bytes(native["image_file"].read_bytes())
    assert record["submitted"]["prompt"] == "保留  exact\nwhitespace"
    assert record["submitted"]["references"] is None
    assert record["submitted"]["model"] is None and record["submitted"]["seed"] is None
    assert record["coverage"]["parameters"] == {"transparent_background": "native.transparentBackground"}
    assert str(native["root"]) not in json.dumps(record)


@pytest.mark.parametrize("wrapper", ["literal", "variable", "extra_code", "wrong_return"])
def test_only_a_direct_executed_literal_call_can_prove_no_reference_arguments(native, wrapper):
    item = native["event"]["payload"]["item"]
    args = {"prompt": item["revisedPrompt"], "transparent_background": False}
    code = "const result = await tools.image_gen__imagegen(" + json.dumps(args) + ");\ngeneratedImage(result);"
    if wrapper == "variable":
        code = "const args = " + json.dumps(args) + ";const result = await tools.image_gen__imagegen(args);generatedImage(result);"
    if wrapper == "extra_code":
        code += "\nstore('anything', result);"
    call = {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "call_id": "actual-call", "input": code}}
    returned = {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "actual-call",
                "output": [{"type": "input_image", "image_url": "data:image/png;base64," +
                             (base64.b64encode(b"different").decode() if wrapper == "wrong_return" else item["result"])}]}}
    native["save"]([call, native["event"], returned])
    record = observations.collect_codex_image(native["selector"]).metadata
    assert record["submitted"]["references"] == ([] if wrapper == "literal" else None)
    assert ("literal_call" in record["source"]) is (wrapper == "literal")


@pytest.mark.parametrize("change", ["host_label", "arbitrary_path", "bad_thread", "wrong_turn", "too_early"])
def test_selector_never_accepts_host_elevation_or_unbound_events(native, change):
    selector = copy.deepcopy(native["selector"])
    if change == "host_label":
        selector["observer"] = "provider_receipt"
    elif change == "arbitrary_path":
        selector["path"] = str(native["session"])
    elif change == "bad_thread":
        selector["thread_id"] = "../elsewhere"
    elif change == "wrong_turn":
        selector["turn_id"] = THREAD
    with pytest.raises(ObservationUnavailable):
        observations.collect_codex_image(selector, minimum_started_at_ms=1100 if change == "too_early" else None)


@pytest.mark.parametrize("change", ["header", "wrapper", "prompt", "duplicate", "image", "symlink", "incomplete"])
def test_invalid_sources_cannot_become_native_observations(native, change):
    event = native["event"]
    if change == "header":
        meta = copy.deepcopy(native["meta"])
        meta["payload"]["id"] = TURN
        native["save"](header=meta)
    elif change == "wrapper":
        event["payload"]["item"]["type"] = "CommandExecution"
        native["save"]()
    elif change == "prompt":
        event["payload"]["item"]["revisedPrompt"] = None
        native["save"]()
    elif change == "duplicate":
        native["save"]([event, event])
    elif change == "image":
        native["image_file"].write_bytes(b"changed")
    elif change == "symlink":
        real = native["session"].with_suffix(".original")
        native["session"].rename(real)
        native["session"].symlink_to(real)
    elif change == "incomplete":
        native["session"].write_bytes(native["session"].read_bytes().rstrip(b"\n"))
    with pytest.raises(ObservationUnavailable):
        observations.collect_codex_image(native["selector"])
