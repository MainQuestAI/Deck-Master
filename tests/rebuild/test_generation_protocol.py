"""W02 protocol behavior; native records here are synthetic test fixtures."""
import base64
import copy
import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest
from PIL import Image

from deck_master import generation, observations, service, tasks, workbench
from deck_master.models import canonical_json_bytes, sha256_bytes, validate_schema
from deck_master.store import Store
from deck_master.web import WorkbenchServer

THREAD = "11111111-1111-7111-8111-111111111111"
TURN = "22222222-2222-7222-8222-222222222222"
EXECUTION = f"codex:{THREAD}:{TURN}"


def test_freeze_rejects_legacy_or_missing_project_before_creating_layout(tmp_path, capsys):
    from deck_master.cli import main
    from deck_master.snapshots import ReadModelError
    old = tmp_path / "old-run"
    old.mkdir()
    (old / "run.json").write_text('{"stage":"completed"}')
    args = dict(task_id="task", input={}, base_revision="base", operation_id="freeze-old")
    with pytest.raises(generation.GenerationError) as failure:
        generation.freeze(old, **args)
    assert failure.value.error_code == "legacy_run_format"
    assert main(["requests", "freeze", "--project", str(old), "--task-id", "task",
                 "--input", "nonexistent.json", "--base-revision", "base", "--operation-id", "freeze-old"]) == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "legacy_run_format"
    assert not (old / ".deckmaster").exists()
    missing = tmp_path / "not-created"
    with pytest.raises(ReadModelError):
        generation.freeze(missing, **args)
    assert not missing.exists()


@pytest.fixture
def flow(tmp_path, monkeypatch):
    project = tmp_path / "synthetic-project"
    draft = {"pages": [{"schema_version": "deck_page_package.v2", "page_id": "p1",
             "customer_visible": {"title": "Synthetic generation", "body_blocks": []},
             "visual_spec": {"intent": "Test only", "reference_mode": "new_design"}}]}
    service.create(project, brief="W02 protocol test", draft=draft, project_format="workbench.v3")
    task = service.continue_project(project)["pending_tasks"][0]
    store = Store(project)
    root = tmp_path / "synthetic-runtime"
    monkeypatch.setattr(observations, "_session_root", lambda: root / "sessions")
    def native(prompt=None, transparent=False):
        item_id = "exec-" + str(uuid.uuid4())
        image = io.BytesIO()
        Image.new("RGB", (12, 8), "#334466").save(image, "PNG")
        raw = image.getvalue()
        saved = root / "generated_images" / THREAD / (item_id + ".png")
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(raw)
        path = root / "sessions/2026/09/26" / ("rollout-2026-09-26T12-00-00-" + THREAD + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps({"type": "session_meta", "payload": {"id": THREAD, "cli_version": "synthetic-test"}}) + "\n")
        now = time.time_ns() // 1000000
        event = {"type": "event_msg", "payload": {"type": "item_completed", "thread_id": THREAD, "turn_id": TURN,
                 "started_at_ms": now, "completed_at_ms": now, "item": {"type": "Extension", "kind": "image_gen.generation",
                 "id": item_id, "status": "completed", "revisedPrompt": prompt or task["generation_input"]["prompt"],
                 "result": base64.b64encode(raw).decode(), "transparentBackground": transparent, "failure": None, "savedPath": str(saved)}}}
        with path.open("a") as handle:
            handle.write(json.dumps(event) + "\n")
        return {"source": "codex_session.v1", "thread_id": THREAD, "turn_id": TURN, "item_id": item_id}, raw
    return project, store, task, native


def start(flow):
    project, store, task, _ = flow
    service.task_start(project, task_id=task["task_id"], execution_ref=EXECUTION,
                       supported_protocols=[generation.PROTOCOL], capabilities=generation.CAPABILITIES)


def freeze(flow, **updates):
    project, store, task, _ = flow
    value = copy.deepcopy(task["generation_input"])
    value["parameters"] = {"transparent_background": False}
    value.update(updates)
    return generation.freeze(project, task_id=task["task_id"], input=value,
                             base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))


def begin(flow, frozen, allowance="call-1"):
    _, store, task, _ = flow
    return tasks.call_begin(store, task_id=task["task_id"], allowance_id=allowance,
                            execution_ref=EXECUTION, request_id=frozen["request_id"])


def settle(flow, attempt, report=None, outcome="consumed"):
    _, store, task, _ = flow
    return tasks.call_settle(store, task_id=task["task_id"], allowance_id=attempt["allowance_id"],
                             attempt_id=attempt["attempt_id"], outcome=outcome,
                             report_bytes=canonical_json_bytes(report) if report is not None else None)


def accept(flow, frozen, attempt, raw):
    project, store, task, _ = flow
    stage = store.staging_dir / task["operation_id"]
    stage.mkdir(exist_ok=True)
    (stage / "result.png").write_bytes(raw)
    payload = {"kind": "blueprint", "files": [{"file_id": "output", "path": "result.png", "media_type": "image/png"}],
               "generation_result": {"request_id": frozen["request_id"], "attempt_id": attempt["attempt_id"]},
               "artifact_specs": [{"role": "blueprint", "page_id": "p1", "file_id": "output",
                                   "provenance": {"source_type": "host_generated", "tool": "image_gen"}}]}
    return service.accept_result(project, result_payload=payload, **{k: task[k] for k in ("task_id", "operation_id", "produced_against")})


def test_capabilities_and_frozen_input_required_before_begin(flow):
    project, store, task, _ = flow
    before = store.current_revision_id()
    with pytest.raises(generation.GenerationError, match="requires generation.v1"):
        service.task_start(project, task_id=task["task_id"], execution_ref=EXECUTION)
    assert store.current_revision_id() == before
    start(flow)
    before = store.current_revision_id()
    start(flow)
    assert store.current_revision_id() == before
    with pytest.raises(generation.GenerationError, match="freeze and bind"):
        tasks.call_begin(store, task_id=task["task_id"], allowance_id="call-1", execution_ref=EXECUTION)
    assert tasks._lookup_task(store.load_document(), task["task_id"], store)["call_allowances"][0]["state"] == "reserved"


def test_encoding_vector_and_freeze_replay_preserve_exact_input(flow):
    vector = {"parameters": {}, "prompt": "保留事实", "references": [], "schema_version": "generation_input.v1"}
    assert sha256_bytes(canonical_json_bytes(vector)) == "d2153cf3ffe6fd547e61bfaa909086e85f8e517e84563a443a108a85d240fa06"
    project, store, task, _ = flow
    start(flow)
    base, op = store.current_revision_id(), str(uuid.uuid4())
    value = {**task["generation_input"], "prompt": "保留  事实\n", "parameters": {"transparent_background": False}}
    args = dict(task_id=task["task_id"], input=value, base_revision=base, operation_id=op)
    first = generation.freeze(project, **args)
    other = freeze(flow, prompt="another frozen input")
    replay = generation.freeze(project, **args)
    assert replay["input"] == value and replay["input_hash"] == sha256_bytes(canonical_json_bytes(value))
    assert replay["revision_id"] == first["revision_id"]
    assert store.current_revision_id() == other["revision_id"]
    with pytest.raises(generation.GenerationError, match="already bound"):
        generation.freeze(project, **{**args, "input": {**value, "prompt": "different"}})


def test_native_roundtrip_links_one_ledger_and_replays_without_new_attempt(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow, parameters={"transparent_background": False})
    attempt = begin(flow, frozen)
    in_flight_revision = store.current_revision_id()
    assert begin(flow, frozen)["attempt_id"] == attempt["attempt_id"]
    report, raw = native()
    settled = settle(flow, attempt, report)
    before = store.current_revision_id()
    assert settle(flow, attempt, report)["attempt_ref"] == settled["attempt_ref"]
    assert store.current_revision_id() == before
    accepted = accept(flow, frozen, attempt, raw)
    assert accept(flow, frozen, attempt, raw)["revision_id"] == accepted["revision_id"]
    saved = tasks._lookup_task(store.load_document(), task["task_id"], store)
    assert len(saved["call_allowances"]) == len(saved["generation_attempts"]) == 1
    artifact = store.read_object_json(saved["result_refs"][0])
    assert artifact["provenance"]["generation_request"] == frozen["request_ref"]
    assert artifact["provenance"]["generation_attempt"] == settled["attempt_ref"]
    shown = generation.show(project, attempt_id=attempt["attempt_id"])
    assert shown["call"]["state"] == "consumed"
    assert shown["observations"][0]["output"]["sha256"] == artifact["file"]["sha256"]
    assert generation.show(project, attempt_id=attempt["attempt_id"], revision=before)["call"]["state"] == "consumed"
    historical = generation.show(project, attempt_id=attempt["attempt_id"], revision=in_flight_revision)
    assert historical["call"]["state"] == "in_flight" and historical["observations"] == []
    lineage = workbench.page_lineage(project, "p1")
    assert lineage["prompts"]["submitted"]["observer"] == "tool_observed"
    assert lineage["generation"]["adopted_observation"]["output"]["sha256"] == artifact["file"]["sha256"]
    assert lineage["generation"]["attempts"][0]["observations"][0]["comparison"]["unknown"] == ["references"]
    assert workbench.workbench_summary(project)["attempts"] == {"status": "recorded", "count": 1}


@pytest.mark.parametrize("difference", ["prompt", "parameter", "extra_parameter", "unobserved_parameter", "output"])
def test_mismatch_or_missing_coverage_refuses_adoption_but_retains_call(flow, difference):
    project, store, task, native = flow
    start(flow)
    parameters = {"seed": 7} if difference == "unobserved_parameter" else {"transparent_background": False}
    if difference == "extra_parameter":
        parameters = {}
    frozen = freeze(flow, parameters=parameters)
    attempt = begin(flow, frozen)
    report, raw = native(prompt="changed input" if difference == "prompt" else None, transparent=difference == "parameter")
    settle(flow, attempt, report)
    with pytest.raises(generation.GenerationError):
        accept(flow, frozen, attempt, b"different bytes" if difference == "output" else raw)
    doc = store.load_document()
    assert doc["pages"][0]["blueprint"] is None
    assert tasks._lookup_task(doc, task["task_id"], store)["call_allowances"][0]["state"] == "consumed"
    assert generation.show(project, request_id=frozen["request_id"])["request"]["input_hash"] == frozen["input_hash"]


def test_host_report_cannot_upgrade_and_native_can_enrich_it(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    attempt = begin(flow, frozen)
    settle(flow, attempt, {"observer": "provider_receipt", "provider": "fake", "signature": "not-a-signature"})
    observed = generation.show(project, attempt_id=attempt["attempt_id"])
    assert observed["call"]["evidence_level"] == "host_reported"
    report, raw = native()
    with pytest.raises(generation.GenerationError, match="native observation"):
        accept(flow, frozen, attempt, raw)
    settle(flow, attempt, report)
    assert len(generation.show(project, attempt_id=attempt["attempt_id"])["observations"]) == 2
    assert accept(flow, frozen, attempt, raw)["status"] == "accepted"


def test_unknown_is_not_resend_permission_and_new_allowance_gets_new_attempt(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    first = begin(flow, frozen)
    settle(flow, first, outcome="unknown")
    with pytest.raises(tasks.CallBlocked):
        tasks.allocate_call_allowances(store, task_id=task["task_id"], count=1)
    with pytest.raises(tasks.TaskConflict):
        begin(flow, frozen)
    report, _ = native()
    settle(flow, first, report)
    allocated = tasks.allocate_call_allowances(store, task_id=task["task_id"], count=1)
    second = begin(flow, frozen, allocated["allowance_ids"][0])
    assert first["attempt_id"] != second["attempt_id"]
    assert generation.show(project, attempt_id=first["attempt_id"])["call"]["state"] == "consumed"
    assert generation.show(project, attempt_id=second["attempt_id"])["call"]["state"] == "in_flight"


def test_native_event_cannot_be_attached_to_two_calls(flow):
    _, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    first = begin(flow, frozen)
    allocated = tasks.allocate_call_allowances(store, task_id=task["task_id"], count=1)
    second = begin(flow, frozen, allocated["allowance_ids"][0])
    report, _ = native()
    settle(flow, first, report)
    with pytest.raises(tasks.TaskConflict, match="already registered"):
        settle(flow, second, report)


def test_completed_native_call_after_cancellation_retains_facts_without_adoption(flow):
    project, store, task, native = flow
    start(flow)
    frozen = freeze(flow)
    attempt = begin(flow, frozen)
    service.task_cancel(project, task_id=task["task_id"])
    report, raw = native()
    settle(flow, attempt, report)
    with pytest.raises(tasks.TaskConflict, match="after cancellation"):
        accept(flow, frozen, attempt, raw)
    assert store.load_document()["pages"][0]["blueprint"] is None
    shown = generation.show(project, attempt_id=attempt["attempt_id"])
    assert shown["call"]["state"] == "consumed" and shown["attempt"]["output_refs"]


def test_complete_request_vector_from_actual_cli_freeze():
    path = Path(__file__).resolve().parents[2] / "docs/reports/workbench-v3-execution-20260926/w02/real-host-literal/freeze.json"
    frozen = json.loads(path.read_bytes())
    validate_schema("generation_input", frozen["input"])
    assert sha256_bytes(canonical_json_bytes(frozen["input"])) == frozen["input_hash"] == "e62ee707ffb1531ce9373ad51fda4d0fc6d999216dca708e84a1d469e71d6fac"


def test_cli_http_freeze_and_fixed_reads_are_the_same_contract(flow, tmp_path):
    project, store, task, _ = flow
    start(flow)
    body = dict(task_id=task["task_id"], input=task["generation_input"], base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    server = WorkbenchServer(project)
    url = server.start().rstrip("/")
    try:
        headers = {"Origin": url, "X-Deck-Token": server.httpd.RequestHandlerClass.write_token, "Content-Type": "application/json"}
        request = urllib.request.Request(url + "/api/requests/freeze", data=canonical_json_bytes(body), headers=headers)
        frozen = json.load(urllib.request.urlopen(request))
        input_file = tmp_path / "input.json"
        input_file.write_bytes(canonical_json_bytes(body["input"]))
        proc = subprocess.run([sys.executable, "-m", "deck_master", "requests", "freeze", "--project", str(project),
               "--task-id", task["task_id"], "--input", str(input_file), "--base-revision", body["base_revision"],
               "--operation-id", body["operation_id"]], capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["input_hash"] == frozen["input_hash"]
        route = f"/api/requests/{frozen['request_id']}?revision={frozen['revision_id']}"
        assert json.load(urllib.request.urlopen(url + route)) == generation.show(project, request_id=frozen["request_id"], revision=frozen["revision_id"])
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(urllib.request.Request(url + "/api/requests/freeze", data=canonical_json_bytes(body)))
        assert err.value.code == 403
    finally:
        server.stop()
