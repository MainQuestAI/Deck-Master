"""S12 neutral fixtures: explicit L1 predecessor, real public SDK and trust.

No fixture is a formal M02 admission or a new S11 full-render/export result.
No guard/authentication/provider is patched; all future SDK IDs are returned.
"""
import importlib.util
import io
import sys
import uuid
from argparse import Namespace
from copy import deepcopy
from pathlib import Path

from rc3_m02_runtime_cases import bind_admission, c, m, proof, s11

TOOL = Path(__file__).resolve().parents[2] / "tools/rc3_campaign/m02_runtime_continuation.py"
IMAGE_TOOL = TOOL.with_name("m02_image_transition.py")
_spec = importlib.util.spec_from_file_location("s12_neutral", IMAGE_TOOL)
s12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s12)


def compose_two(project, store, use):
    from deck_master import service
    from rc3_fixtures import claimed_phase_task
    from test_content_preproduction_review import _page, _plan_input, _source_link
    doc = store.load_document()
    task = claimed_phase_task(store, doc, operation_id="s12-copy-" + use, phase="page_copy")
    doc = store.load_document()
    ids = ["p1", "p2"] if use == "live" else ["r1", "r2"]
    pages = [_page(store, doc, pid, notes="SYNTHETIC neutral notes" if use == "live" else "") for pid in ids]
    if use == "read":
        for page in pages:
            page["content_mapping"]["speech_segments"] = []
    plan = {**_plan_input(doc, ids, [_source_link(store, doc, "L1")]),
            "speech_policy": {"mode": "cues" if use == "live" else "none", "source": "provided", "output": "pptx_notes"}}
    return service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"], produced_against=task["produced_against"],
        result_payload={"schema_version": "compose_result.v2", "kind": "compose", "variant": "page_copy",
            "task_id": task["task_id"], "operation_id": task["operation_id"], "produced_against": task["produced_against"],
            "eligibility_digest": task["collaboration_binding"]["eligibility_digest"],
            "payload": {"pages": pages, "page_order": ids, "plan_input": plan}, "usage_events": []})


def seed(root, installation):
    import deck_master
    from deck_master import method_resources, service
    from deck_master.store import Store
    from test_rc3_m02_recorder import common_argument, declare_and_start
    source = c.write_once(root / "material.txt", b"SYNTHETIC engineering: record an unknown field; no measured outcome.\n")
    grammar = c.save(root / "grammar.json", {"SYNTHETIC_ENGINEERING": True})
    excluded = c.save(root / "excluded.json", {"status": "FROZEN", "excluded_identities": ["/root/preparer"]})
    roles = m.ROLES
    scopes = {}
    limits = {"common": [5, 0, 0, 0, 0, 0], "live": [5, 3, 1, 1, 12, 8], "read": [5, 3, 1, 1, 12, 8], "live_notes_edit": [1, 0, 1, 0, 0, 0]}
    for phase in m.PHASES:
        instruction = c.write_once(root / (phase + ".txt"), ("SYNTHETIC nonhuman M02 scope " + phase).encode())
        scopes[phase] = {"instruction": instruction, "page_ids": [] if phase == "common" else (["r1", "r2"] if phase == "read" else ["p1", "p2"]),
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
    # This neutral fixture submits two actual Pages. Declare exactly those
    # targets before opening the Request; retain the SDK's normal scope guard.
    args["input"]["scope"]["page_ids"] = old["scopes"]["live"]["page_ids"]
    args["input"]["scope"]["layers"] = ["narrative", "plan", "page_copy", "speech", "design", "blueprint", "svg", "review", "output"]
    m.start_variant(hist, state, old, "live", args)
    compose_two(state["project"], store, "live")
    # Explicit cost/history fixture: no actual native invocation or admission.
    recorded = [("common", "initial_writer")] * 2 + [("live", "initial_writer"), ("live", "feedback")] + [("live", "production")] * 7 + [("live", "production_review")] * 3
    for ordinal, (phase, role) in enumerate(recorded, 1):
        row = {"phase": phase, "role": role, "ordinal": ordinal, "stage": "old-" + str(ordinal),
            "executor": "synthetic-l1-host" if ordinal <= 3 else "exec-independent" if ordinal == 4 else "/root/old-" + str(ordinal), "within_budget": True, "SYNTHETIC_BASELINE_NO_NATIVE": True}
        hist.append("native_begun", row); hist.append("m02_native_started", row)
    doc = store.load_document()
    cfg = {"format": s11.FORMAT, "status": s11.ENGINEERING, "companion_sha256": c.digest(TOOL.read_bytes()),
        "common": c.reference(m.SOURCE), "m02_recorder": c.reference(s11.M02), "project": state["project"],
        "experiment_id": old["experiment_id"], "supplemental_validation_id": "synthetic-s11-successor",
        "runtime_epoch": method_resources.method_release([])["release_id"],
        "group_id": doc["collaboration"]["request"]["variant"]["group_id"], "fixed_narrative": doc["narrative"],
        "predecessor": {"run": oldrun, "registration": oldreg, "event_count": len(hist.events()), "frontier": c.reference(historical_root / "journal" / f"{len(hist.events()):06d}.json")},
        "protected_refs": [oldrun, oldreg, source], "initial_content": s11.content_identity(doc), "initial_pages": doc["pages"], "initial_outputs": doc["outputs"], "blocked_stage": "old-11",
        "auxiliary_executions": [{"executor": "/root/aux-" + str(i), "phase": "live", "role": "production_review", "evidence": grammar} for i in (56, 78)],
        "independent_reviews": {k: grammar for k in ("S07", "S10", "installation", "companion")},
        **{k: deepcopy(old[k]) for k in ("scopes", "materials", "grammar", "protocol", "exposure_registry", "technical_supplements")},
        "installation": installation}
    cfg["protected_refs"] += s11.critical_refs(cfg, state)
    bind_admission(root, cfg)
    rows = s11.chain(historical_root); successor = root / "successor"; c.save(successor / "registration.json", cfg)
    state = {**state, "campaign": str(successor), "project_id": doc["project_id"], "runtime_epoch": cfg["runtime_epoch"], "registration_sha256": c.digest(c.encoded(cfg))}
    c.save(successor / "run.json", state); j = s11.Successor(successor, rows); j.append("m02_successor_initialized", state)
    c.save(root / "identity.json", {"isolated": sys.flags.isolated, "dont_write_bytecode": sys.dont_write_bytecode,
        "module": deck_master.__file__, "project": state["project"], "SYNTHETIC_ONLY": True})
    return j, state, cfg


def current_review(project):
    from deck_master import content_review
    from synthetic_review_provider import (
        accept_with_synthetic_provider,
        dispatch_with_synthetic_provider,
    )
    from test_content_preproduction_review import _independent_adapter, _review
    store = c.store_for({"project": project})
    doc = store.load_document()
    adapter = _independent_adapter(store, doc)
    dispatched = dispatch_with_synthetic_provider(project, adapter_context=adapter)
    task = dispatched["task"]
    reviews = [_review(store, doc, unit, reviewer={"type": "independent_host", "id": "SYNTHETIC-L1-precondition",
        "execution_ref": "exec-independent", "independence_confirmed": True, "identity_receipt": None,
        "assurance": "host_attested"}) for unit in dispatched["units"]]
    result = accept_with_synthetic_provider(project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload={"kind": "review", "reviews": reviews, "usage_events": []},
        adapter_context=adapter)
    assert content_review.preproduction_status(store, store.load_document())["status"] == "pass"
    return result


def read_precondition(root, installation):
    """Real SDK content-only export/read Request, explicit L1 host sequencing.

    No full-export/provenance event or Root receipt is fabricated. Production
    S11 release/start-read gates remain unchanged and are not invoked here.
    """
    from deck_master import collaboration, editing, generation, service, tasks
    from rc3_fixtures import authorize_scope, evidence_for
    from test_compose_v2_phases import _scope
    j, state, cfg = seed(root, installation)
    store = c.store_for(state)
    current_review(state["project"])
    doc = store.load_document()
    authorize_scope(state["project"], actions=["dispatch.blueprint", "allowance.allocate", "task.start", "call.begin", "result.accept"],
        scope=doc["collaboration"]["request"]["scope"], max_external_calls=2, max_candidate_count=2,
        adoption_policy="within_scope", evidence=evidence_for(state["project"], text="SYNTHETIC L1 SDK-only live2; zero image calls", locator="L1:s12-live"))
    live = []
    for pid in ("p1", "p2"):
        doc = store.load_document()
        task = service.open_blueprint_task(store, doc, next(p for p in doc["pages"] if p["page_id"] == pid))
        actor = "L1-live-" + pid
        service.task_start(state["project"], task_id=task["task_id"], execution_ref=actor,
            supported_protocols=[task["protocol_version"]], capabilities=task["required_capabilities"])
        value = generation.prepared_input(store, store.load_document(), task)
        value["parameters"] = {"transparent_background": False}
        frozen = generation.freeze(state["project"], task_id=task["task_id"], input=value,
            base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
        allowance = task["call_allowances"][0]["allowance_id"]
        attempt = tasks.call_begin(store, task_id=task["task_id"], allowance_id=allowance, execution_ref=actor, request_id=frozen["request_id"])
        settled = tasks.call_settle(store, task_id=task["task_id"], allowance_id=allowance, attempt_id=attempt["attempt_id"],
            outcome="consumed", report_bytes=c.encoded({"source": "SYNTHETIC_L1_NO_IMAGE_TOOL"}))
        actual = c.task_for(store, task["task_id"])
        auth = store.read_object_json(actual["collaboration_binding"]["authorization_ref"])
        while auth.get("budget_parent_ref"):
            auth = store.read_object_json(auth["budget_parent_ref"])
        live.append({"task_id": task["task_id"], "page_id": pid, "allowance_id": allowance, "attempt_id": attempt["attempt_id"],
            "request_id": frozen["request_id"], "authorization_id": store.read_object_json(actual["collaboration_binding"]["authorization_ref"])["authorization_id"],
            "budget_root_id": auth["authorization_id"], "actual_request_id": doc["collaboration"]["request"]["request_id"], "actual_settlement": settled})
        service.task_cancel(state["project"], task_id=task["task_id"], reason="L1 SDK-only consumed fact; no image/artifact adoption")
    c.save(root / "actual-live-sdk-baseline.json", {"L1_TRANSPORT_ONLY_ZERO_IMAGE_MODEL_CALLS": True, "rows": live})
    exported = editing.export_project(state["project"], output_dir=str(root / "L1-content-only-export"),
        purpose="review", export_id="export-" + str(uuid.uuid4()))
    assert not any(x["path"].endswith(".pptx") for x in exported["manifest"]["files"])
    c.save(root / "L1-content-only-export.json", exported)
    j.append("m02_engineering_read_precondition", {"L1_NOT_FULL_EXPORT": True, "public_export": c.reference(root / "L1-content-only-export.json")})
    j.append("m02_instruction", {"phase": "read", "message": cfg["scopes"]["read"]["instruction"], "L1_PRECONDITION_ONLY": True})
    evidence = m.instruction_evidence(j, state, "read")
    doc = store.load_document()
    request = collaboration.start_request(state["project"], input={"intent": "full_deck", "content_intent": None,
        "scope": _scope(page_ids=["r1", "r2"], layers=["plan", "page_copy", "speech", "design", "blueprint", "svg", "review", "output"]),
        "instruction_evidence": evidence, "replace_request_id": doc["collaboration"]["request"]["request_id"],
        "variant": {"group_id": cfg["group_id"], "variant_id": "read", "label": "Synthetic read", "requested_variant_ids": ["live", "read"]},
        "variant_transition": {"kind": "next_variant", "source": {"revision_id": exported["revision_id"], "export_id": exported["export_id"]}}},
        base_revision=doc["revision_id"], operation_id=str(uuid.uuid4()))
    j.append("m02_phase_started", {"phase": "read", "actual_outcome": request, "L1_PRECONDITION_ONLY": True})
    compose_two(state["project"], store, "read")
    current_review(state["project"])
    c.save(root / "L1-precondition.json", {"new_S11_full_export": False, "SDK_read_Request": request,
        "current_document": store.load_document(), "native_model_image_calls": 0, "live_rows": live})
    return j, state, cfg, live



class TransitionFixture:
    def __init__(self, root, installation):
        self.root = root
        self.j, self.state, self.cfg, live = read_precondition(root, installation)
        self.store = c.store_for(self.state)
        self.ledger = root / "ig"
        self.protocol = self.cfg["grammar"]
        parent = {"parent_id": "M02", "matrix_slot": "M02", "case": "M02", "whole_run_id": self.cfg["experiment_id"],
                  "repetition": 1, "arm": "B", "max_calls": 4}
        scopes = [{"scope_slot": "M02--" + use, "parent_id": "M02", "checkpoint": use,
                   "instruction": self.cfg["scopes"][use]["instruction"], "max_calls": 2,
                   "leaves": [{"leaf_id": "M02-" + use + "-0" + str(i), "page_label": pid, "page_id": None,
                              "max_calls": 1, "max_candidates": 1, "retries": 0}
                              for i, pid in enumerate(self.cfg["scopes"][use]["page_ids"], 1)]} for use in ("live", "read")]
        other = {"parent_id": "other-original", "matrix_slot": "other", "case": "Q4", "whole_run_id": "L1-other-original",
                 "repetition": 1, "arm": "B", "max_calls": 40}
        scopes.append({"scope_slot": "other-original", "parent_id": other["parent_id"], "checkpoint": "Q4B",
            "instruction": self.protocol, "max_calls": 40, "leaves": [{"leaf_id": "other-" + str(i), "page_label": str(i), "page_id": None,
                "max_calls": 1, "max_candidates": 1, "retries": 0} for i in range(40)]})
        policy = s12.e.save(root / "image-policy.json", {"format": s12.e.POLICY, "status": s12.e.ENGINEERING,
            "ledger_root": str(self.ledger), "protocol": self.protocol, "Root_decision": self.protocol, "total_call_cap": 44,
            "parents": [parent, other], "scopes": scopes})
        activation = s12.e.save(root / "image-activation.json", {"assurance": "host_attested", "observer_id": "/root",
            "evidence_kind": s12.e.ENGINEERING, "policy_sha256": policy["sha256"], "legacy_writer_route": "HISTORICAL_READ_ONLY"})
        mappings = []
        for i, row in enumerate(live, 1):
            dispatch = s12.e.save(self.ledger / "dispatches" / f"{i:06d}.json", {"case": "M02", "whole_run_id": parent["whole_run_id"],
                "repetition": 1, "arm": "B", "page_id": row["page_id"],
                **{k: row[k] for k in ("task_id", "request_id", "authorization_id", "attempt_id")},
                "L1_TRANSPORT_BASELINE_ZERO_IMAGE_CALLS": True})
            mappings.append({"dispatch_sha256": dispatch["sha256"], "scope_slot": "M02--live", "leaf_id": "M02-live-0" + str(i),
                "project_id": self.state["project_id"], "project": self.state["project"], "actual_request_id": row["actual_request_id"],
                "instruction_occurrence_sha256": self.protocol["sha256"], "budget_root_id": row["budget_root_id"], "allowance_id": row["allowance_id"]})
        # Real historical registrations pin paths as well as bytes. Keep their
        # exact helpers in a different directory from the new companion.
        frozen_helpers = root / "original-helpers"
        for name in ("controller.py", "image_controller.py", "image_event_controller.py"):
            c.write_once(frozen_helpers / name, TOOL.with_name(name).read_bytes())
        spec = importlib.util.spec_from_file_location("s12_fixture_original_event", frozen_helpers / "image_event_controller.py")
        original_event = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original_event)
        original = {"format": s12.e.FORMAT, "status": s12.e.ENGINEERING, "controller_sha256": s12.EVENT_SHA,
            "sdk_controller": c.reference(frozen_helpers / "controller.py"), "bf_primitives": c.reference(frozen_helpers / "image_controller.py"),
            "policy": policy, "protocol": self.protocol, "admission_review": self.protocol, "activation": activation,
            "installations": {"B": c.read(self.cfg["predecessor"]["registration"]["path"])["installation"]}, "legacy_mapping": mappings}
        original_ref = s12.e.save(root / "original-image-registration.json", original)
        original_event.initialize_epoch(original_ref["path"], self.ledger)
        _, _, _, frontier = s12.original_epoch(self.ledger)
        rows = s12.e._records(self.ledger, frontier)
        value = {"format": s12.FORMAT, "status": s12.e.ENGINEERING, "companion_sha256": c.digest(IMAGE_TOOL.read_bytes()),
            "event_controller": c.reference(TOOL.with_name("image_event_controller.py")), "successor_controller": c.reference(TOOL),
            "ledger_root": str(self.ledger), "scope_slot": s12.SCOPE, "project": self.state["project"], "project_id": self.state["project_id"],
            "whole_run_id": self.cfg["experiment_id"], "live_budget_roots": sorted({r["budget_root_id"] for r in rows}),
            "spend_evidence": [c.reference(root / "actual-live-sdk-baseline.json")],
            "predecessor": {"registration": c.reference(self.ledger / "event-registration.json"), "origin": c.reference(self.ledger / "event-origin.json"),
                "legacy_frontier": c.reference(self.ledger / "event-legacy-frontier.json"), "policy": policy, "charged_rows": rows,
                "protected_refs": s12.protected_frontier(self.ledger, rows)},
            "successor_registration": c.reference(self.j.root / "registration.json"), "successor_admission": self.cfg["admission"],
            "installation_review": self.cfg["independent_reviews"]["installation"], "installation": installation, "runtime_epoch": self.cfg["runtime_epoch"]}
        value["admission"] = s12.e.save(root / "read-transition-admission.json", {"format": "rc3-m02-read-transition-admission.v1",
            "observer": "/root", "status": s12.e.ENGINEERING, "transition_binding": s12.binding(value), "old_M02_write_routes_retired": True,
            "administrative_only": True, "source_observations": [self.protocol], "SYNTHETIC_L1_NOT_FORMAL_ADMISSION": True})
        self.registration = s12.e.save(root / "read-transition-registration.json", value)
        self.initialized = s12.initialize(self.registration["path"], self.ledger)
        self.occurrence = s12.e.save(root / "read-occurrence.json", {"assurance": "host_attested", "observer_id": "/root",
            "evidence_kind": s12.e.ENGINEERING, "scope_slot": s12.SCOPE, "instruction_sha256": self.cfg["scopes"]["read"]["instruction"]["sha256"],
            "actual_trigger_satisfied": True, "source_observations": [c.reference(root / "L1-precondition.json")], "L1_PRECONDITION_ONLY": True})
        self.handoff = {"format": s12.e.HANDOFF, "matrix_slot": parent["matrix_slot"], "case": "M02", "whole_run_id": parent["whole_run_id"],
            "repetition": 1, "arm": "B", "checkpoint": "read", "project": self.state["project"], "scope_slot": s12.SCOPE,
            "installation_transition": s12.transition_ref(self.ledger), "instruction_occurrence_ref": self.occurrence,
            "actual_request_id": self.store.load_document()["collaboration"]["request"]["request_id"]}
        self.original_public = {name: (self.ledger / name).read_bytes() for name in
            ("event-registration.json", "event-origin.json", "event-legacy-frontier.json")}
        self.original_rows = rows

    def bootstrap(self):
        return s12.e.save(self.root / ("bootstrap-" + uuid.uuid4().hex + ".json"), {"observation_kind": c.OBSERVER_KIND,
            "evidence_kind": s12.e.ENGINEERING, "assurance": "host_attested", "tool": "collaboration.list_agents",
            "observed_running_agents": ["/root"], "observed_at_utc": c.now(), "SYNTHETIC_L1_NO_NATIVE_CALL": True})

    def run(self, command, *, handoff=None, arguments=None, leaf=None, callback=None):
        bootstrap = self.bootstrap()
        journal = c.Journal(self.ledger / "m02-read-transition-journal")
        barrier = s12.e.save(self.root / ("barrier-" + uuid.uuid4().hex + ".json"), {"format": "rc3-m02-read-exclusive-barrier.v1",
            "observer": "/root", "assurance": "host_attested", "command": command, "installation_transition": s12.transition_ref(self.ledger),
            "bootstrap": bootstrap, "project_id": self.state["project_id"], "base_revision": self.store.current_revision_id(),
            "journal_frontier": len(journal.events()), "successor_frontier": len(self.j.local.events()), "old_M02_write_routes_retired": True, "all_other_M02_writers_stopped": True,
            "exclusive_until_completed": True, "source_observations": [self.protocol], "observed_at_utc": c.now(),
            "exclusive_through_first_callback": True, "external_M02_inflight": 0, "external_M02_unknown": 0, "L1_ONLY": True})
        return s12.execute(self.ledger, command, barrier_path=barrier["path"], handoff=handoff or self.handoff, arguments=arguments,
            leaf=leaf, callback=callback, bootstrap=bootstrap["path"])

    def s11_run(self, command, **kwargs):
        return s11.execute(self.j, self.state, self.cfg, Namespace(**proof(self.root, self.j, self.state, self.cfg, command), **kwargs))

    def read_grant(self):
        doc = self.store.load_document()
        evidence = m.events(self.j, "m02_instruction_evidence", "read")[0]["evidence"]
        return self.run("grant-read", arguments={"input": {"mode": "execute",
            "actions": ["dispatch.blueprint", "allowance.allocate", "task.start", "call.begin", "result.accept"],
            "scope": doc["collaboration"]["request"]["scope"], "max_external_calls": 2, "max_candidate_count": 2,
            "adoption_policy": "within_scope", "instruction_evidence": evidence},
            "base_revision": doc["revision_id"], "operation_id": str(uuid.uuid4())})

    def prepare_page(self, pid):
        task = self.run("open-task", arguments={"page_id": pid})
        stage = "s12-" + pid
        packet = self.s11_run("prepare", stage=stage, task_id=task["task_id"], role="production")
        actor = "/root/synthetic-s12-" + pid
        invocation = c.save(self.root / (stage + "-invocation.json"), {"observation_kind": c.OBSERVER_KIND, "assurance": "host_attested",
            "observed_at_utc": c.now(), "project_id": self.state["project_id"], "task_id": task["task_id"], "SYNTHETIC_NO_NATIVE_CALL": True,
            "spawn": {"tool": "collaboration.spawn_agent", "canonical_task_name": actor, "returned_task_name": actor,
                      "fork_turns": "none", "inherited_identities": []}})
        started = self.s11_run("begin-native", stage=stage, invocation=invocation["path"])
        ordinal = started["ordinal"]
        raw = c.reference(Path(packet["packet"]) / "work-order.json")
        audit = s12.e.save(self.root / (stage + "-audit.json"), {"status": "PASS", "scope_slot": s12.SCOPE, "task_id": task["task_id"],
            "project": self.state["project"], "stage": stage, "required_read_closure_checked": True, "raw_workorder_preserved": True,
            "original_raw_ref": raw, "author_view_ref": raw, "read_closure_manifest_ref": c.reference(Path(packet["packet"]) / "current-artifacts.json"), "L1_ONLY": True})
        handoff = {**self.handoff, "task_id": task["task_id"], "page_id": pid, "leaf_id": "M02-read-0" + pid[-1],
                   "stage": stage, "ordinal": ordinal, "packet_audit_ref": audit}
        self.run("claim", handoff=handoff, arguments={"execution_ref": actor})
        methods = self.run("methods", handoff=handoff)
        app = s12.e.save(self.root / (stage + "-method-application.json"), {"observer": "/root", "assurance": "host_attested",
            "installation_transition": s12.transition_ref(self.ledger), "task_id": task["task_id"], "project_id": self.state["project_id"],
            "stage": stage, "ordinal": ordinal, "executor": actor, "all_method_bytes_read": True, "methods_applied": True,
            "required_read_closure_checked": True, "packet_audit_ref": audit, "method_response": methods["record"], "L1_ONLY": True})
        handoff["method_application_ref"] = app
        task = c.task_for(self.store, task["task_id"])
        if not task["call_allowances"]:
            self.run("allocate", handoff=handoff, arguments={"operation_id": str(uuid.uuid4())})
            task = c.task_for(self.store, task["task_id"])
        handoff["allowance_id"] = task["call_allowances"][0]["allowance_id"]
        return handoff

    def freeze_begin(self, handoff):
        from deck_master import generation
        task = c.task_for(self.store, handoff["task_id"])
        actor = task["execution_ref"]
        value = generation.prepared_input(self.store, self.store.load_document(), task)
        value["parameters"] = {"transparent_background": False}
        frozen = self.run("freeze", handoff=handoff, arguments={"input": value, "base_revision": self.store.current_revision_id(),
            "operation_id": str(uuid.uuid4())})
        attempt = self.run("begin", handoff=handoff, arguments={"execution_ref": actor, "request_id": frozen["request_id"]})
        handoff["attempt_id"] = attempt["attempt_id"]
        return handoff, frozen, attempt

    def begin_page(self, pid):
        return self.freeze_begin(self.prepare_page(pid))

    def callback(self, handoff, *, status="completed", wrong_arguments=False):
        from PIL import Image
        leaf = handoff["leaf_id"]
        prepared = c.read(s12.e._call_dir(self.ledger, leaf) / "preparation.json")
        response = c.write_once(self.root / (leaf + "-native-response.txt"), b"SYNTHETIC L1 completion, no actual image/model call.\n")
        data = {"observer_kind": s12.e.ENGINEERING, "observer_id": "/root", "tool_name": "image_gen__imagegen",
            "actual_arguments": prepared["tool_arguments"], "controller_observed_completed_at_ms": s12.b.now_ms(),
            "completion_status": status, "native_response": response, "SYNTHETIC_NO_IMAGE_TOOL": True}
        png = None
        if status == "completed":
            png = self.root / (leaf + "-original.png")
            buffer = io.BytesIO()
            Image.new("RGB", (12, 8), "#334466").save(buffer, "PNG")
            png.write_bytes(buffer.getvalue())
            data["original_png"] = c.reference(png)
        if wrong_arguments:
            data["actual_arguments"] = {"prompt": "changed", "transparent_background": False}
        return c.save(self.root / (leaf + "-callback.json"), data), png

    def adopt(self, handoff, frozen, attempt, png):
        task = c.task_for(self.store, handoff["task_id"])
        staging = self.store.staging_dir / task["operation_id"]
        staging.mkdir(exist_ok=True)
        (staging / "result.png").write_bytes(png.read_bytes())
        envelope = {"kind": "blueprint", "files": [{"file_id": "output", "path": "result.png", "media_type": "image/png"}],
            "generation_result": {"request_id": frozen["request_id"], "attempt_id": attempt["attempt_id"]},
            "artifact_specs": [{"role": "blueprint", "page_id": handoff["page_id"], "file_id": "output",
                "provenance": {"source_type": "host_generated", "tool": "image_gen"}}], "usage_events": []}
        raw = c.save(self.root / (handoff["leaf_id"] + "-writer.json"), envelope)
        packet = s11.current_stage(self.j, self.state, self.cfg, handoff["stage"], handoff["ordinal"])
        invocation, target = c.execution(self.j, handoff["stage"], handoff["ordinal"])
        actor = invocation["executor"]
        observed = c.save(self.root / (handoff["leaf_id"] + "-completion.json"), {"observation_kind": c.OBSERVER_KIND,
            "assurance": "host_attested", "observed_at_utc": c.now(), "project_id": self.state["project_id"], "task_id": task["task_id"],
            "model_output_bytes_sha256": raw["sha256"], "method_release": packet["method_release"], "all_method_bytes_read": True,
            "method_read_record_sha256": c.reference(target / "method-read-record.json")["sha256"], "SYNTHETIC_NO_NATIVE_CALL": True,
            "completion": {"sender": actor, "message_type": "FINAL_ANSWER", "status_observation_tool": "collaboration.list_agents",
                "observed_status": "completed", "observed_completed_agents": [actor], "raw_final_message": "SYNTHETIC L1 protocol envelope, no model/human quality claim"}})
        self.s11_run("observe", stage=handoff["stage"], ordinal=handoff["ordinal"], result=raw["path"], result_sha256=raw["sha256"],
                     observation=observed["path"], observation_sha256=observed["sha256"])
        return self.run("accept-blueprint", handoff=handoff)


