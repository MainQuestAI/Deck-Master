"""Snapshot-bound workbench reads. No writes, Host dispatch or reconstructed history.

Document -> ordered slots -> immutable metadata; only page detail loads prompts.
Task and artifact references are facts at the selected revision, not live state.
Candidates and Attempts are projected only from committed writer records.
"""
from __future__ import annotations

import os
import json
import resource
import stat
import threading
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from functools import lru_cache

from .models import canonical_json_bytes, input_alignment, sha256_bytes, validate_ref, validate_schema
from .store import Store

from .snapshots import READ_FAILURES, SLOTS, ReadModelError, load_snapshot


def _copy_json(value):
    """Detach JSON projections without deepcopy's arbitrary-object protocol.

    Stored objects originate in the JSON decoder: their containers are acyclic
    dicts/lists and their leaves are immutable JSON scalars.
    """
    if isinstance(value, dict):
        return {key: _copy_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json(item) for item in value]
    return value


def object_error():
    return {"code": "object_unreadable", "message": "stored object is missing, invalid or damaged",
            "next_action": "read available history; restore the object from a verified project copy"}


# Bounded working set: the 300-page pressure graph has ~2,500 summary
# metadata objects. 2,048 entries made a sequential scan evict every prior hit.
@lru_cache(maxsize=4096)
def _cached_json(root, path, digest, signature):
    # Signature includes ctime/inode as well as size/mtime. Every call checks
    # path safety anew; corrupted/replaced immutable files cannot hide in cache.
    return _read_validated(root, path, digest)


def _read_validated(root, path, digest):
    obj = Store(root).read_object_json({"path": path, "sha256": digest})
    if isinstance(obj, dict):
        kind = {"deck_page_package.v2": "page", "deck_artifact.v1": "artifact",
                "deck_task.v1": "task", "deck_review.v1": "review", "generation_request.v1": "generation_request",
                "generation_attempt.v1": "generation_attempt", "tool_observation.v1": "tool_observation",
                "content_plan.v1": "content_plan"}.get(obj.get("schema_version"))
        if kind:
            validate_schema(kind, obj)
    return obj


@lru_cache(maxsize=4096)
def _cached_overview_metadata(root, path, digest, signature):
    """Keep compact identities separately from the page/task working set.

    Pending candidates and frozen requests add 3,000 objects to a 300-page
    graph. Retaining their full bodies in the shared LRU evicted every task
    between summary scans. Validate immutable bytes once per signature, then
    retain only the fields this projection consumes, never prompt bodies.
    """
    obj = _read_validated(root, path, digest)
    if not isinstance(obj, dict):
        return {"schema_version": None}
    result = {key: _copy_json(obj[key]) for key in (
        "schema_version", "project_id", "task_id", "page_id", "candidate_id",
        "result_kind", "stage", "result_ref") if key in obj}
    if obj.get("schema_version") == "generation_request.v1":
        result["page_id"] = obj["input"]["page"]["page_id"]
    elif obj.get("schema_version") == "deck_blueprint_request.v1":
        prompt = obj.get("prompt")
        result["prompt_valid"] = isinstance(prompt, str) and sha256_bytes(prompt.encode("utf-8")) == obj.get("prompt_sha256")
    return result


class _ReadContext:
    def __init__(self, store, document, *, pin_directories=False):
        self.store, self.document = store, document
        self.objects = {}
        self.metadata_objects = {}
        self.root = str(store.project_root)
        self.directories = (str(store.deck_root), str(store.objects_dir))
        self.pages = {p["page_id"]: p for p in document.get("pages") or []}
        self.pin_directories = (pin_directories and os.name == "posix"
                                and resource.getrlimit(resource.RLIMIT_NOFILE)[0] >= 512)
        self.directory_fds = {}
        self.signatures = {}
        self.clock_tasks = []
        self.read_failed = False

    def close(self):
        for fd in self.directory_fds.values():
            os.close(fd)
        self.directory_fds.clear()

    def _directory_fd(self, relative):
        if relative not in self.directory_fds:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            if not relative:
                fd = os.open(self.root, flags)
            else:
                parent, _, name = relative.rpartition("/")
                fd = os.open(name, flags, dir_fd=self._directory_fd(parent))
            self.directory_fds[relative] = fd
        return self.directory_fds[relative]

    def object_stat(self, ref):
        try:
            value = self._object_stat(ref)
        except READ_FAILURES:
            self.read_failed = True
            raise
        self.signatures[(ref["path"], ref["sha256"])] = (
            value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        return value

    def _object_stat(self, ref):
        # validate_ref fixes the exact objects/<bucket>/<hash>.<ext> grammar.
        # Check every component on every access, including warm cache hits.
        # No repeated realpath traversal of the already-resolved project root.
        validate_ref(ref, where="object")
        if self.pin_directories:
            # Pin checked directory handles for this one snapshot read. Each
            # component is opened with NOFOLLOW; each object is still statted
            # afresh without following symlinks. Directory replacement cannot
            # redirect a later object access through an unchecked ancestor.
            bucket, _, name = ref["path"].rpartition("/")
            value = os.stat(name, dir_fd=self._directory_fd(bucket), follow_symlinks=False)
            if not stat.S_ISREG(value.st_mode):
                raise ValueError("object is not a regular file")
            return value
        if os.name != "posix":
            # Preserve Store's platform-specific resolution (e.g. junctions).
            value = self.store._resolve_object_path(ref["path"]).stat()
            if not stat.S_ISREG(value.st_mode):
                raise ValueError("object is not a regular file")
            return value
        target = self.root + "/" + ref["path"]
        bucket = target.rsplit("/", 1)[0]
        for directory in (*self.directories, bucket):
            if not stat.S_ISDIR(os.lstat(directory).st_mode):
                raise ValueError("unsafe object directory")
        value = os.lstat(target)
        if not stat.S_ISREG(value.st_mode):
            raise ValueError("object is not a regular file")
        return value

    def read(self, ref):
        validate_ref(ref, where="object")
        key = (ref["path"], ref["sha256"])
        if key not in self.objects:
            st = self.object_stat(ref)
            signature = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            try:
                self.objects[key] = _cached_json(self.root, *key, signature)
            except READ_FAILURES:
                self.read_failed = True
                raise
        return self.objects[key]

    def overview_metadata(self, ref):
        key = (ref["path"], ref["sha256"])
        if key not in self.metadata_objects:
            st = self.object_stat(ref)
            signature = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            try:
                self.metadata_objects[key] = _cached_overview_metadata(self.root, *key, signature)
            except READ_FAILURES:
                self.read_failed = True
                raise
        return self.metadata_objects[key]


def _task_rows(ctx):
    rows = []
    for ref in ctx.document.get("tasks") or []:
        try:
            task = ctx.read(ref)
            if task.get("schema_version") != "deck_task.v1":
                raise ValueError("not a task")
            rows.append({"task_id": task["task_id"], "kind": task["kind"],
                         "status": task["status"], "scope_pages": task.get("scope_pages") or [],
                         "execution_ref": task.get("execution_ref"),
                         "attempt_count": len(task.get("generation_attempts") or []),
                         "ref": ref, "instruction": task.get("instruction"), "updated_at": task.get("updated_at"),
                         "result_refs": task.get("result_refs") or [],
                         "request_count": len(task.get("generation_requests") or []),
                         "result_linkage": "known" if task.get("result_refs") else "unknown"})
        except READ_FAILURES:
            rows.append({"ref": ref, "task_id": None, "status": "unreadable",
                         "detail": object_error()["message"], "error": object_error()})
    # Callers must not mutate the shared immutable-object cache via projections.
    return _copy_json(rows)


def tasks_view(project_dir, *, revision=None):
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    return {"project_id": doc["project_id"], "revision_id": doc["revision_id"],
            "tasks": _task_rows(_ReadContext(store, doc))}


def _entry(doc, page_id):
    entry = next((p for p in doc.get("pages") or [] if p.get("page_id") == page_id), None)
    if entry is None:
        raise ReadModelError("page_not_found", "page_id", "page is not present in this snapshot")
    return entry


def page_view(project_dir, page_id, *, revision=None):
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    entry = _entry(doc, page_id)
    try:
        page = store.read_object_json(entry["page"]) if entry.get("page") else None
        if page is not None:
            validate_schema("page", page)
            if page.get("page_id") != page_id:
                raise ValueError("page identity differs")
        error = None
    except READ_FAILURES:
        page, error = None, object_error()
    result = {"project_id": doc["project_id"], "revision_id": doc["revision_id"],
              "page_id": page_id, "page": page,
              "slots": {("content" if slot == "page" else slot): entry.get(slot) for slot in SLOTS}}
    if error:
        result["error"] = error
    return result


def _applicability(ctx, entry, artifact):
    """Report the checks supported by stored bindings, never synthesize a basis."""
    changed, checked, unknown = [], [], []
    generated = (artifact.get("provenance") or {}).get("generated_from_page")
    if generated:
        checked.append("generated_from_page")
        if generated != entry.get("page"):
            changed.append("content")
    for dep in artifact.get("dependencies") or []:
        kind, identity = dep.get("kind"), dep.get("identity", "")
        target = ctx.pages.get(identity.removeprefix("page:"))
        role = {"content": "page", "blueprint": "blueprint", "svg": "svg"}.get(kind)
        if not role:
            unknown.append(kind)
            continue
        checked.append(kind)
        ref = target.get(role) if target else None
        hashes = {ref["sha256"]} if ref else set()
        if ref and role != "page":
            try:
                hashes.add(ctx.read(ref)["file"]["sha256"])
            except READ_FAILURES:
                unknown.append(kind)
                continue
        if dep.get("sha256") not in hashes:
            changed.append(kind)
    return {"status": "basis_changed" if changed else "unknown" if unknown or not checked else "current",
            "changed": sorted(set(changed)), "checked": sorted(set(checked)),
            "unverified": sorted(set(unknown)), "source": "stored_bindings"}


def _stage(ctx, entry, slot):
    ref = entry.get(slot)
    result = {"ref": ref, "scope": "per_page", "existence": "not_generated" if not ref else "recorded",
              "applicability": {"status": "unknown"},
              "adoption": "adopted_at_snapshot" if ref else "none", "relation": "unknown"}
    if not ref:
        return result
    try:
        obj = ctx.read(ref)
        if slot == "page":
            if obj.get("schema_version") != "deck_page_package.v2" or obj.get("page_id") != entry["page_id"]:
                raise ValueError("invalid page")
            result.update(relation="known", applicability={"status": "current"})
            return result
        if (obj.get("schema_version") != "deck_artifact.v1" or obj.get("role") != slot
                or obj.get("page_id") != entry["page_id"]):
            raise ValueError("artifact identity differs")
        validate_ref(obj["file"], where="artifact/file")
        # Byte integrity is checked by /api/file. Summary never hashes large
        # images; absence/path errors can still be shown before image loading.
        ctx.object_stat(obj["file"])
        result.update(file=_copy_json(obj["file"]), media_type=obj["media_type"],
                      relation="known", dependencies=_copy_json(obj.get("dependencies") or []),
                      derived_from=_copy_json(obj.get("derived_from") or []),
                      file_integrity="checked_on_file_read", applicability=_applicability(ctx, entry, obj))
        if slot == "svg_preview":
            result["preview_of"] = {"scope": "per_page", "ref": entry.get("svg"),
                                    "relation": "known" if entry.get("svg") in (obj.get("derived_from") or []) else "unknown"}
        if slot == "ppt_preview":
            deck_ref = (ctx.document.get("outputs") or {}).get("pptx")
            result["preview_of"] = {"scope": "whole_deck", "ref": deck_ref,
                                    "revision_id": ctx.document["revision_id"],
                                    "relation": "derived" if deck_ref else "unknown",
                                    "basis": "co_recorded_snapshot; stored parent remains derived_from"}
    except READ_FAILURES:
        result.update(existence="unreadable", error=object_error(), relation="unknown",
                      applicability={"status": "unknown"})
    return result


def _deck_output(ctx):
    ref = (ctx.document.get("outputs") or {}).get("pptx")
    result = {"ref": ref, "scope": "whole_deck", "revision_id": ctx.document["revision_id"],
              "existence": "recorded" if ref else "not_generated", "relation": "unknown", "ordered_pages": []}
    if not ref:
        return result
    try:
        artifact = ctx.read(ref)
        if artifact.get("schema_version") != "deck_artifact.v1" or artifact.get("role") != "pptx":
            raise ValueError("not a PPT artifact")
        validate_ref(artifact["file"], where="artifact/file")
        ctx.object_stat(artifact["file"])
        deps = [d for d in artifact.get("dependencies") or [] if d.get("kind") == "svg"]
        expected = [(e["page_id"], (e.get("svg") or {}).get("sha256")) for e in ctx.document.get("pages") or []]
        recorded = [(d.get("identity"), d.get("sha256")) for d in deps]
        result.update(file=_copy_json(artifact["file"]), file_integrity="checked_on_file_read",
                      ordered_pages=[{"page_id": pid, "svg_sha256": digest} for pid, digest in recorded],
                      relation="known" if deps else "unknown",
                      applicability="current" if deps and recorded == expected else "basis_changed" if deps else "unknown",
                      basis="artifact.dependencies in stored order")
    except READ_FAILURES:
        result.update(existence="unreadable", error=object_error())
    return result


# B01 actionable overview (INTERFACES "B01：summary增补合同"). Every action is a
# deterministic projection of committed facts; the frontend maps kinds to local
# routes and never receives URLs or commands. No style-deviation action exists:
# without professional review evidence, quality stays "undetermined".
ACTIONS_CAPABILITY = "workbench_actions.v1"

# Ordering tiers: recovery first, then the primary handoff loop, clear
# failures, pending candidates, unreconciled inputs, missing/stale layers, and
# finally general reading. A stale/timeout running task counts as recovery
# (same as run_desk); handoff sits above failures so an awaiting task is never
# buried behind rework, matching run_desk's human_actions ordering.
_ACTION_TIERS = {
    "verify_execution": 1,
    "handoff": 2,
    "inspect_failure": 3, "replan": 3,
    "compare_candidates": 4,
    "reconcile_inputs": 5,
    "prepare_stage": 6, "refresh_stage": 6,
    "review_results": 7, "review_quality": 7,
}


def _action_id(project_id, kind, reason_code, layer, identities):
    basis = "|".join((project_id, kind, reason_code, layer or "-", *sorted(set(identities))))
    return sha256_bytes(basis.encode("utf-8"))[:32]


def _parse_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def _verification_reason(task, *, live, now):
    """Same deterministic checks as run_desk.task_row, with the reason kept
    distinct; staleness is a live-clock fact and is not evaluated for fixed
    revisions so the same revision always reads the same."""
    if any(call.get("state") == "unknown" for call in task.get("call_allowances") or []):
        return "unknown_calls_recorded"
    started = _parse_timestamp(task.get("execution_started_at"))
    wait_basis = started or _parse_timestamp(task.get("updated_at"))
    if live and task.get("status") == "running" and wait_basis and (now - wait_basis).total_seconds() >= 1800:
        return "running_task_stale"
    if task.get("status") == "running" and not task.get("execution_ref"):
        return "running_task_unclaimed"
    return None


def _fact(kind, reason_code, identity, *, page_ids, source_refs, layer=None,
          enabled=True, blocked_reason=None, state="derived", target=None):
    return {"kind": kind, "reason_code": reason_code, "identity": identity, "page_ids": list(page_ids),
            "layer": layer, "source_refs": source_refs, "enabled": enabled,
            "blocked_reason": blocked_reason, "state": state, "target": target}


def _overview_facts(ctx, *, live, now):
    """One bounded pass over committed tasks.

    Produces the summary's slim task rows, per-fact deterministic actions, and
    the per-page prompt indexes. Unreadable JSON task inputs that are not the
    page package itself are attributed to the task's scope pages as potentially
    damaged prepared-prompt records; damage stays local to its own record and
    never crashes a page.
    """
    doc = ctx.document
    page_shas = {(entry.get("page") or {}).get("sha256") for entry in doc.get("pages") or []}
    page_shas.discard(None)
    rows, facts = [], []
    tasks_by_id = {}
    prepared = defaultdict(lambda: {"refs": [], "unreadable": 0})
    frozen = defaultdict(lambda: {"refs": [], "unreadable": 0})
    for ref in doc.get("tasks") or []:
        try:
            task = ctx.read(ref)
            if task.get("schema_version") != "deck_task.v1":
                raise ValueError("not a task")
        except READ_FAILURES:
            rows.append({"ref": ref, "task_id": None, "status": "unreadable",
                         "detail": object_error()["message"], "error": object_error()})
            facts.append(_fact("inspect_failure", "task_unreadable", ref["sha256"],
                               page_ids=[], source_refs=[ref], state="unknown"))
            continue
        tasks_by_id[task["task_id"]] = task
        rows.append({"task_id": task["task_id"], "kind": task["kind"],
                     "status": task["status"], "scope_pages": task.get("scope_pages") or [],
                     "execution_ref": task.get("execution_ref"),
                     "attempt_count": len(task.get("generation_attempts") or [])})
        scope = task.get("scope_pages") or []
        reason = _verification_reason(task, live=live, now=now)
        if live and task.get("status") == "running":
            ctx.clock_tasks.append((task, reason))
        if reason:
            facts.append(_fact("verify_execution", reason, task["task_id"],
                               page_ids=scope, source_refs=[ref]))
        if task["status"] == "failed":
            facts.append(_fact("inspect_failure", "task_failed", task["task_id"],
                               page_ids=scope, source_refs=[ref]))
        elif task["status"] == "superseded":
            facts.append(_fact("replan", "task_superseded", task["task_id"],
                               page_ids=scope, source_refs=[ref]))
        elif task["status"] == "awaiting_host":
            facts.append(_fact("handoff", "task_awaiting_host", task["task_id"],
                               page_ids=scope, source_refs=[ref]))
        elif task["status"] == "completed" and not task.get("candidate_refs") and task.get("result_refs"):
            facts.append(_fact("review_results", "task_results_ready", task["task_id"],
                               page_ids=scope, source_refs=[ref]))
        for input_ref in task.get("inputs") or []:
            try:
                if not str(input_ref.get("path", "")).endswith(".json"):
                    continue
                if input_ref.get("sha256") in page_shas:
                    continue  # the page package itself, never a prompt record
                request = ctx.overview_metadata(input_ref)
                if not isinstance(request, dict):
                    continue
                if request.get("schema_version") != "deck_blueprint_request.v1":
                    continue
                if not request.get("prompt_valid"):
                    raise ValueError("request prompt does not match its recorded hash")
                page_id = request.get("page_id")
                if isinstance(page_id, str):
                    prepared[page_id]["refs"].append(input_ref)
            except READ_FAILURES:
                for page_id in scope:
                    prepared[page_id]["unreadable"] += 1
        for request_ref in task.get("generation_requests") or []:
            try:
                request = ctx.overview_metadata(request_ref)
                if (request.get("schema_version") != "generation_request.v1"
                        or request.get("task_id") != task["task_id"] or request.get("project_id") != doc["project_id"]):
                    raise ValueError("foreign request")
                # Identity/binding only: unlike page_lineage's full record
                # check, this index deliberately skips input_hash so a 300-page
                # deck never re-hashes every frozen request body.
                frozen[request["page_id"]]["refs"].append(request_ref)
            except READ_FAILURES:
                for page_id in scope:
                    frozen[page_id]["unreadable"] += 1
    return {"rows": rows, "facts": facts, "tasks_by_id": tasks_by_id,
            "prepared": prepared, "frozen": frozen}


def _candidate_facts(ctx, tasks_by_id):
    """Count recorded candidates from document facts and project the pending,
    undecided ones as compare_candidates actions. Adoption is matched by the
    committed adoption records first, so adopted candidates are not re-read;
    a damaged or unknown-task candidate stays pending and is isolated."""
    doc = ctx.document
    refs = doc.get("candidates") or []
    adoptions = [a for a in doc.get("candidate_adoptions") or [] if isinstance(a, dict)]
    adopted_shas = {a.get("candidate_ref", {}).get("sha256") for a in adoptions
                    if isinstance(a.get("candidate_ref"), dict)}
    adopted_ids = {a.get("candidate_id") for a in adoptions if isinstance(a.get("candidate_id"), str)}
    # B04: keep_current 决定把候选移出待确认；reopen 恢复待决。决定记录按
    # candidate_id 取最后一条；损坏的决定引用按损伤隔离处理——不做 kept
    # 过滤（候选保持待决可见），不用猜测补齐。
    kept_ids, decisions_readable = set(), True
    for decision_ref in doc.get("candidate_decisions") or []:
        try:
            if not isinstance(decision_ref, dict):
                raise ValueError("not a ref")
            validate_ref(decision_ref, where="document/candidate_decisions")
            record = ctx.read(decision_ref)
            if not isinstance(record, dict) or record.get("schema_version") != "candidate_decision.v1":
                raise ValueError("not a decision")
        except READ_FAILURES + (ValueError,):
            decisions_readable = False
            continue
        kept_ids.discard(record.get("candidate_id"))
        if record.get("decision") == "keep_current":
            kept_ids.add(record.get("candidate_id"))
    if not decisions_readable:
        kept_ids = set()
    facts, adopted, kept, unreadable = [], 0, 0, 0

    def _usable_ref(ref):
        # Snapshot-level damage must stay as isolated as object-level damage:
        # entries that are not valid in-store refs are counted unreadable and
        # never echoed into the public response.
        if not isinstance(ref, dict):
            return False
        try:
            validate_ref(ref, where="document/candidates")
        except READ_FAILURES:
            return False
        return True

    for ref in refs:
        if not _usable_ref(ref):
            unreadable += 1
            facts.append(_fact("compare_candidates", "candidate_pending", str(ref),
                               page_ids=[], source_refs=[], layer=None, enabled=False,
                               blocked_reason="candidate_unreadable", state="unknown"))
            continue
        if ref.get("sha256") in adopted_shas:
            adopted += 1
            continue
        try:
            candidate = ctx.overview_metadata(ref)
            if not isinstance(candidate, dict) or candidate.get("schema_version") != "candidate.v1":
                raise ValueError("not a candidate")
        except READ_FAILURES:
            unreadable += 1
            facts.append(_fact("compare_candidates", "candidate_pending", ref["sha256"],
                               page_ids=[], source_refs=[ref], layer=None, enabled=False,
                               blocked_reason="candidate_unreadable", state="unknown"))
            continue
        if candidate.get("candidate_id") in adopted_ids:
            adopted += 1
            continue
        if candidate.get("candidate_id") in kept_ids:
            kept += 1
            continue
        page_id = candidate.get("page_id")
        page_ids = [page_id] if isinstance(page_id, str) else list(
            (tasks_by_id.get(candidate.get("task_id")) or {}).get("scope_pages") or [])
        stage = candidate.get("stage")
        source_refs = [ref]
        result_ref = candidate.get("result_ref")
        if isinstance(result_ref, dict) and isinstance(result_ref.get("sha256"), str):
            source_refs.append(result_ref)
        candidate_id = candidate.get("candidate_id")
        identity_valid = isinstance(candidate_id, str) and 1 <= len(candidate_id) <= 128
        target_valid = identity_valid and candidate.get("project_id") == doc["project_id"] and (
            candidate.get("result_kind") == "content_update" or page_id in ctx.pages)
        facts.append(_fact("compare_candidates", "candidate_pending", ref["sha256"],
                           page_ids=page_ids, source_refs=source_refs,
                           layer=stage if stage in ("blueprint", "svg") else None,
                           target={"kind": "content_changeset" if candidate.get("result_kind") == "content_update" else "candidate",
                                   "object_id": candidate_id if identity_valid else None, "page_ids": page_ids,
                                   "layer": {"blueprint": "original_image", "svg": "svg", "content": "content"}.get(stage),
                                   "enabled": target_valid,
                                   "blocked_reason": None if target_valid else "target_identity_mismatch"}))
    block = ({"status": "recorded", "count": len(refs), "pending_count": len(refs) - adopted - kept,
              "adopted_count": adopted, "kept_count": kept, "unreadable_count": unreadable} if refs
             else {"status": "not_recorded"})
    return block, facts


def _stage_facts(entry, stages, deck_output):
    """Missing production layers and stale bases are page-scoped facts; an
    unreadable stage is damage to report in stages, never a prepare action."""
    facts = []
    if stages["content"]["existence"] == "recorded" and stages["blueprint"]["existence"] == "not_generated":
        facts.append(_fact("prepare_stage", "stage_missing", entry["page_id"] + ":blueprint",
                           page_ids=[entry["page_id"]], source_refs=[entry["page"]], layer="blueprint"))
    if stages["blueprint"]["existence"] == "recorded" and stages["svg"]["existence"] == "not_generated":
        facts.append(_fact("prepare_stage", "stage_missing", entry["page_id"] + ":svg",
                           page_ids=[entry["page_id"]], source_refs=[entry["blueprint"]], layer="svg"))
    for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
        stage = stages[slot]
        if stage["existence"] == "recorded" and (stage.get("applicability") or {}).get("status") == "basis_changed":
            facts.append(_fact("refresh_stage", "stage_basis_changed", entry["page_id"] + ":" + slot,
                               page_ids=[entry["page_id"]], source_refs=[stage["ref"]], layer=slot))
    if deck_output.get("existence") == "recorded" and deck_output.get("applicability") == "basis_changed":
        facts.append(_fact("refresh_stage", "stage_basis_changed", "deck:pptx",
                           page_ids=[], source_refs=[deck_output["ref"]], layer="pptx"))
    return facts


def _deck_facts(ctx):
    facts = []
    if input_alignment(ctx.document) == "needs_reconciliation":
        plan_ref = ctx.document.get("content_plan")
        facts.append(_fact("reconcile_inputs", "content_needs_reconciliation", "content_basis",
                           page_ids=[], source_refs=[plan_ref] if plan_ref else []))
    if ctx.document.get("reviews"):
        facts.append(_fact("review_quality", "quality_reviews_recorded", "reviews",
                           page_ids=[], source_refs=list(ctx.document["reviews"])))
    return facts


def _merge_refs(ref_groups):
    merged = {}
    for refs in ref_groups:
        for ref in refs:
            if isinstance(ref, dict) and isinstance(ref.get("sha256"), str):
                merged[(ref.get("path"), ref["sha256"])] = ref
    return [_copy_json(merged[key]) for key in sorted(merged)]


def _action_sort_key(action):
    return (_ACTION_TIERS[action["kind"]], action["kind"], action["reason_code"],
            action["layer"] or "", action["page_ids"][0] if action["page_ids"] else "")


def _assemble_actions(ctx, facts, member_index=None):
    """Group per-fact actions by (kind, reason, layer, enabled, blocked, state)
    into the ordered deck list and the per-page attention projections."""
    doc = ctx.document
    groups = defaultdict(list)
    for fact in facts:
        key = (fact["kind"], fact["reason_code"], fact["layer"], fact["enabled"],
               fact["blocked_reason"], fact["state"])
        groups[key].append(fact)
    actions, per_page = [], defaultdict(list)
    for (kind, reason, layer, enabled, blocked, state), members in groups.items():
        actions.append({"action_id": _action_id(doc["project_id"], kind, reason, layer,
                                                [m["identity"] for m in members]),
                        "kind": kind, "page_ids": sorted({pid for m in members for pid in m["page_ids"]}),
                        "layer": layer, "reason_code": reason,
                        "source_refs": _merge_refs(m["source_refs"] for m in members),
                        "enabled": enabled, "blocked_reason": blocked, "state": state,
                        "revision_id": doc["revision_id"]})
        if member_index is not None:
            member_index[actions[-1]["action_id"]] = members
        by_page = defaultdict(list)
        for member in members:
            for page_id in member["page_ids"]:
                by_page[page_id].append(member)
        for page_id, page_members in by_page.items():
            per_page[page_id].append(
                {"action_id": _action_id(doc["project_id"], kind, reason, layer,
                                         [m["identity"] for m in page_members] + ["page:" + page_id]),
                 "kind": kind, "page_ids": [page_id], "layer": layer, "reason_code": reason,
                 "source_refs": _merge_refs(m["source_refs"] for m in page_members),
                 "enabled": enabled, "blocked_reason": blocked, "state": state,
                 "revision_id": doc["revision_id"]})
            if member_index is not None:
                member_index[per_page[page_id][-1]["action_id"]] = page_members
    actions.sort(key=_action_sort_key)
    for items in per_page.values():
        items.sort(key=_action_sort_key)
    return actions, per_page


def _prompt_records_block(index_entry):
    refs = [_copy_json(ref) for ref in index_entry["refs"]]
    unreadable = index_entry["unreadable"]
    if refs:
        value = {"status": "recorded", "count": len(refs), "refs": refs}
        if unreadable:
            value["unreadable_count"] = unreadable
        return value
    if unreadable:
        return {"status": "unreadable", "unreadable_count": unreadable, "error": object_error()}
    return {"status": "not_recorded"}


def _prompt_summary(ctx, entry, prepared, frozen):
    """Metadata-only prompt overview: index refs, never prompt bodies. A missing
    frozen record is never filled from drafts or configuration."""
    page_id = entry["page_id"]
    empty = {"refs": [], "unreadable": 0}
    submitted = {"status": "not_recorded"}
    if entry.get("blueprint"):
        try:
            artifact = ctx.read(entry["blueprint"])
            ref = (artifact.get("provenance") or {}).get("submitted_prompt")
            if ref:
                validate_ref(ref, where="artifact/provenance.submitted_prompt")
                ctx.object_stat(ref)
                submitted = {"status": "recorded", "ref": _copy_json(ref),
                             "observer": "host_reported", "basis": "artifact.provenance.submitted_prompt"}
        except READ_FAILURES:
            submitted = {"status": "unreadable", "error": object_error()}
    return {"prepared": _prompt_records_block(prepared.get(page_id) or empty),
            "frozen": _prompt_records_block(frozen.get(page_id) or empty),
            "submitted": submitted}


def _next_actions_block(ctx, actions):
    if actions:
        return {"status": "recorded", "actions": actions}
    page_ids = [entry["page_id"] for entry in ctx.document.get("pages") or []]
    return {"status": "not_recorded", "reason_code": "no_pending_actions",
            "readable": {"scope": "deck_pages" if page_ids else "no_content", "page_ids": page_ids}}


_summary_cache = OrderedDict()
_summary_cache_lock = threading.Lock()


def workbench_summary(project_dir, *, revision=None):
    return _workbench_summary(project_dir, revision=revision, encoded=False)


def workbench_summary_json(project_dir, *, revision=None):
    """Same guarded snapshot, already encoded for the HTTP transport."""
    return _workbench_summary(project_dir, revision=revision, encoded=True)


def _workbench_summary(project_dir, *, revision, encoded):
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    ctx = _ReadContext(store, doc, pin_directories=True)
    try:
        # The revision file is read and checked by load_snapshot on every call.
        # Hash its actual content too: a changed file retaining the same revision
        # id must not reuse an old projection. File guards below cover every
        # referenced object, including prepared/frozen metadata and image paths.
        key = (ctx.root, sha256_bytes(canonical_json_bytes(doc)), revision)
        with _summary_cache_lock:
            cached = _summary_cache.get(key)
        if cached is not None:
            now = datetime.now(timezone.utc)
            unchanged = all(_verification_reason(task, live=revision is None, now=now) == reason
                            for task, reason in cached["clock_tasks"])
            try:
                if unchanged:
                    for (path, digest), signature in cached["signatures"].items():
                        ctx.object_stat({"path": path, "sha256": digest})
                        if ctx.signatures[(path, digest)] != signature:
                            unchanged = False
                            break
            except READ_FAILURES:
                unchanged = False
            if unchanged:
                return cached["json"] if encoded else json.loads(cached["json"])
        result = _summary(ctx, revision=revision)
        serialized = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        # Never cache partial failures: missing/corrupt objects must be retried
        # so an independent repair is visible without a business revision.
        if not ctx.read_failed:
            entry = {"json": serialized,
                     "signatures": ctx.signatures, "clock_tasks": ctx.clock_tasks}
            with _summary_cache_lock:
                _summary_cache[key] = entry
                _summary_cache.move_to_end(key)
                while len(_summary_cache) > 4:
                    _summary_cache.popitem(last=False)
        return serialized if encoded else result
    finally:
        ctx.close()


def _summary(ctx, *, revision, member_index=None):
    from .content_plan import projection
    store, doc = ctx.store, ctx.document
    now = datetime.now(timezone.utc)
    overview = _overview_facts(ctx, live=revision is None, now=now)
    candidates_block, candidate_facts = _candidate_facts(ctx, overview["tasks_by_id"])
    tasks = overview["rows"]
    by_page = defaultdict(list)
    counts = Counter()
    for task in tasks:
        counts[task["status"]] += 1
        row = {k: task.get(k) for k in ("task_id", "kind", "status", "execution_ref")}
        for page_id in set(task.get("scope_pages") or []):
            by_page[page_id].append(row)
    deck_output = _deck_output(ctx)
    facts = [*overview["facts"], *candidate_facts, *_deck_facts(ctx)]
    pages = []
    for entry in doc.get("pages") or []:
        stages = {("content" if s == "page" else s): _stage(ctx, entry, s) for s in SLOTS}
        title = None
        if stages["content"]["existence"] == "recorded":
            title = (ctx.read(entry["page"]).get("customer_visible") or {}).get("title")
        facts.extend(_stage_facts(entry, stages, deck_output))
        pages.append({"page_id": entry["page_id"], "title": title, "stages": stages,
                      "execution": _copy_json(by_page[entry["page_id"]]),
                      "prompt_summary": _prompt_summary(ctx, entry, overview["prepared"], overview["frozen"]),
                      "attention": {"status": "not_recorded"}})
    actions, per_page = _assemble_actions(ctx, facts, member_index)
    for page in pages:
        items = per_page.get(page["page_id"])
        if items:
            page["attention"] = {"status": "recorded", "items": items}
    return {"format": "workbench_summary.v1", "project_id": doc["project_id"],
            "revision_id": doc["revision_id"], "requested_revision": revision,
            "snapshot_mode": "fixed" if revision is not None else "current",
            "page_count": len(pages), "pages": pages,
            "task_counts": dict(sorted(counts.items())),
            "unreadable_tasks": sum(t["status"] == "unreadable" for t in tasks),
            "outputs": {"pptx": deck_output}, "input_alignment": input_alignment(doc),
            "content_plan": projection(store, doc, reader=ctx.read, summary=True, schema_validated=True),
            "quality": {"status": "detail_required", "review_refs": doc.get("reviews") or []},
            "candidates": candidates_block,
            "attempts": {"status": "recorded", "count": sum(t.get("attempt_count", 0) for t in tasks)}
            if any(t.get("attempt_count") for t in tasks) else {"status": "not_recorded"},
            "next_actions": _next_actions_block(ctx, actions),
            "evidence_level": "engineering"}


def _fact_targets(ctx, fact):
    """Resolve explicit fact semantics, never decode a hash into an identity."""
    target = fact.get("target")
    if target is not None:
        yield {**target, "status": fact["state"]}
        return
    kind, reason = fact["kind"], fact["reason_code"]
    if kind == "compare_candidates":
        yield {"kind": "candidate", "object_id": None, "page_ids": fact["page_ids"], "layer": None,
               "status": "unreadable", "enabled": False, "blocked_reason": "candidate_unreadable"}
    elif kind in ("verify_execution", "handoff", "inspect_failure", "replan", "review_results"):
        unreadable = reason == "task_unreadable"
        yield {"kind": "task", "object_id": None if unreadable else fact["identity"],
               "page_ids": fact["page_ids"], "layer": None,
               "status": "unreadable" if unreadable else reason,
               "enabled": not unreadable, "blocked_reason": "task_unreadable" if unreadable else None}
    elif kind in ("prepare_stage", "refresh_stage"):
        layer = {"blueprint": "original_image", "svg": "svg", "svg_preview": "svg",
                 "ppt_preview": "ppt", "pptx": "ppt"}.get(fact["layer"])
        for page_id in fact["page_ids"] or [None]:
            yield {"kind": "page_layer" if page_id else "review", "object_id": page_id,
                   "page_ids": [page_id] if page_id else [], "layer": layer,
                   "status": reason, "enabled": True, "blocked_reason": None}
    elif kind == "reconcile_inputs":
        yield {"kind": "content_reconciliation", "object_id": None, "page_ids": [], "layer": "content",
               "status": reason, "enabled": True, "blocked_reason": None}
    elif kind == "review_quality":
        for ref in fact["source_refs"]:
            try:
                review = ctx.read(ref)
                validate_schema("review", review)
                yield {"kind": "review", "object_id": review["review_id"], "page_ids": [], "layer": None,
                       "status": review["status"], "enabled": True, "blocked_reason": None,
                       "member_identity": ref["sha256"]}
            except READ_FAILURES:
                yield {"kind": "review", "object_id": None, "page_ids": [], "layer": None,
                       "status": "unreadable", "enabled": False, "blocked_reason": "review_unreadable",
                       "member_identity": ref["sha256"]}


def action_targets(project_dir, action_id, *, revision, limit=30, offset=0):
    """A fixed-snapshot, bounded page of an action's members. No history scan."""
    import re
    if not isinstance(revision, str) or not revision:
        raise ReadModelError("invalid_revision", "revision", "one fixed revision is required", http_status=400)
    if (type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0):
        raise ReadModelError("invalid_action_query", "pagination", "limit must be 1–100 and offset nonnegative", http_status=400)
    if not isinstance(action_id, str) or not re.fullmatch(r"[a-f0-9]{32}", action_id):
        raise ReadModelError("action_not_found", "action_id", "action is not present in this snapshot", http_status=404)
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    ctx, members = _ReadContext(store, doc), {}
    _summary(ctx, revision=revision, member_index=members)
    # A live clock warning has no historical truth. It may resolve while the
    # requested snapshot is still current, but never invent it for old history.
    if action_id not in members and doc["revision_id"] == store.current_revision_id():
        _summary(ctx, revision=None, member_index=members)
    if action_id not in members:
        raise ReadModelError("action_not_found", "action_id", "action is not present in this snapshot", http_status=404)
    targets, seen = [], set()
    for fact in members[action_id]:
        for target in _fact_targets(ctx, fact):
            identity = target.pop("member_identity", fact["identity"])
            key = (target["kind"], target["object_id"] or identity, tuple(target["page_ids"]), target["layer"])
            if key in seen:
                continue
            seen.add(key)
            targets.append({"target_id": sha256_bytes(repr(key).encode())[:32], **target})
    result = {"schema_version": "action_targets.v1", "project_id": doc["project_id"],
              "revision_id": doc["revision_id"], "action_id": action_id, "total": len(targets),
              "limit": limit, "offset": offset, "targets": targets[offset:offset + limit]}
    validate_schema("action_targets", result)
    return result


def _prompt_records(ctx, entry, artifact):
    prepared, errors = [], []
    blueprint_ref = entry.get("blueprint")
    invocation = (artifact.get("provenance") or {}).get("invocation_ref") if artifact else None
    for task_ref in ctx.document.get("tasks") or []:
        try:
            task = ctx.read(task_ref)
            if task.get("schema_version") != "deck_task.v1":
                raise ValueError("not a task")
            if task.get("kind") != "blueprint" or entry["page_id"] not in (task.get("scope_pages") or []):
                continue
        except READ_FAILURES:
            errors.append(object_error())
            continue
        for ref in task.get("inputs") or []:
            try:
                if not ref["path"].endswith(".json"):
                    continue
                request = ctx.read(ref)
                if not isinstance(request, dict):
                    continue
                if request.get("schema_version") != "deck_blueprint_request.v1" or request.get("page_id") != entry["page_id"]:
                    continue
                if not isinstance(request.get("prompt"), str) or sha256_bytes(request["prompt"].encode("utf-8")) != request.get("prompt_sha256"):
                    raise ValueError("request prompt does not match its recorded hash")
                linked = bool(blueprint_ref and blueprint_ref in (task.get("result_refs") or []))
                call_link = bool(invocation and any(c.get("invocation_ref") == invocation for c in task.get("call_allowances") or []))
                from .text_sources import prompt_sections
                prepared.append({"ref": ref, "sections": prompt_sections(request), "task_ref": task_ref, "task_id": task["task_id"],
                                 "dispatch_revision": task.get("dispatch_revision"),
                                 "text": request.get("prompt"), "prompt_sha256": request.get("prompt_sha256"),
                                 "state": "prepared", "observer": "core_frozen",
                                 "output_relation": "known" if linked else "derived" if call_link else "unknown",
                                 "basis": "task_result_ref" if linked else "invocation_ref" if call_link else "task_scope_only"})
            except READ_FAILURES:
                # One lost Page/other input must not hide the separate frozen
                # request still present in this task's remaining inputs.
                errors.append(object_error())
    actual_ref = (artifact.get("provenance") or {}).get("submitted_prompt") if artifact else None
    actual = {"state": "not_recorded", "ref": actual_ref, "observer": "unknown", "text": None}
    if artifact is None and entry.get("blueprint"):
        actual.update(state="unreadable", error=object_error())
    if actual_ref:
        try:
            text = ctx.store.read_object_bytes(actual_ref).decode("utf-8")
            actual.update(state="recorded", observer="host_reported", text=text,
                          relation="known", basis="artifact.provenance.submitted_prompt")
        except READ_FAILURES:
            actual.update(state="unreadable", error=object_error())
    return {"prepared": prepared, "submitted": actual, "errors": errors,
            "parameters": {"status": "not_recorded"}, "attempt": {"status": "not_recorded"}}


def page_lineage(project_dir, page_id, *, revision=None):
    from .content_plan import projection
    from . import production_detail, text_sources
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    entry = _entry(doc, page_id)
    ctx = _ReadContext(store, doc)
    stages = {("content" if s == "page" else s): _stage(ctx, entry, s) for s in SLOTS}
    page, blueprint = None, None
    if stages["content"]["existence"] == "recorded":
        page = _copy_json(ctx.read(entry["page"]))
    if entry.get("blueprint"):
        try:
            obj = ctx.read(entry["blueprint"])
            if (obj.get("schema_version") != "deck_artifact.v1" or obj.get("role") != "blueprint"
                    or obj.get("page_id") != page_id):
                raise ValueError("blueprint identity differs")
            # A missing image must not hide a separately stored prompt.
            blueprint = obj
        except READ_FAILURES:
            pass
    prompts = _prompt_records(ctx, entry, blueprint)
    generation = _generation_records(ctx, entry, blueprint)
    if generation.get("adopted_observation"):
        observed = generation["adopted_observation"]
        if prompts["submitted"]["text"] == observed["submitted"]["prompt"]:
            prompts["submitted"].update(observer="tool_observed", basis="native_tool_observation")
    deck_output = _deck_output(ctx)
    return {"format": "page_lineage.v1", "project_id": doc["project_id"],
            "revision_id": doc["revision_id"], "requested_revision": revision,
            "page_id": page_id, "page": page, "stages": stages,
            "sources": {"citations": (page or {}).get("citations") or [], "relation": "known" if (page or {}).get("citations") else "unknown"},
            "content_plan": projection(store, doc, reader=ctx.read, page_id=page_id),
            "prompts": prompts, "generation": generation,
            "tasks": [t for t in _task_rows(ctx) if page_id in (t.get("scope_pages") or [])],
            "deck_output": deck_output, "production": production_detail.projection(ctx, entry, deck_output),
            "text_sources": text_sources.projection(entry, page, prompts, generation), "evidence_level": "engineering"}


def _generation_records(ctx, entry, artifact):
    from .generation import comparison
    requests, attempts, errors = [], [], []
    adopted = None
    provenance = (artifact or {}).get("provenance") or {}
    for task_ref in ctx.document["tasks"]:
        try:
            task = ctx.read(task_ref)
            if task.get("protocol_version") != "generation.v1" or entry["page_id"] not in task.get("scope_pages", []):
                continue
            request_map = {}
            for ref in task.get("generation_requests") or []:
                request = ctx.read(ref)
                if (request["task_id"] != task["task_id"] or request["project_id"] != ctx.document["project_id"]
                        or request["input"]["page"]["page_id"] != entry["page_id"]):
                    raise ValueError("foreign request")
                from .models import canonical_json_bytes
                if request["input_hash"] != sha256_bytes(canonical_json_bytes(request["input"])):
                    raise ValueError("invalid frozen input hash")
                requests.append({"ref": ref, **_copy_json(request), "observer": "core_frozen"})
                request_map[ref["sha256"]] = request
            for ref in task.get("generation_attempts") or []:
                attempt = ctx.read(ref)
                if attempt["task_id"] != task["task_id"] or attempt["project_id"] != ctx.document["project_id"]:
                    raise ValueError("foreign attempt")
                request = request_map[attempt["request_ref"]["sha256"]]
                observations = []
                for evidence_ref in attempt["observations"]:
                    observation = ctx.read(evidence_ref)
                    observations.append({"ref": evidence_ref, **_copy_json(observation), "comparison": comparison(request, observation)})
                    if (provenance.get("generation_request") == attempt["request_ref"]
                            and provenance.get("generation_attempt") is not None
                            and ctx.read(provenance["generation_attempt"]).get("attempt_id") == attempt["attempt_id"]
                            and observation.get("observer") == "tool_observed"
                            and observation.get("collector") == "codex-session-image.v1"
                            and (observation.get("output") or {}).get("sha256") == (artifact.get("file") or {}).get("sha256")):
                        adopted = _copy_json(observation)
                call = next((c for c in task["call_allowances"] if c["allowance_id"] == attempt["allowance_id"]), None)
                if call is None:
                    raise ValueError("attempt allowance is missing")
                attempts.append({"ref": ref, **_copy_json(attempt), "call": _copy_json(call), "observations": observations})
        except READ_FAILURES:
            errors.append(object_error())
    request_ref = provenance.get("generation_request")
    attempt_ref = provenance.get("generation_attempt")
    bound_request = next((r for r in requests if r["ref"] == request_ref), None)
    bound_attempt = next((a for a in attempts if a["ref"] == attempt_ref and a["request_ref"] == request_ref), None)
    return {"requests": requests, "attempts": attempts, "errors": errors, "adopted_observation": adopted,
            "adopted_request_ref": _copy_json(request_ref) if bound_request else None,
            "adopted_attempt_ref": _copy_json(attempt_ref) if bound_request and bound_attempt else None}
