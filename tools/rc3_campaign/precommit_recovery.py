#!/usr/bin/env python3
"""Explicit Q3 create-absence recovery; never retries or changes project data.

Host attestations authorize the exact diagnostic scope, not the absence fact.
Absence comes only from this own Runtime's public query and locked double probe.
The frozen scoped recorder, registration, installation and old failures remain.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import traceback
import uuid

SCOPED_SHA = "afd3e419dcc88b631347250239d33d83dec5c9d4ea69b7429a9f868c7ef0771d"
COMMON_SHA = "d0b2b079afb7a714c4d7028b7e5eaa6be70cc0cef41db6c73d664c952f373261"
SOURCE = Path(__file__).with_name("supplementary_recorder.py")
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SCOPED_SHA:
    raise RuntimeError("frozen supplementary recorder changed")
_spec = importlib.util.spec_from_file_location("rc3_s03_frozen_scoped", SOURCE)
s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s)
c = s.c
Error = c.CampaignError
FORMAT = "rc3-precommit-absence-admission.v1"
ACTION = "reconcile_service_create_precommit_absence_only"


def require(value, message):
    if not value:
        raise Error(message)


def canonical(path, *, exists=True):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "canonical absolute path required")
    require(path.resolve(strict=exists) == path, "path alias or symlink refused")
    current = path
    while current != current.parent:
        require(not current.is_symlink(), "path ancestry contains a symlink")
        current = current.parent
    return path


def event_ref(journal, event):
    return c.reference(journal.root / "journal" / f"{event['sequence']:06d}.json")


def bind(root, admission_path, admission_sha256):
    root = canonical(root)
    admission_path = canonical(admission_path)
    admission_ref = c.reference(admission_path)
    require(admission_ref["sha256"] == admission_sha256, "Root admission bytes differ")
    admission = c.read(admission_path)
    journal, state, config = s.load(root)
    require(admission.get("format") == FORMAT and admission.get("action") == ACTION,
            "narrow actual create-absence admission required")
    require(admission.get("status") == config["status"], "engineering cannot authorize an admitted run")
    if config["status"] == "ADMITTED":
        require(admission.get("observer_id") == "/root" and admission.get("assurance") == "host_attested"
                and admission.get("evidence_kind") == "ROOT_ACTUAL_PROSPECTIVE_SCOPE_AMENDMENT",
                "actual prospective Root admission required")
    else:
        require(config["status"] == s.ENGINEERING and admission.get("assurance") == "synthetic_engineering"
                and admission.get("observer_id") == "/engineering/rc3-s03",
                "engineering identity must be explicit, never a fake Root observation")
    expected_refs = {"tool": c.reference(Path(__file__).resolve()), "scoped_recorder": c.reference(SOURCE),
                     "common": c.reference(s.SOURCE), "registration": c.reference(Path(state["campaign"]) / "registration.json"),
                     "run_manifest": c.reference(root / "run.json")}
    for key, expected in expected_refs.items():
        require(admission.get(key) == expected, "admission dependency differs: " + key)
    require(expected_refs["common"]["sha256"] == COMMON_SHA, "frozen common helper changed")
    require(state["profile"] == "q3q4" and state["case"] == state["checkpoint"] == "Q3"
            and state["project_mode"] == "new"
            and state["scope_slot"] == f"flow-{state['matrix_slot']}--original-missing-template",
            "only original Q3 missing-template create scope is supported")
    for key in ("root", "slot", "project", "arm", "scope_slot", "whole_run_id"):
        require(admission.get(key) == state[key], "admission workflow identity differs: " + key)
    installation = config["installations"][state["arm"]]
    require(admission.get("installation") == {k: installation[k] for k in ("python", "module_file", "source_sha", "source_tree", "manifest", "wheel_sha256")},
            "admission must bind the original own managed installation")
    key = admission.get("operation_key")
    pending = journal.unfinished()
    require(set(pending) == {key}, "only the exact one unresolved create intent may be reconciled")
    events = journal.events()
    intent_event = next(e for e in events if e["kind"] == "sdk_intent" and e["data"]["operation_key"] == key)
    failures = [e for e in events if e["kind"] == "sdk_error" and e["data"]["operation_key"] == key]
    require(len(failures) == 1 and intent_event["data"]["operation"] == "service.create",
            "exact original create failure required")
    failure = failures[0]
    require(admission.get("intent") == event_ref(journal, intent_event)
            and admission.get("failure") == event_ref(journal, failure), "wrong original intent/failure bytes")
    args = intent_event["data"]["arguments"]
    require("operation_id" not in args and args.get("project_dir") == state["project"],
            "no invented public operation ID or caller project")
    require(admission.get("create_arguments_sha256") == c.digest(c.encoded(args)), "create argument identity changed")
    require(set(args) == {"project_dir", "brief", "sources", "presentation_mode", "page_limit"}
            and args["sources"] == [ref["path"] for ref in state["materials"]]
            and args["brief"] == Path(state["instruction"]["path"]).read_text()
            and args["presentation_mode"] == "read" and args["page_limit"] == 6,
            "only the original Q3 invalid-enum request is supported")
    require(failure["data"].get("error_type") == "ModelError"
            and failure["data"].get("error", "").startswith("document/task/presentation_mode:"),
            "original public enum precommit failure required")
    require(admission.get("enum_mapping") == {"field": "presentation_mode", "original": "read", "public": "read_alone"},
            "explicit nonsemantic enum mapping required")
    require(not any(e["kind"] in {"native_begun", "stage_prepared", "result_accepted"} for e in events),
            "native/Task history contradicts this precommit-only route")
    resources = s.Resources(state)
    require(any(e["kind"] == "resource_charge" and e["data"].get("pool") == s.pool_key(state)
                and e["data"].get("slot") == state["slot"] and e["data"].get("resource") == "sdk"
                and e["data"].get("identity") == key and e["data"].get("amount") == 1
                for e in resources.journal.events()), "original actual failed SDK charge is missing")
    return journal, state, config, admission_ref, intent_event


def expected_orphans(state):
    """Own pure reader/canonicalization, no Store puts or Task construction."""
    from deck_master.models import canonical_json_bytes
    from deck_master.sources import read_source_snapshot
    result = {}
    for material in state["materials"]:
        path = canonical(material["path"])
        c.check_ref(material)
        require(path.suffix.lower() == ".txt", "only registered Q3 plain text source orphans are supported")
        extract, raw = read_source_snapshot(path)
        require(c.digest(raw) == material["sha256"] and extract.status == "read" and extract.format == "txt",
                "own material reader differs from registered source")
        digest = c.digest(raw)
        original = {"path": f".deckmaster/objects/{digest[:2]}/{digest}.txt", "sha256": digest}
        value = {**asdict(extract), "original_file": original}
        encoded = canonical_json_bytes(value)
        extract_digest = c.digest(encoded)
        result[original["path"]] = digest
        result[f".deckmaster/objects/{extract_digest[:2]}/{extract_digest}.json"] = extract_digest
    return result


def signature(st):
    return [st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def probe(state, allowed, lock_identity):
    """Reject any current/revision/operation/Task/unknown object, not just a name."""
    project = canonical(state["project"])
    require(project.is_dir(), "partial project directory is unavailable")
    metadata = project / ".deckmaster"
    require(canonical(metadata).is_dir(), "actual metadata directory is unavailable")
    require({p.name for p in project.iterdir()} == {".deckmaster"}, "foreign project entries make absence ambiguous")
    require({p.name for p in metadata.iterdir()} <= {"objects", "revisions", "staging", "write.lock", "operations"},
            "current/Task/operation or unknown metadata exists")
    files, directories = {}, {}
    shards = {metadata / "objects" / Path(name).parts[-2] for name in allowed}
    for path in sorted(metadata.rglob("*")):
        canonical(path)
        st = path.lstat()
        if path.is_dir():
            require(path == metadata / "objects" or path in shards
                    or path in {metadata / "revisions", metadata / "staging", metadata / "staging/anonymous", metadata / "operations"},
                    "unexpected nested metadata directory")
            directories[path.relative_to(project).as_posix()] = signature(st)
            continue
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "metadata alias/special file refused")
        if path == metadata / "write.lock":
            require([st.st_dev, st.st_ino] == lock_identity and st.st_size == 0, "Runtime lock identity changed")
            continue
        relative = path.relative_to(project).as_posix()
        require(relative in allowed, "Document/Task/receipt or unknown orphan is not source evidence: " + relative)
        raw = path.read_bytes()
        require(signature(st) == signature(path.lstat()) and c.digest(raw) == allowed[relative], "orphan changed during probe")
        files[relative] = {"sha256": c.digest(raw), "signature": signature(st)}
    require(set(files) == set(allowed), "original source ingestion evidence is absent or incomplete")
    return {"project": str(project), "project_identity": signature(project.stat()),
            "metadata_identity": signature(metadata.stat()), "directories": directories, "source_orphans": files,
            "no_current_Document_Task_operation_or_unknown_metadata": True}


@contextmanager
def runtime_lock(state):
    """Same own Runtime write.lock/flock; no second lock protocol or Store put."""
    store = c.store_for(state)
    path = Path(store.lock_path)
    canonical(path.parent)
    require(not path.is_symlink(), "Runtime lock symlink refused")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == 0, "invalid Runtime lock file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        current = path.lstat()
        require([current.st_dev, current.st_ino] == [st.st_dev, st.st_ino], "Runtime lock was replaced")
        yield [st.st_dev, st.st_ino]
        current = path.lstat()
        require([current.st_dev, current.st_ino] == [st.st_dev, st.st_ino], "Runtime lock changed while held")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def recover(root, admission_path, admission_sha256, out, *, reconcile=False):
    journal, state, config, admission_ref, intent = bind(root, admission_path, admission_sha256)
    out = canonical(out, exists=False)
    require(not any(out.is_relative_to(canonical(path)) for path in (state["project"], state["root"], state["campaign"])),
            "evidence output must be outside original project/run/resource ledger")
    out.mkdir(parents=True, exist_ok=False)
    with journal.locked(), s.resource_session(root, readonly=True) as (metered, current_state, current_config):
        require(state == current_state and config == current_config, "scope changed during admission")
        # Resource session verifies actual own Python/module/all installed bytes.
        import deck_master
        from deck_master import service
        from deck_master.store import StoreError
        identity = c.save(out / "own-runtime-identity.json", {
            "python": sys.executable, "module": deck_master.__file__, "installation": config["installations"][state["arm"]],
            "verified_by_unchanged_scoped_resource_session": True})
        allowed = expected_orphans(state)
        with runtime_lock(state) as lock_identity:
            before = probe(state, allowed, lock_identity)
            before_ref = c.save(out / "before-probe.json", before)
            query_key = uuid.uuid4().hex
            metered.resources.charge("sdk", 1, {"operation": "service.inputs_show", "query_key": query_key,
                                               "recovery_of": intent["data"]["operation_key"]})
            query_intent = {"query_key": query_key, "operation": "service.inputs_show", "project": state["project"],
                            "recovery_of": intent["data"]["operation_key"], "started_at_UTC": c.now()}
            journal.append("precommit_absence_query_intent", query_intent)
            try:
                returned = service.inputs_show(state["project"])
            except Exception as exc:
                observed = {**query_intent, "finished_at_UTC": c.now(), "error_type": type(exc).__name__,
                            "path": getattr(exc, "path", None), "detail": getattr(exc, "detail", None),
                            "error": str(exc), "traceback": traceback.format_exc()}
                observed_ref = c.save(out / "actual-public-query.json", observed)
                journal.append("precommit_absence_query_observed", {"query_key": query_key, "observation": observed_ref})
                require(isinstance(exc, StoreError) and exc.path == "(document)" and exc.detail == "no current revision",
                        "actual own public query did not establish missing current; remain unresolved")
            else:
                c.save(out / "actual-public-query.json", {**query_intent, "finished_at_UTC": c.now(), "returned": returned})
                raise Error("public inputs exist; never reconcile this as precommit absence")
            after = probe(state, allowed, lock_identity)
            after_ref = c.save(out / "after-probe.json", after)
            require(after == before, "project changed between actual absence probes; remain unresolved")
            c.check_ref(admission_ref)
            # Rebind under all locks; an old diagnostic/admission is no state proof.
            bound, _, _, _, live_intent = bind(root, admission_path, admission_sha256)
            require(live_intent == intent and set(bound.unfinished()) == {intent["data"]["operation_key"]},
                    "original pending intent changed during probe")
            # Check again after rebinding, immediately before the sole append
            # that can settle the old intent. The own Runtime lock is held
            # throughout; its path identity is included in every probe.
            final = probe(state, allowed, lock_identity)
            require(final == before, "project changed before reconciliation; remain unresolved")
            final_ref = c.save(out / "final-probe.json", final)
            record = {"operation_key": intent["data"]["operation_key"], "observed_state": "not_found",
                      "recovery_kind": "actual_no_public_ID_service_create_precommit_absence",
                      "actual_public_operation_id": None, "admission": admission_ref,
                      "runtime_observations": [identity, before_ref, observed_ref, after_ref, final_ref],
                      "recovery_sdk_query_calls": 1, "same_pool_sdk_charge_already_recorded": True,
                      "original_failure_and_source_orphans_retained": True, "automatic_retry": False}
            record_ref = c.save(out / "reconciliation-record.json", record)
            result = c.reconcile(journal, record_ref["path"]) if reconcile else {"status": "diagnosed_only_original_intent_still_pending"}
            result = {**result, "diagnosis": "actual_precommit_absence", "record": record_ref,
                      "reconciliation_performed": reconcile, "original_create_not_retried": True,
                      "resource_pool": s.pool_key(state), "new_actual_public_query_charge": 1,
                      "mapped_arguments_for_separate_explicit_call_only": {**intent["data"]["arguments"], "presentation_mode": "read_alone"}}
            c.save(out / "result.json", result)
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("diagnose", "reconcile"))
    for key in ("run", "admission", "admission-sha256", "out"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    print(json.dumps(recover(args.run, args.admission, args.admission_sha256, args.out,
                             reconcile=args.command == "reconcile"), ensure_ascii=False))


if __name__ == "__main__":
    main()
