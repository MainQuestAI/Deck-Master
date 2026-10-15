#!/usr/bin/env python3
"""Scoped image-event accounting and own-SDK transport; never calls imagegen.

Root supplies real host-attested observations. Engineering observations remain
engineering. An epoch is an append-only policy at the same canonical formal ig,
not a new allowance, model invocation, human approval or permission to retry.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import stat
import sys

COMMON_SHA = "d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261"
PRIMITIVES_SHA = "bf3998cfb8e8bd0f3aaafb743859fac42dc355a282c5ecab07045877767a33f7"


def _dependency(name, expected):
    path = Path(__file__).with_name(name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("frozen dependency changed before import: " + name)
    spec = importlib.util.spec_from_file_location("rc3_image_event_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


c = _dependency("controller.py", COMMON_SHA)
b = _dependency("image_controller.py", PRIMITIVES_SHA)
FORMAT = "rc3-image-event-registration.v1"
POLICY = "rc3-image-event-policy.v1"
HANDOFF = "rc3-image-scope-handoff.v1"
VERSION = "rc3-image-event-controller.v1"
PROVIDER = "rc3-root-image-event-v1"
ENGINEERING = b.ENGINEERING
canonical, digest, read, reference, check_ref = b.canonical, b.digest, b.read, b.reference, b.check_ref


class ImageEventError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ImageEventError(message)


def save(path, value):
    b.save(path, value)
    descriptor = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return reference(path)


def _finite(value):
    return type(value) is int and value >= 0


def _parent_key(parent):
    return tuple(parent[k] for k in ("case", "whole_run_id", "repetition", "arm"))


def validate_policy(policy):
    require(policy.get("format") == POLICY and policy.get("status") in {"ADMITTED", ENGINEERING}, "wrong event policy/status")
    b.canonical_root(policy.get("ledger_root"))
    require(_finite(policy.get("total_call_cap")) and policy["total_call_cap"] > 0, "finite global image cap required")
    for key in ("protocol", "Root_decision"):
        check_ref(policy[key])
    parents, scopes = policy.get("parents"), policy.get("scopes")
    require(isinstance(parents, list) and parents and isinstance(scopes, list) and scopes, "register original parents and finite scope leaves")
    parent_ids, identities = set(), set()
    for parent in parents:
        b.safe_name(parent["parent_id"])
        identity = _parent_key(parent)
        require(parent["parent_id"] not in parent_ids and identity not in identities, "duplicate original wholeflow/arm parent")
        require(all(isinstance(parent.get(k), str) and parent[k] for k in ("matrix_slot", "case", "whole_run_id", "arm")) and type(parent.get("repetition")) is int and parent["repetition"] > 0, "actual original parent identity required")
        require(_finite(parent.get("max_calls")), "finite original wholeflow cap required")
        parent_ids.add(parent["parent_id"]); identities.add(identity)
    scope_ids, leaf_ids = set(), set()
    for scope in scopes:
        b.safe_name(scope["scope_slot"])
        require(scope["scope_slot"] not in scope_ids and scope.get("parent_id") in parent_ids, "duplicate or foreign scope")
        require(isinstance(scope.get("checkpoint"), str) and scope["checkpoint"], "fixed original checkpoint required")
        check_ref(scope["instruction"])
        require(_finite(scope.get("max_calls")) and scope.get("leaves"), "finite nonempty scope leaves required")
        labels = set()
        for leaf in scope["leaves"]:
            b.safe_name(leaf["leaf_id"])
            require(leaf["leaf_id"] not in leaf_ids and leaf.get("page_label") and leaf["page_label"] not in labels, "duplicate semantic leaf/Page in scope")
            require((leaf.get("max_calls"), leaf.get("max_candidates"), leaf.get("retries")) == (1, 1, 0) and all(type(leaf.get(k)) is int for k in ("max_calls", "max_candidates", "retries")), "each actual leaf is one call/one candidate/retry0")
            require(leaf.get("page_id") is None or isinstance(leaf["page_id"], str) and leaf["page_id"], "future Page binding is null or actual stable ID")
            leaf_ids.add(leaf["leaf_id"]); labels.add(leaf["page_label"])
        require(scope["max_calls"] <= len(scope["leaves"]), "scope cap exceeds its own leaves")
        scope_ids.add(scope["scope_slot"])
    for parent in parents:
        require(parent["max_calls"] <= sum(s["max_calls"] for s in scopes if s["parent_id"] == parent["parent_id"]), "parent cap exceeds declared scopes")
    require(policy["total_call_cap"] <= sum(p["max_calls"] for p in parents), "global cap exceeds original parents")
    return policy


def validate_config(config):
    require(config.get("format") == FORMAT and config.get("status") in {"ADMITTED", ENGINEERING}, "separate event registration required")
    require(config.get("controller_sha256") == digest(Path(__file__).read_bytes()), "event controller identity changed")
    for key, name, expected in (("sdk_controller", "controller.py", COMMON_SHA), ("bf_primitives", "image_controller.py", PRIMITIVES_SHA)):
        check_ref(config[key])
        require(Path(config[key]["path"]).resolve() == Path(__file__).with_name(name).resolve() and config[key]["sha256"] == expected, "pin the exact sibling mechanical dependency")
    for key in ("policy", "protocol", "admission_review", "activation"):
        check_ref(config[key])
    policy = validate_policy(read(config["policy"]["path"]))
    require(policy["status"] == config["status"] and policy["protocol"] == config["protocol"], "event policy/registration scope differs")
    require(config.get("installations") and {p["arm"] for p in policy["parents"]} <= set(config["installations"]), "every original arm needs its own actual installation")
    activation = read(config["activation"]["path"])
    require(activation.get("assurance") == "host_attested" and activation.get("observer_id") == "/root" and activation.get("policy_sha256") == config["policy"]["sha256"] and activation.get("legacy_writer_route") == "HISTORICAL_READ_ONLY", "Root must explicitly select this same-root active epoch; old writers stay historical")
    require(activation.get("evidence_kind") == (ENGINEERING if config["status"] == ENGINEERING else "ROOT_ACTUAL_DECISION"), "engineering decisions cannot admit formal scope")
    for value in config.get("legacy_policy_refs", []):
        check_ref(value)
    return config


def _legacy_files(root):
    directory = Path(root) / "dispatches"
    require(not directory.is_symlink(), "legacy namespace cannot be a symlink")
    return [reference(path) for path in sorted(directory.glob("*.json"))]


def _legacy_rows(config, files):
    policy = read(config["policy"]["path"])
    mappings = config.get("legacy_mapping", [])
    require(len(mappings) == len(files) and {m["dispatch_sha256"] for m in mappings} == {r["sha256"] for r in files}, "every old dispatch/unknown needs an exact immutable scope mapping")
    result = []
    for ref in files:
        item = read(ref["path"])
        mapping = next(m for m in mappings if m["dispatch_sha256"] == ref["sha256"])
        scope = next((s for s in policy["scopes"] if s["scope_slot"] == mapping["scope_slot"]), None)
        require(scope is not None, "legacy mapping has a foreign scope")
        parent = next(p for p in policy["parents"] if p["parent_id"] == scope["parent_id"])
        require(tuple(item.get(k) for k in ("case", "whole_run_id", "repetition", "arm")) == _parent_key(parent), "legacy spend cannot change its original wholeflow")
        leaf = next((v for v in scope["leaves"] if v["leaf_id"] == mapping["leaf_id"]), None)
        require(leaf and (leaf.get("page_id") is None or leaf["page_id"] == item["page_id"]), "legacy spend Page differs")
        result.append({"parent_id": parent["parent_id"], "case": parent["case"], "scope_slot": scope["scope_slot"], "leaf_id": leaf["leaf_id"], "page_id": item["page_id"], "project_id": mapping["project_id"], "project": mapping["project"], "checkpoint": scope["checkpoint"], "page_label": leaf["page_label"], "actual_request_id": mapping["actual_request_id"], "instruction_occurrence_sha256": mapping["instruction_occurrence_sha256"], "task_id": item["task_id"], "generation_request_id": item["request_id"], "authorization_id": item["authorization_id"], "budget_root_id": mapping["budget_root_id"], "allowance_id": mapping["allowance_id"], "attempt_id": item["attempt_id"], "legacy_dispatch": ref})
    return result


def initialize_epoch(config_path, root):
    config = validate_config(read(config_path))
    policy = read(config["policy"]["path"])
    root = b.canonical_root(str(root))
    require(root == b.canonical_root(policy["ledger_root"]), "never initialize another ledger root")
    root.mkdir(parents=True, exist_ok=True)
    with b.locked(root):
        require(not (root / "event-registration.json").exists(), "same-root event epoch already exists; never reset")
        actual = [reference(root / name) for name in ("global-budget.json", "budget-origin.json") if (root / name).exists()]
        require(actual == config.get("legacy_policy_refs", []), "preserve and acknowledge every original policy file, even with zero spend")
        files = _legacy_files(root)
        rows = _legacy_rows(config, files)
        _caps(policy, rows)
        save(root / "event-registration.json", config)
        save(root / "event-origin.json", {"source": reference(config_path), "registration_sha256": digest(canonical(config)), "root": str(root)})
        save(root / "event-legacy-frontier.json", {"files": files, "charged_rows": rows, "legacy_policies": actual})
        # A separate NEW observer key, never the historical bf private key.
        descriptor = os.open(root / ".private-event-observer-key", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(secrets.token_bytes(32)); stream.flush(); os.fsync(stream.fileno())
    return {"status": "EVENT_EPOCH_REGISTERED", "evidence_kind": config["status"], "legacy_calls_charged": len(rows), "native_calls_made": 0}


def load(root):
    root = b.canonical_root(str(root))
    config = validate_config(read(root / "event-registration.json"))
    policy = read(config["policy"]["path"])
    require(root == b.canonical_root(policy["ledger_root"]), "copied ledger cannot reset original budget")
    origin = read(root / "event-origin.json")
    require(origin["registration_sha256"] == digest(canonical(config)) and origin["root"] == str(root), "event registration/origin changed")
    check_ref(origin["source"])
    frontier = read(root / "event-legacy-frontier.json")
    require(_legacy_files(root) == frontier["files"], "legacy writer appended/changed after event epoch activation")
    require(frontier["legacy_policies"] == config.get("legacy_policy_refs", []) and frontier["charged_rows"] == _legacy_rows(config, frontier["files"]), "original legacy scope mappings/charges changed")
    for ref in frontier["legacy_policies"]:
        check_ref(ref)
    return root, config, policy, frontier


def _records(root, frontier):
    rows = list(frontier["charged_rows"])
    paths = sorted((Path(root) / "event-dispatches").glob("*.json"))
    previous, typed = None, {}
    for index, path in enumerate(paths, 1):
        row = read(path)
        require(path.name == f"{index:06d}.json" and row["event_ordinal"] == index and row.get("previous_event_sha256") == previous, "event dispatch sequence/hash chain changed")
        dest = _call_dir(root, row["leaf_id"])
        p = read(dest / "preparation.json")
        require(reference(dest / "preparation.json")["sha256"] == row["preparation_sha256"] and all(row.get(k) == v for k, v in p["row"].items()), "charged event lost/changed its exact original preparation")
        previous = reference(path)["sha256"]
        typed[row["event_id"]] = row
        rows.append(row)
    for path in (Path(root) / "event-calls").glob("*/dispatch-mark.json"):
        marker = read(path)
        require(typed.get(marker["event_id"]) == marker, "local dispatch mark lacks its original global charge")
    return rows


def _caps(policy, rows, proposed=None):
    allrows = rows + ([proposed] if proposed else [])
    require(len(allrows) <= policy["total_call_cap"], "global image cap exhausted")
    for parent in policy["parents"]:
        require(sum(r["parent_id"] == parent["parent_id"] for r in allrows) <= parent["max_calls"], "original wholeflow/arm cap exhausted")
    for scope in policy["scopes"]:
        require(sum(r["scope_slot"] == scope["scope_slot"] for r in allrows) <= scope["max_calls"], "scope image cap exhausted")
    leaves = [r["leaf_id"] for r in allrows]
    require(len(leaves) == len(set(leaves)), "stable Page leaf already charged; no retry/refund")
    for key in ("attempt_id",):
        values = [r[key] for r in allrows]
        require(len(values) == len(set(values)), "actual invocation already charged under another name")
    calls = [(r["project_id"], r["task_id"], r["allowance_id"]) for r in allrows]
    require(len(calls) == len(set(calls)), "actual allowance already charged under another event/op/batch")


def _scope(config, binding):
    policy = read(config["policy"]["path"])
    scope = next((s for s in policy["scopes"] if s["scope_slot"] == binding["scope_slot"]), None)
    require(scope is not None, "scope not preregistered")
    parent = next(p for p in policy["parents"] if p["parent_id"] == scope["parent_id"])
    return policy, parent, scope


def validate_scope_binding(config, binding, *, before_begin=False):
    require(binding.get("format") == HANDOFF, "use the explicit actual scope handoff")
    policy, parent, scope = _scope(config, binding)
    for key in ("matrix_slot", "whole_run_id", "repetition", "arm"):
        require(binding.get(key) == parent[key], "scope tries to rename its original parent: " + key)
    require(binding.get("case") in {parent["case"], scope["checkpoint"]} and binding.get("checkpoint") == scope["checkpoint"], "wrong original checkpoint")
    project = b.canonical_root(binding.get("project"))
    ledger = b.canonical_root(policy["ledger_root"])
    require(not project.is_relative_to(ledger) and not ledger.is_relative_to(project), "project and private ledger must be separate roots")
    for key in ("instruction_occurrence_ref", "packet_audit_ref"):
        check_ref(binding[key])
    occurrence = read(binding["instruction_occurrence_ref"]["path"])
    require(occurrence.get("assurance") == "host_attested" and occurrence.get("observer_id") == "/root" and occurrence.get("actual_trigger_satisfied") is True and occurrence.get("scope_slot") == scope["scope_slot"] and occurrence.get("instruction_sha256") == scope["instruction"]["sha256"] and occurrence.get("source_observations"), "event needs an actually observed new explicit instruction occurrence")
    require(occurrence.get("evidence_kind") == (ENGINEERING if config["status"] == ENGINEERING else "ROOT_ACTUAL_NATIVE"), "engineering trigger cannot become formal authority")
    for value in occurrence["source_observations"]:
        check_ref(value)
    audit = read(binding["packet_audit_ref"]["path"])
    require(audit.get("status") == "PASS" and audit.get("scope_slot") == scope["scope_slot"] and audit.get("required_read_closure_checked") is True and audit.get("raw_workorder_preserved") is True, "actual required-read packet audit pending")
    require(all(audit.get(key) == binding.get(key) for key in ("task_id", "project", "stage")), "packet audit belongs to a different actual Task/project/stage")
    for key in ("original_raw_ref", "author_view_ref", "read_closure_manifest_ref"):
        check_ref(audit[key])
    required = ("actual_request_id", "task_id", "allowance_id", "stage") + (() if before_begin else ("attempt_id",))
    require(all(binding.get(key) for key in required), "actual returned SDK bindings required; null is not dispatchable")
    return {"policy": policy, "parent": parent, "scope": scope}


def inspect_own_rights(config, binding, page_id, attempt_id=None):
    facts = validate_scope_binding(config, binding)
    arm = binding["arm"]
    identity = c.installation(config, arm)
    from deck_master import eligibility, generation, tasks
    from deck_master.store import Store
    store = Store(binding["project"]); doc = store.load_document()
    task = c.task_for(store, binding["task_id"])
    require(task["scope_pages"] == [page_id] and task["status"] == "running", "actual claimed single Page Task required")
    require(doc["collaboration"]["request"]["request_id"] == binding["actual_request_id"], "scope does not own the actual current collaboration Request")
    evidence = doc["collaboration"]["request"].get("instruction_evidence") or {}
    require(evidence.get("source_ref") and digest(store.read_object_bytes(evidence["source_ref"])) == facts["scope"]["instruction"]["sha256"], "own current Request does not bind the exact scope instruction")
    attempt_id = attempt_id or binding["attempt_id"]
    require(attempt_id == binding["attempt_id"], "cannot substitute another Attempt")
    legacy = config["installations"][arm].get("adapter_profile") == "A0-public-legacy"
    if legacy:
        shown = generation.show(binding["project"], attempt_id=attempt_id)
        attempt = shown["attempt"]; request = store.read_object_json(attempt["request_ref"])
        native_binding = {"project_id": doc["project_id"], "task_id": task["task_id"], "attempt": attempt, "request": request, "control_revision": doc["revision_id"], "adapter_profile": "A0-own-generation.v1"}
        capability = "BLOCKED_MISSING_OWN_NATIVE_OBSERVATION"
    else:
        from deck_master.native_image_evidence import image_binding
        native_binding, task, attempt, request = image_binding(store, doc, task["task_id"], attempt_id)
        capability = "OWN_NATIVE_IMAGE_REGISTRY"
    allowance = next((x for x in task.get("call_allowances", []) if x["allowance_id"] == binding["allowance_id"]), None)
    require(allowance and allowance["state"] == "in_flight" and attempt["allowance_id"] == allowance["allowance_id"] and task.get("execution_ref") == attempt["execution_ref"], "bind the real first in-flight allowance/claim")
    require(not attempt.get("observations") and request["input"]["parameters"] == {"transparent_background": False}, "first unobserved frozen exact opaque-background Request required")
    require(tasks.task_inputs_current(store, doc, task), "actual Task basis changed")
    eligibility.guard(store, doc, "call.begin", context={"task": task, "allowance_id": allowance["allowance_id"], "targets": {"page_ids": [page_id]}})
    authref = (task.get("collaboration_binding") or {}).get("authorization_ref")
    require(authref, "Task has no actual production authorization")
    auth = store.read_object_json(authref)
    budget = eligibility.authorization_budget(store, doc, authref)
    root_auth, seen = auth, set()
    while root_auth.get("budget_parent_ref"):
        require(root_auth["authorization_id"] not in seen and len(seen) < 8, "invalid actual budget parent chain")
        seen.add(root_auth["authorization_id"])
        root_auth = store.read_object_json(root_auth["budget_parent_ref"])
    arguments, refs = b.actual_arguments(binding["project"], request)
    return {"status": "CURRENT_OWN_RIGHTS", "native_product_capability": capability, "identity": identity, "project_id": doc["project_id"], "task": task, "attempt": attempt, "request": request, "binding": native_binding, "authorization_ref": authref, "authorization_id": auth["authorization_id"], "budget_root_id": root_auth["authorization_id"], "parent_budget": budget, "tool_arguments": arguments, "reference_snapshots": refs}


def guard_call_begin(config, binding, page_id, arguments):
    """Read actual reserved rights before the caller invokes its own SDK begin.

    No Attempt is invented: the caller appends the actual returned ID afterward.
    Global dispatch is charged separately immediately before Root's real tool.
    """
    facts = validate_scope_binding(config, binding, before_begin=True)
    root = b.canonical_root(facts["policy"]["ledger_root"])
    c.installation(config, binding["arm"])
    from deck_master import eligibility, tasks
    from deck_master.store import Store
    store = Store(binding["project"]); doc = store.load_document()
    task = c.task_for(store, binding["task_id"])
    require(task["status"] == "running" and task["scope_pages"] == [page_id] and task.get("execution_ref") == arguments.get("execution_ref"), "claim the actual single Page Task before begin")
    require(arguments.get("task_id") == task["task_id"] and arguments.get("allowance_id") == binding["allowance_id"], "begin cannot substitute another Task/allowance")
    require(doc["collaboration"]["request"]["request_id"] == binding["actual_request_id"], "actual collaboration Request changed")
    evidence = doc["collaboration"]["request"].get("instruction_evidence") or {}
    require(evidence.get("source_ref") and digest(store.read_object_bytes(evidence["source_ref"])) == facts["scope"]["instruction"]["sha256"], "begin instruction differs from the fixed actual scope")
    allowance = next((x for x in task.get("call_allowances", []) if x["allowance_id"] == binding["allowance_id"]), None)
    require(allowance and allowance["state"] == "reserved", "only an unused real reserved allowance may newly begin; query/reconcile an existing attempt")
    requests = [store.read_object_json(r) for r in task.get("generation_requests", [])]
    request = next((r for r in requests if r["request_id"] == arguments.get("request_id")), None)
    require(request and request["task_id"] == task["task_id"] and request["input"]["parameters"] == {"transparent_background": False}, "freeze the actual exact false-parameter generation Request first")
    require(tasks.task_inputs_current(store, doc, task), "begin Task basis is stale")
    eligibility.guard(store, doc, "call.begin", context={"task": task, "allowance_id": binding["allowance_id"], "targets": {"page_ids": [page_id]}})
    leaves = [v for v in facts["scope"]["leaves"] if v.get("page_id") == page_id or v.get("page_id") is None and v["leaf_id"] == binding.get("leaf_id")]
    require(len(leaves) == 1, "bind one preregistered actual Page leaf before begin")
    with b.locked(root):
        root, actual_config, policy, frontier = load(root)
        require(actual_config == config, "begin must use the exact active event registration")
        rows = _records(root, frontier)
        require(len(rows) < policy["total_call_cap"] and sum(r["parent_id"] == facts["parent"]["parent_id"] for r in rows) < facts["parent"]["max_calls"] and sum(r["scope_slot"] == binding["scope_slot"] for r in rows) < facts["scope"]["max_calls"] and all(r["leaf_id"] != leaves[0]["leaf_id"] for r in rows), "campaign global/parent/scope/Page budget exhausted before begin")
    return {"status": "OWN_RESERVED_RIGHTS_CHECKED_NOT_BEGUN", "leaf_id": leaves[0]["leaf_id"], "project_id": doc["project_id"], "attempt_id": None, "no_permission_minted": True}


def _call_dir(root, leaf_id):
    return Path(root) / "event-calls" / b.safe_name(leaf_id)


def prepare_page_call(root, binding, leaf_id, attempt_id):
    root = b.canonical_root(str(root))
    with b.locked(root):
        root, config, policy, frontier = load(root)
        spec = validate_scope_binding(config, binding)
        leaf = next((v for v in spec["scope"]["leaves"] if v["leaf_id"] == leaf_id), None)
        require(leaf, "leaf does not belong to this real scope")
        page_id = leaf.get("page_id") or binding.get("page_id")
        require(page_id, "bind an actual Page before preparation, not a future placeholder")
        actual = inspect_own_rights(config, binding, page_id, attempt_id)
        require(actual["native_product_capability"] == "OWN_NATIVE_IMAGE_REGISTRY" or spec["scope"].get("allow_A0_host_observed_only") is True, "own native capability blocked; no B adapter transplant")
        dest = _call_dir(root, leaf_id)
        require(not dest.exists(), "original preparation already exists; never replace it")
        row = {"parent_id": spec["parent"]["parent_id"], "case": spec["parent"]["case"], "scope_slot": binding["scope_slot"], "leaf_id": leaf_id, "page_id": page_id, "page_label": leaf["page_label"], "checkpoint": binding["checkpoint"], "project_id": actual["project_id"], "project": binding["project"], "actual_request_id": binding["actual_request_id"], "instruction_occurrence_sha256": binding["instruction_occurrence_ref"]["sha256"], "task_id": actual["task"]["task_id"], "allowance_id": actual["attempt"]["allowance_id"], "attempt_id": attempt_id, "generation_request_id": actual["request"]["request_id"], "authorization_id": actual["authorization_id"], "budget_root_id": actual["budget_root_id"]}
        _check_events(_records(root, frontier), row)
        _caps(policy, _records(root, frontier), row)
        preparation = {"format": "rc3-image-event-preparation.v1", "event_id": "rc3-event-" + secrets.token_hex(16), "provider_id": PROVIDER, "registration_sha256": digest(canonical(config)), "scope_binding": deepcopy(binding), "row": row, "binding": actual["binding"], "identity": actual["identity"], "native_product_capability": actual["native_product_capability"], "parent_budget_at_prepare": actual["parent_budget"], "tool_arguments": actual["tool_arguments"], "reference_snapshots": actual["reference_snapshots"], "prepared_at_ms": b.now_ms()}
        save(dest / "preparation.json", preparation)
        save(dest / "literal-tool-arguments.json", actual["tool_arguments"])
        return {"status": "PREPARED_NOT_DISPATCHED", "preparation": reference(dest / "preparation.json"), "arguments": reference(dest / "literal-tool-arguments.json"), "native_product_capability": actual["native_product_capability"]}


def _check_events(rows, proposed):
    for old in rows:
        if old["parent_id"] != proposed["parent_id"]:
            require(old["project"] != proposed["project"] and old["project_id"] != proposed["project_id"], "same actual project cannot acquire a new parent/run name or copied path")
            continue
        if old["checkpoint"] == proposed["checkpoint"]:
            require((old["project_id"], old["project"]) == (proposed["project_id"], proposed["project"]), "checkpoint cannot be reset to a copied project")
            if old["page_label"] == proposed["page_label"]:
                require(old["page_id"] == proposed["page_id"], "stable Page cannot be renamed between events")
            if old["page_id"] == proposed["page_id"]:
                require(old["page_label"] == proposed["page_label"], "actual Page cannot acquire another semantic name")
        else:
            require(old["case"] == proposed["case"], "original parent case changed")
            if old["case"] == "M02":
                require({old["checkpoint"], proposed["checkpoint"]} <= {"live", "read"} and (old["project_id"], old["project"]) == (proposed["project_id"], proposed["project"]), "M02 two uses must stay in the same actual project")
            else:
                require(old["case"] == "Q4" and {old["checkpoint"], proposed["checkpoint"]} <= {"Q4A", "Q4B"} and old["project"] != proposed["project"] and old["project_id"] != proposed["project_id"], "independent Q4 checkpoints require separate real projects; no generic project alias")
        if old["scope_slot"] == proposed["scope_slot"]:
            require(all(old[k] == proposed[k] for k in ("actual_request_id", "instruction_occurrence_sha256", "budget_root_id")), "one multi-page scope shares its actual original parent, not copied new authority")
        else:
            require(all(old[k] != proposed[k] for k in ("actual_request_id", "instruction_occurrence_sha256", "authorization_id")), "new scope label/op/grant is not a genuine new instruction/current Request/right")


def _preparation(root, config, leaf_id):
    dest = _call_dir(root, leaf_id); p = read(dest / "preparation.json")
    require(p["registration_sha256"] == digest(canonical(config)), "preparation was rebound to another registration")
    require(read(dest / "literal-tool-arguments.json") == p["tool_arguments"], "literal tool arguments changed")
    return dest, p


def mark_dispatch(root, leaf_id, bootstrap_path):
    root = b.canonical_root(str(root))
    with b.locked(root):
        root, config, policy, frontier = load(root)
        dest, p = _preparation(root, config, leaf_id)
        require(not (dest / "dispatch-mark.json").exists(), "already marked; never resend an uncertain tool call")
        boot = b.bootstrap({**config, "sdk_controller": config["sdk_controller"]}, bootstrap_path)
        actual = inspect_own_rights(config, p["scope_binding"], p["row"]["page_id"], p["row"]["attempt_id"])
        require(all(actual[k] == p[k] for k in ("binding", "identity", "tool_arguments", "reference_snapshots", "native_product_capability")), "current own rights/literal inputs changed before dispatch")
        b.unchanged_references(p["reference_snapshots"])
        rows = _records(root, frontier)
        _check_events(rows, p["row"]); _caps(policy, rows, p["row"])
        ordinal = len(rows) - len(frontier["charged_rows"]) + 1
        previous = reference(root / "event-dispatches" / f"{ordinal-1:06d}.json")["sha256"] if ordinal > 1 else None
        value = {**p["row"], "event_ordinal": ordinal, "previous_event_sha256": previous, "event_id": p["event_id"], "preparation_sha256": reference(dest / "preparation.json")["sha256"], "arguments_sha256": digest(canonical(p["tool_arguments"])), "binding_sha256": digest(canonical(p["binding"])), "controller_dispatch_mark_ms": b.now_ms(), "bootstrap": boot, "automatic_retry": False, "cost": "CHARGED_PENDING_ROOT_TOOL_OBSERVATION"}
        save(root / "event-dispatches" / f"{ordinal:06d}.json", value)
        save(dest / "dispatch-mark.json", value)
        return value


def inspect_accounting(root):
    root = b.canonical_root(str(root))
    with b.locked(root):
        root, config, policy, frontier = load(root)
        rows = _records(root, frontier); _caps(policy, rows)
    return {"status": "ACCOUNTING_ONLY_NOT_QUALIFICATION", "evidence_kind": config["status"], "ledger_root": str(root), "total_charged": len(rows), "total_cap": policy["total_call_cap"], "legacy_charged": len(frontier["charged_rows"]), "by_parent": {p["parent_id"]: sum(r["parent_id"] == p["parent_id"] for r in rows) for p in policy["parents"]}, "by_scope": {s["scope_slot"]: sum(r["scope_slot"] == s["scope_slot"] for r in rows) for s in policy["scopes"]}, "all_rows": rows, "unknown_refunds": False}


def _key(root):
    descriptor = os.open(Path(root) / ".private-event-observer-key", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == os.getuid(), "new observer key must be owned mode600")
        value = os.read(descriptor, 33)
        require(len(value) == 32, "invalid new observer key")
        return value
    finally:
        os.close(descriptor)


def _authenticated(root, config, leaf_id):
    dest, p = _preparation(root, config, leaf_id)
    signed = read(dest / "sealed-observation.json"); record = signed["record"]
    require(hmac.compare_digest(signed["mac_sha256"], hmac.new(_key(root), canonical(record), hashlib.sha256).hexdigest()), "ordinary JSON/tampered observation has no protected event seal")
    require(record["event_id"] == p["event_id"] and record["preparation_sha256"] == reference(dest / "preparation.json")["sha256"], "sealed event was rebound")
    marker = record["marker"]
    require(read(dest / "dispatch-mark.json") == marker and read(Path(root) / "event-dispatches" / f"{marker['event_ordinal']:06d}.json") == marker, "sealed observation lost its original shared global charge")
    return dest, p, record


def seal_observation(root, leaf_id, callback_path, bootstrap_path):
    root = b.canonical_root(str(root))
    with b.locked(root):
        root, config, _, _ = load(root)
        dest, p = _preparation(root, config, leaf_id)
        marker = read(dest / "dispatch-mark.json")
        require(not (dest / "sealed-observation.json").exists(), "first observation is immutable, including error/unknown")
        # Freeze Root's entire first callback before parsing/refusing it. No
        # format repair replaces this first original or refunds its charge.
        callback_ref = c.write_once(dest / "raw-first-root-callback", Path(callback_path).read_bytes())
        callback = read(callback_ref["path"])
        for key in ("native_response", "original_png"):
            if isinstance(callback.get(key), dict) and callback[key].get("path"):
                source = Path(callback[key]["path"])
                if source.is_file() and not source.is_symlink():
                    c.write_once(dest / ("raw-first-" + key), source.read_bytes())
        boot = b.bootstrap(config, bootstrap_path)
        require(c.installation(config, p["scope_binding"]["arm"]) == p["identity"], "actual installation changed")
        # Exact unchanged bf literal argument/time/raw response primitive.
        completed = b.validate_callback(config, p, marker, callback)
        require(callback.get("completion_status") in {"completed", "error", "unknown"}, "record true first completion/uncertainty")
        record = {"format": "rc3-root-image-event-observation.v1", "event_id": p["event_id"], "preparation_sha256": reference(dest / "preparation.json")["sha256"], "callback": callback, "callback_source": reference(callback_path), "frozen_first_callback": callback_ref, "bootstrap": boot, "marker": marker, "sealed_at_ms": b.now_ms(), "evidence_kind": config["status"], "assurance": "host_attested", "platform_signed": False, "human": False, "actual_call_outcome": "consumed" if callback["completion_status"] == "completed" else "unknown", "automatic_retry": False}
        if callback["completion_status"] == "completed":
            png = check_ref(callback["original_png"])
            record["original_png"] = png
            try:
                b.unchanged_references(p["reference_snapshots"])
                from PIL import Image
                with Image.open(io.BytesIO(Path(png["path"]).read_bytes())) as original:
                    require(original.format == "PNG", "retain actual original PNG bytes, no re-encoding")
                    original.verify()
            except (OSError, ValueError) as exc:
                record["unusable_output_or_reference"] = str(exc)
            record["claims"] = {"provider_id": PROVIDER, "event_id": p["event_id"], "binding": p["binding"], "tool_name": "image_gen__imagegen", "status": "completed", "issued_at_ms": record["sealed_at_ms"], "expires_at_ms": record["sealed_at_ms"] + 86400000, "started_at_ms": marker["controller_dispatch_mark_ms"], "completed_at_ms": completed, "arguments": p["tool_arguments"], "output_sha256": png["sha256"], "invocation_ref": callback.get("platform_invocation_ref")}
        save(dest / "sealed-observation.json", {"record": record, "mac_sha256": hmac.new(_key(root), canonical(record), hashlib.sha256).hexdigest()})
        return {"status": "SEALED_" + record["actual_call_outcome"].upper(), "evidence_kind": config["status"], "automatic_retry": False, "native_product_capability": p["native_product_capability"]}


class RootEventProvider:
    provider_id = PROVIDER
    adapter_version = VERSION
    authentication = "protected_transport"

    def __init__(self, root, config, leaf_id):
        self.root, self.config, self.leaf_id = root, config, leaf_id

    def health(self):
        try:
            _authenticated(self.root, self.config, self.leaf_id)
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def fetch(self, event_id):
        dest, p, _ = _authenticated(self.root, self.config, self.leaf_id)
        require(event_id == p["event_id"], "foreign native event")
        return (dest / "sealed-observation.json").read_bytes()

    def verify(self, raw):
        from deck_master.native_image_evidence import NativeImageCompletion
        dest, p, record = _authenticated(self.root, self.config, self.leaf_id)
        require(raw == (dest / "sealed-observation.json").read_bytes() and record["actual_call_outcome"] == "consumed" and not record.get("unusable_output_or_reference"), "not the exact usable first sealed native observation")
        require(c.installation(self.config, p["scope_binding"]["arm"]) == p["identity"], "actual installation changed")
        for value in (record["callback_source"], record["frozen_first_callback"], record["callback"]["native_response"], record["original_png"]):
            check_ref(value)
        b.unchanged_references(p["reference_snapshots"])
        return NativeImageCompletion(deepcopy(record["claims"]), Path(record["original_png"]["path"]).read_bytes())


def settle(root, leaf_id):
    root = b.canonical_root(str(root))
    with b.locked(root):
        root, config, _, _ = load(root)
        dest, p, record = _authenticated(root, config, leaf_id)
        require(not (dest / "settlement.json").exists(), "settlement already recorded; inspect actual state instead of replay")
        from deck_master import tasks
        from deck_master.store import Store
        store = Store(p["scope_binding"]["project"])
        c.installation(config, p["scope_binding"]["arm"])
        outcome = record["actual_call_outcome"]
        rejection = None

        def call(context, report):
            return tasks.call_settle(store, task_id=p["row"]["task_id"], allowance_id=p["row"]["allowance_id"], attempt_id=p["row"]["attempt_id"], outcome=outcome, report_bytes=canonical(report), invocation_ref=record["callback"].get("platform_invocation_ref"), **({"adapter_context": context} if p["native_product_capability"] == "OWN_NATIVE_IMAGE_REGISTRY" else {}))

        try:
            if p["native_product_capability"] == "OWN_NATIVE_IMAGE_REGISTRY":
                from deck_master.native_image_evidence import NativeImageRegistry, NativeImageRuntime
                registry = NativeImageRegistry(); registry.register(RootEventProvider(root, config, leaf_id))
                with NativeImageRuntime(registry).bound():
                    context = None
                    if outcome == "consumed":
                        try:
                            context = registry.image_context(store, store.load_document(), task_id=p["row"]["task_id"], attempt_id=p["row"]["attempt_id"], selector={"provider_id": PROVIDER, "event_id": p["event_id"]})
                        except Exception as exc:
                            rejection = {"type": type(exc).__name__, "detail": str(exc)}
                    report = {"source": "native_host_image.v1", "provider_id": PROVIDER, "event_id": p["event_id"]} if outcome == "consumed" else {"source": "rc3-root-uncertain-image-event.v1", "observation": reference(dest / "sealed-observation.json")}
                    result = call(context, report)
            else:
                # Own A0 report records facts only. Never impersonate its
                # codex_session collector, import B registry, or claim adoption.
                result = call(None, {"source": "rc3-root-host-reported-image-event.v1", "observation": reference(dest / "sealed-observation.json"), "native_product_capability": "BLOCKED_MISSING_OWN_NATIVE_OBSERVATION"})
        except Exception as exc:
            save(dest / ("settlement-error-" + secrets.token_hex(6) + ".json"), {"status": "SETTLEMENT_UNCONFIRMED", "error_type": type(exc).__name__, "detail": str(exc), "actual_call_outcome": outcome, "automatic_retry": False})
            raise
        value = {"status": "SETTLED", "actual_result": result, "context_rejection": rejection, "actual_call_outcome": outcome, "native_product_capability": p["native_product_capability"], "evidence_kind": config["status"], "automatic_adoption": False, "automatic_retry": False}
        save(dest / "settlement.json", value)
        return value


def reconcile_settlement(root, leaf_id, observations_path):
    root = b.canonical_root(str(root))
    with b.locked(root):
        root, config, _, _ = load(root)
        dest, p, _ = _authenticated(root, config, leaf_id)
        from deck_master import generation
        c.installation(config, p["scope_binding"]["arm"])
        supplied = read(observations_path)
        require(supplied.get("runtime_observations"), "actual public Runtime query refs required")
        for value in supplied["runtime_observations"]:
            check_ref(value)
        shown = generation.show(p["scope_binding"]["project"], attempt_id=p["row"]["attempt_id"])
        state = shown["call"]["state"]
        value = {"status": "RUNTIME_SETTLEMENT_OBSERVED" if state in {"consumed", "unknown", "released"} else "STILL_UNRESOLVED", "actual_state": state, "actual_query": shown, "source_observations": reference(observations_path), "automatic_retry": False, "budget_refund": False}
        save(dest / ("reconciliation-" + secrets.token_hex(6) + ".json"), value)
        return value


def validate_m02_policy(config):
    event = validate_config(read(config["image_event_registration"]["path"]))
    require(event["policy"] == config["global_image_policy"], "M02 must share the exact effective event policy")
    require(event["protocol"] == config["protocol"], "M02/event registration must share the same governing protocol")
    require(event["status"] == ("ADMITTED" if config["status"] == "ADMITTED" else ENGINEERING), "M02/event admission scopes differ")
    policy = read(event["policy"]["path"])
    parents = [p for p in policy["parents"] if _parent_key(p) == ("M02", config["experiment_id"], 1, "B")]
    require(len(parents) == 1, "one original M02 whole-run parent required")
    scopes = [s for s in policy["scopes"] if s["parent_id"] == parents[0]["parent_id"]]
    wanted = set(config["scopes"]["live"]["page_ids"] + config["scopes"]["read"]["page_ids"])
    leaves = [leaf for scope in scopes for leaf in scope["leaves"]]
    labels = [leaf["page_label"] for leaf in leaves]
    require(len(labels) == len(set(labels)) and set(labels) == wanted, "event M02 planned Page labels must be exactly the distinct two-use Pages")
    require(all(leaf["page_id"] is None or leaf["page_id"] == leaf["page_label"] for leaf in leaves), "bound M02 Page must equal its own planned Page ID")
    require(parents[0]["max_calls"] == sum(config["scopes"][p]["max_external_calls"] for p in ("live", "read")), "event M02 shared cap differs from both registered scopes")
    for phase in ("live", "read"):
        selected = [s for s in scopes if s["checkpoint"] == phase]
        require(len(selected) == 1 and selected[0]["max_calls"] == config["scopes"][phase]["max_external_calls"] and {x["page_label"] for x in selected[0]["leaves"]} == set(config["scopes"][phase]["page_ids"]), "M02 event scope cannot borrow Pages/calls across uses")
        require(selected[0]["instruction"]["sha256"] == config["scopes"][phase]["instruction"]["sha256"], "M02 event instruction differs from its fixed use")
        require(config["scopes"][phase]["max_candidates"] == config["scopes"][phase]["max_external_calls"], "M02 event profile registers one candidate per permitted call")
    require(event["installations"]["B"] == config["installation"], "M02 event/profile must bind the same own B installation")
    return {"policy": policy, "event_registration": event, "parent": parents[0]}


def guard_m02_begin(journal, state, config, task, phase, arguments):
    values = validate_m02_policy(config)
    root, event, policy, _ = load(values["policy"]["ledger_root"])
    require(event == values["event_registration"] and policy == values["policy"], "M02 event epoch/registration changed")
    require(phase in {"live", "read"} and task["scope_pages"] and set(task["scope_pages"]) <= set(config["scopes"][phase]["page_ids"]), "M02 actual begin outside registered use")
    require(Path(state["project"]).is_absolute() and arguments["task_id"] == task["task_id"], "actual M02 project/Task required")
    counted = inspect_accounting(root)
    require(counted["by_parent"][values["parent"]["parent_id"]] < values["parent"]["max_calls"], "M02 image parent exhausted; no new begin")
    return {"status": "EVENT_POLICY_CURRENT", "ledger_root": str(root), "note": "Own SDK gate/allowance begin remains authoritative; this grants no tool dispatch."}


def main():
    require(sys.flags.isolated and sys.dont_write_bytecode, "use the own installation absolute Python with -I -B")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect-plan"); p.add_argument("--registration", required=True)
    p = sub.add_parser("admit-epoch"); p.add_argument("--registration", required=True); p.add_argument("--root", required=True)
    for command in ("prepare-page-call", "mark-dispatch", "seal-observation", "settle", "reconcile-settlement", "inspect-accounting"):
        p = sub.add_parser(command); p.add_argument("--root", required=True)
        if command != "inspect-accounting": p.add_argument("--leaf-id", required=True)
        if command == "prepare-page-call": p.add_argument("--binding", required=True); p.add_argument("--attempt-id", required=True)
        if command in {"mark-dispatch", "seal-observation"}: p.add_argument("--bootstrap", required=True)
        if command == "seal-observation": p.add_argument("--callback", required=True)
        if command == "reconcile-settlement": p.add_argument("--runtime-observations", required=True)
    args = parser.parse_args()
    if args.command == "inspect-plan":
        config = validate_config(read(args.registration)); result = {"status": "INSPECTED_NOT_EXECUTED", "policy": read(config["policy"]["path"]), "native_calls": 0}
    elif args.command == "admit-epoch": result = initialize_epoch(args.registration, args.root)
    elif args.command == "prepare-page-call": result = prepare_page_call(args.root, read(args.binding), args.leaf_id, args.attempt_id)
    elif args.command == "mark-dispatch": result = mark_dispatch(args.root, args.leaf_id, args.bootstrap)
    elif args.command == "seal-observation": result = seal_observation(args.root, args.leaf_id, args.callback, args.bootstrap)
    elif args.command == "settle": result = settle(args.root, args.leaf_id)
    elif args.command == "reconcile-settlement": result = reconcile_settlement(args.root, args.leaf_id, args.runtime_observations)
    else: result = inspect_accounting(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
