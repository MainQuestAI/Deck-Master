#!/usr/bin/env python3
"""Root-observed image transport for fixed RC3 trials; never sends an image call.

Run the admitted installation's absolute Python with -I -B. The seal command is
reserved to Root after observing the literal native tool response. The local
private MAC authenticates that controller observation, not a platform signature.
Coequal malicious Hosts are outside this host-attested assurance. Engineering
registrations and their synthetic signatures never establish native evidence.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time

VERSION = "rc3-final-image-controller.v1"
PROVIDER_ID = "rc3-final-root-observed-image-v1"
FORMAT = "rc3-image-campaign-registration.v1"
ENGINEERING = "SYNTHETIC_ENGINEERING_NOT_NATIVE_NOT_BENCHMARK"
KEY_NAME = ".private-image-controller-key"
OBSERVER = "root_controller_transcription_of_actual_native_tool_response"
SCOPE_KEYS = ("case", "whole_run_id", "repetition", "arm", "page_id")
WORKFLOW_KEYS = ("case", "whole_run_id", "repetition", "arm")


class ImageControllerError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ImageControllerError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "record must be a regular non-symlink file")
    return json.loads(path.read_bytes())


def reference(path):
    path = Path(path).absolute()
    require(not path.is_symlink() and path.is_file(), "reference must be a regular non-symlink file")
    raw = path.read_bytes()
    return {"path": str(path), "sha256": digest(raw), "bytes": len(raw)}


def check_ref(value):
    actual = reference(value["path"])
    require(actual["sha256"] == value["sha256"] and actual["bytes"] == value.get("bytes", actual["bytes"]), "pinned reference bytes changed")
    return actual


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def now_ms():
    return time.time_ns() // 1_000_000


def safe_name(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value), "invalid simple trial identity")
    return value


def sdk_controller(config):
    path = Path(__file__).with_name("controller.py").absolute()
    spec = config["sdk_controller"]
    require(Path(spec["path"]).absolute() == path, "SDK controller must be the pinned sibling file")
    check_ref(spec)
    module_spec = importlib.util.spec_from_file_location("rc3_image_pinned_sdk_controller", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def validate_config(config):
    require(config.get("format") == FORMAT, "wrong image registration format")
    require(config.get("status") in {"ADMITTED", ENGINEERING}, "image trials are not admitted")
    require(config.get("image_controller_sha256") == digest(Path(__file__).read_bytes()), "image controller bytes differ from registration")
    for name in ("protocol", "admission_review"):
        check_ref(config[name])
    trials = config.get("trials")
    require(isinstance(trials, dict) and trials, "freeze nonempty actual image trials before the first call")
    require(type(config.get("batch_call_cap")) is int and config["batch_call_cap"] == len(trials), "batch call cap must equal one per registered trial")
    require(isinstance(config.get("installations"), dict) and config["installations"], "no admitted installations")
    identities = {name: set() for name in ("task_id", "request_id", "authorization_id", "request_ref", "authorization_ref")}
    page_arms = set()
    for trial_id, trial in trials.items():
        safe_name(trial_id)
        require(trial.get("arm") in config["installations"], "trial has no admitted arm")
        require(config["installations"][trial["arm"]].get("adapter_profile") != "A0-public-legacy", "A0 does not expose this formal native adapter; use its own public protocol separately")
        require(all(type(trial.get(key)) is int for key in ("max_calls", "max_candidates", "retries")) and (trial.get("max_calls"), trial.get("max_candidates"), trial.get("retries")) == (1, 1, 0), "each trial requires distinct one-call/one-candidate authority, retry zero")
        require(trial.get("parameters") == {"transparent_background": False}, "this campaign preregisters exact opaque false transparency")
        require(Path(trial["project"]).is_absolute(), "trial must pin its actual absolute project")
        require(trial.get("case") and trial.get("page_id") and trial.get("checkpoint"), "trial needs case/page/checkpoint identity")
        check_ref(trial["checkpoint"])
        require(isinstance(trial.get("whole_run_id"), str) and trial["whole_run_id"] and type(trial.get("repetition")) is int and trial["repetition"] >= 1, "pin the original whole-run and repetition identity before image dispatch")
        pair = tuple(trial[key] for key in SCOPE_KEYS)
        require(pair not in page_arms, "duplicate page/arm trial would repeat the one-call budget")
        page_arms.add(pair)
        for name, seen in identities.items():
            value = canonical(trial[name])
            require(value not in seen, "each trial must own a distinct " + name)
            seen.add(value)
    check_ref(config["global_budget"])
    budget = validate_global_budget(read(config["global_budget"]["path"]))
    require(config["status"] == budget["status"], "engineering and actual global budgets cannot mix")
    require(canonical_root(config.get("global_ledger")) == canonical_root(budget["ledger_root"]), "batch must use the unique ledger root pinned in the original global budget")
    allowed = {tuple(item[key] for key in SCOPE_KEYS) for item in budget["allowed_page_arms"]}
    require(page_arms <= allowed, "batch expands the preregistered global page/arm scope")
    return config


def canonical_root(value):
    require(isinstance(value, str) and value, "pin a nonempty canonical absolute ledger root")
    path = Path(value)
    require(path.is_absolute() and str(path) == str(path.resolve()), "ledger root must be the actual canonical absolute path, without aliases or symlinks")
    return path


def validate_global_budget(budget):
    require(budget.get("format") == "rc3-image-global-budget.v1" and budget.get("status") in {"ADMITTED", ENGINEERING}, "wrong global budget format/status")
    canonical_root(budget.get("ledger_root"))
    allowed = budget.get("allowed_page_arms")
    require(isinstance(allowed, list) and allowed, "global page/arm scope is empty")
    pairs = [tuple(item[key] for key in SCOPE_KEYS) for item in allowed]
    require(all(all(isinstance(item.get(key), str) and item[key] for key in ("case", "whole_run_id", "arm", "page_id")) and type(item.get("repetition")) is int and item["repetition"] >= 1 for item in allowed) and len(pairs) == len(set(pairs)), "global whole-run/repetition/page/arm identities must be explicit and unique")
    require(type(budget.get("total_call_cap")) is int and 1 <= budget["total_call_cap"] <= len(pairs), "invalid global total call cap")
    caps = budget.get("workflow_arm_caps")
    require(isinstance(caps, list) and caps, "preregister whole-workflow/arm call caps")
    keys = [tuple(item[key] for key in WORKFLOW_KEYS) for item in caps]
    require(len(keys) == len(set(keys)) and set(keys) == {tuple(item[key] for key in WORKFLOW_KEYS) for item in allowed}, "whole-workflow/arm cap coverage differs from global page scope")
    require(all(type(item["max_calls"]) is int and 1 <= item["max_calls"] <= sum(all(scope[key] == item[key] for key in WORKFLOW_KEYS) for scope in allowed) for item in caps), "invalid whole-workflow/arm cap")
    for name in ("protocol", "admission_review"):
        check_ref(budget[name])
    return budget


def initialize_global(budget_path, root):
    budget = validate_global_budget(read(budget_path))
    root = canonical_root(str(root))
    require(root == canonical_root(budget["ledger_root"]), "one frozen global budget cannot initialize another ledger root")
    root.mkdir(parents=True, exist_ok=False)
    save(root / "global-budget.json", budget)
    save(root / "budget-origin.json", {"source": reference(budget_path), "canonical_sha256": digest(canonical(budget))})
    return {"status": "GLOBAL_IMAGE_BUDGET_FROZEN", "total_call_cap": budget["total_call_cap"], "automatic_retry": False}


def global_state(config):
    root = canonical_root(config["global_ledger"])
    require(root.is_dir() and not root.is_symlink(), "initialize the shared global image ledger before batches")
    budget = validate_global_budget(read(root / "global-budget.json"))
    require(root == canonical_root(budget["ledger_root"]), "a copied ledger at another root cannot restart the original global budget")
    origin = read(root / "budget-origin.json")
    require(digest(canonical(budget)) == origin["canonical_sha256"] and budget == read(config["global_budget"]["path"]), "global ledger is not the exact preregistered budget")
    require(origin["source"]["sha256"] == config["global_budget"]["sha256"], "global ledger origin differs from profile")
    return root, budget


def bootstrap(config, path):
    sdk = sdk_controller(config)
    if config["status"] == ENGINEERING:
        value = read(path)
        require(value.get("evidence_kind") == ENGINEERING, "engineering bootstrap must label synthetic observations")
        return reference(path)
    sdk.bootstrap(path)
    return reference(path)


def installation(config, arm):
    require(sys.flags.isolated and sys.dont_write_bytecode, "use the admitted absolute Python with -I -B")
    observed = sdk_controller(config).installation(config, arm)
    spec = config["installations"][arm]
    manifest = read(spec["manifest"]["path"])
    require(manifest.get("source_sha") == spec["source_sha"] and manifest.get("source_tree") == spec["source_tree"] and manifest.get("wheel_sha256") == spec["wheel_sha256"], "source/tree/wheel differ from pinned actual manifest")
    return {"source_sha": spec["source_sha"], "source_tree": spec["source_tree"], "wheel_sha256": spec["wheel_sha256"],
            "manifest": deepcopy(spec["manifest"]), "module_file": spec["module_file"], "python": spec["python"], "observed": observed}


@contextmanager
def locked(root):
    with (Path(root) / ".image-controller.lock").open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def load(root):
    root = Path(root).absolute()
    config = validate_config(read(root / "registration.json"))
    origin = read(root / "registration-origin.json")
    require(digest(canonical(config)) == origin["canonical_sha256"], "frozen image registration changed")
    return root, config


def trial_path(root, trial_id):
    return Path(root) / "trials" / safe_name(trial_id)


def key_bytes(root):
    path = Path(root) / KEY_NAME
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == os.getuid(), "controller key must be a private owned mode600 regular file")
        key = os.read(descriptor, 33)
        require(len(key) == 32, "invalid private controller key length")
        return key
    finally:
        os.close(descriptor)


def initialize(config_path, root, bootstrap_path):
    config = validate_config(read(config_path))
    boot = bootstrap(config, bootstrap_path)
    root = Path(root).absolute()
    require(not any(root.is_relative_to(Path(t["project"])) for t in config["trials"].values()), "private controller storage must be outside every project")
    globalroot, _ = global_state(config)
    require(not root.is_relative_to(globalroot) and not globalroot.is_relative_to(root), "batch and shared global ledger must use distinct storage roots")
    require(not any(globalroot.is_relative_to(Path(t["project"])) for t in config["trials"].values()), "global ledger must be outside project storage")
    root.mkdir(parents=True, exist_ok=False)
    save(root / "registration.json", config)
    save(root / "registration-origin.json", {"source": reference(config_path), "canonical_sha256": digest(canonical(config)), "bootstrap": boot, "evidence_kind": config["status"]})
    descriptor = os.open(root / KEY_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(secrets.token_bytes(32))
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": "IMAGE_REGISTRATION_FROZEN", "trial_count": len(config["trials"]), "evidence_kind": config["status"], "actual_calls": 0}


def actual_arguments(project, request):
    value = request["input"]
    require(value["parameters"] == {"transparent_background": False}, "actual frozen parameters differ from this preregistered image campaign")
    args = {"prompt": value["prompt"], "transparent_background": False}
    require(isinstance(args["prompt"], str) and args["prompt"], "empty frozen prompt")
    snapshots, paths = [], []
    objects = (Path(project) / ".deckmaster/objects").resolve(strict=True)
    for item in value["references"]:
        require(item["role"] == "reference", "only literal reference image roles are supported")
        rel = Path(item["file"]["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "reference escapes project")
        path = Path(project) / rel
        require(not path.is_symlink() and path.resolve(strict=True).is_relative_to(objects), "use unchanged same-project immutable original blobs")
        info = path.stat()
        require(stat.S_ISREG(info.st_mode) and digest(path.read_bytes()) == item["file"]["sha256"], "immutable attachment bytes changed")
        paths.append(str(path.absolute()))
        snapshot = {**reference(path), "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns, "inode": info.st_ino, "size": info.st_size}
        after = path.stat()
        require((info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "reference changed while preparing literal arguments")
        snapshots.append(snapshot)
    require(len(paths) <= 16, "native tool reference limit exceeded")
    if paths:
        args["referenced_image_paths"] = paths
    return args, snapshots


def unchanged_references(snapshots):
    for item in snapshots:
        path = Path(item["path"])
        check_ref(item)
        info = path.stat()
        require((info.st_mtime_ns, info.st_ctime_ns, info.st_ino, info.st_size) == (item["mtime_ns"], item["ctime_ns"], item["inode"], item["size"]), "reference timestamp/inode/size changed around dispatch")


def state(config, trial_id, attempt_id):
    from deck_master import eligibility, tasks
    from deck_master.native_image_evidence import image_binding
    from deck_master.store import Store
    trial = config["trials"][trial_id]
    identity = installation(config, trial["arm"])
    store = Store(trial["project"])
    binding, task, attempt, request = image_binding(store, store.load_document(), trial["task_id"], attempt_id)
    require(task["scope_pages"] == [trial["page_id"]] and request["request_id"] == trial["request_id"] and attempt["request_ref"] == trial["request_ref"], "actual Page/Request differs from registered trial")
    authref = (task.get("collaboration_binding") or {}).get("authorization_ref")
    require(authref == trial["authorization_ref"], "Task does not own the registered distinct authorization")
    auth = store.read_object_json(authref)
    require(auth["authorization_id"] == trial["authorization_id"] and auth["max_external_calls"] == 1 and auth["max_candidate_count"] == 1 and auth["status"] == "active", "trial must bind a new active one-call/one-candidate authorization")
    require(len(task["call_allowances"]) == 1 and task["call_allowances"][0]["allowance_id"] == attempt["allowance_id"], "trial cannot acquire a second call allowance")
    require(task["execution_ref"] == attempt["execution_ref"] and tasks.task_inputs_current(store, store.load_document(), task), "actual claim or freshness changed")
    require(task["call_allowances"][0]["state"] == "in_flight" and len(task.get("generation_attempts") or []) == 1, "only the first genuinely in-flight Attempt may prepare/dispatch")
    eligibility.guard(store, store.load_document(), "call.begin", context={"task": task, "allowance_id": attempt["allowance_id"], "targets": {"page_ids": task["scope_pages"]}})
    arguments, refs = actual_arguments(trial["project"], request)
    return store, binding, task, attempt, request, identity, arguments, refs


def prepare(root, trial_id, attempt_id):
    root, config = load(root)
    with locked(root):
        dest = trial_path(root, trial_id)
        require(not dest.exists(), "trial already prepared; no replacement attempt or automatic retry")
        _, binding, _, attempt, _, identity, arguments, refs = state(config, trial_id, attempt_id)
        require(not attempt.get("observations"), "prepare only the first unobserved Attempt")
        value = {"schema": "rc3_final_image_preparation.v1", "trial_id": trial_id, "trial": config["trials"][trial_id], "event_id": "rc3-image-" + secrets.token_hex(16), "provider_id": PROVIDER_ID,
                 "registration_sha256": digest(canonical(config)), "image_controller_sha256": digest(Path(__file__).read_bytes()), "binding": binding,
                 "attempt_id": attempt_id, "allowance_id": attempt["allowance_id"], "installation_identity": identity, "tool_arguments": arguments,
                 "reference_snapshots": refs, "prepared_at_ms": now_ms(), "evidence_kind": config["status"], "platform_model": None, "platform_seed": None, "tokens": None, "price": None}
        save(dest / "preparation.json", value)
        save(dest / "literal-tool-arguments.json", arguments)
        return {"status": "PREPARED_NOT_DISPATCHED", "trial_id": trial_id, "event_id": value["event_id"], "arguments_path": str(dest / "literal-tool-arguments.json")}


def preparation(root, config, trial_id):
    dest = trial_path(root, trial_id)
    value = read(dest / "preparation.json")
    require(value["registration_sha256"] == digest(canonical(config)) and value["trial"] == config["trials"][trial_id] and value["image_controller_sha256"] == digest(Path(__file__).read_bytes()), "preparation/config/controller changed")
    return dest, value


def mark_dispatch(root, trial_id, bootstrap_path):
    root, config = load(root)
    with locked(root):
        dest, p = preparation(root, config, trial_id)
        require(not (dest / "dispatch-mark.json").exists(), "trial was already marked; never resend an uncertain call")
        boot = bootstrap(config, bootstrap_path)
        store, binding, task, attempt, _, identity, args, refs = state(config, trial_id, p["attempt_id"])
        require(binding == p["binding"] and identity == p["installation_identity"] and args == p["tool_arguments"] and refs == p["reference_snapshots"], "bound state or literal inputs changed before dispatch")
        require(next(c for c in task["call_allowances"] if c["allowance_id"] == attempt["allowance_id"])["state"] == "in_flight", "only a genuinely begun in-flight allowance may dispatch")
        count = len(list((root / "trials").glob("*/dispatch-mark.json")))
        require(count < config["batch_call_cap"], "batch image budget exhausted")
        unchanged_references(refs)
        stamp = now_ms()
        require(all(max(item["mtime_ns"], item["ctime_ns"]) // 1_000_000 <= stamp for item in refs), "reference blob was not fixed before dispatch")
        value = {"schema": "rc3_final_image_dispatch.v1", "event_id": p["event_id"], "preparation_sha256": reference(dest / "preparation.json")["sha256"], "arguments_sha256": digest(canonical(args)), "binding_sha256": digest(canonical(binding)), "controller_dispatch_mark_ms": stamp, "timestamp_kind": "controller clock immediately before Root literal tool submission; platform clock unknown", "bootstrap": boot, "budget_ordinal": count + 1, "automatic_retry": False}
        globalroot, budget = global_state(config)
        with locked(globalroot):
            pair = {key: p["trial"][key] for key in SCOPE_KEYS}
            key = digest(canonical(pair))
            previous = [read(path) for path in (globalroot / "dispatches").glob("*.json")]
            require(not (globalroot / "dispatches" / (key + ".json")).exists(), "global page/arm was already dispatched in this or another batch; no retry")
            require(len(previous) < budget["total_call_cap"], "global image call cap exhausted")
            cap = next(item["max_calls"] for item in budget["workflow_arm_caps"] if all(item[key] == pair[key] for key in WORKFLOW_KEYS))
            require(sum(all(item[key] == pair[key] for key in WORKFLOW_KEYS) for item in previous) < cap, "global whole-workflow/arm call cap exhausted")
            rights = {key: p["trial"][key] for key in ("task_id", "request_id", "authorization_id")}
            rights["attempt_id"] = p["attempt_id"]
            require(all(all(item.get(key) != value for item in previous) for key, value in rights.items()), "a Task/Request/authorization/Attempt already dispatched in another batch cannot grant another call")
            value["global_budget_ordinal"] = len(previous) + 1
            value["global_ledger"] = str(globalroot)
            # Reserve globally before publishing the local mark. A crash can
            # block dispatch, never make an uncertain call spendable twice.
            save(globalroot / "dispatches" / (key + ".json"), {**pair, **rights, "event_id": p["event_id"], "batch_root": str(root), "trial_id": trial_id, "dispatch_mark": value})
            save(dest / "dispatch-mark.json", value)
        return value


def validate_callback(config, p, marker, callback):
    require(callback.get("observer_kind") == (ENGINEERING if config["status"] == ENGINEERING else OBSERVER), "callback must be Root's actual native response observation; synthetic callbacks stay engineering")
    require(callback.get("observer_id") == "/root" or config["status"] == ENGINEERING, "only Root seals actual tool observations")
    require(callback.get("tool_name") == "image_gen__imagegen" and callback.get("actual_arguments") == p["tool_arguments"], "callback differs from the exact literal frozen tool call")
    require(marker["event_id"] == p["event_id"] and marker["arguments_sha256"] == digest(canonical(p["tool_arguments"])) and marker["binding_sha256"] == digest(canonical(p["binding"])), "dispatch marker/event/input changed")
    completed = callback.get("controller_observed_completed_at_ms")
    require(type(completed) is int and p["prepared_at_ms"] <= marker["controller_dispatch_mark_ms"] <= completed <= now_ms(), "callback/dispatch clocks are absent or out of order")
    check_ref(callback["native_response"])
    return completed


def authenticated_record(root, dest, p):
    signed = read(dest / "sealed-observation.json")
    record = signed["record"]
    require(hmac.compare_digest(signed["mac_sha256"], hmac.new(key_bytes(root), canonical(record), hashlib.sha256).hexdigest()), "sealed Root observation MAC changed or ordinary JSON has no protected seal")
    require(record["preparation_sha256"] == reference(dest / "preparation.json")["sha256"] and record["event_id"] == p["event_id"], "sealed event was rebound to another preparation")
    return record


def seal(root, trial_id, callback_path, bootstrap_path):
    root, config = load(root)
    with locked(root):
        dest, p = preparation(root, config, trial_id)
        require(not (dest / "sealed-observation.json").exists(), "observation is immutable; do not reseal or replace the first result")
        marker = read(dest / "dispatch-mark.json")
        require(marker["preparation_sha256"] == reference(dest / "preparation.json")["sha256"], "preparation changed after dispatch")
        boot = bootstrap(config, bootstrap_path)
        identity = installation(config, p["trial"]["arm"])
        require(identity == p["installation_identity"], "seal with the exact admitted executing installation")
        callback = read(callback_path)
        completed = validate_callback(config, p, marker, callback)
        outcome = callback.get("completion_status")
        require(outcome in {"completed", "error", "unknown"}, "record the actual native completion status")
        record = {"schema": "rc3_final_root_image_transport.v1", "event_id": p["event_id"], "preparation_sha256": reference(dest / "preparation.json")["sha256"], "callback": callback, "callback_source": reference(callback_path), "bootstrap": boot, "marker": marker, "sealed_at_ms": now_ms(), "evidence_kind": config["status"], "assurance": "host_attested", "platform_signed": False, "human": False, "verified_user": False, "actual_call_outcome": "consumed" if outcome == "completed" else "unknown", "automatic_retry": False, "model": None, "seed": None, "tokens": None, "price": None}
        if outcome == "completed":
            from PIL import Image
            try:
                unchanged_references(p["reference_snapshots"])
            except (OSError, ValueError) as exc:
                record["reference_preservation_error"] = {"type": type(exc).__name__, "detail": str(exc)}
            png_ref = check_ref(callback["original_png"])
            raw = Path(png_ref["path"]).read_bytes()
            dimensions = None
            try:
                with Image.open(io.BytesIO(raw)) as original:
                    require(original.format == "PNG", "preserve the original PNG without re-encoding")
                    dimensions = list(original.size)
                    original.verify()
            except (OSError, ValueError) as exc:
                record["output_validation_error"] = {"type": type(exc).__name__, "detail": str(exc)}
            record["original_png"] = {**png_ref, "dimensions": dimensions}
            record["claims"] = {"provider_id": p["provider_id"], "event_id": p["event_id"], "binding": p["binding"], "tool_name": "image_gen__imagegen", "status": "completed", "issued_at_ms": record["sealed_at_ms"], "expires_at_ms": record["sealed_at_ms"] + 86_400_000, "started_at_ms": marker["controller_dispatch_mark_ms"], "completed_at_ms": completed, "arguments": p["tool_arguments"], "output_sha256": png_ref["sha256"], "invocation_ref": callback.get("platform_invocation_ref")}
        else:
            require(callback.get("original_error") or callback.get("native_response"), "preserve the actual error or uncertain response")
        save(dest / "sealed-observation.json", {"record": record, "mac_sha256": hmac.new(key_bytes(root), canonical(record), hashlib.sha256).hexdigest()})
        return {"status": "SEALED_" + record["actual_call_outcome"].upper(), "evidence_kind": config["status"], "original_png": record.get("original_png"), "automatic_retry": False}


class RootObservedImageProvider:
    authentication = "protected_transport"
    adapter_version = VERSION

    def __init__(self, root, config, trial_id):
        self.root, self.config = Path(root), config
        self.dest, self.p = preparation(self.root, config, trial_id)
        self.provider_id = self.p["provider_id"]

    def health(self):
        try:
            authenticated_record(self.root, self.dest, self.p)
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def fetch(self, event_id):
        require(event_id == self.p["event_id"], "unknown provider event; events cannot be swapped")
        return (self.dest / "sealed-observation.json").read_bytes()

    def verify(self, raw):
        from deck_master.native_image_evidence import NativeImageCompletion
        require(raw == (self.dest / "sealed-observation.json").read_bytes(), "provider returns only the exact sealed raw event")
        record = authenticated_record(self.root, self.dest, self.p)
        require(record["actual_call_outcome"] == "consumed" and "claims" in record, "error/unknown observation is not a native completion")
        require(installation(self.config, self.p["trial"]["arm"]) == self.p["installation_identity"], "actual installation changed")
        require(not record.get("reference_preservation_error") and not record.get("output_validation_error"), "completed call has unusable reference/output evidence; retain consumed facts without native qualification")
        check_ref(record["callback_source"])
        check_ref(record["callback"]["native_response"])
        unchanged_references(self.p["reference_snapshots"])
        png = Path(check_ref(record["original_png"])["path"]).read_bytes()
        return NativeImageCompletion(deepcopy(record["claims"]), png)


def settle(root, trial_id):
    from deck_master import tasks
    from deck_master.native_image_evidence import NativeImageRegistry, NativeImageRuntime
    from deck_master.store import Store
    root, config = load(root)
    with locked(root):
        dest, p = preparation(root, config, trial_id)
        installation(config, p["trial"]["arm"])
        record = authenticated_record(root, dest, p)
        require(not (dest / "settlement.json").exists(), "settlement already recorded; inspect original facts instead of replaying a call")
        store = Store(p["trial"]["project"])
        outcome = record["actual_call_outcome"]
        selector = {"provider_id": p["provider_id"], "event_id": p["event_id"]}
        rejection = None
        registry = NativeImageRegistry()
        registry.register(RootObservedImageProvider(root, config, trial_id))
        with NativeImageRuntime(registry).bound():
            context = None
            if outcome == "consumed":
                try:
                    context = registry.image_context(store, store.load_document(), task_id=p["trial"]["task_id"], attempt_id=p["attempt_id"], selector=selector)
                except Exception as exc:  # facts remain consumed even when current control/observation rejects
                    rejection = {"type": type(exc).__name__, "detail": str(exc)}
                report = {"source": "native_host_image.v1", **selector}
            else:
                report = {"source": "root_controller_completion_uncertain.v1", "event_id": p["event_id"], "binding": p["binding"], "sealed_observation": reference(dest / "sealed-observation.json"), "actual_callback": record["callback"], "evidence_kind": config["status"], "automatic_retry": False}
            try:
                result = tasks.call_settle(store, task_id=p["trial"]["task_id"], allowance_id=p["allowance_id"], attempt_id=p["attempt_id"], outcome=outcome, report_bytes=canonical(report), invocation_ref=record["callback"].get("platform_invocation_ref"), adapter_context=context)
            except Exception as exc:
                error = {"status": "SETTLEMENT_UNCONFIRMED", "type": type(exc).__name__, "detail": str(exc), "context_rejection": rejection, "actual_call_outcome": outcome, "automatic_retry": False, "next_action": "Inspect actual committed allowance/Attempt and recover settlement only; never resend the tool."}
                save(dest / ("settlement-error-" + secrets.token_hex(6) + ".json"), error)
                raise
        value = {"status": "SETTLED", "result": result, "context_rejection": rejection, "actual_call_outcome": outcome, "evidence_kind": config["status"], "automatic_retry": False, "automatic_candidate_acceptance": False, "automatic_adoption": False, "automatic_expansion": False, "model": None, "seed": None, "tokens": None, "price": None}
        save(dest / "settlement.json", value)
        return value


def main():
    require(sys.flags.isolated and sys.dont_write_bytecode, "use an absolute installed Python with -I -B")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("initialize-global")
    p.add_argument("--budget", required=True)
    p.add_argument("--root", required=True)
    p = sub.add_parser("initialize")
    p.add_argument("--config", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--bootstrap", required=True)
    for command in ("prepare", "mark-dispatch", "seal", "settle"):
        p = sub.add_parser(command)
        p.add_argument("--root", required=True)
        p.add_argument("--trial-id", required=True)
        if command == "prepare":
            p.add_argument("--attempt-id", required=True)
        if command in ("mark-dispatch", "seal"):
            p.add_argument("--bootstrap", required=True)
        if command == "seal":
            p.add_argument("--callback", required=True)
    args = parser.parse_args()
    if args.command == "initialize-global":
        result = initialize_global(args.budget, args.root)
    elif args.command == "initialize":
        result = initialize(args.config, args.root, args.bootstrap)
    elif args.command == "prepare":
        result = prepare(args.root, args.trial_id, args.attempt_id)
    elif args.command == "mark-dispatch":
        result = mark_dispatch(args.root, args.trial_id, args.bootstrap)
    elif args.command == "seal":
        result = seal(args.root, args.trial_id, args.callback, args.bootstrap)
    else:
        result = settle(args.root, args.trial_id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
