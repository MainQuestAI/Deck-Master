#!/usr/bin/env python3
"""Finite prospective M02 runtime epoch; no model/image caller or admission grant.

The predecessor is verified, read-only history. Only the successor receives
events. Host observations are explicitly attestations, not platform signatures.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid
import zipfile

M02_SHA = "56d01a929b9ae490e4ea33fdcf753cbc9e5b38fee4f5559e030d89440c1d1502"
M02 = Path(__file__).with_name("m02_recorder.py")


def helpers():
    if hashlib.sha256(M02.read_bytes()).hexdigest() != M02_SHA:
        raise ValueError("frozen M02 recorder changed")
    spec = importlib.util.spec_from_file_location("rc3_s11_frozen_m02", M02)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = helpers()
c, Error, require = m.c, m.Error, m.require
FORMAT = "rc3-m02-runtime-successor.v1"
ENGINEERING = "ENGINEERING_ONLY_NOT_ADMITTED"
PROJECT = "/tmp/rc3-pv2/m02"
RUN = "/tmp/rc3-pv2/m02-r-common"
TASK = "88deb3fff924"
ACTOR = "/root/pv2_m02_native_readback_repair_writer_01"
NARRATIVE = {"path": ".deckmaster/objects/e9/e9db3e5c8950edc043e688e204665d3ddcb51793820f80b7834aa1242e9ff68d.json",
             "sha256": "e9db3e5c8950edc043e688e204665d3ddcb51793820f80b7834aa1242e9ff68d"}


def chain(root):
    """Read only the explicitly pinned predecessor journal, without mkdir/lock."""
    rows, previous = [], None
    for index, path in enumerate(sorted((Path(root) / "journal").glob("*.json")), 1):
        raw = path.read_bytes(); row = json.loads(raw)
        require(path.name == f"{index:06d}.json" and row["sequence"] == index
                and row["previous_sha256"] == previous, "predecessor journal chain changed")
        rows.append(row); previous = c.digest(raw)
    return rows


class Successor:
    """Historical projection, never copied old native_begun/cost events."""
    def __init__(self, root, historical):
        self.local = c.Journal(root); self.root = self.local.root
        self.historical = historical

    def events(self):
        return self.historical + self.local.events()

    def append(self, kind, data):
        return self.local.append(kind, data)

    def unfinished(self):
        pending = {}
        for row in self.events():
            data = row["data"]
            if row["kind"] == "sdk_intent": pending[data["operation_key"]] = data
            elif row["kind"] in {"sdk_outcome", "sdk_reconciliation"}:
                pending.pop(data["operation_key"], None)
        return pending


def binding(config):
    return c.digest(c.encoded({k: v for k, v in config.items() if k != "admission"}))


def validate(config):
    require(sys.flags.isolated and sys.dont_write_bytecode, "use own absolute Python -I -B")
    require(config.get("format") == FORMAT and config.get("status") in {ENGINEERING, "ADMITTED"}, "separate successor registration required")
    require(config["companion_sha256"] == c.digest(Path(__file__).read_bytes()), "companion changed")
    for key, path in (("common", m.SOURCE), ("m02_recorder", M02)):
        require(c.check_ref(config[key]) == c.reference(path), "pin exact sibling helper")
    p = config["predecessor"]
    for key in ("run", "registration", "frontier"): c.check_ref(p[key])
    old_state = c.read(p["run"]["path"]); old = c.read(p["registration"]["path"])
    require(c.digest(c.encoded(old)) == old_state["registration_sha256"], "predecessor registration digest changed")
    require(Path(p["run"]["path"]).name == "run.json", "actual predecessor run required")
    old_root = Path(p["run"]["path"]).parent
    rows = chain(old_root)
    require(len(rows) == p["event_count"] and p["frontier"] == c.reference(old_root / "journal" / f"{len(rows):06d}.json"), "predecessor frontier changed")
    require(rows[0]["kind"] == "m02_initialized" and rows[0]["data"] == old_state, "predecessor identity changed")
    require(old_state["project"] == config["project"] and old_state["experiment_id"] == config["experiment_id"], "same project and whole run required")
    require(config["scopes"] == old["scopes"] and config["materials"] == old["materials"], "inherit exact scopes, instructions, sources and caps")
    for scope in config["scopes"].values(): c.check_ref(scope["instruction"])
    for ref in config["materials"]: c.check_ref(ref)
    for key in ("grammar", "protocol", "exposure_registry"):
        require(config[key] == old[key], "inherit original public protocol and exclusions")
        c.check_ref(config[key])
    require(config["technical_supplements"] == old["technical_supplements"], "inherit method supplements")
    for ref in config["technical_supplements"]: c.check_ref(ref)
    exposure = c.read(config["exposure_registry"]["path"])
    require(exposure.get("status") == "FROZEN" and exposure.get("excluded_identities"), "original public exclusion policy required")
    require(m.phase(SuccessorView(rows)) == "live", "predecessor must stop in original live phase")
    fixed = m.fixed(SuccessorView(rows))
    require(config["fixed_narrative"] == fixed["narrative_ref"], "fixed adopted Narrative changed")
    require(not m.events(SuccessorView(rows), "m02_version_exported")
            and not m.events(SuccessorView(rows), "m02_instruction", "read")
            and not m.events(SuccessorView(rows), "m02_instruction", "live_notes_edit"), "predecessor already progressed beyond transition")
    for ref in config["protected_refs"]: c.check_ref(ref)
    require(config["protected_refs"], "pin old correct and failed artifacts")
    require_protected(config, old_state)
    aux = config["auxiliary_executions"]
    require(len(aux) == 2 and len({x["executor"] for x in aux}) == 2
            and all(x["role"] == "production_review" and x["phase"] == "live" for x in aux), "two genuine historical auxiliary reviews required")
    for row in aux: c.check_ref(row["evidence"])
    require(len(m.events(SuccessorView(rows), "native_begun")) == 14, "historical helper14 baseline changed")
    require(sum(x["role"] == "production" for x in m.events(SuccessorView(rows), "m02_native_started", "live")) == 7
            and sum(x["role"] == "production_review" for x in m.events(SuccessorView(rows), "m02_native_started", "live")) == 3, "historical live7/review3 baseline changed")
    require(sum(sum(s["native_limits"].values()) for s in config["scopes"].values()) == 67
            and config["scopes"]["live"]["native_limits"]["production"] == 12
            and config["scopes"]["live"]["native_limits"]["production_review"] == 8, "original whole67/live12/review8 caps required")
    for name in ("S07", "S10", "installation", "companion"):
        c.check_ref(config["independent_reviews"][name])
    spec = config["installation"]
    require(spec["source_sha"] != old["installation"]["source_sha"] and spec["python"] != old["installation"]["python"], "distinct new own runtime required")
    c.safe_name(config["supplemental_validation_id"]); c.safe_name(config["runtime_epoch"])
    admission = config["admission"]; c.check_ref(admission); admitted = c.read(admission["path"])
    require(admitted.get("format") == "rc3-m02-runtime-admission.v1" and admitted.get("observer") == "/root"
            and admitted.get("registration_binding") == binding(config)
            and admitted.get("status") == config["status"]
            and admitted.get("administrative_only") is True
            and admitted.get("no_new_image_or_direction_authority") is True, "prospective exact Root admission required")
    for ref in admitted["source_observations"]: c.check_ref(ref)
    require(admitted["source_observations"], "actual Root transition evidence required")
    if config["status"] == "ADMITTED":
        require(config["project"] == PROJECT and str(old_root) == RUN
                and config["experiment_id"] == "m02-telescope-prod-01"
                and config["group_id"] == "vg-b277642f95b75d84" and config["fixed_narrative"] == NARRATIVE
                and p["event_count"] == 229
                and p["run"]["sha256"] == "197fd59584638f4b4ec10c20f3712615526db40aea790cdf05ad62b73c26b7fa"
                and p["registration"]["sha256"] == "1b436044fdfee5fd2499e4a0a47eaae45125f47f87f690310db4fd4a0a81f163"
                and p["frontier"]["sha256"] == "db5d126d9f92de2fd47d8137bce324a210727e23e26ae86ae6af24b8d7f3814d", "exact formal M02 predecessor required")
        review = c.read(config["independent_reviews"]["installation"]["path"])
        require(review.get("status") == "PASS" and review.get("installation") == spec
                and review.get("managed_candidate") is True and review.get("toolchain_verified") is True
                and review.get("native_image_registry_verified") is True, "independent final managed installed review required")
    else:
        require(Path(config["project"]).resolve() != Path(PROJECT) and old_root.resolve() != Path(RUN), "engineering cannot target formal project/run")
    return old_state, old, rows


class SuccessorView:
    """Only a verified in-memory historical event view; never a Runtime Store."""
    def __init__(self, rows): self.rows = rows
    def events(self): return self.rows


def content_identity(doc):
    return {"sources": doc["sources"], "narrative": doc.get("narrative"), "content_plan": doc.get("content_plan"),
            "pages": [{k: v for k, v in row.items() if k != "ppt_preview"} for row in doc["pages"]]}


def critical_refs(config, state):
    """Exact initial published objects/files, not a Store or nested-Ref crawl."""
    store = c.store_for(state)
    initial = config["initial_content"]; pages = config["initial_pages"]
    require([{k: v for k, v in row.items() if k != "ppt_preview"} for row in pages] == initial["pages"], "initial complete Page entries differ")
    artifact_refs = [row[slot] for row in pages for slot in ("blueprint", "svg", "svg_preview", "ppt_preview") if row.get(slot)]
    artifact_refs += [ref for ref in config["initial_outputs"].values() if ref]
    objects = [ref for ref in (initial["narrative"], initial["content_plan"]) if ref] + [row["page"] for row in pages] + artifact_refs
    result = []
    for ref in objects:
        value = store.read_object_json(ref)  # validates the actual immutable hash
        result.append(c.reference(Path(state["project"]) / ref["path"]))
        if ref in artifact_refs:
            from deck_master.models import validate_schema
            validate_schema("artifact", value)
            store.read_object_bytes(value["file"])
            result.append(c.reference(Path(state["project"]) / value["file"]["path"]))
    return result


def require_protected(config, state):
    wanted = {(r["path"], r["sha256"]) for r in critical_refs(config, state)}
    pinned = {(r["path"], r["sha256"]) for r in config["protected_refs"]}
    require(wanted <= pinned, "pin every initial N/Plan/Page/PNG/SVG/preview/PPTX/report/trace object and file")


def installation(config):
    """Formal always uses the unchanged managed guard. Engineering can reuse an
    existing plain wheel prefix, with complete wheel/member verification and
    honest install=null; it never fabricates managed release metadata.
    """
    if config["status"] == "ADMITTED":
        observed = c.installation({"installations": {"B": config["installation"]}}, "B")
        require((observed.get("install") or {}).get("release_id") == config["runtime_epoch"], "actual managed runtime epoch differs")
        return observed
    from deck_master import capabilities, method_resources
    observed = capabilities.installation_identity(); spec = config["installation"]
    require(Path(sys.executable).absolute() == Path(spec["python"]).absolute()
            and observed["module_path"] == spec["module_file"] and observed["method_source"] == "packaged", "own packaged engineering interpreter/module required")
    c.check_ref(spec["wheel"])
    root = Path(spec["module_file"]).parent
    with zipfile.ZipFile(spec["wheel"]["path"]) as wheel:
        expected = {name.removeprefix("deck_master/"): c.digest(wheel.read(name)) for name in wheel.namelist() if name.startswith("deck_master/") and not name.endswith("/")}
    actual = {p.relative_to(root).as_posix(): c.digest(p.read_bytes()) for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    require(actual == expected and spec["package_files"] == expected, "complete engineering wheel/member inventory differs")
    require(method_resources.method_release([])["release_id"] == config["runtime_epoch"], "actual engineering method epoch differs")
    require(all(Path(mod.__file__).resolve().is_relative_to(root.resolve()) for name, mod in sys.modules.items() if (name == "deck_master" or name.startswith("deck_master.")) and getattr(mod, "__file__", None)), "borrowed Runtime module")
    return {"actual_identity": observed, "engineering_wheel": spec["wheel"], "verified_members": len(actual), "formal_managed_admission": False}


def guard(journal, state, config):
    for ref in config["protected_refs"]: c.check_ref(ref)
    require_protected(config, state)
    m.guard(journal, state, config)
    doc = c.store_for(state).load_document()
    require(doc["project_id"] == state["project_id"], "project identity changed")
    target = doc["collaboration"]["request"].get("variant") or {}
    require(target.get("group_id") == config["group_id"]
            and target.get("requested_variant_ids") == ["live", "read"], "same declared variant group required")
    return doc


def initialize(registration, root):
    config = c.read(registration); old_state, _, historical = validate(config)
    identity = installation(config)
    store = c.store_for(old_state); doc = store.load_document()
    require(content_identity(doc) == config["initial_content"], "current initial protected content differs")
    require(doc["pages"] == config["initial_pages"] and doc["outputs"] == config["initial_outputs"], "exact initial failed outputs/previews required")
    variant = doc["collaboration"]["request"].get("variant") or {}
    require(doc.get("narrative") == config["fixed_narrative"] and variant.get("group_id") == config["group_id"]
            and variant.get("variant_id") == "live" and variant.get("requested_variant_ids") == ["live", "read"], "same original live group/N required")
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=False)
    c.save(root / "registration.json", config)
    state = {**old_state, "format": FORMAT, "project_id": doc["project_id"], "campaign": str(root),
             "registration_sha256": c.digest(c.encoded(config)), "supplemental_validation_id": config["supplemental_validation_id"],
             "runtime_epoch": config["runtime_epoch"], "predecessor": config["predecessor"],
             "budget": {role: sum(s["native_limits"][role] for s in config["scopes"].values()) for role in m.ROLES}}
    c.save(root / "run.json", state)
    journal = Successor(root, historical); journal.append("m02_successor_initialized", state)
    guard(journal, state, config)
    return {"run": str(root), "scope": config["status"], "created_project": False, "identity": identity, "cost_baseline": costs(journal, config)}


def load(root):
    root = Path(root).resolve(); config = c.read(root / "registration.json")
    _, _, historical = validate(config); journal = Successor(root, historical); state = c.read(root / "run.json")
    require(state["registration_sha256"] == c.digest(c.encoded(config))
            and journal.local.events()[0]["kind"] == "m02_successor_initialized"
            and journal.local.events()[0]["data"] == state, "immutable successor identity changed")
    installation(config)
    guard(journal, state, config)
    return journal, state, config


def costs(journal, config):
    counts = {p: {r: 0 for r in m.ROLES} for p in m.PHASES}
    for row in m.events(journal, "m02_native_started") + config["auxiliary_executions"]:
        counts[row["phase"]][row["role"]] += 1
    return {"whole": sum(sum(x.values()) for x in counts.values()), "whole_cap": 67, "by_phase_role": counts,
            "sdk_attempts_successor": sum(e["kind"] == "sdk_intent" for e in journal.local.events()),
            "sdk_queries_successor": sum(e["kind"] == "m02_query_intent" for e in journal.local.events())}


def barrier(journal, state, config, command, path):
    """Root serializes *all* old/new routes; local flock alone cannot stop old code."""
    c.check_ref(config["admission"]); ref = c.reference(path); value = c.read(path)
    doc = guard(journal, state, config)
    require(value.get("format") == "rc3-m02-exclusive-root-barrier.v1" and value.get("observer") == "/root"
            and value.get("assurance") == "host_attested" and value.get("command") == command
            and value.get("registration_binding") == binding(config)
            and value.get("project_id") == doc["project_id"] and value.get("base_revision") == doc["revision_id"]
            and value.get("successor_frontier") == len(journal.local.events())
            and value.get("old_write_routes_retired") is True and value.get("all_other_writers_stopped") is True
            and value.get("exclusive_until_command_completed") is True, "fresh exact exclusive Root route barrier required")
    c.fresh(value["observed_at_utc"])
    require(value.get("source_observations"), "actual serialization observations required")
    for item in value["source_observations"]: c.check_ref(item)
    require(not any(x["data"].get("barrier") == ref for x in journal.local.events()), "barrier already consumed")
    journal.append("m02_root_barrier", {"command": command, "barrier": ref, "base_revision": doc["revision_id"]})
    return value


def query(journal, state, config, operation_key):
    """Query only a pending successor mutation; never call its original function."""
    from deck_master import operations, service, capabilities, collaboration
    pending = journal.unfinished(); require(operation_key in pending, "exact unresolved successor key required")
    local = [x["data"] for x in journal.local.events() if x["kind"] == "sdk_intent" and x["data"]["operation_key"] == operation_key]
    require(len(local) == 1, "historical operations are not successor reconciliation scope")
    intent = local[0]; operation = intent["operation"]; opid = intent["arguments"].get("operation_id")
    fixed_reads = {"service.task_status": lambda: service.task_status(state["project"], task_id=TASK),
                   "capabilities.installation_identity": capabilities.installation_identity,
                   "collaboration.describe": lambda: collaboration.describe(state["project"])}
    require(operation in fixed_reads or operation == "service.task_cancel" or (opid and operation == "stages.assemble"), "operation has no supported public durable reconciliation; remain blocked")
    args = {"task_id": TASK} if operation == "service.task_cancel" else ({"operation_id": opid} if operation not in fixed_reads else intent["arguments"])
    qid = uuid.uuid4().hex
    journal.append("m02_query_intent", {"query_key": qid, "operation_key": operation_key, "arguments": args})
    try:
        result = (fixed_reads[operation]() if operation in fixed_reads else
                  service.task_status(state["project"], task_id=TASK) if operation == "service.task_cancel" else
                  operations.show(state["project"], **args))
    except Exception as exc:
        journal.append("m02_query_error", {"query_key": qid, "type": type(exc).__name__, "error": str(exc)})
        raise
    journal.append("m02_query_outcome", {"query_key": qid, "result": result})
    # Actual durable response is preserved. Host interpretation cannot turn a
    # not-found/error into permission to replay. No generic settlement input.
    if operation in fixed_reads:
        journal.append("sdk_reconciliation", {"operation_key": operation_key, "actual_query": qid, "result": result, "retry_authorized": False, "kind": "fresh_read_only_observation"})
    elif operation == "service.task_cancel":
        doc = guard(journal, state, config); task = c.task_for(c.store_for(state), TASK)
        require(intent["arguments"]["task_id"] == TASK, "exact original cancel intent required")
        stable = lambda value: {k: v for k, v in value.items() if k not in {"status", "updated_at"}}
        if task["status"] == "cancelled" and stable(task) == stable(config["blocked_task"]):
            require(content_identity(doc) == config["initial_content"] and doc["outputs"] == config["initial_outputs"], "cancel reconciliation protected content/output drift")
            journal.append("sdk_reconciliation", {"operation_key": operation_key, "actual_query": qid, "result": result, "retry_authorized": False})
            journal.append("m02_obsolete_task_cancelled", {"task_id": TASK, "result": result, "recovered_actual_fact": True})
    elif result.get("status") == "committed":
        doc = c.store_for(state).load_document()
        actual = result["operation_result"]
        require(doc["revision_id"] == result["committed_revision_id"] == actual["revision_id"]
                and doc["parent_revision_id"] == intent["arguments"]["base_revision"]
                and doc["change"]["operation_id"] == opid and doc["outputs"] == actual["outputs"]
                and content_identity(doc) == config["initial_content"], "committed assembly no longer exact current transition; remain blocked")
        journal.append("sdk_reconciliation", {"operation_key": operation_key, "actual_query": qid, "result": result, "retry_authorized": False})
        journal.append("m02_supplemental_assembled", {"runtime_epoch": config["runtime_epoch"], "outputs": doc["outputs"], "result": result, "recovered_actual_commit": True})
    return result


def claim_read(journal, state, config, stage, ordinal, executor):
    from deck_master import service
    invocation, target = c.execution(journal, stage, ordinal)
    require(executor == invocation["executor"], "actual successor executor required")
    dispatch = current_stage(journal, state, config, stage, ordinal)
    task = c.task_for(c.store_for(state), dispatch["task_id"])
    args = {"task_id": task["task_id"], "execution_ref": executor,
            "supported_protocols": [task["protocol_version"]] if task.get("protocol_version") else None,
            "capabilities": task.get("required_capabilities")}
    claimed = c.record_sdk(journal, "service.task_start", args, lambda: service.task_start(state["project"], **args))
    methods = c.record_sdk(journal, "method_resources.read_task_methods", {"task_id": task["task_id"]}, lambda: c.read_installed_task_methods(state, task))
    require(methods["status"] == "current" and methods["dispatch_method_release"] == methods["current_method_release"] == dispatch["method_release"], "current new methods required")
    c.save(target / "claim.json", claimed)
    ref = c.save(target / "method-read-record.json", methods)
    journal.append("method_bytes_returned", {"ordinal": ordinal, "executor": executor, "record": ref,
        "limitation": "runtime full bytes; actual read/application requires Root observation"})
    return methods


def inspect_transition(journal, state, config):
    from deck_master import capabilities, service, collaboration
    return {"installation": c.record_sdk(journal, "capabilities.installation_identity", {}, capabilities.installation_identity),
            "task": c.record_sdk(journal, "service.task_status", {"task_id": TASK}, lambda: service.task_status(state["project"], task_id=TASK)),
            "collaboration": c.record_sdk(journal, "collaboration.describe", {}, lambda: collaboration.describe(state["project"])),
            "dependencies": guard(journal, state, config), "costs": costs(journal, config)}


def cancel_blocked(journal, state, config, evidence):
    from deck_master import service
    require(m.phase(journal) == "live" and not m.events(journal, "m02_obsolete_task_cancelled"), "one live administrative cancellation only")
    doc = guard(journal, state, config)
    require(content_identity(doc) == config["initial_content"], "protected content drift before cancellation")
    status = c.record_sdk(journal, "service.task_status", {"task_id": TASK}, lambda: service.task_status(state["project"], task_id=TASK))
    task = c.task_for(c.store_for(state), TASK)
    require(task["status"] == "running" and task["kind"] == "repair" and task.get("execution_ref") == ACTOR
            and task["scope_pages"] == config["scopes"]["live"]["page_ids"]
            and task == config["blocked_task"], "exact original stopped readback Task required")
    # Legacy repair Tasks legitimately omit generation_attempts; an explicit
    # null/unknown value is not the schema's absent, never-begun collection.
    require(task.get("call_allowances", []) == [] and task.get("generation_attempts", []) == [], "no allowance or external attempt may exist")
    require(evidence.get("producer_executor") == ACTOR and evidence.get("producer_status") == "completed"
            and evidence.get("producer_raw") is None and evidence.get("external_inflight") == 0
            and evidence.get("external_unknown") == 0 and evidence.get("external_attempts") == 0, "real stopped producer/no raw/zero external evidence required")
    obsolete = {r["ordinal"] for r in m.events(journal, "native_begun") if r["stage"] == config["blocked_stage"]}
    require(not any(r.get("ordinal") in obsolete for r in m.events(journal, "native_output_frozen")), "obsolete stage has frozen raw")
    require(guard(journal, state, config)["revision_id"] == doc["revision_id"], "current changed during cancellation checks")
    reason = "Prospective M02 Source S07/S10 runtime revalidation: stopped obsolete 3ec readback task; no raw or external calls; no claim transfer."
    result = c.record_sdk(journal, "service.task_cancel", {"task_id": TASK, "reason": reason}, lambda: service.task_cancel(state["project"], task_id=TASK, reason=reason))
    after = guard(journal, state, config)
    require({k: after.get(k) for k in ("narrative", "content_plan", "pages", "outputs", "files")} == {k: doc.get(k) for k in ("narrative", "content_plan", "pages", "outputs", "files")}, "cancellation changed protected objects")
    journal.append("m02_obsolete_task_cancelled", {"task_id": TASK, "actual_status_before": status, "result": result})
    return result


def assemble(journal, state, config, operation_id):
    from deck_master import stages, content_review
    require(m.phase(journal) == "live" and m.events(journal, "m02_obsolete_task_cancelled")
            and not m.events(journal, "m02_supplemental_assembled"), "cancel obsolete task then one unchanged live assembly")
    doc = guard(journal, state, config); store = c.store_for(state)
    require(content_identity(doc) == config["initial_content"], "unchanged original content/PNG/SVG/notes required")
    require(content_review.preproduction_status(store, doc)["status"] == "pass", "ordinary current preproduction gate blocked")
    stages.require_assembly_ready(store, doc)
    args = {"base_revision": doc["revision_id"], "operation_id": c.safe_name(operation_id)}
    require(not any(x["kind"] == "sdk_intent" and x["data"]["arguments"].get("operation_id") == operation_id for x in journal.events()), "new operation ID required")
    result = c.record_sdk(journal, "stages.assemble", args, lambda: stages.assemble(state["project"], **args))
    after = guard(journal, state, config)
    require(content_identity(after) == config["initial_content"], "compiler changed correct content")
    journal.append("m02_supplemental_assembled", {"runtime_epoch": config["runtime_epoch"], "outputs": after["outputs"], "result": result})
    return result


def current_stage(journal, state, config, stage, ordinal=None):
    c.safe_name(stage)
    require(any(e["kind"] == "stage_prepared" and e["data"]["stage"] == stage for e in journal.local.events()), "only successor prepared stages; no old claim/raw transfer")
    dispatch = m.current_stage(journal, stage)
    if ordinal is not None:
        require(any(e["kind"] == "native_begun" and e["data"]["stage"] == stage and e["data"]["ordinal"] == ordinal for e in journal.local.events()), "only actual successor execution ordinal")
        require(costs(journal, config)["whole"] <= 67, "whole inherited native ceiling exceeded")
    return dispatch


def prepare(journal, state, config, stage, task_id, role):
    """Keep original role/scope gates; packet contains current facts, not old raw."""
    from deck_master import service, tasks
    require(role in m.ROLES, "original M02 role required")
    store = c.store_for(state); doc = guard(journal, state, config); task = c.task_for(store, task_id)
    old_ids = {x["data"].get("task_id") for x in journal.historical if x["kind"] == "stage_prepared"}
    require(task_id not in old_ids and task_id != TASK, "old Task/method release cannot transfer")
    require(task["status"] in {"awaiting_host", "running"} and tasks.task_inputs_current(store, doc, task), "current genuine Task required")
    require(set(task.get("scope_pages") or []) <= set(config["scopes"][m.phase(journal)]["page_ids"]), "Task scope outside current use")
    require((role in {"feedback", "verification", "production_review"}) == (task["kind"] == "review")
            and (role in {"feedback", "verification"}) == (task["kind"] == "review" and task.get("review_stage") == "preproduction"), "actual Task/review role mismatch")
    require(role not in {"initial_writer", "repair_writer"} or task["kind"] == "compose", "real compose required")
    require(role != "production" or task["kind"] in {"blueprint", "reconstruct", "repair", "style_analyze"}, "real production Task required")
    current = m.phase(journal)
    if role == "initial_writer": require(not m.events(journal, "m02_feedback_delivered", current), "no postfeedback initial author")
    if role == "feedback": require(not m.accepted_reviews(journal, current, role), "one inherited feedback")
    if role in {"repair_writer", "verification"}:
        require(m.events(journal, "m02_repair_begun", current), "finding-driven repair required")
        if role == "verification": require(m.events(journal, "m02_repair_accepted", current), "actual accepted repair before verification")
        else: require((task.get("collaboration_binding") or {}).get("phase") in m.events(journal, "m02_repair_begun", current)[0]["declaration"]["necessary_layers"], "only necessary repair layer")
    methods = c.record_sdk(journal, "service.read_task_methods", {"task_id": task_id}, lambda: c.read_installed_task_methods(state, task))
    require(methods["current_method_release"]["release_id"] == config["runtime_epoch"]
            and methods["dispatch_method_release"] == methods["current_method_release"], "genuine new-release Task/methods required")
    c.safe_name(stage); target = journal.root / "stages" / stage; target.mkdir(parents=True, exist_ok=False)
    c.save(target / "task.json", task); c.save(target / "work-order.json", service.task_summary(store, doc, task))
    c.save(target / "prepared-method-bytes.json", methods); c.save(target / "current-artifacts.json", c.current_manuscript(store))
    m.packet_boundary(target, state, role)
    for ref in [config["grammar"], *config["technical_supplements"]]: c.write_once(target / "technical" / Path(ref["path"]).name, Path(ref["path"]).read_bytes())
    for schema in (Path(config["installation"]["module_file"]).parent / "resources/contracts").glob("*.schema.json"):
        c.write_once(target / "schemas" / schema.name, schema.read_bytes())
    if role == "repair_writer":
        original = m.events(journal, "m02_feedback_delivered", current)[0]
        c.write_once(target / "single-feedback.json", Path(original["raw"]["path"]).read_bytes())
        c.save(target / "repair-scope.json", m.events(journal, "m02_repair_begun", current)[0])
    dispatch = {"stage": stage, "role": role, "task_id": task_id, "project_id": doc["project_id"], "method_release": methods["current_method_release"], "m02_phase": current}
    c.save(target / "dispatch.json", dispatch); journal.append("stage_prepared", dispatch)
    return {"packet": str(target), **dispatch}


def begin(journal, state, config, stage, invocation, *, notes=False):
    dispatch = current_stage(journal, state, config, stage); obs = c.read(invocation)
    executor = obs["spawn"]["canonical_task_name"]
    old_actors = {r["executor"] for r in m.events(SuccessorView(journal.historical), "native_begun")} | {r["executor"] for r in config["auxiliary_executions"]}
    require(executor not in old_actors and not set(obs["spawn"].get("inherited_identities", [])) & old_actors, "fresh new execution; no old actor/raw reuse")
    count = costs(journal, config); role = dispatch["role"]; phase = m.phase(journal)
    # Actual overrun invocation is still recorded and remains unconsumable.
    bounded = deepcopy(state); total = sum(r["role"] == role for r in m.events(journal, "native_begun"))
    remaining = min(67 - count["whole"], config["scopes"][phase]["native_limits"][role] - count["by_phase_role"][phase][role])
    bounded["budget"][role] = total + max(0, remaining)
    if notes:
        bounded_config = deepcopy(config)
        bounded_config["scopes"][phase]["native_limits"][role] = count["by_phase_role"][phase][role] + max(0, remaining)
        return m.begin_notes(journal, bounded, bounded_config, stage, invocation)
    result = c.begin_native(journal, bounded, m.helper_config(config), stage, invocation)
    journal.append("m02_native_started", {"phase": phase, **result})
    return result


def review_prepare(journal, state, config, stage, role, bootstrap):
    from deck_master import content_review
    current = m.phase(journal)
    require(role in {"feedback", "verification"}, "ordinary content review only")
    if role == "feedback":
        require(not m.accepted_reviews(journal, current, role), "one inherited feedback")
        m.content_checkpoint(journal, state, config)
    else: require(m.events(journal, "m02_repair_begun", current) and m.events(journal, "m02_repair_accepted", current), "actual adopted repair required")
    with c.native_runtime(bootstrap) as registry:
        result = c.record_sdk(journal, "content_review.dispatch_preproduction_review", {"bootstrap": c.reference(bootstrap)}, lambda: content_review.dispatch_preproduction_review(state["project"], adapter_context=registry.channel_context()))
    if result["status"] != "review_dispatched": return result
    packet = prepare(journal, state, config, stage, result["task"]["task_id"], role)
    c.save(Path(packet["packet"]) / "review-packet.json", c.store_for(state).read_object_json(result["review_draft_ref"]))
    return packet


def export_current(journal, state, config, arguments):
    require(m.events(journal, "m02_supplemental_assembled"), "real supplemental assembly required")
    doc = guard(journal, state, config); final = {r["task_id"] for r in m.events(journal, "stage_prepared") if r.get("m02_phase") == m.phase(journal) and r["role"] == "production_review"}
    accepted = {r.get("task_id") or (r.get("outcome") or {}).get("task_id") for r in m.events(journal, "result_accepted")}
    require(any(t["kind"] == "review" and t.get("review_stage", "final") == "final" and t["status"] == "completed" and t["task_id"] in final & accepted for t in (c.store_for(state).read_object_json(ref) for ref in doc["tasks"])), "fresh current final review required")
    # Retain the frozen full-version predicates; meter the public export and
    # each actual manifest/download query individually. Binary returns remain
    # complete immutable bytes, never converted into a fabricated report.
    from deck_master import editing, exports
    current = m.phase(journal)
    require(not m.events(journal, "m02_version_exported", current), "one original export per use")
    record = m.complete_version(journal, state, config, current)
    args = deepcopy(arguments)
    require(args.get("revision") == record["revision_id"] and args.get("purpose") == "review"
            and args.get("notes_policy") == config["scopes"][current]["notes_policy"], "exact current review/notes projection required")
    require(args.get("output_dir") and not Path(args["output_dir"]).exists() and args.get("export_id"), "new export identity/destination required")
    result = c.record_sdk(journal, "editing.export_project.M02", args, lambda: editing.export_project(state["project"], **args))
    stored = c.record_sdk(journal, "exports.show", {"export_id": result["export_id"]}, lambda: exports.show(state["project"], export_id=result["export_id"]))
    require(stored["manifest"]["variant"]["narrative_ref"] == record["narrative_ref"], "export fixed Narrative differs")
    for index, item in enumerate(stored["manifest"]["files"]):
        def download(item=item, index=index):
            raw, media = exports.download(state["project"], export_id=result["export_id"], filename=item["path"])
            return {"bytes": c.write_once(journal.root / "download-proof" / result["export_id"] / str(index), raw), "media_type": media}
        c.record_sdk(journal, "exports.download", {"export_id": result["export_id"], "filename": item["path"]}, download)
    require(any(f["path"] == "deck.pptx" for f in stored["manifest"]["files"]), "content-only export cannot complete M02")
    root = Path(state["project"]) / ".deckmaster/workbench/exports" / result["export_id"]
    copy_root = Path(args["output_dir"]).resolve()
    tree = lambda folder: {p.relative_to(folder).as_posix(): c.reference(p)["sha256"] for p in folder.rglob("*") if p.is_file()}
    record.update(output_copy_root=str(copy_root), output_copy_tree=tree(copy_root), export_id=result["export_id"],
                  export_root=str(root), notes_policy=args["notes_policy"], export_tree=tree(root), export_record=stored)
    c.save(journal.root / "versions" / (current + ".json"), record); journal.append("m02_version_exported", record)
    m.preserved(journal)
    journal.append("m02_supplemental_export_provenance", {"runtime_epoch": config["runtime_epoch"], "supplemental_validation_id": config["supplemental_validation_id"], "version": result})
    return record


def execute(journal, state, config, args):
    if args.command in {"status", "query"}: return execute_bound(journal, state, config, args)
    # Registry binding covers every downstream gate, including APIs without
    # an adapter_context parameter. Caller never supplies a context/provider.
    with c.native_runtime(args.bootstrap):
        proof = c.read(args.barrier)
        require(proof.get("bootstrap") == c.reference(args.bootstrap), "barrier must bind actual live Root channel observation")
        return execute_bound(journal, state, config, args)


def execute_bound(journal, state, config, args):
    command = args.command
    if command == "status": return {"scope": config["status"], "runtime_epoch": config["runtime_epoch"], "phase": m.phase(journal), "costs": costs(journal, config), "pending": journal.unfinished(), "credit": "NOT_E1_NOT_E2_NOT_HUMAN"}
    if command == "query": return query(journal, state, config, args.operation_key)
    require(not journal.unfinished(), "unresolved old or successor SDK intent; query, no retry")
    proof = barrier(journal, state, config, command, args.barrier)
    if command == "inspect-transition": return inspect_transition(journal, state, config)
    if command == "cancel-blocked-readback-task": return cancel_blocked(journal, state, config, proof)
    if command == "assemble-existing-live": return assemble(journal, state, config, args.operation_id)
    if command == "continue-current":
        from deck_master import service
        return c.record_sdk(journal, "service.continue_project", {}, lambda: service.continue_project(state["project"]))
    if command == "prepare": return prepare(journal, state, config, args.stage, args.task_id, args.role)
    if command == "review-prepare": return review_prepare(journal, state, config, args.stage, args.role, args.bootstrap)
    if command == "release-instruction": return m.instruction(journal, state, config, args.scope, args.trigger)
    if command == "materialize-instruction": return m.instruction_evidence(journal, state, args.scope)
    if command == "start-next-variant":
        arguments = c.read(args.arguments)
        require(set(arguments) == {"input", "base_revision", "operation_id"}, "only original public Request arguments")
        return m.start_variant(journal, state, config, args.variant, arguments)
    if command == "export-current-version":
        arguments = c.read(args.arguments)
        require(set(arguments) == {"output_dir", "purpose", "revision", "export_id", "notes_policy"}, "only original full export arguments")
        return export_current(journal, state, config, arguments)
    if command == "deliver-feedback":
        current_stage(journal, state, config, args.stage, args.ordinal)
        return m.feedback(journal, args.stage, args.ordinal)
    if command == "repair-begin": return m.repair(journal, args.necessity)
    if command == "prepare-notes":
        require(m.phase(journal) == "live_notes_edit", "actual selected-live notes phase required")
        return c.record_sdk(journal, "method_resources.read_skill_methods.prepare_notes", {"stage": args.stage, "operation_id": args.operation_id}, lambda: m.prepare_notes(journal, state, config, args.stage, args.operation_id, args.role))
    current_stage(journal, state, config, args.stage, getattr(args, "ordinal", None))
    if command in {"begin-native", "begin-notes"}: return begin(journal, state, config, args.stage, args.invocation, notes=command == "begin-notes")
    if command == "claim-read": return claim_read(journal, state, config, args.stage, args.ordinal, args.executor)
    if command == "read-notes": return c.record_sdk(journal, "method_resources.read_skill_methods.notes", {"stage": args.stage, "ordinal": args.ordinal, "executor": args.executor}, lambda: m.read_notes(journal, state, args.stage, args.ordinal, args.executor))
    if command in {"observe", "observe-notes"}:
        function = c.observe if command == "observe" else m.observe_notes
        return function(journal, state, args.stage, args.ordinal, args.result, args.result_sha256, args.observation, args.observation_sha256)
    if command == "materialize-native-objects": return c.materialize_native_objects(journal, state, args.stage, args.ordinal)
    if command == "review-accept": return c.review_accept(journal, state, args.stage, args.ordinal, args.bootstrap)
    if command == "accept-notes": return m.accept_notes(journal, state, config, args.stage, args.ordinal)
    if command == "accept": return m.accept(journal, state, args.stage, args.ordinal)
    raise Error("unsupported finite command")


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("initialize"); p.add_argument("--registration", required=True); p.add_argument("--out", required=True)
    commands = ("status", "query", "inspect-transition", "cancel-blocked-readback-task", "assemble-existing-live", "continue-current", "prepare", "review-prepare", "begin-native", "claim-read", "observe", "materialize-native-objects", "accept", "review-accept", "deliver-feedback", "repair-begin", "export-current-version", "release-instruction", "materialize-instruction", "start-next-variant", "prepare-notes", "begin-notes", "read-notes", "observe-notes", "accept-notes")
    staged = {"prepare", "review-prepare", "begin-native", "claim-read", "observe", "materialize-native-objects", "accept", "review-accept", "deliver-feedback", "prepare-notes", "begin-notes", "read-notes", "observe-notes", "accept-notes"}
    for command in commands:
        p = sub.add_parser(command); p.add_argument("--run", required=True)
        if command not in {"status", "query"}:
            p.add_argument("--barrier", required=True)
            p.add_argument("--bootstrap", required=True)
        if command in staged: p.add_argument("--stage", required=True)
        if command in staged - {"prepare", "review-prepare", "begin-native", "prepare-notes", "begin-notes"}: p.add_argument("--ordinal", type=int, required=True)
        if command in {"prepare", "prepare-notes", "review-prepare"}: p.add_argument("--role", choices=m.ROLES, required=True)
        if command == "prepare": p.add_argument("--task-id", required=True)
        if command in {"assemble-existing-live", "prepare-notes"}: p.add_argument("--operation-id", required=True)
        if command in {"begin-native", "begin-notes"}: p.add_argument("--invocation", required=True)
        if command in {"claim-read", "read-notes"}: p.add_argument("--executor", required=True)
        if command in {"observe", "observe-notes"}:
            for name in ("result", "result-sha256", "observation", "observation-sha256"): p.add_argument("--" + name, required=True)
        if command in {"release-instruction", "materialize-instruction"}: p.add_argument("--scope", choices=("read", "live_notes_edit"), required=True)
        if command == "release-instruction": p.add_argument("--trigger", required=True)
        if command == "start-next-variant": p.add_argument("--variant", choices=("read", "live_notes_edit"), required=True)
        if command in {"start-next-variant", "export-current-version"}: p.add_argument("--arguments", required=True)
        if command == "repair-begin": p.add_argument("--necessity", required=True)
        if command == "query": p.add_argument("--operation-key", required=True)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated and sys.dont_write_bytecode, "use own absolute Python -I -B")
        if args.command == "initialize": result = initialize(args.registration, args.out)
        else:
            # Acquire lock before reloading any admission/frontier/current facts.
            with c.Journal(args.run).locked():
                journal, state, config = load(args.run)
                result = execute(journal, state, config, args)
                guard(journal, state, config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (Error, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__": main()
