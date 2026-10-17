"""Synthetic engineering only: actual SDK rights, zero model/image calls.

The install identity and Root observations are explicit unit seams. They do not
admit native evidence or an installed candidate. Root's actual primitive remains
separate; ordinary JSON and synthetic MACs never become benchmark results.
"""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest
from PIL import Image

from test_generation_protocol import flow, start, freeze, begin, accept  # noqa: F401

SCRIPT = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/image_event_controller.py"
spec = importlib.util.spec_from_file_location("rc3_image_event_engineering", SCRIPT)
e = importlib.util.module_from_spec(spec); spec.loader.exec_module(e)


def setup(tmp_path, monkeypatch, *, scope_specs=None, parent=None, total=None, legacy=False, protocol_ref=None, installation=None, prior_dispatch=None, page_id_bindings=None):
    protocol = protocol_ref or e.save(tmp_path / "protocol.json", {"scope": "SYNTHETIC_ENGINEERING_ONLY"})
    scopes = []
    for slot, checkpoint, pids, instruction in scope_specs or [("scope-one", "Q4B", ["p1"], "Synthetic event one")]:
        message = tmp_path / (slot + ".txt"); message.write_text(instruction)
        scopes.append({"scope_slot": slot, "parent_id": "original-flow", "checkpoint": checkpoint,
            "instruction": e.reference(message), "max_calls": len(pids),
            "leaves": [{"leaf_id": slot + "-" + pid, "page_label": pid, "page_id": (page_id_bindings or {}).get(pid, pid),
                "max_calls": 1, "max_candidates": 1, "retries": 0} for pid in pids]})
    parent = parent or {"parent_id": "original-flow", "matrix_slot": "08", "case": "Q4",
        "whole_run_id": "synthetic-original-flow", "repetition": 1, "arm": "B", "max_calls": sum(s["max_calls"] for s in scopes)}
    ledger = tmp_path / "ig"
    policy = {"format": e.POLICY, "status": e.ENGINEERING, "ledger_root": str(ledger),
        "protocol": protocol, "Root_decision": protocol, "total_call_cap": total or parent["max_calls"], "parents": [parent], "scopes": scopes}
    policy_ref = e.save(tmp_path / "policy.json", policy)
    activation = e.save(tmp_path / "activation.json", {"assurance": "host_attested", "observer_id": "/root",
        "evidence_kind": e.ENGINEERING, "policy_sha256": policy_ref["sha256"], "legacy_writer_route": "HISTORICAL_READ_ONLY"})
    config = {"format": e.FORMAT, "status": e.ENGINEERING, "controller_sha256": e.digest(SCRIPT.read_bytes()),
        "sdk_controller": e.reference(SCRIPT.with_name("controller.py")), "bf_primitives": e.reference(SCRIPT.with_name("image_controller.py")),
        "policy": policy_ref, "protocol": protocol, "admission_review": protocol, "activation": activation,
        "installations": {"B": installation or {"SYNTHETIC_INSTALLATION_SEAM": True}}}
    if legacy:
        ledger.mkdir()
        e.save(ledger / "global-budget.json", {"unchanged": "original empty policy; not reinterpreted as typed"})
        e.save(ledger / "budget-origin.json", {"unchanged": True})
        config["legacy_policy_refs"] = [e.reference(ledger / name) for name in ("global-budget.json", "budget-origin.json")]
    if prior_dispatch:
        dispatch, mapping = prior_dispatch
        ref = e.save(ledger / "dispatches/000001.json", dispatch)
        config["legacy_mapping"] = [{**mapping, "dispatch_sha256": ref["sha256"]}]
    config_ref = e.save(tmp_path / "config.json", config)
    e.initialize_epoch(config_ref["path"], ledger)
    boot = e.save(tmp_path / "bootstrap.json", {"evidence_kind": e.ENGINEERING})
    monkeypatch.setattr(e.c, "installation", lambda *_args, **_kw: {"SYNTHETIC_INSTALLATION_SEAM": True})
    return ledger, config, boot


def handoff(tmp_path, config, flow_value, attempt, *, slot="scope-one"):
    project, store, task, _ = flow_value
    p = next(s for s in e.read(config["policy"]["path"])["scopes"] if s["scope_slot"] == slot)
    parent = e.read(config["policy"]["path"])["parents"][0]
    occurrence_path = tmp_path / (slot + "-occurrence.json")
    observation = e.reference(occurrence_path) if occurrence_path.exists() else e.save(occurrence_path, {"assurance": "host_attested", "observer_id": "/root",
        "evidence_kind": e.ENGINEERING, "scope_slot": slot, "instruction_sha256": p["instruction"]["sha256"],
        "actual_trigger_satisfied": True, "source_observations": [config["protocol"]]})
    stage = slot + "-" + task["task_id"]
    raw = e.save(tmp_path / (stage + "-raw.json"), {"SYNTHETIC_PACKET_AUDIT_SEAM": True})
    audit = e.save(tmp_path / (stage + "-audit.json"), {"status": "PASS", "scope_slot": slot,
        "task_id": task["task_id"], "project": str(project), "stage": stage, "required_read_closure_checked": True,
        "raw_workorder_preserved": True, "original_raw_ref": raw, "author_view_ref": raw, "read_closure_manifest_ref": raw})
    return {"format": e.HANDOFF, "matrix_slot": parent["matrix_slot"], "case": parent["case"], "whole_run_id": parent["whole_run_id"],
        "repetition": 1, "arm": "B", "checkpoint": p["checkpoint"], "project": str(project), "scope_slot": slot,
        "instruction_occurrence_ref": observation, "actual_request_id": store.load_document()["collaboration"]["request"]["request_id"],
        "task_id": task["task_id"], "allowance_id": attempt["allowance_id"], "attempt_id": attempt.get("attempt_id"), "packet_audit_ref": audit, "stage": stage}


def current_instruction(flow_value, instruction):
    """Change the synthetic test's current request through its own public API."""
    from deck_master import collaboration
    from rc3_fixtures import evidence_for
    project, store, _, _ = flow_value
    doc = store.load_document()
    return collaboration.start_request(project, input={"intent": "full_deck", "content_intent": None,
        "scope": doc["collaboration"]["request"]["scope"], "replace_request_id": doc["collaboration"]["request"]["request_id"],
        "instruction_evidence": evidence_for(project, text=instruction, locator="L1:image-event")},
        base_revision=doc["revision_id"], operation_id="new-event-request-" + str(len(doc["tasks"])))


def fixture_request_instruction(flow_value):
    store = flow_value[1]
    evidence = store.load_document()["collaboration"]["request"]["instruction_evidence"]
    return store.read_object_bytes(evidence["source_ref"]).decode()


def ready(tmp_path, monkeypatch, flow_value):
    text = fixture_request_instruction(flow_value)
    ledger, config, boot = setup(tmp_path, monkeypatch, scope_specs=[("scope-one", "Q4B", ["p1"], text)])
    start(flow_value); frozen = freeze(flow_value); attempt = begin(flow_value, frozen)
    binding = handoff(tmp_path, config, flow_value, attempt)
    prepared = e.prepare_page_call(ledger, binding, "scope-one-p1", attempt["attempt_id"])
    return ledger, config, boot, binding, frozen, attempt, prepared


def callback(tmp_path, config, ledger, leaf, *, status="completed", fault=None):
    p = e.read(e._call_dir(ledger, leaf) / "preparation.json")
    response = tmp_path / "synthetic-native-response.txt"; response.write_text("SYNTHETIC NO IMAGE TOOL INVOCATION")
    value = {"observer_kind": e.ENGINEERING, "observer_id": "/root", "tool_name": "image_gen__imagegen",
        "actual_arguments": p["tool_arguments"], "controller_observed_completed_at_ms": e.b.now_ms(),
        "completion_status": status, "native_response": e.reference(response)}
    if status == "completed":
        png = tmp_path / "synthetic-original.png"; buffer = io.BytesIO()
        Image.new("RGB", (12, 8), "#334466").save(buffer, "PNG"); png.write_bytes(buffer.getvalue())
        value["original_png"] = e.reference(png)
    if fault == "arguments": value["actual_arguments"] = {"prompt": "changed", "transparent_background": False}
    return e.save(tmp_path / "callback.json", value)


def test_actual_sdk_frozen_attempt_and_synthetic_opaque_transport(flow, tmp_path, monkeypatch):
    ledger, config, boot, _, frozen, attempt, _ = ready(tmp_path, monkeypatch, flow)
    marker = e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    cb = callback(tmp_path, config, ledger, "scope-one-p1")
    sealed = e.seal_observation(ledger, "scope-one-p1", cb["path"], boot["path"])
    assert sealed["evidence_kind"] == e.ENGINEERING
    assert e.inspect_accounting(ledger)["total_charged"] == 1
    assert marker["automatic_retry"] is False
    result = e.settle(ledger, "scope-one-p1")
    assert result["actual_result"]["native_observation_status"] == "accepted"
    assert result["automatic_adoption"] is False
    png = Path(e.read(cb["path"])["original_png"]["path"]).read_bytes()
    assert accept(flow, frozen, attempt, png)["status"] == "accepted"
    assert e.inspect_accounting(ledger)["total_charged"] == 1


@pytest.mark.parametrize("status", ["unknown", "error"])
def test_unknown_and_error_remain_charged_and_cannot_resend(flow, tmp_path, monkeypatch, status):
    ledger, config, boot, binding, _, attempt, _ = ready(tmp_path, monkeypatch, flow)
    e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    cb = callback(tmp_path, config, ledger, "scope-one-p1", status=status)
    e.seal_observation(ledger, "scope-one-p1", cb["path"], boot["path"])
    assert e.settle(ledger, "scope-one-p1")["actual_call_outcome"] == "unknown"
    assert e.inspect_accounting(ledger)["total_charged"] == 1
    with pytest.raises(e.ImageEventError): e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    with pytest.raises(e.ImageEventError): e.prepare_page_call(ledger, binding, "scope-one-p1", attempt["attempt_id"])


@pytest.mark.parametrize("fault", ["task", "request", "attempt", "whole-run", "packet", "instruction", "parameters"])
def test_wrong_bindings_fail_without_new_global_charge(flow, tmp_path, monkeypatch, fault):
    from deck_master import generation
    text = fixture_request_instruction(flow)
    ledger, config, _ = setup(tmp_path, monkeypatch, scope_specs=[("scope-one", "Q4B", ["p1"], text)])
    start(flow)
    if fault == "parameters":
        task = flow[2]; value = generation.prepared_input(flow[1], flow[1].load_document(), task)
        value["parameters"]["transparent_background"] = True
        frozen = generation.freeze(flow[0], task_id=task["task_id"], input=value, base_revision=flow[1].current_revision_id(), operation_id="legal-true-freeze")
    else: frozen = freeze(flow)
    attempt = begin(flow, frozen); binding = handoff(tmp_path, config, flow, attempt)
    if fault == "task": binding["task_id"] = "foreign"
    if fault == "request": binding["actual_request_id"] = "foreign"
    if fault == "attempt": binding["attempt_id"] = "foreign"
    if fault == "whole-run": binding["whole_run_id"] = "renamed"
    if fault == "packet": binding["packet_audit_ref"]["sha256"] = "0" * 64
    if fault == "instruction": binding["instruction_occurrence_ref"]["sha256"] = "0" * 64
    before = {str(p): p.read_bytes() for p in Path(flow[0]).rglob("*") if p.is_file()}
    with pytest.raises((ValueError, KeyError, generation.GenerationError)): e.prepare_page_call(ledger, binding, "scope-one-p1", binding["attempt_id"])
    assert e.inspect_accounting(ledger)["total_charged"] == 0
    assert before == {str(p): p.read_bytes() for p in Path(flow[0]).rglob("*") if p.is_file()}


def test_first_wrong_native_callback_frozen_before_refusal(flow, tmp_path, monkeypatch):
    ledger, config, boot, *_ = ready(tmp_path, monkeypatch, flow)
    e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    cb = callback(tmp_path, config, ledger, "scope-one-p1", fault="arguments")
    with pytest.raises(ValueError): e.seal_observation(ledger, "scope-one-p1", cb["path"], boot["path"])
    dest = e._call_dir(ledger, "scope-one-p1")
    assert (dest / "raw-first-root-callback").read_bytes() == Path(cb["path"]).read_bytes()
    assert (dest / "raw-first-original_png").exists()
    assert e.inspect_accounting(ledger)["total_charged"] == 1


def test_plain_json_cannot_replace_new_protected_seal(flow, tmp_path, monkeypatch):
    ledger, config, boot, *_ = ready(tmp_path, monkeypatch, flow)
    e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    cb = callback(tmp_path, config, ledger, "scope-one-p1")
    e.seal_observation(ledger, "scope-one-p1", cb["path"], boot["path"])
    dest = e._call_dir(ledger, "scope-one-p1")
    original = e.read(dest / "sealed-observation.json")
    changed = deepcopy(original); changed["record"]["claims"]["arguments"]["prompt"] += " tampered"
    (dest / "sealed-observation.json").write_bytes(e.c.encoded(changed))
    assert e.RootEventProvider(ledger, config, "scope-one-p1").health() is False
    with pytest.raises(e.ImageEventError): e.settle(ledger, "scope-one-p1")
    assert e.inspect_accounting(ledger)["total_charged"] == 1


def test_empty_original_policy_preserved_and_second_root_refused(tmp_path, monkeypatch):
    ledger, config, _ = setup(tmp_path, monkeypatch, legacy=True)
    assert e.read(ledger / "global-budget.json")["unchanged"].startswith("original")
    with pytest.raises(e.ImageEventError): e.initialize_epoch(tmp_path / "config.json", tmp_path / "ig2")
    with pytest.raises(e.ImageEventError): e.initialize_epoch(tmp_path / "config.json", ledger)
    assert e.inspect_accounting(ledger)["total_charged"] == 0
    e.save(ledger / "dispatches/late-old-writer.json", {"not": "an admitted new dispatch"})
    with pytest.raises(e.ImageEventError, match="legacy writer"): e.inspect_accounting(ledger)


def test_reserved_global_charge_survives_missing_local_mark(flow, tmp_path, monkeypatch):
    ledger, _, boot, *_ = ready(tmp_path, monkeypatch, flow)
    e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    # Explicit crash-window seam: only the local publication is absent. The
    # original globally reserved call remains, with no actual tool invocation.
    (e._call_dir(ledger, "scope-one-p1") / "dispatch-mark.json").unlink()
    assert e.inspect_accounting(ledger)["total_charged"] == 1
    with pytest.raises(e.ImageEventError): e.mark_dispatch(ledger, "scope-one-p1", boot["path"])


@pytest.mark.parametrize("legacy_append", [True, False])
def test_real_shared_lock_rechecks_frontier_after_wait(flow, tmp_path, monkeypatch, legacy_append):
    """A scheduling-only child wrapper still acquires the unchanged bf lock.

    Installation identity is the same explicit synthetic seam as this module's
    other tests; real Store/currentness/rights checks and OS locks are retained.
    """
    ledger, _, boot, *_ = ready(tmp_path, monkeypatch, flow)
    ready_path = tmp_path / "child-waiting-for-actual-lock"
    child_source = '''
from contextlib import contextmanager
import importlib.util,json,sys
from pathlib import Path
tool,root,bootstrap,ready,sdk_init=sys.argv[1:]
sdk_spec=importlib.util.spec_from_file_location("deck_master",sdk_init,submodule_search_locations=[str(Path(sdk_init).parent)])
sdk=importlib.util.module_from_spec(sdk_spec);sys.modules["deck_master"]=sdk;sdk_spec.loader.exec_module(sdk)
spec=importlib.util.spec_from_file_location("lock_frontier_regression",tool)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
e.c.installation=lambda *_args,**_kwargs:{"SYNTHETIC_INSTALLATION_SEAM":True}
original=e.b.locked
@contextmanager
def schedule_only(path):
    Path(ready).write_text("about to acquire original bf lock")
    with original(path):yield
e.b.locked=schedule_only
print(json.dumps(e.mark_dispatch(root,"scope-one-p1",bootstrap)))
'''
    import deck_master
    command = [sys.executable, "-I", "-B", "-c", child_source, str(SCRIPT), str(ledger), boot["path"], str(ready_path), deck_master.__file__]
    with e.b.locked(ledger):
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready_path.exists():
                if child.poll() is not None or time.monotonic() >= deadline:
                    raise AssertionError("child did not reach the unchanged shared lock")
                time.sleep(.01)
            if legacy_append:
                e.save(ledger / "dispatches/unexpected-legacy.json", {"evidence_kind": e.ENGINEERING,
                    "scenario": "Synthetic unexpected old writer under same lock; no actual tool call", "outcome": "unknown"})
        except BaseException:
            child.kill(); child.communicate(timeout=5); raise
    stdout, stderr = child.communicate(timeout=15)
    if legacy_append:
        assert child.returncode != 0 and b"legacy writer appended/changed" in stderr
        assert not list((ledger / "event-dispatches").glob("*.json"))
        assert not (e._call_dir(ledger, "scope-one-p1") / "dispatch-mark.json").exists()
        assert not stdout
    else:
        assert child.returncode == 0, stderr.decode()
        assert json.loads(stdout)["cost"] == "CHARGED_PENDING_ROOT_TOOL_OBSERVATION"
        assert e.inspect_accounting(ledger)["total_charged"] == 1


def test_legacy_unknown_charge_is_not_reset_and_frontier_tamper_is_refused(tmp_path, monkeypatch):
    # Explicit synthetic historical dispatch, not a real/native tool record.
    dispatch = {"case": "Q4", "whole_run_id": "synthetic-original-flow", "repetition": 1, "arm": "B", "page_id": "p1",
        "task_id": "old-task", "request_id": "old-generation-request", "authorization_id": "old-auth", "attempt_id": "old-attempt", "outcome": "unknown"}
    mapping = {"scope_slot": "scope-one", "leaf_id": "scope-one-p1", "project_id": "old-project", "project": "/synthetic/historical",
        "actual_request_id": "old-request", "instruction_occurrence_sha256": "old-trigger", "budget_root_id": "old-budget", "allowance_id": "old-allowance"}
    ledger, _, _ = setup(tmp_path, monkeypatch, legacy=True, prior_dispatch=(dispatch, mapping))
    original = {p.name: p.read_bytes() for p in (ledger / "dispatches").glob("*.json")}
    assert e.inspect_accounting(ledger)["total_charged"] == 1
    assert e.inspect_accounting(ledger)["legacy_charged"] == 1
    with pytest.raises(e.ImageEventError, match="cap exhausted"):
        e._caps(e.read(tmp_path / "policy.json"), e.inspect_accounting(ledger)["all_rows"], {**e.inspect_accounting(ledger)["all_rows"][0], "leaf_id": "another"})
    assert original == {p.name: p.read_bytes() for p in (ledger / "dispatches").glob("*.json")}
    frontier = e.read(ledger / "event-legacy-frontier.json"); frontier["charged_rows"] = []
    (ledger / "event-legacy-frontier.json").write_bytes(e.c.encoded(frontier))
    with pytest.raises(e.ImageEventError, match="legacy scope mappings"):
        e.inspect_accounting(ledger)


def test_sealed_observation_must_keep_its_global_charge(flow, tmp_path, monkeypatch):
    ledger, config, boot, *_ = ready(tmp_path, monkeypatch, flow)
    e.mark_dispatch(ledger, "scope-one-p1", boot["path"])
    cb = callback(tmp_path, config, ledger, "scope-one-p1")
    e.seal_observation(ledger, "scope-one-p1", cb["path"], boot["path"])
    # Explicit storage-corruption seam, never a supported reset operation.
    (ledger / "event-dispatches/000001.json").write_bytes(b'{}\n')
    assert not e.RootEventProvider(ledger, config, "scope-one-p1").health()
    with pytest.raises(e.ImageEventError, match="global charge"):
        e.settle(ledger, "scope-one-p1")


@pytest.mark.parametrize("which", ["global", "parent", "scope", "leaf", "allowance"])
def test_independent_nonfungible_caps(which):
    policy = {"total_call_cap": 2, "parents": [{"parent_id": "p", "max_calls": 2}], "scopes": [{"scope_slot": "s", "max_calls": 2}]}
    old = {"parent_id": "p", "scope_slot": "s", "leaf_id": "l1", "attempt_id": "a1", "task_id": "t1", "allowance_id": "c1", "project_id": "pr"}
    new = {**old, "leaf_id": "l2", "attempt_id": "a2", "task_id": "t2"}
    if which == "global": policy["total_call_cap"] = 1
    if which == "parent": policy["parents"][0]["max_calls"] = 1
    if which == "scope": policy["scopes"][0]["max_calls"] = 1
    if which == "leaf": new["leaf_id"] = "l1"
    if which == "allowance": new["task_id"] = "t1"
    with pytest.raises(e.ImageEventError): e._caps(policy, [old], new)


def test_shared_parent_child_authorizations_not_duplicated_and_real_new_event_allowed():
    old = {"parent_id": "p", "case": "Q3", "project": "/synthetic/p", "scope_slot": "s1", "page_label": "p1", "page_id": "p1", "checkpoint": "Q3", "project_id": "pr", "actual_request_id": "rq1", "instruction_occurrence_sha256": "o1", "authorization_id": "child-one", "budget_root_id": "shared"}
    child = {**old, "page_label": "p2", "page_id": "p2", "authorization_id": "child-two"}
    e._check_events([old], child)
    renamed = {**old, "scope_slot": "fake-new"}
    with pytest.raises(e.ImageEventError): e._check_events([old], renamed)
    actual_new = {**old, "scope_slot": "s2", "actual_request_id": "rq2", "instruction_occurrence_sha256": "o2", "authorization_id": "real-new"}
    e._check_events([old], actual_new)
    with pytest.raises(e.ImageEventError): e._check_events([old], {**actual_new, "page_id": "renamed-page"})


def test_exact_literal_primitives_are_reused_not_reimplemented():
    assert e.b.actual_arguments.__module__ == e.b.__name__
    assert e.b.validate_callback.__module__ == e.b.__name__
    assert e.digest(Path(e.b.__file__).read_bytes()) == e.PRIMITIVES_SHA
    assert e.digest(Path(e.c.__file__).read_bytes()) == e.COMMON_SHA


def test_m02_same_project_sequential_two_uses_and_q4_independent_checkpoints():
    # These are counter identities, not claimed complete M02/native results.
    old = {"parent_id": "m02", "case": "M02", "project": "/synthetic/m02", "project_id": "one-project",
        "scope_slot": "live", "checkpoint": "live", "actual_request_id": "live-request",
        "instruction_occurrence_sha256": "live-event", "authorization_id": "live-auth", "budget_root_id": "live-parent",
        "page_id": "live-01", "page_label": "live-01"}
    read = {**old, "scope_slot": "read", "checkpoint": "read", "actual_request_id": "read-request",
        "instruction_occurrence_sha256": "read-event", "authorization_id": "read-auth", "budget_root_id": "read-parent",
        "page_id": "read-01", "page_label": "read-01"}
    e._check_events([old], read)
    with pytest.raises(e.ImageEventError): e._check_events([old], {**read, "project": "/synthetic/copied"})
    with pytest.raises(e.ImageEventError): e._check_events([old], {**read, "parent_id": "renamed-parent"})
    with pytest.raises(e.ImageEventError): e._check_events([old], {**read, "parent_id": "renamed-parent", "project": "/synthetic/copied"})
    q4 = {**old, "parent_id": "q4", "case": "Q4", "checkpoint": "Q4A"}
    with pytest.raises(e.ImageEventError): e._check_events([q4], {**read, "parent_id": "q4", "case": "Q4", "checkpoint": "Q4B"})


def test_real_sdk_shared_two_page_parent_and_m02_four_leaf_counter(tmp_path, monkeypatch):
    """Four fixed neutral Pages isolate accounting, not M02 variant effects.

    Two actual public Requests/grants, actual claimed Tasks/frozen inputs/begun
    Attempts, synthetic dispatch markers and host-reported consumed settlements.
    There are zero external/native calls and no qualified artifact claim.
    """
    from deck_master import collaboration, generation, service, tasks, eligibility
    from deck_master.store import Store
    from rc3_fixtures import public_project, settle_fidelity_review, authorize_scope, evidence_for
    ids = ["live-01", "live-02", "read-01", "read-02"]
    def scope(pids):
        return {"subject": "deck", "page_ids": pids, "page_manifest_ref": None, "external_artifact_ref": None,
            "layers": ["narrative", "plan", "page_copy", "speech", "design", "blueprint", "svg", "review", "output"],
            "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "working"}
    draft = {"pages": [{"schema_version": "deck_page_package.v2", "page_id": pid,
        "customer_visible": {"title": "Synthetic neutral " + pid, "body_blocks": []},
        "visual_spec": {"intent": "L1 only", "reference_mode": "new_design"}} for pid in ids]}
    project = public_project(tmp_path, create_input={"brief": "Explicit synthetic accounting experiment"}, manuscript=draft,
        request_input={"intent": "full_deck", "content_intent": None, "scope": scope(ids),
            "instruction_evidence": {"kind": "host_attested_instruction", "text": "Synthetic live event", "source_locator": "L1:event-live"}})["project"]
    store = Store(project)
    parent = {"parent_id": "original-flow", "matrix_slot": "M02", "case": "M02", "whole_run_id": "one-m02-run", "repetition": 1, "arm": "B", "max_calls": 4}
    ledger, config, boot = setup(tmp_path, monkeypatch, parent=parent, scope_specs=[("live", "live", ids[:2], "Synthetic live event"), ("read", "read", ids[2:], "Synthetic read event")])
    for use, pids in (("live", ids[:2]), ("read", ids[2:])):
        if use == "read":
            doc = store.load_document()
            collaboration.start_request(project, input={"intent": "full_deck", "content_intent": None, "scope": scope(ids),
                "replace_request_id": doc["collaboration"]["request"]["request_id"], "instruction_evidence": evidence_for(project, text="Synthetic read event", locator="L1:event-read")},
                base_revision=doc["revision_id"], operation_id="actual-new-read-request")
        settle_fidelity_review(project, page_ids=ids, execution_ref="L1-independent-" + use, scenario="Synthetic fixed Pages")
        authorize_scope(project, actions=["dispatch.blueprint", "allowance.allocate", "task.start", "call.begin", "result.accept"], scope=scope(pids),
            max_external_calls=2, max_candidate_count=2, adoption_policy="within_scope", evidence=evidence_for(project, text="Bounded synthetic two Page " + use, locator="L1:grant-" + use))
        opened = []
        for pid in pids:
            doc = store.load_document(); entry = next(row for row in doc["pages"] if row["page_id"] == pid)
            opened.append(service.open_blueprint_task(store, doc, entry))
        for task in opened:
            pid = task["scope_pages"][0]
            service.task_start(project, task_id=task["task_id"], execution_ref="L1-" + pid, supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
            value = generation.prepared_input(store, store.load_document(), task)
            frozen = generation.freeze(project, task_id=task["task_id"], input=value, base_revision=store.current_revision_id(), operation_id="freeze-" + pid)
            args = {"task_id": task["task_id"], "allowance_id": task["call_allowances"][0]["allowance_id"], "execution_ref": "L1-" + pid, "request_id": frozen["request_id"]}
            binding = handoff(tmp_path, config, (project, store, task, None), {"allowance_id": args["allowance_id"]}, slot=use)
            assert e.guard_call_begin(config, binding, pid, args)["attempt_id"] is None
            attempt = tasks.call_begin(store, **args); binding["attempt_id"] = attempt["attempt_id"]
            actual = e.inspect_own_rights(config, binding, pid)
            # Both real reserved child calls share a bounded2 parent. Zero
            # remaining does not forbid its own already reserved final call.
            assert actual["parent_budget"]["ceiling"] == 2
            assert actual["parent_budget"]["remaining"] == 0
            e.prepare_page_call(ledger, binding, use + "-" + pid, attempt["attempt_id"])
            e.mark_dispatch(ledger, use + "-" + pid, boot["path"])
            tasks.call_settle(store, task_id=task["task_id"], allowance_id=args["allowance_id"], attempt_id=attempt["attempt_id"], outcome="consumed", report_bytes=b'{"source":"explicit_synthetic_host_report_no_native"}')
        authref = e.c.task_for(store, opened[-1]["task_id"])["collaboration_binding"]["authorization_ref"]
        assert eligibility.authorization_budget(store, store.load_document(), authref)["used"] == 2
    counted = e.inspect_accounting(ledger)
    assert counted["total_charged"] == 4 and counted["by_parent"] == {"original-flow": 4}
    assert counted["by_scope"] == {"live": 2, "read": 2}


def test_same_real_page_new_instruction_request_and_right_use_one_parent(flow, tmp_path, monkeypatch):
    from deck_master import generation, service, tasks
    from rc3_fixtures import settle_fidelity_review, authorize_scope, evidence_for
    first_instruction = fixture_request_instruction(flow)
    ledger, config, boot = setup(tmp_path, monkeypatch, scope_specs=[
        ("first", "Q4B", ["p1"], first_instruction), ("second", "Q4B", ["p1"], "Synthetic second explicit event")])
    project, store, task, _ = flow
    start(flow); frozen = freeze(flow); attempt = begin(flow, frozen)
    binding = handoff(tmp_path, config, flow, attempt, slot="first")
    e.prepare_page_call(ledger, binding, "first-p1", attempt["attempt_id"])
    e.mark_dispatch(ledger, "first-p1", boot["path"])
    cb = callback(tmp_path, config, ledger, "first-p1")
    e.seal_observation(ledger, "first-p1", cb["path"], boot["path"]); e.settle(ledger, "first-p1")
    assert accept(flow, frozen, attempt, Path(e.read(cb["path"])["original_png"]["path"]).read_bytes())["status"] == "accepted"
    first = e.inspect_accounting(ledger)["all_rows"][0]
    current_instruction(flow, "Synthetic second explicit event")
    settle_fidelity_review(project, page_ids=["p1"], execution_ref="L1-second-event-review", scenario="Explicit synthetic new request")
    doc = store.load_document(); scope = doc["collaboration"]["request"]["scope"]
    authorize_scope(project, actions=["dispatch.blueprint", "allowance.allocate", "task.start", "call.begin", "result.accept"], scope=scope,
        max_external_calls=1, max_candidate_count=1, adoption_policy="within_scope", evidence=evidence_for(project, text="Synthetic new one-call right", locator="L1:second-event-right"))
    task = service.open_blueprint_task(store, store.load_document(), store.load_document()["pages"][0])
    service.task_start(project, task_id=task["task_id"], execution_ref="L1-second-event-author", supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
    frozen = generation.freeze(project, task_id=task["task_id"], input=generation.prepared_input(store, store.load_document(), task), base_revision=store.current_revision_id(), operation_id="freeze-second-event")
    attempt = tasks.call_begin(store, task_id=task["task_id"], allowance_id=task["call_allowances"][0]["allowance_id"], execution_ref="L1-second-event-author", request_id=frozen["request_id"])
    binding = handoff(tmp_path, config, (project, store, task, None), attempt, slot="second")
    e.prepare_page_call(ledger, binding, "second-p1", attempt["attempt_id"]); e.mark_dispatch(ledger, "second-p1", boot["path"])
    rows = e.inspect_accounting(ledger)["all_rows"]
    assert len(rows) == 2 and rows[1]["page_id"] == first["page_id"] == "p1"
    assert rows[1]["parent_id"] == first["parent_id"]
    for key in ("actual_request_id", "authorization_id", "attempt_id", "instruction_occurrence_sha256"):
        assert rows[1][key] != first[key]
