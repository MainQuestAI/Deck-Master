"""Read-only, report-bound repair context. No authorization or review execution."""
from __future__ import annotations

import copy
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import models
from .review_import import _report


def imported_review_id(report_sha256, review_id):
    return f'external-{report_sha256}-{review_id}'


def _reviews(report):
    """Validate external reference shape against the fixed manifest, not a Store."""
    raw_report = report.get('original_report')
    if raw_report is not None:
        raw = raw_report['content_utf8'].encode('utf-8')
        if len(raw) != raw_report['size'] or models.sha256_bytes(raw) != raw_report['sha256']:
            raise models.ModelError('original_report', 'original report bytes do not match their identity')
    available = {(s['source_uri'], s['sha256']) for s in report['subjects']}
    seen = set()
    reviews = report.get('reviews') or []
    for original in reviews:
        row = copy.deepcopy(original)
        if row.get('replaces') is not None:
            raise models.ModelError('reviews/replaces', 'initial external report must retain original owners; recheck through existing bound replacements')
        rid = row.get('review_id')
        if rid in seen:
            raise models.ModelError('reviews', 'duplicate review_id in one report')
        seen.add(rid)
        ids = [f.get('finding_id') for f in row.get('findings') or []]
        if len(ids) != len(set(ids)):
            raise models.ModelError('reviews/findings', 'duplicate finding_id within one review')
        def ref(value):
            if set(value) != {'source_uri', 'sha256'} or (value['source_uri'], value['sha256']) not in available:
                raise models.ModelError('reviews/evidence', 'reference must name an exact reviewed source subject')
            sha = value['sha256']
            return {'path': f'.deckmaster/objects/{sha[:2]}/{sha}.json', 'sha256': sha}
        row['subjects'] = [ref(s) for s in row.get('subjects') or []]
        if not row['subjects']:
            raise models.ModelError('reviews/subjects', 'reviewed subjects are required')
        for finding in row.get('findings') or []:
            finding['evidence'] = [ref(s) for s in finding.get('evidence') or []]
        # Synthetic references above only validate shape. No object, receipt,
        # identity assurance, observation or authorization is manufactured.
        models.validate_review_semantics(row)
    if 'engineering_packet_sha256' in report:
        expected = {(r['review_id'], f['finding_id']) for r in reviews for f in r['findings']}
        contexts = set()
        for row in report.get('finding_context') or []:
            key = (row.get('review_id'), row.get('finding_id'))
            if key not in expected or key in contexts:
                raise models.ModelError('finding_context', 'each context must name a unique original review/finding')
            if row.get('severity') not in ('F0', 'F1', 'F2', 'F3') or any(
                    not isinstance(row.get(k), str) or not row[k].strip()
                    for k in ('use_impact', 'repair_layer', 'acceptance')):
                raise models.ModelError('finding_context', 'severity, use impact, repair layer and observable acceptance are required')
            contexts.add(key)
        if contexts != expected:
            raise models.ModelError('finding_context', 'retain the complete original finding set')
    return reviews


def record_reviews(*, external_report, reviews, finding_context, report_output=None, original_report_path=None):
    """Package actual Host judgments, never execute them or import into a project.

    Callers supply standard review.v2 judgments with source_uri/sha256 subjects
    and evidence. Context keeps F-level, responsibility, use impact and observable
    acceptance without changing the existing project Review schema.
    """
    from .external_review import _output, _publish
    report = copy.deepcopy(_report(external_report))
    if not isinstance(reviews, list) or not reviews:
        raise models.ModelError('reviews', 'actual review judgments are required')
    if report.get('reviews'):
        raise models.ModelError('reviews', 'preserve the original report; record against an engineering packet')
    report['reviews'] = copy.deepcopy(reviews)
    _reviews(report)
    if original_report_path is not None:
        from .external_review import _path, _read
        original_path = _path(original_report_path, 'original_report_path')
        raw, signature = _read(original_path)
        if signature[0] == 'source_changed_during_read':
            raise models.ModelError('original_report_path', 'original report changed during read')
        report['original_report'] = {'source_uri': original_path.as_uri(),
                                     'sha256': models.sha256_bytes(raw), 'size': len(raw),
                                     'content_utf8': raw.decode('utf-8')}
    report['finding_context'] = copy.deepcopy(finding_context)
    report['engineering_packet_sha256'] = external_report['report_sha256']
    _reviews(report)
    # Engineering provenance stays engineering. Caller judgments retain their
    # own reviewer identity; JSON cannot upgrade it to authenticated execution.
    result = {'report': report, 'report_sha256': models.sha256_bytes(models.canonical_json_bytes(report))}
    if report_output is not None:
        roots = [Path(unquote(urlparse(s['source_uri']).path)).parent
                 for s in report['source_manifest']['files']]
        if original_report_path is not None:
            roots.append(original_path.parent)
        target = _output(report_output, roots)
        _publish(target, result)
    return {'external_report': result, 'handoff': repair_handoff(external_report=result),
            'report_output': str(report_output) if report_output is not None else None,
            'execution': 'caller_supplied_judgments', 'project_written': False}


def repair_handoff(*, external_report, project=None):
    """Derive a complete repair list even when the original files are unavailable.

    A canonical report SHA identifies JSON content, not the bytes of a saved
    report file. Unbound findings remain unverified; generic pass is irrelevant.
    """
    report = _report(external_report, verify_sources=False)
    reviews = _reviews(report)
    digest = external_report['report_sha256']
    contexts = {(r['review_id'], r['finding_id']): r for r in report.get('finding_context') or []}
    records, artifacts = [], {}
    binding_status = 'not_requested'
    if project is not None:
        from .store import Store, StoreError
        from .editing import _current_artifact_digests
        store = Store(project)
        try:
            document = store.load_document()
        except (OSError, ValueError, StoreError):
            document = None
        if document is None:
            result = repair_handoff(external_report=external_report)
            result['project_binding'] = 'unavailable'
            return result
        binding_status = 'read_current_project'
        records = [{**store.read_object_json(ref), 'ref': ref} for ref in document.get('reviews') or []]
        artifacts = _current_artifact_digests(store, document)
    from .review import finding_closed
    rows = []
    for original in reviews:
        owners = [r for r in records if r['review_id'] == imported_review_id(digest, original['review_id'])]
        # Only the original import has no replacement. Later reviews remain
        # endpoints of its existing replaces chain, never a new finding owner.
        owners = list({r['ref']['sha256']: r for r in owners if not r.get('replaces')}.values())
        owner = owners[0] if len(owners) == 1 else None
        for finding in original['findings']:
            fid = finding['finding_id']
            bound = next((f for f in (owner or {}).get('findings', []) if f['finding_id'] == fid), None)
            if bound and any(bound.get(k) != finding.get(k) for k in finding if k != 'evidence'):
                bound = None
            closed = bool(bound and finding_closed(records, owner, bound, artifacts))
            rows.append({'identity': {'report_sha256': digest, 'review_id': original['review_id'], 'finding_id': fid},
                         'review_kind': original['kind'], 'review_stage': original.get('review_stage', 'final'),
                         'scope': copy.deepcopy(report['scope']), 'original_subjects': copy.deepcopy(original['subjects']),
                         'reviewer': copy.deepcopy(original['reviewer']), 'finding': copy.deepcopy(finding),
                         'context': copy.deepcopy(contexts.get((original['review_id'], fid))),
                         'owner_ref': owner['ref'] if owner else None,
                         'closed': closed, 'verification': 'current_replacement_review' if closed else 'not_verified',
                         'next_action': 'none' if closed else 'recheck_original_finding' if owner else 'bind_under_existing_authorization_or_keep_external'})
    return {'report_sha256': digest, 'hash_kind': 'canonical_json',
            'project_binding': binding_status, 'source_verification': 'fixed_manifest_not_re_read',
            'source_manifest': copy.deepcopy(report['source_manifest']),
            'original_report': copy.deepcopy(report.get('original_report')), 'scope': copy.deepcopy(report['scope']),
            'findings': rows, 'all_findings_closed': bool(rows) and all(r['closed'] for r in rows),
            'limitations': copy.deepcopy(report.get('limitations') or []), 'project_written': False,
            'evidence_boundary': 'Engineering, host_self, independent, rendering and desktop observations are distinct; no model was called.'}


def project_findings(store, document, page_ids=None):
    """Read original reports referenced by imported reviews; never discover new files."""
    reports = {}
    for ref in document.get('reviews') or []:
        row = store.read_object_json(ref)
        parts = row.get('review_id', '').split('-', 2)
        if len(parts) != 3 or parts[0] != 'external' or len(parts[1]) != 64:
            continue
        digest = parts[1]
        if any(c not in '0123456789abcdef' for c in digest) or digest in reports:
            continue
        report_ref = {'path': f'.deckmaster/objects/{digest[:2]}/{digest}.json', 'sha256': digest}
        try:
            report = store.read_object_json(report_ref)
        except (ValueError, OSError):
            continue
        if report.get('schema_version') == 'external_review_report.v1':
            reports[digest] = repair_handoff(external_report={'report': report, 'report_sha256': digest})
    # This is context, not a new gate or a claim that any finding was rechecked.
    return [row for report in reports.values() for row in report['findings']
            if page_ids is None or row['finding'].get('page_id') is None or row['finding']['page_id'] in page_ids]
