"""Finite same-ledger M02 read installation transition; never calls imagegen.

The Root barrier is an operational retirement of old M02 writers, not crypto.
Only original recorder authentication and the actual scoped SDK are used.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import io
import json
import secrets
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path

EVENT_SHA = "1bf6c82e9fc2c18798f2c9cfda2ec214836d64cffcaf52bf27db883b0116b182"
SUCCESSOR_SHA = "2428fd3906d3dd67e36ad12051065aa72b5e53877fc61d4a4e340e2ca1749f47"


def dependency(name, sha):
    path = Path(__file__).with_name(name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError("exact sibling changed: " + name)
    spec = importlib.util.spec_from_file_location("s12_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e = dependency("image_event_controller.py", EVENT_SHA)
s11 = dependency("m02_runtime_continuation.py", SUCCESSOR_SHA)
c, b = e.c, e.b
require, read, save, reference = e.require, e.read, e.save, e.reference
FORMAT = "rc3-m02-read-installation-transition.v1"
NAME = "m02-read-runtime-transition.json"
SCOPE = "M02--read"
LEAVES = ("M02-read-01", "M02-read-02")
_LOCK = ContextVar("m02_read_same_ledger_lock", default=None)


@contextmanager
def locked(root):
    root = b.canonical_root(str(root))
    require(all((root / name).is_file() and not (root / name).is_symlink() for name in
                ("event-registration.json", "event-origin.json", "event-legacy-frontier.json")),
            "existing canonical event epoch only; never create another root")
    with b.locked(root):
        token = _LOCK.set(root)
        try:
            yield root
        finally:
            _LOCK.reset(token)


def binding(value):
    return e.digest(e.canonical({k: v for k, v in value.items() if k != "admission"}))


def transition_ref(root):
    return reference(Path(root) / NAME)


def events(journal, kind):
    return [x["data"] for x in journal.events() if x["kind"] == kind]


def original_epoch(root):
    """The frozen loader pins sibling paths as well as hashes.

    Load only the original registered, exact helper sibling, not an old
    Runtime or a caller-selected API. Never rewrite the original registration.
    """
    config = read(root / "event-registration.json")
    require(config.get("controller_sha256") == EVENT_SHA, "original event identity required")
    for key, sha in (("sdk_controller", e.COMMON_SHA), ("bf_primitives", e.PRIMITIVES_SHA)):
        c.check_ref(config[key])
        require(config[key]["sha256"] == sha, "original helper bytes differ")
    path = Path(config["sdk_controller"]["path"]).with_name("image_event_controller.py")
    require(path.parent == Path(config["bf_primitives"]["path"]).parent
            and e.digest(path.read_bytes()) == EVENT_SHA, "only original pinned event sibling")
    spec = importlib.util.spec_from_file_location("s12_original_epoch", path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    return original.load(root)


def protected_frontier(root, rows, *, initial=True):
    refs = []
    for row in rows:
        if row.get("legacy_dispatch"):
            refs.append(row["legacy_dispatch"])
            continue
        refs.append(reference(root / "event-dispatches" / f"{row['event_ordinal']:06d}.json"))
        for name in ("preparation.json", "literal-tool-arguments.json", "dispatch-mark.json",
                     "sealed-observation.json", "raw-first-root-callback",
                     "raw-first-native_response", "raw-first-original_png", "settlement.json"):
            path = e._call_dir(root, row["leaf_id"]) / name
            if path.exists() and (initial or name in {"preparation.json", "literal-tool-arguments.json", "dispatch-mark.json"}):
                refs.append(reference(path))
    return refs


def validate(value, root, config, policy, rows, *, initial=False):
    require(sys.flags.isolated and sys.dont_write_bytecode, "use own absolute Python -I -B")
    fields = {"format", "status", "companion_sha256", "event_controller", "successor_controller",
              "ledger_root", "scope_slot", "project", "project_id", "whole_run_id", "live_budget_roots",
              "spend_evidence", "predecessor", "successor_registration", "successor_admission",
              "installation_review", "installation", "runtime_epoch", "admission"}
    require(set(value) == fields, "finite transition fields only; no future Task/grant or override")
    require(value["format"] == FORMAT and value["status"] in {"ADMITTED", e.ENGINEERING}
            and value["status"] == config["status"], "separate same-status scope transition required")
    require(value["companion_sha256"] == e.digest(Path(__file__).read_bytes()), "transition code changed")
    for key, name, sha in (("event_controller", "image_event_controller.py", EVENT_SHA),
                           ("successor_controller", "m02_runtime_continuation.py", SUCCESSOR_SHA)):
        require(c.check_ref(value[key]) == c.reference(Path(__file__).with_name(name))
                and value[key]["sha256"] == sha, "pin exact sibling " + key)
    require(value["ledger_root"] == str(root) and value["scope_slot"] == SCOPE, "same canonical M02 read root only")
    for key, name in (("registration", "event-registration.json"), ("origin", "event-origin.json"),
                      ("legacy_frontier", "event-legacy-frontier.json")):
        require(c.check_ref(value["predecessor"][key]) == c.reference(root / name), "original epoch changed")
    require(value["predecessor"]["policy"] == config["policy"], "original policy changed")
    old = value["predecessor"]["charged_rows"]
    require(rows[:len(old)] == old, "captured charged frontier changed")
    for ref in value["predecessor"]["protected_refs"]:
        c.check_ref(ref)
    require({(r["path"], r["sha256"]) for r in protected_frontier(root, old, initial=initial)} <=
            {(r["path"], r["sha256"]) for r in value["predecessor"]["protected_refs"]}, "pin existing public charged evidence")
    parent = next(p for p in policy["parents"] if p["parent_id"] == "M02")
    scopes = {s["checkpoint"]: s for s in policy["scopes"] if s["parent_id"] == "M02"}
    require(e._parent_key(parent) == ("M02", value["whole_run_id"], 1, "B") and parent["max_calls"] == 4
            and policy["total_call_cap"] == 44 and set(scopes) == {"live", "read"}, "original global44/parent4/two uses")
    require(scopes["read"]["scope_slot"] == SCOPE and scopes["read"]["max_calls"] == scopes["live"]["max_calls"] == 2
            and tuple(x["leaf_id"] for x in scopes["read"]["leaves"]) == LEAVES, "only original read2 leaves")
    spent = [r for r in old if r["parent_id"] == "M02"]
    require(len(spent) == 2 and {r["leaf_id"] for r in spent} == {"M02-live-01", "M02-live-02"}
            and all(r["scope_slot"] == "M02--live" and r["project"] == value["project"]
                    and r["project_id"] == value["project_id"] for r in spent), "same actual project with original live2 spent")
    require(value["live_budget_roots"] == sorted({r["budget_root_id"] for r in spent}), "actual live roots required")
    require(value["spend_evidence"], "Root spend evidence required")
    for ref in value["spend_evidence"]:
        c.check_ref(ref)
    for key in ("successor_registration", "successor_admission", "installation_review", "admission"):
        c.check_ref(value[key])
    cfg = read(value["successor_registration"]["path"])
    require(cfg["project"] == value["project"] and cfg["experiment_id"] == value["whole_run_id"]
            and cfg["admission"] == value["successor_admission"] and cfg["installation"] == value["installation"]
            and cfg["runtime_epoch"] == value["runtime_epoch"]
            and cfg["independent_reviews"]["installation"] == value["installation_review"]
            and cfg["status"] == ("ADMITTED" if value["status"] == "ADMITTED" else s11.ENGINEERING),
            "same admitted S11 successor/installation")
    require(set(cfg["scopes"]["read"]["page_ids"]) == {x["page_label"] for x in scopes["read"]["leaves"]}
            and cfg["scopes"]["read"]["instruction"]["sha256"] == scopes["read"]["instruction"]["sha256"],
            "same planned read Pages and instruction")
    admitted = read(value["admission"]["path"])
    require(admitted.get("format") == "rc3-m02-read-transition-admission.v1" and admitted.get("observer") == "/root"
            and admitted.get("status") == value["status"] and admitted.get("transition_binding") == binding(value)
            and admitted.get("old_M02_write_routes_retired") is True and admitted.get("administrative_only") is True
            and admitted.get("source_observations"), "exact prospective administrative Root admission required")
    for ref in admitted["source_observations"]:
        c.check_ref(ref)
    if value["status"] == "ADMITTED":
        require(str(root) == "/workspace/work/rc3/r05/ig" and value["project"] == s11.PROJECT
                and value["whole_run_id"] == "m02-telescope-prod-01"
                and value["predecessor"]["registration"]["sha256"] == "bfe5fd0d7de98a2ed80b70e0990977cf1d956728382a638dddaa50b2f97d3fa8"
                and config["policy"]["sha256"] == "125beabe02b71f45e9564fd403d80ddc2b8cb29ff242fbbbe38aea1e759aeaeb",
                "exact original formal M02 epoch")
        review = read(value["installation_review"]["path"])
        require(review.get("status") == "PASS" and review.get("managed_candidate") is True
                and review.get("installation") == value["installation"] and review.get("native_image_registry_verified") is True,
                "independent final managed installation review required")
        require(value["installation"] != config["installations"]["B"], "no global B replacement")
    else:
        require(str(root) != "/workspace/work/rc3/r05/ig" and value["project"] != s11.PROJECT, "engineering never targets formal M02")
    return cfg


def load(root):
    require(_LOCK.get() == root, "same canonical recorder lock required")
    root, config, policy, frontier = original_epoch(root)
    rows = e._records(root, frontier)
    value = read(root / NAME)
    validate(value, root, config, policy, rows)
    origin = read(root / "m02-read-transition-origin.json")
    require(origin["transition"] == transition_ref(root), "transition cannot be replaced")
    c.check_ref(origin["source"])
    journal = c.Journal(root / "m02-read-transition-journal")
    first = journal.events()[0]
    require(first["kind"] == "m02_read_transition" and first["data"]["transition"] == transition_ref(root), "transition journal changed")
    for row in rows[len(value["predecessor"]["charged_rows"]):]:
        if row["parent_id"] == "M02":
            _, p = e._preparation(root, config, row["leaf_id"])
            require(row["scope_slot"] == SCOPE and p.get("installation_transition") == transition_ref(root),
                    "retired M02 route appended; stop and reconcile")
    successor = s11.load(Path(value["successor_registration"]["path"]).parent)
    require(successor[1]["project_id"] == value["project_id"], "same real project")
    return root, config, policy, frontier, rows, value, journal, successor


def initialize(registration, root_path):
    with locked(root_path) as root:
        require(not (root / NAME).exists(), "one transition; never replace/reset/re-epoch")
        _, config, policy, frontier = original_epoch(root)
        rows = e._records(root, frontier)
        e._caps(policy, rows)
        value = read(registration)
        validate(value, root, config, policy, rows, initial=True)
        j, state, cfg = s11.load(Path(value["successor_registration"]["path"]).parent)
        require(state["project_id"] == value["project_id"], "same real project")
        save(root / NAME, value)
        save(root / "m02-read-transition-origin.json", {"transition": transition_ref(root), "source": reference(registration)})
        c.Journal(root / "m02-read-transition-journal").append("m02_read_transition",
            {"transition": transition_ref(root), "costs": s11.costs(j, cfg), "grants_calls": False})
        return {"status": "SCOPE_TRANSITION_REGISTERED_NOT_READ_AUTHORIZED", "transition": transition_ref(root),
                "charged": len(rows), "new_calls": 0}


def barrier(values, command, path, bootstrap):
    root, _, _, _, _, value, journal, (_, state, _) = values
    proof = read(path)
    ref = reference(path)
    doc = c.store_for(state).load_document()
    require(proof.get("format") == "rc3-m02-read-exclusive-barrier.v1" and proof.get("observer") == "/root"
            and proof.get("assurance") == "host_attested" and proof.get("command") == command
            and proof.get("installation_transition") == transition_ref(root) and proof.get("bootstrap") == c.reference(bootstrap)
            and proof.get("project_id") == value["project_id"] and proof.get("base_revision") == doc["revision_id"]
            and proof.get("journal_frontier") == len(journal.events())
            and proof.get("successor_frontier") == len(values[7][0].local.events())
            and proof.get("old_M02_write_routes_retired") is True and proof.get("all_other_M02_writers_stopped") is True
            and proof.get("exclusive_until_completed") is True and proof.get("source_observations"),
            "fresh exact exclusive operational Root barrier required")
    c.fresh(proof["observed_at_utc"])
    for item in proof["source_observations"]:
        c.check_ref(item)
    if command == "mark":
        require(proof.get("exclusive_through_first_callback") is True and proof.get("external_M02_inflight") == 0
                and proof.get("external_M02_unknown") == 0, "Root serializes tool through its first callback")
    require(not any(x["data"].get("barrier") == ref for x in journal.events()), "barrier already consumed")
    journal.append("m02_read_root_barrier", {"command": command, "barrier": ref})


def read_grant(values, *, required=False):
    """Bind only the one real SDK outcome; no post-success binding-write gap.

    A committed SDK call whose outcome was lost stays unresolved. Neither a
    Host success string nor a current Store lookup can substitute for it.
    """
    journal = values[6]
    requested = events(journal, "m02_read_grant_requested")
    intents = [x for x in events(journal, "sdk_intent") if x["operation"] == "collaboration.grant"]
    require(len(requested) <= 1 and len(intents) <= 1, "one actual read grant attempt; no new pool")
    if not requested or not intents:
        require(not required, "unique read grant has no recorded SDK outcome; BLOCKED")
        return None
    request, intent = requested[0], intents[0]
    require(intent["arguments"] == request["SDK_arguments"], "grant intent changed")
    outcomes = [x for x in events(journal, "sdk_outcome") if x["operation_key"] == intent["operation_key"]]
    if not outcomes:
        require(not required, "read grant outcome unresolved; no retry or replacement pool")
        return None
    require(len(outcomes) == 1, "ambiguous SDK grant outcome")
    result = outcomes[0]["result"]
    require(result.get("status") == "accepted" and result.get("authorization_ref") and result.get("authorization_id"),
            "actual public grant result required")
    store = c.store_for(values[7][1])
    auth = store.read_object_json(result["authorization_ref"])
    require(auth["authorization_id"] == result["authorization_id"] and auth["project_id"] == values[5]["project_id"]
            and auth["request_id"] == request["request_id"] and auth["mode"] == "execute"
            and auth["max_external_calls"] == auth["max_candidate_count"] == 2
            and not auth.get("budget_parent_ref") and not auth.get("parent_authorization_ref")
            and auth["authorization_id"] not in values[5]["live_budget_roots"], "actual original distinct bounded2 read root")
    return {"request_id": request["request_id"], "occurrence": request["occurrence"],
            "authorization_ref": result["authorization_ref"], "budget_root_id": auth["authorization_id"],
            "SDK_operation_key": intent["operation_key"], "SDK_result": result}



def opened_tasks(values):
    """Actual immutable SDK outcomes, not a second post-success bookkeeping write."""
    journal = values[6]
    outcomes = {x["operation_key"]: x["result"] for x in events(journal, "sdk_outcome")}
    return [{"page_id": x["arguments"]["page_id"], "SDK_result": outcomes[x["operation_key"]]}
            for x in events(journal, "sdk_intent") if x["operation"] == "service.open_blueprint_task"
            and x["operation_key"] in outcomes]


def current_scope(values, handoff, *, task_required=True):
    root, config, policy, _, rows, value, _, (j, state, cfg) = values
    require(handoff.get("installation_transition") == transition_ref(root) and handoff.get("scope_slot") == SCOPE
            and handoff.get("project") == value["project"], "explicit same transition/scope/project required")
    parent = next(p for p in policy["parents"] if p["parent_id"] == "M02")
    require(handoff.get("format") == e.HANDOFF and handoff.get("case") == "M02" and handoff.get("checkpoint") == "read"
            and all(handoff.get(k) == parent[k] for k in ("matrix_slot", "whole_run_id", "repetition", "arm")), "original parent/use required")
    scope = next(s for s in policy["scopes"] if s["scope_slot"] == SCOPE)
    doc = s11.guard(j, state, cfg)
    request = doc["collaboration"]["request"]
    require(s11.m.phase(j) == "read" and (request.get("variant") or {}).get("variant_id") == "read"
            and request["request_id"] == handoff.get("actual_request_id"), "real current S11 read Request required")
    # Unchanged S11 owns real full-export -> release -> next-read sequencing.
    # This supplement introduces neither a second transition route nor a test
    # bypass. Its engineering fixture declares the current-read premise as L1.
    evidence = request.get("instruction_evidence") or {}
    store = c.store_for(state)
    require(evidence.get("source_ref") and e.digest(store.read_object_bytes(evidence["source_ref"])) == scope["instruction"]["sha256"],
            "actual project input must bind original read instruction")
    occurrence = handoff["instruction_occurrence_ref"]
    c.check_ref(occurrence)
    observed = read(occurrence["path"])
    require(observed.get("observer_id") == "/root" and observed.get("assurance") == "host_attested"
            and observed.get("scope_slot") == SCOPE and observed.get("actual_trigger_satisfied") is True
            and observed.get("instruction_sha256") == scope["instruction"]["sha256"] and observed.get("source_observations")
            and observed.get("evidence_kind") == (e.ENGINEERING if value["status"] == e.ENGINEERING else "ROOT_ACTUAL_NATIVE"),
            "genuine read occurrence required")
    for ref in observed["source_observations"]:
        c.check_ref(ref)
    bound = read_grant(values)
    require(not bound or (bound["request_id"] == request["request_id"] and bound["occurrence"] == occurrence),
            "original read Request/occurrence cannot drift into another SDK pool")
    from deck_master import eligibility
    roots = {}
    for row in value["predecessor"]["charged_rows"]:
        if row["parent_id"] != "M02":
            continue
        task = c.task_for(store, row["task_id"])
        allowance = next((a for a in task["call_allowances"] if a["allowance_id"] == row["allowance_id"]), None)
        attempts = [store.read_object_json(r) for r in task.get("generation_attempts", [])]
        require(allowance and allowance["state"] == "consumed"
                and any(a["attempt_id"] == row["attempt_id"] and a["allowance_id"] == row["allowance_id"]
                        and a["execution_ref"] == allowance.get("execution_ref") for a in attempts), "actual live spend unresolved")
        ref = task["collaboration_binding"]["authorization_ref"]
        auth = store.read_object_json(ref)
        seen = set()
        while auth.get("budget_parent_ref"):
            require(auth["authorization_id"] not in seen and len(seen) < 8, "invalid live SDK ancestry")
            seen.add(auth["authorization_id"])
            auth = store.read_object_json(auth["budget_parent_ref"])
        budget = eligibility.authorization_budget(store, doc, ref)
        require(auth["authorization_id"] == row["budget_root_id"] and budget["used"] == budget["ceiling"], "live SDK root not exhausted")
        roots[auth["authorization_id"]] = budget["ceiling"]
    require(sum(roots.values()) == 2, "original live SDK roots represent exactly spent2")
    if task_required:
        if handoff.get("allowance_id"):
            e.validate_scope_binding(config, handoff, before_begin=not handoff.get("attempt_id"))
        else:
            c.check_ref(handoff["packet_audit_ref"])
            audit = read(handoff["packet_audit_ref"]["path"])
            require(audit.get("status") == "PASS" and audit.get("required_read_closure_checked") is True
                    and audit.get("raw_workorder_preserved") is True
                    and all(audit.get(k) == handoff.get(k) for k in ("scope_slot", "task_id", "project", "stage")), "actual Task packet audit required")
            for k in ("original_raw_ref", "author_view_ref", "read_closure_manifest_ref"):
                c.check_ref(audit[k])
    e._caps(policy, rows)
    return store, doc, scope


def applied_methods(values, handoff):
    c.check_ref(handoff["method_application_ref"])
    proof = read(handoff["method_application_ref"]["path"])
    c.check_ref(proof["method_response"])
    returned = events(values[6], "m02_read_methods_returned")
    require(proof.get("observer") == "/root" and proof.get("assurance") == "host_attested"
            and proof.get("installation_transition") == transition_ref(values[0])
            and proof.get("task_id") == handoff["task_id"] and proof.get("project_id") == values[5]["project_id"]
            and proof.get("stage") == handoff["stage"] and proof.get("ordinal") == handoff["ordinal"]
            and proof.get("all_method_bytes_read") is True and proof.get("methods_applied") is True
            and proof.get("required_read_closure_checked") is True and proof.get("packet_audit_ref") == handoff["packet_audit_ref"]
            and any(r["record"] == proof["method_response"] and r["task_id"] == handoff["task_id"]
                    and r["executor"] == proof.get("executor") for r in returned), "actual full returned methods and application proof required")
    return proof


def actual_task(values, handoff, *, claimed=False):
    store, doc, scope = current_scope(values, handoff)
    j, state, cfg = values[7]
    grant = read_grant(values, required=True)
    packet = s11.current_stage(j, state, cfg, handoff["stage"], handoff["ordinal"])
    invocation, _ = s11.c.execution(j, handoff["stage"], handoff["ordinal"])
    require(packet["role"] == invocation["role"] == "production" and packet["task_id"] == handoff["task_id"], "same new S11 production execution")
    from deck_master import eligibility, method_resources, tasks
    task = c.task_for(store, handoff["task_id"])
    leaf = next((v for v in scope["leaves"] if v["leaf_id"] == handoff.get("leaf_id")), None)
    require(leaf and task["kind"] == "blueprint" and task["scope_pages"] == [handoff["page_id"]]
            and handoff["page_id"] == leaf["page_label"], "actual single planned read Page Task")
    require(task["status"] == ("running" if claimed else "awaiting_host") and tasks.task_inputs_current(store, doc, task),
            "actual current Task/claim required")
    require(not claimed or task.get("execution_ref") == invocation["executor"], "same actual successor writer claim")
    require(any(r["SDK_result"]["task_id"] == task["task_id"] and r["page_id"] == handoff["page_id"] for r in opened_tasks(values)),
            "Task must originate through this transition")
    methods = c.record_sdk(values[6], "method_resources.read_task_methods", {"task_id": task["task_id"]},
        lambda: method_resources.read_task_methods(state["project"], task["task_id"]))
    require(methods["status"] == "current" and methods["dispatch_method_release"] == methods["current_method_release"]
            and methods["current_method_release"]["release_id"] == values[5]["runtime_epoch"], "actual complete current successor methods")
    authref = task.get("collaboration_binding", {}).get("authorization_ref")
    require(authref, "actual read authorization required")
    auth = store.read_object_json(authref)
    seen = set()
    while auth.get("budget_parent_ref"):
        require(auth["authorization_id"] not in seen and len(seen) < 8, "invalid read SDK ancestry")
        seen.add(auth["authorization_id"])
        auth = store.read_object_json(auth["budget_parent_ref"])
    require(auth["authorization_id"] == grant["budget_root_id"]
            and auth["max_external_calls"] == auth["max_candidate_count"] == 2
            and eligibility.authorization_budget(store, doc, authref)["ceiling"] <= 2, "only actual first returned read pool")
    return store, doc, task, methods, auth


def rights(values, handoff):
    applied_methods(values, handoff)
    store, doc, task, _, auth = actual_task(values, handoff, claimed=True)
    from deck_master import capabilities, eligibility
    from deck_master.native_image_evidence import image_binding
    native_binding, task, attempt, request = image_binding(store, doc, task["task_id"], handoff["attempt_id"])
    allowance = next((a for a in task["call_allowances"] if a["allowance_id"] == handoff["allowance_id"]), None)
    require(allowance and allowance["state"] == "in_flight" and attempt["allowance_id"] == allowance["allowance_id"]
            and task["execution_ref"] == attempt["execution_ref"] and not attempt.get("observations"), "first actual in-flight claimed Attempt")
    require(request["input"]["parameters"] == {"transparent_background": False}, "exact false parameters required")
    args, refs = b.actual_arguments(handoff["project"], request)
    eligibility.guard(store, doc, "call.begin", context={"task": task, "allowance_id": allowance["allowance_id"], "targets": {"page_ids": task["scope_pages"]}})
    return {"binding": native_binding, "identity": capabilities.installation_identity(), "task": task, "attempt": attempt,
            "request": request, "tool_arguments": args, "reference_snapshots": refs, "budget_root_id": auth["authorization_id"],
            "parent_budget": eligibility.authorization_budget(store, doc, task["collaboration_binding"]["authorization_ref"])}


def capacity(values, leaf):
    require(leaf in LEAVES, "one original read leaf required")
    rows, policy = values[4], values[2]
    require(len(rows) < policy["total_call_cap"] and sum(r["parent_id"] == "M02" for r in rows) < 4
            and sum(r["scope_slot"] == SCOPE for r in rows) < 2 and all(r["leaf_id"] != leaf for r in rows),
            "original global/parent/read/leaf cap exhausted; no retry/refund")


def require_resolved_read_dispatches(values):
    """Fact recording remains available; later consumption cannot hide unknown."""
    for row in values[4][len(values[5]["predecessor"]["charged_rows"]):]:
        if row["parent_id"] != "M02":
            continue
        require((e._call_dir(values[0], row["leaf_id"]) / "sealed-observation.json").exists(), "prior read pending its first callback")
        _, _, record = e._authenticated(values[0], values[1], row["leaf_id"])
        task = c.task_for(c.store_for(values[7][1]), row["task_id"])
        require(record["actual_call_outcome"] == "consumed"
                and any(a["allowance_id"] == row["allowance_id"] and a["state"] == "consumed" for a in task["call_allowances"]),
                "prior read outcome/SDK settlement unresolved or unknown; no further consumption")


def preparation(values, leaf):
    require(leaf in LEAVES, "old live/foreign leaf cannot use transition")
    dest, prepared = e._preparation(values[0], values[1], leaf)
    require(prepared.get("installation_transition") == transition_ref(values[0])
            and prepared["scope_binding"].get("installation_transition") == transition_ref(values[0]), "old preparation cannot be rebound")
    require(prepared["row"]["scope_slot"] == SCOPE and prepared["row"]["project"] == values[5]["project"], "prepared scope/project changed")
    applied_methods(values, prepared["scope_binding"])
    return dest, prepared


def prepare(values, handoff):
    root, config, policy, _, rows, _, journal, _ = values
    leaf = handoff["leaf_id"]
    capacity(values, leaf)
    actual = rights(values, handoff)
    dest = e._call_dir(root, leaf)
    require(not dest.exists(), "one immutable original preparation")
    auth = c.store_for(values[7][1]).read_object_json(actual["task"]["collaboration_binding"]["authorization_ref"])
    row = {"parent_id": "M02", "case": "M02", "scope_slot": SCOPE, "leaf_id": leaf,
           "page_id": handoff["page_id"], "page_label": handoff["page_id"], "checkpoint": "read",
           "project_id": values[5]["project_id"], "project": handoff["project"], "actual_request_id": handoff["actual_request_id"],
           "instruction_occurrence_sha256": handoff["instruction_occurrence_ref"]["sha256"],
           "task_id": handoff["task_id"], "allowance_id": handoff["allowance_id"], "attempt_id": handoff["attempt_id"],
           "generation_request_id": actual["request"]["request_id"], "authorization_id": auth["authorization_id"],
           "budget_root_id": actual["budget_root_id"]}
    e._check_events(rows, row)
    e._caps(policy, rows, row)
    prepared = {"format": "rc3-image-event-preparation.v1", "event_id": "rc3-event-" + secrets.token_hex(16),
                "provider_id": e.PROVIDER, "registration_sha256": e.digest(e.canonical(config)), "scope_binding": deepcopy(handoff),
                "row": row, "installation_transition": transition_ref(root), "native_product_capability": "OWN_NATIVE_IMAGE_REGISTRY",
                "prepared_at_ms": b.now_ms(), "parent_budget_at_prepare": actual["parent_budget"],
                **{k: actual[k] for k in ("binding", "identity", "tool_arguments", "reference_snapshots")}}
    save(dest / "preparation.json", prepared)
    save(dest / "literal-tool-arguments.json", prepared["tool_arguments"])
    journal.append("m02_read_prepared", {"leaf_id": leaf, "transition": transition_ref(root), "preparation": reference(dest / "preparation.json")})
    return {"status": "PREPARED_NOT_DISPATCHED", "preparation": reference(dest / "preparation.json"),
            "arguments": reference(dest / "literal-tool-arguments.json")}


def mark(values, leaf, bootstrap):
    root, config, policy, frontier, rows = values[:5]
    dest, prepared = preparation(values, leaf)
    require(not (dest / "dispatch-mark.json").exists(), "already charged; uncertain calls never resend")
    boot = b.bootstrap(config, bootstrap)
    actual = rights(values, prepared["scope_binding"])
    require(all(actual[k] == prepared[k] for k in ("binding", "identity", "tool_arguments", "reference_snapshots")), "current rights/inputs changed")
    b.unchanged_references(prepared["reference_snapshots"])
    e._check_events(rows, prepared["row"])
    e._caps(policy, rows, prepared["row"])
    ordinal = len(rows) - len(frontier["charged_rows"]) + 1
    previous = reference(root / "event-dispatches" / f"{ordinal-1:06d}.json")["sha256"] if ordinal > 1 else None
    marker = {**prepared["row"], "event_ordinal": ordinal, "previous_event_sha256": previous, "event_id": prepared["event_id"],
              "preparation_sha256": reference(dest / "preparation.json")["sha256"],
              "arguments_sha256": e.digest(e.canonical(prepared["tool_arguments"])), "binding_sha256": e.digest(e.canonical(prepared["binding"])),
              "controller_dispatch_mark_ms": b.now_ms(), "bootstrap": boot, "automatic_retry": False, "cost": "CHARGED_PENDING_ROOT_TOOL_OBSERVATION"}
    save(root / "event-dispatches" / f"{ordinal:06d}.json", marker)
    save(dest / "dispatch-mark.json", marker)
    return marker


def seal(values, leaf, callback, bootstrap):
    root, config = values[:2]
    dest, prepared = preparation(values, leaf)
    require(not (dest / "sealed-observation.json").exists(), "first observation immutable, including failure/unknown")
    raw = c.write_once(dest / "raw-first-root-callback", Path(callback).read_bytes())
    data = read(raw["path"])
    for key in ("native_response", "original_png"):
        if isinstance(data.get(key), dict) and data[key].get("path"):
            source = Path(data[key]["path"])
            if source.is_file() and not source.is_symlink():
                c.write_once(dest / ("raw-first-" + key), source.read_bytes())
    boot = b.bootstrap(config, bootstrap)
    from deck_master import capabilities
    require(capabilities.installation_identity() == prepared["identity"], "actual scoped installation changed")
    marker = read(dest / "dispatch-mark.json")
    completed = b.validate_callback(config, prepared, marker, data)
    require(data.get("completion_status") in {"completed", "error", "unknown"}, "actual first outcome required")
    record = {"format": "rc3-root-image-event-observation.v1", "event_id": prepared["event_id"],
              "preparation_sha256": reference(dest / "preparation.json")["sha256"], "callback": data, "callback_source": reference(callback),
              "frozen_first_callback": raw, "bootstrap": boot, "marker": marker, "sealed_at_ms": b.now_ms(),
              "evidence_kind": config["status"], "assurance": "host_attested", "platform_signed": False, "human": False,
              "actual_call_outcome": "consumed" if data["completion_status"] == "completed" else "unknown", "automatic_retry": False}
    if data["completion_status"] == "completed":
        png = c.check_ref(data["original_png"])
        record["original_png"] = png
        try:
            b.unchanged_references(prepared["reference_snapshots"])
            from PIL import Image
            with Image.open(io.BytesIO(Path(png["path"]).read_bytes())) as original:
                require(original.format == "PNG", "preserve original PNG, no re-encoding")
                original.verify()
        except (OSError, ValueError) as exc:
            record["unusable_output_or_reference"] = str(exc)
        record["claims"] = {"provider_id": e.PROVIDER, "event_id": prepared["event_id"], "binding": prepared["binding"],
                            "tool_name": "image_gen__imagegen", "status": "completed", "issued_at_ms": record["sealed_at_ms"],
                            "expires_at_ms": record["sealed_at_ms"] + 86400000, "started_at_ms": marker["controller_dispatch_mark_ms"],
                            "completed_at_ms": completed, "arguments": prepared["tool_arguments"], "output_sha256": png["sha256"],
                            "invocation_ref": data.get("platform_invocation_ref")}
    # The only secret access is the original recorder's internal authenticator.
    # No new key, exported key, accepted-PNG shortcut or caller context.
    save(dest / "sealed-observation.json", {"record": record,
        "mac_sha256": hmac.new(e._key(root), e.canonical(record), hashlib.sha256).hexdigest()})
    return {"status": "SEALED_" + record["actual_call_outcome"].upper(), "automatic_retry": False}


class ScopedRootEventProvider(e.RootEventProvider):
    """Original provider identity/transport, scoped installation resolution."""
    def checked(self):
        require(_LOCK.get() == self.root, "provider requires the canonical recorder lock")
        values = load(self.root)
        preparation(values, self.leaf_id)
        dest, prepared, record = e._authenticated(self.root, values[1], self.leaf_id)
        current_scope(values, prepared["scope_binding"])
        from deck_master import capabilities
        require(capabilities.installation_identity() == prepared["identity"], "actual scoped installation changed")
        return dest, prepared, record

    def health(self):
        try:
            self.checked()
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def fetch(self, event_id):
        dest, prepared, _ = self.checked()
        require(event_id == prepared["event_id"], "foreign native event")
        return (dest / "sealed-observation.json").read_bytes()

    def verify(self, raw):
        from deck_master.native_image_evidence import NativeImageCompletion
        dest, prepared, record = self.checked()
        require(raw == (dest / "sealed-observation.json").read_bytes() and record["actual_call_outcome"] == "consumed"
                and not record.get("unusable_output_or_reference"), "exact usable first original protected observation required")
        for ref in (record["callback_source"], record["frozen_first_callback"], record["callback"]["native_response"], record["original_png"]):
            c.check_ref(ref)
        b.unchanged_references(prepared["reference_snapshots"])
        return NativeImageCompletion(deepcopy(record["claims"]), Path(record["original_png"]["path"]).read_bytes())


@contextmanager
def native(values, leaf):
    from deck_master.native_image_evidence import (
        NativeImageRegistry,
        NativeImageRuntime,
    )
    preparation(values, leaf)
    registry = NativeImageRegistry()
    registry.register(ScopedRootEventProvider(values[0], values[1], leaf))
    with NativeImageRuntime(registry).bound():
        yield registry


def settle(values, leaf):
    root, config = values[:2]
    dest, prepared = preparation(values, leaf)
    _, _, record = e._authenticated(root, config, leaf)
    require(not (dest / "settlement.json").exists()
            and not any(r["leaf_id"] == leaf for r in events(values[6], "m02_read_settlement_reconciled"))
            and not any(r["operation"] == "tasks.call_settle" and all(r["arguments"].get(k) == prepared["row"][k]
                        for k in ("task_id", "allowance_id", "attempt_id")) for r in events(values[6], "sdk_intent")),
            "settlement already attempted/recorded/reconciled")
    from deck_master import tasks
    store = c.store_for(values[7][1])
    outcome = record["actual_call_outcome"]
    rejection = None
    with native(values, leaf) as registry:
        context = None
        if outcome == "consumed":
            try:
                context = registry.image_context(store, store.load_document(), task_id=prepared["row"]["task_id"],
                    attempt_id=prepared["row"]["attempt_id"], selector={"provider_id": e.PROVIDER, "event_id": prepared["event_id"]})
            except Exception as exc:  # noqa: BLE001 - preserve actual native-context rejection before settling unknown
                rejection = {"type": type(exc).__name__, "detail": str(exc)}
        report = ({"source": "native_host_image.v1", "provider_id": e.PROVIDER, "event_id": prepared["event_id"]}
                  if outcome == "consumed" else {"source": "rc3-root-uncertain-image-event.v1", "observation": reference(dest / "sealed-observation.json")})
        args = {**{k: prepared["row"][k] for k in ("task_id", "allowance_id", "attempt_id")}, "outcome": outcome, "report": report}
        result = c.record_sdk(values[6], "tasks.call_settle", args, lambda: tasks.call_settle(store,
            **{k: args[k] for k in ("task_id", "allowance_id", "attempt_id", "outcome")}, report_bytes=e.canonical(report),
            invocation_ref=record["callback"].get("platform_invocation_ref"), adapter_context=context))
    value = {"status": "SETTLED", "actual_result": result, "context_rejection": rejection, "actual_call_outcome": outcome,
             "automatic_retry": False, "automatic_adoption": False}
    save(dest / "settlement.json", value)
    return value


def query(values, leaf):
    require(leaf in LEAVES, "exact original read leaf required")
    _, prepared = preparation(values, leaf)
    from deck_master import generation
    journal = values[6]
    key = secrets.token_hex(16)
    journal.append("m02_read_query_intent", {"query_key": key, "transition": transition_ref(values[0]), "leaf": leaf})
    try:
        shown = generation.show(prepared["row"]["project"], attempt_id=prepared["row"]["attempt_id"])
    except Exception as exc:
        journal.append("m02_read_query_error", {"query_key": key, "type": type(exc).__name__, "error": str(exc)})
        raise
    journal.append("m02_read_query_outcome", {"query_key": key, "result": shown})
    if shown["call"]["state"] in {"consumed", "unknown", "released"}:
        for pending in journal.unfinished().values():
            if pending["operation"] == "tasks.call_settle" and all(pending["arguments"].get(k) == prepared["row"][k]
                    for k in ("task_id", "allowance_id", "attempt_id")):
                journal.append("sdk_reconciliation", {"operation_key": pending["operation_key"], "actual_query": key,
                    "result": shown, "retry_authorized": False})
                journal.append("m02_read_settlement_reconciled", {"leaf_id": leaf, "actual_query": key,
                    "actual_state": shown["call"]["state"], "retry_authorized": False, "budget_refund": False})
    return {"actual_query": shown, "automatic_retry": False, "budget_refund": False}


def execute(root, command, *, barrier_path=None, handoff=None, arguments=None, leaf=None, callback=None, bootstrap=None):
    if command in {"status", "query"}:
        return execute_bound(root, command, barrier_path=barrier_path, handoff=handoff, arguments=arguments,
                             leaf=leaf, callback=callback, bootstrap=bootstrap)
    with c.native_runtime(bootstrap):
        return execute_bound(root, command, barrier_path=barrier_path, handoff=handoff, arguments=arguments,
                             leaf=leaf, callback=callback, bootstrap=bootstrap)


def execute_bound(root_path, command, *, barrier_path=None, handoff=None, arguments=None, leaf=None, callback=None, bootstrap=None):
    """Finite original SDK operations; no operation/context/Store/receipt selector."""
    with locked(root_path) as root:
        values = load(root)
        journal = values[6]
        j, state, cfg = values[7]
        if command == "status":
            return {"transition": transition_ref(root), "all_charged_rows": values[4], "read_grant": read_grant(values),
                    "read_grant_requested": bool(events(journal, "m02_read_grant_requested")), "read_tasks": opened_tasks(values),
                    "pending": {"successor": j.unfinished(), "transition": journal.unfinished()}, "costs": s11.costs(j, cfg),
                    "transition_SDK_attempts": len(events(journal, "sdk_intent")), "transition_SDK_queries": len(events(journal, "m02_read_query_intent")),
                    "credit": "NOT_FORMAL_ACCEPTANCE"}
        if command == "query":
            return query(values, leaf)
        if command != "seal":
            require(not journal.unfinished() and not j.unfinished(), "unresolved old/successor/transition SDK intent; exact query, no retry")
        barrier(values, command, barrier_path, bootstrap)
        if command not in {"seal", "settle"}:
            s11.require_effective_budget(j, cfg)
            require_resolved_read_dispatches(values)
        if command == "prepare":
            return prepare(values, handoff)
        if command == "mark":
            return mark(values, leaf, bootstrap)
        if command == "seal":
            return seal(values, leaf, callback, bootstrap)
        if command == "settle":
            return settle(values, leaf)
        store, doc, scope = current_scope(values, handoff, task_required=command not in {"open-task", "grant-read"})
        from deck_master import generation, service, tasks
        args = deepcopy(arguments or {})
        if command == "grant-read":
            from deck_master import collaboration
            require(not events(journal, "m02_read_grant_requested")
                    and not any(x["operation"] == "collaboration.grant" for x in events(journal, "sdk_intent")), "one grant attempt; never reopen a pool")
            require(set(args) == {"input", "base_revision", "operation_id"} and args["base_revision"] == doc["revision_id"], "current ordinary read grant only")
            grant = args["input"]
            require(set(grant) == {"mode", "actions", "scope", "max_external_calls", "max_candidate_count", "adoption_policy", "instruction_evidence"}
                    and grant["mode"] == "execute" and grant["max_external_calls"] == grant["max_candidate_count"] == 2
                    and set(grant["actions"]) == {"dispatch.blueprint", "allowance.allocate", "task.start", "call.begin", "result.accept"}
                    and grant["scope"] == doc["collaboration"]["request"]["scope"] and grant["adoption_policy"] == "within_scope",
                    "fixed original bounded2 read grant; no live pool/identity/scope transfer")
            s11.m.check_evidence(j, grant["instruction_evidence"], "read")
            s11.m.scope_check(grant["scope"], cfg["scopes"]["read"])
            require(not any(store.read_object_json(r).get("request_id") == handoff["actual_request_id"]
                            and store.read_object_json(r).get("mode") == "execute"
                            and (store.read_object_json(r).get("max_external_calls", 0) > 0
                                 or store.read_object_json(r).get("max_candidate_count", 0) > 0)
                            for r in doc["collaboration"]["authorizations"]), "actual read production grant already exists")
            journal.append("m02_read_grant_requested", {"request_id": handoff["actual_request_id"],
                "occurrence": handoff["instruction_occurrence_ref"], "SDK_arguments": deepcopy(args)})
            result = c.record_sdk(journal, "collaboration.grant", args, lambda: collaboration.grant(state["project"], **args))
            return {"actual_result": result, "read_grant_binding": read_grant(values, required=True)}
        if command == "open-task":
            read_grant(values, required=True)
            require(set(args) == {"page_id"} and args["page_id"] in {x["page_label"] for x in scope["leaves"]}, "one original read Page only")
            leaf = next(x["leaf_id"] for x in scope["leaves"] if x["page_label"] == args["page_id"])
            capacity(values, leaf)
            require(not any(r["operation"] == "service.open_blueprint_task" and r["arguments"]["page_id"] == args["page_id"]
                            for r in events(journal, "sdk_intent")), "one actual Task attempt per leaf; errors never reopen")
            entry = next(x for x in doc["pages"] if x["page_id"] == args["page_id"])
            result = c.record_sdk(journal, "service.open_blueprint_task", args, lambda: service.open_blueprint_task(store, doc, entry))
            return result
        store, doc, task, _methods, _ = actual_task(values, handoff, claimed=command != "claim")
        if command == "claim":
            capacity(values, handoff["leaf_id"])
            invocation, _ = s11.c.execution(j, handoff["stage"], handoff["ordinal"])
            require(set(args) == {"execution_ref"} and args["execution_ref"] == invocation["executor"], "actual S11 executor only")
            return c.record_sdk(journal, "service.task_start", {"task_id": task["task_id"], **args}, lambda: service.task_start(state["project"],
                task_id=task["task_id"], execution_ref=args["execution_ref"], supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"]))
        if command == "methods":
            require(not args, "no method selector")
            result = c.record_sdk(journal, "method_resources.read_task_methods", {"task_id": task["task_id"]},
                                  lambda: c.read_installed_task_methods(state, task))
            ref = save(journal.root / "methods" / (task["task_id"] + "-" + secrets.token_hex(8) + ".json"), result)
            journal.append("m02_read_methods_returned", {"task_id": task["task_id"], "executor": task["execution_ref"], "record": ref})
            _, target = s11.c.execution(j, handoff["stage"], handoff["ordinal"])
            first = target / "method-read-record.json"
            if not first.exists():
                original = s11.c.save(first, result)
                j.append("method_bytes_returned", {"ordinal": handoff["ordinal"], "executor": task["execution_ref"], "record": original,
                    "limitation": "full SDK bytes returned; Root separately observes actual read/application"})
            return {"methods": result, "record": ref, "successor_method_record": reference(first)}
        if command == "allocate":
            capacity(values, handoff["leaf_id"])
            require(set(args) == {"operation_id"} and not task.get("call_allowances"), "one actual initial allowance only")
            return c.record_sdk(journal, "tasks.allocate_call_allowances", {"task_id": task["task_id"], "count": 1, **args},
                lambda: tasks.allocate_call_allowances(store, task_id=task["task_id"], count=1, **args))
        if command == "freeze":
            capacity(values, handoff["leaf_id"])
            applied_methods(values, handoff)
            require(set(args) == {"input", "base_revision", "operation_id"} and args["base_revision"] == doc["revision_id"]
                    and args["input"]["parameters"] == {"transparent_background": False} and not task.get("generation_requests"),
                    "first exact-false current Request only")
            return c.record_sdk(journal, "generation.freeze", {"task_id": task["task_id"], **args},
                lambda: generation.freeze(state["project"], task_id=task["task_id"], **args))
        if command == "begin":
            capacity(values, handoff["leaf_id"])
            applied_methods(values, handoff)
            require(set(args) == {"execution_ref", "request_id"} and args["execution_ref"] == task["execution_ref"], "same claimed executor/Request")
            allowance = next((a for a in task["call_allowances"] if a["allowance_id"] == handoff["allowance_id"]), None)
            require(allowance and allowance["state"] == "reserved" and not task.get("generation_attempts"), "first actual unused allowance")
            require(any(store.read_object_json(r)["request_id"] == args["request_id"]
                        and store.read_object_json(r)["input"]["parameters"] == {"transparent_background": False}
                        for r in task["generation_requests"]), "same frozen false Request")
            return c.record_sdk(journal, "tasks.call_begin", {"task_id": task["task_id"], "allowance_id": allowance["allowance_id"], **args},
                lambda: tasks.call_begin(store, task_id=task["task_id"], allowance_id=allowance["allowance_id"], **args))
        if command == "accept-blueprint":
            require(not args, "only original S11 frozen output; no caller envelope")
            _, prepared = preparation(values, handoff["leaf_id"])
            _, _, envelope, _ = s11.c.observed_result(j, handoff["stage"], handoff["ordinal"])
            require(envelope["kind"] == "blueprint" and envelope["generation_result"] ==
                    {"request_id": prepared["row"]["generation_request_id"], "attempt_id": prepared["row"]["attempt_id"]}, "same actual first generation result")
            before = len(j.local.events())
            try:
                with native(values, handoff["leaf_id"]):
                    result = s11.m.accept(j, state, handoff["stage"], handoff["ordinal"])
            except Exception as exc:
                journal.append("m02_read_accept_error", {"task_id": task["task_id"], "type": type(exc).__name__, "error": str(exc),
                    "successor_pending": j.unfinished()})
                raise
            journal.append("m02_read_accept_link", {"task_id": task["task_id"], "transition": transition_ref(root),
                "actual_successor_events": [reference(j.root / "journal" / f"{x['sequence']:06d}.json") for x in j.local.events()[before:]]})
            return result
        raise e.ImageEventError("unsupported finite command")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("initialize", "status", "query", "grant-read", "open-task", "claim", "methods",
        "allocate", "freeze", "begin", "prepare", "mark", "seal", "settle", "accept-blueprint"))
    parser.add_argument("--root", required=True)
    for name in ("registration", "barrier", "binding", "arguments", "callback", "bootstrap"):
        parser.add_argument("--" + name)
    parser.add_argument("--leaf-id", choices=LEAVES)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated and sys.dont_write_bytecode, "use own absolute Python -I -B")
        if args.command == "initialize":
            result = initialize(args.registration, args.root)
        else:
            result = execute(args.root, args.command, barrier_path=args.barrier,
                handoff=read(args.binding) if args.binding else None, arguments=read(args.arguments) if args.arguments else None,
                leaf=args.leaf_id, callback=args.callback, bootstrap=args.bootstrap)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

