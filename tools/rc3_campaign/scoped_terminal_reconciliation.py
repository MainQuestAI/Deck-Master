#!/usr/bin/env python3
"""Reconcile one scoped intent from live own Runtime observations; never retry.

Only changes.commit and its failed operations.show queries are supported.
Root admission is bookkeeping, not a signature or an SDK authority grant.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import traceback

SCOPED_SHA = "afd3e419dcc88b631347250239d33d83dec5c9d4ea69b7429a9f868c7ef0771d"
COMMON_SHA = "d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261"
SOURCE = Path(__file__).with_name("supplementary_recorder.py")
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SCOPED_SHA:
    raise RuntimeError("frozen scoped helper changed")
_spec = importlib.util.spec_from_file_location("rc3_s05_frozen_scoped", SOURCE)
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)
c, Error = s.c, s.Error
FORMAT = "rc3-scoped-terminal-admission.v1"
ACTION = "observe_one_scoped_terminal_intent_no_retry"
IDENTITY = ("root", "slot", "project", "arm", "scope_slot", "whole_run_id")
INSTALLATION = ("python", "module_file", "source_sha", "source_tree", "manifest", "wheel_sha256")


def require(value, message):
    if not value:
        raise Error(message)


def canonical(value, *, exists=True):
    require(isinstance(value, (str, Path)), "absolute ordinary path required")
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and path.resolve(strict=exists) == path,
            "canonical absolute path required")
    return path


def file_ref(path):
    path = canonical(path)
    require(path.is_file(), "ordinary evidence file required")
    return c.reference(path)


def event_ref(journal, event):
    return file_ref(journal.root / "journal" / f"{event['sequence']:06d}.json")


def check_ref(value):
    require(isinstance(value, dict) and isinstance(value.get("path"), str)
            and isinstance(value.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
            "complete ordinary evidence Ref required")
    if "bytes" in value:
        require(type(value["bytes"]) is int and value["bytes"] >= 0, "invalid evidence length")
    actual = file_ref(value["path"])
    require(actual["sha256"] == value["sha256"] and value.get("bytes", actual["bytes"]) == actual["bytes"],
            "evidence bytes changed")
    return actual


def bind(root, path, sha256):
    root = canonical(root)
    admission_ref = file_ref(path)
    require(admission_ref["sha256"] == sha256, "admission bytes differ")
    a = c.read(path)
    require(isinstance(a, dict) and a.get("format") == FORMAT and a.get("action") == ACTION,
            "one-key prospective admission required")
    journal, state, config = s.load(root)
    c.installation(config, state["arm"])
    require(config["status"] == a.get("status"), "admission status differs")
    if config["status"] == "ADMITTED":
        require(a.get("observer_id") == "/root" and a.get("assurance") == "host_attested"
                and a.get("evidence_kind") == "ROOT_ACTUAL_PROSPECTIVE_SCOPE_AMENDMENT",
                "actual prospective Root admission required")
    else:
        require(config["status"] == s.ENGINEERING and a.get("observer_id") == "/engineering/rc3-s05"
                and a.get("assurance") == "synthetic_engineering", "explicit engineering identity required")
    c.fresh(a["observed_at_utc"])
    require(state["profile"] == "q3q4", "only original q3q4 scoped pool supported")
    for key in IDENTITY:
        require(a.get(key) == state[key], "workflow identity differs: " + key)
    expected = {"tool": file_ref(Path(__file__).resolve()), "scoped_recorder": file_ref(SOURCE),
                "common": file_ref(s.SOURCE), "registration": file_ref(Path(state["campaign"]) / "registration.json"),
                "run_manifest": file_ref(root / "run.json")}
    require(expected["common"]["sha256"] == COMMON_SHA, "frozen common helper changed")
    for key, value in expected.items():
        require(a.get(key) == value, "admission dependency differs: " + key)
    install = config["installations"][state["arm"]]
    require(a.get("installation") == {k: install[k] for k in INSTALLATION}, "own installation differs")
    key = a.get("operation_key")
    require(isinstance(key, str) and key in journal.unfinished(), "exact unresolved operation_key required")
    events = journal.events()
    intents = [e for e in events if e["kind"] == "sdk_intent" and e["data"]["operation_key"] == key]
    failures = [e for e in events if e["kind"] == "sdk_error" and e["data"]["operation_key"] == key]
    require(len(intents) == len(failures) == 1, "one original intent and error required")
    intent, failure = intents[0], failures[0]
    require(a.get("intent") == event_ref(journal, intent) and a.get("failure") == event_ref(journal, failure),
            "original intent/error Ref differs")
    require(datetime.fromisoformat(a["observed_at_utc"].replace("Z", "+00:00")) >=
            datetime.fromisoformat(failure["recorded_at"]), "admission predates original failure")
    operation, args = intent["data"]["operation"], intent["data"]["arguments"]
    require(operation in {"changes.commit", "operations.show"} and isinstance(args, dict),
            "unsupported original intent; retain UNKNOWN")
    require(a.get("arguments") == args and a.get("arguments_sha256") == c.digest(c.encoded(args)),
            "original arguments/payload differ")
    require(args.get("project") == state["project"] and a.get("operation_id") == args.get("operation_id")
            and isinstance(a["operation_id"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", a["operation_id"]),
            "same own project and operation ID required")
    require(isinstance(a.get("project_id"), str) and a["project_id"]
            and isinstance(a.get("expected_revision"), str) and a["expected_revision"], "exact current project/revision required")
    if operation == "changes.commit":
        require(set(args) == {"project", "plan_id", "base_revision", "operation_id"}, "exact commit arguments required")
        from deck_master import operations
        operations.validate_id(a["operation_id"], new=True)
        plans = [e for e in events if e["kind"] == "sdk_outcome" and
                 isinstance(e["data"].get("result"), dict) and e["data"]["result"].get("plan_id") == args["plan_id"]]
        require(len(plans) == 1 and a.get("plan_outcome") == event_ref(journal, plans[0]), "original public plan outcome required")
        require(plans[0]["sequence"] < intent["sequence"] and any(
            e["kind"] == "sdk_intent" and e["data"]["operation_key"] == plans[0]["data"]["operation_key"]
            and e["data"]["operation"] == "changes.plan" and e["data"]["arguments"].get("project") == state["project"]
            for e in events), "plan must come from the original own public planning call")
        plan = plans[0]["data"]["result"]["plan"]
        from deck_master.models import canonical_json_bytes
        require(args["plan_id"] == "plan-" + c.digest(canonical_json_bytes(plan))
                and plan["project_id"] == a["project_id"] and plan["base_revision"] == args["base_revision"],
                "original plan payload/basis differs")
        digest = operations.request_digest({"project_id": a["project_id"]}, operation, args["base_revision"],
                                           {"plan_id": args["plan_id"], "plan": plan})
        require(a.get("request_digest") == digest, "original Runtime request digest differs")
    else:
        require(set(args) == {"project", "operation_id"} and a.get("request_digest") is None,
                "readonly query cannot claim a business payload/commit")
    resources = s.Resources(state)
    require(any(e["kind"] == "resource_charge" and e["data"].get("pool") == s.pool_key(state)
                and e["data"].get("slot") == state["slot"] and e["data"].get("resource") == "sdk"
                and e["data"].get("amount") == 1 and e["data"].get("identity") == key
                for e in resources.journal.events()), "original actual SDK charge missing")
    return journal, state, config, a, admission_ref, intent, failure


@contextmanager
def runtime_lock(state):
    """Serialize with the own Runtime's existing write.lock, as S03 does."""
    path = Path(c.store_for(state).lock_path)
    canonical(path.parent)
    require(path.exists() and not path.is_symlink(), "existing own Runtime lock required")
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "ordinary Runtime lock required")
        fcntl.flock(fd, fcntl.LOCK_EX)
        def unchanged():
            current = path.lstat()
            require((current.st_dev, current.st_ino) == (st.st_dev, st.st_ino), "Runtime lock replaced")
        unchanged()
        yield unchanged
        unchanged()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def query(journal, out, operation, arguments, function):
    """Private fixed-call bridge, always the frozen metered query protocol."""
    start = c.now()
    before = len(journal.events())
    error = None
    try:
        result = s.perform(journal, operation, arguments, function, query=True)
        body = {"result": result}
    except Exception as exc:
        error = exc
        body = {"error_type": type(exc).__name__, "error": str(exc),
                "typed_payload": exc.payload() if hasattr(exc, "payload") else None,
                "http_status": getattr(exc, "http_status", None)}
    intents = [e for e in journal.events()[before:] if e["kind"] == "sdk_intent"]
    # A resource refusal before sdk_intent did not invoke the SDK and is never charged as a call.
    require(len(intents) == 1, "public query did not dispatch; no synthetic call or settlement")
    key = intents[0]["data"]["operation_key"]
    body.update(operation=operation, arguments=arguments, operation_key=key,
                started_at_utc=start, finished_at_utc=c.now())
    ref = c.save(out / f"query-{key}.json", body)
    return body, ref, error


def reconcile_key(root, admission_path, admission_sha256, out):
    require(sys.flags.isolated and sys.flags.dont_write_bytecode, "use own absolute Python -I -B")
    initial = bind(root, admission_path, admission_sha256)
    journal, state, config, a, admission_ref, intent, failure = initial
    # Verify the complete original installation before importing any Runtime reader.
    identity = c.installation(config, state["arm"])
    out = canonical(out, exists=False)
    require(not any(out.is_relative_to(canonical(p)) for p in (state["root"], state["campaign"], state["project"])),
            "new evidence must be outside original run/project/ledger")
    out.mkdir(parents=True, exist_ok=False)
    refs = [c.save(out / "identity.json", {"argv": sys.argv, "python": sys.executable,
            "isolated": sys.flags.isolated, "dont_write_bytecode": sys.flags.dont_write_bytecode,
            "installation_observation": identity, "observed_at_utc": c.now()}), admission_ref,
            event_ref(journal, intent), event_ref(journal, failure)]
    with journal.locked(), s.resource_session(root, readonly=True) as (metered, current, current_config):
        require(state == current and config == current_config, "scope changed during admission")
        pending_render = metered.resources.totals()[2]
        # The current read-only resource_session owns exactly one zero reserve.
        # Even an older zero reserve is unknown after process death, not a refund.
        require(len(pending_render) == 1 and next(iter(pending_render.values()))["maximum"] == 0,
                "prior renderer reservation unresolved")
        original_pending = journal.unfinished()
        require(all(k == a["operation_key"] or
                    (d["operation"] == "operations.show" and d["arguments"] == {"project": state["project"], "operation_id": a["operation_id"]})
                    for k, d in original_pending.items()), "other unresolved mutation/inflight intent blocks settlement")
        from deck_master import collaboration, operations, run_desk, view
        fresh_failed = []
        state_ok, observations, reasons = True, {}, []
        with runtime_lock(state) as lock_check:
            def observe(name, args, function):
                body, ref, error = query(metered, out, name, args, function)
                refs.append(ref)
                if error is not None:
                    fresh_failed.append((body, ref, error))
                return body, error

            body, error = observe("view.project_view", {"project_dir": state["project"]},
                                  lambda: view.project_view(state["project"]))
            observations["view"] = body.get("result")
            state_ok = state_ok and error is None
            body, error = observe("collaboration.describe", {"project": state["project"]},
                                  lambda: collaboration.describe(state["project"]))
            observations["collaboration"] = body.get("result")
            state_ok = state_ok and error is None
            offset, tasks = 0, []
            while True:
                args = {"project": state["project"], "revision": a["expected_revision"], "limit": 100, "offset": offset}
                body, error = observe("run_desk.listing", args, lambda args=args: run_desk.listing(**args))
                if error is not None:
                    state_ok = False
                    break
                page = body["result"]
                state_ok = state_ok and page.get("project_id") == a["project_id"] and page.get("revision_id") == a["expected_revision"]
                tasks.extend(page["tasks"])
                next_offset = page["pagination"]["next_offset"]
                if next_offset is None:
                    break
                require(type(next_offset) is int and next_offset > offset, "invalid public pagination; preserve UNKNOWN")
                offset = next_offset
            for obj in observations.values():
                state_ok = state_ok and isinstance(obj, dict) and obj.get("project_id") == a["project_id"] and obj.get("revision_id") == a["expected_revision"]
            current_view = observations["view"] or {}
            state_ok = state_ok and not current_view.get("quality_error") and not any(
                p.get("broken") for p in current_view.get("pages", [])) and not any(
                r.get("status") == "unreadable" for r in current_view.get("reviews", []))
            state_ok = state_ok and all(t.get("status") not in {"running", "unreadable"}
                and not any(t.get("call_counts", {}).get(k, 0) for k in ("reserved", "in_flight", "unknown")) for t in tasks)
            if not state_ok:
                reasons.append("current identity/revision/Task call state is incomplete, changed or inflight")
            opbody, operror = observe("operations.show", {"project": state["project"], "operation_id": a["operation_id"]},
                                     lambda: operations.show(state["project"], operation_id=a["operation_id"]))
            observed = "unknown"
            typed_not_found = (isinstance(operror, operations.OperationError)
                and operror.error_code == "operation_not_found" and operror.operation_state == "not_found"
                and operror.operation_id == a["operation_id"] and operror.http_status == 404)
            readonly = intent["data"]["operation"] == "operations.show"
            if state_ok and typed_not_found:
                # Frozen error bytes plus unchanged original base prove this supported
                # public refusal was before task/allowance/business mutation.
                precommit = (failure["data"].get("error_type") == "EligibilityBlocked"
                    and failure["data"].get("error", "").startswith("eligibility/change.commit:")
                    and a["arguments"].get("base_revision") == a["expected_revision"])
                if readonly or precommit:
                    observed = "not_found"
                else:
                    reasons.append("not_found lacks an exact supported precommit refusal and unchanged base")
            elif state_ok and operror is None and not readonly:
                result = opbody["result"]
                if (result.get("status") == "committed" and result.get("operation_id") == a["operation_id"]
                        and result.get("request_digest") == a["request_digest"]
                        and result.get("current_revision_id") == a["expected_revision"]
                        and isinstance(result.get("committed_revision_id"), str)):
                    observed = "committed"
            if observed == "unknown":
                reasons.append("live own typed operation/current-state observations do not establish a terminal state")
            # Recheck exact admitted bytes and original pending key inside both locks.
            rebound = bind(root, admission_path, admission_sha256)
            require(rebound[1:7] == initial[1:7], "admission/dependencies changed before append")
            for ref in refs:
                check_ref(ref)
            lock_check()
            records = []
            for body, ref, error in fresh_failed:
                own_not_found = body["operation"] == "operations.show" and typed_not_found and error is operror
                value = "not_found" if state_ok and own_not_found else "unknown"
                record = c.save(out / ("record-" + body["operation_key"] + ".json"), {
                    "operation_key": body["operation_key"], "observed_state": value,
                    "runtime_observations": refs, "observation_kind": "readonly_terminal" if value != "unknown" else "readonly_unknown",
                    "business_commit_asserted": False, "observed_at_utc": c.now(), "automatic_retry": False})
                records.append({"record": record, **c.reconcile(journal, record["path"])})
            record = c.save(out / "record-original.json", {
                "operation_key": a["operation_key"], "operation_id": a["operation_id"],
                "observed_state": observed, "arguments_sha256": a["arguments_sha256"],
                "request_digest": a["request_digest"], "runtime_observations": refs,
                "observation_kind": "readonly_terminal" if readonly and observed != "unknown" else "operation_observation",
                "business_commit_asserted": observed == "committed", "observed_at_utc": c.now(),
                "automatic_retry": False, "reasons": reasons})
            result = c.reconcile(journal, record["path"])
            return {**result, "record": record, "query_records": records,
                    "remaining_unresolved_keys": sorted(journal.unfinished()), "automatic_retry": False,
                    "business_authority_granted": False, "observed_at_utc": c.now()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--admission", required=True)
    parser.add_argument("--admission-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = reconcile_key(args.run, args.admission, args.admission_sha256, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "recorded_no_retry" else 3
    except Exception as exc:
        print(json.dumps({"status": "refused_or_unknown", "error_type": type(exc).__name__, "error": str(exc),
                          "automatic_retry": False}, ensure_ascii=False))
        traceback.print_exc(file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
