"""Personal drafts and location. Never writes Document, Tasks, or call facts."""
from __future__ import annotations

import copy
from functools import lru_cache
import time
import uuid

from .local_state import MAX_BODY, LocalStateConflict, LocalStateError, local_lock, project_path, read_json, safe_path, write_json
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import IDENTIFIER, committed_snapshots, load_snapshot
from .store import Store


def digest(value):
    return sha256_bytes(canonical_json_bytes(value))


@lru_cache(maxsize=128)
def _logical_identity(project, current_revision):
    # Genesis UUID distinguishes two projects with the same basename/page IDs,
    # yet remains stable when the same project is moved or copied for recovery.
    root = None
    for doc in committed_snapshots(Store(project)):
        root = doc
    if root is None or root.get("parent_revision_id") is not None:
        raise LocalStateError("project", "project ancestry is incomplete")
    return digest({"project_id": root["project_id"], "genesis_revision": root["revision_id"]})


def context(project):
    path = project_path(project)
    store = Store(path)
    doc = load_snapshot(store)
    return store, doc, _logical_identity(str(path), doc["revision_id"])


def project_info(project):
    store, doc, identity = context(project)
    from .samples import sample_info
    return {"project_id": doc["project_id"], "project_identity": identity,
            "title": doc["task"]["title"], "revision_id": doc["revision_id"],
            "project_format": doc.get("compatibility", {}).get("project_format", "deck_document.v1"),
            "host_execution": "handoff_required", "draft_journal": "ui_draft.v1",
            "sample": sample_info(store.project_root)}


def _directory(store):
    return safe_path(store.project_root, ".deckmaster", "workbench", "drafts")


def _draft_path(store, draft_id):
    if not isinstance(draft_id, str) or not IDENTIFIER.fullmatch(draft_id):
        raise LocalStateError("draft_id", "invalid draft identity")
    return safe_path(_directory(store), draft_id + ".json")


def _base_refs(store, doc, target):
    layer = target["layer"]
    if target["scope"] == "project":
        if target["page_id"] is not None or layer not in ("outline", "materials", "notes"):
            raise LocalStateError("target", "project draft requires a project layer and no page")
        return [doc["content_plan"]] if layer == "outline" and doc.get("content_plan") else []
    entry = next((p for p in doc["pages"] if p["page_id"] == target["page_id"]), None)
    if entry is None or layer in ("outline", "materials"):
        raise LocalStateError("target", "draft page/layer is not in its base revision")
    if layer in ("prepared_prompt", "submitted_prompt"):
        from .workbench import page_lineage
        lineage = page_lineage(store.project_root, entry["page_id"], revision=doc["revision_id"])
        prompts = lineage["prompts"]
        if layer == "submitted_prompt":
            submitted = prompts["submitted"]
            return [submitted["ref"]] if submitted.get("state") == "recorded" else []
        return [p["ref"] for p in prompts["prepared"]]
    slot = {"content": "page", "notes": "page", "original_image": "blueprint", "svg": "svg", "ppt": "ppt_preview"}[layer]
    ref = entry.get(slot)
    if not ref:
        return []
    refs = [ref]
    if slot != "page":
        obj = store.read_object_json(ref)
        validate_schema("artifact", obj)
        if obj.get("page_id") != entry["page_id"] or obj.get("role") != slot:
            raise LocalStateError("base_ref", "artifact belongs to another page")
        if obj.get("file"):
            refs.append(obj["file"])
    return refs


def _validate(store, current, identity, draft):
    validate_schema("ui_draft", draft)
    if draft["project_id"] != current["project_id"] or draft["project_identity"] != identity:
        raise LocalStateError("project_identity", "draft belongs to another project")
    base = load_snapshot(store, draft["base_revision"])
    refs = _base_refs(store, base, draft["target"])
    if (refs and draft["base_ref"] not in refs) or (not refs and draft["base_ref"] is not None):
        raise LocalStateError("base_ref", "draft basis does not belong to this page/layer/revision")
    if draft["base_ref"]:
        store.read_object_bytes(draft["base_ref"])
    pending = draft["pending"]
    if pending and digest(pending["payload"]) != pending["payload_digest"]:
        raise LocalStateError("pending/payload_digest", "pending request bytes do not match their digest")
    if len(canonical_json_bytes(draft)) > MAX_BODY - 1024:
        raise LocalStateError("draft", "draft exceeds the supported size")


def _read(store, draft_id):
    record = read_json(_draft_path(store, draft_id))
    if record is None:
        return None
    validate_schema("ui_draft_record", record)
    if (record["draft"]["draft_id"] != draft_id or record["digest"] != digest(record["draft"])
            or record["etag"] != digest({"sequence": record["updated_sequence"], "digest": record["digest"]})):
        raise LocalStateError("draft", "saved draft identity or hash is invalid")
    return record


def get(project, draft_id):
    store, doc, identity = context(project)
    record = _read(store, draft_id)
    if record:
        _validate(store, doc, identity, record["draft"])
    return {"status": "saved" if record else "not_found", "record": record}


def list_drafts(project):
    store, doc, identity = context(project)
    directory = _directory(store)
    records, errors = [], []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                record = _read(store, path.stem)
                _validate(store, doc, identity, record["draft"])
                records.append(record)
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                errors.append({"draft_id": path.stem, "status": "unreadable"})
    return {"project_id": doc["project_id"], "project_identity": identity, "records": records, "errors": errors}


def save(project, *, draft, expected_etag=None):
    store, doc, identity = context(project)
    _validate(store, doc, identity, draft)
    path = _draft_path(store, draft["draft_id"])
    with local_lock(safe_path(_directory(store), "journal.lock")):
        previous = _read(store, draft["draft_id"])
        content_digest = digest(draft)
        # A lost ACK can be verified/replayed without incrementing the sequence.
        if previous and previous["digest"] == content_digest:
            return {"status": "saved", "replayed": True, "record": previous}
        if previous and any(previous["draft"][key] != draft[key] for key in ("target", "base_revision", "base_ref")):
            raise LocalStateConflict("draft_id", "use a new draft identity for a different target or base")
        if (previous["etag"] if previous else None) != expected_etag:
            raise LocalStateConflict("expected_etag", "draft changed in another window; retain both versions and read the saved draft")
        sequence = previous["updated_sequence"] + 1 if previous else 1
        record = {"schema_version": "ui_draft_record.v1", "draft": copy.deepcopy(draft),
                  "updated_sequence": sequence, "digest": content_digest,
                  "etag": digest({"sequence": sequence, "digest": content_digest})}
        write_json(path, record)
        return {"status": "saved", "replayed": False, "record": record}


def _portable(value, where="draft"):
    # Check structured transport metadata; never silently redact a user's text.
    if isinstance(value, dict):
        forbidden = {"token", "authorization", "x-deck-token", "cookie", "command", "cwd", "absolute_path", "file_path"}
        for key, child in value.items():
            if key.lower() in forbidden:
                raise LocalStateError(where + "/" + key, "recovery files cannot contain credentials, local paths or execution metadata")
            _portable(child, where + "/" + key)
    elif isinstance(value, list):
        for child in value:
            _portable(child, where)
    elif isinstance(value, str) and (value.startswith(("/", "file://", "\\\\")) or ":\\" in value[:4]):
        raise LocalStateError(where, "recovery files cannot contain an absolute local path")


def recovery_file(project, *, draft):
    store, doc, identity = context(project)
    _validate(store, doc, identity, draft)
    _portable(draft)
    return {"schema_version": "ui_draft_recovery.v1", "draft": draft, "digest": digest(draft)}


def import_recovery(project, *, recovery):
    validate_schema("ui_draft_recovery", recovery)
    if len(canonical_json_bytes(recovery)) > MAX_BODY or digest(recovery["draft"]) != recovery["digest"]:
        raise LocalStateError("recovery", "recovery size or hash is invalid")
    draft = copy.deepcopy(recovery["draft"])
    recovery_file(project, draft=draft)  # schema/project/base/portable validation
    try:
        return save(project, draft=draft)
    except LocalStateConflict:
        imported_from = draft["draft_id"]
        draft["draft_id"] = "recovered-" + uuid.uuid4().hex
        return {**save(project, draft=draft), "imported_from": imported_from}


def _position_path(store):
    return safe_path(store.project_root, ".deckmaster", "workbench", "position.json")


def read_position(project):
    store, doc, identity = context(project)
    record = read_json(_position_path(store))
    if record:
        validate_schema("ui_position", record.get("position"))
        if record.get("digest") != digest(record["position"]):
            raise LocalStateError("position", "saved position hash is invalid")
        if record["position"]["project_id"] != doc["project_id"] or record["position"]["project_identity"] != identity:
            raise LocalStateError("position", "saved position belongs to another project")
    return record


def save_position(project, *, position):
    store, doc, identity = context(project)
    validate_schema("ui_position", position)
    if position["project_id"] != doc["project_id"] or position["project_identity"] != identity:
        raise LocalStateError("project_identity", "position belongs to another project")
    base = load_snapshot(store, position["revision"])
    if position["page_id"] is not None and position["page_id"] not in {p["page_id"] for p in base["pages"]}:
        raise LocalStateError("page_id", "position page is not in this revision")
    if position.get("task_id") is not None and position["task_id"] not in {
            store.read_object_json(ref)["task_id"] for ref in base["tasks"]}:
        raise LocalStateError("task_id", "position task is not in this revision")
    path = _position_path(store)
    with local_lock(safe_path(path.parent, "position.lock")):
        record = {"position": position, "digest": digest(position), "updated_at": time.time()}
        write_json(path, record)
    return {"status": "saved", **record}
