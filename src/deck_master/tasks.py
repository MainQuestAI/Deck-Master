"""Host task envelopes and result adoption (spec 09.4, 09.7, 08.6).

The result envelope has fixed slots: kind/files/pages/page_order/
artifact_specs/reviews/usage_events/notes. The parser branches on
``Task.kind`` and validates into the five permanent object types only — the
envelope itself is not a sixth schema. Adoption is all-or-nothing: files are
staged under ``staging/<operation_id>/``, every payload is prevalidated, and
the current Document switches once inside the project lock. Call settlement
facts survive even when product adoption fails (spec 08.6).
"""

from __future__ import annotations

import json
import uuid
from functools import wraps
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .content import check_page
from .models import (
    ModelError,
    bump_revision,
    content_identity,
    canonical_json_bytes,
    sha256_bytes,
    validate_artifact_semantics,
    validate_review_semantics,
    validate_task_semantics,
)
from .store import Store, StoreError

ENVELOPE_KINDS = ("compose", "blueprint", "reconstruct", "review", "repair")
ENVELOPE_SLOTS = (
    "kind",
    "files",
    "pages",
    "page_order",
    "artifact_specs",
    "reviews",
    "usage_events",
    "notes",
)

TASK_KINDS = ENVELOPE_KINDS + ("compile", "render", "check")
TASK_STATUSES = (
    "queued",
    "awaiting_host",
    "running",
    "completed",
    "failed",
    "cancelled",
    "superseded",
)
CALL_OUTCOMES = ("consumed", "not_sent", "unknown")
ALLOWANCE_STATES = ("reserved", "in_flight", "consumed", "released", "unknown")

HOST_TASK_KINDS = ENVELOPE_KINDS
LOCAL_TASK_KINDS = ("compile", "render", "check")

MEDIA_EXT = {
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/jpeg": "jpg",
    "text/plain": "txt",
    "application/json": "json",
    "text/markdown": "md",
}


class EnvelopeError(ModelError):
    """The result envelope violates the fixed shape (exit code 2)."""


class TaskConflict(StoreError):
    """Late result, stale input, or a different output for a known operation."""


@dataclass
class OperationJournal:
    """Management-record layer for idempotency and settled call facts.

    Not a permanent object type; service derives status from it.
    """

    operation_id: str
    task_id: str
    kind: str
    produced_against: str
    result_digest: str
    revision_id: str
    status: str = "applied"
    usage_events: list[dict] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "task_id": self.task_id,
            "kind": self.kind,
            "produced_against": self.produced_against,
            "result_digest": self.result_digest,
            "revision_id": self.revision_id,
            "usage_events": self.usage_events,
        }


def parse_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate the fixed envelope shape; unknown fields are explicit errors."""
    if not isinstance(raw, dict):
        raise EnvelopeError("(result)", "result must be a JSON object")
    kind = raw.get("kind")
    if kind not in ENVELOPE_KINDS:
        raise EnvelopeError(
            "(result)/kind",
            f"kind must be one of {', '.join(ENVELOPE_KINDS)}; got {kind!r}",
        )
    unknown = sorted(set(raw) - set(ENVELOPE_SLOTS))
    if unknown:
        raise EnvelopeError("(result)", f"unknown envelope fields: {unknown}")
    for slot in ("pages", "page_order", "artifact_specs", "reviews", "usage_events"):
        value = raw.get(slot)
        if value is not None and not isinstance(value, list):
            raise EnvelopeError(f"(result)/{slot}", "must be an array when present")
    if raw.get("notes") is not None and not isinstance(raw["notes"], str):
        raise EnvelopeError("(result)/notes", "must be a string when present")
    files = raw.get("files") or []
    for index, item in enumerate(files):
        if not isinstance(item, dict) or not {"file_id", "path", "media_type"} <= set(item):
            raise EnvelopeError(
                f"(result)/files[{index}]", "files need file_id, path and media_type"
            )
        staged_path = item.get("path")
        if not isinstance(staged_path, str) or not staged_path:
            raise EnvelopeError(
                f"(result)/files/{item.get('file_id')}", "path must be a non-empty string"
            )
        path = Path(staged_path)
        if path.is_absolute() or ".." in path.parts:
            raise EnvelopeError(
                f"(result)/files/{item.get('file_id')}",
                f"path must stay inside this operation's staging directory, got {staged_path!r}",
            )
    return raw


def _staged_file_path(store: Store, operation_id: str, staged_path: str) -> Path:
    staging = (store.deck_root / "staging" / operation_id).resolve()
    candidate = (staging / staged_path).resolve()
    if not candidate.is_relative_to(staging):
        raise EnvelopeError(
            f"(result)/files/{staged_path}", "path escapes this operation's staging directory"
        )
    walked = staging
    for part in Path(staged_path).parts[:-1]:
        walked = walked / part
        if walked.is_symlink():
            raise EnvelopeError(
                f"(result)/files/{staged_path}", f"symlink component {part!r} in staging path"
            )
    if candidate.is_symlink():
        raise EnvelopeError(
            f"(result)/files/{staged_path}", "staged file must be a regular file, not a symlink"
        )
    return candidate


def _read_staged(store: Store, operation_id: str, envelope: dict) -> dict[str, dict]:
    """file_id -> {bytes, media_type, staged_path}; every declared file must exist."""
    staged: dict[str, dict] = {}
    for item in envelope.get("files") or []:
        resolved = _staged_file_path(store, operation_id, item["path"])
        if not resolved.is_file():
            raise EnvelopeError(
                f"(result)/files/{item['file_id']}",
                f"declared staging file missing: {item['path']}",
            )
        staged[item["file_id"]] = {
            "bytes": resolved.read_bytes(),
            "media_type": item["media_type"],
            "staged_path": item["path"],
        }
    return staged


def _ext_for(media_type: str, staged_path: str) -> str:
    by_media = {
        "image/svg+xml": "svg",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/svg": "svg",
        "text/plain": "txt",
        "application/json": "json",
        "text/markdown": "md",
    }
    ext = by_media.get(media_type)
    if ext:
        return ext
    suffix = Path(staged_path).suffix.lstrip(".").lower()
    if suffix.isalnum() and suffix:
        return suffix
    return "bin"


def _operations_dir(store: Store) -> Path:
    return store.deck_root / "operations"


def read_operation_journal(store: Store, operation_id: str) -> dict[str, Any] | None:
    path = _operations_dir(store) / f"{operation_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text("utf-8"))


def write_operation_journal(store: Store, journal: OperationJournal) -> None:
    directory = _operations_dir(store)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{journal.operation_id}.json"
    if path.exists():
        existing = json.loads(path.read_text("utf-8"))
        if existing.get("result_digest") != journal.result_digest:
            raise TaskConflict(
                path.name,
                f"operation {journal.operation_id} journal conflicts with a different result",
            )
        return
    path.write_text(json.dumps(journal.to_json(), ensure_ascii=False, indent=1) + "\n")


def _lookup_task(document: dict, task_id: str, store: Store) -> dict:
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if task.get("task_id") == task_id:
            return task
    raise EnvelopeError(f"(task {task_id})", "task not found in current Document")


def task_inputs_current(store, document, task):
    if content_identity(document) == task.get('produced_against'):
        return True
    if not task.get('scope_pages'):
        return False
    dispatched = store.load_document(task['dispatch_revision'])
    if dispatched['design_context'] != document['design_context'] or dispatched['sources'] != document['sources']:
        return False
    before = {e['page_id']: e for e in dispatched['pages']}
    after = {e['page_id']: e for e in document['pages']}
    slots = ('page','blueprint','svg') if task['kind'] in ('reconstruct','repair','review') else ('page',)
    for pid in task['scope_pages']:
        if pid not in before or pid not in after or any(before[pid].get(k) != after[pid].get(k) for k in slots):
            return False
    if task['kind'] == 'review' and dispatched['outputs'] != document['outputs']:
        return False
    return True


def _validate_svg_reference(data, expected_sha):
    import re
    import xml.etree.ElementTree as ET
    if re.search(br'<!\s*(DOCTYPE|ENTITY)',data,re.I):
        raise EnvelopeError('svg/reference','XML entities are forbidden')
    try:
        root=ET.fromstring(data)
    except ET.ParseError as exc:
        raise EnvelopeError('svg/reference',str(exc)) from exc
    claimed=root.get('data-blueprint-sha256')
    if claimed is not None and claimed != expected_sha:
        raise EnvelopeError('svg/data-blueprint-sha256','SVG was reconstructed against a different original image')


def _build_artifact(
    store: Store,
    spec: dict[str, Any],
    staged: dict[str, dict],
    page_ids: set[str],
) -> dict:
    """Build the permanent Artifact from a spec; bytes come from staged files."""
    file_id = spec.get("file_id")
    if not isinstance(file_id, str) or file_id not in staged:
        raise EnvelopeError(
            f"(result)/artifact_specs/{file_id}", "file_id must reference an envelope file"
        )
    media = staged[file_id]
    file_ref = store.put_blob(
        media["bytes"], ext=_ext_for(media["media_type"], media["staged_path"])
    )
    page_id = spec.get("page_id")
    if page_id is not None and page_id not in page_ids:
        raise EnvelopeError(
            f"(result)/artifact_specs/{spec.get('role')}",
            f"artifact targets page {page_id!r} which is not part of this Document",
        )
    provenance = dict(spec.get("provenance") or {})
    prompt_file_id = provenance.pop("submitted_prompt_file_id", None)
    if prompt_file_id is not None:
        if prompt_file_id not in staged:
            raise EnvelopeError(
                f"(result)/artifact_specs/{spec.get('role')}",
                f"submitted_prompt_file_id {prompt_file_id!r} not declared in files",
            )
        provenance["submitted_prompt"] = store.put_blob(
            staged[prompt_file_id]["bytes"], ext="txt"
        )
    artifact = {
        "schema_version": "deck_artifact.v1",
        "artifact_id": f"{spec.get('role')}-{page_id or 'shared'}-{sha256_bytes(media['bytes'])[:8]}",
        "page_id": page_id,
        "role": spec.get("role"),
        "file": file_ref,
        "media_type": media["media_type"],
        "created_at": _utc_now_iso(),
        "dependencies": spec.get("dependencies") or [],
        "derived_from": spec.get("derived_from") or [],
        "provenance": provenance,
        "limitations": spec.get("limitations") or [],
    }
    validate_artifact_semantics(artifact)
    return artifact


def _adopt_review(store: Store, review: dict) -> dict:
    """Reviews must reference already-saved objects, never envelope aliases."""
    validate_review_semantics(review)
    for subject in review.get("subjects") or []:
        store.read_object_bytes(subject)  # must exist and match its digest
    return review


def _check_scope(kind: str, envelope: dict, task: dict) -> None:
    scope = task.get("scope_pages") or []
    pages = envelope.get("pages") or []
    page_order = envelope.get("page_order") or []
    page_ids = [page.get("page_id") for page in pages]
    if page_order and sorted(page_order) != sorted(page_ids):
        raise EnvelopeError(
            "(result)/page_order", "page_order must match the pages payload exactly"
        )
    if kind == "compose":
        if not pages or not page_order:
            raise EnvelopeError(
                "(result)/pages", "compose must deliver the full page array with page_order"
            )
        if len(set(page_ids)) != len(page_ids):
            raise EnvelopeError("(result)/pages", "duplicate page_id in result")
    elif kind == "repair":
        if scope:
            outside = [pid for pid in page_ids if page_ids and page_id not in scope]
            if outside:
                raise EnvelopeError(
                    "(result)/pages",
                    f"repair pages {outside} are outside the authorized scope {scope}",
                )
    elif pages and scope:
        outside = [pid for pid in page_ids if pid not in scope]
        if outside:
            raise EnvelopeError(
                "(result)/pages", f"pages {outside} are outside the authorized scope {scope}"
            )


def _settled_allowances(
    task: dict, usage_events: list[dict], staged: dict[str, dict], store: Store
) -> dict:
    """Apply usage observations onto call_allowances; allocation is not granted here."""
    allowances = [dict(entry) for entry in (task.get("call_allowances") or [])]
    by_id = {entry.get("allowance_id"): entry for entry in allowances}
    for event in usage_events or []:
        allowance_id = event.get("allowance_id")
        if allowance_id not in by_id:
            raise EnvelopeError(
                f"(result)/usage_events/{allowance_id}",
                "usage events may only report pre-allocated allowances; "
                "allocation is a project transaction (spec 08.6)",
            )
        outcome = event.get("outcome")
        if outcome not in CALL_OUTCOMES:
            raise EnvelopeError(
                f"(result)/usage_events/{allowance_id}",
                f"outcome must be one of {', '.join(CALL_OUTCOMES)}",
            )
        allowance = by_id[allowance_id]
        reports = []
        for file_id in event.get("evidence_file_ids") or []:
            if file_id not in staged:
                raise EnvelopeError("(result)/usage_events", f"missing evidence file {file_id!r}")
            reports.append(staged[file_id])
        invocation = event.get("invocation_ref")
        if invocation and any(a is not allowance and a.get("invocation_ref") == invocation for a in allowances):
            raise TaskConflict("(result)/usage_events", "duplicate invocation")
        report = reports[0] if reports else None
        updated = _settle_target(
            store, store.load_document(), task["task_id"], allowance_id, allowance, outcome,
            report["bytes"] if report else None,
            _ext_for(report["media_type"], report["staged_path"]) if report else "json", invocation,
        )
        for extra in reports[1:]:
            ref = store.put_blob(extra["bytes"], ext=_ext_for(extra["media_type"], extra["staged_path"]))
            if ref not in updated["evidence"]:
                updated["evidence"] = updated["evidence"] + [ref]
        allowance.update(updated)
    task["call_allowances"] = allowances
    return task


def new_task(
    *,
    task_id: str,
    operation_id: str,
    kind: str,
    scope_pages: list[str],
    instruction: str,
    inputs: list[dict],
    dependencies: list[dict],
    dispatch_revision: str,
    produced_against: str,
    cost_class: str = "host_reasoning",
    call_allowances: list[dict] | None = None,
    status: str = "awaiting_host",
) -> dict:
    """Build a minimal valid Task v1 (05 chapter wires dispatch)."""
    task = {
        "schema_version": "deck_task.v1",
        "task_id": task_id,
        "operation_id": operation_id,
        "kind": kind,
        "status": status,
        "scope_pages": scope_pages,
        "instruction": instruction,
        "inputs": inputs,
        "dependencies": dependencies,
        "dispatch_revision": dispatch_revision,
        "produced_against": produced_against,
        "result_refs": [],
        "error": None,
        "execution_ref": None,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "cost_class": cost_class,
        "usage": {"source": "not_reported", "external_calls": None},
        "call_allowances": call_allowances or [],
    }
    validate_task_semantics(task)
    return task


def accept_result(
    store: Store,
    *,
    task_id: str,
    operation_id: str,
    produced_against: str,
    envelope_raw: dict[str, Any],
) -> dict:
    """Validate a Host result envelope and adopt it atomically (spec 09.7).

    Returns a response dict with ``status`` accepted/already_applied; raises
    EnvelopeError (invalid input) or TaskConflict (late result / stale input /
    different output for a known operation) without touching current state.
    """
    envelope = parse_envelope(envelope_raw)
    result_digest = sha256_bytes(canonical_json_bytes(envelope))
    document = store.load_document()
    task = _lookup_task(document, task_id, store)

    if task.get("kind") != envelope["kind"]:
        raise EnvelopeError(
            f"(task {task_id})/kind",
            f"task kind is {task.get('kind')!r}; envelope kind {envelope['kind']!r} does not match",
        )

    journal = read_operation_journal(store, operation_id)
    if journal is not None:
        if journal.get("result_digest") == result_digest:
            return {
                "status": "already_applied",
                "revision_id": journal.get("revision_id"),
                "same_revision": True,
            }
        raise TaskConflict(
            f"(operation {operation_id})",
            "same operation already applied with a different result",
        )

    if task.get("status") in ("cancelled", "superseded"):
        # Settle call facts first; the late product is then refused (current unchanged).
        staged = _read_staged(store, operation_id, envelope)
        settled = _settled_allowances(task, envelope.get("usage_events") or [], staged, store)
        updated_task = {
            **task,
            "call_allowances": settled["call_allowances"],
            "updated_at": _utc_now_iso(),
        }
        validate_task_semantics(updated_task)
        task_ref = store.put_json_object(updated_task)
        bumped = bump_revision(
            document,
            {
                "operation_id": f"settle-{operation_id}",
                "kind": "task_update",
                "description": "late result after cancellation; call facts settled",
                "read_set": [],
            },
        )
        bumped = _replace_task_ref(bumped, task, task_ref, store)
        store.commit_change(
            base_revision=document["revision_id"],
            document=bumped,
            operation_id=f"settle-{operation_id}",
        )
        write_operation_journal(
            store,
            OperationJournal(
                operation_id=operation_id,
                task_id=task_id,
                kind=envelope["kind"],
                produced_against=produced_against,
                result_digest=result_digest,
                revision_id=document["revision_id"],
                status="late_result_settled",
                usage_events=envelope.get("usage_events") or [],
            ),
        )
        raise TaskConflict(
            f"(task {task_id})", "result arrived after cancellation; call facts were settled"
        )

    if produced_against != task.get("produced_against"):
        raise TaskConflict(
            f"(task {task_id})",
            "produced_against does not match the dispatched dependency hash; rebase required",
        )
    # Freshness is content-based: task-management revisions (claim, allocation)
    # keep the result valid; a content change invalidates it (spec 09.7 recheck).
    if not task_inputs_current(store, document, task):
        raise TaskConflict(
            "(document)",
            "project content moved since dispatch; read the new inputs and rebase",
        )

    staged = _read_staged(store, operation_id, envelope)
    _check_scope(envelope["kind"], envelope, task)

    # Prevalidate everything before any adoption.
    adopted_pages = []
    for page in envelope.get("pages") or []:
        adopted_pages.append(check_page(page))
    artifacts = []
    existing_page_ids = {entry.get("page_id") for entry in document.get("pages") or []} | {
        page["page_id"] for page in adopted_pages
    }
    for spec in envelope.get("artifact_specs") or []:
        if spec.get('role') == 'svg':
            entry=next((e for e in document['pages'] if e['page_id']==spec.get('page_id')),None)
            if entry and entry['blueprint']:
                original=store.read_object_json(entry['blueprint'])
                _validate_svg_reference(staged[spec['file_id']]['bytes'],original['file']['sha256'])
        artifacts.append(_build_artifact(store, spec, staged, existing_page_ids))
    reviews = []
    for review in envelope.get("reviews") or []:
        reviews.append(_adopt_review(store, review))
    updated_task = dict(_settled_allowances(task, envelope.get("usage_events") or [], staged, store))
    updated_task = {
        **updated_task,
        "status": "completed",
        "updated_at": _utc_now_iso(),
    }

    # Persist the validated payload (immutable blobs), then switch the Document once.
    page_refs = {}
    for page in adopted_pages:
        page_refs[page["page_id"]] = store.put_json_object(page)
    artifact_refs = [store.put_json_object(artifact) for artifact in artifacts]
    review_refs = [store.put_json_object(review) for review in reviews]
    task_ref = store.put_json_object(updated_task)

    new_document = bump_revision(
        document,
        {"operation_id": operation_id, "kind": "task_update", "description": "", "read_set": []},
    )
    page_slots = {}
    for artifact in artifacts:
        if artifact.get("page_id"):
            page_slots.setdefault(artifact["page_id"], {})[artifact["role"]] = _ref_of(store, artifact)
    if envelope["kind"] == "compose":
        new_pages = []
        for page_id in envelope.get("page_order") or []:
            new_pages.append(
                {
                    "page_id": page_id,
                    "page": page_refs[page_id],
                    "blueprint": None,
                    "svg": None,
                    "svg_preview": None,
                    "ppt_preview": None,
                    **(page_slots.get(page_id) or {}),
                }
            )
        new_document["pages"] = new_pages
        new_document['outputs'] = {key: None for key in new_document['outputs']}
    else:
        existing = {
            entry.get("page_id"): entry
            for entry in (new_document.get("pages") or [])
        }
        order = [entry.get("page_id") for entry in new_document.get("pages") or []] + [
            pid for pid in page_refs if pid not in existing
        ]
        new_document["pages"] = [
            _merge_page_entry(existing, page_slots, page_refs, pid) for pid in order
        ]
    if envelope['kind'] in ('blueprint', 'reconstruct', 'repair') and (page_refs or artifacts):
        changed_ids = set(page_refs) | {a['page_id'] for a in artifacts if a.get('page_id')}
        new_document['outputs'] = {key: None for key in new_document['outputs']}
        for entry in new_document['pages']:
            if entry['page_id'] in changed_ids:
                entry['svg_preview'] = entry['ppt_preview'] = None
                if (entry['page_id'] in page_refs or 'blueprint' in page_slots.get(entry['page_id'], {})) and 'svg' not in page_slots.get(entry['page_id'], {}):
                    entry['svg'] = None
    new_document["reviews"] = list(new_document.get("reviews") or []) + review_refs
    _replace_task_in_document(new_document, task, task_ref, store)
    if envelope["kind"] == "compose":
        new_document["change"] = {
            "operation_id": operation_id,
            "kind": "content_update",
            "description": envelope.get("notes") or "compose result adopted",
            "read_set": [{"identity": f"document-revision:{task.get('dispatch_revision')}", "sha256": produced_against}],
        }
    elif reviews:
        new_document["change"] = {
            "operation_id": operation_id,
            "kind": "review_update",
            "description": envelope.get("notes") or "review adopted",
            "read_set": [{"identity": f"document-revision:{task.get('dispatch_revision')}", "sha256": produced_against}],
        }
    else:
        new_document["change"] = {
            "operation_id": operation_id,
            "kind": "task_update",
            "description": envelope.get("notes") or "task result adopted",
            "read_set": [{"identity": f"document-revision:{task.get('dispatch_revision')}", "sha256": produced_against}],
        }
    new_revision = store.commit_change(
        base_revision=document["revision_id"],
        document=new_document,
        operation_id=operation_id,
    )
    write_operation_journal(
        store,
        OperationJournal(
            operation_id=operation_id,
            task_id=task_id,
            kind=envelope["kind"],
            produced_against=produced_against,
            result_digest=result_digest,
            revision_id=new_revision,
            usage_events=envelope.get("usage_events") or [],
        ),
    )
    return {
        "status": "accepted",
        "revision_id": new_revision,
        "new_page_hashes": {
            page_id: ref["sha256"] for page_id, ref in page_refs.items()
        },
        "result_refs": artifact_refs + review_refs,
        "work_complete": derive_work_complete(new_document, store),
        "next_action": "auto_view_then_production"
        if envelope["kind"] == "compose"
        else "continue_production",
    }


class CallBlocked(TaskConflict):
    """A recoverable stop/budget/unknown condition, not an input conflict."""


def _project_transaction(function):
    @wraps(function)
    def locked(store, *args, **kwargs):
        with store._locked():
            return function(store, *args, **kwargs)
    return locked


def reserve_allowances(store, document, task, count):
    """Build an updated task using the locked current project ledger."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise EnvelopeError("(allocate)/count", "count must be a positive integer")
    if task.get("status") not in ("awaiting_host", "running", "queued"):
        raise TaskConflict("(allocate)", "allowances require an active task")
    policy = document.get("policy") or {}
    if policy.get("user_stop"):
        raise CallBlocked("policy/user_stop", "user stopped external calls")
    if project_has_unknown_calls(document, store):
        raise CallBlocked("call_allowances", "resolve unknown calls before allocating")
    held = sum(
        entry["state"] in ("reserved", "in_flight", "consumed", "unknown")
        for ref in document.get("tasks") or []
        for entry in store.read_object_json(ref).get("call_allowances") or []
    )
    limit = policy.get("external_call_limit")
    if limit is not None and held + count > limit:
        raise CallBlocked("policy/external_call_limit",
                          f"project limit {limit}; already held/consumed {held}; requested {count}")
    existing = list(task.get("call_allowances") or [])
    allocated = [dict(allowance_id=f"call-{len(existing)+i+1}", state="reserved",
                      execution_ref=None, invocation_ref=None, evidence=[]) for i in range(count)]
    return {**task, "call_allowances": existing + allocated, "updated_at": _utc_now_iso()}, [x["allowance_id"] for x in allocated]


@_project_transaction
def allocate_call_allowances(
    store: Store, *, task_id: str, count: int, operation_id: str | None = None
) -> dict:
    """Reserve ``count`` external-call allowances inside one project transaction.

    Already-settled facts (consumed/released/unknown) are never erased; the
    project ``policy.external_call_limit`` bounds total held+consumed slots.
    This is a service-side allocation, not a Host-granted budget (spec 08.6).
    """
    document = store.load_document()
    task = _lookup_task(document, task_id, store)
    updated_task, allocated_ids = reserve_allowances(store, document, task, count)
    validate_task_semantics(updated_task)
    task_ref = store.put_json_object(updated_task)
    bumped = bump_revision(
        document,
        {
            "operation_id": operation_id or f"allocate-{uuid.uuid4().hex[:8]}",
            "kind": "task_update",
            "description": f"allocated {count} call allowance(s)",
            "read_set": [],
        },
    )
    bumped = _replace_task_ref(bumped, task, task_ref, store)
    store._commit_locked(blobs=[],
        base_revision=document["revision_id"], document=bumped, operation_id=bumped["change"]["operation_id"]
    )
    return {
        "status": "allocated",
        "task_id": task_id,
        "allowance_ids": allocated_ids,
    }


@_project_transaction
def repair_empty_allowance(store, *, task_id):
    document = store.load_document()
    task = _lookup_task(document, task_id, store)
    if task.get("call_allowances"):
        return
    if task["status"] != "awaiting_host" or task.get("execution_ref"):
        raise TaskConflict("(repair)", "only unclaimed empty tasks may be repaired")
    if task["produced_against"] != content_identity(document):
        original = store.load_document(task["dispatch_revision"])
        if task["produced_against"] != content_identity(original):
            raise TaskConflict("(repair)", "invalid dispatched input identity")
        comparable = {**document, "policy": {**document["policy"],
            "external_call_limit": original["policy"].get("external_call_limit"),
            "user_stop": original["policy"].get("user_stop")}}
        if content_identity(comparable) != content_identity(original):
            raise TaskConflict("(repair)", "stale blueprint inputs")
        task = {**task, "produced_against": content_identity(document)}
    updated, _ = reserve_allowances(store, document, task, 1)
    ref = store.put_json_object(updated)
    bumped = bump_revision(document, {"operation_id": f"repair-allowance-{uuid.uuid4().hex}", "kind": "task_update", "description": "repair empty allowance", "read_set": []})
    bumped = _replace_task_ref(bumped, task, ref, store)
    store._commit_locked(blobs=[], base_revision=document["revision_id"], document=bumped)


def project_has_unknown_calls(document: dict, store: Store) -> str | None:
    """Any allowance in ``unknown`` pauses new external calls project-wide."""
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        for entry in task.get("call_allowances") or []:
            if entry.get("state") == "unknown":
                return task.get("task_id")
    return None


@_project_transaction
def call_begin(store: Store, *, task_id: str, allowance_id: str, execution_ref: str | None) -> dict:
    """Atomically take one pre-allocated call allowance (spec 08.6, T13.min)."""
    document = store.load_document()
    task = _lookup_task(document, task_id, store)
    if task.get("status") in ("cancelled", "superseded", "completed"):
        raise TaskConflict(
            f"(task {task_id})",
            f"task is {task.get('status')}; cancelled or finished tasks cannot start external calls",
        )
    allowances = [dict(entry) for entry in (task.get("call_allowances") or [])]
    target = next((entry for entry in allowances if entry.get("allowance_id") == allowance_id), None)
    if target is None:
        raise EnvelopeError(
            f"(task {task_id})/call_allowances/{allowance_id}",
            "allowance not allocated on this task; allocation is a project transaction",
        )
    if task.get("status") != "running" or not execution_ref or task.get("execution_ref") != execution_ref:
        raise TaskConflict("(begin)/execution_ref", "claim task first with the same execution_ref")
    if target.get("state") == "in_flight":
        if target.get("execution_ref") == execution_ref:
            return {"status": "already_started", "task_id": task_id, "allowance_id": allowance_id}
        raise TaskConflict(
            f"(task {task_id})/{allowance_id}",
            "allowance already in flight under another execution",
        )
    if target.get("state") in ("consumed", "released", "unknown"):
        raise TaskConflict(
            f"(task {task_id})/{allowance_id}",
            f"allowance already settled as {target.get('state')}; re-sending is not allowed",
        )
    if (document.get("policy") or {}).get("user_stop"):
        raise CallBlocked("policy/user_stop", "user stopped external calls")
    if project_has_unknown_calls(document, store):
        raise CallBlocked("call_allowances", "resolve unknown calls before beginning")
    target["state"] = "in_flight"
    target["execution_ref"] = execution_ref
    updated_task = {**task, "call_allowances": allowances, "updated_at": _utc_now_iso()}
    validate_task_semantics(updated_task)
    task_ref = store.put_json_object(updated_task)
    begin_operation_id = f"begin-{task_id}-{allowance_id}"
    new_document = bump_revision(
        document,
        {
            "operation_id": begin_operation_id,
            "kind": "task_update",
            "description": f"external call {allowance_id} began",
            "read_set": [],
        },
    )
    new_document = _replace_task_ref(new_document, task, task_ref, store)
    store._commit_locked(blobs=[],
        base_revision=document["revision_id"], document=new_document, operation_id=begin_operation_id
    )
    return {"status": "started", "task_id": task_id, "allowance_id": allowance_id}


def _settle_target(store, document, task_id, allowance_id, target, outcome, report_bytes,
                   report_ext="json", invocation_ref=None):
    """Shared settlement validation for CLI and result-envelope observations."""
    target = dict(target)
    state = target["state"]
    desired = {"consumed": "consumed", "not_sent": "released", "unknown": "unknown"}[outcome]
    known_invocation = target.get("invocation_ref")
    if known_invocation and invocation_ref and known_invocation != invocation_ref:
        raise TaskConflict("(settle)/invocation_ref", "conflicting invocation")
    if invocation_ref:
        for ref in document.get("tasks") or []:
            other = store.read_object_json(ref)
            for entry in other.get("call_allowances") or []:
                if other["task_id"] == task_id and entry["allowance_id"] == allowance_id:
                    continue
                if entry.get("invocation_ref") == invocation_ref:
                    raise TaskConflict("(settle)/invocation_ref", "invocation already registered in project")
    if state in ("consumed", "released") and state != desired:
        raise TaskConflict("(settle)/outcome", "terminal settlement cannot be overwritten")
    if state == "reserved" and desired != "released":
        raise TaskConflict("(settle)/state", "call must begin before reporting sent or unknown")
    report_ref = None
    if report_bytes is not None:
        report_ref = {"sha256": sha256_bytes(report_bytes)}
    evidence_hashes = {r["sha256"] for r in target.get("evidence") or []}
    if state == desired:
        if report_ref and evidence_hashes and report_ref["sha256"] not in evidence_hashes:
            raise TaskConflict("(settle)/report", "conflicting settlement report")
        if (not invocation_ref or known_invocation == invocation_ref) and (not report_ref or report_ref["sha256"] in evidence_hashes):
            return target
    if (desired == "consumed" or state == "unknown" and desired != "unknown" or invocation_ref and not known_invocation) and not report_bytes:
        raise EnvelopeError("(settle)/report", "execution evidence required (host_reported)")
    evidence = list(target.get("evidence") or [])
    if report_bytes is not None:
        ref = store.put_blob(report_bytes, ext=report_ext)
        if ref not in evidence:
            evidence.append(ref)
    target["state"] = {"consumed": "consumed", "not_sent": "released", "unknown": "unknown"}[outcome]
    if invocation_ref:
        target["invocation_ref"] = invocation_ref
    target["evidence"] = evidence
    return target


@_project_transaction
def call_settle(
    store: Store,
    *,
    task_id: str,
    allowance_id: str,
    outcome: str,
    report_bytes: bytes | None,
    report_ext: str = "json",
    invocation_ref: str | None = None,
) -> dict:
    """Record a real call observation; the report is not a permanent sixth object."""
    if outcome not in CALL_OUTCOMES:
        raise EnvelopeError(
            f"(settle {allowance_id})/outcome",
            f"outcome must be one of {', '.join(CALL_OUTCOMES)}",
        )
    document = store.load_document()
    task = _lookup_task(document, task_id, store)
    allowances = [dict(entry) for entry in (task.get("call_allowances") or [])]
    target = next((entry for entry in allowances if entry.get("allowance_id") == allowance_id), None)
    if target is None:
        raise EnvelopeError(
            f"(task {task_id})/call_allowances/{allowance_id}", "allowance not allocated"
        )
    settled = _settle_target(store, document, task_id, allowance_id, target, outcome,
                             report_bytes, report_ext, invocation_ref)
    if settled == target:
        return {"status": "already_settled", "task_id": task_id, "allowance_id": allowance_id}
    target.update(settled)
    updated_task = {
        **task,
        "call_allowances": allowances,
        "updated_at": _utc_now_iso(),
    }
    validate_task_semantics(updated_task)
    task_ref = store.put_json_object(updated_task)
    settle_operation_id = f"settle-{task_id}-{allowance_id}-{sha256_bytes(canonical_json_bytes(target))[:16]}"
    new_document = bump_revision(
        document,
        {
            "operation_id": settle_operation_id,
            "kind": "task_update",
            "description": f"call {allowance_id} settled as {outcome}",
            "read_set": [],
        },
    )
    new_document = _replace_task_ref(new_document, task, task_ref, store)
    store._commit_locked(blobs=[],
        base_revision=document["revision_id"], document=new_document, operation_id=settle_operation_id
    )
    return {"status": "settled", "task_id": task_id, "allowance_id": allowance_id, "outcome": outcome}


def _replace_task_ref(document: dict, old_task: dict, new_ref: dict, store: Store) -> dict:
    """Return a Document copy whose tasks list swaps the old task ref for the new one."""
    old_path = None
    for ref in document.get("tasks") or []:
        resolved = store.read_object_json(ref)
        if resolved.get("task_id") == old_task.get("task_id"):
            old_path = ref["path"]
            break
    if old_path is None:
        raise EnvelopeError(f"(task {old_task.get('task_id')})", "task ref not found in Document")
    tasks = [
        new_ref if ref["path"] == old_path else ref for ref in document.get("tasks") or []
    ]
    if new_ref["path"] not in [ref["path"] for ref in tasks]:
        tasks = tasks + [new_ref]
    return {**document, "tasks": tasks}


def task_ref_of_document(document: dict, task: dict, store: Store) -> str:
    for ref in document.get("tasks") or []:
        resolved = store.read_object_json(ref)
        if resolved.get("task_id") == task.get("task_id"):
            return ref["path"]
    raise EnvelopeError(f"(task {task.get('task_id')})", "task ref not found")


def _replace_task_in_document(new_document: dict, old_task: dict, new_ref: dict, store: Store) -> None:
    """In-place: swap the old task ref (matching task_id) for the fresh blob ref."""
    old_path = task_ref_of_document(new_document, old_task, store)
    tasks = []
    for ref in new_document.get("tasks") or []:
        if ref["path"] == old_path:
            tasks.append(new_ref)
        else:
            tasks.append(ref)
    if new_ref["path"] not in {ref["path"] for ref in tasks}:
        tasks.append(new_ref)
    new_document["tasks"] = tasks


def _merge_page_entry(existing: dict, page_slots: dict, page_refs: dict, page_id: str) -> dict:
    """Merge one page entry: page ref only when the envelope re-delivered the page;
    artifact slots fill in whenever the envelope carries them (blueprint/svg/...)."""
    entry = dict(existing.get(page_id) or {"page_id": page_id})
    if page_id in page_refs:
        entry["page"] = page_refs[page_id]
    for role, slot in (page_slots.get(page_id) or {}).items():
        entry[role] = slot
    return entry


def _ref_of(store: Store, obj: dict) -> dict:
    return store.put_json_object(obj)


def derive_work_complete(document: dict, store: Store) -> bool:
    """Engineering part of completeness: every page has its current artifacts.

    Final delivery semantics stay with T15; this only prevents a bare
    ``completed`` claim when pages lack their artifacts.
    """
    pages = document.get("pages") or []
    if not pages:
        return False
    for entry in pages:
        if not entry.get("page"):
            return False
    return True


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
