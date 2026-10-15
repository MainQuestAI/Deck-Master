#!/usr/bin/env python3
"""RC3 campaign recorder and installed-SDK adapter (no model or image calls).

Run with an admitted installation's absolute Python, -I -B. Root supplies its
actual native observations. Hashes preserve observations; they do not make
them platform attestations, human evidence, or proof of semantic quality.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
import sys
import uuid


VERSION = "rc3-campaign-controller.v1"
OBSERVER_KIND = "root_controller_transcription_of_actual_native_tool_response"
CHANNEL = "independent_review_receipts"
PROVIDER_ID = "rc3-final-native-root-controller"
ROLES = {"initial_writer", "repair_writer", "feedback", "verification", "production", "production_review", "post_comparison_writer", "extra_writer"}
WRITER_ROLES = {"initial_writer", "repair_writer", "production", "post_comparison_writer", "extra_writer"}
SNAPSHOTS = {"original_complete", "first_sdk_complete", "equal_budget_evaluated",
             "qualified_for_owner", "owner_later", "extra_work"}
PUBLIC_OPERATIONS = {
    "service.create", "service.continue_project", "service.inputs_show", "service.inputs_update",
    "service.import_draft", "service.preview_draft_import", "service.update_design", "service.import_asset",
    "collaboration.start_request", "collaboration.record_decision", "collaboration.grant",
    "content_production.adopt_proposal",
    "changes.plan", "changes.commit", "styles.propose", "styles.confirm", "styles.plan",
    "candidates.listing", "candidates.show", "candidates.plan", "candidates.adopt", "generation.freeze", "generation.show",
    "delivery_eligibility.describe", "editing.export_project", "operations.show", "changes.handoff",
    "tasks.allocate_call_allowances", "tasks.call_begin", "native_image_evidence.image_binding",
}


class CampaignError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def write_once(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    return {"path": str(path.resolve()), "sha256": digest(raw), "bytes": len(raw)}


def save(path, value):
    return write_once(path, encoded(value))


def reference(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {"path": str(path), "sha256": digest(raw), "bytes": len(raw)}


def check_ref(ref):
    actual = reference(ref["path"])
    if actual["sha256"] != ref["sha256"] or ("bytes" in ref and actual["bytes"] != ref["bytes"]):
        raise CampaignError("pinned bytes changed: " + str(ref["path"]))
    return actual


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise CampaignError("use a simple nonempty identity, without path components")
    return value


def fresh(value, *, max_age=timedelta(minutes=45)):
    stamp = (datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
             if value.endswith(" UTC") else datetime.fromisoformat(value.replace("Z", "+00:00")))
    if stamp.tzinfo is None:
        raise CampaignError("native observation needs a timezone")
    age = datetime.now(timezone.utc) - stamp
    if age < timedelta(seconds=-10) or age > max_age:
        raise CampaignError("native observation is stale or in the future")


class Journal:
    """Local append-only hash chain; deliberately not an authorization store.

    The lock prevents accidental concurrent controller writes. Existing files
    are never replaced. A crashed SDK intent needs explicit reconciliation;
    the log never implies the external operation happened or did not happen.
    """
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def locked(self):
        with (self.root / ".controller.lock").open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def events(self):
        result, previous = [], None
        for index, path in enumerate(sorted((self.root / "journal").glob("*.json")), 1):
            raw = path.read_bytes()
            item = json.loads(raw)
            if path.name != f"{index:06d}.json" or item["sequence"] != index or item["previous_sha256"] != previous:
                raise CampaignError("journal sequence/hash chain changed")
            result.append(item)
            previous = digest(raw)
        return result

    def append(self, kind, data):
        events = self.events()
        previous = reference(self.root / "journal" / f"{len(events):06d}.json")["sha256"] if events else None
        event = {"sequence": len(events) + 1, "previous_sha256": previous,
                 "recorded_at": now(), "kind": kind, "data": data}
        save(self.root / "journal" / f"{len(events)+1:06d}.json", event)
        return event

    def unfinished(self):
        pending = {}
        for event in self.events():
            data = event["data"]
            if event["kind"] == "sdk_intent":
                pending[data["operation_key"]] = data
            elif event["kind"] in {"sdk_outcome", "sdk_reconciliation"}:
                pending.pop(data["operation_key"], None)
        return pending


def validate_registration(config):
    engineering = config.get("status") == "ENGINEERING_ONLY_NOT_ADMITTED"
    if config.get("format") != "rc3-campaign-registration.v1" or config.get("status") not in {"ADMITTED", "ENGINEERING_ONLY_NOT_ADMITTED"}:
        raise CampaignError("registration must be an independently reviewed, actual ADMITTED version")
    if engineering and set(config.get("cases", {})) != {"GENTRY"}:
        raise CampaignError("engineering registration may expose only a separate neutral GENTRY case")
    if config.get("controller_sha256") != digest(Path(__file__).read_bytes()):
        raise CampaignError("registration does not pin these controller bytes")
    for key in ("protocol", "grammar", "exposure_registry", "admission_review"):
        check_ref(config[key])
    for component in config.get("component_dependencies", []):
        check_ref(component)
    for gate in ("G04", "GID", "GADAPTER", "GENTRY", "GFREEZE"):
        record = config["gates"][gate]
        if record.get("status") != "PASS" and not engineering:
            raise CampaignError(gate + " has not passed")
        if record.get("status") == "PASS":
            check_ref(record["evidence"])
    if config["budget"] != {"initial_writer": 5, "feedback": 1, "repair_cycles": 1, "repair_writer": 3}:
        raise CampaignError("v3 common content budget differs; register a separate protocol before execution")
    if not config.get("installations"):
        raise CampaignError("no actual installations registered")
    for spec in config["installations"].values():
        for key in ("source_sha", "source_tree", "wheel_sha256", "python", "module_file", "package_files"):
            if not spec.get(key):
                raise CampaignError("actual installation identity missing: " + key)
        check_ref(spec["manifest"])
    exposure = read(config["exposure_registry"]["path"])
    if exposure.get("status") != "FROZEN" or not exposure.get("excluded_identities"):
        raise CampaignError("freeze the complete preparer/author/exposure registry first")
    return config


def freeze_registration(config_path, root):
    config = validate_registration(read(config_path))
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    save(root / "registration.json", config)
    save(root / "registration-origin.json", reference(config_path))
    Journal(root).append("registration_frozen", {"registration_sha256": digest(encoded(config)),
                                               "actual_model_execution": "NOT_RUN"})
    return {"campaign": str(root), "status": "admitted_registration_frozen"}


def installation(config, arm, *, enforce_isolation=True):
    """Recheck actual installed code, not an arm label or source checkout."""
    if enforce_isolation and not sys.flags.isolated:
        raise CampaignError("run the actual admitted installation Python with -I -B")
    import deck_master
    spec = config["installations"][arm]
    if Path(sys.executable).absolute() != Path(spec["python"]).absolute():
        raise CampaignError("wrong installation interpreter")
    if Path(deck_master.__file__).resolve() != Path(spec["module_file"]).resolve():
        raise CampaignError("wrong deck_master module origin")
    check_ref(spec["manifest"])
    root = Path(spec["module_file"]).resolve().parent
    candidate_manifest = read(spec["manifest"]["path"])
    manifest_module = candidate_manifest.get("module_path") or candidate_manifest.get("installed_module_path")
    if (candidate_manifest.get("source_sha") != spec["source_sha"]
            or candidate_manifest.get("source_tree") != spec["source_tree"]
            or candidate_manifest.get("wheel_sha256") != spec["wheel_sha256"]
            or not manifest_module or Path(manifest_module).resolve() != root / "__init__.py"):
        raise CampaignError("actual pinned candidate manifest source/tree/wheel/module differs")
    expected = {}
    for item in spec["package_files"]:
        relative = Path(item["relative_path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() in expected:
            raise CampaignError("invalid installed package inventory")
        target = root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise CampaignError("installed package escapes its admitted root")
        if digest(target.read_bytes()) != item["sha256"]:
            raise CampaignError("installed bytes changed: " + str(relative))
        expected[relative.as_posix()] = item["sha256"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    if actual != set(expected):
        raise CampaignError("installed package inventory gained or lost files")
    if spec.get("adapter_profile") == "A0-public-legacy":
        # A0 has no capabilities module. Its original package/manifest and own
        # installed work-order methods are observed without importing B code.
        check_ref(spec["wheel"])
        manifest = read(spec["manifest"]["path"])
        if (spec["wheel"]["sha256"] != spec["wheel_sha256"]
                or manifest.get("source_sha") != spec["source_sha"]
                or manifest.get("source_tree") != spec["source_tree"]
                or manifest.get("wheel_sha256") != spec["wheel_sha256"]
                or Path(manifest["installed_module_path"]).resolve() != root / "__init__.py"):
            raise CampaignError("original A0 package/wheel/manifest differs")
        observed = {"module_path": str(root / "__init__.py"), "python_executable": sys.executable,
                    "install": {"source_sha": manifest["source_sha"], "source_tree": manifest["source_tree"], "wheel_sha256": manifest["wheel_sha256"]},
                    "adapter_profile": "A0-public-legacy", "identity_source": "actual original wheel and pinned package inventory"}
    else:
        from deck_master import capabilities
        observed = capabilities.installation_identity()
    identity = observed.get("install") or {}
    if (identity.get("source_sha") != spec["source_sha"]
            or identity.get("source_tree") is not None and identity["source_tree"] != spec["source_tree"]
            or identity.get("wheel_sha256") != spec["wheel_sha256"]):
        raise CampaignError("installed source/tree/wheel metadata differs from admitted arm")
    observed["tree_observation"] = {"sdk_source_tree": identity.get("source_tree"),
                                    "pinned_candidate_manifest_source_tree": candidate_manifest["source_tree"]}
    for name, module in tuple(sys.modules.items()):
        if (name == "deck_master" or name.startswith("deck_master.")) and getattr(module, "__file__", None):
            if not Path(module.__file__).resolve().is_relative_to(root):
                raise CampaignError("borrowed module: " + name)
    return observed


def load_run(path):
    root = Path(path).resolve()
    state = read(root / "run.json")
    config = read(Path(state["campaign"]) / "registration.json")
    if digest(encoded(config)) != state["registration_sha256"]:
        raise CampaignError("campaign registration changed after workflow init")
    validate_registration(config)
    installation(config, state["arm"])
    journal = Journal(root)
    events = journal.events()
    if not events or events[0]["kind"] != "workflow_initialized" or events[0]["data"] != state:
        raise CampaignError("workflow manifest differs from its immutable initialized identity")
    return journal, state, config


def init_run(campaign, root, arm, case, repetition, project, *, checkpoint=None):
    config = validate_registration(read(Path(campaign) / "registration.json"))
    installation(config, arm)
    if case not in {"Q1", "Q2", "Q3", "Q4A", "Q4B", "GENTRY", "U-LIVE-01", "U-READ-01"}:
        raise CampaignError("case not registered")
    if repetition not in {1, 2} or (repetition == 2 and case not in {"Q1", "Q2"}):
        raise CampaignError("repeat identity must match the predeclared Q1/Q2 pairs")
    inputs = config["cases"][case]
    for ref in inputs["materials"]:
        check_ref(ref)
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    state = {"format": VERSION, "campaign": str(Path(campaign).resolve()),
             "registration_sha256": digest(encoded(config)), "arm": arm, "case": case,
             "repetition": repetition, "project": str(Path(project).resolve()),
             "budget": config["budget"], "materials": inputs["materials"],
             "checkpoint": checkpoint, "human": "NOT_RUN_USER_DEFERRED"}
    save(root / "run.json", state)
    Journal(root).append("workflow_initialized", state)
    return state


def sdk_operation(journal, state, operation, arguments, *, evidence=None, operation_key=None):
    """One explicit public call. No fake success, retries, phase dispatch or cancel."""
    if operation not in PUBLIC_OPERATIONS:
        raise CampaignError("operation not exposed by this campaign adapter: " + operation)
    if journal.unfinished():
        raise CampaignError("an earlier SDK intent is unresolved; inspect actual Runtime operations/state first")
    if any(k in arguments for k in ("adapter_context", "review_receipt_selector")):
        raise CampaignError("project JSON cannot choose a trusted receipt context")
    arguments = deepcopy(arguments)
    module_name, name = operation.split(".", 1)
    module = importlib.import_module("deck_master." + module_name)
    function = getattr(module, name)
    parameters = inspect.signature(function).parameters
    project_parameter = next((key for key in ("project_dir", "project", "store") if key in parameters), None)
    if project_parameter is None:
        raise CampaignError("unsupported public function signature: " + operation)
    if project_parameter == "store" and "store" in arguments:
        raise CampaignError("project JSON cannot supply a Runtime Store")
    if project_parameter != "store" and project_parameter in arguments and Path(arguments[project_parameter]).resolve() != Path(state["project"]):
        raise CampaignError("operation tries to change the workflow's project")
    if operation == "generation.freeze":
        if arguments.get("input", {}).get("parameters") != {"transparent_background": False}:
            raise CampaignError("campaign freezes exactly preregistered opaque-background tool parameters")
    if operation in {"tasks.call_begin", "native_image_evidence.image_binding"}:
        from deck_master import generation
        if operation == "tasks.call_begin":
            request = generation.show(state["project"], request_id=arguments.get("request_id"))["request"]
        else:
            attempt = generation.show(state["project"], attempt_id=arguments.get("attempt_id"))["attempt"]
            request = store_for(state).read_object_json(attempt["request_ref"])
        if request.get("task_id") != arguments.get("task_id") or request["input"].get("parameters") != {"transparent_background": False}:
            raise CampaignError("existing frozen request differs from this campaign's exact opaque-background parameters/Task")
    if operation == "native_image_evidence.image_binding":
        if "document" in arguments:
            raise CampaignError("image binding uses the actual current committed Document")
    serial_arguments = {**arguments, project_parameter: state["project"]}
    arguments[project_parameter] = store_for(state) if project_parameter == "store" else state["project"]
    if operation == "native_image_evidence.image_binding":
        arguments["document"] = arguments["store"].load_document()
    key = safe_name(operation_key or uuid.uuid4().hex)
    if any(event["data"].get("operation_key") == key for event in journal.events()):
        raise CampaignError("operation key already recorded; inspect its actual outcome, do not resend blindly")
    if evidence is not None:
        check_ref(evidence)
    return record_sdk(journal, operation, serial_arguments, lambda: function(**arguments),
                      key=key, evidence=evidence)


def record_sdk(journal, operation, arguments, call, *, key=None, evidence=None):
    if journal.unfinished():
        raise CampaignError("earlier SDK intent is unresolved; inspect actual Runtime operations/state")
    key = safe_name(key or uuid.uuid4().hex)
    journal.append("sdk_intent", {"operation_key": key, "operation": operation,
                                 "arguments": arguments, "authority_evidence": evidence})
    try:
        outcome = call()
    except Exception as exc:
        journal.append("sdk_error", {"operation_key": key, "error_type": type(exc).__name__, "error": str(exc),
                                    "semantic_fallback": False, "commit_state": "unresolved_until_runtime_observed"})
        raise
    journal.append("sdk_outcome", {"operation_key": key, "result": outcome})
    return outcome


def store_for(state):
    from deck_master.store import Store
    return Store(state["project"])


def task_for(store, task_id):
    for ref in store.load_document()["tasks"]:
        task = store.read_object_json(ref)
        if task["task_id"] == task_id:
            return task
    raise CampaignError("Task is not referenced by the actual current project")


def current_manuscript(store):
    document = store.load_document()
    return {"document": document,
            "narrative": store.read_object_json(document["narrative"]) if document.get("narrative") else None,
            "content_plan": store.read_object_json(document["content_plan"]) if document.get("content_plan") else None,
            "pages": [{"ref": e["page"], "object": store.read_object_json(e["page"])} for e in document["pages"]],
            "reviews": [{"ref": ref, "object": store.read_object_json(ref)} for ref in document.get("reviews", [])],
            "tasks": [store.read_object_json(ref) for ref in document["tasks"]]}


def read_installed_task_methods(state, task):
    from deck_master import method_resources, service
    if hasattr(method_resources, "read_task_methods"):
        return method_resources.read_task_methods(state["project"], task["task_id"])
    # Older A0 exposes entries through its public task_summary. Reading those
    # exact installed files is a technical adapter, not a replacement method.
    store = store_for(state)
    order = service.task_summary(store, store.load_document(), task)
    entries = []
    method_root = method_resources.resolve_root().resolve()
    for entry in order["method_resources"]:
        path = Path(entry["path"]).resolve()
        if not path.is_relative_to(method_root):
            raise CampaignError("A0 declared method is outside its own installed method root")
        raw = path.read_bytes()
        if digest(raw) != entry["sha256"]:
            raise CampaignError("A0 work-order method bytes changed")
        entries.append({**entry, "content": raw.decode("utf-8")})
    release = method_resources.method_release(entries)
    return {"task_id": task["task_id"], "project_id": store.load_document()["project_id"],
            "work_order": order, "status": "current" if task.get("method_release") == release else "stale",
            "current_method_release": release, "dispatch_method_release": task.get("method_release"),
            "methods": entries, "adapter_profile": "A0-public-task-summary-full-byte-read",
            "consumption": "runtime_returned_bytes", "host_application": "not_recorded"}


def prepare(journal, state, config, stage, task_id, role):
    from deck_master import content_production, service
    stage = safe_name(stage)
    if role not in ROLES:
        raise CampaignError("unregistered native role")
    store = store_for(state)
    task = task_for(store, task_id)
    if task["status"] not in {"awaiting_host", "running"}:
        raise CampaignError("only the Runtime's actual pending/running Task may be prepared")
    if (role in {"feedback", "verification", "production_review"}) != (task["kind"] == "review"):
        raise CampaignError("review and writing Tasks have separate execution accounting")
    if role in {"initial_writer", "repair_writer", "post_comparison_writer", "extra_writer"} and task["kind"] != "compose":
        raise CampaignError("content Writer roles require an actual compose Task")
    if role == "production" and task["kind"] not in {"blueprint", "reconstruct", "repair", "style_analyze"}:
        raise CampaignError("production cannot relabel a substantive compose execution to evade its cap")
    if role in {"feedback", "verification"} and task.get("review_stage") != "preproduction":
        raise CampaignError("feedback/verification must be actual preproduction review Tasks")
    if role == "production_review" and task.get("review_stage") == "preproduction":
        raise CampaignError("preproduction review cannot bypass the independent feedback/verification accounting")
    if role == "post_comparison_writer":
        if state["case"] != "Q2" or not (journal.root / "snapshots" / "equal_budget_evaluated.json").exists() or not any(
                e["kind"] == "scripted_event" and e["data"]["event_id"] == "Q2-change-5min" for e in journal.events()):
            raise CampaignError("post-comparison work needs frozen E1 timepoint and its actual scripted input change")
    if role == "extra_writer" and not any(e["kind"] == "extra_work_begun" for e in journal.events()):
        raise CampaignError("extra work needs an explicit separate evidence-backed declaration")
    if role == "repair_writer" and not any(e["kind"] == "repair_begun" for e in journal.events()):
        raise CampaignError("one actual feedback and necessary repair-layer declaration are required")
    if role == "repair_writer":
        repair = next(e["data"] for e in journal.events() if e["kind"] == "repair_begun")
        if (task.get("collaboration_binding") or {}).get("phase") not in repair["necessary_layers"]:
            raise CampaignError("actual repair Task is outside the preregistered necessary layers")
    if role == "initial_writer" and any(e["kind"] == "repair_begun" for e in journal.events()):
        raise CampaignError("cannot relabel post-feedback work as initial Writer work")
    target = journal.root / "stages" / stage
    target.mkdir(parents=True, exist_ok=False)
    methods = read_installed_task_methods(state, task)
    save(target / "task.json", task)
    save(target / "work-order.json", service.task_summary(store, store.load_document(), task))
    save(target / "prepared-method-bytes.json", methods)
    save(target / "current-artifacts.json", current_manuscript(store))
    grammar = Path(config["grammar"]["path"])
    write_once(target / "public-technical-grammar.json", grammar.read_bytes())
    if task["kind"] == "compose" and task.get("protocol_version") == "compose.v2":
        metadata = {"schema_version": "compose_result.v2", "kind": "compose",
                    "variant": content_production.expected_variant(task), "task_id": task_id,
                    "operation_id": task["operation_id"], "produced_against": task["produced_against"],
                    "eligibility_digest": task["collaboration_binding"]["eligibility_digest"], "usage_events": []}
        save(target / "envelope-metadata.json", metadata)
    module_root = Path(config["installations"][state["arm"]]["module_file"]).resolve().parent
    for path in (module_root / "resources" / "contracts").glob("*.schema.json"):
        write_once(target / "schemas" / path.name, path.read_bytes())
    if role == "repair_writer":
        event = next(e for e in journal.events() if e["kind"] == "repair_begun")
        write_once(target / "single-feedback.json", Path(event["data"]["feedback_raw"]["path"]).read_bytes())
        save(target / "repair-scope.json", event["data"])
    if role == "verification":
        # Includes immutable historical reviews/findings as well as current refs.
        save(target / "historical-review-and-repair-events.json", [e for e in journal.events()
             if e["kind"] in {"feedback_delivered", "repair_begun", "result_accepted", "snapshot_frozen"}])
    dispatch = {"stage": stage, "role": role, "task_id": task_id,
                "project_id": store.load_document()["project_id"], "method_release": methods["current_method_release"],
                "prepared_at": now(), "status": "prepared_not_executed"}
    save(target / "dispatch.json", dispatch)
    save(target / "writer-boundary.json", {"allowed_packet": str(target), "material_refs": state["materials"],
         "forbidden": ["answer banks", "private oracles", "other arm outputs", "old native FINALs", "delegation"],
         "model_calls": "only Root-recorded native executions", "external_image_calls": 0,
         "unknown_native_configuration": "unknown", "human_acceptance": "NOT_RUN_USER_DEFERRED",
         "must_claim_and_read_all_methods": True, "raw_before_sdk": True,
         "verification_feedback_must_not_be_returned_to_writer": role == "verification"})
    journal.append("stage_prepared", dispatch)
    return {"packet": str(target), **dispatch}


def stage_info(journal, stage):
    target = journal.root / "stages" / safe_name(stage)
    return target, read(target / "dispatch.json")


def begin_native(journal, state, config, stage, observation_path):
    target, dispatch = stage_info(journal, stage)
    ref = reference(observation_path)
    observation = read(observation_path)
    spawn = observation["spawn"]
    executor = spawn["canonical_task_name"]
    if (observation.get("observation_kind") != OBSERVER_KIND or observation.get("assurance") != "host_attested"
            or not executor.startswith("/root/") or spawn.get("returned_task_name") != executor
            or observation.get("task_id") != dispatch["task_id"]
            or observation.get("project_id") != dispatch["project_id"]):
        raise CampaignError("Root must record the actual native invocation and exact Task")
    fresh(observation["observed_at_utc"])
    exposure = read(config["exposure_registry"]["path"])
    excluded = set(exposure["excluded_identities"])
    lineage = spawn.get("inherited_identities", [])
    if executor in excluded or any(x in excluded for x in lineage):
        raise CampaignError("native executor inherited excluded preparer/answer/author exposure")
    previous = [e for e in journal.events() if e["kind"] == "native_begun"]
    same = [e for e in previous if e["data"]["executor"] == executor]
    if spawn.get("tool") == "collaboration.spawn_agent":
        if spawn.get("fork_turns") != "none" or same:
            raise CampaignError("a fresh actual Writer/reviewer must use fork_turns=none")
    elif spawn.get("tool") == "collaboration.followup_task":
        if not same or any(e["data"]["role"] != dispatch["role"] for e in same):
            # Initial Writer may continue as its single repair; no reviewer becomes an author.
            writer_repair = same and dispatch["role"] == "repair_writer" and all(
                e["data"]["role"] in {"initial_writer", "repair_writer"} for e in same)
            reviewer_verification = same and dispatch["role"] == "verification" and all(
                e["data"]["role"] in {"feedback", "verification"} for e in same)
            if not writer_repair and not reviewer_verification:
                raise CampaignError("continuation must belong to the same recorded workflow role")
    else:
        raise CampaignError("native invocation must be an actual spawn or followup")
    role = dispatch["role"]
    if role in {"feedback", "verification", "production_review"}:
        authors = {e["data"]["executor"] for e in previous
                   if e["data"]["role"] in WRITER_ROLES}
        if executor in authors:
            raise CampaignError("review execution is a manuscript author")
    used = sum(e["data"]["role"] == role for e in previous)
    cap = state["budget"].get(role)
    # Actual over-budget work is still recorded; consumption is refused later.
    ordinal = len(previous) + 1
    invocation = {"ordinal": ordinal, "stage": stage, "role": role, "executor": executor,
                  "observation": ref, "same_role_ordinal": used + 1, "cap": cap,
                  "within_budget": cap is None or used < cap, "actual_cost": "unknown"}
    write_once(target / "executions" / f"{ordinal:04d}" / "root-invocation.json", Path(observation_path).read_bytes())
    journal.append("native_begun", invocation)
    save(target / "executions" / f"{ordinal:04d}" / "launch-ready.json", invocation)
    return invocation


def execution(journal, stage, ordinal):
    entries = [e["data"] for e in journal.events() if e["kind"] == "native_begun"
               and e["data"]["stage"] == stage and e["data"]["ordinal"] == ordinal]
    if len(entries) != 1:
        raise CampaignError("no unique actual native invocation registered")
    return entries[0], journal.root / "stages" / safe_name(stage) / "executions" / f"{ordinal:04d}"


def claim_read(journal, state, stage, ordinal, executor):
    from deck_master import service
    invocation, target = execution(journal, stage, ordinal)
    if executor != invocation["executor"]:
        raise CampaignError("claim does not match Root's actual invocation")
    dispatch = read(target.parent.parent / "dispatch.json")
    store = store_for(state)
    task = task_for(store, dispatch["task_id"])
    arguments = {"task_id": task["task_id"], "execution_ref": executor,
                 "supported_protocols": [task["protocol_version"]] if task.get("protocol_version") else None,
                 "capabilities": task.get("required_capabilities")}
    claim = record_sdk(journal, "service.task_start", arguments, lambda: service.task_start(state["project"], **arguments))
    methods = read_installed_task_methods(state, task)
    if methods["status"] != "current" or methods["current_method_release"] != dispatch["method_release"]:
        raise CampaignError("actual current Task method bytes changed")
    save(target / "claim.json", claim)
    ref = save(target / "method-read-record.json", methods)
    journal.append("method_bytes_returned", {"ordinal": ordinal, "executor": executor, "record": ref,
                   "limitation": "runtime-returned full bytes; native read/application separately observed"})
    return methods


def observe(journal, state, stage, ordinal, result_path, result_sha256, observation_path, observation_sha256):
    invocation, target = execution(journal, stage, ordinal)
    raw, observed = Path(result_path).read_bytes(), Path(observation_path).read_bytes()
    # Freeze every supplied original, including malformed/rejected outputs, before any SDK parse.
    raw_ref = write_once(target / "raw-native-output", raw)
    obs_ref = write_once(target / "raw-root-completion.json", observed)
    journal.append("native_output_frozen", {"ordinal": ordinal, "raw": raw_ref, "observation": obs_ref})
    try:
        observation = json.loads(observed)
        objects, object_errors = [], []
        declared_objects = observation.get("native_object_files", [])
        if not isinstance(declared_objects, list):
            raise CampaignError("native_object_files must be a list of original file bindings")
        # Preserve the entire readable in-scope collection before any metadata
        # or hash refusal. A bad first item must not discard later originals.
        for index, item in enumerate(declared_objects):
            try:
                original = Path(item["path"]).resolve(strict=True)
                if not original.is_relative_to(target.parent.parent.resolve()) or original.suffix != ".json":
                    raise CampaignError("native proposal originals must be JSON files inside this allowed stage packet")
                original_raw = original.read_bytes()
                frozen = write_once(target / "native-objects" / f"{index:04d}-{digest(original_raw)}.json", original_raw)
                objects.append({"original": reference(original), "frozen": frozen, "declared_ref": item.get("declared_ref")})
                if digest(original_raw) != item.get("sha256"):
                    raise CampaignError("Root observed different native proposal-object bytes")
            except Exception as exc:
                object_errors.append({"index": index, "error_type": type(exc).__name__, "error": str(exc)})
        if declared_objects:
            journal.append("native_objects_frozen", {"ordinal": ordinal, "objects": objects, "errors": object_errors})
        if object_errors:
            raise CampaignError("native object collection has errors; all readable in-scope originals were preserved")
        if digest(raw) != result_sha256 or digest(observed) != observation_sha256:
            raise CampaignError("Root observed different output/observation bytes")
        completed = observation["completion"]
        dispatch = read(target.parent.parent / "dispatch.json")
        executor = invocation["executor"]
        if (observation.get("observation_kind") != OBSERVER_KIND or observation.get("assurance") != "host_attested"
                or observation.get("project_id") != dispatch["project_id"]
                or observation.get("task_id") != dispatch["task_id"]
                or observation.get("model_output_bytes_sha256") != digest(raw)
                or observation.get("method_release") != dispatch["method_release"]
                or completed.get("sender") != executor or completed.get("message_type") != "FINAL_ANSWER"
                or completed.get("status_observation_tool") != "collaboration.list_agents"
                or completed.get("observed_status") != "completed"
                or executor not in completed.get("observed_completed_agents", [])
                or not completed.get("raw_final_message") or not observation.get("all_method_bytes_read")):
            raise CampaignError("actual full FINAL/completed/method/task/output binding disagrees")
        fresh(observation["observed_at_utc"])
        method = reference(target / "method-read-record.json")
        if observation.get("method_read_record_sha256") != method["sha256"]:
            raise CampaignError("native observation does not bind the exact full method response")
        store = store_for(state)
        task = task_for(store, dispatch["task_id"])
        if task["status"] != "running" or task.get("execution_ref") != executor:
            raise CampaignError("actual native execution did not claim this current Task")
        # Parse only after raw immutable storage. No controller metadata/semantic repair.
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise CampaignError("native result must be a complete object")
        save(target / "observed.json", {"raw": raw_ref, "observation": obs_ref, "executor": executor,
                                      "ordinal": ordinal, "within_budget": invocation["within_budget"], "native_objects": objects})
    except Exception as exc:
        journal.append("native_observation_refused", {"ordinal": ordinal, "error_type": type(exc).__name__, "error": str(exc)})
        raise
    journal.append("native_observed", {"ordinal": ordinal, "stage": stage, "raw": raw_ref,
                                     "executor": executor, "assurance": "host_attested"})
    return {"raw": raw_ref, "status": "frozen_before_sdk", "within_budget": invocation["within_budget"]}


def observed_result(journal, stage, ordinal):
    invocation, target = execution(journal, stage, ordinal)
    proof = read(target / "observed.json")
    check_ref(proof["raw"])
    check_ref(proof["observation"])
    if not invocation["within_budget"]:
        raise CampaignError("actual over-budget execution preserved; cannot consume as equal-budget result")
    if any(e["kind"] == "result_accepted" and e["data"]["ordinal"] == ordinal for e in journal.events()):
        raise CampaignError("result already accepted; inspect its actual receipt")
    return invocation, target, read(proof["raw"]["path"]), proof


def accept(journal, state, stage, ordinal):
    from deck_master import service
    invocation, target, envelope, proof = observed_result(journal, stage, ordinal)
    dispatch = read(target.parent.parent / "dispatch.json")
    store = store_for(state)
    task = task_for(store, dispatch["task_id"])
    if task["kind"] == "review" and task.get("review_stage") == "preproduction":
        raise CampaignError("review acceptance requires the scoped opaque native receipt provider")
    if invocation["role"] != "production" and envelope.get("usage_events"):
        raise CampaignError("content experiment has zero external-call budget")
    before = store.load_document()
    protected = {k: deepcopy(before.get(k)) for k in ("narrative", "content_plan", "pages", "files", "design_context", "outputs")}
    try:
        arguments = {"task_id": task["task_id"], "operation_id": task["operation_id"],
                     "produced_against": task["produced_against"], "result_payload": envelope}
        outcome = record_sdk(journal, "service.accept_result", arguments,
                             lambda: service.accept_result(state["project"], **arguments))
    except Exception as exc:
        journal.append("result_refused", {"ordinal": ordinal, "raw": proof["raw"], "error_type": type(exc).__name__,
                                           "error": str(exc), "semantic_fallback": False})
        raise
    if task["kind"] == "review" and {k: store.load_document().get(k) for k in protected} != protected:
        raise CampaignError("read-only review changed content or production")
    journal.append("result_accepted", {"ordinal": ordinal, "role": invocation["role"], "task_id": task["task_id"],
                                      "executor": invocation["executor"], "raw": proof["raw"], "outcome": outcome})
    return outcome


def materialize_native_objects(journal, state, stage, ordinal):
    """Store only exact Writer-authored, pre-frozen objects; change no envelope.

    The Writer computes ordinary content-addressed Refs using the arm's public
    canonical JSON encoding. Root freezes its full response and object files
    first. This function never fills changed layers, diff, prose or a Ref.
    """
    from deck_master import models, content_production, tasks
    from deck_master.content import check_page
    from deck_master.models import canonical_json_bytes
    invocation, target, envelope, proof = observed_result(journal, stage, ordinal)
    objects = proof.get("native_objects") or []
    if envelope.get("variant") != "input_revision" or not objects:
        raise CampaignError("only an actual input_revision with frozen native proposal objects uses this step")
    store = store_for(state)
    document = store.load_document()
    dispatch = read(target.parent.parent / "dispatch.json")
    task = task_for(store, dispatch["task_id"])
    content_production.parse_compose_v2(envelope)
    if (task["kind"] != "compose" or task.get("intent") != "input_revision"
            or content_production.expected_variant(task) != "input_revision"
            or task["status"] != "running" or task.get("execution_ref") != invocation["executor"]
            or not tasks.task_inputs_current(store, document, task)
            or envelope.get("task_id") != task["task_id"] or envelope.get("operation_id") != task["operation_id"]
            or envelope.get("produced_against") != task["produced_against"]
            or envelope.get("eligibility_digest") != (task.get("collaboration_binding") or {}).get("eligibility_digest")):
        raise CampaignError("native objects require the exact claimed current input_revision Task and unchanged envelope binding")
    proposals = envelope.get("payload", {}).get("proposals", [])
    declared = [proposal.get("ref") for proposal in proposals]
    if any(not isinstance(ref, dict) or set(ref) != {"path", "sha256"} for ref in declared):
        raise CampaignError("each native proposal declares its complete canonical Ref")
    if len({(ref["path"], ref["sha256"]) for ref in declared}) != len(declared):
        raise CampaignError("duplicate native proposal Refs are ambiguous")
    pending, seen = [], set()
    for item in objects:
        check_ref(item["frozen"])
        obj = read(item["frozen"]["path"])
        hashed = digest(canonical_json_bytes(obj))
        expected = {"path": f".deckmaster/objects/{hashed[:2]}/{hashed}.json", "sha256": hashed}
        if expected != item["declared_ref"] or expected not in declared or hashed in seen:
            raise CampaignError("native object, own canonical Ref and unchanged formal proposal Ref disagree")
        seen.add(hashed)
        pending.append((obj, expected, item["frozen"]))
    revision = store.current_revision_id()
    prepared = {ref["sha256"]: obj for obj, ref, _ in pending}
    for proposal in proposals:
        ref = proposal["ref"]
        try:
            obj = prepared[ref["sha256"]] if ref["sha256"] in prepared else store.read_object_json(ref)
        except Exception as exc:
            raise CampaignError("missing native sidecar or proposal Ref outside this actual Store") from exc
        layer = proposal.get("layer")
        canonical = digest(canonical_json_bytes(obj))
        if ref != {"path": f".deckmaster/objects/{canonical[:2]}/{canonical}.json", "sha256": canonical}:
            raise CampaignError("formal proposal has a noncanonical or foreign object Ref")
        if layer == "narrative":
            models.validate_narrative_semantics(obj)
            if obj["project_id"] != store.load_document()["project_id"]:
                raise CampaignError("native Narrative belongs to another project")
        elif layer == "plan":
            if obj.get("schema_version") == "content_plan.v2":
                models.validate_content_plan_semantics(obj)
                if obj["project_id"] != store.load_document()["project_id"]:
                    raise CampaignError("native Plan belongs to another project")
            else:
                models.validate_schema("content_plan_input", obj)
        elif layer in {"page_copy", "speech"}:
            check_page(obj)
        else:
            raise CampaignError("unknown native proposal layer")
    # Every byte/ref/set/type check above finishes before the first Store put.
    # An I/O interruption can leave immutable orphan objects, never a current
    # manuscript adoption; its unresolved intent requires real reconciliation.
    results = []
    for obj, expected, frozen in pending:
        actual = record_sdk(journal, "Store.put_json_object.exact_frozen_native_proposal", {"ordinal": ordinal,
                           "raw_object": frozen, "native_declared_ref": expected}, lambda: store.put_json_object(obj))
        if actual != expected or store.current_revision_id() != revision:
            raise CampaignError("proposal materialization changed canonical identity or current Document")
        results.append(actual)
    journal.append("native_objects_materialized", {"ordinal": ordinal, "refs": results, "semantic_wrapping": False})
    return {"status": "exact_native_objects_stored", "refs": results, "current_revision_unchanged": True}


def bootstrap(path):
    raw = Path(path).read_bytes()
    record = json.loads(raw)
    if (record.get("observation_kind") != OBSERVER_KIND or record.get("assurance") != "host_attested"
            or record.get("tool") != "collaboration.list_agents"
            or "/root" not in record.get("observed_running_agents", [])):
        raise CampaignError("Root must supply its actual live native channel observation")
    fresh(record["observed_at_utc"])
    return raw


class NativeProvider:
    """Trusted Root bootstrap, not a provider selected by project/output JSON."""
    provider_id = PROVIDER_ID
    adapter_version = VERSION
    authentication = "protected_transport"
    channels = (CHANNEL,)

    def __init__(self, path, raw=None, claims=None):
        self.path, self.bootstrap_raw = Path(path), bootstrap(path)
        self.raw, self.claims = raw, claims

    def health(self):
        try:
            return bootstrap(self.path) == self.bootstrap_raw
        except (OSError, KeyError, ValueError):
            return False

    def fetch(self, event_id):
        if self.claims is None or self.raw is None or event_id != self.claims["event_id"]:
            raise CampaignError("no actual native completion registered")
        return self.raw

    def verify(self, raw):
        if self.claims is None or self.raw is None or raw != self.raw:
            raise CampaignError("not the exact actual Root-observed completion")
        return deepcopy(self.claims)


@contextmanager
def native_runtime(path, raw=None, claims=None):
    from deck_master import review_evidence
    registry = review_evidence.ProviderRegistry()
    registry.register(NativeProvider(path, raw, claims))
    with review_evidence.ProviderRuntime(registry).bound():
        yield registry


def review_prepare(journal, state, config, stage, role, bootstrap_path):
    from deck_master import content_review
    if role not in {"feedback", "verification"}:
        raise CampaignError("choose feedback or separate read-only verification")
    if role == "feedback" and any(e["kind"] == "feedback_delivered" for e in journal.events()):
        raise CampaignError("only one substantive feedback may be delivered to Writer")
    if role == "feedback" and any(not (journal.root / "snapshots" / (name + ".json")).exists()
                                  for name in ("original_complete", "first_sdk_complete")):
        raise CampaignError("freeze native complete draft and first SDK-accepted complete draft before feedback")
    if role == "verification" and not any(e["kind"] == "repair_begun" for e in journal.events()):
        raise CampaignError("verification is separate post-repair work; no artificial repair")
    if config["installations"][state["arm"]].get("adapter_profile") == "A0-public-legacy":
        # Observe A0's own entry and blocker; never import the new bridge into
        # the older process or upgrade its native policy/assurance.
        outcome = record_sdk(journal, "content_review.dispatch_preproduction_review.A0-original", {},
            lambda: content_review.dispatch_preproduction_review(state["project"]))
    else:
        with native_runtime(bootstrap_path) as registry:
            outcome = record_sdk(journal, "content_review.dispatch_preproduction_review", {"bootstrap": reference(bootstrap_path)},
                lambda: content_review.dispatch_preproduction_review(state["project"], adapter_context=registry.channel_context()))
    journal.append("review_dispatch", {"role": role, "actual_result": outcome, "bootstrap": reference(bootstrap_path)})
    if outcome["status"] != "review_dispatched":
        return outcome
    result = prepare(journal, state, config, stage, outcome["task"]["task_id"], role)
    store = store_for(state)
    save(Path(result["packet"]) / "review-packet.json", store.read_object_json(outcome["review_draft_ref"]))
    save(Path(result["packet"]) / "review-dispatch.json", outcome)
    return result


def review_accept(journal, state, stage, ordinal, bootstrap_path):
    if importlib.util.find_spec("deck_master.review_evidence") is None:
        raise CampaignError("this original Runtime has no protected native review bridge; preserve its actual legacy review/blocker separately")
    from deck_master import content_review, review_evidence, service
    invocation, target, envelope, proof = observed_result(journal, stage, ordinal)
    if invocation["role"] not in {"feedback", "verification"}:
        raise CampaignError("native execution was not registered as an independent review")
    dispatch = read(target.parent.parent / "dispatch.json")
    store = store_for(state)
    task = task_for(store, dispatch["task_id"])
    binding = review_evidence.review_binding(store, store.load_document(), task, envelope)
    authors = {e["data"]["executor"] for e in journal.events() if e["kind"] == "native_begun"
               and e["data"]["role"] in WRITER_ROLES}
    if invocation["executor"] in authors or not set(binding["author_execution_refs"]) <= authors:
        raise CampaignError("actual authors must be observed; reviewer must be independent of all authors")
    issued = datetime.now(timezone.utc)
    observation_raw = Path(proof["observation"]["path"]).read_bytes()
    claims = {**binding, "provider_id": PROVIDER_ID, "event_id": "native-" + digest(observation_raw)[:40],
              "channel": CHANNEL, "issued_at": issued.isoformat(), "expires_at": (issued + timedelta(minutes=30)).isoformat(),
              "executor_ref": invocation["executor"], "reviewer_id": invocation["executor"],
              "assurance": "host_attested", "observation_kind": OBSERVER_KIND,
              "model_output_bytes_sha256": proof["raw"]["sha256"], "all_native_writer_execution_refs": sorted(authors),
              "evidence_scope": "actual synthetic campaign native review; not human or professional evidence"}
    before = store.load_document()
    protected = {k: deepcopy(before.get(k)) for k in ("narrative", "content_plan", "pages", "files", "design_context", "outputs")}
    try:
        with native_runtime(bootstrap_path, observation_raw, claims) as registry:
            context = registry.review_context(store, before, task, envelope, {"provider_id": PROVIDER_ID, "event_id": claims["event_id"]})
            arguments = {"task_id": task["task_id"], "operation_id": task["operation_id"],
                         "produced_against": task["produced_against"], "result_payload": envelope}
            outcome = record_sdk(journal, "service.accept_result.independent_review", arguments,
                lambda: service.accept_result(state["project"], **arguments, adapter_context=context))
    except Exception as exc:
        journal.append("result_refused", {"ordinal": ordinal, "raw": proof["raw"], "error_type": type(exc).__name__, "error": str(exc)})
        raise
    after = store.load_document()
    if {k: after.get(k) for k in protected} != protected:
        raise CampaignError("read-only review changed content or production")
    gate = content_review.preproduction_status(store, after)
    data = {"ordinal": ordinal, "role": invocation["role"], "task_id": task["task_id"], "raw": proof["raw"],
            "executor": invocation["executor"], "outcome": outcome, "current_gate": gate, "binding": binding}
    journal.append("result_accepted", data)
    return data


def deliver_feedback(journal, stage, ordinal):
    invocation, target, envelope, proof = observed_result_for_feedback(journal, stage, ordinal)
    if any(e["kind"] == "feedback_delivered" for e in journal.events()):
        raise CampaignError("the single feedback has already been frozen/delivered")
    data = {"ordinal": ordinal, "executor": invocation["executor"], "feedback_raw": proof["raw"],
            "actual_reviews": [{"review_id": r.get("review_id"), "findings": r.get("findings", []),
                                "status": r.get("status")} for r in envelope["reviews"]]}
    journal.append("feedback_delivered", data)
    return data


def observed_result_for_feedback(journal, stage, ordinal):
    invocation, target = execution(journal, stage, ordinal)
    proof = read(target / "observed.json")
    check_ref(proof["raw"])
    if invocation["role"] != "feedback" or not invocation["within_budget"]:
        raise CampaignError("only the within-budget independent feedback can be delivered")
    if not any(e["kind"] == "result_accepted" and e["data"]["ordinal"] == ordinal for e in journal.events()):
        raise CampaignError("feedback must have an actual formal review acceptance")
    return invocation, target, read(proof["raw"]["path"]), proof


def repair_begin(journal, necessity_path):
    events = journal.events()
    feedbacks = [e["data"] for e in events if e["kind"] == "feedback_delivered"]
    if len(feedbacks) != 1 or any(e["kind"] == "repair_begun" for e in events):
        raise CampaignError("one feedback, at most one autonomous repair cycle")
    record = read(necessity_path)
    layers = record.get("necessary_layers", [])
    if (not layers or len(layers) > 3 or len(set(layers)) != len(layers)
            or any(x not in {"argument", "page_copy", "speech"} for x in layers)
            or not record.get("actual_review_finding_refs")):
        raise CampaignError("declare only necessary layers, with actual finding references")
    if not any(r.get("findings") or r.get("status") != "pass" for r in feedbacks[0]["actual_reviews"]):
        raise CampaignError("no actual defect; do not manufacture a repair")
    valid_ids = {f.get("finding_id") or f.get("id") for r in feedbacks[0]["actual_reviews"] for f in r["findings"]}
    if not set(record["actual_review_finding_refs"]) <= valid_ids:
        raise CampaignError("repair necessity cites findings outside the single real feedback")
    data = {**record, "necessity_record": reference(necessity_path), "feedback_raw": feedbacks[0]["feedback_raw"],
            "repair_cycle": 1, "new_facts": False, "new_feedback": False}
    journal.append("repair_begun", data)
    return data


def scripted_event(journal, state, config, event_id, trigger_path):
    """Release exact preregistered bytes only after a Root-observed real trigger.

    Trigger interpretation is explicit host attestation, not a keyword test.
    Formal SDK inputs/requests remain separate recorded public operations.
    """
    event_id = safe_name(event_id)
    event = config["cases"][state["case"]]["events"][event_id]
    if event.get("planned_dispatch") is not True:
        raise CampaignError("event was not authorized for planned dispatch")
    check_ref(event["message"])
    trigger = read(trigger_path)
    if (trigger.get("event_id") != event_id or trigger.get("assurance") != "host_attested"
            or trigger.get("actual_trigger_satisfied") is not True
            or not trigger.get("actual_trigger_explanation") or not trigger.get("source_observations")):
        raise CampaignError("actual trigger and source observation references are required")
    for ref in trigger["source_observations"]:
        check_ref(ref)
    for name in event.get("required_snapshots", []):
        if not (journal.root / "snapshots" / (safe_name(name) + ".json")).exists():
            raise CampaignError("scripted event is premature: " + name)
    if any(e["kind"] == "scripted_event" and e["data"]["event_id"] == event_id for e in journal.events()):
        raise CampaignError("scripted event already released; record a repeated question separately")
    raw = Path(event["message"]["path"]).read_bytes()
    ref = write_once(journal.root / "messages" / (event_id + ".txt"), raw)
    data = {"event_id": event_id, "message": ref, "trigger": reference(trigger_path),
            "source": event["source"], "kind": "scripted experiment message; not human receipt"}
    journal.append("scripted_event", data)
    return {**data, "text": raw.decode("utf-8")}


def materialize_instruction(journal, state, event_id):
    events = [e["data"] for e in journal.events() if e["kind"] == "scripted_event" and e["data"]["event_id"] == event_id]
    if len(events) != 1:
        raise CampaignError("only a genuinely triggered, released preregistered message may become instruction evidence")
    message = events[0]["message"]
    check_ref(message)
    store = store_for(state)
    ref = record_sdk(journal, "Store.put_blob.exact_scripted_instruction", {"event_id": event_id, "original_message": message},
                     lambda: store.put_blob(Path(message["path"]).read_bytes(), ext="txt"))
    evidence = {"kind": "host_attested_instruction", "source_ref": ref, "source_locator": "scripted-event:" + event_id,
                "actor_id": "synthetic-scripted-controller-not-human", "transport_receipt_ref": None, "presentation_ref": None}
    journal.append("scripted_instruction_materialized", {"event_id": event_id, "instruction_evidence": evidence})
    return evidence


def snapshot(journal, state, name, *, native_manifest=None):
    from deck_master import content_review
    safe_name(name)
    if name not in SNAPSHOTS:
        raise CampaignError("unregistered manuscript timepoint")
    if name == "original_complete":
        if native_manifest is None:
            raise CampaignError("original_complete needs the actual native complete-draft manifest; Store is not the raw draft")
        manifest = read(native_manifest)
        originals = {e["data"]["ordinal"]: e["data"] for e in journal.events() if e["kind"] == "native_output_frozen"}
        selected = manifest.get("raw_stage_ordinals", [])
        if (manifest.get("format") != "rc3-native-complete-draft-manifest.v1"
                or manifest.get("complete_native_manuscript_observed") is not True
                or manifest.get("assurance") != "host_attested" or not selected
                or len(selected) != len(set(selected)) or not set(selected) <= set(originals)
                or any(e["kind"] == "feedback_delivered" for e in journal.events())):
            raise CampaignError("invalid/premature native complete-draft observation")
        for ordinal in selected:
            check_ref(originals[ordinal]["raw"])
            check_ref(originals[ordinal]["observation"])
        source = manifest["completeness_source_observation"]
        check_ref(source)
        if source["sha256"] not in {originals[n]["observation"]["sha256"] for n in selected}:
            raise CampaignError("completeness observation is not one of the exact frozen native completions")
        if manifest.get("readonly_conversion") is not None:
            check_ref(manifest["readonly_conversion"])
        data = {"format": "rc3-campaign-original-native-snapshot.v1", "timepoint": name, "frozen_at": now(),
                "native_complete_manifest": reference(native_manifest), "native_originals": [originals[n] for n in selected],
                "readonly_conversion": manifest.get("readonly_conversion"),
                "sdk_outcomes_separate": [e for e in journal.events() if e["kind"] in {"result_accepted", "result_refused"}],
                "human_owner_acceptance": "NOT_RUN_USER_DEFERRED", "professional": "not_asserted"}
        ref = save(journal.root / "snapshots" / (name + ".json"), data)
        journal.append("snapshot_frozen", {"name": name, "snapshot": ref, "sdk_acceptance_implied": False})
        return ref
    store = store_for(state)
    gate = content_review.preproduction_status(store, store.load_document())
    if name in {"equal_budget_evaluated", "qualified_for_owner"} and any(
            e["kind"] == "native_begun" and e["data"]["role"] in {"extra_writer", "post_comparison_writer"}
            for e in journal.events()):
        raise CampaignError("post-comparison/extra writing cannot become an equal-budget snapshot")
    if name == "qualified_for_owner":
        if gate.get("status") != "pass" or gate.get("missing_units") or gate.get("blocking_findings"):
            raise CampaignError("current central preproduction gate has not passed")
        if any(e["kind"] == "repair_begun" for e in journal.events()):
            if not any(e["kind"] == "result_accepted" and e["data"].get("role") == "verification" for e in journal.events()):
                raise CampaignError("post-repair independent currentness/explicit finding-closure verification is missing")
        if any(e["kind"] == "native_begun" and not e["data"]["within_budget"] for e in journal.events()):
            raise CampaignError("over-budget execution cannot become the equal-budget qualified manuscript")
    data = {"format": "rc3-campaign-manuscript-snapshot.v1", "timepoint": name, "frozen_at": now(),
            "manuscript": current_manuscript(store), "current_preproduction_gate": gate,
            "native_originals": [e["data"] for e in journal.events() if e["kind"] == "native_output_frozen"],
            "human_owner_acceptance": "NOT_RUN_USER_DEFERRED", "professional": "not_asserted"}
    ref = save(journal.root / "snapshots" / (name + ".json"), data)
    journal.append("snapshot_frozen", {"name": name, "snapshot": ref, "current_gate": gate})
    return ref


def reconcile(journal, record_path):
    """Close an interrupted intent only using explicit Runtime observation.

    This never resends the command. A not_found receipt permits a separately
    recorded public retry; original intent and observation remain unchanged.
    """
    record = read(record_path)
    pending = journal.unfinished()
    key = record["operation_key"]
    if key not in pending or record.get("observed_state") not in {"committed", "not_found", "unknown"}:
        raise CampaignError("reconciliation must refer to an unresolved actual intent")
    if not record.get("runtime_observations"):
        raise CampaignError("actual operations query/current-state observation is required")
    for ref in record["runtime_observations"]:
        check_ref(ref)
    if record["observed_state"] == "unknown":
        journal.append("sdk_reconciliation_unknown", {**record, "record": reference(record_path)})
        return {"status": "still_unresolved"}
    journal.append("sdk_reconciliation", {**record, "record": reference(record_path), "automatic_retry": False})
    return {"status": "recorded_no_retry", "observed_state": record["observed_state"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze-campaign")
    freeze.add_argument("--registration", required=True); freeze.add_argument("--out", required=True)
    init = sub.add_parser("init")
    for key in ("campaign", "out", "arm", "case", "project"):
        init.add_argument("--" + key, required=True)
    init.add_argument("--repetition", type=int, default=1)
    for command in ("public-operation", "prepare", "begin-native", "claim-read", "observe", "accept", "materialize-native-objects",
                    "review-prepare", "review-accept", "deliver-feedback", "repair-begin", "scripted-event", "materialize-instruction", "snapshot", "reconcile", "declare-extra", "status"):
        p = sub.add_parser(command); p.add_argument("--run", required=True)
        if command in {"prepare", "begin-native", "claim-read", "observe", "accept", "materialize-native-objects", "review-prepare", "review-accept", "deliver-feedback"}:
            p.add_argument("--stage", required=True)
        if command in {"claim-read", "observe", "accept", "materialize-native-objects", "review-accept", "deliver-feedback"}:
            p.add_argument("--ordinal", type=int, required=True)
        if command == "public-operation":
            p.add_argument("--operation", required=True); p.add_argument("--arguments", required=True)
            p.add_argument("--evidence"); p.add_argument("--operation-key")
        if command == "prepare":
            p.add_argument("--task-id", required=True); p.add_argument("--role", choices=sorted(ROLES), required=True)
        if command == "begin-native": p.add_argument("--invocation", required=True)
        if command == "claim-read": p.add_argument("--executor", required=True)
        if command == "observe":
            for key in ("result", "result-sha256", "observation", "observation-sha256"):
                p.add_argument("--" + key, required=True)
        if command == "review-prepare": p.add_argument("--role", choices=["feedback", "verification"], required=True)
        if command in {"review-prepare", "review-accept"}: p.add_argument("--bootstrap", required=True)
        if command == "repair-begin": p.add_argument("--necessity", required=True)
        if command == "scripted-event":
            p.add_argument("--event-id", required=True); p.add_argument("--trigger", required=True)
        if command == "materialize-instruction": p.add_argument("--event-id", required=True)
        if command == "snapshot":
            p.add_argument("--name", choices=sorted(SNAPSHOTS), required=True)
            p.add_argument("--native-manifest")
        if command == "reconcile": p.add_argument("--record", required=True)
        if command == "declare-extra": p.add_argument("--evidence", required=True)
    args = parser.parse_args()
    if args.command == "freeze-campaign":
        result = freeze_registration(args.registration, args.out)
    elif args.command == "init":
        result = init_run(args.campaign, args.out, args.arm, args.case, args.repetition, args.project)
    else:
        journal, state, config = load_run(args.run)
        with journal.locked():
            if journal.unfinished() and args.command not in {"status", "reconcile"}:
                raise CampaignError("SDK outcome unresolved; status/reconcile only until actual Runtime observation")
            if args.command == "public-operation":
                result = sdk_operation(journal, state, args.operation, read(args.arguments),
                    evidence=reference(args.evidence) if args.evidence else None, operation_key=args.operation_key)
            elif args.command == "prepare": result = prepare(journal, state, config, args.stage, args.task_id, args.role)
            elif args.command == "begin-native": result = begin_native(journal, state, config, args.stage, args.invocation)
            elif args.command == "claim-read": result = claim_read(journal, state, args.stage, args.ordinal, args.executor)
            elif args.command == "observe":
                result = observe(journal, state, args.stage, args.ordinal, args.result, args.result_sha256,
                                 args.observation, args.observation_sha256)
            elif args.command == "accept": result = accept(journal, state, args.stage, args.ordinal)
            elif args.command == "materialize-native-objects": result = materialize_native_objects(journal, state, args.stage, args.ordinal)
            elif args.command == "review-prepare": result = review_prepare(journal, state, config, args.stage, args.role, args.bootstrap)
            elif args.command == "review-accept": result = review_accept(journal, state, args.stage, args.ordinal, args.bootstrap)
            elif args.command == "deliver-feedback": result = deliver_feedback(journal, args.stage, args.ordinal)
            elif args.command == "repair-begin": result = repair_begin(journal, args.necessity)
            elif args.command == "scripted-event": result = scripted_event(journal, state, config, args.event_id, args.trigger)
            elif args.command == "materialize-instruction": result = materialize_instruction(journal, state, args.event_id)
            elif args.command == "snapshot": result = snapshot(journal, state, args.name, native_manifest=args.native_manifest)
            elif args.command == "reconcile": result = reconcile(journal, args.record)
            elif args.command == "declare-extra":
                result = journal.append("extra_work_begun", {"evidence": reference(args.evidence),
                    "comparison_budget": "excluded", "original_timepoints_preserved": True})
            elif args.command == "status":
                result = {"workflow": state, "unfinished_operations": journal.unfinished(), "events": journal.events(),
                          "actual_current": current_manuscript(store_for(state))}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
