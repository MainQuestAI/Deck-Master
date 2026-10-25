"""Explicit source-bound external Review import under current project control."""
from __future__ import annotations

import copy
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import collaboration, eligibility, models, operations, tasks
from .snapshots import load_snapshot
from .store import ConflictError, Store


def _report(external_report, *, verify_sources=True):
    if not isinstance(external_report, dict) or set(external_report) != {"report", "report_sha256"}:
        raise models.ModelError("external_report", "provide report and its canonical report_sha256")
    report = external_report["report"]
    if not isinstance(report, dict) or report.get("schema_version") != "external_review_report.v1":
        raise models.ModelError("external_report/report", "unsupported external report")
    if models.sha256_bytes(models.canonical_json_bytes(report)) != external_report["report_sha256"]:
        raise models.ModelError("external_report/report_sha256", "report bytes do not match their declaration")
    manifest = report.get("source_manifest")
    if models.sha256_bytes(models.canonical_json_bytes(manifest)) != report.get("source_manifest_sha256"):
        raise models.ModelError("external_report/source_manifest", "source manifest hash does not match")
    if report.get("source_unchanged") is not True:
        raise ConflictError("external_report/source_unchanged", "source_changed: changed-source reports cannot be imported")
    if not isinstance(manifest, dict) or manifest.get("source_kind") not in ("file", "fileset", "project"):
        raise models.ModelError("external_report/source_manifest", "a fixed source manifest is required")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise models.ModelError("external_report/source_manifest/files", "source files are required")
    available = {(row.get("source_uri"), row.get("sha256")): row for row in rows if isinstance(row, dict)}
    if len(available) != len(rows):
        raise models.ModelError("external_report/source_manifest/files", "file identities must be unique")
    subjects = report.get("subjects")
    if not isinstance(subjects, list):
        raise models.ModelError("external_report/subjects", "subjects must be an array")
    selected = set()
    for subject in subjects:
        identity = (subject.get("source_uri"), subject.get("sha256"))
        if identity not in available or subject.get("media_type") != available[identity].get("media_type") or identity in selected:
            raise models.ModelError("external_report/subjects", "each unique subject must belong to the original source manifest")
        selected.add(identity)
    for observed in report.get("engineering_observations") or []:
        identity = (observed.get("source_uri"), observed.get("sha256"))
        if identity not in available:
            raise models.ModelError("external_report/engineering_observations", "observations must bind original manifest bytes")
        selected.add(identity)
    if manifest["source_kind"] == "project":
        # Immutable dependency closure was actually read by the evaluator. Mutable
        # current/control/cache files are inventory facts, not an adoption basis.
        selected.update(identity for identity in available if "/.deckmaster/objects/" in identity[0])
        rows = [row for identity, row in available.items() if identity in selected]
    if not verify_sources:
        rows = []
    for row in rows:
        uri = urlparse(row.get("source_uri", ""))
        if uri.scheme != "file" or uri.netloc not in ("", "localhost"):
            raise models.ModelError("external_report/source_uri", "source must be a fixed local file URI")
        path = Path(unquote(uri.path))
        if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
            raise operations.OperationError("source_not_found", "source_uri", "source is unavailable", http_status=404)
        raw = path.read_bytes()
        if len(raw) != row.get("size") or models.sha256_bytes(raw) != row.get("sha256"):
            raise ConflictError("external_report/source_uri", "source_changed: original source bytes changed")
    return report


def _context(project, report, artifact_revision):
    store = Store(project)
    control = store.load_document()
    artifact = load_snapshot(store, artifact_revision) if artifact_revision else control
    original = report["source_manifest"].get("original_project_id")
    if original not in (None, control["project_id"]):
        raise models.ModelError("source_bindings/project_id", "the report belongs to another project")
    refs = ([artifact["narrative"]] if artifact.get("narrative") else [])
    refs += ([artifact["content_plan"]] if artifact.get("content_plan") else [])
    refs += [entry[key] for entry in artifact["pages"] for key in
             ("page", "blueprint", "svg", "svg_preview", "ppt_preview") if entry.get(key)]
    refs += [ref for ref in artifact["outputs"].values() if ref]
    refs += [source[key] for source in artifact["sources"] for key in ("original", "extract")
             if isinstance(source.get(key), dict)]
    # Public export bytes are a separate review subject from their internal
    # wrapper. Admit only a verified, fixed export of this exact revision.
    from . import exports
    root = store.deck_root / "workbench" / "exports"
    if root.is_dir():
        for record_path in sorted(root.glob("*/export-record.json")):
            record = exports.show(project, export_id=record_path.parent.name)
            if record["revision_id"] != artifact["revision_id"] or "deck.pptx" not in record["files"]:
                continue
            raw, _ = exports.download(project, export_id=record["export_id"], filename="deck.pptx")
            sha = models.sha256_bytes(raw)
            ref = {"path": f".deckmaster/objects/{sha[:2]}/{sha}.pptx", "sha256": sha}
            if store.read_object_bytes(ref) != raw:
                raise ConflictError("source_bindings", "export projection differs from its immutable subject")
            refs.append(ref)
    return store, control, artifact, refs


def describe_bindings(project, *, external_report, artifact_revision=None):
    report = _report(external_report)
    store, control, artifact, refs = _context(project, report, artifact_revision)
    matches = []
    for subject in report.get("subjects", []):
        for ref in refs:
            raw = store.read_object_bytes(ref)
            file_sha = None
            try:
                obj = store.read_object_json(ref)
                file_sha = (obj.get("file") or {}).get("sha256")
            except (ValueError, TypeError, UnicodeError):
                pass
            if subject["sha256"] in (ref["sha256"], file_sha):
                matches.append({"source_uri": subject["source_uri"], "source_sha256": subject["sha256"],
                    "target_ref": ref, **({"target_file_sha256": file_sha} if file_sha and subject["sha256"] == file_sha else {})})
    return {"project_id": control["project_id"], "artifact_revision_id": artifact["revision_id"],
        "control_revision_id": control["revision_id"], "source_bindings": matches,
        "limitations": ["Bindings prove bytes, not reviewer identity or professional approval"]}


def import_report(project, *, external_report, source_bindings, evidence, base_revision,
                  operation_id, artifact_revision=None, adapter_context=None):
    report = _report(external_report, verify_sources=False)
    if 'engineering_packet_sha256' in report:
        from .review_handoff import _reviews
        _reviews(report)
    store = Store(project)
    payload = {"external_report": external_report, "source_bindings": source_bindings,
               "evidence": evidence, "artifact_revision": artifact_revision}
    digest = collaboration.payload_digest("review.import", payload)
    with store._locked():
        control = store.load_document()
        replay = collaboration.replay_or_conflict(store, control, operation_id, "review.import", digest)
        if replay:
            return replay
        _report(external_report)
        if base_revision != control["revision_id"]:
            raise ConflictError("base_revision", "review import base changed")
        _, _, artifact, refs = _context(project, report, artifact_revision)
        if not isinstance(source_bindings, list) or not source_bindings:
            raise models.ModelError("source_bindings", "explicit source bindings are required")
        admissible = {(ref["path"], ref["sha256"]) for ref in refs}
        available = {(item["source_uri"], item["source_sha256"],
            item["target_ref"]["path"], item["target_ref"]["sha256"])
            for item in describe_bindings(project, external_report=external_report,
                                          artifact_revision=artifact_revision)["source_bindings"]}
        mapping = {}
        for row in source_bindings:
            ref = row.get("target_ref") or {}
            key = (row.get("source_uri"), row.get("source_sha256"))
            if key in mapping or (ref.get("path"), ref.get("sha256")) not in admissible:
                raise models.ModelError("source_bindings", "duplicate or foreign target")
            if (*key, ref["path"], ref["sha256"]) not in available:
                raise ConflictError("source_bindings", "report subjects no longer match the selected objects")
            if row.get("target_file_sha256") not in (None, key[1]):
                raise ConflictError("source_bindings/target_file_sha256", "actual file hash differs")
            mapping[key] = ref
        subjects = {(item["source_uri"], item["sha256"]) for item in report.get("subjects", [])}
        if not subjects or not subjects <= set(mapping):
            raise models.ModelError("source_bindings", "every reviewed source subject requires a unique binding")
        page_ids = [entry["page_id"] for entry in artifact["pages"] if entry["page"] in mapping.values()]
        eligibility.guard(store, control, "review.import", context={"targets": {"page_ids": page_ids,
            "layers": ["review"]}, "subject_refs": list(mapping.values())})
        resolved = collaboration.resolve_evidence(evidence, adapter_context, store=store,
            action_binding=digest, project_id=control["project_id"],
            request_id=(control["collaboration"].get("request") or {}).get("request_id"))
        collaboration._require_stored_evidence_refs(store, resolved, "review.import/evidence")
        report_ref = store.put_blob(models.canonical_json_bytes(report), ext="json")
        reviews = []
        for original in report.get("reviews", []):
            review = copy.deepcopy(original)
            selected = review.get("subjects") or []
            if not selected:
                raise models.ModelError("external_report/reviews/subjects", "each review names its exact source subjects")
            review["subjects"] = [mapping[(item["source_uri"], item["sha256"])] for item in selected]
            if 'engineering_packet_sha256' in report:
                from .review_handoff import imported_review_id
                review['review_id'] = imported_review_id(external_report['report_sha256'], original['review_id'])
                for finding in review.get('findings') or []:
                    finding['evidence'] = [mapping[(item['source_uri'], item['sha256'])]
                                           for item in finding.get('evidence') or []]
            reviewer = review.setdefault("reviewer", {})
            from .delivery_eligibility import human_evidence_status, required_professional_dependencies
            human = reviewer.get("type") in ("human_internal", "human_external")
            verified_human = human and human_evidence_status(review, project_id=control["project_id"])["verified"]
            if (reviewer.get("assurance") == "verified_user" or reviewer.get("identity_receipt")) and not verified_human:
                raise operations.OperationError("untrusted_review_identity", "reviewer", "a registered identity adapter must verify the actual human receipt", exit_code=4, http_status=403)
            reviewer["assurance"] = "verified_user" if verified_human else ("host_attested" if reviewer.get("type") == "host_self" else "unverified")
            reviewer["evidence_ref"] = report_ref
            if reviewer.get("type") == "independent_host":
                # A report JSON does not carry a protected execution channel.
                # Opaque SDK contexts bind this exact source/report/result.
                from .review_evidence import validate_external_review_context
                proof = validate_external_review_context(adapter_context, store, control, artifact,
                    external_report, source_bindings)
                reviewer["assurance"] = "host_attested"
                reviewer["independence_confirmed"] = True
                reviewer["evidence_ref"] = proof["receipt_ref"]
            review["schema_version"] = "deck_review.v2"
            models.validate_review_semantics(review)
            from .editing import _current_artifact_digests
            from .review import dependency_problems
            digests = _current_artifact_digests(store, artifact)
            bound_pages = [entry for entry in artifact["pages"] if entry["page"] in review["subjects"]]
            required = {f"content:page:{entry['page_id']}": entry["page"]["sha256"] for entry in bound_pages}
            if review.get("review_stage") == "preproduction":
                from .content_review import _require_subject_binding, requirement_state
                try:
                    _require_subject_binding(store, artifact, review, [entry["page_id"] for entry in bound_pages])
                except models.ModelError as exc:
                    if getattr(exc, "path", "").endswith("dependencies"):
                        raise ConflictError("external_report/reviews/dependencies", "review dependencies are incomplete or stale") from exc
                    raise
                requirement = requirement_state(store, control)["effective"]
                if requirement == "independent_model_or_human" and not (verified_human or reviewer.get("type") == "independent_host"):
                    raise operations.OperationError("needs_reviewer", "reviewer", "preproduction requires a real independent execution or verified human", exit_code=3, http_status=409)
            if review.get("kind") in ("argument", "progression", "page_copy", "speech"):
                required.update({f"content:{role}": artifact[role]["sha256"] for role in ("narrative", "content_plan") if artifact.get(role)})
                required.update({f"source:{row['source_id']}": row["extract"]["sha256"] for row in artifact.get("sources", []) if row.get("extract")})
            if review.get("review_stage") == "page_visual":
                for entry in bound_pages:
                    pid = entry["page_id"]
                    for identity in (f"blueprint:{pid}", f"artifact:svg:{pid}", f"style:{pid}"):
                        if identity not in digests:
                            raise ConflictError("external_report/reviews/dependencies", "selected visual inputs are missing")
                        required[identity] = digests[identity]
            if review.get("review_stage", "final") in ("final", "use_validation"):
                if (artifact.get("outputs") or {}).get("pptx") in review["subjects"]:
                    required.update(required_professional_dependencies(store, artifact))
                raw_pptx = [ref for ref in review["subjects"] if ref["path"].endswith(".pptx")]
                if raw_pptx:
                    if len(raw_pptx) != 1:
                        raise models.ModelError("external_report/reviews/subjects", "select one actual delivery file")
                    digests["artifact:pptx"] = raw_pptx[0]["sha256"]
                    required.update(required_professional_dependencies(store, artifact,
                        selected_output={"file_sha256": raw_pptx[0]["sha256"]}))
            declared = {f"{row['kind']}:{row['identity']}": row['sha256'] for row in review.get("dependencies") or []}
            if (not required or any(declared.get(key) != sha for key, sha in required.items())
                    or dependency_problems(review, digests)):
                raise ConflictError("external_report/reviews/dependencies", "review dependencies are incomplete or stale")
            reviews.append(tasks._adopt_review(store, review))
        refs_out = [store.put_json_object(review) for review in reviews]
        updated = {**control, "reviews": [*control["reviews"], *refs_out]}
        return collaboration.commit_collaboration_change(store, control, operation_id=operation_id,
            action="review.import", digest=digest, description="Import fixed external review with original provenance",
            updated=updated, response={"review_refs": refs_out, "report_ref": report_ref,
                "assurance": "unverified", "creates_confirmation": False,
                "next_action": "inspect_recorded_review" if refs_out else "provide_reviewer"})
