"""Read-only check that a proposed PPTX handoff belongs to the current run."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path
from pptx.exc import PackageNotFoundError
from lxml.etree import XMLSyntaxError

from .editing import check_summary
from .store import Store, StoreError


def _historical_outputs(store, document):
    """Index committed originals by metadata and size; do not read every PPTX."""
    from .models import validate_ref, validate_schema
    from .snapshots import committed_snapshots
    objects, rows, gaps = {}, [], []
    try:
        for snapshot in committed_snapshots(store, head_revision=document['revision_id']):
            prior = (snapshot.get('outputs') or {}).get('pptx')
            if not prior:
                continue
            try:
                key = prior['sha256']
                if key not in objects:
                    output = store.read_object_json(prior)
                    validate_schema('artifact', output)
                    if output['role'] != 'pptx':
                        raise ValueError('historical output is not a PPTX artifact')
                    ref = output['file']
                    validate_ref(ref, where='historical_output')
                    info = store._resolve_object_path(ref['path']).lstat()
                    if not stat.S_ISREG(info.st_mode):
                        raise ValueError('historical output is not a regular file')
                    objects[key] = (ref, info.st_size)
                ref, size = objects[key]
                rows.append({'revision_id': snapshot['revision_id'], 'output_ref': prior,
                             'file_ref': ref, 'file_sha256': ref['sha256'], 'size': size})
            except (StoreError, OSError, ValueError) as exc:
                gaps.append({'code': 'historical_output_unverifiable',
                             'revision_id': snapshot['revision_id'], 'reason': type(exc).__name__})
    except (StoreError, OSError, ValueError) as exc:
        gaps.append({'code': 'historical_output_unverifiable', 'reason': type(exc).__name__})
    return rows, gaps


def check_handoff(project_dir, *, file_path, purpose="review", notes_policy=None):
    if purpose not in ("review", "delivery"):
        raise ValueError("purpose must be review or delivery")
    candidate = Path(file_path).expanduser().absolute()
    if not candidate.is_file() or candidate.suffix.lower() != ".pptx":
        raise ValueError("file must be an existing PPTX")

    store = Store(Path(project_dir).expanduser())
    document = store.load_document()
    from .exports import resolve_notes_policy, _page_notes, _pptx_projection_notes
    resolved_notes = resolve_notes_policy(store, document, notes_policy)
    if purpose == "delivery":
        from . import eligibility
        from .delivery_eligibility import selected_output
        selected = selected_output(store, document, notes_policy=notes_policy, file_path=candidate)
        decision = eligibility.evaluate(store, document, document, "handoff.delivery",
                                        {"expected_output_ref": (document.get("outputs") or {}).get("pptx"), "selected_output": selected})
        if not decision["allowed"]:
            raise eligibility.EligibilityBlocked(decision)
    output_ref = (document.get("outputs") or {}).get("pptx")
    expected_hash = None
    if output_ref:
        expected_hash = store.read_object_json(output_ref)["file"]["sha256"]
    from .selected_file import read_selected_file, SelectedFileConflict
    sanitized_hash = None
    sizes = set()
    if output_ref:
        from .export_sanitize import pptx
        from .operations import OperationError
        original = store.read_object_json(output_ref)['file']
        raw = store.read_object_bytes(original)
        sizes.add(len(raw))
        try:
            records = _pptx_projection_notes(store, document, resolved_notes)
            projected = pptx(raw, 'deck.pptx', notes=records, include_notes=resolved_notes['pptx_notes'])
            sizes.add(len(projected))
            sanitized_hash = hashlib.sha256(projected).hexdigest()
        except OperationError:
            pass
    candidate_bytes, actual_hash = b'', None
    try:
        if sizes:
            candidate_bytes, actual_hash = read_selected_file(candidate, sizes=sizes)
    except SelectedFileConflict as exc:
        if exc.error_code != 'candidate_not_selected_output':
            raise
    matches, history_gaps, history_status = [], [], 'not_requested'
    if purpose == 'review' and (actual_hash is None or actual_hash not in (expected_hash, sanitized_hash)):
        rows, history_gaps = _historical_outputs(store, document)
        sizes.update(row['size'] for row in rows)
        if actual_hash is None and sizes:
            try:
                candidate_bytes, actual_hash = read_selected_file(candidate, sizes=sizes)
            except SelectedFileConflict as exc:
                if exc.error_code != 'candidate_not_selected_output':
                    raise
        matched = [row for row in rows if row['file_sha256'] == actual_hash]
        attempted = set()
        for row in matched:
            key = row['file_sha256']
            if key in attempted:
                continue
            attempted.add(key)
            try:
                store.read_object_bytes(row['file_ref'])  # verifies the matched immutable hash once
            except (StoreError, OSError, ValueError) as exc:
                history_gaps.append({'code': 'historical_output_unverifiable',
                                     'revision_id': row['revision_id'], 'reason': type(exc).__name__})
        history_status = 'incomplete' if history_gaps else 'complete'
        if not history_gaps:
            matches = [{k: row[k] for k in ('revision_id', 'output_ref', 'file_sha256')} for row in matched]
    gaps = []
    if history_gaps:
        gaps.append('historical_output_unverifiable')
    if not output_ref:
        gaps.append("missing_current_pptx")
    if actual_hash is None or actual_hash not in (expected_hash, sanitized_hash):
        gaps.append("candidate_not_current_output")
    from .compiler.native import notes_records
    try:
        actual_notes = notes_records(candidate_bytes)
        page_notes = _page_notes(store, document)
        expected_text = [p['notes'] if resolved_notes['pptx_notes'] else '' for p in page_notes]
        strict_notes = _pptx_projection_notes(store, document, resolved_notes) is not None
        if (strict_notes and (len(actual_notes) != len(expected_text) or
                              [r['notes'] for r in actual_notes] != expected_text)):
            gaps.append('candidate_notes_policy_mismatch')
        elif not strict_notes and any(r['notes'] for r in actual_notes):
            gaps.append('candidate_notes_policy_mismatch')
        elif strict_notes and [r['page_id'] for r in actual_notes] != [p['page_id'] for p in page_notes]:
            gaps.append('candidate_notes_page_identity_mismatch')
    except (ValueError, KeyError, zipfile.BadZipFile, PackageNotFoundError, XMLSyntaxError):
        gaps.append('candidate_notes_unreadable')
    for entry in document.get("pages") or []:
        for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
            if not entry.get(slot):
                gaps.append(f"{entry['page_id']}:missing_{slot}")

    from .review import task_blocks_current_output
    pending = []
    for ref in document.get("tasks") or []:
        task = store.read_object_json(ref)
        if task_blocks_current_output(task, store=store, document=document):
            pending.append({"task_id": task["task_id"], "kind": task["kind"], "status": task["status"]})
    if pending:
        gaps.append("pending_host_tasks")

    report_ref = (document.get("outputs") or {}).get("render_report")
    report_status = None
    if report_ref:
        report = json.loads(store.read_object_bytes(store.read_object_json(report_ref)["file"]))
        report_status = report.get("status")
    if report_status != "pass":
        gaps.append("render_report_not_pass")

    review_status = check_summary(store, document)["status"] if output_ref else "not_evaluated"
    if purpose == "delivery" and review_status != "pass":
        gaps.append("required_review_not_pass")
    from .delivery_eligibility import professional_policy
    professional = professional_policy(store, document, selected_output=selected if purpose == "delivery" else None)
    if purpose == "delivery" and professional["required"] and not professional["satisfied"]:
        gaps.append("professional_review_not_satisfied")
    from .models import input_alignment
    alignment = input_alignment(document)
    if alignment == "needs_reconciliation":
        # Refused for both purposes: the deck cannot be handed off against an
        # input version it was not built on (spec v1.1 §5.5).
        gaps.append("input_reconciliation_pending")

    return {
        "status": "verified" if not gaps else "blocked",
        "project_id": document["project_id"],
        "revision_id": document["revision_id"],
        "purpose": purpose,
        "notes_policy": resolved_notes,
        "file": str(candidate),
        "file_sha256": actual_hash,
        "current_pptx_sha256": expected_hash,
        "sanitized_pptx_sha256": sanitized_hash,
        "candidate_relation": ("immutable_original" if actual_hash is not None and actual_hash==expected_hash else "sanitized_copy" if actual_hash is not None and actual_hash==sanitized_hash else "historical_output" if matches else "unverified"),
        "matched_historical_outputs": matches,
        "history_status": history_status,
        "history_gaps": history_gaps,
        "input_alignment": alignment,
        "page_count": len(document.get("pages") or []),
        "render_report_status": report_status or "not_evaluated",
        "review_status": review_status,
        "professional": {
            "required": professional["required"],
            "satisfied": professional["satisfied"],
            "human_signoff": professional["human_signoff"],
            "gap_reasons": professional["gap_reasons"],
        },
        "pending_tasks": pending,
        "gaps": gaps,
        "evidence_level": "engineering",
        "next_action": None if not gaps else "continue_current_project",
    }
