"""Executed S12 own-wheel probe. Synthetic L1 prerequisites; real SDK/trust.

No renderer/model/image/actor call or formal project is used. Observer facts are
labelled engineering. The original image recorder alone handles its secret.
"""
import argparse
import json
import os
import sys
import traceback
import uuid
import zipfile
from copy import deepcopy
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))  # test helpers only, never Source/src
from rc3_s12_evidence import Recorder, publish_workspace, save

SCENARIOS = ("positive", "unknown", "bad-callback", "grant-lost-ack", "grant-durable", "role-overrun")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--working", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    working, evidence = Path(args.working).resolve(), Path(args.evidence).resolve()
    assert not working.is_relative_to(evidence) and not evidence.is_relative_to(working)
    working.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=True)
    assert sys.flags.isolated == sys.dont_write_bytecode == 1
    import deck_master
    from deck_master import (
        collaboration,
        content_production,
        content_review,
        editing,
        exports,
        generation,
        method_resources,
        service,
        tasks,
    )
    from rc3_m02_image_fixture import TransitionFixture, c, m, s11, s12
    source = Path(__file__).resolve().parents[2]
    package = Path(deck_master.__file__).resolve().parent
    assert package.is_relative_to(Path(sys.prefix).resolve()) and not package.is_relative_to(source / "src")
    wheel = Path(args.wheel).resolve()
    actual = {p.relative_to(package).as_posix(): c.digest(p.read_bytes()) for p in package.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    with zipfile.ZipFile(wheel) as archive:
        expected = {p.removeprefix("deck_master/"): c.digest(archive.read(p)) for p in archive.namelist()
                    if p.startswith("deck_master/") and not p.endswith("/")}
    source_files = {p.relative_to(source / "src/deck_master").as_posix(): c.digest(p.read_bytes())
                    for p in (source / "src/deck_master").rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    assert actual == expected and all(actual.get(p) == sha for p, sha in source_files.items())
    installation = {"python": sys.executable, "module_file": deck_master.__file__, "source_sha": "portable-own-wheel-engineering",
                    "wheel": c.reference(wheel), "package_files": actual}
    save(evidence / "identity.json", {"isolated": sys.flags.isolated, "dont_write_bytecode": sys.dont_write_bytecode,
        "installation": installation, "source_files": source_files, "actual_identity":
        __import__("deck_master.capabilities", fromlist=["installation_identity"]).installation_identity(),
        "github_sha": os.environ.get("GITHUB_SHA"), "formal_managed_admission": False})
    for name in ("m02_image_transition.py", "m02_runtime_continuation.py", "image_event_controller.py", "image_controller.py", "controller.py"):
        path = source / "tools/rc3_campaign" / name
        save(evidence / "source-inputs" / (name + ".json"), {"path": str(path), "bytes": path.stat().st_size, "sha256": c.digest(path.read_bytes())})
    recorder = Recorder(evidence / "functions")
    for module, names in [(service, ("create", "task_start", "task_cancel", "open_host_task", "open_blueprint_task", "accept_result")),
            (collaboration, ("start_request", "grant", "record_decision")), (content_production, ("open_phase_task", "adopt_proposal")),
            (content_review, ("dispatch_preproduction_review",)), (editing, ("export_project",)), (exports, ("show", "download")),
            (method_resources, ("read_task_methods", "read_skill_methods")), (generation, ("freeze", "show")),
            (tasks, ("call_begin", "call_settle", "allocate_call_allowances")), (s12, ("execute",)), (s11, ("execute",))]:
        recorder.wrap(module, names)
    outcomes, checks = [], []

    def check(scenario, label, condition):
        row = {"scenario": scenario, "check": label, "pass": bool(condition)}
        checks.append(row)
        save(evidence / "checks" / f"{len(checks):04d}.json", row)
        assert condition, label

    def reject(fixture, scenario, label, call, match):
        before = fixture.store.load_document()
        count = len(s12.e._records(fixture.ledger, c.read(fixture.ledger / "event-legacy-frontier.json")))
        try:
            call()
        except Exception as exc:  # noqa: BLE001 - negatives must preserve every real SDK refusal
            save(evidence / "refusals" / f"{len(checks):04d}.json", {"scenario": scenario, "label": label,
                "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
            assert match in str(exc), (label, type(exc).__name__, str(exc))
        else:
            raise AssertionError("allowed: " + label)
        check(scenario, label, fixture.store.load_document() == before
              and len(s12.e._records(fixture.ledger, c.read(fixture.ledger / "event-legacy-frontier.json"))) == count)

    try:
        for scenario in SCENARIOS:
            root = working / scenario
            root.mkdir()
            start = recorder.count
            fixture = TransitionFixture(root, installation)
            check(scenario, "real live2 baseline; transition alone grants no calls",
                  fixture.initialized["new_calls"] == 0 and len(fixture.run("status")["all_charged_rows"]) == 2)
            check(scenario, "L1 never invents full S11 export/provenance",
                  not m.events(fixture.j, "m02_version_exported") and not m.events(fixture.j, "m02_supplemental_export_provenance"))
            if scenario in {"grant-lost-ack", "grant-durable"}:
                if scenario == "grant-lost-ack":
                    original = collaboration.grant
                    def lose_ack(*a, _original=original, **kw):
                        result = _original(*a, **kw)
                        save(evidence / "actual-grant-before-lost-ack.json", result)
                        raise ConnectionError("L1 actual grant committed; acknowledgment lost")
                    collaboration.grant = lose_ack
                    try:
                        fixture.read_grant()
                    except ConnectionError:
                        pass
                    else:
                        raise AssertionError("grant lost-ack fault did not execute")
                    finally:
                        collaboration.grant = original
                    status = fixture.run("status")
                    check(scenario, "SDK committed without recorded outcome stays blocked",
                          status["pending"]["transition"] and status["read_grant"] is None)
                    reject(fixture, scenario, "unknown grant cannot retry or change pool", fixture.read_grant, "unresolved")
                    reject(fixture, scenario, "unknown grant cannot open Task", lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r1"}), "unresolved")
                else:
                    original = s12.c.Journal.append
                    fired = []
                    def durable_then_fail(journal, kind, data, _original=original, _fixture=fixture, _fired=fired):
                        result = _original(journal, kind, data)
                        if kind == "sdk_outcome" and journal.root == _fixture.ledger / "m02-read-transition-journal" and not _fired:
                            _fired.append(True)
                            raise OSError("L1 SDK outcome durable; caller return interrupted")
                        return result
                    s12.c.Journal.append = durable_then_fail
                    try:
                        fixture.read_grant()
                    except OSError:
                        pass
                    else:
                        raise AssertionError("durable-outcome fault did not execute")
                    finally:
                        s12.c.Journal.append = original
                    status = fixture.run("status")
                    check(scenario, "durable actual outcome restores binding without another grant",
                          fired and not status["pending"]["transition"] and status["read_grant"]["SDK_result"]["status"] == "accepted")
                    reject(fixture, scenario, "durable grant cannot open second pool", fixture.read_grant, "one grant")
                    task = fixture.run("open-task", arguments={"page_id": "r1"})
                    actual_auth = fixture.store.read_object_json(task["collaboration_binding"]["authorization_ref"])
                    while actual_auth.get("budget_parent_ref"):
                        actual_auth = fixture.store.read_object_json(actual_auth["budget_parent_ref"])
                    check(scenario, "new Task consumes exact returned root", actual_auth["authorization_id"] == status["read_grant"]["budget_root_id"])
                journal = c.Journal(fixture.ledger / "m02-read-transition-journal")
                check(scenario, "one physical SDK grant intent", len([r for r in journal.events()
                    if r["kind"] == "sdk_intent" and r["data"]["operation"] == "collaboration.grant"]) == 1)
            else:
                fixture.read_grant()
                reject(fixture, scenario, "same scope cannot renew read2 pool", fixture.read_grant, "one grant")
                handoff = fixture.prepare_page("r1")
                from deck_master import generation as gen
                current_task = c.task_for(fixture.store, handoff["task_id"])
                bad_input = gen.prepared_input(fixture.store, fixture.store.load_document(), current_task)
                bad_input["parameters"] = {"transparent_background": True}
                reject(fixture, scenario, "true parameter rejected before first actual freeze",
                       lambda fixture=fixture, handoff=handoff, bad_input=bad_input: fixture.run("freeze", handoff=handoff, arguments={"input": bad_input,
                           "base_revision": fixture.store.current_revision_id(), "operation_id": str(uuid.uuid4())}), "exact-false")
                handoff, frozen, attempt = fixture.freeze_begin(handoff)
                for key, value in (("scope_slot", "M02--live"), ("project", str(root / "foreign")), ("actual_request_id", fixture.original_rows[0]["actual_request_id"])):
                    bad = {**handoff, key: value}
                    reject(fixture, scenario, "current guard rejects " + key, lambda bad=bad, fixture=fixture: fixture.run("prepare", handoff=bad), "same" if key != "actual_request_id" else "Request")
                fixture.run("prepare", handoff=handoff)
                fixture.run("mark", leaf="M02-read-01")
                reject(fixture, scenario, "pending first callback blocks next consumption",
                       lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r2"}), "pending")
                if scenario == "role-overrun":
                    packet = s11.current_stage(fixture.j, fixture.state, fixture.cfg, handoff["stage"], handoff["ordinal"])
                    for index in range(12):
                        actor = "/root/L1-overrun-" + str(index)
                        invocation = c.save(root / ("overrun-" + str(index) + ".json"), {"observation_kind": c.OBSERVER_KIND,
                            "assurance": "host_attested", "observed_at_utc": c.now(), "project_id": fixture.state["project_id"], "task_id": packet["task_id"],
                            "SYNTHETIC_NO_MODEL_CALL": True, "spawn": {"tool": "collaboration.spawn_agent", "canonical_task_name": actor,
                                "returned_task_name": actor, "fork_turns": "none", "inherited_identities": []}})
                        fixture.s11_run("begin-native", stage=handoff["stage"], invocation=invocation["path"])
                    check(scenario, "all13 observed production invocations remain counted", s11.costs(fixture.j, fixture.cfg)["by_phase_role"]["read"]["production"] == 13)
                callback, png = fixture.callback(handoff, status="unknown" if scenario == "unknown" else "completed",
                                                 wrong_arguments=scenario == "bad-callback")
                if scenario == "bad-callback":
                    reject(fixture, scenario, "malformed first callback is preserved before refusal",
                           lambda fixture=fixture, callback=callback: fixture.run("seal", leaf="M02-read-01", callback=callback["path"]), "literal")
                    first = s12.e._call_dir(fixture.ledger, "M02-read-01") / "raw-first-root-callback"
                    check(scenario, "full first bad raw bytes immutable", first.read_bytes() == Path(callback["path"]).read_bytes())
                    reject(fixture, scenario, "bad callback does not refund or permit another Task",
                           lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r2"}), "pending")
                else:
                    fixture.run("seal", leaf="M02-read-01", callback=callback["path"])
                    if scenario != "role-overrun":
                        reject(fixture, scenario, "callback alone cannot hide unresolved SDK settlement",
                               lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r2"}), "unresolved")
                    settled = fixture.run("settle", leaf="M02-read-01")
                    if scenario == "unknown":
                        check(scenario, "unknown actual SDK remains charged", settled["actual_call_outcome"] == "unknown"
                              and settled["actual_result"]["outcome"] == "unknown")
                        reject(fixture, scenario, "terminal unknown never unlocks other read leaf",
                               lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r2"}), "unknown")
                        shown = s12.execute(fixture.ledger, "query", leaf="M02-read-01")
                        check(scenario, "real unknown query never refunds", shown["actual_query"]["call"]["state"] == "unknown" and shown["budget_refund"] is False)
                    else:
                        check(scenario, "original authenticated provider accepted actual scoped SDK fact",
                              settled["context_rejection"] is None and settled["actual_result"]["native_observation_status"] == "accepted")
                        if scenario == "role-overrun":
                            reject(fixture, scenario, "earlier within-budget ordinal cannot consume after13of12",
                                   lambda fixture=fixture, handoff=handoff, frozen=frozen, attempt=attempt, png=png: fixture.adopt(handoff, frozen, attempt, png), "caps exceeded")
                            check(scenario, "raw and consumed image fact survive overrun",
                                  c.observed_result(fixture.j, handoff["stage"], handoff["ordinal"])[0]["within_budget"]
                                  and c.task_for(fixture.store, handoff["task_id"])["call_allowances"][0]["state"] == "consumed")
                        else:
                            result = fixture.adopt(handoff, frozen, attempt, png)
                            check(scenario, "first exact PNG really adopted", result["status"] == "accepted")
                            h2, f2, a2 = fixture.begin_page("r2")
                            fixture.run("prepare", handoff=h2)
                            fixture.run("mark", leaf="M02-read-02")
                            cb2, png2 = fixture.callback(h2)
                            fixture.run("seal", leaf="M02-read-02", callback=cb2["path"])
                            original = tasks.call_settle
                            def lose_settle_ack(*a, _original=original, **kw):
                                result = _original(*a, **kw)
                                save(evidence / "actual-settle-before-lost-ack.json", result)
                                raise ConnectionError("L1 actual settlement committed; acknowledgment lost")
                            tasks.call_settle = lose_settle_ack
                            try:
                                fixture.run("settle", leaf="M02-read-02")
                            except ConnectionError:
                                pass
                            else:
                                raise AssertionError("settlement lost-ack fault did not execute")
                            finally:
                                tasks.call_settle = original
                            reject(fixture, scenario, "lost settlement ACK blocks consumption",
                                   lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r1"}), "unresolved")
                            shown = s12.execute(fixture.ledger, "query", leaf="M02-read-02")
                            check(scenario, "exact real query recovers consumed without retry",
                                  shown["actual_query"]["call"]["state"] == "consumed" and shown["automatic_retry"] is False)
                            reject(fixture, scenario, "reconciled settlement cannot replay",
                                   lambda fixture=fixture: fixture.run("settle", leaf="M02-read-02"), "settlement")
                            check(scenario, "second exact PNG really adopted", fixture.adopt(h2, f2, a2, png2)["status"] == "accepted")
                            status = fixture.run("status")
                            check(scenario, "same ledger retains live2 and read2, parent4/global44", len(status["all_charged_rows"]) == 4)
                            reject(fixture, scenario, "third call cannot reopen original leaf", lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r1"}), "cap")
                            with s12.locked(fixture.ledger) as ledger:
                                values = s12.load(ledger)
                                for key in ("admission", "successor_admission", "installation_review"):
                                    bad = deepcopy(values[5])
                                    bad[key] = c.reference(root / "L1-precondition.json")
                                    reject(fixture, scenario, "wrong exact " + key, lambda bad=bad, values=values: s12.validate(bad, values[0], values[1], values[2], values[4]),
                                           "installation" if key != "admission" else "admission")
                                provider = s12.ScopedRootEventProvider(ledger, values[1], "M02-read-02")
                                reject(fixture, scenario, "ordinary JSON cannot replace protected observation", lambda provider=provider: provider.verify(b"{}"), "protected")
                            fixture.j.append("m02_phase_started", {"phase": "live", "L1_NEGATIVE_ONLY": True})
                            reject(fixture, scenario, "read label cannot override real phase", lambda fixture=fixture: fixture.run("open-task", arguments={"page_id": "r1"}), "read Request")
            status = fixture.run("status")
            check(scenario, "original registration/globalB/frontier bytes unchanged",
                  all((fixture.ledger / name).read_bytes() == raw for name, raw in fixture.original_public.items())
                  and status["all_charged_rows"][:2] == fixture.original_rows)
            check(scenario, "all Runtime modules exclusively in own prefix", all(Path(mod.__file__).resolve().is_relative_to(package)
                  for name, mod in sys.modules.items() if (name == "deck_master" or name.startswith("deck_master.")) and getattr(mod, "__file__", None)))
            item = {"scenario": scenario, "status": "executed", "function_observations": recorder.count-start, "ledger": status,
                    "real_native_model_image_actor_render_calls": 0, "L1_history_and_observations": True}
            outcomes.append(item)
            save(evidence / (scenario + ".result.json"), item)
        save(evidence / "result.json", {"status": "ENGINEERING_ONLY", "scenarios": outcomes, "checks": checks,
            "function_observations": recorder.count, "new_S11_full_export_or_formal_M02": False, "managed_candidate": False})
        print(json.dumps({"scenarios": len(outcomes), "checks": len(checks), "function_observations": recorder.count}))
    except BaseException as exc:
        save(evidence / "failure.json", {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(),
            "completed_scenarios": outcomes, "checks": checks, "function_observations": recorder.count})
        raise
    finally:
        manifest = publish_workspace(working, evidence / "neutral-workspaces")
        save(evidence / "workspace-manifest-from-probe.json", manifest)


if __name__ == "__main__":
    main()

