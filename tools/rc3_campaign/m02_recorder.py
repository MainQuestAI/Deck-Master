#!/usr/bin/env python3
"""One sequential M02 SDK/native experiment; never a generator or admission claim.

Independent registration, finite preregistered scope, one current project. Root
performs native/model/image calls. Reused d0 helpers are pinned, not patched.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import hashlib
from pathlib import Path
import sys

COMMON_SHA = "d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261"
IMAGE_SHA = "bf3998cfb8e8bd0f3aaafb743859fac42dc355a282c5ecab07045877767a33f7"
PHASES = ("common", "live", "read", "live_notes_edit")
ROLES = ("initial_writer", "repair_writer", "feedback", "verification", "production", "production_review")
SOURCE = Path(__file__).with_name("controller.py")
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != COMMON_SHA:
    raise RuntimeError("frozen d0 helper changed; refuse before executing it")
_spec = importlib.util.spec_from_file_location("rc3_m02_pinned_common", SOURCE)
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)
Error = c.CampaignError
FORMAT = "rc3-m02-registration.v1"
ENGINEERING = "ENGINEERING_ONLY_NOT_ADMITTED"


def require(condition, message):
    if not condition:
        raise Error(message)


def ref_key(ref):
    return (ref.get("path"), ref.get("sha256")) if isinstance(ref, dict) else None



def image_helper(config):
    path = Path(__file__).with_name("image_controller.py")
    require(config["image_controller"]["sha256"] == IMAGE_SHA and Path(config["image_controller"]["path"]).resolve() == path.resolve(), "pin actual frozen image-budget helper")
    require(c.digest(path.read_bytes()) == IMAGE_SHA, "frozen image helper changed")
    spec = importlib.util.spec_from_file_location("rc3_m02_image_budget_helper", path)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    return helper


def validate(config):
    require(config.get("format") == FORMAT and config.get("status") in {"ADMITTED", ENGINEERING}, "separate reviewed M02 registration required")
    require(c.digest(SOURCE.read_bytes()) == COMMON_SHA, "frozen d0 common helper changed")
    require(config.get("recorder_sha256") == c.digest(Path(__file__).read_bytes()), "M02 recorder identity changed")
    require(config["common"]["sha256"] == COMMON_SHA and Path(config["common"]["path"]).resolve() == SOURCE.resolve(), "pin the actual sibling d0 helper")
    for key in ("common", "protocol", "admission_review", "exposure_registry", "grammar", "global_image_budget", "image_controller"):
        c.check_ref(config[key])
    for ref in config["technical_supplements"] + config["materials"]:
        c.check_ref(ref)
    require(set(config["create_arguments"]) <= {"title", "audience", "scenario", "presentation_mode", "page_limit"} and config["create_arguments"].get("presentation_mode") == "mixed", "preregister actual common task facts, no imported semantic objects")
    require(config["materials"] and len({ref["path"] for ref in config["materials"]}) == len(config["materials"]), "fixed nonempty distinct material set required")
    exposure = c.read(config["exposure_registry"]["path"])
    require(exposure.get("status") == "FROZEN" and exposure.get("excluded_identities"), "freeze actual exposure/author exclusions")
    require(set(config["scopes"]) == set(PHASES), "register common/live/read/notes-edit scopes, not GENTRY/E1 aliases")
    for phase in PHASES:
        scope = config["scopes"][phase]
        c.check_ref(scope["instruction"])
        require(set(scope["native_limits"]) == set(ROLES) and all(type(v) is int and v >= 0 for v in scope["native_limits"].values()), "explicit finite native ceilings per scope; no E1 defaults")
        require(type(scope["max_external_calls"]) is int and scope["max_external_calls"] >= 0, "finite production ceiling required")
        require(type(scope["max_candidates"]) is int and scope["max_candidates"] >= 0, "finite candidate ceiling required")
        ids = scope["page_ids"]
        require(isinstance(ids, list) and len(ids) == len(set(ids)) and all(isinstance(x, str) and x for x in ids), "distinct registered Page IDs")
    require(config["scopes"]["live"]["page_ids"] and config["scopes"]["read"]["page_ids"] and not set(config["scopes"]["live"]["page_ids"]) & set(config["scopes"]["read"]["page_ids"]), "register distinct stable live/read Page sets in one whole run before first output")
    require(config["scopes"]["common"]["page_ids"] == [], "common scope fixes only the shared Narrative before Pages")
    require(config["scopes"]["common"]["max_external_calls"] == config["scopes"]["live_notes_edit"]["max_external_calls"] == 0, "common and notes edit have zero image budget")
    require(len(config["scopes"]["live_notes_edit"]["page_ids"]) == 1 and set(config["scopes"]["live_notes_edit"]["page_ids"]) <= set(config["scopes"]["live"]["page_ids"]), "notes edit selects one declared live Page")
    require(config["scopes"]["live"]["notes_policy"] == "both" and config["scopes"]["read"]["notes_policy"] == "pure_reading", "freeze requested export/notes combinations")
    for use in ("live", "read"):
        patch = config["scopes"][use]["input_patch"]
        # A variant request + explicit Plan policy is a use change, not a new
        # global task fact. Optional real fact changes retain Runtime barriers.
        require(patch is None or (set(patch) == {"reason", "task_patch"} and set(patch["task_patch"]) <= {"presentation_mode", "brief"}), "only optional preregistered actual task-fact events")
        if patch and "brief" in patch["task_patch"]: require(patch["task_patch"]["brief"] == Path(config["scopes"][use]["instruction"]["path"]).read_text(), "actual exact preregistered use instruction only")
    budget = c.read(config["global_image_budget"]["path"])
    image = image_helper(config)
    image.validate_global_budget(budget)
    require(budget.get("status") == ("ADMITTED" if config["status"] == "ADMITTED" else image.ENGINEERING), "M02/image admission scopes cannot mix")
    require(Path(budget["ledger_root"]).is_absolute() and str(Path(budget["ledger_root"]).resolve()) == budget["ledger_root"], "pin one canonical shared image ledger")
    for phase in ("live", "read"):
        allowed = {(r["case"], r["whole_run_id"], r["repetition"], r["arm"], r["page_id"]) for r in budget["allowed_page_arms"]}
        scope = config["scopes"][phase]
        wanted = {("M02", config["experiment_id"], 1, "B", pid) for pid in scope["page_ids"]}
        require(wanted <= allowed, "M02 complete-version Pages must be in original shared global image scope")
    own_rows = {row["page_id"] for row in budget["allowed_page_arms"] if (row["case"], row["whole_run_id"], row["repetition"], row["arm"]) == ("M02", config["experiment_id"], 1, "B")}
    require(own_rows == set(config["scopes"]["live"]["page_ids"] + config["scopes"]["read"]["page_ids"]), "shared M02 budget may not hide extra Pages or another whole-run alias")
    own_cap = [row["max_calls"] for row in budget["workflow_arm_caps"] if (row["case"], row["whole_run_id"], row["repetition"], row["arm"]) == ("M02", config["experiment_id"], 1, "B")]
    require(own_cap == [sum(config["scopes"][p]["max_external_calls"] for p in ("live", "read"))], "shared M02 workflow cap must equal both fixed use ceilings")
    if config["status"] == "ADMITTED":
        require(config["common_review"]["sha256"] == "204242f6a4e0d9fef878d1b2a936176583e2b71061eb7f6fab200719e59c823b", "M02 admission depends on exact d0 R4 limited review, not a reused old head")
        c.check_ref(config["common_review"])
        require("7075da738d5681dfe2431208d09e29dbe8a5257f47c36e244d9bca66cc0dd246" in {r["sha256"] for r in config["technical_supplements"]}, "dispatch the actual current public layer rules to future Authors")
        for name in ("G04", "GID", "GADAPTER", "M02_NATIVE", "IMAGE_NATIVE", "M02_SCOPE"):
            require(config["gates"][name]["status"] == "PASS", "actual M02 prerequisite pending: " + name)
            c.check_ref(config["gates"][name]["evidence"])
    c.safe_name(config["experiment_id"])
    return config


def freeze(registration, root):
    config = validate(c.read(registration))
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=False)
    c.save(root / "registration.json", config)
    c.save(root / "origin.json", c.reference(registration))
    return {"campaign": str(root), "scope": config["status"], "models": 0}


def init(campaign, root, project):
    config = validate(c.read(Path(campaign) / "registration.json"))
    c.installation({"installations": {"B": config["installation"]}}, "B")
    root, project = Path(root).resolve(), Path(project).resolve()
    require(not project.exists(), "M02 uses a new separately authorized project, never edits active GENTRY")
    root.mkdir(parents=True, exist_ok=False)
    state = {"format": "rc3-m02-run.v1", "campaign": str(Path(campaign).resolve()), "project": str(project),
             "experiment_id": config["experiment_id"], "registration_sha256": c.digest(c.encoded(config)),
             "arm": "B", "case": "M02", "materials": config["materials"],
             "budget": {role: sum(config["scopes"][p]["native_limits"][role] for p in PHASES) for role in ROLES},
             "human": "NOT_RUN_USER_DEFERRED", "comparison_credit": "NOT_E1_NOT_ORIGINAL12"}
    c.save(root / "run.json", state)
    journal = c.Journal(root); journal.append("m02_initialized", state)
    journal.append("m02_phase_started", {"phase": "common"})
    return state


def phase(journal):
    return [e["data"]["phase"] for e in journal.events() if e["kind"] == "m02_phase_started"][-1]


def events(journal, kind, scope=None):
    return [e["data"] for e in journal.events() if e["kind"] == kind and (scope is None or e["data"].get("phase") == scope)]


def fixed(journal):
    rows = events(journal, "m02_narrative_fixed")
    require(len(rows) == 1, "fix one actual adopted shared Narrative before variant work")
    return rows[0]


def preserved(journal):
    for record in events(journal, "m02_version_exported"):
        root = Path(record["export_root"])
        actual = {p.relative_to(root).as_posix(): c.reference(p)["sha256"] for p in root.rglob("*") if p.is_file()}
        require(actual == record["export_tree"], "an immutable earlier export tree changed")
        if record.get("output_copy_root"):
            copy_root = Path(record["output_copy_root"])
            copy_tree = {p.relative_to(copy_root).as_posix(): c.reference(p)["sha256"] for p in copy_root.rglob("*") if p.is_file()}
            require(copy_tree == record["output_copy_tree"], "an original exported copy changed")


def guard(journal, state, config):
    preserved(journal)
    if not Path(state["project"]).exists():
        return
    store = c.store_for(state); doc = store.load_document()
    bound = events(journal, "m02_project_bound")
    if not bound:
        require(journal.unfinished(), "actual created project needs binding or real recovery observation")
        return
    require(doc["project_id"] == bound[0]["project_id"], "actual project identity changed")
    require(sorted(s["original_sha256"] for s in doc["sources"]) == sorted(r["sha256"] for r in config["materials"]), "actual stored material identity changed")
    if events(journal, "m02_narrative_fixed"):
        locked = fixed(journal)
        require(doc.get("narrative") == locked["narrative_ref"], "fixed shared Narrative changed")
        require(doc["sources"] == locked["sources"], "fixed source/project dependencies changed")


def load(root):
    journal = c.Journal(root); state = c.read(journal.root / "run.json")
    config = validate(c.read(Path(state["campaign"]) / "registration.json"))
    require(c.digest(c.encoded(config)) == state["registration_sha256"], "registration changed after init")
    require(journal.events()[0]["kind"] == "m02_initialized" and journal.events()[0]["data"] == state, "immutable M02 run identity changed")
    c.installation({"installations": {"B": config["installation"]}}, "B")
    guard(journal, state, config)
    return journal, state, config


def helper_config(config):
    return {"installations": {"B": config["installation"]}, "grammar": config["grammar"], "exposure_registry": config["exposure_registry"]}


def instruction(journal, state, config, scope, trigger_path):
    require(scope in PHASES and not events(journal, "m02_instruction", scope), "one exact preregistered instruction event per scope")
    trigger = c.read(trigger_path)
    require(trigger.get("assurance") == "host_attested" and trigger.get("actual_trigger_satisfied") is True and trigger.get("source_observations"), "Root actual trigger observations required")
    for ref in trigger["source_observations"]: c.check_ref(ref)
    if scope != "common": fixed(journal)
    if scope == "read": require(events(journal, "m02_version_exported", "live"), "read event follows actual complete live export")
    if scope == "live_notes_edit": require(events(journal, "m02_version_exported", "read"), "local edit follows both immutable exports")
    message = config["scopes"][scope]["instruction"]; c.check_ref(message)
    raw = c.write_once(journal.root / "instructions" / (scope + ".txt"), Path(message["path"]).read_bytes())
    journal.append("m02_instruction", {"phase": scope, "message": raw, "trigger": c.reference(trigger_path), "human": False})
    return raw


def instruction_evidence(journal, state, scope):
    rows = events(journal, "m02_instruction", scope); require(len(rows) == 1, "release the actual preregistered instruction first")
    raw = rows[0]["message"]; c.check_ref(raw)
    ref = c.record_sdk(journal, "Store.put_blob.exact_m02_instruction", {"message": raw},
                       lambda: c.store_for(state).put_blob(Path(raw["path"]).read_bytes(), ext="txt"))
    result = {"kind": "host_attested_instruction", "source_ref": ref, "source_locator": "m02-synthetic:" + scope,
              "actor_id": "synthetic-controller-not-human", "transport_receipt_ref": None, "presentation_ref": None}
    journal.append("m02_instruction_evidence", {"phase": scope, "evidence": result})
    return result


def check_evidence(journal, value, scope):
    require(any(r["evidence"] == value for r in events(journal, "m02_instruction_evidence", scope)), "actual exact synthetic instruction evidence required; no Owner/human claim")


def scope_check(value, registered, *, notes=False):
    require(isinstance(value, dict), "actual bounded scope required")
    require(set(value.get("page_ids") or []) <= set(registered["page_ids"]), "Page scope exceeds preregistration")
    require(not notes or (value.get("page_ids") == registered["page_ids"] and set(value.get("layers") or []) == {"speech"}
                         and not value.get("allow_page_membership_change") and not value.get("allow_page_order_change")), "notes edit must be exactly one live Page/speech-only scope")


def operate(journal, state, config, operation, arguments):
    require(operation in c.PUBLIC_OPERATIONS | {"pipeline.preview_svg_page", "stages.assemble", "exports.show", "exports.download", "handoff.check_handoff"}, "public operation is not exposed by scoped M02 recorder")
    require(operation not in {"collaboration.start_request", "editing.export_project", "service.import_draft", "service.preview_draft_import"}, "use scoped variant/export commands; no manuscript import bypass")
    current = phase(journal); args = deepcopy(arguments)
    if operation == "service.continue_project" and current == "common" and events(journal, "m02_narrative_fixed"):
        raise Error("fixed common argument must enter explicit live sub-request before Page production")
    if operation == "service.create":
        require(current == "common" and not Path(state["project"]).exists(), "create only the new common project once")
        require(events(journal, "m02_instruction", "common"), "freeze actual common instruction before create")
        expected = {**config["create_arguments"], "brief": Path(config["scopes"]["common"]["instruction"]["path"]).read_text(), "sources": [r["path"] for r in config["materials"]]}
        require(args == expected and "draft" not in args, "create exact preregistered facts/materials, no authored semantic objects")
    if operation == "tasks.call_begin":
        image_begin_guard(journal, state, config, args)
    if operation == "service.inputs_update":
        require(current in ("live", "read"), "input events are preregistered per variant")
        require(config["scopes"][current]["input_patch"] is not None and args["patch"] == config["scopes"][current]["input_patch"], "input patch differs from preregistered actual use-mode event")
    if operation == "collaboration.grant":
        value = args["input"]; check_evidence(journal, value.get("instruction_evidence"), current)
        scope_check(value.get("scope"), config["scopes"][current], notes=current == "live_notes_edit")
        require(type(value.get("max_external_calls", 0)) is int and 0 <= value.get("max_external_calls", 0) <= config["scopes"][current]["max_external_calls"], "production ceiling outside preregistration")
        require(type(value.get("max_candidate_count", 0)) is int and 0 <= value.get("max_candidate_count", 0) <= config["scopes"][current]["max_candidates"], "candidate ceiling outside preregistration")
        if (value.get("constraints") or {}).get("variant_ids") is not None:
            require(current == "common" and value["constraints"]["variant_ids"] == ["live", "read"], "only original two-use declaration, never a third version/group")
    if operation == "collaboration.record_decision":
        value = args["input"]; check_evidence(journal, value.get("instruction_evidence"), current)
        require(value.get("authority_mode") == "delegated" and value.get("delegation_ref"), "actual delegated mechanical decision only; no fake human Owner")
    if operation == "content_production.adopt_proposal" and events(journal, "m02_narrative_fixed"):
        obj = c.store_for(state).read_object_json(args["input"]["proposal_ref"])
        require(current != "common" or obj.get("schema_version") == "narrative.v1", "no Plan/Page adoption in common scope")
        if obj.get("schema_version") == "narrative.v1": require(args["input"]["proposal_ref"] == fixed(journal)["narrative_ref"], "cannot replace fixed Narrative")
    if current == "live_notes_edit":
        require(operation in {"collaboration.grant", "service.inputs_show", "delivery_eligibility.describe", "operations.show", "exports.show", "exports.download", "handoff.check_handoff"}, "notes edit cannot dispatch production/change inputs/refresh image rights")
    if operation in c.PUBLIC_OPERATIONS:
        outcome = c.sdk_operation(journal, state, operation, args)
    else:
        module, name = operation.split(".", 1)
        imported = __import__("deck_master." + module, fromlist=[name]); function = getattr(imported, name)
        project_key = "project_dir" if "project_dir" in __import__("inspect").signature(function).parameters else "project"
        require(project_key not in args, "M02 owns the actual project argument")
        outcome = c.record_sdk(journal, operation, args, lambda: function(**{project_key: state["project"], **args}))
    if operation == "service.create":
        store = c.store_for(state); journal.append("m02_project_bound", {"project_id": store.load_document()["project_id"]})
    guard(journal, state, config)
    return outcome


def fix_narrative(journal, state, config):
    require(phase(journal) == "common" and not events(journal, "m02_narrative_fixed"), "fix common Narrative once")
    store = c.store_for(state); doc = store.load_document(); ref = doc.get("narrative")
    require(ref and not doc["pages"], "actually adopt argument Narrative before either Page set")
    obj = store.read_object_json(ref)
    require(obj.get("maturity") == "argument" and obj.get("project_id") == doc["project_id"], "actual own-project argument required")
    require(any(ref in r.get("outcome", {}).get("result_refs", []) for r in events(journal, "result_accepted")), "common Narrative needs observed actual native result and SDK acceptance before adoption")
    record = {"phase": "common", "narrative_ref": ref, "sources": doc["sources"], "revision_id": doc["revision_id"]}
    c.save(journal.root / "fixed-narrative.json", record); journal.append("m02_narrative_fixed", record)
    return record


def start_variant(journal, state, config, variant, arguments):
    from deck_master import collaboration, variant_requests
    require(variant in ("live", "read", "live_notes_edit"), "only two variants and bounded same-live notes edit")
    prior = {"live": "common", "read": "live", "live_notes_edit": "read"}[variant]
    require(phase(journal) == prior, "single sequential current; no repeated/third/reordered variants")
    locked = fixed(journal); store = c.store_for(state); doc = store.load_document()
    args = deepcopy(arguments); value = args["input"]
    check_evidence(journal, value.get("instruction_evidence"), variant)
    scope_check(value.get("scope"), config["scopes"][variant], notes=variant == "live_notes_edit")
    require(doc.get("narrative") == locked["narrative_ref"], "actual fixed source argument changed")
    if variant == "live":
        declaration = variant_requests.declaring_authorization(store, doc); require(declaration, "effective original two-version declaration required")
        group = variant_requests.variant_group_id(declaration[0], declaration[2])
        require(declaration[2] == ["live", "read"] and "variant_transition" not in value, "first live uses only original declared pair")
    else:
        records = events(journal, "m02_version_exported", "live" if variant == "live_notes_edit" else prior)
        require(len(records) == 1, "source must be a truly complete recorded version/export")
        source = records[0]; group = source["variant"]["group_id"]
        require(value.get("variant_transition") == {"kind": "edit_variant" if variant == "live_notes_edit" else "next_variant", "source": {"revision_id": source["revision_id"], "export_id": source["export_id"]}}, "transition must select exact recorded real source revision/export")
    if variant != "live_notes_edit":
        target = value.get("variant") or {}
        require(set(target) == {"group_id", "variant_id", "label", "requested_variant_ids"} and target["group_id"] == group and target["variant_id"] == variant
                and target["requested_variant_ids"] == ["live", "read"] and value.get("intent") == "full_deck", "exact two-use variant metadata required")
    else:
        require(value.get("intent") == "edit" and "variant" not in value, "notes edit infers selected existing live variant; no third declaration")
    outcome = c.record_sdk(journal, "collaboration.start_request.M02." + variant, args, lambda: collaboration.start_request(state["project"], **args))
    journal.append("m02_phase_started", {"phase": variant, "actual_outcome": outcome})
    guard(journal, state, config)
    return outcome


def packet_boundary(target, state, role):
    c.save(target / "native-boundary.json", {"allowed_packet": str(target), "material_refs": state["materials"],
        "forbidden": ["private oracles", "old native FINALs", "other experiment outputs", "delegation"],
        "must_read_all_actual_methods": True, "raw_before_sdk": True, "model_calls": "Root observed actual native executions only",
        "external_image_calls": 0, "human": "NOT_RUN_USER_DEFERRED", "verification_is_readonly_not_new_writer_feedback": role == "verification"})


def prepare(journal, state, config, stage, task_id, role):
    from deck_master import service, tasks
    require(role in ROLES and (phase(journal) != "live_notes_edit" or role in {"feedback", "verification", "production_review"}), "real Task role required; notes writing has a distinct public-operation packet")
    c.safe_name(stage); store = c.store_for(state); doc = store.load_document(); task = c.task_for(store, task_id)
    if phase(journal) == "common":
        require(task["kind"] == "compose" and (task.get("collaboration_binding") or {}).get("phase") in {"framing", "argument"}, "common scope cannot produce variant Pages or files")
    require(task["status"] in ("awaiting_host", "running") and tasks.task_inputs_current(store, doc, task), "actual current pending/running Task required")
    require((role in {"feedback", "verification", "production_review"}) == (task["kind"] == "review"), "role cannot relabel actual Task kind")
    require(role not in {"initial_writer", "repair_writer"} or task["kind"] == "compose", "content role requires compose")
    require(role != "production" or task["kind"] in {"blueprint", "reconstruct", "repair", "style_analyze"}, "production cannot relabel content")
    require((role in {"feedback", "verification"}) == (task["kind"] == "review" and task.get("review_stage") == "preproduction"), "separate actual preproduction and production review roles")
    if role == "initial_writer":
        require(not events(journal, "m02_repair_begun", phase(journal)) and not events(journal, "m02_feedback_delivered", phase(journal)), "post-feedback repair cannot become initial work")
    if role == "feedback": require(not accepted_reviews(journal, phase(journal), "feedback"), "second feedback cannot masquerade as verification")
    if role == "verification": require(events(journal, "m02_repair_accepted", phase(journal)), "readonly verification requires actual current repair acceptance")
    if role == "repair_writer":
        rows = events(journal, "m02_repair_begun", phase(journal))
        require(rows and (task.get("collaboration_binding") or {}).get("phase") in rows[0]["declaration"]["necessary_layers"], "actual Task must be a declared necessary repair layer")
    target = journal.root / "stages" / stage; target.mkdir(parents=True, exist_ok=False)
    methods = c.read_installed_task_methods(state, task)
    c.save(target / "task.json", task); c.save(target / "work-order.json", service.task_summary(store, doc, task))
    c.save(target / "prepared-method-bytes.json", methods); c.save(target / "current-artifacts.json", c.current_manuscript(store))
    if task["kind"] == "compose" and task.get("protocol_version") == "compose.v2":
        from deck_master import content_production
        c.save(target / "envelope-metadata.json", {"schema_version": "compose_result.v2", "kind": "compose", "variant": content_production.expected_variant(task),
            "task_id": task_id, "operation_id": task["operation_id"], "produced_against": task["produced_against"], "eligibility_digest": task["collaboration_binding"]["eligibility_digest"], "usage_events": []})
    packet_boundary(target, state, role)
    if role == "repair_writer":
        actual = events(journal, "m02_feedback_delivered", phase(journal))[0]
        c.write_once(target / "single-feedback.json", Path(actual["raw"]["path"]).read_bytes())
        c.save(target / "repair-scope.json", events(journal, "m02_repair_begun", phase(journal))[0])
    for ref in [config["grammar"], *config["technical_supplements"]]:
        c.write_once(target / "technical" / Path(ref["path"]).name, Path(ref["path"]).read_bytes())
    root = Path(config["installation"]["module_file"]).parent
    for schema in (root / "resources/contracts").glob("*.schema.json"): c.write_once(target / "schemas" / schema.name, schema.read_bytes())
    c.save(target / "history-and-findings.json", {"events": journal.events(), "current_review_refs": doc.get("reviews", [])})
    dispatch = {"stage": stage, "role": role, "task_id": task_id, "project_id": doc["project_id"], "method_release": methods["current_method_release"], "m02_phase": phase(journal)}
    c.save(target / "dispatch.json", dispatch); journal.append("stage_prepared", dispatch)
    return {"packet": str(target), **dispatch}


def begin(journal, state, config, stage, invocation):
    _, dispatch = c.stage_info(journal, stage); current = phase(journal); role = dispatch["role"]
    require(dispatch["m02_phase"] == current, "stale scope dispatch")
    used = sum(1 for e in events(journal, "m02_native_started", current) if e["role"] == role)
    # Root has already observed an actual invocation: count even an overrun.
    # Offset prior scopes only to let the unchanged helper enforce this scope's
    # own preregistered ceiling, never the E1 global 5/1/1/3 profile.
    total = sum(r["role"] == role for r in events(journal, "native_begun"))
    bounded_state = deepcopy(state)
    bounded_state["budget"][role] = total - used + config["scopes"][current]["native_limits"][role]
    result = c.begin_native(journal, bounded_state, helper_config(config), stage, invocation)
    journal.append("m02_native_started", {"phase": current, **result})
    return result


def accept(journal, state, stage, ordinal):
    current_stage(journal, stage)
    _, _, envelope, _ = c.observed_result(journal, stage, ordinal)
    if phase(journal) == "common": require(envelope.get("variant") in {"framing", "narrative"}, "common native output only fixes the argument")
    if events(journal, "m02_narrative_fixed"):
        require(envelope.get("variant") not in {"narrative", "framing"}, "no replacement shared Narrative phase")
        for proposal in envelope.get("payload", {}).get("proposals", []):
            if proposal.get("layer") == "narrative": require(proposal["ref"] == fixed(journal)["narrative_ref"], "cannot change fixed Narrative")
    result = c.accept(journal, state, stage, ordinal)
    invocation, _ = c.execution(journal, stage, ordinal)
    if invocation["role"] == "repair_writer": journal.append("m02_repair_accepted", {"phase": phase(journal), "ordinal": ordinal, "result": result})
    return result


def review_prepare(journal, state, config, stage, role, bootstrap):
    from deck_master import content_review
    current = phase(journal)
    require(current in ("live", "read", "live_notes_edit") and role in {"feedback", "verification"}, "review belongs to actual current use")
    if role == "feedback":
        require(not events(journal, "m02_feedback_delivered", current), "second feedback is not verification")
        content_checkpoint(journal, state, config)
    else: require(events(journal, "m02_repair_begun", current) and events(journal, "m02_repair_accepted", current), "readonly verification follows actual repair and frozen originals")
    with c.native_runtime(bootstrap) as registry:
        result = c.record_sdk(journal, "content_review.dispatch_preproduction_review", {"bootstrap": c.reference(bootstrap)},
            lambda: content_review.dispatch_preproduction_review(state["project"], adapter_context=registry.channel_context()))
    if result["status"] != "review_dispatched": return result
    packet = prepare(journal, state, config, stage, result["task"]["task_id"], role)
    c.save(Path(packet["packet"]) / "review-packet.json", c.store_for(state).read_object_json(result["review_draft_ref"]))
    return packet


def feedback(journal, stage, ordinal):
    current = phase(journal); require(not events(journal, "m02_feedback_delivered", current), "one actual Writer feedback per scope")
    current_stage(journal, stage)
    invocation, _, envelope, proof = c.observed_result_for_feedback(journal, stage, ordinal)
    record = {"phase": current, "ordinal": ordinal, "executor": invocation["executor"], "raw": proof["raw"], "reviews": envelope["reviews"]}
    journal.append("m02_feedback_delivered", record); return record


def repair(journal, necessity):
    current = phase(journal); rows = events(journal, "m02_feedback_delivered", current)
    require(len(rows) == 1 and not events(journal, "m02_repair_begun", current), "one actual feedback and autonomous repair cycle")
    value = c.read(necessity); ids = {f.get("finding_id") for r in rows[0]["reviews"] for f in r.get("findings", [])}
    require(ids and value.get("actual_review_finding_refs") and set(value["actual_review_finding_refs"]) <= ids and value.get("necessary_layers") and set(value["necessary_layers"]) <= {"argument", "page_copy", "speech"}, "actual finding IDs and necessary repair layers required; never manufacture a defect")
    record = {"phase": current, "necessity": c.reference(necessity), "declaration": value}
    journal.append("m02_repair_begun", record); return record


def complete_version(journal, state, config, variant):
    from deck_master import content_review, editing, exports, pipeline
    from deck_master.compiler.native import notes_records, normalize_notes
    store = c.store_for(state); doc = store.load_document(); locked = fixed(journal)
    require(phase(journal) == variant and variant in ("live", "read"), "complete actual current variant only")
    target = (doc["collaboration"]["request"].get("variant") or {})
    require(target.get("variant_id") == variant and target.get("requested_variant_ids") == ["live", "read"], "actual variant metadata differs")
    require(doc["narrative"] == locked["narrative_ref"] and [r["page_id"] for r in doc["pages"]] == config["scopes"][variant]["page_ids"], "complete preregistered Page set and fixed argument required")
    plan = store.read_object_json(doc["content_plan"])
    require(plan.get("narrative_ref") == locked["narrative_ref"] and [{"page_id": r["page_id"], "page_ref": r["page_ref"]} for r in plan["page_links"]] == [{"page_id": r["page_id"], "page_ref": r["page"]} for r in doc["pages"]], "actual complete Plan/Page mapping required")
    gate = content_review.preproduction_status(store, doc)
    require(gate["status"] == "pass", "actual current independent content gate is blocked")
    require(accepted_reviews(journal, variant, "feedback"), "actual independent first review must belong to this use")
    if events(journal, "m02_repair_begun", variant): require(accepted_reviews(journal, variant, "verification"), "actual repaired use requires separate readonly closure verification")
    require(editing.check_summary(store, doc)["status"] == "pass", "actual final/visual checks are not pass")
    require(pipeline.output_matches_current_svg(store, doc), "actual full native PPTX output is missing/stale")
    for slot in ("pptx", "trace", "render_report"):
        require(doc["outputs"].get(slot), "full version lacks actual output " + slot)
        output = store.read_object_json(doc["outputs"][slot]); store.read_object_bytes(output["file"])
    for row in doc["pages"]:
        for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
            require(row.get(slot), "full version lacks " + slot)
            artifact = store.read_object_json(row[slot]); store.read_object_bytes(artifact["file"])
            require(artifact.get("role") == slot and artifact.get("page_id") == row["page_id"], "actual visual artifact belongs to another layer/Page")
    actual = store.read_object_json(doc["outputs"]["pptx"]); raw = store.read_object_bytes(actual["file"])
    pages = [store.read_object_json(row["page"]) for row in doc["pages"]]
    notes = notes_records(raw)
    require(len(notes) == len(pages) and all(n["page_id"] == p["page_id"] and n["notes"] == normalize_notes(p.get("speaker_notes", "")) for n, p in zip(notes, pages)), "full notes/Page identity/text readback mismatch")
    speech = plan["input"]["speech_policy"]
    require(speech["mode"] == ("cues" if variant == "live" else "none"), "per-use speech policy differs")
    require(variant != "read" or all(not p.get("speaker_notes") for p in pages), "new read Pages must not acquire speaking notes")
    return {"phase": variant, "revision_id": doc["revision_id"], "variant": exports.variant_metadata(store, doc),
            "narrative_ref": doc["narrative"], "plan_ref": doc["content_plan"], "page_entries": doc["pages"], "outputs": doc["outputs"],
            "actual_gate": gate, "notes_readback": notes, "original_pptx_file": actual["file"]}


def export_version(journal, state, config, arguments):
    from deck_master import editing, exports
    current = phase(journal); require(not events(journal, "m02_version_exported", current), "one immutable original export per actual variant")
    record = complete_version(journal, state, config, current)
    args = deepcopy(arguments)
    require(args.get("revision") == record["revision_id"] and args.get("purpose") == "review"
            and args.get("notes_policy") == config["scopes"][current]["notes_policy"], "exact current review file/notes projection required; no human delivery claim")
    require(args.get("output_dir") and not Path(args["output_dir"]).exists() and args.get("export_id"), "new distinct actual versioned export ID/destination required")
    result = c.record_sdk(journal, "editing.export_project.M02", args, lambda: editing.export_project(state["project"], **args))
    stored = exports.show(state["project"], export_id=result["export_id"])
    require(stored["manifest"]["variant"]["narrative_ref"] == record["narrative_ref"], "export fixed Narrative differs")
    for item in stored["manifest"]["files"]: exports.download(state["project"], export_id=result["export_id"], filename=item["path"])
    require(any(f["path"] == "deck.pptx" for f in stored["manifest"]["files"]), "content-only export does not complete M02 full production")
    root = Path(state["project"]) / ".deckmaster/workbench/exports" / result["export_id"]
    copy_root = Path(args["output_dir"]).resolve()
    record.update(output_copy_root=str(copy_root), output_copy_tree={p.relative_to(copy_root).as_posix(): c.reference(p)["sha256"] for p in copy_root.rglob("*") if p.is_file()},
                  export_id=result["export_id"], export_root=str(root), notes_policy=args["notes_policy"],
                  export_tree={p.relative_to(root).as_posix(): c.reference(p)["sha256"] for p in root.rglob("*") if p.is_file()}, export_record=stored)
    c.save(journal.root / "versions" / (current + ".json"), record); journal.append("m02_version_exported", record)
    preserved(journal); return record


def selected_file(journal, state, variant, path):
    from deck_master import delivery_eligibility, handoff
    rows = events(journal, "m02_version_exported", variant); require(len(rows) == 1, "select one actual complete recorded version")
    record = rows[0]; preserved(journal)
    raw = c.reference(path)
    allowed = {item["sha256"] for item in record["export_record"]["manifest"]["files"] if item["path"] == "deck.pptx"}
    require(raw["sha256"] in allowed, "selected file is not the actual fixed exported PPTX")
    report = delivery_eligibility.describe(state["project"], revision=record["revision_id"], file_path=path, notes_policy=record["notes_policy"])
    result = {"variant": variant, "file": raw, "actual_current_control": report,
              "actual_handoff": handoff.check_handoff(state["project"], file_path=path, purpose="review", notes_policy=record["notes_policy"]), "human": "NOT_RUN_USER_DEFERRED"}
    journal.append("m02_selected_file_check", result); return result


def prepare_notes(journal, state, config, stage, operation_id, role="initial_writer"):
    from deck_master import method_resources, editing, eligibility
    require(phase(journal) == "live_notes_edit" and role in {"initial_writer", "repair_writer"}, "direct notes author belongs to bounded selected-live edit")
    store = c.store_for(state); doc = store.load_document()
    pid = config["scopes"]["live_notes_edit"]["page_ids"][0]
    row = next(r for r in doc["pages"] if r["page_id"] == pid)
    require(doc["collaboration"]["request"]["intent"] == "edit", "actual edit_variant request required")
    eligibility.guard(store, doc, "page.edit", context={"targets": {"page_ids": [pid], "layers": ["speech"]}})
    if role == "repair_writer": require(events(journal, "m02_repair_begun", "live_notes_edit"), "real current feedback defect required")
    else: require(not events(journal, "m02_notes_edit_accepted", "live_notes_edit"), "notes edit already accepted; later work needs actual defect/repair role")
    c.safe_name(stage)
    target = journal.root / "stages" / stage; target.mkdir(parents=True, exist_ok=False)
    methods = method_resources.read_skill_methods("deck-content", project=state["project"])
    binding = {"operation": "editing.edit_page", "project_id": doc["project_id"], "page_id": pid,
               "base_revision": doc["revision_id"], "page_hash": row["page"]["sha256"], "operation_id": operation_id}
    dispatch = {"stage": stage, "role": role, "project_id": doc["project_id"], "task_id": None,
                "method_release": methods["method_release"], "m02_phase": "live_notes_edit", "direct_operation_binding": binding}
    c.save(target / "dispatch.json", dispatch)
    c.save(target / "original-page.json", store.read_object_json(row["page"]))
    c.save(target / "prepared-method-bytes.json", methods)
    c.save(target / "current-artifacts.json", c.current_manuscript(store))
    packet_boundary(target, state, role)
    if role == "repair_writer":
        actual = events(journal, "m02_feedback_delivered", "live_notes_edit")[0]
        c.write_once(target / "single-feedback.json", Path(actual["raw"]["path"]).read_bytes())
        c.save(target / "repair-scope.json", events(journal, "m02_repair_begun", "live_notes_edit")[0])
    for ref in [config["grammar"], *config["technical_supplements"]]:
        c.write_once(target / "technical" / Path(ref["path"]).name, Path(ref["path"]).read_bytes())
    require(editing.notes_only_change(store.read_object_json(row["page"]), store.read_object_json(row["page"])), "notes-only comparator unavailable")
    journal.append("stage_prepared", dispatch)
    return {"packet": str(target), **dispatch}


def begin_notes(journal, state, config, stage, invocation_path):
    _, dispatch = c.stage_info(journal, stage)
    require(dispatch.get("direct_operation_binding") and phase(journal) == "live_notes_edit", "actual direct public notes operation, never a fabricated Task")
    observation = c.read(invocation_path); spawn = observation.get("spawn") or {}; executor = spawn.get("canonical_task_name")
    require(observation.get("observation_kind") == c.OBSERVER_KIND and observation.get("assurance") == "host_attested"
            and observation.get("dispatch_sha256") == c.reference(journal.root / "stages" / stage / "dispatch.json")["sha256"]
            and spawn.get("tool") == "collaboration.spawn_agent" and spawn.get("fork_turns") == "none"
            and spawn.get("inherited_identities") == [] and executor == spawn.get("returned_task_name")
            and isinstance(executor, str) and executor.startswith("/root/"), "actual fresh Root native invocation must bind direct notes operation")
    c.fresh(observation["observed_at_utc"])
    excluded = c.read(config["exposure_registry"]["path"])["excluded_identities"]
    require(executor not in excluded and not any(r["executor"] == executor for r in events(journal, "native_begun")), "fresh unexposed notes author required")
    role = dispatch["role"]; used = sum(r["role"] == role for r in events(journal, "m02_native_started", "live_notes_edit"))
    within_budget = used < config["scopes"]["live_notes_edit"]["native_limits"][role]
    ordinal = len(events(journal, "native_begun")) + 1
    result = {"ordinal": ordinal, "stage": stage, "role": role, "executor": executor, "observation": c.reference(invocation_path),
              "within_budget": within_budget, "actual_cost": "unknown", "direct_public_operation": "editing.edit_page"}
    target = journal.root / "stages" / stage / "executions" / f"{ordinal:04d}"
    c.write_once(target / "root-invocation.json", Path(invocation_path).read_bytes())
    journal.append("native_begun", result); journal.append("m02_native_started", {"phase": "live_notes_edit", **result})
    c.save(target / "launch-ready.json", result)
    return result


def read_notes(journal, state, stage, ordinal, executor):
    from deck_master import method_resources
    invocation, target = c.execution(journal, stage, ordinal)
    require(invocation["executor"] == executor and invocation.get("direct_public_operation"), "actual notes executor/operation binding required")
    _, dispatch = c.stage_info(journal, stage)
    methods = method_resources.read_skill_methods("deck-content", project=state["project"])
    require(methods["method_release"] == dispatch["method_release"], "own installed method bytes changed")
    ref = c.save(target / "method-read-record.json", methods)
    journal.append("method_bytes_returned", {"ordinal": ordinal, "executor": executor, "record": ref, "actual_claim": "NO_TASK_PUBLIC_PAGE_EDIT", "limitation": "runtime-returned full bytes, Root must observe actual full native read"})
    return methods


def observe_notes(journal, state, stage, ordinal, result_path, result_sha256, observation_path, observation_sha256):
    import json
    invocation, target = c.execution(journal, stage, ordinal)
    raw = c.write_once(target / "raw-native-output", Path(result_path).read_bytes())
    observation_ref = c.write_once(target / "raw-root-observation.json", Path(observation_path).read_bytes())
    journal.append("native_output_frozen", {"ordinal": ordinal, "stage": stage, "raw": raw, "observation": observation_ref})
    observation = c.read(observation_ref["path"]); completed = observation.get("completion") or {}
    require(raw["sha256"] == result_sha256 and observation_ref["sha256"] == observation_sha256, "Root observed different original bytes")
    require(observation.get("observation_kind") == c.OBSERVER_KIND and observation.get("assurance") == "host_attested"
            and observation.get("dispatch_sha256") == c.reference(target.parent.parent / "dispatch.json")["sha256"]
            and observation.get("model_output_bytes_sha256") == raw["sha256"] and observation.get("all_method_bytes_read") is True
            and observation.get("method_read_record_sha256") == c.reference(target / "method-read-record.json")["sha256"]
            and completed.get("sender") == invocation["executor"] and completed.get("message_type") == "FINAL_ANSWER"
            and completed.get("status_observation_tool") == "collaboration.list_agents" and completed.get("observed_status") == "completed"
            and invocation["executor"] in completed.get("observed_completed_agents", []) and completed.get("raw_final_message"), "actual full native completion/read/direct-operation binding required")
    c.fresh(observation["observed_at_utc"])
    require(isinstance(json.loads(Path(raw["path"]).read_bytes()), dict), "complete native public editing arguments required")
    c.save(target / "observed.json", {"raw": raw, "observation": observation_ref, "executor": invocation["executor"], "ordinal": ordinal})
    return {"raw": raw, "status": "frozen_before_sdk", "not_a_Task": True}


def accept_notes(journal, state, config, stage, ordinal):
    from deck_master import editing
    invocation, target, args, proof = c.observed_result(journal, stage, ordinal)
    require(phase(journal) == "live_notes_edit" and invocation.get("direct_public_operation") == "editing.edit_page", "only actual scoped direct notes result")
    dispatch = c.read(target.parent.parent / "dispatch.json"); binding = dispatch["direct_operation_binding"]
    require(set(args) == {"page", "base_revision", "page_hash", "operation_id"}
            and all(args[k] == binding[k] for k in ("base_revision", "page_hash", "operation_id")), "consume exact native editing arguments without Root wrapping")
    store = c.store_for(state); before = store.load_document()
    original = c.read(target.parent.parent / "original-page.json")
    require(args["page"].get("page_id") == binding["page_id"] and editing.notes_only_change(original, args["page"]), "only authorized notes/segment fields may change")
    row = next(r for r in before["pages"] if r["page_id"] == binding["page_id"])
    require(row["page"]["sha256"] == binding["page_hash"], "selected live Page moved")
    outcome = c.record_sdk(journal, "editing.edit_page.exact_native_notes", {"raw_native": proof["raw"], "arguments": args},
                           lambda: editing.edit_page(state["project"], **args))
    after = store.load_document()
    for old, new in zip(before["pages"], after["pages"]):
        require(old["page_id"] == new["page_id"] and all(old.get(slot) == new.get(slot) for slot in ("blueprint", "svg", "svg_preview")), "notes edit moved actual visual artifacts")
    require(before["tasks"] == after["tasks"], "notes edit changed call/task facts; inspect actual Runtime state")
    journal.append("result_accepted", {"ordinal": ordinal, "role": invocation["role"], "executor": invocation["executor"], "raw": proof["raw"], "outcome": outcome})
    journal.append("m02_notes_edit_accepted", {"phase": "live_notes_edit", "ordinal": ordinal, "revision_id": after["revision_id"], "new_image_calls": 0, "outputs": after["outputs"], "note": "Runtime may clear PPTX/output freshness; no fresh edited PPTX is claimed"})
    if invocation["role"] == "repair_writer": journal.append("m02_repair_accepted", {"phase": "live_notes_edit", "ordinal": ordinal})
    guard(journal, state, config)
    return outcome



def current_stage(journal, stage):
    _, dispatch = c.stage_info(journal, stage)
    require(dispatch["m02_phase"] == phase(journal), "stage belongs to an earlier use/scope")
    return dispatch


def image_begin_guard(journal, state, config, args):
    current = phase(journal)
    require(current in ("live", "read"), "only explicitly authorized variant production can begin an image")
    store = c.store_for(state)
    task = c.task_for(store, args["task_id"])
    require(task["kind"] == "blueprint" and set(task["scope_pages"]) <= set(config["scopes"][current]["page_ids"]), "actual image Task outside registered variant")
    known = {r["task_id"]: r["m02_phase"] for r in events(journal, "stage_prepared") if r.get("task_id")}
    require(known.get(task["task_id"]) == current, "prepare/observe actual production Task before any call")
    used = sum(len(c.store_for(state).read_object_json(ref).get("generation_attempts", []))
               for ref in store.load_document()["tasks"] if known.get(store.read_object_json(ref)["task_id"]) == current)
    require(used < config["scopes"][current]["max_external_calls"], "actual begun-attempt ceiling reached; query/reconcile, never reset rights")
    c.check_ref(config["global_image_budget"])
    budget = c.read(config["global_image_budget"]["path"])
    ledger = Path(budget["ledger_root"])
    require(ledger.is_dir() and not ledger.is_symlink() and c.read(ledger / "global-budget.json") == budget, "freeze the exact budget-pinned canonical shared ledger before first call, never reset between uses")


def accepted_reviews(journal, current, role):
    stages = {row["stage"] for row in events(journal, "stage_prepared") if row.get("m02_phase") == current}
    ordinals = {row["ordinal"] for row in events(journal, "native_begun") if row["stage"] in stages and row["role"] == role}
    return [row for row in events(journal, "result_accepted") if row.get("ordinal") in ordinals and row.get("role") == role]


def content_checkpoint(journal, state, config):
    current = phase(journal); store = c.store_for(state); doc = store.load_document()
    if current == "live_notes_edit": require(events(journal, "m02_notes_edit_accepted", current), "actual notes-only edit must be accepted before its review")
    require(doc.get("narrative") == fixed(journal)["narrative_ref"] and doc.get("content_plan"), "complete current fixed-argument manuscript required")
    expected = config["scopes"]["live" if current == "live_notes_edit" else current]["page_ids"]
    require([row["page_id"] for row in doc["pages"]] == expected, "review must cover entire current use Page set")
    stages = {row["stage"] for row in events(journal, "stage_prepared") if row.get("m02_phase") == current}
    ordinals = {row["ordinal"] for row in events(journal, "native_begun") if row["stage"] in stages}
    originals = [row for row in events(journal, "native_output_frozen") if row["ordinal"] in ordinals]
    require(originals, "current use has no frozen full native originals")
    name = "before-feedback-" + current
    if not (journal.root / (name + ".json")).exists():
        result = {"phase": current, "original_native_stages": originals, "sdk_manuscript_before_first_review": c.current_manuscript(store),
                  "distinction": "native original bytes and actual SDK state are separate; no claim that a Store snapshot is the raw original"}
        c.save(journal.root / (name + ".json"), result)
        journal.append("m02_content_checkpoint", {"phase": current, "record": c.reference(journal.root / (name + ".json"))})


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("freeze"); p.add_argument("--registration", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("init"); p.add_argument("--campaign", required=True); p.add_argument("--out", required=True); p.add_argument("--project", required=True)
    commands = ("instruction", "instruction-evidence", "public-operation", "fix-narrative", "start-variant", "prepare", "begin-native", "claim-read", "observe", "materialize-native-objects", "accept", "review-prepare", "review-accept", "deliver-feedback", "repair-begin", "export-version", "selected-file", "prepare-notes", "begin-notes", "read-notes", "observe-notes", "accept-notes", "reconcile", "status")
    for command in commands:
        p = sub.add_parser(command); p.add_argument("--run", required=True)
        if command in {"instruction", "instruction-evidence"}: p.add_argument("--scope", choices=PHASES, required=True)
        if command == "instruction": p.add_argument("--trigger", required=True)
        if command == "public-operation": p.add_argument("--operation", required=True)
        if command in {"public-operation", "start-variant", "export-version"}: p.add_argument("--arguments", required=True)
        if command in {"start-variant", "selected-file"}: p.add_argument("--variant", required=True)
        if command == "selected-file": p.add_argument("--file", required=True)
        if command in {"prepare", "begin-native", "claim-read", "observe", "materialize-native-objects", "accept", "review-prepare", "review-accept", "deliver-feedback", "prepare-notes", "begin-notes", "read-notes", "observe-notes", "accept-notes"}: p.add_argument("--stage", required=True)
        if command in {"claim-read", "observe", "materialize-native-objects", "accept", "review-accept", "deliver-feedback", "read-notes", "observe-notes", "accept-notes"}: p.add_argument("--ordinal", type=int, required=True)
        if command == "prepare": p.add_argument("--task-id", required=True)
        if command in {"prepare", "prepare-notes", "review-prepare"}: p.add_argument("--role", choices=ROLES, required=True)
        if command == "prepare-notes": p.add_argument("--operation-id", required=True)
        if command in {"begin-native", "begin-notes"}: p.add_argument("--invocation", required=True)
        if command in {"claim-read", "read-notes"}: p.add_argument("--executor", required=True)
        if command in {"observe", "observe-notes"}:
            for name in ("result", "result-sha256", "observation", "observation-sha256"): p.add_argument("--" + name, required=True)
        if command in {"review-prepare", "review-accept"}: p.add_argument("--bootstrap", required=True)
        if command == "repair-begin": p.add_argument("--necessity", required=True)
        if command == "reconcile": p.add_argument("--record", required=True)
    args = parser.parse_args()
    require(sys.flags.isolated and sys.dont_write_bytecode, "use own installed absolute Python -I -B")
    if args.command == "freeze": result = freeze(args.registration, args.out)
    elif args.command == "init": result = init(args.campaign, args.out, args.project)
    else:
        journal, state, config = load(args.run)
        with journal.locked():
            command = args.command
            if hasattr(args, "stage") and command not in {"prepare", "review-prepare", "prepare-notes"}: current_stage(journal, args.stage)
            if command == "instruction": result = instruction(journal, state, config, args.scope, args.trigger)
            elif command == "instruction-evidence": result = instruction_evidence(journal, state, args.scope)
            elif command == "public-operation": result = operate(journal, state, config, args.operation, c.read(args.arguments))
            elif command == "fix-narrative": result = fix_narrative(journal, state, config)
            elif command == "start-variant": result = start_variant(journal, state, config, args.variant, c.read(args.arguments))
            elif command == "prepare": result = prepare(journal, state, config, args.stage, args.task_id, args.role)
            elif command == "begin-native": result = begin(journal, state, config, args.stage, args.invocation)
            elif command == "claim-read": result = c.claim_read(journal, state, args.stage, args.ordinal, args.executor)
            elif command == "observe": result = c.observe(journal, state, args.stage, args.ordinal, args.result, args.result_sha256, args.observation, args.observation_sha256)
            elif command == "materialize-native-objects": result = c.materialize_native_objects(journal, state, args.stage, args.ordinal)
            elif command == "accept": result = accept(journal, state, args.stage, args.ordinal)
            elif command == "review-prepare": result = review_prepare(journal, state, config, args.stage, args.role, args.bootstrap)
            elif command == "review-accept": result = c.review_accept(journal, state, args.stage, args.ordinal, args.bootstrap)
            elif command == "deliver-feedback": result = feedback(journal, args.stage, args.ordinal)
            elif command == "repair-begin": result = repair(journal, args.necessity)
            elif command == "export-version": result = export_version(journal, state, config, c.read(args.arguments))
            elif command == "selected-file": result = selected_file(journal, state, args.variant, args.file)
            elif command == "prepare-notes": result = prepare_notes(journal, state, config, args.stage, args.operation_id, args.role)
            elif command == "begin-notes": result = begin_notes(journal, state, config, args.stage, args.invocation)
            elif command == "read-notes": result = read_notes(journal, state, args.stage, args.ordinal, args.executor)
            elif command == "observe-notes": result = observe_notes(journal, state, args.stage, args.ordinal, args.result, args.result_sha256, args.observation, args.observation_sha256)
            elif command == "accept-notes": result = accept_notes(journal, state, config, args.stage, args.ordinal)
            elif command == "reconcile":
                result = c.reconcile(journal, args.record)
                if not journal.unfinished() and Path(state["project"]).exists() and not events(journal, "m02_project_bound"):
                    from deck_master import service
                    actual = service.inputs_show(state["project"])
                    doc = c.store_for(state).load_document()
                    journal.append("m02_project_bound", {"project_id": doc["project_id"], "recovered_actual_inputs_show": actual})
            else: result = {"scope": config["status"], "phase": phase(journal), "versions": events(journal, "m02_version_exported"), "unfinished_sdk_intents": journal.unfinished(), "native_executions": len(events(journal, "native_begun")), "human": "NOT_RUN_USER_DEFERRED", "credit": "NOT_E1_NOT_ORIGINAL12"}
            guard(journal, state, config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
