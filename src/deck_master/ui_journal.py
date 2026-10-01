"""Personal drafts and location. Never writes Document, Tasks, or call facts."""
from __future__ import annotations

import copy
import time
import uuid

import json

from .local_state import MAX_BODY, LocalStateConflict, LocalStateError, local_lock, project_path, read_json, safe_path, write_json
from .models import canonical_json_bytes, sha256_bytes, validate_schema
from .snapshots import IDENTIFIER, committed_headers, load_snapshot
from .tasks import _utc_now_iso
from .store import Store


def digest(value):
    return sha256_bytes(canonical_json_bytes(value))


def _logical_identity(project, current_revision):
    # Genesis UUID distinguishes two projects with the same basename/page IDs,
    # yet remains stable when the same project is moved or copied for recovery.
    root = None
    for header in committed_headers(Store(project), head=current_revision):
        root = header
    if root is None or root[2] is not None:
        raise LocalStateError("project", "project ancestry is incomplete")
    return digest({"project_id": root[1], "genesis_revision": root[0]})


def context(project):
    path = project_path(project)
    store = Store(path)
    doc = load_snapshot(store)
    return store, doc, _logical_identity(str(path), doc["revision_id"])


# B02 (INTERFACES "B02：有效能力与主入口"): what the serving core supports and
# what THIS project can do right now are separate facts. The projection below
# never replaces the write gates - every write endpoint keeps validating on
# its own and must not trust this list.
CORE_READERS = ("deckmaster-current.v1", "deckmaster-current.v2")

# (action, capability the serving core must advertise). "drafts" lives in the
# personal journal and needs no workbench.v3 project. FORMAT_GATED families
# mirror the real workbench.v3 gates enforced at the service layer of
# annotation_service/changes/content_ops/styles/candidates (B07/G54 also added
# the candidates gate to plan/adopt/decide). Known granularity limit: the
# run_desk family mixes /api/feedback (serves v1 projects by design) with
# /api/stages/assemble (v3-only) — a single family-level projection cannot
# separate them, recorded as an open G54 follow-up.
PROJECT_ACTIONS = (
    ("drafts", "ui_draft.v1"),
    ("annotations", "annotations.v1"),
    ("changes", "changes.v1"),
    ("candidates", "candidates.v1"),
    ("content", "content_ops.v1"),
    ("inputs", "content_ops.v1"),
    ("styles", "style_recipes.v1"),
    ("run_desk", "run_desk.v1"),
    ("exports", "exports.v1"),
    ("restoration", "restoration.v1"),
)
FORMAT_GATED = frozenset({"annotations", "changes", "content", "styles", "candidates"})


def _capabilities(server_capabilities):
    # A caller without a live server (CLI, direct tests) describes this core.
    if server_capabilities is None:
        return {capability for _, capability in PROJECT_ACTIONS}
    return set(server_capabilities)


def _effective_actions(*, project_format, sample_readonly, server_capabilities=None):
    """Project-level availability, truthful to the real write gates.

    reason_code is a projection vocabulary, not the endpoints' error-envelope
    codes: sample_readonly matches the real 403 code, unsupported_project_format
    describes the format gate the gated families really enforce, and the two
    upgrade reasons mirror store.read_current's pointer refusals. The
    historical-view reason fixed_revision is composed by the UI from its route,
    never by the server.
    """
    capabilities = _capabilities(server_capabilities)
    actions = []
    for action, capability in PROJECT_ACTIONS:
        supported = capability in capabilities
        writable, reason = True, None
        if not supported:
            writable = False
        elif sample_readonly:
            writable, reason = False, "sample_readonly"
        elif action in FORMAT_GATED and project_format != "workbench.v3":
            writable, reason = False, "unsupported_project_format"
        actions.append({"action": action, "supported": supported,
                        "writable": writable, "reason_code": reason})
    return actions


def _pointer_gate(project):
    """Classify pointer-level refusals before the document loads, so the UI
    gets an explainable payload instead of a failed boot. Reads the raw
    pointer file on purpose: project_path() itself validates through the
    snapshot loader, which is exactly what fails here."""
    from pathlib import Path

    from .store import SUPPORTED_WRITERS, WORKBENCH_FORMAT
    root = Path(project).expanduser().resolve()
    pointer = read_json(safe_path(root, ".deckmaster", "current.json"))
    if not isinstance(pointer, dict):
        return None
    fmt = pointer.get("format")
    if fmt not in CORE_READERS:
        return "reader_upgrade_required", pointer
    if fmt == WORKBENCH_FORMAT and pointer.get("minimum_writer") not in SUPPORTED_WRITERS:
        return "writer_upgrade_required", pointer
    return None


def project_info(project, *, server_capabilities=None):
    from .samples import sample_info
    from .store import SUPPORTED_WRITERS
    gate = _pointer_gate(project)
    if gate is not None:
        reason, pointer = gate
        capabilities = _capabilities(server_capabilities)
        return {"project_id": None, "project_identity": None, "title": None, "revision_id": None,
                "project_format": pointer.get("format"), "minimum_writer": pointer.get("minimum_writer"),
                "core_readers": list(CORE_READERS), "core_writers": list(SUPPORTED_WRITERS),
                "read_status": {"status": "unreadable", "reason_code": reason,
                                "detail": "this core cannot read the project pointer; open it with a matching core"},
                "host_execution": "handoff_required", "draft_journal": "ui_draft.v1", "sample": None,
                "effective_actions": [{"action": action, "supported": capability in capabilities,
                                       "writable": False, "reason_code": reason}
                                      for action, capability in PROJECT_ACTIONS]}
    store, doc, identity = context(project)
    sample = sample_info(store.project_root)
    compatibility = doc.get("compatibility", {})
    project_format = compatibility.get("project_format", "deck_document.v1")
    return {"project_id": doc["project_id"], "project_identity": identity,
            "title": doc["task"]["title"], "revision_id": doc["revision_id"],
            "project_format": project_format,
            "minimum_writer": compatibility.get("minimum_writer"),
            "core_readers": list(CORE_READERS), "core_writers": list(SUPPORTED_WRITERS),
            "host_execution": "handoff_required", "draft_journal": "ui_draft.v1",
            "sample": sample,
            "effective_actions": _effective_actions(project_format=project_format,
                                                    sample_readonly=bool(sample and sample.get("readonly")),
                                                    server_capabilities=server_capabilities)}


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
        return [p["ref"] for p in prompts["prepared"]] + [request["ref"] for request in lineage["generation"]["requests"]]
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


# ---------------------------------------------------------------------------
# B05 (INTERFACES "B05：个人状态清理"): clearing personal workspace state is a
# two-phase personal action. plan reads and writes nothing; commit re-derives
# the manifest, keeps a recovery backup, deletes only the planned objects and
# logs the transaction in the personal journal — never as a business revision.
# Project content, history, tasks, call ledger and candidates are out of scope.


CLEAR_INPUT_KEYS = frozenset({"project_id", "scope", "draft_ids", "reading_preferences"})


def _reject_unknown_clear_keys(input):
    unknown = sorted(set(input) - CLEAR_INPUT_KEYS)
    if unknown:
        raise LocalStateError("input", "unknown clear request fields: " + ", ".join(unknown))


def _clear_log_path(store):
    return safe_path(store.project_root, ".deckmaster", "workbench", "clear-log.jsonl")


def _clear_backup_path(store, manifest_digest):
    return safe_path(store.project_root, ".deckmaster", "workbench", "clear-backups",
                     manifest_digest[:16] + ".json")


def _read_clear_log(store):
    path = _clear_log_path(store)
    entries = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                validate_schema("ui_clear_result", entry)
            except (ValueError, KeyError, TypeError):
                continue  # 崩溃残行按缺失处理；已完成事务以项目状态为准
            entries.append(entry)
    return entries


def _operation_committed(store, operation_id):
    from .operations import committed_record
    try:
        return committed_record(store, operation_id) is not None
    except Exception:
        return False


def _reading_items(store, doc, identity):
    """Gallery record and saved reading position, damage-isolated."""
    from . import gallery_state
    items, kept_out = [], []
    try:
        record = gallery_state._read(store, doc, identity)
    except (LocalStateError, ValueError, KeyError, TypeError):
        record = None
    if record is not None:
        items.append({"kind": "gallery_state", "id": "gallery.json", "etag": record["etag"]})
    elif safe_path(store.deck_root, "workbench", "gallery.json").exists():
        kept_out.append("gallery_state: saved gallery record is damaged or foreign; kept for manual recovery")
    position = read_json(_position_path(store))
    if position is not None:
        try:
            validate_schema("ui_position", position.get("position"))
            if position.get("digest") != digest(position["position"]):
                raise LocalStateError("position", "saved position hash is invalid")
            if position["position"]["project_id"] != doc["project_id"] or position["position"]["project_identity"] != identity:
                raise LocalStateError("position", "saved position belongs to another project")
            items.append({"kind": "reading_position", "id": "position.json", "etag": position["digest"]})
        except (LocalStateError, ValueError, KeyError, TypeError):
            kept_out.append("reading_position: saved position record is damaged or foreign; kept for manual recovery")
    return items, kept_out


def _clear_selection(input, records):
    selected = input.get("draft_ids", "all")
    if selected == "all":
        return sorted(records)
    if isinstance(selected, list) and all(isinstance(item, str) for item in selected):
        unknown = [item for item in selected if item not in records]
        if unknown:
            raise LocalStateError("draft_ids", "selected drafts are not readable personal drafts of this project")
        if len(selected) != len(set(selected)):
            raise LocalStateError("draft_ids", "select each draft once")
        return sorted(selected)
    raise LocalStateError("draft_ids", "draft_ids is 'all' or a list of draft identities")


def _clear_draft_records(store, doc, identity):
    """Draft records on an established context (same rules as list_drafts)."""
    directory = _directory(store)
    records, errors = {}, []
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                record = _read(store, path.stem)
                _validate(store, doc, identity, record["draft"])
                records[record["draft"]["draft_id"]] = record
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                errors.append({"draft_id": path.stem, "status": "unreadable"})
    return records, errors


def _clear_manifest(store, doc, identity, input):
    """Derive the deletable items, blockers and damage notes from live state.

    Callers pass one established context so plan walks the project ancestry once
    and commit twice (its own + the re-derivation), not once per nested helper.
    """
    if input.get("project_id") != doc["project_id"]:
        raise LocalStateError("project_id", "clear plan belongs to the current project")
    if not isinstance(input.get("reading_preferences"), bool):
        raise LocalStateError("reading_preferences", "reading_preferences is true or false")
    records, listing_errors = _clear_draft_records(store, doc, identity)
    items, blockers = [], []
    explicit = input.get("draft_ids", "all") != "all"
    for draft_id in _clear_selection(input, records):
        record = records[draft_id]
        pending = record["draft"].get("pending")
        if pending and not _operation_committed(store, pending["operation_id"]):
            if explicit:
                # 明确点名的未决草稿不进计划：先去查询原 operation 状态。
                raise LocalStateError("draft_ids", f"draft {draft_id} holds an unconfirmed operation "
                                      f"{pending['operation_id']}; query deck-master operations show first")
            blockers.append({"kind": "draft", "id": draft_id, "reason_code": "unconfirmed_operation",
                             "operation_id": pending["operation_id"],
                             "next_action": "query deck-master operations show with this operation ID before clearing"})
            continue
        items.append({"kind": "draft", "id": draft_id, "etag": record["etag"]})
    kept_out = [f"draft {error['draft_id']}: saved record is unreadable or foreign; kept for manual recovery"
                for error in listing_errors]
    if input["reading_preferences"]:
        reading, damage = _reading_items(store, doc, identity)
        items.extend(reading)
        kept_out.extend(damage)
    manifest = {"project_id": doc["project_id"], "project_identity": identity,
                "scope": "current_project", "items": items}
    return doc, identity, items, blockers, kept_out, digest(manifest)


def plan_clear(project, *, input):
    """Read-only clear plan: items, etags, blockers, kept-out damage, backup slot.

    Cancel is this function alone — it performs no write anywhere.
    """
    if not isinstance(input, dict) or input.get("scope") != "current_project":
        raise LocalStateError("scope", "clearing scope is current_project")
    _reject_unknown_clear_keys(input)
    store, doc, identity = context(project)
    _, _, items, blockers, kept_out, manifest_digest = _clear_manifest(store, doc, identity, input)
    plan = {"schema_version": "ui_clear_plan.v1", "project_id": doc["project_id"], "project_identity": identity,
            "scope": "current_project", "items": items, "blockers": blockers, "kept_out": kept_out,
            "manifest_digest": manifest_digest, "plan_id": "clear-plan-" + manifest_digest[:16],
            "backup_ref": ".deckmaster/workbench/clear-backups/" + manifest_digest[:16] + ".json"}
    validate_schema("ui_clear_plan", plan)
    return plan


def commit_clear(project, *, operation_id, input, plan_id, manifest_digest):
    """Backup, then delete exactly the planned same-etag objects; log for replay.

    The manifest digest must match the live re-derivation: any draft added,
    edited or removed since the plan (or a moved etag) refuses with 409 and
    deletes nothing. Backup failure also deletes nothing. The transaction log
    lives in the personal journal — the business Document is never revised.
    """
    if not IDENTIFIER.fullmatch(operation_id or ""):
        raise LocalStateError("operation_id", "invalid clear operation identity")
    if not isinstance(input, dict) or input.get("scope") != "current_project":
        raise LocalStateError("scope", "clearing scope is current_project")
    _reject_unknown_clear_keys(input)
    store, doc, identity = context(project)
    # 与三类保存方互斥：drafts/journal.lock、gallery.lock、position.lock 全程持有
    # （固定获取顺序，保存方各自只取一把锁，不存在死锁环）。clear.lock 保护日志追加。
    with local_lock(safe_path(_directory(store), "journal.lock")), \
            local_lock(safe_path(store.deck_root, "workbench", "gallery.lock")), \
            local_lock(safe_path(_position_path(store).parent, "position.lock")), \
            local_lock(safe_path(_clear_log_path(store).parent, "clear.lock")):
        for entry in _read_clear_log(store):
            if entry["operation_id"] == operation_id:
                return {"status": "cleared", "replayed": True, **entry}
        expected_plan_id, expected_digest = plan_id, manifest_digest
        if not isinstance(expected_digest, str) or len(expected_digest) != 64:
            raise LocalStateError("manifest_digest", "manifest digest is required for the commit")
        if expected_plan_id != "clear-plan-" + expected_digest[:16]:
            raise LocalStateError("plan_id", "plan identifier does not match the manifest digest")
        _, _, items, _, _, live_digest = _clear_manifest(store, doc, identity, input)
        if live_digest != expected_digest:
            raise LocalStateConflict("manifest_digest",
                                     "personal state changed since the plan; nothing was cleared, plan again")
        # 删除前逐项复核 etag：后台已变化的对象退出本次清理（整体 409，双方保留）。
        _verify_items_unchanged(store, items)
        cleared_at = _utc_now_iso()
        result = {"schema_version": "ui_clear_result.v1", "operation_id": operation_id,
                  "plan_id": expected_plan_id, "manifest_digest": expected_digest, "scope": "current_project",
                  "backup_ref": ".deckmaster/workbench/clear-backups/" + expected_digest[:16] + ".json",
                  "cleared": items, "cleared_at": cleared_at}
        validate_schema("ui_clear_result", result)
        # 恢复备份先于任何删除；备份失败不得清理。
        records = _clear_backup_records(store, items)
        backup = {"schema_version": "ui_clear_backup.v1", "operation_id": operation_id,
                  "manifest_digest": expected_digest, "records": records, "cleared_at": cleared_at}
        validate_schema("ui_clear_backup", backup)
        write_json(_clear_backup_path(store, expected_digest), backup)
        for item in items:
            path = _draft_path(store, item["id"]) if item["kind"] == "draft" else (
                safe_path(store.deck_root, "workbench", "gallery.json") if item["kind"] == "gallery_state"
                else _position_path(store))
            path.unlink(missing_ok=True)  # 锁内复核 etag 后仍缺失=并发已删；按已清理如实记录
        log_path = _clear_log_path(store)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        return {"status": "cleared", "replayed": False, **result}


def _verify_items_unchanged(store, items):
    for item in items:
        if item["kind"] == "draft":
            record = read_json(_draft_path(store, item["id"]))
            current = record.get("etag") if record else None
        elif item["kind"] == "gallery_state":
            record = read_json(safe_path(store.deck_root, "workbench", "gallery.json"))
            current = record.get("etag") if record else None
        else:
            record = read_json(_position_path(store))
            current = record.get("digest") if record else None
        if current != item["etag"]:
            raise LocalStateConflict(item["id"], "personal object changed since the plan; nothing was cleared")


def _clear_backup_records(store, items):
    """Snapshot the exact bytes being removed so an explicit import can restore."""
    records = []
    for item in items:
        if item["kind"] == "draft":
            records.append({"kind": "draft", "id": item["id"], "etag": item["etag"],
                            "record": read_json(_draft_path(store, item["id"]))})
        elif item["kind"] == "gallery_state":
            records.append({"kind": "gallery_state", "id": item["id"], "etag": item["etag"],
                            "record": read_json(safe_path(store.deck_root, "workbench", "gallery.json"))})
        else:
            records.append({"kind": "reading_position", "id": item["id"], "etag": item["etag"],
                            "record": read_json(_position_path(store))})
    return records
