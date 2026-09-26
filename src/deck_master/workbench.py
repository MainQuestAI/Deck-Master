"""Snapshot-bound workbench reads. No writes, Host dispatch or reconstructed history.

Document -> ordered slots -> immutable metadata; only page detail loads prompts.
Task and artifact references are facts at the selected revision, not live state.
Candidates/Attempts are deliberately not invented before their writer exists.
"""
from __future__ import annotations

import copy
from functools import lru_cache

from .models import input_alignment, sha256_bytes, validate_ref, validate_schema
from .store import Store

from .snapshots import READ_FAILURES, SLOTS, ReadModelError, load_snapshot


def object_error():
    return {"code": "object_unreadable", "message": "stored object is missing, invalid or damaged",
            "next_action": "read available history; restore the object from a verified project copy"}


@lru_cache(maxsize=2048)
def _cached_json(root, path, digest, signature):
    # Signature includes ctime/inode as well as size/mtime. Every call checks
    # path safety anew; corrupted/replaced immutable files cannot hide in cache.
    obj = Store(root).read_object_json({"path": path, "sha256": digest})
    if isinstance(obj, dict):
        kind = {"deck_page_package.v2": "page", "deck_artifact.v1": "artifact",
                "deck_task.v1": "task", "deck_review.v1": "review", "generation_request.v1": "generation_request",
                "generation_attempt.v1": "generation_attempt", "tool_observation.v1": "tool_observation"}.get(obj.get("schema_version"))
        if kind:
            validate_schema(kind, obj)
    return obj


class _ReadContext:
    def __init__(self, store, document):
        self.store, self.document = store, document
        self.objects = {}
        self.pages = {p["page_id"]: p for p in document.get("pages") or []}

    def read(self, ref):
        validate_ref(ref, where="object")
        key = (ref["path"], ref["sha256"])
        if key not in self.objects:
            target = self.store._resolve_object_path(ref["path"])
            st = target.stat()
            signature = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            self.objects[key] = _cached_json(str(self.store.project_root), *key, signature)
        return self.objects[key]


def _task_rows(ctx):
    rows = []
    for ref in ctx.document.get("tasks") or []:
        try:
            task = ctx.read(ref)
            if task.get("schema_version") != "deck_task.v1":
                raise ValueError("not a task")
            rows.append({"ref": ref, "task_id": task["task_id"], "kind": task["kind"],
                         "status": task["status"], "scope_pages": task.get("scope_pages") or [],
                         "instruction": task.get("instruction"), "updated_at": task.get("updated_at"),
                         "execution_ref": task.get("execution_ref"),
                         "result_refs": task.get("result_refs") or [],
                         "request_count": len(task.get("generation_requests") or []),
                         "attempt_count": len(task.get("generation_attempts") or []),
                         "result_linkage": "known" if task.get("result_refs") else "unknown"})
        except READ_FAILURES:
            rows.append({"ref": ref, "task_id": None, "status": "unreadable",
                         "detail": object_error()["message"], "error": object_error()})
    # Callers must not mutate the shared immutable-object cache via projections.
    return copy.deepcopy(rows)


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
        if not ctx.store._resolve_object_path(obj["file"]["path"]).is_file():
            raise ValueError("missing artifact file")
        result.update(file=copy.deepcopy(obj["file"]), media_type=obj["media_type"],
                      relation="known", dependencies=copy.deepcopy(obj.get("dependencies") or []),
                      derived_from=copy.deepcopy(obj.get("derived_from") or []),
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
        if not ctx.store._resolve_object_path(artifact["file"]["path"]).is_file():
            raise ValueError("missing PPT file")
        deps = [d for d in artifact.get("dependencies") or [] if d.get("kind") == "svg"]
        expected = [(e["page_id"], (e.get("svg") or {}).get("sha256")) for e in ctx.document.get("pages") or []]
        recorded = [(d.get("identity"), d.get("sha256")) for d in deps]
        result.update(file=copy.deepcopy(artifact["file"]), file_integrity="checked_on_file_read",
                      ordered_pages=[{"page_id": pid, "svg_sha256": digest} for pid, digest in recorded],
                      relation="known" if deps else "unknown",
                      applicability="current" if deps and recorded == expected else "basis_changed" if deps else "unknown",
                      basis="artifact.dependencies in stored order")
    except READ_FAILURES:
        result.update(existence="unreadable", error=object_error())
    return result


def workbench_summary(project_dir, *, revision=None):
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    ctx = _ReadContext(store, doc)
    tasks = _task_rows(ctx)
    pages = []
    for entry in doc.get("pages") or []:
        stages = {("content" if s == "page" else s): _stage(ctx, entry, s) for s in SLOTS}
        title = None
        if stages["content"]["existence"] == "recorded":
            title = (ctx.read(entry["page"]).get("customer_visible") or {}).get("title")
        pages.append({"page_id": entry["page_id"], "title": title, "stages": stages,
                      "execution": [{k: t.get(k) for k in ("task_id", "kind", "status", "execution_ref")}
                                    for t in tasks if entry["page_id"] in (t.get("scope_pages") or [])],
                      "attention": {"status": "not_recorded"}})
    return {"format": "workbench_summary.v1", "project_id": doc["project_id"],
            "revision_id": doc["revision_id"], "requested_revision": revision,
            "snapshot_mode": "fixed" if revision is not None else "current",
            "page_count": len(pages), "pages": pages,
            "task_counts": {status: sum(t["status"] == status for t in tasks) for status in sorted({t["status"] for t in tasks})},
            "unreadable_tasks": sum(t["status"] == "unreadable" for t in tasks),
            "outputs": {"pptx": _deck_output(ctx)}, "input_alignment": input_alignment(doc),
            "quality": {"status": "detail_required", "review_refs": doc.get("reviews") or []},
            "candidates": {"status": "not_recorded"},
            "attempts": {"status": "recorded", "count": sum(t.get("attempt_count", 0) for t in tasks)}
            if any(t.get("attempt_count") for t in tasks) else {"status": "not_recorded"},
            "evidence_level": "engineering"}


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
                prepared.append({"ref": ref, "task_ref": task_ref, "task_id": task["task_id"],
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
    store = Store(project_dir)
    doc = load_snapshot(store, revision)
    entry = _entry(doc, page_id)
    ctx = _ReadContext(store, doc)
    stages = {("content" if s == "page" else s): _stage(ctx, entry, s) for s in SLOTS}
    page, blueprint = None, None
    if stages["content"]["existence"] == "recorded":
        page = copy.deepcopy(ctx.read(entry["page"]))
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
    return {"format": "page_lineage.v1", "project_id": doc["project_id"],
            "revision_id": doc["revision_id"], "requested_revision": revision,
            "page_id": page_id, "page": page, "stages": stages,
            "sources": {"citations": (page or {}).get("citations") or [], "relation": "known" if (page or {}).get("citations") else "unknown"},
            "prompts": prompts, "generation": generation,
            "tasks": [t for t in _task_rows(ctx) if page_id in (t.get("scope_pages") or [])],
            "deck_output": _deck_output(ctx), "evidence_level": "engineering"}


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
                requests.append({"ref": ref, **copy.deepcopy(request), "observer": "core_frozen"})
                request_map[ref["sha256"]] = request
            for ref in task.get("generation_attempts") or []:
                attempt = ctx.read(ref)
                if attempt["task_id"] != task["task_id"] or attempt["project_id"] != ctx.document["project_id"]:
                    raise ValueError("foreign attempt")
                request = request_map[attempt["request_ref"]["sha256"]]
                observations = []
                for evidence_ref in attempt["observations"]:
                    observation = ctx.read(evidence_ref)
                    observations.append({"ref": evidence_ref, **copy.deepcopy(observation), "comparison": comparison(request, observation)})
                    if (provenance.get("generation_request") == attempt["request_ref"]
                            and provenance.get("generation_attempt") is not None
                            and ctx.read(provenance["generation_attempt"]).get("attempt_id") == attempt["attempt_id"]
                            and observation.get("observer") == "tool_observed"
                            and observation.get("collector") == "codex-session-image.v1"
                            and (observation.get("output") or {}).get("sha256") == (artifact.get("file") or {}).get("sha256")):
                        adopted = copy.deepcopy(observation)
                call = next((c for c in task["call_allowances"] if c["allowance_id"] == attempt["allowance_id"]), None)
                if call is None:
                    raise ValueError("attempt allowance is missing")
                attempts.append({"ref": ref, **copy.deepcopy(attempt), "call": copy.deepcopy(call), "observations": observations})
        except READ_FAILURES:
            errors.append(object_error())
    return {"requests": requests, "attempts": attempts, "errors": errors, "adopted_observation": adopted}
