"""S11 explicit isolated carrier. All Host/native/history fixtures are SYNTHETIC.

Public local SDK transactions are real. No model/image service is called; the
historical cost seed is a mechanical fixture, never a claim of 14 real actors.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import uuid

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/m02_runtime_continuation.py"
spec = importlib.util.spec_from_file_location("s11_cases", TOOL)
s11 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s11)
m, c = s11.m, s11.c


def seed(root):
    from deck_master import service
    from deck_master.store import Store
    from test_rc3_m02_recorder import common_argument, declare_and_start, produce_use_content
    import deck_master
    source = c.write_once(root / "material.txt", b"SYNTHETIC engineering: record an unknown field; no measured outcome.\n")
    grammar = c.save(root / "grammar.json", {"SYNTHETIC_ENGINEERING": True})
    excluded = c.save(root / "excluded.json", {"status": "FROZEN", "excluded_identities": ["/root/preparer"]})
    roles = m.ROLES
    scopes = {}
    limits = {"common": [5, 0, 0, 0, 0, 0], "live": [5, 3, 1, 1, 12, 8], "read": [5, 3, 1, 1, 12, 8], "live_notes_edit": [1, 0, 1, 0, 0, 0]}
    for phase in m.PHASES:
        instruction = c.write_once(root / (phase + ".txt"), ("SYNTHETIC nonhuman M02 scope " + phase).encode())
        scopes[phase] = {"instruction": instruction, "page_ids": [] if phase == "common" else ["r1" if phase == "read" else "p1"],
            "native_limits": dict(zip(roles, limits[phase])), "max_external_calls": 2 if phase in {"live", "read"} else 0,
            "max_candidates": 2 if phase in {"live", "read"} else 0, "notes_policy": "pure_reading" if phase == "read" else "both", "input_patch": None}
    old = {"experiment_id": "synthetic-s11", "materials": [source], "scopes": scopes,
        "grammar": grammar, "protocol": grammar, "exposure_registry": excluded, "technical_supplements": [],
        "installation": {"module_file": deck_master.__file__, "python": "/synthetic/obsolete/python", "source_sha": "obsolete-engineering-history"}}
    oldreg = c.save(root / "old-registration.json", old)
    historical_root = root / "historical"
    state = {"format": "rc3-m02-run.v1", "arm": "B", "case": "M02", "experiment_id": old["experiment_id"],
        "campaign": str(root), "project": str(root / "project"), "materials": [source],
        "budget": {r: sum(v["native_limits"][r] for v in scopes.values()) for r in roles}, "registration_sha256": c.digest(c.encoded(old))}
    oldrun = c.save(historical_root / "run.json", state); hist = c.Journal(historical_root)
    hist.append("m02_initialized", state); hist.append("m02_phase_started", {"phase": "common"})
    service.create(state["project"], brief="SYNTHETIC sequential mixed use", sources=[source["path"]], presentation_mode="mixed", page_limit=2)
    store = Store(state["project"]); hist.append("m02_project_bound", {"project_id": store.load_document()["project_id"]})
    trigger = c.save(root / "trigger.json", {"assurance": "host_attested", "actual_trigger_satisfied": True, "source_observations": [grammar], "SYNTHETIC_ONLY": True})
    m.instruction(hist, state, old, "common", trigger["path"])
    common_argument(hist, state, old)
    args = declare_and_start(hist, state, old, trigger)
    args["input"]["scope"]["layers"] = ["narrative", "plan", "page_copy", "speech", "design", "blueprint", "svg", "review", "output"]
    m.start_variant(hist, state, old, "live", args)
    produce_use_content(state["project"], store, "live")
    # Explicit cost/history fixture: no actual native invocation or admission.
    recorded = [("common", "initial_writer")] * 2 + [("live", "initial_writer"), ("live", "feedback")] + [("live", "production")] * 7 + [("live", "production_review")] * 3
    for ordinal, (phase, role) in enumerate(recorded, 1):
        row = {"phase": phase, "role": role, "ordinal": ordinal, "stage": "old-" + str(ordinal),
            "executor": "synthetic-l1-host" if ordinal <= 3 else "exec-independent" if ordinal == 4 else "/root/old-" + str(ordinal), "within_budget": True, "SYNTHETIC_BASELINE_NO_NATIVE": True}
        hist.append("native_begun", row); hist.append("m02_native_started", row)
    doc = store.load_document()
    cfg = {"format": s11.FORMAT, "status": s11.ENGINEERING, "companion_sha256": c.digest(TOOL.read_bytes()),
        "common": c.reference(m.SOURCE), "m02_recorder": c.reference(s11.M02), "project": state["project"],
        "experiment_id": old["experiment_id"], "supplemental_validation_id": "synthetic-s11-successor", "runtime_epoch": "1.0.0rc3",
        "group_id": doc["collaboration"]["request"]["variant"]["group_id"], "fixed_narrative": doc["narrative"],
        "predecessor": {"run": oldrun, "registration": oldreg, "event_count": len(hist.events()), "frontier": c.reference(historical_root / "journal" / f"{len(hist.events()):06d}.json")},
        "protected_refs": [oldrun, oldreg, source], "initial_content": s11.content_identity(doc), "initial_pages": doc["pages"], "initial_outputs": doc["outputs"], "blocked_stage": "old-11",
        "auxiliary_executions": [{"executor": "/root/aux-" + str(i), "phase": "live", "role": "production_review", "evidence": grammar} for i in (56, 78)],
        "independent_reviews": {k: grammar for k in ("S07", "S10", "installation", "companion")},
        **{k: deepcopy(old[k]) for k in ("scopes", "materials", "grammar", "protocol", "exposure_registry", "technical_supplements")},
        "installation": {"source_sha": "new-engineering-runtime", "python": sys.executable, "module_file": deck_master.__file__}}
    cfg["protected_refs"] += s11.critical_refs(cfg, state)
    bind_admission(root, cfg)
    rows = s11.chain(historical_root); successor = root / "successor"; c.save(successor / "registration.json", cfg)
    state = {**state, "campaign": str(successor), "project_id": doc["project_id"], "runtime_epoch": cfg["runtime_epoch"], "registration_sha256": c.digest(c.encoded(cfg))}
    c.save(successor / "run.json", state); j = s11.Successor(successor, rows); j.append("m02_successor_initialized", state)
    c.save(root / "identity.json", {"isolated": sys.flags.isolated, "dont_write_bytecode": sys.dont_write_bytecode,
        "module": deck_master.__file__, "project": state["project"], "SYNTHETIC_ONLY": True})
    return j, state, cfg


def bind_admission(root, cfg):
    path = root / ("admission-" + uuid.uuid4().hex + ".json")
    cfg["admission"] = c.save(path, {"format": "rc3-m02-runtime-admission.v1", "observer": "/root", "status": cfg["status"],
        "registration_binding": s11.binding(cfg), "administrative_only": True, "no_new_image_or_direction_authority": True,
        "source_observations": [cfg["grammar"]], "SYNTHETIC_NOT_FORMAL_ADMISSION": True})


def proof(root, j, state, cfg, command, **extra):
    bootstrap = c.save(root / ("bootstrap-" + uuid.uuid4().hex + ".json"), {"observation_kind": c.OBSERVER_KIND,
        "assurance": "host_attested", "tool": "collaboration.list_agents", "observed_running_agents": ["/root"], "observed_at_utc": c.now(), "SYNTHETIC_ONLY": True})
    doc = c.store_for(state).load_document()
    barrier = c.save(root / ("barrier-" + uuid.uuid4().hex + ".json"), {"format": "rc3-m02-exclusive-root-barrier.v1", "observer": "/root", "assurance": "host_attested", "command": command,
        "registration_binding": s11.binding(cfg), "project_id": doc["project_id"], "base_revision": doc["revision_id"],
        "successor_frontier": len(j.local.events()), "old_write_routes_retired": True, "all_other_writers_stopped": True,
        "exclusive_until_command_completed": True, "observed_at_utc": c.now(), "source_observations": [cfg["grammar"]], "bootstrap": bootstrap, **extra})
    return {"command": command, "bootstrap": bootstrap["path"], "barrier": barrier["path"]}


@pytest.mark.parametrize("fault", ["helper", "companion", "predecessor", "frontier", "caps", "instruction", "N", "review", "phase", "protected-object"])
def test_registration_refuses_exact_drift_before_any_successor_sdk_write(tmp_path, fault):
    j, state, cfg = seed(tmp_path); before = c.store_for(state).current_revision_id()
    bad = deepcopy(cfg)
    if fault == "helper": bad["common"]["sha256"] = "0" * 64
    if fault == "companion": bad["companion_sha256"] = "0" * 64
    if fault == "predecessor": bad["predecessor"]["registration"]["sha256"] = "0" * 64
    if fault == "frontier": bad["predecessor"]["event_count"] += 1
    if fault == "caps": bad["scopes"]["live"]["native_limits"]["production"] += 1
    if fault == "instruction": bad["scopes"]["read"]["instruction"] = cfg["scopes"]["live"]["instruction"]
    if fault == "N": bad["fixed_narrative"] = None
    if fault == "protected-object": bad["protected_refs"].pop()
    if fault == "review": bad["independent_reviews"]["S10"]["sha256"] = "0" * 64
    if fault == "phase":
        c.Journal(Path(cfg["predecessor"]["run"]["path"]).parent).append("m02_phase_started", {"phase": "read"})
    with pytest.raises((s11.Error, KeyError)): s11.validate(bad)
    assert c.store_for(state).current_revision_id() == before
    assert not any(e["kind"] == "sdk_intent" for e in j.local.events())


def test_registration_positive_is_explicit_synthetic_and_history_is_not_copied(tmp_path):
    j, state, cfg = seed(tmp_path)
    assert s11.validate(cfg)[0]["project"] == state["project"]
    assert s11.costs(j, cfg)["whole"] == 16
    assert s11.costs(j, cfg)["by_phase_role"]["live"]["production"] == 7
    assert s11.costs(j, cfg)["by_phase_role"]["live"]["production_review"] == 5
    assert len(j.local.events()) == 1
    assert not any(e["kind"] == "native_begun" for e in j.local.events())


@pytest.mark.parametrize("fault", ["revision", "frontier", "command", "retired", "exclusive", "stale", "bootstrap", "group"])
def test_current_exclusive_barrier_and_effective_root_context(tmp_path, fault):
    from argparse import Namespace
    j, state, cfg = seed(tmp_path)
    kwargs = proof(tmp_path, j, state, cfg, "continue-current")
    value = c.read(kwargs["barrier"])
    if fault == "revision": value["base_revision"] = "wrong"
    if fault == "frontier": value["successor_frontier"] += 1
    if fault == "command": value["command"] = "assemble-existing-live"
    if fault == "retired": value["old_write_routes_retired"] = False
    if fault == "exclusive": value["exclusive_until_command_completed"] = False
    if fault == "stale": value["observed_at_utc"] = "2000-01-01T00:00:00+00:00"
    if fault == "bootstrap": value["bootstrap"]["sha256"] = "0" * 64
    if fault == "group": cfg["group_id"] = "foreign"
    ref = c.save(tmp_path / "bad-barrier.json", value); kwargs["barrier"] = ref["path"]
    before = c.store_for(state).current_revision_id()
    with pytest.raises(s11.Error): s11.execute(j, state, cfg, Namespace(**kwargs))
    assert c.store_for(state).current_revision_id() == before
    assert not j.unfinished()


def test_bound_context_is_real_and_barrier_cannot_replay(tmp_path):
    from deck_master import content_review
    j, state, cfg = seed(tmp_path)
    kwargs = proof(tmp_path, j, state, cfg, "inspect-transition")
    assert not content_review.reviewer_capabilities()["independent_review_receipts"]
    with c.native_runtime(kwargs["bootstrap"]):
        assert content_review.reviewer_capabilities()["independent_review_receipts"]
        s11.barrier(j, state, cfg, "inspect-transition", kwargs["barrier"])
        with pytest.raises(s11.Error): s11.barrier(j, state, cfg, "inspect-transition", kwargs["barrier"])
    assert not content_review.reviewer_capabilities()["independent_review_receipts"]


def blocked_task(j, state, cfg):
    """Explicit historical Task fixture ID, not a production alias parameter."""
    from deck_master import service
    from deck_master.models import bump_revision
    store = c.store_for(state)
    task = service.open_host_task(store, kind="repair", page_ids=["p1"], instruction="SYNTHETIC old conversion task")
    doc = store.load_document(); updated = deepcopy(task)
    updated.update(task_id=s11.TASK, status="running", execution_ref=s11.ACTOR)
    ref = store.put_json_object(updated)
    new = bump_revision(doc, {"operation_id": "seed-obsolete", "kind": "task_update", "description": "Explicit synthetic historical ID", "read_set": []})
    new["tasks"] = [ref if store.read_object_json(r)["task_id"] == task["task_id"] else r for r in doc["tasks"]]
    store.commit_change(base_revision=doc["revision_id"], document=new, operation_id="seed-obsolete")
    cfg["blocked_task"] = updated
    return updated


@pytest.mark.parametrize("fault", [None, "active", "unknown", "raw", "inflight", "external-unknown", "attempt", "scope", "terminal", "changed-task", "content"])
def test_only_genuine_stopped_exact_task_can_cancel_and_late_adoption_refuses(tmp_path, fault):
    from deck_master import service
    from deck_master.tasks import TaskConflict
    j, state, cfg = seed(tmp_path); task = blocked_task(j, state, cfg)
    evidence = {"producer_executor": s11.ACTOR, "producer_status": "completed", "producer_raw": None, "external_inflight": 0, "external_unknown": 0, "external_attempts": 0}
    if fault in {"active", "unknown"}: evidence["producer_status"] = fault
    if fault == "raw": evidence["producer_raw"] = cfg["grammar"]
    if fault == "inflight": evidence["external_inflight"] = 1
    if fault == "external-unknown": evidence["external_unknown"] = 1
    if fault == "attempt": evidence["external_attempts"] = 1
    if fault == "scope": cfg["scopes"]["live"]["page_ids"] = ["elsewhere"]
    if fault == "changed-task": cfg["blocked_task"] = {**task, "instruction": "changed"}
    if fault == "content": cfg["initial_content"]["content_plan"] = None
    if fault == "terminal": service.task_cancel(state["project"], task_id=s11.TASK, reason="synthetic previous cancellation")
    before = c.store_for(state).load_document()
    if fault:
        with pytest.raises(s11.Error): s11.cancel_blocked(j, state, cfg, evidence)
        assert c.store_for(state).load_document() == before
    else:
        result = s11.cancel_blocked(j, state, cfg, evidence)
        assert result["status"] == "cancelled"
        assert s11.content_identity(c.store_for(state).load_document()) == cfg["initial_content"]
        with pytest.raises(TaskConflict, match="after cancellation"):
            service.accept_result(state["project"], task_id=s11.TASK, operation_id=task["operation_id"], produced_against=task["produced_against"], result_payload={"kind": "repair", "files": []})
        assert c.task_for(c.store_for(state), s11.TASK)["status"] == "cancelled"
        assert not j.unfinished()


def test_old_claim_and_raw_and_actor_never_transfer_to_successor(tmp_path):
    from test_rc3_campaign_controller import fake_invocation
    j, state, cfg = seed(tmp_path); task = blocked_task(j, state, cfg)
    with pytest.raises(s11.Error): s11.prepare(j, state, cfg, "new", s11.TASK, "production")
    with pytest.raises(s11.Error): s11.current_stage(j, state, cfg, "old-11", 11)
    dispatch = {"stage": "synthetic-dispatch", "role": "production_review", "task_id": "synthetic-unit", "project_id": state["project_id"], "method_release": {}, "m02_phase": "live"}
    c.save(j.root / "stages/synthetic-dispatch/dispatch.json", dispatch); j.append("stage_prepared", dispatch)
    for actor in ("/root/old-5", "/root/aux-56"):
        with pytest.raises(s11.Error): s11.begin(j, state, cfg, dispatch["stage"], fake_invocation(tmp_path, dispatch, actor))
    assert s11.costs(j, cfg)["whole"] == 16


def test_actual_invocations_inherit_review5of8_and_overrun_stays_counted(tmp_path):
    from test_rc3_campaign_controller import fake_invocation
    j, state, cfg = seed(tmp_path)
    dispatch = {"stage": "counted", "role": "production_review", "task_id": "synthetic-unit", "project_id": state["project_id"], "method_release": {}, "m02_phase": "live"}
    c.save(j.root / "stages/counted/dispatch.json", dispatch); j.append("stage_prepared", dispatch)
    outcomes = [s11.begin(j, state, cfg, "counted", fake_invocation(tmp_path, dispatch, "/root/fresh-" + str(i))) for i in range(4)]
    assert [row["within_budget"] for row in outcomes] == [True, True, True, False]
    assert s11.costs(j, cfg)["whole"] == 20
    assert s11.costs(j, cfg)["by_phase_role"]["live"]["production_review"] == 9
    assert len(m.events(s11.SuccessorView(j.historical), "native_begun")) == 14


def test_unknown_sdk_commit_is_never_replayed_or_refunded(tmp_path):
    j, state, cfg = seed(tmp_path)
    with pytest.raises(RuntimeError): c.record_sdk(j, "stages.assemble", {"operation_id": str(uuid.uuid4())}, lambda: (_ for _ in ()).throw(RuntimeError("lost acknowledgment")), key="lost")
    assert s11.costs(j, cfg)["sdk_attempts_successor"] == 1
    with pytest.raises(s11.Error): c.record_sdk(j, "service.continue_project", {}, lambda: {})
    with pytest.raises(Exception) as error: s11.query(j, state, cfg, "lost")
    assert getattr(error.value, "error_code", None) == "operation_not_found"
    assert "lost" in j.unfinished()
    assert s11.costs(j, cfg)["sdk_attempts_successor"] == 1
    assert s11.costs(j, cfg)["sdk_queries_successor"] == 1


@pytest.mark.parametrize("command", ["assemble", "export", "read", "notes"])
def test_original_gates_block_fake_assembly_export_and_future_triggers(tmp_path, command):
    j, state, cfg = seed(tmp_path); before = c.store_for(state).load_document()
    if command == "assemble":
        j.append("m02_obsolete_task_cancelled", {"SYNTHETIC_PREREQUISITE_ONLY": True})
        with pytest.raises(s11.Error, match="preproduction"): s11.assemble(j, state, cfg, str(uuid.uuid4()))
    if command == "export":
        with pytest.raises(s11.Error, match="assembly"): s11.export_current(j, state, cfg, {})
    if command in {"read", "notes"}:
        scope = "read" if command == "read" else "live_notes_edit"
        trigger = c.save(tmp_path / "future-trigger.json", {"assurance": "host_attested", "actual_trigger_satisfied": True, "source_observations": [cfg["grammar"]]})
        with pytest.raises(s11.Error): m.instruction(j, state, cfg, scope, trigger["path"])
    assert c.store_for(state).load_document() == before


def test_query_rejects_historical_or_arbitrary_identity(tmp_path):
    j, state, cfg = seed(tmp_path)
    for key in ("historical", "arbitrary", "service.task_cancel"):
        with pytest.raises(s11.Error): s11.query(j, state, cfg, key)
    assert not any(x["kind"] == "m02_query_intent" for x in j.local.events())


def test_actual_cancel_commit_lost_ack_is_recovered_without_second_cancel(tmp_path):
    from deck_master import service
    j, state, cfg = seed(tmp_path); blocked_task(j, state, cfg)
    def lost_ack():
        service.task_cancel(state["project"], task_id=s11.TASK, reason="SYNTHETIC exact technical lost-ack test")
        raise ConnectionError("actual commit, simulated transport acknowledgment loss")
    with pytest.raises(ConnectionError):
        c.record_sdk(j, "service.task_cancel", {"task_id": s11.TASK, "reason": "SYNTHETIC exact technical lost-ack test"}, lost_ack, key="cancel-lost")
    assert c.task_for(c.store_for(state), s11.TASK)["status"] == "cancelled"
    result = s11.query(j, state, cfg, "cancel-lost")
    assert result["status"] == "cancelled" and not j.unfinished()
    assert s11.costs(j, cfg)["sdk_attempts_successor"] == 1
    assert s11.costs(j, cfg)["sdk_queries_successor"] == 1
    assert len(m.events(j, "m02_obsolete_task_cancelled")) == 1
