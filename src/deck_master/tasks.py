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
import copy
import uuid
from functools import wraps
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .content import check_page
from .models import (
    ModelError,
    page_limit_violation,
    bump_revision,
    content_identity,
    compute_input_digest,
    canonical_json_bytes,
    sha256_bytes,
    validate_artifact_semantics,
    validate_review_semantics,
    validate_task_semantics,
)
from .store import Store, StoreError, _atomic_write_bytes

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
    "content_update",
    "generation_result",
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


class StaleInputContext(TaskConflict):
    """A result arrived after the task inputs moved on (exit 5,
    ``stale_input_context``): continue hands out a fresh task."""

    error_code = "stale_input_context"
    exit_code = 5


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
            "status": self.status,
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
    if raw.get("content_update") is not None and not isinstance(raw["content_update"], dict):
        raise EnvelopeError("(result)/content_update", "must be an object when present")
    if raw.get("notes") is not None and not isinstance(raw["notes"], str):
        raise EnvelopeError("(result)/notes", "must be a string when present")
    files = raw.get("files") or []
    file_ids = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict) or not {"file_id", "path", "media_type"} <= set(item):
            raise EnvelopeError(
                f"(result)/files[{index}]", "files need file_id, path and media_type"
            )
        staged_path = item.get("path")
        if not isinstance(item.get('file_id'), str) or not item['file_id'] or item['file_id'] in file_ids:
            raise EnvelopeError(f'(result)/files[{index}]/file_id', 'must be a unique non-empty string')
        file_ids.add(item['file_id'])
        if not isinstance(item.get('media_type'), str) or not item['media_type']:
            raise EnvelopeError(f'(result)/files[{index}]/media_type', 'must be a non-empty string')
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
    for index, event in enumerate(raw.get('usage_events') or []):
        if not isinstance(event, dict):
            raise EnvelopeError(f'(result)/usage_events[{index}]', 'usage event must be an object')
        if not isinstance(event.get('allowance_id'), str) or not event['allowance_id']:
            raise EnvelopeError(f'(result)/usage_events[{index}]/allowance_id', 'must be a non-empty string')
        if not isinstance(event.get('outcome'), str):
            raise EnvelopeError(f'(result)/usage_events[{index}]/outcome', 'must be a string')
        evidence = event.get('evidence_file_ids')
        if evidence is not None and (not isinstance(evidence, list) or
                                     not all(isinstance(item, str) for item in evidence)):
            raise EnvelopeError(f'(result)/usage_events[{index}]/evidence_file_ids', 'must be an array of strings')
        if event.get('invocation_ref') is not None and not isinstance(event['invocation_ref'], str):
            raise EnvelopeError(f'(result)/usage_events[{index}]/invocation_ref', 'must be a string or null')
    return raw


def _validate_content_envelope(raw: dict) -> None:
    """Validate nested product fields after call facts settle, before field access."""
    file_ids = {item['file_id'] for item in raw.get('files') or []}
    for index, spec in enumerate(raw.get('artifact_specs') or []):
        where = f'(result)/artifact_specs[{index}]'
        if not isinstance(spec, dict):
            raise EnvelopeError(where, 'artifact spec must be an object')
        if not isinstance(spec.get('file_id'), str) or spec['file_id'] not in file_ids:
            raise EnvelopeError(where + '/file_id', 'must reference a declared file')
        if not isinstance(spec.get('role'), str) or not spec['role']:
            raise EnvelopeError(where + '/role', 'must be a non-empty string')
        for slot in ('dependencies', 'derived_from', 'reference_regions', 'limitations'):
            if spec.get(slot) is not None and not isinstance(spec[slot], list):
                raise EnvelopeError(where + '/' + slot, 'must be an array')
        if spec.get('provenance') is not None and not isinstance(spec['provenance'], dict):
            raise EnvelopeError(where + '/provenance', 'must be an object')
    for index, review in enumerate(raw.get('reviews') or []):
        where = f'(result)/reviews[{index}]'
        if not isinstance(review, dict):
            raise EnvelopeError(where, 'review must be an object')
        try:
            validate_review_semantics(review)
        except ModelError as exc:
            raise EnvelopeError(where, str(exc)) from exc
    for index, page in enumerate(raw.get('pages') or []):
        if not isinstance(page, dict):
            raise EnvelopeError(f'(result)/pages[{index}]', 'page must be an object')
        if not isinstance(page.get('page_id'), str) or not page['page_id']:
            raise EnvelopeError(f'(result)/pages[{index}]/page_id', 'must be a non-empty string')
    for index, page_id in enumerate(raw.get('page_order') or []):
        if not isinstance(page_id, str) or not page_id:
            raise EnvelopeError(f'(result)/page_order[{index}]', 'must be a non-empty string')


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


def write_operation_journal(store: Store, journal: OperationJournal, *, committed: bool = False) -> None:
    directory = _operations_dir(store)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{journal.operation_id}.json"
    if path.exists() and not committed:
        existing = json.loads(path.read_text("utf-8"))
        if existing.get("result_digest") != journal.result_digest:
            raise TaskConflict(
                path.name,
                f"operation {journal.operation_id} journal conflicts with a different result",
            )
        return
    _atomic_write_bytes(path, canonical_json_bytes(journal.to_json()))


def _request_digest(task_id, operation_id, produced_against, envelope):
    return sha256_bytes(canonical_json_bytes({"task_id": task_id, "operation_id": operation_id,
                                             "produced_against": produced_against, "envelope": envelope}))


def _publish_receipt_cache(store, *, task, envelope, produced_against, result_digest, response):
    """The committed Document remains authoritative even if cache I/O fails."""
    try:
        write_operation_journal(store, OperationJournal(
            operation_id=task["operation_id"], task_id=task["task_id"], kind=envelope["kind"],
            produced_against=produced_against, result_digest=result_digest,
            revision_id=response["revision_id"], usage_events=envelope.get("usage_events") or [],
        ), committed=True)
    except OSError:
        return {"code": "receipt_cache_unavailable", "message": "result is committed; the derived receipt file could not be saved",
                "next_action": "retry the same task operation to rebuild its receipt cache"}
    return None


def _commit_adoption(store, *, document, base_revision, task, envelope, produced_against, result_digest, response):
    receipt = {"format": "operation_receipt.v1",
               "request_digest": _request_digest(task["task_id"], task["operation_id"], produced_against, envelope),
               "response": response}
    store.commit_change(base_revision=base_revision, document=document,
                        operation_id=task["operation_id"], operation_receipt=receipt)
    warning = _publish_receipt_cache(store, task=task, envelope=envelope, produced_against=produced_against,
                                     result_digest=result_digest, response=response)
    result = {**response, "operation_result": copy.deepcopy(response)}
    if warning:
        result["journal_warning"] = warning
    return result


def _lookup_task(document: dict, task_id: str, store: Store) -> dict:
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if task.get("task_id") == task_id:
            return task
    raise EnvelopeError(f"(task {task_id})", "task not found in current Document")


def task_inputs_current(store, document, task):
    if content_identity(document) == task.get('produced_against'):
        return True
    dispatched = store.load_document(task['dispatch_revision'])
    # Task facts are part of the dispatched input: a task-field change
    # (audience, decisions, ...) invalidates scoped results too, even when
    # pages/design/sources are untouched (spec v1.1 §5.4, c93 defect).
    if (compute_input_digest(dispatched) != compute_input_digest(document)
            or dispatched['design_context'] != document['design_context']):
        return False
    if task.get('kind') == 'compose' and task.get('intent') == 'input_revision':
        # The result writes the whole page order, so its read dependency must
        # include order and membership as well as normalized Page contents.
        return [(p['page_id'], p['page']['sha256']) for p in dispatched['pages']] == [
            (p['page_id'], p['page']['sha256']) for p in document['pages']]
    # Display names and source paths are not input semantics. A metadata-only
    # revision keeps even an initial, unscoped compose task usable.
    if content_identity({**document, 'sources': dispatched['sources']}) == task.get('produced_against'):
        return True
    if not task.get('scope_pages'):
        return False
    before = {e['page_id']: e for e in dispatched['pages']}
    after = {e['page_id']: e for e in document['pages']}
    slots = ('page','blueprint','svg','svg_preview') if task.get('review_stage') == 'page_visual' else (
        ('page','blueprint','svg') if task['kind'] in ('reconstruct','repair','review') else ('page',))
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


def _preflight_svg(store, document, entry, data, *, page=None):
    """Use the production parser and the current Page's approved assets before adoption."""
    import tempfile
    from .compiler.svg import parse_svg, SvgError
    from .pipeline import page_asset_paths
    with tempfile.TemporaryDirectory(prefix='svg-preflight-', dir=store.staging_dir) as temporary:
        mapping = page_asset_paths(store, document, entry, temporary, page=page)
        try:
            parse_svg(data, page_id=entry['page_id'], assets=mapping)
        except SvgError as exc:
            diagnostic = exc.diagnostic
            raise EnvelopeError(
                f"svg/{diagnostic['page_id']}/{diagnostic['element_id'] or 'root'}",
                f"{diagnostic['detail']}; {diagnostic['recovery']}",
            ) from exc


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
    derived_from = spec.get("derived_from") or []
    # P1-04: the original image must not be back-fed from derived/preview
    # products; a blueprint built on its own preview would fabricate lineage.
    if spec.get("role") == "blueprint":
        for ref in derived_from:
            try:
                parent = store.read_object_json(ref)
            except Exception as exc:
                raise EnvelopeError(
                    f"(result)/artifact_specs/{spec.get('role')}/derived_from",
                    f"blueprint derived_from is not resolvable: {ref.get('path')}",
                ) from exc
            if parent.get("schema_version") == "deck_artifact.v1" and parent.get("role") in (
                "svg_preview", "ppt_preview", "render_report", "object_trace",
                "source_extract", "comparison_crop",
            ):
                raise EnvelopeError(
                    f"(result)/artifact_specs/{spec.get('role')}/derived_from",
                    f"blueprint lineage must not derive from a {parent.get('role')} artifact",
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
        "derived_from": derived_from,
        "provenance": provenance,
        "reference_regions": spec.get("reference_regions") or [],
        "limitations": spec.get("limitations") or [],
    }
    validate_artifact_semantics(artifact)
    return artifact


def _adopt_review(store: Store, review: dict) -> dict:
    """Reviews must reference already-saved objects, never envelope aliases."""
    validate_review_semantics(review)
    finding_keys = [(item.get('finding_id'), item.get('page_id'))
                    for item in review.get('findings') or []]
    if len(finding_keys) != len(set(finding_keys)):
        raise EnvelopeError('review/findings', 'duplicate finding_id for the same page')
    for subject in review.get("subjects") or []:
        try:
            store.read_object_bytes(subject)  # must exist and match its digest
        except StoreError as exc:
            raise EnvelopeError('review/subjects', f'unreadable subject: {exc}') from exc
    replaced = review.get("replaces")
    if replaced is not None:
        # AC-R06 receiver side: R1 must replace the same logical review and
        # actually re-check a new product, not merely re-label the old one.
        try:
            prior = json.loads(store.read_object_bytes(replaced).decode("utf-8"))
        except StoreError as exc:
            raise EnvelopeError("review/replaces", f"replaced review not found: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EnvelopeError("review/replaces", "replaced object is not a review") from exc
        if prior.get("schema_version") != "deck_review.v1":
            raise EnvelopeError("review/replaces", "replaced object is not a review record")
        if (prior.get("review_id") != review.get("review_id") or
                prior.get("kind") != review.get("kind") or
                prior.get("review_stage", "final") != review.get("review_stage", "final")):
            raise EnvelopeError("review/replaces", "replaces must point at the same logical review")
        prior = {**prior, 'ref': replaced}
        old_findings = {f.get("finding_id"): f for f in prior.get("findings") or []}
        new_findings = {f.get("finding_id"): f for f in review.get("findings") or []}
        shared = old_findings.keys() & new_findings.keys()
        if not shared:
            raise EnvelopeError("review/replaces", "no shared finding_id with the replaced review")
        from .editing import _current_artifact_digests
        from .review import finding_closed
        context = _current_artifact_digests(
            store, store.load_document(),
            [*(prior.get('subjects') or []), *(review.get('subjects') or [])])
        for fid in shared:
            old, new = old_findings[fid], new_findings[fid]
            if new.get('page_id') != old.get('page_id'):
                raise EnvelopeError('review/replaces', 'finding page changed')
            if new.get('resolution') == 'accepted_variance':
                if old.get('impact') != 'needs_judgment':
                    raise EnvelopeError('review/replaces', 'only needs_judgment can accept a variance')
                if not (new.get('resolution_reason') or '').strip() or not review.get('observations') or not new.get('evidence'):
                    raise EnvelopeError('review/replaces', 'accepted variance needs reason, observation and evidence')
            if new.get('resolution') in ('fixed', 'accepted_variance'):
                for evidence in new.get('evidence') or []:
                    try:
                        store.read_object_bytes(evidence)
                    except StoreError as exc:
                        raise EnvelopeError('review/findings/evidence', f'unreadable evidence: {exc}') from exc
                if not finding_closed([prior, review], prior, old, context):
                    raise EnvelopeError('review/replaces',
                                        f"finding {fid!r} is not closed by a current same-page product, dependencies and evidence")
    return review


# Roles a task kind may write into page slots (spec 09.7 scope). Conservative:
# compose keeps full-deck semantics; blueprint writes the original image only;
# reconstruct/repair rework the SVG; review writes no artifacts.
_KIND_ARTIFACT_ROLES = {
    "compose": None,
    "blueprint": {"blueprint"},
    "reconstruct": {"svg"},
    "repair": {"svg"},
    "review": set(),
}


def _check_scope(kind: str, envelope: dict, task: dict) -> None:
    scope = task.get("scope_pages") or []
    pages = envelope.get("pages") or []
    page_order = envelope.get("page_order") or []
    page_ids = [page.get("page_id") for page in pages]
    if page_order and sorted(page_order) != sorted(page_ids):
        raise EnvelopeError(
            "(result)/page_order", "page_order must match the pages payload exactly"
        )
    # P1-03: artifact specs are scoped like pages — every page-bound artifact
    # must target an in-scope page with a role this task kind may write.
    allowed_roles = _KIND_ARTIFACT_ROLES.get(kind, set())
    for index, spec in enumerate(envelope.get("artifact_specs") or []):
        role = spec.get("role")
        page_id = spec.get("page_id")
        where = f"(result)/artifact_specs/{index}"
        if allowed_roles is None:
            continue  # compose: full-deck semantics
        if role not in allowed_roles:
            raise EnvelopeError(
                where, f"task kind {kind!r} may not deliver role {role!r} artifacts"
            )
        if not page_id or page_id not in scope:
            raise EnvelopeError(
                where, f"artifact targets page {page_id!r} outside the authorized scope {scope}"
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
            outside = [pid for pid in page_ids if pid not in scope]
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
        if task.get("protocol_version") == "generation.v1" and updated.get("evidence_level") == "provider_verified":
            updated["evidence_level"] = "host_reported"
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
    review_stage: str | None = None,
    intent: str | None = None,
    input_digest: str | None = None,
    input_revision_id: str | None = None,
    method_release: dict | None = None,
    review_units: list[dict] | None = None,
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
    if review_stage is not None:
        task['review_stage'] = review_stage
    if intent is not None:
        task['intent'] = intent
    if input_digest is not None:
        task['input_digest'] = input_digest
    if input_revision_id is not None:
        task['input_revision_id'] = input_revision_id
    if method_release is not None:
        task['method_release'] = method_release
    if review_units is not None:
        task['review_units'] = review_units
    validate_task_semantics(task)
    return task


def _validate_content_update_request(envelope: dict, document: dict, task: dict, content_update: dict) -> None:
    """Shape and scope checks for a compose/input_revision content_update (§5.4)."""
    if task.get("kind") != "compose" or task.get("intent") != "input_revision":
        raise EnvelopeError(
            "(result)/content_update",
            "content_update is only accepted by compose tasks dispatched with intent=input_revision",
        )
    allowed = {"input_digest", "upsert_pages", "remove_page_ids", "page_order",
               "impact_summary", "unchanged_reason"}
    unknown = sorted(set(content_update) - allowed)
    if unknown:
        raise EnvelopeError("(result)/content_update", f"unknown fields: {unknown}")
    for field in ("impact_summary", "unchanged_reason"):
        if field in content_update and not isinstance(content_update[field], str):
            raise EnvelopeError(f"(result)/content_update/{field}", "must be a string")
    for slot in ("pages", "page_order", "artifact_specs", "reviews"):
        if envelope.get(slot):
            raise EnvelopeError(
                f"(result)/{slot}",
                "input_revision results submit content_update only; no top-level pages, "
                "page_order, artifacts or reviews",
            )
    digest = content_update.get("input_digest")
    if digest != task.get("input_digest"):
        raise TaskConflict(
            "(result)/content_update/input_digest",
            "content_update input_digest does not match the dispatched input revision; "
            "read the new inputs and resubmit",
        )
    upserts = content_update.get("upsert_pages", [])
    removes = content_update.get("remove_page_ids", [])
    if not isinstance(upserts, list) or not all(
            isinstance(page, dict) and isinstance(page.get("page_id"), str) and page["page_id"]
            for page in upserts):
        raise EnvelopeError("(result)/content_update/upsert_pages",
                            "must be an array of complete Page v2 objects")
    if not isinstance(removes, list) or not all(isinstance(pid, str) and pid for pid in removes) or \
            len(set(removes)) != len(removes):
        raise EnvelopeError("(result)/content_update/remove_page_ids",
                            "must be unique page ids currently in the deck")
    if not upserts and not removes and not (content_update.get("unchanged_reason") or "").strip():
        raise EnvelopeError(
            "(result)/content_update/unchanged_reason",
            "an adoption with no page changes requires a concrete unchanged_reason",
        )
    upsert_ids = [page["page_id"] for page in upserts]
    if len(set(upsert_ids)) != len(upsert_ids):
        raise EnvelopeError("(result)/content_update/upsert_pages", "duplicate page_id")
    if set(upsert_ids) & set(removes):
        raise EnvelopeError("(result)/content_update", "a page cannot be both upserted and removed")
    old_ids = [entry["page_id"] for entry in document.get("pages") or []]
    ghosts = [pid for pid in removes if pid not in old_ids]
    if ghosts:
        raise EnvelopeError("(result)/content_update/remove_page_ids",
                            f"pages not in the current deck: {ghosts}")
    expected = (set(old_ids) - set(removes)) | set(upsert_ids)
    page_order = content_update.get("page_order")
    if (not isinstance(page_order, list) or not page_order
            or not all(isinstance(pid, str) and pid for pid in page_order)
            or len(set(page_order)) != len(page_order)
            or set(page_order) != expected):
        raise EnvelopeError(
            "(result)/content_update/page_order",
            "page_order must equal current pages minus removals plus additions; "
            "no ghost pages, duplicates or omissions",
        )


def _accept_content_update(store: Store, *, document: dict, task: dict, envelope: dict,
                           content_update: dict, result_digest: str, produced_against: str,
                           staged: dict[str, dict]) -> dict:
    """Adopt an input_revision result: only changed pages move (spec v1.1 §5.4).

    Unchanged pages keep every slot; changed pages keep their original
    blueprint as history while SVG/previews clear for reconstruction; new
    pages start from blueprint; removed pages exit the current set with their
    history intact. Changed content/order retires current deck outputs; their
    immutable objects remain available in history.
    """
    if not task_inputs_current(store, document, task):
        raise StaleInputContext('(content_update)', 'document changed since dispatch; run continue')
    _validate_content_update_request(envelope, document, task, content_update)
    violation = page_limit_violation({**document, 'pages': content_update['page_order']})
    if violation:
        raise EnvelopeError('(result)/content_update/page_order', violation)
    upserts = {}
    for index, page in enumerate(content_update.get("upsert_pages") or []):
        try:
            upserts[page["page_id"]] = check_page(page)
        except ModelError as exc:
            raise EnvelopeError(f"(result)/content_update/upsert_pages[{index}]", str(exc)) from exc

    updated_task = {**task, "status": "completed", "updated_at": _utc_now_iso()}
    old_entries = {entry["page_id"]: entry for entry in document.get("pages") or []}
    page_refs = {pid: store.put_json_object(page) for pid, page in upserts.items()}
    new_pages = []
    changed_ids = []
    for pid in content_update["page_order"]:
        old = old_entries.get(pid)
        if pid in page_refs:
            if old and old["page"]["sha256"] == page_refs[pid]["sha256"]:
                new_pages.append(dict(old))  # normalized bytes identical: all slots preserved
                continue
            changed_ids.append(pid)
            if old:
                entry = {**old, "page": page_refs[pid],
                         "svg": None, "svg_preview": None, "ppt_preview": None}
            else:
                entry = {"page_id": pid, "page": page_refs[pid], "blueprint": None,
                         "svg": None, "svg_preview": None, "ppt_preview": None}
            new_pages.append(entry)
        else:
            new_pages.append(dict(old))
    for pid in content_update.get("remove_page_ids") or []:
        changed_ids.append(pid)  # exits the current set; history stays

    new_document = bump_revision(document, {
        "operation_id": task["operation_id"], "kind": "content_update",
        "description": content_update.get("impact_summary") or envelope.get("notes")
        or "input revision adopted", "read_set": [],
    })
    new_document["pages"] = new_pages
    before_sequence = [(entry["page_id"], entry["page"]["sha256"]) for entry in document["pages"]]
    after_sequence = [(entry["page_id"], entry["page"]["sha256"]) for entry in new_pages]
    if before_sequence != after_sequence:
        new_document["outputs"] = dict.fromkeys(document["outputs"])
    new_document["content_basis"] = {
        "input_digest": content_update["input_digest"],
        "input_revision_id": task.get("input_revision_id"),
        "resolved_by_task_id": task["task_id"],
    }
    updated_task["result_refs"] = list(page_refs.values())
    validate_task_semantics(updated_task)
    task_ref = store.put_json_object(updated_task)
    _replace_task_in_document(new_document, task, task_ref, store)
    new_document["change"] = {
        "operation_id": task["operation_id"],
        "kind": "content_update",
        "description": content_update.get("impact_summary") or envelope.get("notes")
        or "input revision adopted",
        "read_set": [{"identity": f"document-revision:{task.get('dispatch_revision')}",
                      "sha256": produced_against}],
    }
    response = {
        "status": "accepted",
        "revision_id": new_document["revision_id"],
        "new_page_hashes": {pid: page_refs[pid]["sha256"] for pid in changed_ids if pid in page_refs},
        "unchanged_reason": (content_update.get("unchanged_reason") or "").strip() or None,
        "impact_summary": content_update.get("impact_summary"),
        "result_refs": list(page_refs.values()),
        "work_complete": derive_work_complete(new_document, store),
        "next_action": "continue_production",
    }

    return _commit_adoption(store, document=new_document, base_revision=document["revision_id"],
                            task=task, envelope=envelope, produced_against=produced_against,
                            result_digest=result_digest, response=response)


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
    # P1-03: an envelope is bound to the task's own operation; a different
    # operation id is a conflict, never a new submission channel.
    if operation_id != task.get("operation_id"):
        raise TaskConflict(
            f"(task {task_id})/operation_id",
            "operation_id does not match the dispatched task operation",
        )

    # Successful adoption completes the Task in the same pointer swap. New
    # active tasks have no committed receipt; avoid scanning every old revision
    # on the normal production path. Terminal retries recover from ancestry.
    receipt = store.operation_receipt(operation_id) if task.get("status") in (
        "completed", "cancelled", "superseded", "failed"
    ) or (_operations_dir(store) / f"{operation_id}.json").is_file() else None
    if receipt is not None:
        if task.get("status") == "superseded":
            raise StaleInputContext(f"(task {task_id})", "task was superseded by newer inputs; run continue")
        if receipt["request_digest"] != _request_digest(task_id, operation_id, produced_against, envelope):
            raise TaskConflict("(operation)", "same operation already applied with a different result or request binding")
        response = receipt["response"]
        warning = _publish_receipt_cache(store, task=task, envelope=envelope, produced_against=produced_against,
                                         result_digest=result_digest, response=response)
        replay = {**response, "status": "already_applied", "same_revision": True,
                  "operation_result": copy.deepcopy(response)}
        if warning:
            replay["journal_warning"] = warning
        return replay

    journal = read_operation_journal(store, operation_id)
    if journal is not None:
        if task.get("status") == "superseded":
            raise StaleInputContext(f"(task {task_id})", "task was superseded by newer inputs; run continue")
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

    if task.get("status") == "completed":
        # P1-03: a completed task only ever replays its original result (the
        # journal check above already returned already_applied for it). Any
        # other submission is refused; call facts are history, not a channel.
        raise TaskConflict(
            f"(task {task_id})",
            "task already completed; only the original operation result replays",
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
        conflict = StaleInputContext if task.get("status") == "superseded" else TaskConflict
        raise conflict(
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
        raise StaleInputContext(
            "(document)",
            "project content moved since dispatch; read the new inputs and rebase",
        )

    # Round-B: settle call facts BEFORE any content prevalidation, in its own
    # committed revision. A later content refusal must never erase already
    # observed call facts (spec 09.7 settle-then-adopt, as on the cancelled path).
    staged = _read_staged(store, operation_id, envelope)
    allowances_before = [dict(entry) for entry in (task.get("call_allowances") or [])]
    _settled_allowances(task, envelope.get("usage_events") or [], staged, store)
    if task.get("call_allowances") != allowances_before:
        validate_task_semantics(task)
        settled_ref = store.put_json_object(task)
        settled_doc = bump_revision(
            document,
            {"operation_id": f"settle-{operation_id}", "kind": "task_update",
             "description": "call facts settled before content adoption", "read_set": []},
        )
        settled_doc = _replace_task_ref(settled_doc, task, settled_ref, store)
        store.commit_change(base_revision=document["revision_id"], document=settled_doc,
                            operation_id=f"settle-{operation_id}")
        document = store.load_document()
    _validate_content_envelope(envelope)
    from .generation import adoption_binding, bind_artifact
    generation_binding = adoption_binding(store, document, task, envelope, staged)
    content_update = envelope.get("content_update")
    if task.get("intent") == "input_revision" and content_update is None:
        raise EnvelopeError("(result)/content_update",
                            "input_revision requires content_update; full pages cannot replace the deck")
    if content_update is not None:
        return _accept_content_update(
            store, document=document, task=task, envelope=envelope,
            content_update=content_update, result_digest=result_digest,
            produced_against=produced_against, staged=staged)
    _check_scope(envelope["kind"], envelope, task)
    stage = task.get('review_stage', 'final')
    if stage == 'page_visual' and len(task.get('scope_pages') or []) != 1:
        raise EnvelopeError('task/scope_pages', 'page_visual requires exactly one page; retire this historical task and continue')
    if stage == 'page_visual' and envelope['kind'] == 'repair' and envelope.get('reviews'):
        raise EnvelopeError('review', 'page_visual repair submits Page/SVG only; submit reviews in the subsequent review task')
    for review in envelope.get('reviews') or []:
        if review.get('review_stage', 'final') != stage:
            raise EnvelopeError('review/review_stage', 'review stage does not match the dispatched task')
    if stage == 'page_visual' and envelope['kind'] == 'review':
        from .review import PAGE_VISUAL_KINDS
        required = set(PAGE_VISUAL_KINDS)
        reviews_by_kind = {item.get('kind'): item for item in envelope.get('reviews') or []}
        if set(reviews_by_kind) != required or len(envelope.get('reviews') or []) != len(required):
            raise EnvelopeError('review/kind', 'page_visual requires exactly blueprint_content, blueprint_fidelity and readability')
        entry = next(e for e in document['pages'] if e['page_id'] == task['scope_pages'][0])
        subjects = {(ref['path'], ref['sha256']) for ref in (entry['page'], entry['blueprint'], entry['svg'], entry['svg_preview'])}
        from .editing import _current_artifact_digests
        from .production import resolve_design
        page = store.read_object_json(entry['page'])
        effective, _ = resolve_design(page, document['design_context'], document['design_context'].get('assets') or [])
        digests = _current_artifact_digests(store, document)
        required_deps = {f"content:page:{entry['page_id']}", f"blueprint:{entry['page_id']}",
                         f"artifact:svg:{entry['page_id']}", f"style:{entry['page_id']}"}
        required_deps.update(f'asset:{asset_id}' for asset_id in effective.get('allowed_asset_ids') or [])
        for item in reviews_by_kind.values():
            if any(f.get('page_id') != entry['page_id'] for f in item.get('findings') or []):
                raise EnvelopeError('review/findings/page_id', 'page_visual findings must name the reviewed page')
            if not subjects <= {(ref['path'], ref['sha256']) for ref in item.get('subjects') or []}:
                raise EnvelopeError('review/subjects', 'page_visual review must reference current Page, blueprint, SVG and SVG preview')
            deps = {f"{dep['kind']}:{dep['identity']}": dep['sha256'] for dep in item.get('dependencies') or []}
            if not required_deps <= deps.keys() or any(digests.get(key) != sha for key, sha in deps.items()):
                raise EnvelopeError('review/dependencies', 'page_visual review must bind current Page, blueprint, SVG, style and allowed assets')
    if stage == 'final' and envelope['kind'] == 'review' and envelope.get('reviews'):
        from .review import REVIEW_DIMENSIONS
        # The six content dimensions are required; professional_use and
        # desktop_editing remain valid supplementary final records.
        allowed_kinds = set(REVIEW_DIMENSIONS) | {'professional_use', 'desktop_editing'}
        pptx_ref = (document.get('outputs') or {}).get('pptx')
        pages_by_id = {e['page_id']: e for e in document.get('pages') or []}
        for item in envelope['reviews']:
            if item.get('kind') not in allowed_kinds:
                raise EnvelopeError('review/kind',
                                    f"final review kinds must be among {', '.join(sorted(allowed_kinds))}")
            cited = {(ref.get('path'), ref.get('sha256')) for ref in item.get('subjects') or []}
            if pptx_ref and (pptx_ref['path'], pptx_ref['sha256']) not in cited:
                raise EnvelopeError('review/subjects', 'final review must reference the current PPTX')
            for f in item.get('findings') or []:
                entry = pages_by_id.get(f.get('page_id'))
                if f.get('page_id') not in (task.get('scope_pages') or []) or not entry:
                    raise EnvelopeError('review/findings/page_id', 'final findings must name a page in the task scope')
                if (entry['page']['path'], entry['page']['sha256']) not in cited:
                    raise EnvelopeError('review/subjects', 'final review must reference the current Page of each finding')

    # Prevalidate everything before any adoption.
    adopted_pages = []
    for index, page in enumerate(envelope.get("pages") or []):
        try:
            adopted_pages.append(check_page(page))
        except ModelError as exc:
            raise EnvelopeError(f'(result)/pages[{index}]', str(exc)) from exc
    artifacts = []
    existing_page_ids = {entry.get("page_id") for entry in document.get("pages") or []} | {
        page["page_id"] for page in adopted_pages
    }
    candidates = {entry['page_id']: entry for entry in document.get('pages') or []}
    for page in adopted_pages:
        candidates.setdefault(page['page_id'], {'page_id': page['page_id'], 'page': None,
                                                'blueprint': None})
    adopted_by_id = {page['page_id']: page for page in adopted_pages}
    staged_blueprints = {spec['page_id']: staged[spec['file_id']]['bytes']
                         for spec in envelope.get('artifact_specs') or []
                         if spec.get('role') == 'blueprint' and spec.get('page_id')}
    for spec in envelope.get("artifact_specs") or []:
        if spec.get('role') == 'svg':
            entry = candidates.get(spec.get('page_id'))
            if entry:
                data = staged[spec['file_id']]['bytes']
                if entry['page_id'] in staged_blueprints:
                    _validate_svg_reference(data, sha256_bytes(staged_blueprints[entry['page_id']]))
                elif entry.get('blueprint'):
                    original=store.read_object_json(entry['blueprint'])
                    _validate_svg_reference(data,original['file']['sha256'])
                _preflight_svg(store, document, entry, data,
                               page=adopted_by_id.get(entry['page_id']))
        try:
            artifacts.append(bind_artifact(store, _build_artifact(store, spec, staged, existing_page_ids), generation_binding))
        except ModelError as exc:
            raise EnvelopeError(f'(result)/artifact_specs/{spec.get("role")}', str(exc)) from exc
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
    if envelope['kind'] == 'compose' or adopted_pages:
        resulting_ids = (envelope.get('page_order') or []) if envelope['kind'] == 'compose' else (
            {entry['page_id'] for entry in document['pages']} | {page['page_id'] for page in adopted_pages})
        violation = page_limit_violation({**document, 'pages': resulting_ids})
        if violation:
            raise EnvelopeError('(result)/pages', violation)
    page_refs = {}
    for page in adopted_pages:
        page_refs[page["page_id"]] = store.put_json_object(page)
    artifact_refs = [store.put_json_object(artifact) for artifact in artifacts]
    review_refs = [store.put_json_object(review) for review in reviews]
    updated_task["result_refs"] = list(page_refs.values()) + artifact_refs + review_refs
    validate_task_semantics(updated_task)
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
        if task.get("input_digest"):
            # The initial content is complete against its dispatch inputs.
            new_document["content_basis"] = {
                "input_digest": task["input_digest"],
                "input_revision_id": task.get("input_revision_id"),
                "resolved_by_task_id": task["task_id"],
            }
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
    response = {
        "status": "accepted",
        "revision_id": new_document["revision_id"],
        "new_page_hashes": {
            page_id: ref["sha256"] for page_id, ref in page_refs.items()
        },
        "result_refs": list(page_refs.values()) + artifact_refs + review_refs,
        "work_complete": derive_work_complete(new_document, store),
        "next_action": "auto_view_then_production"
        if envelope["kind"] == "compose"
        else "continue_production",
    }

    return _commit_adoption(store, document=new_document, base_revision=document["revision_id"],
                            task=task, envelope=envelope, produced_against=produced_against,
                            result_digest=result_digest, response=response)


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
def call_begin(store: Store, *, task_id: str, allowance_id: str, execution_ref: str | None,
               request_id: str | None = None) -> dict:
    """Atomically take one pre-allocated call allowance (spec 08.6, T13.min)."""
    document = store.load_document()
    task = _lookup_task(document, task_id, store)
    from .generation import is_new, check_host, begin_attempt
    check_host(task)
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
            if is_new(task):
                _, attempt, ref = begin_attempt(store, document, task, allowance_id, execution_ref, request_id)
                return {"status": "already_started", "task_id": task_id, "allowance_id": allowance_id,
                        "attempt_id": attempt["attempt_id"], "attempt_ref": ref, "request_id": request_id}
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
    extra = {}
    updated_task = task
    if is_new(task):
        updated_task, attempt, ref = begin_attempt(store, document, task, allowance_id, execution_ref, request_id)
        extra = {"attempt_id": attempt["attempt_id"], "attempt_ref": ref, "request_id": request_id}
    elif request_id is not None:
        raise EnvelopeError("request_id", "old tasks cannot bind generation requests")
    updated_task = {**updated_task, "call_allowances": allowances, "updated_at": _utc_now_iso()}
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
    return {"status": "started", "task_id": task_id, "allowance_id": allowance_id, **extra}



def _provider_receipt(report_bytes) -> bool:
    """A tool-issued receipt: JSON carrying a provider identity and a signature."""
    if not report_bytes:
        return False
    try:
        payload = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False
    return bool(isinstance(payload, dict) and payload.get("provider")
                and payload.get("signature"))


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
    # Evidence grading (spec 08.6, round-B): provider_verified requires a
    # verifiable tool-issued receipt structure in the report bytes (a provider
    # identity plus a signature); a bare host report — with or without an
    # invocation_ref — stays host_reported and is never upgraded implicitly.
    target["evidence_level"] = "provider_verified" if _provider_receipt(report_bytes) else "host_reported"
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
    attempt_id: str | None = None,
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
    from .generation import is_new, settle_attempt
    extra = {}
    updated_task = task
    if is_new(task):
        updated_task, settled, ref = settle_attempt(store, document, task, target, attempt_id=attempt_id,
                                                   outcome=outcome, report_bytes=report_bytes, invocation_ref=invocation_ref)
        extra = {"attempt_id": attempt_id, "attempt_ref": ref}
    else:
        if attempt_id is not None:
            raise EnvelopeError("attempt_id", "old tasks cannot bind generation attempts")
        settled = _settle_target(store, document, task_id, allowance_id, target, outcome,
                                 report_bytes, report_ext, invocation_ref)
    if settled == target and updated_task == task:
        return {"status": "already_settled", "task_id": task_id, "allowance_id": allowance_id, **extra}
    target.update(settled)
    updated_task = {
        **updated_task,
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
    return {"status": "settled", "task_id": task_id, "allowance_id": allowance_id, "outcome": outcome, **extra}


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
