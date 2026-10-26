#!/usr/bin/env python3
"""Finite, own-installation RC3 supplementary operations and quarantined packets.

This Host recorder neither writes semantic objects nor produces native evidence.
Its append-only records describe actual calls; SDK gates and Root observations
remain separate. A bounded workorder view is explicitly different from raw SDK
output. No caller JSON selects a trusted adapter or a settlement receipt.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import threading
import uuid

COMMON_SHA = "db94a7bb8008c0c55dfb6761703b831027904e563873599ca87a025180931d8b"
SOURCE = Path(__file__).with_name("controller_v2.py")
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != COMMON_SHA:
    raise RuntimeError("frozen d0 helper changed")
_spec = importlib.util.spec_from_file_location("rc3_supplementary_pinned_common", SOURCE)
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)
Error = c.CampaignError
FORMAT = "rc3-supplementary-registration.v2"
ENGINEERING = "ENGINEERING_ONLY_NOT_ADMITTED"
ROLES = ("initial_writer", "repair_writer", "feedback", "verification", "production", "production_review")
WRITERS = {"initial_writer", "repair_writer", "production"}
# Each explicit profile has executable entrypoints and finite ceilings. These
# are maxima, not an authority to increase a smaller preregistered scope cap.
PROFILES = {
    "q3q4": {"cases": {"Q3", "Q4"}, "checkpoints": {"Q3", "Q4A", "Q4B"}, "writer": 48, "review": 32, "sdk": 1200, "render": 64},
    "q1-p5": {"cases": {"Q1"}, "checkpoints": {"Q1P5"}, "writer": 5, "review": 3, "sdk": 128, "render": 8},
    "q2-300": {"cases": {"Q2"}, "checkpoints": {"Q2_300"}, "writer": 6, "review": 2, "sdk": 128, "render": 0},
    "e2": {"cases": {"E2"}, "checkpoints": {"E2"}, "writer": 5, "review": 3, "sdk": 128, "render": 8},
    "e3": {"cases": {"E3"}, "checkpoints": {"E3"}, "writer": 0, "review": 1, "sdk": 0, "render": 0},
    # Used as a metering wrapper around the existing M02 state machine, not a
    # replacement for its native roles, variant provenance or notes guards.
    "m02-tools": {"cases": {"M02"}, "checkpoints": {"M02"}, "writer": 0, "review": 0, "sdk": 1024, "render": 64},
}
PUBLIC_OPERATIONS = c.PUBLIC_OPERATIONS - {"tasks.call_begin", "native_image_evidence.image_binding"} | {
    "legacy.inspect_legacy", "legacy.import_legacy", "collaboration.describe",
    "collaboration.pause_request", "collaboration.resume_request", "collaboration.revoke_authorization",
    "candidates.decide", "stages.assemble", "pipeline.preview_svg_page",
    "editing.edit_page", "editing.restore", "restoration.plan", "restoration.commit",
    "collaboration_migration.describe", "collaboration_migration.apply", "view.project_view",
    "tasks.call_begin",
    "service.open_host_task",
}
QUERY_OPERATIONS = {"operations.show", "service.inputs_show", "view.project_view", "delivery_eligibility.describe",
                    "collaboration.describe", "candidates.show", "candidates.listing", "generation.show"}
INTERNAL_OPERATIONS = {"service.task_start", "method_resources.read_task_methods", "service.task_summary",
                       "service.accept_result", "content_review.dispatch_preproduction_review"}
PACKETS = {"q3-full", "q4-p5", "nonblind-file-engineering"}


def require(condition, message):
    if not condition:
        raise Error(message)


def canonical(value, *, exists=False):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and str(path.resolve(strict=exists)) == str(path),
            "use one canonical absolute path; aliases and symlinks are not supported")
    return path


def checked(ref):
    canonical(ref["path"], exists=True)
    return c.check_ref(ref)


def validate(config):
    require(config.get("format") == FORMAT and config.get("status") in {"ADMITTED", ENGINEERING}, "separate scoped registration required")
    require(config.get("recorder_sha256") == c.digest(Path(__file__).read_bytes()), "scoped recorder bytes changed")
    canonical(config["ledger_root"])
    require(config["common"]["sha256"] == COMMON_SHA and Path(config["common"]["path"]) == SOURCE.resolve(), "pin sibling d0")
    for key in ("common", "protocol", "policy_epoch", "admission_review", "exposure_registry", "grammar"):
        checked(config[key])
    if config.get("image_event_helper"):
        checked(config["image_event_helper"])
    exposure = c.read(config["exposure_registry"]["path"])
    require(exposure.get("status") == "FROZEN" and exposure.get("excluded_identities"), "freeze exposure exclusions")
    require(config.get("installations") and config.get("scopes"), "actual installations and finite scope rows required")
    projects = {}
    for slot, row in config["scopes"].items():
        c.safe_name(slot)
        p = PROFILES.get(row.get("profile"))
        require(p and row["case"] in p["cases"] and row["checkpoint"] in p["checkpoints"], "profile/case/checkpoint mismatch, no aliases")
        require((row["case"] == "Q3") == (row["checkpoint"] == "Q3") if row["profile"] == "q3q4" else True, "Q3/Q4 checkpoint mismatch")
        require(row["arm"] in config["installations"] and type(row["repetition"]) is int and row["repetition"] > 0, "actual arm and repetition")
        for key in ("whole_run_id", "matrix_slot", "scope_slot"):
            c.safe_name(row[key])
        canonical(row["project"])
        require(row.get("project_mode") in {"new", "existing"}, "explicit project lifecycle")
        if row["project_mode"] == "existing":
            checked(row["checkpoint_ref"])
        checked(row["instruction"])
        for ref in row.get("materials", []) + row.get("technical_supplements", []):
            checked(ref)
        require(set(row["limits"]) == {"writer", "review", "sdk", "render"} and all(
            type(v) is int and 0 <= v <= p[k] for k, v in row["limits"].items()), "finite scope ceilings within explicit profile")
        require(set(row["native_limits"]) == set(ROLES) and all(type(v) is int and v >= 0 for v in row["native_limits"].values()), "finite actual role ceilings")
        for role, cap in row["native_limits"].items():
            require(cap <= row["limits"]["writer" if role in WRITERS else "review"], "role cannot exceed aggregate ceiling")
        require(row["native_limits"]["feedback"] <= 1 and row["native_limits"]["verification"] <= 1, "one feedback and one read-only verification")
        if row["profile"] in {"q1-p5", "e2"}:
            require(all(row["native_limits"][r] == 0 for r in ("initial_writer", "repair_writer", "feedback", "verification")),
                    "production-only checkpoint cannot reopen content/feedback budgets")
        if row["profile"] == "q2-300":
            require(row["native_limits"]["initial_writer"] <= 3 and row["native_limits"]["repair_writer"] <= 3
                    and row["native_limits"]["production"] == row["native_limits"]["production_review"] == 0,
                    "Q2 actual 300s is content-only, initial3 plus necessary repair3")
        if row["profile"] == "e3":
            require(row["native_limits"]["verification"] <= 1 and sum(row["native_limits"].values()) <= 1,
                    "E3 is one independent read-only audit")
        ids = row.get("page_ids", [])
        require(len(ids) == len(set(ids)) and all(isinstance(x, str) and x for x in ids), "stable distinct Page IDs")
        if row["checkpoint"] in {"Q4A", "Q4B", "Q1P5"}:
            require(len(ids) == 1, "local profile has one actual stable target Page")
        key = (row["profile"], row["whole_run_id"], row["repetition"], row["arm"], row["scope_slot"])
        require(key not in projects, "scope alias cannot refresh budget")
        projects[key] = row["project"]
    if config["status"] == "ADMITTED":
        require(config.get("gates") and all(v.get("status") == "PASS" for v in config["gates"].values()), "all actual scoped gates required")
        for gate in config["gates"].values():
            checked(gate["evidence"])
    return config


def freeze(registration, root):
    config = validate(c.read(registration))
    root = canonical(root)
    require(str(root) == config["ledger_root"], "registration has one fixed resource ledger root")
    root.mkdir(parents=True, exist_ok=False)
    c.save(root / "registration.json", config)
    c.save(root / "origin.json", c.reference(registration))
    c.save(root / "ledger-origin.json", {"root": str(root), "registration_sha256": c.digest(c.encoded(config))})
    return {"campaign": str(root), "status": config["status"], "native_calls": 0}


def init(campaign, root, slot):
    campaign, root = canonical(campaign, exists=True), canonical(root)
    config = validate(c.read(campaign / "registration.json"))
    require(config["ledger_root"] == str(campaign), "copied campaign cannot initialize another ledger")
    row = config["scopes"][slot]
    c.installation(config, row["arm"])
    project = canonical(row["project"])
    require(project.exists() == (row["project_mode"] == "existing"), "project lifecycle differs from registration")
    root.mkdir(parents=True, exist_ok=False)
    state = {"format": "rc3-supplementary-run.v1", "campaign": str(campaign), "root": str(root),
             "slot": slot, **deepcopy(row), "materials": row.get("materials", []), "budget": row["native_limits"],
             "registration_sha256": c.digest(c.encoded(config)), "human": "NOT_RUN_USER_DEFERRED"}
    state["grammar"] = config["grammar"]
    # A slot is consumed even if initialization subsequently fails; never reset.
    c.save(campaign / "runs" / (slot + ".json"), {"root": str(root), "project": str(project)})
    c.save(root / "run.json", state)
    c.Journal(root).append("scoped_initialized", state)
    return state


def load(root):
    root = canonical(root, exists=True)
    state = c.read(root / "run.json")
    require(state["root"] == str(root), "copied run cannot refresh scope")
    config = validate(c.read(Path(state["campaign"]) / "registration.json"))
    require(config["ledger_root"] == state["campaign"], "copied campaign cannot refresh budget")
    require(state["registration_sha256"] == c.digest(c.encoded(config)), "registration drift")
    row = config["scopes"][state["slot"]]
    require(all(state.get(k) == v for k, v in row.items()), "run changed preregistered scope")
    require(state["grammar"] == config["grammar"], "technical grammar drift")
    require(c.read(Path(state["campaign"]) / "runs" / (state["slot"] + ".json"))["root"] == str(root), "slot belongs to another run")
    origin = c.read(Path(state["campaign"]) / "ledger-origin.json")
    require(origin == {"root": state["campaign"], "registration_sha256": state["registration_sha256"]}, "budget ledger copied or changed")
    return c.Journal(root), state, config


def pool_key(state):
    # Q3 and both Q4 checkpoints share one arm-wide pool, never one per case.
    return "q3q4:" + state["arm"] if state["profile"] == "q3q4" else ":".join(
        (state["profile"], state["whole_run_id"], str(state["repetition"]), state["arm"]))


def case_key(state):
    return ":".join((state["case"], state["whole_run_id"], str(state["repetition"]), state["arm"]))


class Resources:
    def __init__(self, state):
        self.state = state
        self.root = canonical(state["campaign"], exists=True)
        origin = c.read(self.root / "ledger-origin.json")
        require(origin["root"] == str(self.root) and origin["registration_sha256"] == state["registration_sha256"], "one registered ledger only")
        self.journal = c.Journal(self.root / "resource-ledger")

    @contextmanager
    def locked(self):
        with (self.root / ".resources.lock").open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield self
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def totals(self):
        totals = {k: 0 for k in ("writer", "review", "sdk", "render")}
        scope = dict(totals)
        pending = {}
        for event in self.journal.events():
            d = event["data"]
            if d.get("pool") != pool_key(self.state):
                continue
            if event["kind"] == "resource_charge":
                totals[d["resource"]] += d["amount"]
                if d["slot"] == self.state["slot"]:
                    scope[d["resource"]] += d["amount"]
            elif event["kind"] == "render_reserved":
                pending[d["key"]] = d
            elif event["kind"] == "render_reconciled":
                pending.pop(d["key"], None)
        return totals, scope, pending

    def charge(self, resource, amount, identity, *, actual=False):
        require(resource in {"writer", "review", "sdk", "render"} and type(amount) is int and amount >= 0, "nonnegative actual resource units only")
        totals, scope, pending = self.totals()
        held = sum(d["maximum"] for d in pending.values()) if resource == "render" else 0
        own_held = sum(d["maximum"] for d in pending.values() if d["slot"] == self.state["slot"]) if resource == "render" else 0
        within = totals[resource] + held + amount <= PROFILES[self.state["profile"]][resource] and scope[resource] + own_held + amount <= self.state["limits"][resource]
        require(within or actual, "finite shared/scope " + resource + " cap exhausted")
        data = {"pool": pool_key(self.state), "slot": self.state["slot"], "resource": resource,
                "amount": amount, "identity": identity, "within_budget": within, "actual": actual}
        self.journal.append("resource_charge", data)
        return data

    def once(self, kind, identity, evidence):
        require(not any(e["kind"] == kind and e["data"]["case"] == case_key(self.state)
                        and e["data"]["identity"] == identity for e in self.journal.events()), "one " + kind + " per original case/Page, no event reset")
        self.journal.append(kind, {"case": case_key(self.state), "identity": identity, "evidence": evidence})


class MeteredJournal:
    """d0 raw/native helpers retain their checks; real SDK intents are counted."""
    def __init__(self, journal, state, resources):
        self.journal, self.state, self.resources, self.root = journal, state, resources, journal.root

    def events(self):
        return self.journal.events()

    def unfinished(self):
        return self.journal.unfinished()

    def append(self, kind, data):
        if kind == "sdk_intent":
            self.resources.charge("sdk", 1, data["operation_key"])
        elif kind == "native_begun":
            charge = self.resources.charge("writer" if data["role"] in WRITERS else "review", 1,
                                           {"run": str(self.root), "ordinal": data["ordinal"], "executor": data["executor"], "observation": data["observation"]}, actual=True)
            data["within_budget"] = data["within_budget"] and charge["within_budget"]
        return self.journal.append(kind, data)


class RenderTrace:
    """Read-only Python call observation, including entries followed by failure.

    The units are native compile, outer PPT renderer round, and SVG page preview.
    pdftoppm's internal page loop is not an extra renderer unit. Tracing does not
    replace package functions or turn an absent tool into success.
    """
    def __init__(self, module_root):
        self.root, self.calls = Path(module_root).resolve(), []
        self.units = {(str(self.root / "compiler/api.py"), "compile_deck"): "compile",
                      (str(self.root / "pipeline.py"), "render_deck"): "ppt_render",
                      (str(self.root / "pipeline.py"), "preview_svg_page"): "svg_preview"}

    def __call__(self, frame, event, arg):
        if event == "call":
            unit = self.units.get((frame.f_code.co_filename, frame.f_code.co_name))
            if unit:
                self.calls.append({"unit": unit, "file": frame.f_code.co_filename, "line": frame.f_code.co_firstlineno,
                                   "page_id": frame.f_locals.get("page_id"), "at": c.now()})


@contextmanager
def resource_session(root, *, render_reserve=0, readonly=False):
    """Host Python bridge for M02/companion calls; not a JSON callback loader.

    The Host must pass the yielded journal to the actual existing operation.
    Calls made with another journal are not claimed as metered by this recorder.
    """
    journal, state, config = load(root)
    c.installation(config, state["arm"])
    require(type(render_reserve) is int and render_reserve >= 0, "finite maximum renderer reservation")
    require(not readonly or render_reserve == 0, "read-only reconciliation cannot reserve renderer work")
    resources = Resources(state)
    with resources.locked():
        require(sys.getprofile() is None and threading.getprofile() is None, "do not displace an existing profiler")
        key = uuid.uuid4().hex
        totals, scope, pending = resources.totals()
        require(not pending or readonly, "earlier renderer reservation unresolved; preserve unknown, no automatic retry")
        require(totals["render"] + render_reserve <= PROFILES[state["profile"]]["render"]
                and scope["render"] + render_reserve <= state["limits"]["render"], "reserve known maximum compile/render before SDK dispatch")
        resources.journal.append("render_reserved", {"pool": pool_key(state), "slot": state["slot"], "key": key, "maximum": render_reserve})
        trace = RenderTrace(Path(config["installations"][state["arm"]]["module_file"]).parent)
        completed = False
        sys.setprofile(trace)
        threading.setprofile(trace)
        try:
            yield MeteredJournal(journal, state, resources), state, config
            completed = True
        finally:
            intact = sys.getprofile() is trace and threading.getprofile() is trace
            sys.setprofile(None)
            threading.setprofile(None)
            # A Python exception still has a complete local trace. Process death
            # never reaches here and keeps its original reservation pending.
            if intact:
                resources.journal.append("render_reconciled", {"pool": pool_key(state), "slot": state["slot"], "key": key,
                    "actual_calls": trace.calls, "maximum": render_reserve, "operation_returned": completed})
                charge = resources.charge("render", len(trace.calls), {"trace": trace.calls, "reservation": key}, actual=True)
                journal.append("render_accounted", {"key": key, **charge, "reserved_maximum_exceeded": len(trace.calls) > render_reserve})
                if len(trace.calls) > render_reserve:
                    raise Error("actual renderer attempts exceeded prior reservation; all outcomes retained")
            else:
                journal.append("render_observation_unknown", {"key": key, "reason": "profiler changed during operation", "known_calls": trace.calls})
                raise Error("renderer observation lost; reservation stays pending")


def forbid_context(value):
    if isinstance(value, dict):
        require(not ({"store", "adapter_context", "review_receipt_selector", "document"} & set(value)), "caller JSON cannot select Store/document/trusted context")
        for item in value.values():
            forbid_context(item)
    elif isinstance(value, list):
        for item in value:
            forbid_context(item)


def perform(journal, operation, arguments, callback, *, query=False):
    require(not journal.unfinished() or query, "earlier SDK intent unresolved; only actual read-only reconciliation queries permitted")
    key = uuid.uuid4().hex
    journal.append("sdk_intent", {"operation_key": key, "operation": operation, "arguments": arguments})
    try:
        result = callback()
    except Exception as exc:
        journal.append("sdk_error", {"operation_key": key, "error_type": type(exc).__name__, "error": str(exc),
                                      "commit_state": "unresolved_until_runtime_observed", "semantic_fallback": False})
        raise
    journal.append("sdk_outcome", {"operation_key": key, "result": result})
    return result


def operate(root, operation, arguments, *, render_reserve=0, image_guard=None):
    require(operation in PUBLIC_OPERATIONS, "closed own public-operation allowlist; image begin/settle belongs to companion")
    forbid_context(arguments)
    with resource_session(root, render_reserve=render_reserve, readonly=operation in QUERY_OPERATIONS) as (journal, state, _):
        module_name, name = operation.split(".", 1)
        module = importlib.import_module("deck_master." + module_name)
        require(hasattr(module, name), "BLOCKED_MISSING_OWN_CAPABILITY: " + operation)
        function = getattr(module, name)
        params = inspect.signature(function).parameters
        args = deepcopy(arguments)
        project_key = next((k for k in ("project_dir", "project", "store", "out_path") if k in params), None)
        if project_key:
            if project_key in args:
                require(str(canonical(args[project_key])) == state["project"], "operation cannot switch project")
            args[project_key] = c.store_for(state) if project_key == "store" else state["project"]
        else:
            require(operation == "legacy.inspect_legacy", "unsupported own public signature")
        if operation == "generation.freeze":
            require(args.get("input", {}).get("parameters") == {"transparent_background": False}, "exact preregistered image parameters")
        if operation == "tasks.call_begin":
            require(image_guard, "actual image scope guard required before own call_begin")
            image_guard(journal, state, args)
        inspect.signature(function).bind(**args)
        serial = {**arguments, **({project_key: state["project"]} if project_key else {})}
        return perform(journal, operation, serial, lambda: function(**args), query=operation in QUERY_OPERATIONS)


def pinned_image_guard(root, packet_path):
    """CLI/Host bridge to the exact separately reviewed image companion guard."""
    _, state, config = load(root)
    helper_ref = config.get("image_event_helper")
    require(helper_ref, "image companion not pinned in this registration")
    checked(helper_ref)
    require(Path(helper_ref["path"]) == Path(__file__).with_name("image_event_controller.py").resolve(), "use actual sibling image companion")
    packet_ref, packet_input = c.reference(packet_path), c.read(packet_path)
    for key in ("event_registration_ref", "binding_ref"):
        checked(packet_input[key])
    helper_spec = importlib.util.spec_from_file_location("rc3_supplementary_actual_image_helper", helper_ref["path"])
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    event_config = c.read(packet_input["event_registration_ref"]["path"])
    binding = c.read(packet_input["binding_ref"]["path"])
    require(all(binding.get(k) == state[k] for k in ("case", "whole_run_id", "repetition", "arm", "project", "scope_slot")), "image binding belongs to another scope")

    def guard(journal, _state, arguments):
        # Current helper performs only installed-identity and Store/eligibility
        # observations here, not generation.show or another public SDK entry.
        # A future changed helper must be separately reviewed/pinned again.
        outcome = helper.guard_call_begin(event_config, binding, packet_input["page_id"], arguments)
        journal.append("image_begin_guard_observed", {"guard_packet": packet_ref, "helper": helper_ref,
            "outcome": outcome, "sdk_entries_in_guard": 0, "observation_kind": "installed_identity_and_store_readonly"})
        return outcome
    return guard


def instruction_event(root, scope_slot, observation_path):
    journal, state, _ = load(root)
    require(scope_slot == state["scope_slot"], "actual preregistered instruction occurrence only")
    ref, obs = c.reference(observation_path), c.read(observation_path)
    require(obs.get("assurance") == "host_attested" and obs.get("observer_id") == "/root"
            and obs.get("scope_slot") == scope_slot and obs.get("actual_trigger") is True, "Root actual trigger, not planned future event")
    checked(state["instruction"])
    require(obs.get("instruction_sha256") == state["instruction"]["sha256"] and obs.get("source_observations"), "bind exact instruction and actual trigger refs")
    for item in obs["source_observations"]:
        checked(item)
    require(not any(e["kind"] == "instruction_occurrence" for e in journal.events()), "instruction already occurred")
    data = {"scope_slot": scope_slot, "instruction": state["instruction"], "observation": ref}
    journal.append("instruction_occurrence", data)
    return data


def role_task(journal, state, task, role):
    require(role in ROLES and state["native_limits"][role] > 0, "role not registered for this scope")
    require(task["status"] in {"awaiting_host", "running"}, "actual pending/running own Task required")
    if state["page_ids"]:
        require(set(task.get("scope_pages", [])) <= set(state["page_ids"]), "actual Task Page scope exceeds registered operation scope")
    phase = (task.get("collaboration_binding") or {}).get("phase")
    if role in {"initial_writer", "repair_writer"}:
        require(task["kind"] == "compose" and phase != "production", "content role must match actual compose phase")
    elif role == "production":
        require(task["kind"] in {"blueprint", "reconstruct", "repair", "style_analyze"}, "production cannot relabel compose")
    else:
        require(task["kind"] == "review", "independent reviewer needs actual review Task")
        require((role in {"feedback", "verification"}) == (task.get("review_stage") == "preproduction"), "review stage/role mismatch")
    if role == "repair_writer":
        repairs = [e["data"] for e in journal.events() if e["kind"] == "repair_begun"]
        require(repairs and phase in repairs[0]["necessary_layers"], "single necessary repair layer must match actual Task")
    if role == "initial_writer":
        require(not any(e["kind"] in {"repair_begun", "feedback_delivered"} for e in journal.events()), "cannot rename post-feedback work initial")
    if role == "verification":
        require(any(e["kind"] == "repair_begun" for e in journal.events()), "verification requires one actual necessary repair")
    if role == "production" and task.get("review_stage") == "page_visual" and task["kind"] == "repair":
        require(any(e["kind"] == "svg_repair_begun" and e["data"]["task_id"] == task["task_id"] for e in journal.events()), "necessary per-Page SVG repair declaration required")


def read_methods(journal, state, task):
    from deck_master import method_resources
    if hasattr(method_resources, "read_task_methods"):
        return perform(journal, "method_resources.read_task_methods", {"task_id": task["task_id"], "project": state["project"]},
                       lambda: method_resources.read_task_methods(state["project"], task["task_id"]))
    return perform(journal, "service.task_summary", {"task_id": task["task_id"], "own_legacy_full_method_adapter": True},
                   lambda: c.read_installed_task_methods(state, task))


class Closure:
    """Structural required-read traversal; opaque refs never grant expansion."""
    def __init__(self, project, target, destination, *, bounded):
        self.project = canonical(project, exists=True)
        self.target, self.destination, self.bounded = target, Path(destination), bounded
        self.items, self.opaque, self.seen = [], [], set()

    def path(self, value):
        path = Path(value)
        require(".." not in path.parts, "required read contains ..")
        path = path if path.is_absolute() else self.project / path
        canonical(str(path), exists=True)
        require(path.is_relative_to(self.project), "foreign required-read path")
        return path

    def add(self, path, sha, pointer, classification="required_read"):
        path = self.path(path)
        raw = path.read_bytes()
        require(c.digest(raw) == sha, "required-read hash mismatch")
        key = (str(path), sha)
        if key not in self.seen:
            self.seen.add(key)
            copy_path = self.destination / "files" / (sha + path.suffix)
            saved = c.reference(copy_path) if copy_path.exists() else c.write_once(copy_path, raw)
            require(saved["sha256"] == sha, "existing byte-identical read copy drifted")
            self.items.append({"source_path": str(path), "sha256": sha, "bytes": len(raw), "pointer": pointer,
                               "classification": classification, "author_copy": saved})
        return raw

    @staticmethod
    def is_ref(value):
        return isinstance(value, dict) and set(value) == {"path", "sha256"} and isinstance(value["sha256"], str)

    def identity(self, value, pointer):
        if value is None:
            return
        require(self.is_ref(value), "opaque binding must remain a Ref, never expanded content")
        path = self.path(value["path"])
        require(c.digest(path.read_bytes()) == value["sha256"], "opaque identity hash mismatch")
        self.opaque.append({"pointer": pointer, "ref": value, "classification": "opaque_binding_only", "read_permission": False})

    def reject_full_semantics(self, value):
        """Check inline JSON before any bounded author copy, without Ref expansion."""
        if isinstance(value, dict):
            schema = value.get("schema_version")
            require(not (isinstance(schema, str) and schema.startswith(("narrative.", "content_plan.", "deck_narrative.", "deck_content_plan."))), "full Narrative/Plan cannot become P5 author reading")
            for item in value.values():
                self.reject_full_semantics(item)
        elif isinstance(value, list):
            for item in value:
                self.reject_full_semantics(item)

    def visit(self, value, pointer):
        if self.is_ref(value):
            key = (str(self.path(value["path"])), value["sha256"])
            if key in self.seen:
                return
            if self.bounded:
                raw = self.path(value["path"]).read_bytes()
                require(c.digest(raw) == value["sha256"], "required-read hash mismatch")
                try:
                    decoded = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    decoded = None
                self.reject_full_semantics(decoded)
            raw = self.add(value["path"], value["sha256"], pointer)
            if Path(value["path"]).suffix == ".json":
                self.visit(json.loads(raw), pointer + "/@object")
        elif isinstance(value, dict):
            if self.bounded:
                self.reject_full_semantics(value)
                if value.get("schema_version", "").startswith("deck_page_package."):
                    require(value == self.target, "required Page is not the complete exact current target including notes")
                if "page_id" in value:
                    require(value["page_id"] in {None, self.target["page_id"]}, "required-read closure expands another Page")
                require(not value.get("page_order") or value["page_order"] == [self.target["page_id"]], "required-read closure expands full Plan order")
            for key, item in value.items():
                # Page content mapping binds its existing Narrative identity; it
                # is not permission to read the complete Narrative.
                if self.bounded and key in {"narrative_ref", "page_manifest_ref"} and self.is_ref(item):
                    self.identity(item, pointer + "/" + key)
                elif key in {"original_uri", "source_uri"} and isinstance(item, str):
                    if self.bounded:
                        require(not item or item.startswith("source:"), "unclassified URI in required object")
                    self.opaque.append({"pointer": pointer + "/" + key, "value": item,
                                        "classification": "opaque_binding_only", "read_permission": False})
                else:
                    self.visit(item, pointer + "/" + key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                self.visit(item, pointer + "/" + str(i))


VIEW_FIELDS = {"task_id", "operation_id", "kind", "intent", "method_release", "current_method_release", "method_basis_status",
               "review_stage", "status", "scope_pages", "dispatch_revision", "produced_against", "call_allowances", "staging_dir",
               "execution_ref", "execution_started_at", "protocol_version", "required_capabilities", "host_protocol",
               "method_manifest", "method_basis_issues", "content_validation_policy"}
BOUND_REQUIRED = {"inputs", "page_entries", "resolved_design_context", "production_request", "review_plan",
                  "prior_page_visual_findings", "prior_page_visual_evidence", "reference_images", "page_design_contexts",
                  "change_binding", "change_action", "candidate_refs"}
BOUND_CLASSIFIED = VIEW_FIELDS | BOUND_REQUIRED | {"instruction", "sources", "source_reading", "method_resources", "project_context", "collaboration_binding", "outputs"}


def packet(journal, state, task, methods, directory, profile):
    require(profile in PACKETS, "explicit packet profile")
    bounded = profile == "q4-p5"
    require(not bounded or (state["checkpoint"] in {"Q4A", "Q4B", "Q1P5"} and len(state["page_ids"]) == 1), "bounded profile needs an actual local target")
    store = c.store_for(state)
    doc = store.load_document()
    directory = Path(directory)
    raw_ref = c.save(directory / "quarantine" / "sdk-method-response.json", methods)
    c.save(directory / "quarantine" / "actual-task.json", task)
    work = methods["work_order"]
    require(methods["status"] == "current" and methods["current_method_release"] == task["method_release"], "own current full methods required")
    require(work["task_id"] == task["task_id"], "actual workorder Task mismatch")
    # RC4 method/policy fields are read-only metadata, never file-read grants.
    # Historical responses without a manifest keep their original adapter path.
    if work.get("method_manifest") is not None:
        selected = [{key: item[key] for key in ("id", "relative_path", "sha256")} for item in methods["methods"]]
        require(work["method_manifest"] == selected, "workorder method manifest differs from complete selected methods")
    if task.get("method_manifest") is not None:
        require(work.get("method_manifest") == task["method_manifest"], "workorder method manifest differs from frozen Task")
    target = None
    if bounded:
        require(task["scope_pages"] == state["page_ids"] and work["scope_pages"] == state["page_ids"], "actual Task scope exceeds target; never repair global reconciliation in P5 wrapper")
        require(task["kind"] in {"blueprint", "reconstruct", "repair"} or
                (task["kind"] == "review" and task.get("review_stage") == "page_visual"), "this actual protocol requires wider content; use nonblind engineering separately")
        entry = next(e for e in doc["pages"] if e["page_id"] == state["page_ids"][0])
        target = store.read_object_json(entry["page"])
    closure = Closure(state["project"], target, directory / "author-packet", bounded=bounded)
    method_rows = []
    module = Path(sys.modules["deck_master"].__file__).resolve().parent
    method_root = module / "resources/skill"
    if module.parent.name == "src":
        method_root = module.parent.parent / "skills/deck-master"
    for item in methods["methods"]:
        path, raw = canonical(item["path"], exists=True), item["content"].encode("utf-8")
        require(path.is_relative_to(method_root) and path.read_bytes() == raw and c.digest(raw) == item["sha256"], "complete method bytes must come from own installation")
        ref = c.write_once(directory / "author-packet" / "methods" / (c.safe_name(item["id"]) + ".md"), raw)
        method_rows.append({"id": item["id"], "own_installed_path": str(path), "sha256": item["sha256"], "bytes": len(raw), "read_file": ref})
    view = {k: deepcopy(v) for k, v in work.items() if k in VIEW_FIELDS}
    view.update({"format": "rc3-bounded-workorder-view.v1" if bounded else "rc3-full-workorder-view.v1",
                 "raw_response_ref": raw_ref, "raw_response_read_permission": False,
                 "instruction": state["instruction"], "methods": method_rows})
    instruction_copy = c.write_once(directory / "author-packet" / "actual-instruction.txt", Path(checked(state["instruction"])["path"]).read_bytes())
    view["instruction_read_file"] = instruction_copy
    technical_files = []
    for item in [state["grammar"]] + state.get("technical_supplements", []):
        checked(item)
        technical_files.append(c.write_once(directory / "author-packet" / "technical" / (item["sha256"] + Path(item["path"]).suffix), Path(item["path"]).read_bytes()))
    for path in sorted((module / "resources/contracts").glob("*.schema.json")):
        technical_files.append(c.write_once(directory / "author-packet" / "schemas" / path.name, path.read_bytes()))
    view["technical_read_files"] = technical_files
    if not bounded:
        # Explicitly full/nonblind: copy the real workorder, not a fabricated
        # manuscript. It remains ineligible for P5 or blind content dispatch.
        view["work_order"] = work
        closure.visit(work, "/work_order")
        for index, source in enumerate(work.get("source_reading", [])):
            require(source.get("original_file"), "full packet source lacks immutable original")
            ref = source["original_file"]
            closure.add(ref["path"], ref["sha256"], f"/source_reading/{index}/original_file")
            if source.get("extract_path"):
                path = closure.path(source["extract_path"])
                closure.add(str(path), c.digest(path.read_bytes()), f"/source_reading/{index}/extract_path")
    else:
        require(set(work) <= BOUND_CLASSIFIED, "new unclassified workorder field requires explicit closure review")
        for field in BOUND_REQUIRED - {"inputs"}:
            if field in work:
                closure.visit(work[field], "/" + field)
                view[field] = work[field]
        # The public local-task constructor also puts current whole-file
        # outputs in inputs. In this page-local view these exact output Refs
        # retain their binding identity, without becoming file-read grants.
        output_refs = [v for v in (work.get("outputs") or {}).values() if v]
        for index, value in enumerate(work.get("inputs", [])):
            if value in output_refs:
                closure.identity(value, f"/inputs/{index}")
            else:
                closure.visit(value, f"/inputs/{index}")
        view["inputs"] = work.get("inputs", [])
        require(set(work.get("page_design_contexts") or {}) <= set(state["page_ids"]), "design context expands another Page")
        binding = work.get("collaboration_binding") or {}
        require((binding.get("write_scope") or {}).get("page_ids", state["page_ids"]) == state["page_ids"], "actual binding widens local target")
        for i, basis in enumerate(binding.get("eligibility_basis", [])):
            if basis.get("ref"):
                closure.identity(basis["ref"], f"/collaboration_binding/eligibility_basis/{i}/ref")
        if (binding.get("write_scope") or {}).get("page_manifest_ref"):
            closure.identity(binding["write_scope"]["page_manifest_ref"], "/collaboration_binding/write_scope/page_manifest_ref")
        view["collaboration_binding"] = binding
        # Outputs are identity metadata for these page-local Task protocols.
        # Final review protocols were rejected above; expanded outputs are not
        # made harmless by calling them opaque.
        for key, value in (work.get("outputs") or {}).items():
            closure.identity(value, "/outputs/" + key)
        view["outputs"] = work.get("outputs")
        view["source_reading"] = []
        for index, source in enumerate(work.get("source_reading", [])):
            require(source.get("status") == "read" and source.get("format_kind") == "json", "P5 requires byte-complete JSON Page source")
            source_page = json.loads(source["text"])
            allowed = [target]
            for item in state.get("materials", []):
                checked(item)
                if Path(item["path"]).suffix == ".json":
                    value = c.read(item["path"])
                    if isinstance(value, dict) and value.get("page_id") == target["page_id"] and value.get("schema_version", "").startswith("deck_page_package."):
                        allowed.append(value)
            require(source_page in allowed, "source_reading is not exactly the registered complete target Page/notes")
            original = source["original_file"]
            raw = closure.add(original["path"], original["sha256"], f"/source_reading/{index}/original_file")
            require(json.loads(raw) == source_page and source["original_sha256"] == original["sha256"], "original source differs from the complete target projection")
            require(closure.path(source["original_path"]) == closure.path(original["path"]), "source original_path differs from verified immutable original")
            extract_path = closure.path(source["extract_path"])
            extract_raw = extract_path.read_bytes()
            extract = json.loads(extract_raw)
            require(extract.get("text") == source["text"] and extract.get("locators") == source["locators"] and extract.get("tables") == source["tables"], "expanded extraction fields differ from actual extract")
            require(not source.get("image_pages"), "unclassified source image pages are not P5 JSON projection")
            closure.add(str(extract_path), c.digest(extract_raw), f"/source_reading/{index}/extract_path")
            # original_uri is retained only as provenance, with no read grant.
            view["source_reading"].append(source)
            closure.opaque.append({"pointer": f"/source_reading/{index}/original_uri", "value": source.get("original_uri"),
                                   "classification": "opaque_binding_only", "read_permission": False})
        require(view["source_reading"], "complete own P5 source must actually be returned")
        require(work.get("page_entries") and all(x["page_id"] == target["page_id"] for x in work["page_entries"]), "actual target page_entries required")
    manifest = {"format": "rc3-required-read-closure.v1", "project": state["project"], "task_id": task["task_id"],
                "bounded": bounded, "target_page_ids": state["page_ids"], "required_read": closure.items,
                "methods": method_rows, "opaque_binding_only": closure.opaque,
                "instruction_read_file": instruction_copy,
                "technical_read_files": technical_files,
                "original_raw_ref": raw_ref, "raw_preserved": True, "os_sandbox_claim": False}
    manifest_ref = c.save(directory / "read-closure-manifest.json", manifest)
    view["read_closure_manifest_ref"] = manifest_ref
    view["required_read_files"] = [x["author_copy"] for x in closure.items]
    view_ref = c.save(directory / "author-packet" / "workorder-view.json", view)
    mapping_ref = c.save(directory / "view-mapping.json", {"original_raw_ref": raw_ref, "author_view_ref": view_ref,
        "copied_fields": sorted(set(work) & VIEW_FIELDS), "omitted_raw_fields": sorted(set(work) - set(view)),
        "mode": "explicit_bounded_view_not_raw_redaction" if bounded else "explicit_full_nonblind_view"})
    return {"original_raw_ref": raw_ref, "author_view_ref": view_ref, "read_closure_manifest_ref": manifest_ref,
            "view_mapping_ref": mapping_ref, "method_release": methods["current_method_release"], "raw_workorder_preserved": True}


def prepare_task(root, stage, task_id, role, profile):
    with resource_session(root) as (journal, state, config):
        require(any(e["kind"] == "instruction_occurrence" for e in journal.events()), "actual instruction occurrence must precede dispatch")
        if state["checkpoint"] in {"Q4A", "Q4B"}:
            require(profile == "q4-p5" or (profile == "nonblind-file-engineering" and config["status"] == ENGINEERING), "local formal author must use bounded P5 view")
        task = c.task_for(c.store_for(state), task_id)
        role_task(journal, state, task, role)
        target = journal.root / "stages" / c.safe_name(stage)
        target.mkdir(parents=True, exist_ok=False)
        try:
            methods = read_methods(journal, state, task)
            result = packet(journal, state, task, methods, target / "preflight", profile)
            dispatch = {"stage": stage, "role": role, "task_id": task_id, "project_id": methods["project_id"],
                        "method_release": methods["current_method_release"], "packet_profile": profile,
                        "prepared_at": c.now(), "status": "quarantined_not_released", **result}
            c.save(target / "dispatch.json", dispatch)
            journal.append("stage_prepared", dispatch)
            return dispatch
        except Exception as exc:
            journal.append("packet_refused", {"stage": stage, "error_type": type(exc).__name__, "error": str(exc), "raw_directory": str(target)})
            raise


def audit_packet(root, stage, observation_path, *, ordinal=None):
    journal, state, config = load(root)
    target, dispatch = c.stage_info(journal, stage)
    actual_task = c.task_for(c.store_for(state), dispatch["task_id"])
    role_task(journal, state, actual_task, dispatch["role"])
    require(actual_task["method_release"] == dispatch["method_release"], "current Task method release drift")
    if ordinal is None:
        result = dispatch
        directory = target / "preflight"
    else:
        _, directory = c.execution(journal, stage, ordinal)
        result = c.read(directory / "post-claim-packet.json")
    ref, obs = c.reference(observation_path), c.read(observation_path)
    excluded = set(c.read(config["exposure_registry"]["path"])["excluded_identities"])
    authors = {e["data"]["executor"] for e in journal.events() if e["kind"] == "native_begun" and e["data"]["role"] in WRITERS}
    require(obs.get("assurance") == "host_attested" and obs.get("observer_id", "").startswith("/root/")
            and obs["observer_id"] not in authors | excluded and obs.get("status") == "PASS", "actual independent non-author packet audit required")
    require(obs.get("task_id") == dispatch["task_id"] and obs.get("project") == state["project"]
            and obs.get("required_read_closure_checked") is True and obs.get("raw_workorder_preserved") is True,
            "audit must check actual raw/view/transitive closure")
    for key in ("original_raw_ref", "author_view_ref", "read_closure_manifest_ref"):
        checked(result[key])
        require(obs.get(key) == result[key], "audit binds different packet bytes")
    # Recheck every transitive file; an audit cannot launder source drift.
    manifest = c.read(result["read_closure_manifest_ref"]["path"])
    for item in manifest["required_read"]:
        require(c.reference(item["source_path"])["sha256"] == item["sha256"], "required read changed since quarantine")
        checked(item["author_copy"])
    for item in manifest["methods"]:
        checked(item["read_file"])
        require(c.reference(item["own_installed_path"])["sha256"] == item["sha256"], "installed method changed")
    checked(manifest["instruction_read_file"])
    for ref in manifest["technical_read_files"]:
        checked(ref)
    audit = {"scope_slot": state["scope_slot"], "task_id": dispatch["task_id"], "project": state["project"], "stage": stage,
             "status": "PASS", "required_read_closure_checked": True, "raw_workorder_preserved": True,
             **{k: result[k] for k in ("original_raw_ref", "author_view_ref", "read_closure_manifest_ref")}, "independent_observation": ref}
    audit_ref = c.save(directory / "independent-packet-audit.json", audit)
    journal.append("packet_audited", {"stage": stage, "ordinal": ordinal, "audit": audit_ref})
    return audit_ref


def begin_native(root, stage, observation_path):
    with resource_session(root) as (journal, state, config):
        target, dispatch = c.stage_info(journal, stage)
        audits = [e["data"]["audit"] for e in journal.events() if e["kind"] == "packet_audited"
                  and e["data"]["stage"] == stage and e["data"]["ordinal"] is None]
        require(len(audits) == 1, "one actual preflight packet audit required")
        checked(audits[0])
        role_task(journal, state, c.task_for(c.store_for(state), dispatch["task_id"]), dispatch["role"])
        return c.begin_native(journal, state, config, stage, observation_path)


def claim_read(root, stage, ordinal, executor):
    with resource_session(root) as (journal, state, _):
        invocation, directory = c.execution(journal, stage, ordinal)
        require(invocation["executor"] == executor, "claim executor must match actual Root invocation")
        _, dispatch = c.stage_info(journal, stage)
        task = c.task_for(c.store_for(state), dispatch["task_id"])
        role_task(journal, state, task, dispatch["role"])
        from deck_master import service
        args = {"task_id": task["task_id"], "execution_ref": executor,
                "supported_protocols": [task["protocol_version"]] if task.get("protocol_version") else None,
                "capabilities": task.get("required_capabilities")}
        claim = perform(journal, "service.task_start", args, lambda: service.task_start(state["project"], **args))
        c.save(directory / "claim.json", claim)
        task = c.task_for(c.store_for(state), task["task_id"])
        methods = read_methods(journal, state, task)
        require(methods["current_method_release"] == dispatch["method_release"], "claim method release drift")
        try:
            result = packet(journal, state, task, methods, directory / "post-claim", dispatch["packet_profile"])
            c.save(directory / "post-claim-packet.json", result)
            # This is an exact record of the view and full methods made
            # available, not a claim that the author read the raw workorder.
            record = c.save(directory / "method-read-record.json", {"format": "rc3-scoped-author-read.v1", **result,
                "methods": [{k: v for k, v in m.items() if k != "content"} for m in methods["methods"]],
                "consumption": "quarantined_until_independent_post_claim_audit", "raw_workorder_read_by_author": False})
            journal.append("method_bytes_returned", {"ordinal": ordinal, "executor": executor, "record": record,
                "limitation": "full own method bytes returned; actual view/method consumption requires separate Root observation"})
            return result
        except Exception as exc:
            journal.append("post_claim_packet_refused", {"ordinal": ordinal, "error": str(exc), "actual_spawn_still_charged": True})
            raise


def release_packet(root, stage, ordinal, observation_path):
    audit = audit_packet(root, stage, observation_path, ordinal=ordinal)
    journal, _, _ = load(root)
    _, target = c.execution(journal, stage, ordinal)
    result = c.read(target / "post-claim-packet.json")
    data = {"ordinal": ordinal, "stage": stage, "packet_audit_ref": audit, **result, "author_read_permission": "listed_required_files_only"}
    c.save(target / "released-packet.json", data)
    journal.append("safe_packet_released", data)
    return data


def observe(root, stage, ordinal, result, result_sha256, observation, observation_sha256):
    journal, state, _ = load(root)
    _, target = c.execution(journal, stage, ordinal)
    # d0 freezes originals before parsing. Additional view binding is checked
    # only afterwards so a bad/late completion is never discarded.
    outcome = c.observe(journal, state, stage, ordinal, result, result_sha256, observation, observation_sha256)
    try:
        release = c.read(target / "released-packet.json")
        obs = c.read(observation)
        require(obs.get("author_view_sha256") == release["author_view_ref"]["sha256"]
                and obs.get("read_closure_manifest_sha256") == release["read_closure_manifest_ref"]["sha256"]
                and obs.get("all_required_view_files_read") is True
                and obs.get("raw_workorder_read_by_author") is False, "native receipt must bind actual bounded/full view, not pretend raw SDK reading")
        journal.append("scoped_native_observed", {"stage": stage, "ordinal": ordinal, "author_view": release["author_view_ref"]})
        return outcome
    except Exception as exc:
        journal.append("scoped_native_observation_refused", {"ordinal": ordinal, "error": str(exc), "raw_preserved": True})
        raise


def require_scoped_native_observation(journal, stage, ordinal):
    require(any(e["kind"] == "scoped_native_observed" and e["data"]["stage"] == stage and e["data"]["ordinal"] == ordinal for e in journal.events()), "scoped full view/method consumption not observed")


def accepted_native(journal, stage, ordinal):
    require_scoped_native_observation(journal, stage, ordinal)
    return c.observed_result(journal, stage, ordinal)


def budget_clean(journal, state):
    resources = Resources(state)
    require(not any(e["kind"] == "resource_charge" and e["data"].get("pool") == pool_key(state)
                    and not e["data"]["within_budget"] for e in resources.journal.events()), "actual shared pool overrun retained; cannot consume as same-budget work")
    require(not any(e["kind"] == "render_accounted" and e["data"]["reserved_maximum_exceeded"] for e in journal.events()), "unreserved renderer work cannot be consumed as admitted work")


def accept(root, stage, ordinal, *, render_reserve=0, bootstrap=None, materialize=False):
    with resource_session(root, render_reserve=render_reserve) as (journal, state, _):
        invocation, _, _, _ = accepted_native(journal, stage, ordinal)
        budget_clean(journal, state)
        _, dispatch = c.stage_info(journal, stage)
        task = c.task_for(c.store_for(state), dispatch["task_id"])
        role_task(journal, state, task, invocation["role"])
        before = c.store_for(state).load_document()
        protected = {e["page_id"]: deepcopy(e) for e in before["pages"] if e["page_id"] not in state["page_ids"]}
        if materialize:
            result = c.materialize_native_objects(journal, state, stage, ordinal)
        elif bootstrap:
            result = c.review_accept(journal, state, stage, ordinal, bootstrap)
        else:
            result = c.accept(journal, state, stage, ordinal)
        after = c.store_for(state).load_document()
        if dispatch["packet_profile"] == "q4-p5":
            require({e["page_id"]: e for e in after["pages"] if e["page_id"] not in state["page_ids"]} == protected,
                    "actual SDK result changed non-target Page refs; preserved as failed scope, never claim PASS")
        return result


def feedback(root, stage, ordinal):
    journal, state, _ = load(root)
    resources = Resources(state)
    with resources.locked():
        require_scoped_native_observation(journal, stage, ordinal)
        _, _, _, proof = c.observed_result_for_feedback(journal, stage, ordinal)
        c.check_ref(proof['observation'])
        resources.once("content_feedback", "one", {"stage": stage, "ordinal": ordinal})
        return c.deliver_feedback(journal, stage, ordinal)


def repair_begin(root, necessity):
    journal, state, _ = load(root)
    resources = Resources(state)
    with resources.locked():
        require(not any(e["kind"] == "content_repair_cycle" and e["data"]["case"] == case_key(state)
                        for e in resources.journal.events()), "one semantic repair cycle per original case")
        # d0 validates actual accepted feedback/finding IDs and necessary layers.
        result = c.repair_begin(journal, necessity)
        resources.once("content_repair_cycle", "one", result)
        return result


def svg_repair_begin(root, task_id, finding_ref):
    journal, state, _ = load(root)
    store = c.store_for(state)
    task = c.task_for(store, task_id)
    require(task["kind"] == "repair" and len(task["scope_pages"]) == 1, "necessary SVG repair uses an actual single-Page repair Task")
    pid = task["scope_pages"][0]
    entry = next(e for e in store.load_document()["pages"] if e["page_id"] == pid)
    require(entry.get("page") and entry.get("svg"), "one repair belongs to an actually adopted Page and existing SVG")
    # Adopted real Runtime review, not a caller-invented feedback JSON.
    require(finding_ref in store.load_document().get("reviews", []), "SVG necessity cites an actual current project review")
    review = store.read_object_json(finding_ref)
    require(review.get("findings") and (entry["page"] in review.get("subjects", []) or entry["svg"] in review.get("subjects", []))
            and review.get("review_stage") == "page_visual", "actual page-visual finding for this adopted Page/SVG required")
    data = {"page_id": pid, "task_id": task_id, "page_ref": entry["page"], "first_svg": entry["svg"], "finding_ref": finding_ref}
    resources = Resources(state)
    with resources.locked():
        resources.once("necessary_svg_repair", pid, data)
        journal.append("svg_repair_begun", data)
    return data


def reconcile(root, operation_key):
    journal, state, _ = load(root)
    intent = journal.unfinished().get(operation_key)
    require(intent, "no unresolved operation with that identity")
    opid = intent["arguments"].get("operation_id")
    require(opid, "operation lacks public reconciliation ID; retain unknown until actual own Runtime evidence exists")
    try:
        outcome = operate(root, "operations.show", {"operation_id": opid})
    except Exception:
        # Historical/unverified/unavailable is unknown, not proof of no commit.
        journal.append("reconciliation_unknown", {"operation_key": operation_key, "no_retry": True})
        raise
    require(outcome.get("status") in {"committed", "applied", "already_applied"} or outcome.get("committed_revision_id"), "actual public query did not establish commit; retain unknown")
    data = {"operation_key": operation_key, "actual_runtime_observation": outcome, "automatic_retry": False}
    journal.append("sdk_reconciliation", data)
    return data


def image_handoff(root, stage, ordinal, *, allowance_id, attempt_id):
    journal, state, _ = load(root)
    _, target = c.execution(journal, stage, ordinal)
    release = c.read(target / "released-packet.json")
    _, dispatch = c.stage_info(journal, stage)
    store = c.store_for(state)
    task = c.task_for(store, dispatch["task_id"])
    attempts = [store.read_object_json(ref) for ref in task.get("generation_attempts", [])]
    attempts = [a for a in attempts if a["attempt_id"] == attempt_id]
    allowance = next((a for a in task.get("call_allowances", []) if a["allowance_id"] == allowance_id), None)
    require(len(attempts) == 1 and allowance and allowance["state"] == "in_flight", "handoff requires own actual begun Attempt/in-flight allowance, no future IDs")
    attempt = attempts[0]
    require(attempt["allowance_id"] == allowance_id and attempt["execution_ref"] == task.get("execution_ref"), "actual Attempt/claim/allowance mismatch")
    request = store.read_object_json(attempt["request_ref"])
    require(request["task_id"] == task["task_id"] and request["input"]["parameters"] == {"transparent_background": False}, "actual frozen Request differs")
    occurrence = next(e["data"] for e in journal.events() if e["kind"] == "instruction_occurrence")
    return {"format": "rc3-image-scope-handoff.v1", **{k: state[k] for k in ("matrix_slot", "case", "whole_run_id", "repetition", "arm", "checkpoint", "project", "scope_slot")},
            "instruction_occurrence_ref": occurrence["observation"], "actual_request_id": task["collaboration_binding"]["request_id"],
            "task_id": task["task_id"], "allowance_id": allowance_id, "attempt_id": attempt_id,
            "packet_audit_ref": release["packet_audit_ref"], "stage": stage}


def status(root):
    journal, state, _ = load(root)
    resources = Resources(state)
    with resources.locked():
        totals, scope, pending = resources.totals()
    return {"profile": state["profile"], "slot": state["slot"], "pool": pool_key(state), "pool_used": totals, "scope_used": scope,
            "render_pending": pending, "sdk_unresolved": journal.unfinished(), "semantic_gate": "NOT_ASSERTED",
            "human": "NOT_RUN_USER_DEFERRED", "os_sandbox": "NOT_ASSERTED"}


def review_prepare(root, stage, role, profile, bootstrap):
    """Dispatch own preproduction bridge without d0's full-manuscript prepare."""
    with resource_session(root) as (journal, state, config):
        require(role in {"feedback", "verification"}, "preproduction review role")
        from deck_master import content_review
        if config["installations"][state["arm"]].get("adapter_profile") == "A0-public-legacy":
            journal.append("own_capability_blocked", {"operation": "native_preproduction_review", "reason": "A0 has no admitted opaque collector; no B substitution"})
            raise Error("BLOCKED_MISSING_OWN_CAPABILITY: A0 protected review bridge")
        if role == "feedback":
            require((journal.root / "snapshots/original_complete.json").is_file()
                    and (journal.root / "snapshots/first_sdk_complete.json").is_file(), "freeze actual original and accepted full draft before feedback")
        else:
            require(any(e["kind"] == "repair_begun" for e in journal.events()), "post-repair read-only verification only")
        with c.native_runtime(bootstrap) as registry:
            outcome = perform(journal, "content_review.dispatch_preproduction_review", {"bootstrap": c.reference(bootstrap)},
                              lambda: content_review.dispatch_preproduction_review(state["project"], adapter_context=registry.channel_context()))
        journal.append("review_dispatch", {"role": role, "actual_result": outcome})
    if outcome["status"] != "review_dispatched":
        return outcome
    return prepare_task(root, stage, outcome["task"]["task_id"], role, profile)


def snapshot(root, name, *, complete=False):
    """Real current objects and public readiness, never a synthetic content gate."""
    journal, state, _ = load(root)
    doc = c.store_for(state).load_document()
    if complete:
        require(state["profile"] != "e3", "read-only audit does not establish a production completion")
        expected = state["page_ids"]
        entries = [e for e in doc["pages"] if not expected or e["page_id"] in expected]
        if state["checkpoint"] == "Q3":
            require(len(entries) == 6, "Q3 needs all six actual Pages")
        for entry in entries:
            require(all(entry.get(k) for k in ("page", "blueprint", "svg", "svg_preview", "ppt_preview")), "actual complete Page/blueprint/SVG/both previews required")
        require(doc.get("outputs", {}).get("pptx") and doc.get("outputs", {}).get("render_report"), "real whole-file production outputs required")
    readiness = operate(root, "delivery_eligibility.describe", {})
    data = {"document": doc, "actual_readiness": readiness, "complete_artifacts_checked": complete,
            "professional_quality": "ONLY_ACTUAL_SDK_STATUS_NO_MODEL_INFERENCE", "human": "NOT_RUN_USER_DEFERRED"}
    ref = c.save(journal.root / "snapshots" / (c.safe_name(name) + ".json"), data)
    journal.append("snapshot_frozen", {"name": name, "snapshot": ref})
    return ref


def prepare_file_audit(root, stage):
    """E3's one extra read-only *file operation*, honestly not a DM Task.

    Only actual current outputs and their transitive artifacts are copied. No
    public SDK call, renderer, model, synthetic Task or review receipt is made.
    """
    journal, state, config = load(root)
    require(state["profile"] == "e3", "file-audit entry belongs only to preregistered E3")
    require(any(e["kind"] == "instruction_occurrence" for e in journal.events()), "actual registered audit instruction occurrence required")
    c.installation(config, state["arm"])
    store, target = c.store_for(state), journal.root / "stages" / c.safe_name(stage)
    doc = store.load_document()
    require(doc["outputs"].get("pptx"), "actual current native PPTX is required; no content-only substitute")
    closure = Closure(state["project"], None, target / "author-packet", bounded=False)
    closure.visit(doc["outputs"], "/actual_current_outputs")
    module = Path(config["installations"][state["arm"]]["module_file"]).parent
    methods = []
    for name in ("review-and-repair", "physical-units"):
        path = module / "resources/skill/references" / (name + ".md")
        require(path.is_file(), "BLOCKED_MISSING_OWN_CAPABILITY: installed file-review method")
        methods.append(c.write_once(target / "author-packet/methods" / path.name, path.read_bytes()))
    packet_ref = c.save(target / "author-packet/operation.json", {"format": "rc3-selected-file-audit-operation.v1",
        "not_a_dm_task": True, "project_id": doc["project_id"], "project": state["project"], "revision_id": doc["revision_id"],
        "actual_outputs": doc["outputs"], "required_files": closure.items, "methods": methods,
        "instruction": state["instruction"], "read_only": True, "sdk_acceptance": "NOT_APPLICABLE"})
    ref = c.save(target / "file-audit-binding.json", {"project_id": doc["project_id"], "revision_id": doc["revision_id"],
        "actual_outputs": doc["outputs"], "author_view_ref": packet_ref, "not_a_dm_task": True})
    journal.append("file_audit_prepared", {"stage": stage, "binding": ref})
    return ref


def begin_file_audit(root, stage, observation):
    journal, state, config = load(root)
    require(state["profile"] == "e3", "E3 file audit only")
    target = journal.root / "stages" / c.safe_name(stage)
    binding = c.read(target / "file-audit-binding.json")
    require(c.store_for(state).load_document()["outputs"] == binding["actual_outputs"], "selected file is no longer current")
    obs, ref = c.read(observation), c.reference(observation)
    spawn = obs["spawn"]
    executor = spawn["canonical_task_name"]
    require(obs.get("observation_kind") == c.OBSERVER_KIND and obs.get("assurance") == "host_attested"
            and obs.get("project_id") == binding["project_id"] and obs.get("author_view_sha256") == binding["author_view_ref"]["sha256"]
            and spawn.get("tool") == "collaboration.spawn_agent" and spawn.get("fork_turns") == "none"
            and spawn.get("returned_task_name") == executor and executor.startswith("/root/"), "actual fresh independent file-audit native invocation")
    c.fresh(obs["observed_at_utc"])
    resources = Resources(state)
    excluded = set(c.read(config["exposure_registry"]["path"])["excluded_identities"])
    authors = {e["data"]["identity"].get("executor") for e in resources.journal.events() if e["kind"] == "resource_charge"
               and e["data"]["resource"] == "writer" and isinstance(e["data"]["identity"], dict)}
    require(executor not in excluded | authors and not set(spawn.get("inherited_identities", [])) & (excluded | authors), "file reviewer is an exposed preparer/manuscript author")
    with resources.locked():
        require(not any(e["kind"] == "file_audit_begun" for e in journal.events()), "one E3 extra audit per registered chain")
        charge = resources.charge("review", 1, {"executor": executor, "observation": ref}, actual=True)
        data = {"stage": stage, "executor": executor, "observation": ref, "within_budget": charge["within_budget"], "not_a_dm_task": True}
        journal.append("file_audit_begun", data)
    return data


def observe_file_audit(root, stage, result, observation):
    journal, state, _ = load(root)
    target = journal.root / "stages" / c.safe_name(stage)
    raw = c.write_once(target / "raw-native-file-audit", Path(result).read_bytes())
    obs_ref = c.write_once(target / "raw-root-file-audit-completion.json", Path(observation).read_bytes())
    journal.append("file_audit_originals_frozen", {"raw": raw, "observation": obs_ref})
    try:
        invocation = next(e["data"] for e in journal.events() if e["kind"] == "file_audit_begun" and e["data"]["stage"] == stage)
        binding, obs = c.read(target / "file-audit-binding.json"), c.read(observation)
        completion = obs["completion"]
        require(invocation["within_budget"] and obs.get("observation_kind") == c.OBSERVER_KIND and obs.get("assurance") == "host_attested"
                and obs.get("model_output_bytes_sha256") == raw["sha256"] and obs.get("author_view_sha256") == binding["author_view_ref"]["sha256"]
                and obs.get("all_required_view_files_read") is True and completion.get("sender") == invocation["executor"]
                and completion.get("message_type") == "FINAL_ANSWER" and completion.get("observed_status") == "completed"
                and completion.get("status_observation_tool") == "collaboration.list_agents" and completion.get("raw_final_message")
                and invocation["executor"] in completion.get("observed_completed_agents", []), "actual full FINAL/completed/selected-file read binding required")
        c.fresh(obs["observed_at_utc"])
        require(c.store_for(state).load_document()["outputs"] == binding["actual_outputs"], "file audit no longer current")
        value = c.read(result)
        require(isinstance(value, dict), "complete read-only audit object required")
        ref = c.save(target / "observed-file-audit.json", {"raw": raw, "observation": obs_ref, "not_a_dm_task": True,
            "sdk_review_receipt": "NOT_CREATED", "semantic_gate": "NOT_ASSERTED"})
        journal.append("file_audit_observed", {"stage": stage, "audit": ref})
        return ref
    except Exception as exc:
        journal.append("file_audit_refused", {"stage": stage, "error": str(exc), "originals_retained": True})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "init", "instruction-event", "public-operation", "prepare-task", "audit-packet", "begin-native", "claim-read", "release-safe-packet", "observe", "accept", "materialize-native-objects", "review-prepare", "review-accept", "deliver-feedback", "repair-begin", "svg-repair-begin", "snapshot", "prepare-file-audit", "begin-file-audit", "observe-file-audit", "image-handoff", "reconcile", "status"))
    for key in ("registration", "out", "campaign", "slot", "run", "scope-slot", "observation", "operation", "arguments", "stage", "task-id", "role", "packet-profile", "executor", "result", "result-sha256", "observation-sha256", "bootstrap", "necessity", "operation-key", "image-guard", "finding-ref", "name", "allowance-id", "attempt-id"):
        parser.add_argument("--" + key)
    parser.add_argument("--ordinal", type=int)
    parser.add_argument("--render-reserve", type=int, default=0)
    parser.add_argument("--complete", action="store_true")
    a = parser.parse_args(argv)
    command = a.command
    if command == "freeze": result = freeze(a.registration, a.out)
    elif command == "init": result = init(a.campaign, a.out, a.slot)
    elif command == "instruction-event": result = instruction_event(a.run, a.scope_slot, a.observation)
    elif command == "public-operation": result = operate(a.run, a.operation, c.read(a.arguments), render_reserve=a.render_reserve,
        image_guard=pinned_image_guard(a.run, a.image_guard) if a.image_guard else None)
    elif command == "prepare-task": result = prepare_task(a.run, a.stage, a.task_id, a.role, a.packet_profile)
    elif command == "audit-packet": result = audit_packet(a.run, a.stage, a.observation)
    elif command == "begin-native": result = begin_native(a.run, a.stage, a.observation)
    elif command == "claim-read": result = claim_read(a.run, a.stage, a.ordinal, a.executor)
    elif command == "release-safe-packet": result = release_packet(a.run, a.stage, a.ordinal, a.observation)
    elif command == "observe": result = observe(a.run, a.stage, a.ordinal, a.result, a.result_sha256, a.observation, a.observation_sha256)
    elif command in {"accept", "materialize-native-objects", "review-accept"}: result = accept(a.run, a.stage, a.ordinal, render_reserve=a.render_reserve, bootstrap=a.bootstrap, materialize=command == "materialize-native-objects")
    elif command == "review-prepare": result = review_prepare(a.run, a.stage, a.role, a.packet_profile, a.bootstrap)
    elif command == "deliver-feedback": result = feedback(a.run, a.stage, a.ordinal)
    elif command == "repair-begin": result = repair_begin(a.run, a.necessity)
    elif command == "svg-repair-begin": result = svg_repair_begin(a.run, a.task_id, c.read(a.finding_ref))
    elif command == "snapshot": result = snapshot(a.run, a.name, complete=a.complete)
    elif command == "prepare-file-audit": result = prepare_file_audit(a.run, a.stage)
    elif command == "begin-file-audit": result = begin_file_audit(a.run, a.stage, a.observation)
    elif command == "observe-file-audit": result = observe_file_audit(a.run, a.stage, a.result, a.observation)
    elif command == "image-handoff": result = image_handoff(a.run, a.stage, a.ordinal, allowance_id=a.allowance_id, attempt_id=a.attempt_id)
    elif command == "reconcile": result = reconcile(a.run, a.operation_key)
    else: result = status(a.run)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
