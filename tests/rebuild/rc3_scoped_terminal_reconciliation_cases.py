"""ENGINEERING_ONLY neutral public SDK trajectories; no native/image PASS.

The source test suite bypasses only installed-package admission. The separate
managed trace verifies real own Python -I -B and installation without that seam.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import uuid

import pytest

from deck_master import changes, collaboration, eligibility, generation, operations, run_desk, service, tasks, view
from deck_master.store import Store
from rc3_fixtures import authorize_scope, evidence_for, settle_fidelity_review, source_snapshot
from test_rc3_supplementary_recorder import page

SCRIPT = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/scoped_terminal_reconciliation.py"
spec = importlib.util.spec_from_file_location("rc3_s05_test", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
s, c = m.s, m.c


def setup(tmp_path, monkeypatch, *, committed=False, inflight=False):
    import deck_master
    monkeypatch.setattr(c, "installation", lambda *_a, **_k: {"SYNTHETIC_INSTALLATION_ADMISSION_SEAM": True})
    instruction = c.write_once(tmp_path / "instruction.txt", b"ENGINEERING_ONLY: one neutral p5 page. No images or grant.")
    material = c.save(tmp_path / "p5.json", page("p5"))
    tech = c.save(tmp_path / "technical.json", {"ENGINEERING_ONLY": True})
    exposure = c.save(tmp_path / "exposure.json", {"status": "FROZEN", "excluded_identities": ["/engineering/preparer"]})
    installation = {"python": sys.executable, "module_file": deck_master.__file__, "source_sha": "synthetic-source-env",
                    "source_tree": "synthetic", "manifest": tech, "wheel_sha256": "synthetic"}
    row = {"profile": "q3q4", "case": "Q4", "checkpoint": "Q4A", "matrix_slot": "05", "whole_run_id": "engineering-s05",
        "repetition": 1, "arm": "B", "scope_slot": "local-p5", "project": str(tmp_path / "project"), "project_mode": "new",
        "page_ids": ["p5"], "instruction": instruction, "materials": [material], "technical_supplements": [],
        "limits": {"writer": 0, "review": 0, "sdk": 90, "render": 0}, "native_limits": {r: 0 for r in s.ROLES}}
    config = {"format": s.FORMAT, "status": s.ENGINEERING, "recorder_sha256": m.SCOPED_SHA,
        "ledger_root": str(tmp_path / "campaign"), "common": c.reference(s.SOURCE), "protocol": tech, "policy_epoch": tech,
        "admission_review": tech, "grammar": tech, "exposure_registry": exposure,
        "installations": {"B": installation}, "scopes": {"local": row}}
    reg = c.save(tmp_path / "config.json", config)
    s.freeze(reg["path"], tmp_path / "campaign")
    state = s.init(tmp_path / "campaign", tmp_path / "run", "local")
    root = Path(state["root"])
    text = Path(instruction["path"]).read_text()
    request = {"intent": "edit", "content_intent": None,
        "scope": {"subject": "pages", "page_ids": ["p5"], "page_manifest_ref": None, "external_artifact_ref": None,
            "layers": ["page_copy", "speech", "design", "blueprint", "svg", "review", "output"],
            "allow_page_membership_change": False, "allow_page_order_change": False, "purpose": "working"},
        "instruction_evidence": {"kind": "host_attested_instruction", "text": text, "source_locator": "ENGINEERING_ONLY"}}
    s.operate(root, "service.create", {"brief": text, "sources": [material["path"]],
        "draft": {"pages": [page("p5")]}, "request_input": request})
    store = Store(state["project"])
    if committed or inflight:
        scope = store.load_document()["collaboration"]["request"]["scope"]
        authorize_scope(state["project"], actions=["change.commit"] if committed else ["dispatch.blueprint", "call.begin", "allowance.allocate"],
            scope=scope, max_external_calls=0 if committed else 1,
            max_candidate_count=0, adoption_policy="within_scope",
            evidence=evidence_for(state["project"], text="ENGINEERING_ONLY explicit zero-call change", locator="ENGINEERING_ONLY"))
        settle_fidelity_review(state["project"], page_ids=["p5"], execution_ref="L1-synthetic-s05-fidelity",
                              scenario="ENGINEERING_ONLY current zero-call content plan")
    if inflight:
        task = service.continue_project(state["project"])["pending_tasks"][0]
        service.task_start(state["project"], task_id=task["task_id"], execution_ref="ENGINEERING_ONLY_INFLIGHT",
                           supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
        value = deepcopy(task["generation_input"])
        value["parameters"] = {"transparent_background": False}
        frozen = generation.freeze(state["project"], task_id=task["task_id"], input=value,
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
        current_task = tasks._lookup_task(store.load_document(), task["task_id"], store)
        tasks.call_begin(store, task_id=task["task_id"], allowance_id=current_task["call_allowances"][0]["allowance_id"],
                         execution_ref="ENGINEERING_ONLY_INFLIGHT", request_id=frozen["request_id"])
    doc = store.load_document()
    intent = {"schema_version": "change_intent.v1", "project_id": doc["project_id"], "base_revision": doc["revision_id"],
        "intent": "clarify", "instruction": "ENGINEERING_ONLY clarify the neutral label.", "annotation_refs": [], "max_calls": 0,
        "targets": [{"page_id": "p5", "page_ref": doc["pages"][0]["page"], "layer": "content", "artifact_ref": doc["pages"][0]["page"]}]}
    plan = s.operate(root, "changes.plan", {"input": intent})
    args = {"plan_id": plan["plan_id"], "base_revision": doc["revision_id"], "operation_id": str(uuid.uuid4())}
    if committed:
        def lost_response():
            changes.commit(state["project"], **args)
            raise TimeoutError("ENGINEERING_ONLY transport lost the real committed response")
        with pytest.raises(TimeoutError):
            with s.resource_session(root) as (journal, _, _):
                s.perform(journal, "changes.commit", {"project": state["project"], **args}, lost_response)
    else:
        with pytest.raises(eligibility.EligibilityBlocked):
            s.operate(root, "changes.commit", args)
    key = next(iter(c.Journal(root).unfinished()))
    return root, state, config, key


def admission(tmp_path, root, key, name="admission", **overrides):
    journal, state, config = s.load(root)
    intent = next(e for e in journal.events() if e["kind"] == "sdk_intent" and e["data"]["operation_key"] == key)
    failure = next(e for e in journal.events() if e["kind"] == "sdk_error" and e["data"]["operation_key"] == key)
    args = intent["data"]["arguments"]
    doc = Store(state["project"]).load_document()
    value = {"format": m.FORMAT, "action": m.ACTION, "status": s.ENGINEERING,
        "observer_id": "/engineering/rc3-s05", "assurance": "synthetic_engineering", "observed_at_utc": c.now(),
        "tool": c.reference(SCRIPT), "scoped_recorder": c.reference(m.SOURCE), "common": c.reference(s.SOURCE),
        "registration": c.reference(Path(state["campaign"]) / "registration.json"), "run_manifest": c.reference(root / "run.json"),
        **{k: state[k] for k in m.IDENTITY}, "installation": {k: config["installations"][state["arm"]][k] for k in m.INSTALLATION},
        "operation_key": key, "intent": m.event_ref(journal, intent), "failure": m.event_ref(journal, failure),
        "arguments": args, "arguments_sha256": c.digest(c.encoded(args)), "operation_id": args["operation_id"],
        "project_id": doc["project_id"], "expected_revision": doc["revision_id"], "request_digest": None}
    if intent["data"]["operation"] == "changes.commit":
        plan = next(e for e in journal.events() if e["kind"] == "sdk_outcome" and e["data"].get("result", {}).get("plan_id") == args["plan_id"])
        value["plan_outcome"] = m.event_ref(journal, plan)
        value["request_digest"] = operations.request_digest(doc, "changes.commit", args["base_revision"],
            {"plan_id": args["plan_id"], "plan": plan["data"]["result"]["plan"]})
    value.update(overrides)
    return c.save(tmp_path / (name + ".json"), value)


def invoke(root, ref, out):
    return m.reconcile_key(root, ref["path"], ref["sha256"], out)


def test_not_found_preserves_original_bytes_caps_and_has_no_retry(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch)
    before = source_snapshot(state["project"])
    old = c.Journal(root).events()
    ref = admission(tmp_path, root, key)
    result = invoke(root, ref, tmp_path / "observed")
    assert result["status"] == "recorded_no_retry" and result["observed_state"] == "not_found"
    assert result["automatic_retry"] is result["business_authority_granted"] is False
    assert source_snapshot(state["project"]) == before
    assert c.Journal(root).events()[:len(old)] == old and not c.Journal(root).unfinished()
    assert s.Resources(state).totals()[0] == {"writer": 0, "review": 0, "sdk": 7, "render": 0}
    assert result["query_records"][0]["observed_state"] == "not_found"
    assert c.read(result["query_records"][0]["record"]["path"])["business_commit_asserted"] is False
    # Original execute authority is still missing; a distinct explicit attempt fails.
    args = c.read(ref["path"])["arguments"]
    with pytest.raises(eligibility.EligibilityBlocked):
        s.operate(root, "changes.commit", args)


def test_original_failed_query_is_handled_one_key_at_a_time_without_recharging_past(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch)
    args = c.Journal(root).unfinished()[key]["arguments"]
    with pytest.raises(operations.OperationError):
        s.operate(root, "operations.show", {"operation_id": args["operation_id"]})
    querykey = next(k for k in c.Journal(root).unfinished() if k != key)
    ref = admission(tmp_path, root, key)
    result = invoke(root, ref, tmp_path / "commit-observed")
    assert result["observed_state"] == "not_found" and result["remaining_unresolved_keys"] == [querykey]
    assert s.Resources(state).totals()[0]["sdk"] == 8
    ref = admission(tmp_path, root, querykey, name="query-admission")
    assert invoke(root, ref, tmp_path / "query-observed")["remaining_unresolved_keys"] == []
    assert s.Resources(state).totals()[0]["sdk"] == 12


@pytest.mark.parametrize("fault", ["key", "operation-id", "project", "project-id", "revision", "runtime", "payload", "digest", "failure", "stale", "root", "tool", "status"])
def test_exact_admission_and_original_identity_are_mandatory(tmp_path, monkeypatch, fault):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    a = c.read(ref["path"])
    if fault == "key": a["operation_key"] = "unrelated"
    if fault == "operation-id": a["operation_id"] = str(uuid.uuid4())
    if fault == "project": a["project"] += "-other"
    if fault == "project-id": a["project_id"] += "-other"
    if fault == "revision": a["expected_revision"] += "-other"
    if fault == "runtime": a["installation"]["python"] += "-other"
    if fault == "payload": a["arguments"]["base_revision"] += "-other"
    if fault == "digest": a["request_digest"] = "0" * 64
    if fault == "failure": a["failure"] = a["intent"]
    if fault == "stale": a["observed_at_utc"] = "2000-01-01T00:00:00+00:00"
    if fault == "root": a["observer_id"] = "/root"
    if fault == "tool": a["tool"] = a["scoped_recorder"]
    if fault == "status": a["status"] = "ADMITTED"
    ref = c.save(tmp_path / "bad.json", a)
    if fault == "revision":
        result = invoke(root, ref, tmp_path / "out")
        assert result["status"] == "still_unresolved"
    else:
        with pytest.raises((m.Error, KeyError)):
            invoke(root, ref, tmp_path / "out")
    assert key in c.Journal(root).unfinished()


@pytest.mark.parametrize("kind", ["bare404", "timeout", "unknown", "wrong-id", "wrong-state", "fake-committed", "query-failure"])
def test_untrusted_or_uncertain_live_result_stays_unknown(tmp_path, monkeypatch, kind):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    def bad(*_a, **_k):
        opid = c.read(ref["path"])["operation_id"]
        if kind == "bare404": raise operations.OperationError("operation_not_found", "operation_id", "bare", http_status=404)
        if kind == "timeout": raise TimeoutError("ENGINEERING_ONLY timeout")
        if kind == "unknown": raise operations.OperationError("operation_unavailable", "project", "unknown", operation_id=opid, operation_state="unknown")
        if kind == "wrong-id": raise operations.OperationError("operation_not_found", "operation_id", "wrong", http_status=404, operation_id="other", operation_state="not_found")
        if kind == "wrong-state": raise operations.OperationError("operation_not_found", "operation_id", "wrong", http_status=404, operation_id=opid, operation_state="unknown")
        if kind == "fake-committed": return {"status": "committed", "operation_id": opid, "request_digest": "0" * 64,
            "current_revision_id": c.read(ref["path"])["expected_revision"], "committed_revision_id": "fake"}
        raise TimeoutError("ENGINEERING_ONLY public state query timeout")
    monkeypatch.setattr(view if kind == "query-failure" else operations, "project_view" if kind == "query-failure" else "show", bad)
    result = invoke(root, ref, tmp_path / "out")
    assert result["status"] == "still_unresolved" and key in c.Journal(root).unfinished()
    if kind != "fake-committed":
        assert any(c.read(r["record"]["path"])["observed_state"] == "unknown" for r in result["query_records"])


def test_real_current_state_mutation_after_original_failure_is_not_not_found(tmp_path, monkeypatch):
    root, _, _, key = setup(tmp_path, monkeypatch)
    # A real public dispatch advances revision; no synthetic current pointer edit.
    _, state, _ = s.load(root)
    service.open_host_task(Store(state["project"]), kind="repair", page_ids=["p5"], instruction="ENGINEERING_ONLY extra current work")
    ref = admission(tmp_path, root, key)
    result = invoke(root, ref, tmp_path / "out")
    assert result["status"] == "still_unresolved"


def test_real_committed_receipt_with_exact_original_digest_is_observed_without_retry(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch, committed=True)
    before = source_snapshot(state["project"])
    ref = admission(tmp_path, root, key)
    result = invoke(root, ref, tmp_path / "out")
    assert result["observed_state"] == "committed" and not c.Journal(root).unfinished()
    # operations.show may republish its disposable derived index. Business bytes stay exact.
    after = source_snapshot(state["project"])
    assert {k: v for k, v in after.items() if "/operations/" not in k} == {k: v for k, v in before.items() if "/operations/" not in k}
    assert c.read(result["record"]["path"])["business_commit_asserted"] is True


def test_actual_public_inflight_allowance_blocks_without_touching_call_fact(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch, inflight=True)
    before = source_snapshot(state["project"])
    ref = admission(tmp_path, root, key)
    result = invoke(root, ref, tmp_path / "out")
    assert result["status"] == "still_unresolved" and key in c.Journal(root).unfinished()
    assert source_snapshot(state["project"]) == before
    actual = run_desk.listing(state["project"])
    assert any(row["call_counts"].get("in_flight") for row in actual["tasks"])


@pytest.mark.parametrize("hazard", ["reserved", "in_flight", "unknown", "running", "unreadable"])
def test_current_task_hazards_block_even_typed_not_found(tmp_path, monkeypatch, hazard):
    root, _, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    original = run_desk.listing
    def listing(*a, **kw):
        result = original(*a, **kw)
        # Explicit public-projection fault seam, never an SDK or native fact.
        result["tasks"].append({"task_id": "ENGINEERING_ONLY", "status": hazard if hazard in {"running", "unreadable"} else "awaiting_host",
                               "call_counts": {hazard: 1} if hazard not in {"running", "unreadable"} else {}})
        return result
    monkeypatch.setattr(run_desk, "listing", listing)
    assert invoke(root, ref, tmp_path / "out")["status"] == "still_unresolved"


def test_final_exact_admission_reload_refuses_drift(tmp_path, monkeypatch):
    root, _, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    original = operations.show
    def drift(*a, **kw):
        try:
            return original(*a, **kw)
        finally:
            path = Path(ref["path"])
            path.write_bytes(path.read_bytes() + b" ")
    monkeypatch.setattr(operations, "show", drift)
    with pytest.raises(m.Error, match="admission bytes"):
        invoke(root, ref, tmp_path / "out")
    assert key in c.Journal(root).unfinished()


def test_prior_other_mutation_blocks_before_new_reads_and_frozen_helpers_still_exact(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    with s.resource_session(root, readonly=True) as (journal, _, _):
        journal.append("sdk_intent", {"operation_key": "ENGINEERING_ONLY_unknown_mutation", "operation": "tasks.call_begin", "arguments": {}})
    count = s.Resources(state).totals()[0]["sdk"]
    with pytest.raises(m.Error, match="other unresolved"):
        invoke(root, ref, tmp_path / "out")
    assert s.Resources(state).totals()[0]["sdk"] == count
    assert c.digest(m.SOURCE.read_bytes()) == m.SCOPED_SHA and c.digest(s.SOURCE.read_bytes()) == m.COMMON_SHA


@pytest.mark.parametrize("field,value", [("arguments", []), ("arguments", None), ("operation_key", True),
    ("operation_key", []), ("operation_id", 42), ("project_id", None), ("expected_revision", False),
    ("installation", []), ("runtime_observations", [{"status": "committed"}])])
def test_json_types_and_caller_commit_observations_do_not_authorize_terminal_state(tmp_path, monkeypatch, field, value):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    a = c.read(ref["path"])
    a[field] = value
    if field == "runtime_observations":
        # A caller observation is ignored. Force the live read to fail and prove
        # the injected successful observation cannot settle the original key.
        monkeypatch.setattr(operations, "show", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("ENGINEERING_ONLY")))
        ref = c.save(tmp_path / "bad.json", a)
        assert invoke(root, ref, tmp_path / "out")["status"] == "still_unresolved"
    else:
        ref = c.save(tmp_path / "bad.json", a)
        with pytest.raises((m.Error, TypeError, KeyError)):
            invoke(root, ref, tmp_path / "out")
        assert s.Resources(state).totals()[0]["sdk"] == 3
    assert key in c.Journal(root).unfinished()


def test_real_lock_replacement_never_clears_key(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    original = operations.show
    def replacement(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            path = Path(Store(state["project"]).lock_path)
            path.rename(path.with_suffix(".preserved-old"))
            path.touch()
    monkeypatch.setattr(operations, "show", replacement)
    with pytest.raises(m.Error, match="lock replaced"):
        invoke(root, ref, tmp_path / "out")
    assert key in c.Journal(root).unfinished()


def test_exhausted_pool_is_not_refunded(tmp_path, monkeypatch):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    # Spend the remaining SDK cap honestly as explicitly engineering bookkeeping;
    # no calls are claimed by this test's externally supplied resource charge.
    resources = s.Resources(state)
    resources.charge("sdk", 87, {"ENGINEERING_ONLY_SYNTHETIC_CAP_EXHAUSTION": True})
    with pytest.raises(m.Error, match="did not dispatch"):
        invoke(root, ref, tmp_path / "out")
    assert key in c.Journal(root).unfinished() and s.Resources(state).totals()[0]["sdk"] == 90


@pytest.mark.parametrize("maximum", [0, 1])
def test_any_prior_crashed_render_reservation_stays_unknown(tmp_path, monkeypatch, maximum):
    root, state, _, key = setup(tmp_path, monkeypatch)
    ref = admission(tmp_path, root, key)
    resources = s.Resources(state)
    resources.journal.append("render_reserved", {"pool": s.pool_key(state), "slot": state["slot"],
        "key": "ENGINEERING_ONLY_prior_crashed_reservation", "maximum": maximum})
    with pytest.raises(m.Error, match="prior renderer"):
        invoke(root, ref, tmp_path / "out")
    assert key in c.Journal(root).unfinished() and s.Resources(state).totals()[0]["sdk"] == 3
