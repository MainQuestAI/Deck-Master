"""Frozen-revision exports. Public copies and internal recovery bundles are distinct."""

from __future__ import annotations
from contextlib import nullcontext
import copy
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
import uuid
import zipfile

from . import operations
from .errors import InputReconciliationPending
from .export_sanitize import sanitize, text_safe, pptx as sanitize_pptx, link_safe, public_projection_safe
from .local_state import local_lock, safe_path
from .models import canonical_json_bytes, input_alignment, page_limit_violation, sha256_bytes, validate_ref, validate_schema
from .snapshots import load_snapshot, _snapshot
from .store import Store, CURRENT_FORMAT, WORKBENCH_FORMAT
from .ui_journal import _logical_identity


class ExportError(operations.OperationError):
    def __init__(self, code, message, *, revision=None, gaps=None, exit_code=3, http_status=409):
        super().__init__(code, "export", message, exit_code=exit_code, http_status=http_status)
        self.revision = revision
        self.gaps = gaps or []

    def payload(self):
        result = super().payload()
        result["error"].update(
            revision_id=self.revision,
            gaps=self.gaps,
            docs_ref="docs/agent-recovery-playbook.md#versioned-exports",
            next_action="inspect the selected snapshot gaps; complete the relevant page/layer or export a review copy",
        )
        return result


class ExportInputPending(ExportError, InputReconciliationPending):
    """Keep the existing Python exception type and the structured export gaps."""


def _context(project, revision):
    store = Store(project)
    doc = load_snapshot(store, revision)
    return store, doc, _logical_identity(str(store.project_root), doc["revision_id"])


def _facts(store, doc, *, selected_output=None, control=None, read_context=None, deck_output=None):
    control = store.load_document() if control is None else control
    doc = {**doc, "policy": control["policy"], "reviews": control.get("reviews", [])}
    from .editing import ReviewReadContext, check_summary
    from .production_detail import projection
    from .workbench import _ReadContext, _deck_output

    review_context = (read_context.require(store, doc) if read_context is not None and read_context.document == doc
                      else ReviewReadContext(store, doc))
    summary = check_summary(store, doc, read_context=review_context)
    ctx = _ReadContext(store, doc)
    # A paired summary may supply the same artifact's already-checked output.
    # The control overlay above changes policy/reviews only, not output inputs.
    # Standalone exports retain their own original output check.
    output = _deck_output(ctx) if deck_output is None else deck_output
    production = [projection(ctx, page, output) for page in doc["pages"]]
    gaps = [
        {"page_id": e["page_id"], "layer": layer, "reason": "not_recorded"}
        for e in doc["pages"]
        for layer in ("page", "blueprint", "svg", "svg_preview", "ppt_preview")
        if not e.get(layer)
    ]
    if output.get("applicability") == "basis_changed":
        gaps.append({"page_id": None, "layer": "ppt", "reason": "basis_changed"})
    if not doc["outputs"].get("pptx"):
        gaps.append({"page_id": None, "layer": "ppt", "reason": "not_recorded"})

    def quality_gap(dimension, reason):
        layer, separator, page_id = dimension.rpartition(":")
        scoped = bool(separator and page_id in {p["page_id"] for p in doc["pages"]})
        return {"page_id": page_id if scoped else None, "layer": layer if scoped else dimension, "reason": reason}

    for dimension in summary["missing_dimensions"]:
        gaps.append(quality_gap(dimension, "not_evaluated"))
    for dimension, value in summary["dimensions"].items():
        if value["open_must_fix"] or value["status"] == "fail":
            gaps.append(quality_gap(dimension, "unresolved"))
    if page_limit_violation(doc):
        gaps.append({"page_id": None, "layer": "page_limit", "reason": "page_limit_violation"})
    output_facts = summary.get("output_facts") or {}
    if output_facts.get("render_report_missing"):
        gaps.append({"page_id": None, "layer": "render_report", "reason": "not_recorded"})
    elif output_facts.get("render_report_status") == "fail":
        gaps.append({"page_id": None, "layer": "render_report", "reason": "unresolved"})
    for key, reason in (summary.get("dimension_reasons") or {}).items():
        gaps.append(quality_gap(key, reason))
    from .delivery_eligibility import professional_policy
    professional = professional_policy(store, doc, selected_output=selected_output, read_context=review_context)
    if professional["required"] and not professional["satisfied"]:
        # Report the named professional gaps wherever this snapshot's gaps are
        # listed, including when the engineering gate refuses first.
        gaps.extend({"page_id": None, "layer": "professional_use", "reason": reason}
                    for reason in professional["gap_reasons"])
    return {
        "revision_id": doc["revision_id"],
        "input_alignment": getattr(store, "input_alignment", input_alignment)(doc),
        "check_summary": summary,
        "production": production,
        "professional_evidence": professional["evidence"],
        "professional": professional,
        "gaps": gaps,
    }


@operations.public
def describe(project, *, revision=None):
    store, doc, _ = _context(project, revision)
    return {"project_id": doc["project_id"], **_facts(store, doc), "purposes": ["review", "delivery", "engineering"]}


def _engineering_ready(doc, facts):
    """The recorded engineering predicate used by export and its read-only UI.

    A passing review cannot make an output compiled from another SVG basis
    current. Input reconciliation keeps its existing distinct export error.
    """
    return bool(doc['outputs'].get('pptx')
                and facts['input_alignment'] != 'needs_reconciliation'
                and facts['check_summary']['status'] == 'pass'
                and not any(gap['reason'] == 'basis_changed' for gap in facts['gaps']))


def _gate(store, doc, facts, purpose):
    if purpose != "delivery":
        return
    if facts["input_alignment"] == "needs_reconciliation":
        raise ExportInputPending(
            "input_reconciliation_pending",
            "selected snapshot inputs await Host reconciliation",
            revision=doc["revision_id"],
            gaps=[{"page_id": None, "layer": "content", "reason": "needs_reconciliation"}],
        )
    if not _engineering_ready(doc, facts):
        raise ExportError(
            "delivery_blocked",
            ("no current PPT; " if not doc["outputs"].get("pptx") else "")
            + "delivery requires every required check to pass on the selected snapshot"
            + ("; page_limit_violation" if page_limit_violation(doc) else ""),
            revision=doc["revision_id"],
            gaps=facts["gaps"],
        )
    professional = facts["professional"]
    if professional["required"] and not professional["satisfied"]:
        # Unified predicate (delivery_eligibility): only a verified human
        # professional_use pass on the exact current deck satisfies this gate.
        raise ExportError(
            "delivery_blocked",
            "selected snapshot needs professional or human review",
            revision=doc["revision_id"],
            gaps=[{"page_id": None, "layer": "professional_use", "reason": reason}
                  for reason in professional["gap_reasons"]],
        )


def _public_report(doc, facts, purpose):
    ordinal = {p["page_id"]: i + 1 for i, p in enumerate(doc["pages"])}
    s = facts["check_summary"]
    return {
        "revision_id": doc["revision_id"],
        "purpose": purpose,
        "review_status": s["status"],
        "input_alignment": facts["input_alignment"],
        "unresolved": {
            "missing_dimensions": s["missing_dimensions"],
            "failed_dimensions": [k for k, v in s["dimensions"].items() if v["status"] == "fail" or v["open_must_fix"]],
            "gaps": [{**{k: v for k, v in gap.items() if k != "page_id"}, "page": ordinal.get(gap["page_id"])} for gap in facts["gaps"]],
        },
        "editability": facts["production"][0]["pptx"]["editability"]
        if facts["production"] and facts["production"][0]["pptx"].get("editability")
        else "unknown",
        "professional_evidence": facts["professional_evidence"],
        "desktop_editing": facts["professional_evidence"]["desktop_editing"],
        "professional": {
            "required": facts["professional"]["required"],
            "satisfied": facts["professional"]["satisfied"],
            "human_signoff": facts["professional"]["human_signoff"],
            "gap_reasons": facts["professional"]["gap_reasons"],
        },
        "evidence_level": "engineering",
        "pages": [
            {
                "page": i + 1,
                "text_runs": p["render_report"]["text_runs"],
                "native_shapes": p["render_report"]["native_shapes"],
                "engineering_status": p["render_report"]["recorded_status"],
                "svg_input_image_elements": p["object_trace"]["svg_input_image_elements"],
                "font_substitution": p["font_substitution"],
                "compiler_font_count": len(p["object_trace"]["compiler_fonts"]),
                "font_diagnostic_count": len(p["object_trace"]["diagnostics"]),
                "professional": {k: v["status"] for k, v in p["evaluations"].items()},
                "limitations": p["limitations"],
            }
            for i, p in enumerate(facts["production"])
        ],
        "notice": "待按新要求更新"
        if facts["input_alignment"] == "needs_reconciliation"
        else (
            "Professional delivery gate is not satisfied on this snapshot; this copy is for review only and records no human approval."
            if facts["professional"]["required"] and not facts["professional"]["satisfied"]
            else "See the recorded gaps and independent review status."
        ),
        "package_notice": "Public reading copy; internal sources, prompts, project objects and presenter notes are excluded."
        if purpose != "engineering"
        else "Internal recovery package; contains original sources, prompts and project history. No runtime authentication files or personal UI journal.",
        "metadata_cleanup": (
            "Original bytes preserved for internal recovery."
            if purpose == "engineering"
            else "PNG text/EXIF, SVG metadata/comments, PPT properties/notes/comments removed in copies; visible facts still require review."
        ),
    }


def _visible_text(visible):
    """Only schema-declared customer-facing strings; no citations/notes/prompts."""
    lines = []

    def walk(value, key=None):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for item in value:
                walk(item, key)
        elif isinstance(value, str) and key in ("title", "subtitle", "text", "heading", "label", "display_text"):
            lines.append(value)

    title = visible.get("title", "")
    lines.append(title)
    walk({k: v for k, v in visible.items() if k != "title"})
    return lines


def _artifact(store, ref, role, page_id):
    value = store.read_object_json(ref)
    validate_schema("artifact", value)
    if value["role"] != role or value["page_id"] != page_id:
        raise ExportError("export_artifact_mismatch", "artifact does not belong to the selected page and layer", exit_code=4)
    return value


def resolve_notes_policy(store, document, notes_policy=None):
    """Resolve a projection choice against this exact selected snapshot."""
    if isinstance(notes_policy, dict):
        resolved = resolve_notes_policy(store, document, notes_policy.get('selection') if notes_policy.get('source') == 'explicit' else None)
        if resolved != notes_policy:
            raise ExportError('invalid_notes_policy', 'resolved notes policy belongs to another selected snapshot', exit_code=2, http_status=422)
        return resolved
    choices = ('pptx_notes', 'separate_script', 'both', 'pure_reading')
    if notes_policy is not None and notes_policy not in choices:
        raise ExportError('invalid_notes_policy', 'choose pptx_notes, separate_script, both or pure_reading',
                          exit_code=2, http_status=422)
    plan_ref = document.get('content_plan')
    plan = store.read_object_json(plan_ref) if plan_ref else {}
    if plan_ref:
        from .models import validate_content_plan_semantics
        validate_content_plan_semantics(plan)
    speech = (plan.get('input') or {}).get('speech_policy') or plan.get('speech_policy') or {}
    if speech and plan.get('mode') in ('bound', 'imported_mapping'):
        links = plan.get('page_links') or []
        expected_links = {entry['page_id']: entry['page'] for entry in document['pages']}
        actual_links = {link.get('page_id'): link.get('page_ref') for link in links}
        if len(actual_links) != len(links) or actual_links != expected_links:
            raise ExportError('export_notes_mapping_invalid', 'selected Plan does not bind the exact current Page set', exit_code=4)
    if speech:
        from .content_production import speech_policy as effective_speech_policy
        effective = effective_speech_policy(document, plan_input=plan.get('input') or {'speech_policy': speech})
    else:
        # A projection of existing notes creates no new speech instruction.
        effective = {'mode': 'none', 'output': 'none'}
    mode = effective['mode']
    selected = notes_policy
    source = 'explicit' if selected is not None else 'plan' if speech else 'preserve_existing'
    if selected is None:
        selected = effective['output'] if mode != 'none' else None
        if selected not in choices:
            selected = 'pptx_notes'
    from .compiler.native import normalize_notes
    pages = []
    for entry in document['pages']:
        page = store.read_object_json(entry['page'])
        if page['page_id'] != entry['page_id']:
            raise ExportError('export_notes_mapping_invalid', 'Page identity differs from selected Document', exit_code=4)
        text = normalize_notes(page.get('speaker_notes', ''))
        pages.append({'page_id': entry['page_id'], 'page_sha256': entry['page']['sha256'],
                      'notes_sha256': sha256_bytes(text.encode('utf-8'))})
    if len({p['page_id'] for p in pages}) != len(pages):
        raise ExportError('export_notes_mapping_invalid', 'selected Page IDs must be unique', exit_code=4)
    return {'selection': selected, 'source': source, 'speech_mode': mode,
            'plan_sha256': plan_ref['sha256'] if plan_ref else None, 'newlines': 'LF',
            'pptx_notes': selected in ('pptx_notes', 'both'),
            'separate_script': selected in ('separate_script', 'both'), 'pages': pages}


def _page_notes(store, doc):
    from .compiler.native import normalize_notes
    return [{'page_id': entry['page_id'],
             'title': store.read_object_json(entry['page'])['customer_visible'].get('title', ''),
             'notes': normalize_notes(store.read_object_json(entry['page']).get('speaker_notes', ''))}
            for entry in doc['pages']]


def _pptx_projection_notes(store, doc, policy):
    """Return the full identity promise even when all notes are empty."""
    notes = _page_notes(store, doc)
    output = (doc.get('outputs') or {}).get('pptx')
    artifact = store.read_object_json(output) if output else {}
    notes_aware = any(d.get('kind') == 'content' and str(d.get('identity', '')).startswith('page_notes:')
                      for d in artifact.get('dependencies') or [])
    if notes_aware or policy['source'] in ('explicit', 'plan') or any(p['notes'] for p in notes):
        return notes
    return None


def _write_public(store, doc, target, report):
    notes_policy = report['notes_policy']
    public_projection_safe(report, 'delivery.json')
    headings = []
    original_hashes = {}
    for i, entry in enumerate(doc["pages"], 1):
        directory = target / f"page-{i:03d}"
        directory.mkdir()
        page = store.read_object_json(entry["page"])
        lines = _visible_text(page["customer_visible"])
        text = "\n\n".join(lines) + "\n"
        text_safe(text, f"page-{i:03d}/content")
        (directory / "content.txt").write_text(text, encoding="utf-8")
        headings.append(f"<section><h2>Page {i}</h2>" + "".join("<p>" + html.escape(line) + "</p>" for line in lines) + "</section>")
        for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
            if not entry.get(slot):
                continue
            obj = _artifact(store, entry[slot], slot, entry["page_id"])
            ref = obj["file"]
            suffix = Path(ref["path"]).suffix
            name = f"page-{i:03d}/{slot}{suffix}"
            (target / name).write_bytes(sanitize(store.read_object_bytes(ref), suffix, name))
            original_hashes[name] = ref["sha256"]
    if doc["outputs"].get("pptx"):
        artifact = _artifact(store, doc["outputs"]["pptx"], "pptx", None)
        ref = artifact["file"]
        records = _pptx_projection_notes(store, doc, notes_policy)
        (target / "deck.pptx").write_bytes(sanitize_pptx(store.read_object_bytes(ref), 'deck.pptx',
            notes=records, include_notes=notes_policy['pptx_notes']))
        original_hashes["deck.pptx"] = ref["sha256"]
    if notes_policy['separate_script']:
        pages = _page_notes(store, doc)
        for page in pages:
            text_safe(page['title'], 'speaker-script/title')
            text_safe(page['notes'], 'speaker-script/notes')
            for url in re.findall(r'https?://[^\s<>]+', page['notes'], re.I):
                link_safe(url, 'speaker-script/notes/link')
        script = {'schema_version': 'speaker_script_projection.v1', 'revision_id': doc['revision_id'],
                  'purpose': report['purpose'], 'newlines': 'LF', 'pages': pages}
        public_projection_safe(script, 'speaker-script')
        (target / 'speaker-script.json').write_bytes(canonical_json_bytes(script))
        # A readable view and its exact structured pairing are two projections
        # of the same Page truth; edits must be written back to Page notes.
        script_text = '\n\n'.join(f"[{page['page_id']}] {page['title']}\n{page['notes']}" for page in pages)
        (target / 'speaker-script.txt').write_text(script_text, encoding='utf-8', newline='\n')
    (target / "review.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Fixed revision review</title><body><h1>Review '
        + html.escape(doc["revision_id"])
        + "</h1><p>See delivery.json for missing stages and independent review status.</p>"
        + "".join(headings)
        + "</body></html>",
        encoding="utf-8",
    )
    (target / "delivery.json").write_bytes(canonical_json_bytes(report))
    return original_hashes


def _write_engineering(store, doc, target):
    portable = target / "project" / ".deckmaster"
    portable.mkdir(parents=True)
    seen = set()

    def collect(value, *, leaf=False):
        if isinstance(value, dict):
            if set(value) == {"path", "sha256"}:
                # Frozen SVG locators share these keys with object refs, but
                # identify XML elements rather than portable files.
                if re.fullmatch(r"[0-9]+(?:/[0-9]+)*", str(value["path"])) and re.fullmatch(r"[a-f0-9]{64}", str(value["sha256"])):
                    return
                validate_ref(value, where="engineering/ref")
                key = value["path"]
                if key in seen:
                    return
                seen.add(key)
                raw = store.read_object_bytes(value)
                out = target / "project" / key
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(raw)
                if key.endswith(".json") and not leaf:
                    try:
                        collect(json.loads(raw))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        pass
            else:
                for name, child in value.items():
                    collect(child, leaf=name in ("file", "original_file"))
        elif isinstance(value, list):
            for child in value:
                collect(child)

    historic = doc
    visited = set()
    while historic:
        if historic["revision_id"] in visited:
            raise ExportError("export_history_invalid", "cyclic snapshot history")
        visited.add(historic["revision_id"])
        folder = portable / "revisions"
        folder.mkdir(exist_ok=True)
        (folder / (historic["revision_id"] + ".json")).write_bytes(canonical_json_bytes(historic))
        collect(historic)
        historic = _snapshot(store, historic["parent_revision_id"]) if historic.get("parent_revision_id") else None
    pointer = {"format": CURRENT_FORMAT, "revision_id": doc["revision_id"]}
    if doc.get("compatibility"):
        pointer.update(format=WORKBENCH_FORMAT, minimum_writer=doc["compatibility"]["minimum_writer"])
    (portable / "current.json").write_bytes(canonical_json_bytes(pointer))
    (target / "INTERNAL-RECOVERY.txt").write_text(
        "Internal only: original materials, complete prompts, immutable objects and committed history.\nOpen the project directory with a compatible core. Service state, authentication, caches and personal UI drafts are excluded.\n",
        encoding="utf-8",
    )


def variant_metadata(store, doc):
    """The live/read variant this revision belongs to, as fixed labels and refs.

    CONTRACTS §11.7.2: the versioned export records group_id/variant_id/label
    plus the frozen Narrative/Plan refs; it never creates a second content
    truth or a second current pointer.
    """
    request = (doc.get("collaboration") or {}).get("request") or {}
    variant = request.get("variant")
    if not variant:
        return None
    return {
        "group_id": variant.get("group_id"),
        "variant_id": variant.get("variant_id"),
        "label": variant.get("label"),
        "narrative_ref": doc.get("narrative"),
        "plan_ref": doc.get("content_plan"),
    }


def _bundle(store, doc, identity, purpose, export_id, target, notes_policy):
    from .delivery_eligibility import selected_output
    selected = selected_output(store, doc, notes_policy=notes_policy) if purpose != "engineering" else None
    facts = _facts(store, doc, selected_output=selected)
    _gate(store, doc, facts, purpose)
    report = _public_report(doc, facts, purpose)
    report['notes_policy'] = notes_policy
    if purpose != 'engineering':
        report['package_notice'] = 'Public copy with the recorded presenter-notes policy; internal materials and prompts excluded.'
        report['metadata_cleanup'] = 'Hidden properties, original notes metadata and comments removed; only selected Page notes are projected.'
    originals = {}
    if purpose == "engineering":
        _write_engineering(store, doc, target)
        (target / "delivery.json").write_bytes(canonical_json_bytes(report))
    else:
        originals = _write_public(store, doc, target, report)
        if (target / "deck.pptx").is_file():
            store.put_blob((target / "deck.pptx").read_bytes(), ext="pptx")
    files = []
    for path in sorted(target.rglob("*")):
        if path.is_file():
            relative = path.relative_to(target).as_posix()
            raw = path.read_bytes()
            files.append({"path": relative, "sha256": sha256_bytes(raw), "size": len(raw), "original_sha256": originals.get(relative)})
    manifest = {
        "schema_version": "export_manifest.v1",
        "export_id": export_id,
        "project_identity": identity,
        "revision_id": doc["revision_id"],
        "purpose": purpose,
        "files": files,
        "excluded": ["runtime_authentication", "service_state", "locks", "personal_ui_drafts"],
        "metadata_policy": "original_internal" if purpose == "engineering" else "sanitized_public_copy",
        "notes_policy": notes_policy,
        "request_sha256": sha256_bytes(canonical_json_bytes({
            'project_identity': identity, 'revision_id': doc['revision_id'],
            'purpose': purpose, 'notes_policy': notes_policy})),
    }
    variant = variant_metadata(store, doc)
    if variant is not None:
        manifest["variant"] = variant
    if purpose != 'engineering':
        public_projection_safe(manifest, 'manifest.json')
    validate_schema("export_manifest", manifest)
    (target / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    filename = f"deck-{purpose}-{doc['revision_id'][:8]}.zip"
    with zipfile.ZipFile(target / filename, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(target / item["path"], item["path"])
        archive.write(target / "manifest.json", "manifest.json")
    return manifest, filename


@operations.public
def create(project, *, purpose="review", revision=None, export_id=None, output_dir=None, notes_policy=None):
    if purpose == "working":
        purpose = "review"
    if purpose not in ("review", "delivery", "engineering"):
        raise ExportError("invalid_export_purpose", "choose review, delivery or engineering", exit_code=2, http_status=422)
    if export_id is None:
        export_id = "export-" + str(uuid.uuid4())
    _id(export_id)
    store, doc, identity = _context(project, revision)
    resolved_notes = resolve_notes_policy(store, doc, notes_policy)
    if purpose == "delivery":
        _guard_delivery(store, doc, revision, resolved_notes)
    cache = safe_path(store.project_root, ".deckmaster", "workbench", "exports")
    cache.mkdir(parents=True, exist_ok=True)
    final = safe_path(cache, export_id)
    with local_lock(safe_path(cache, "exports.lock")):
        # The lock order is exports -> project. A request pause/revocation can
        # commit while an export waits for the cache lock. Once admitted again,
        # delivery publication and any external copy serialize with control
        # writes through the same project lock, including the final rename.
        with store._locked() if purpose == 'delivery' else nullcontext():
            if purpose == 'delivery':
                if revision is None:
                    doc = store.load_document()
                    resolved_notes = resolve_notes_policy(store, doc, notes_policy)
                _guard_delivery(store, doc, revision, resolved_notes)
            if final.exists():
                result = _record(store, identity, export_id)
                old_policy = result['manifest'].get('notes_policy')
                if (result["revision_id"] != doc["revision_id"] or result["purpose"] != purpose
                        or (old_policy != resolved_notes and (old_policy is not None or notes_policy is not None))):
                    raise ExportError("export_id_conflict", "export ID already belongs to another fixed request", exit_code=5)
            else:
                stage = Path(tempfile.mkdtemp(prefix=".export-", dir=cache))
                try:
                    manifest, filename = _bundle(store, doc, identity, purpose, export_id, stage, resolved_notes)
                    allowed = {v["path"]: {"sha256": v["sha256"], "size": v["size"]} for v in manifest["files"]}
                    for name in ("manifest.json", filename):
                        raw = (stage / name).read_bytes()
                        allowed[name] = {"sha256": sha256_bytes(raw), "size": len(raw)}
                    result = {
                        "schema_version": "export_record.v1", "export_id": export_id,
                        "project_identity": identity, "revision_id": doc["revision_id"],
                        "purpose": purpose, "archive": filename, "files": allowed, "manifest": manifest,
                    }
                    (stage / "export-record.json").write_bytes(canonical_json_bytes(result))
                    stage.rename(final)
                except BaseException:
                    shutil.rmtree(stage)
                    raise
            response = {"status": "exported", **copy.deepcopy(result), "download_url": f"/api/exports/{export_id}/files/{result['archive']}"}
            if output_dir is not None:
                destination = Path(output_dir).expanduser()
                _copy_bundle(project, result, destination)
                response['output_dir'] = str(destination)
    return response


def _guard_delivery(store, doc, revision, notes_policy):
    if input_alignment(doc) == 'needs_reconciliation':
        # Flow Quality SPEC §5.4 / AC-13 keeps this existing export failure at
        # CLI exit 3. New collaboration admission/report gaps remain exit 4.
        raise ExportInputPending('input_reconciliation_pending',
            'selected snapshot inputs await Host reconciliation', revision=doc['revision_id'],
            gaps=[{'page_id': None, 'layer': 'content', 'reason': 'needs_reconciliation'}])
    from . import eligibility
    from .delivery_eligibility import selected_output
    selected = selected_output(store, doc, notes_policy=notes_policy)
    action = 'delivery.historical' if revision else 'export.delivery'
    decision = eligibility.evaluate(store, doc, store.load_document(), action,
        {'expected_output_ref': (doc.get('outputs') or {}).get('pptx'), 'selected_output': selected})
    if not decision['allowed']:
        raise eligibility.EligibilityBlocked(decision)


def _copy_bundle(project, result, destination):
    if destination.exists():
        raise ExportError('export_destination_exists', 'destination exists; choose a new output directory',
            exit_code=2, http_status=422)
    store, _, identity = _context(project, None)
    record = _record(store, identity, result['export_id'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.delivery-', dir=destination.parent))
    try:
        for name in result['files']:
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_download_file(store, record, name)[0])
        if destination.exists():
            raise ExportError('export_destination_exists', 'destination exists; choose a new output directory',
                exit_code=2, http_status=422)
        stage.rename(destination)
    except BaseException:
        shutil.rmtree(stage)
        raise


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"export-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value):
        raise ExportError("invalid_export_id", "use an export ID returned by this project", exit_code=2, http_status=404)


def _record(store, identity, export_id):
    _id(export_id)
    path = safe_path(store.project_root, ".deckmaster", "workbench", "exports", export_id, "export-record.json")
    if not path.is_file():
        raise ExportError("export_not_found", "export is not available in this project", exit_code=2, http_status=404)
    result = json.loads(path.read_bytes())
    if result.get("project_identity") != identity or result.get("export_id") != export_id:
        raise ExportError("export_not_found", "export does not belong to this project", exit_code=2, http_status=404)
    validate_schema("export_manifest", result["manifest"])
    manifest = result["manifest"]
    if manifest.get('request_sha256') is not None:
        expected_request = sha256_bytes(canonical_json_bytes({
            'project_identity': identity, 'revision_id': manifest['revision_id'],
            'purpose': manifest['purpose'], 'notes_policy': manifest.get('notes_policy')}))
        if manifest['request_sha256'] != expected_request:
            raise ExportError('export_file_changed', 'export request differs from its recorded notes policy', exit_code=4)
    for key in ("export_id", "project_identity", "revision_id", "purpose"):
        if result.get(key) != manifest[key]:
            raise ExportError("export_file_changed", "export record differs from its manifest", exit_code=4)
    archive = f"deck-{manifest['purpose']}-{manifest['revision_id'][:8]}.zip"
    expected = {v["path"]: {"sha256": v["sha256"], "size": v["size"]} for v in manifest["files"]}
    if (
        len(expected) != len(manifest["files"])
        or result.get("archive") != archive
        or set(result.get("files", {})) != set(expected) | {"manifest.json", archive}
    ):
        raise ExportError("export_file_changed", "export whitelist differs from its manifest", exit_code=4)
    for name, record in expected.items():
        if result["files"][name] != record:
            raise ExportError("export_file_changed", "export hash differs from manifest", exit_code=4)
    for name in ("manifest.json", archive):
        record = result["files"][name]
        if (
            set(record) != {"sha256", "size"}
            or not re.fullmatch("[a-f0-9]{64}", str(record["sha256"]))
            or type(record["size"]) is not int
            or record["size"] < 0
        ):
            raise ExportError("export_file_changed", "invalid export file identity", exit_code=4)
    raw = safe_path(store.project_root, ".deckmaster", "workbench", "exports", export_id, "manifest.json").read_bytes()
    if raw != canonical_json_bytes(manifest) or sha256_bytes(raw) != result["files"]["manifest.json"]["sha256"]:
        raise ExportError("export_file_changed", "frozen manifest changed", exit_code=4)
    return result


@operations.public
def show(project, *, export_id):
    store, _, identity = _context(project, None)
    return _record(store, identity, export_id)


@operations.public
def download(project, *, export_id, filename):
    store, _, identity = _context(project, None)
    record = _record(store, identity, export_id)
    return _download_file(store, record, filename)


def _download_file(store, record, filename):
    if not isinstance(filename, str) or filename not in record["files"]:
        raise ExportError("export_file_not_found", "file is not on the export whitelist", exit_code=2, http_status=404)
    path = safe_path(store.project_root, ".deckmaster", "workbench", "exports", record['export_id'], *filename.split("/"))
    data = path.read_bytes()
    expected = record["files"][filename]
    if len(data) != expected["size"] or sha256_bytes(data) != expected["sha256"]:
        raise ExportError("export_file_changed", "frozen export file failed its manifest hash", exit_code=4, http_status=409)
    return data, Path(filename).name
