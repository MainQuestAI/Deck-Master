"""Unified professional-delivery evidence predicate (content collaboration
v1.2, CONTRACTS §8). One interpretation consumed by exports, handoff-check and
final-readiness: engineering pass never implies professional sign-off, and no
non-fail status, reviewer name, ``professional_use`` kind from a non-human
reviewer, or empty dependency array can satisfy the human professional policy.

Human identity is only verifiable through a registered trusted adapter receipt
(review.v1 ``reviewer.identity_receipt``). This module ships the protocol and
the registry; it registers no production adapter. Until a real channel adapter
lands (T07), a strict human policy honestly stays blocked with a concrete gap.
"""
from __future__ import annotations

from collections import OrderedDict
import stat
import threading

_projection_cache = OrderedDict()
_projection_lock = threading.Lock()

# Gap reasons in report order. Each failing review contributes its specific
# reasons; a delivery refusal lists the distinct set.
_REASON_ORDER = (
    'reviewer_not_human',
    'status_not_pass',
    'human_identity_evidence_missing',
    'human_identity_evidence_malformed',
    'identity_adapter_unavailable',
    'human_identity_rejected',
    'identity_adapter_error',
    'subject_not_current_pptx',
    'required_dependencies_incomplete',
    'stale_review_dependency',
    'unresolvable_review_dependency',
    'no_substantive_observations',
    'open_must_fix_findings',
    'not_final_stage',
    'superseded',
    'professional_review_failed',
    'no_professional_review',
)

_HUMAN_TYPES = ('human_internal', 'human_external')

# adapter_id -> verify(receipt, review, context) -> (ok, reason|None).
# context carries {'project_id': ...}. A real adapter must verify issuer and
# trusted transport, project/actor binding, subject binding, validity time and
# event_id anti-replay before returning ok. Registry keys and stubs used by
# unit fixtures must be clearly labeled synthetic (CONTRACTS §12.1).
_IDENTITY_ADAPTERS: dict[str, object] = {}


def register_identity_adapter(adapter_id: str, verify) -> None:
    _IDENTITY_ADAPTERS[adapter_id] = verify


def unregister_identity_adapter(adapter_id: str) -> None:
    _IDENTITY_ADAPTERS.pop(adapter_id, None)


def human_evidence_status(review: dict, *, project_id: str | None = None) -> dict:
    """Verify the human identity evidence on one review record.

    reviewer.id strings, execution_ref strings or a claimed human type never
    verify on their own; only a receipt issued by a registered adapter does.
    """
    reviewer = review.get('reviewer') or {}
    if reviewer.get('type') not in _HUMAN_TYPES:
        return {'verified': False, 'reason': 'reviewer_not_human'}
    receipt = reviewer.get('identity_receipt')
    if not receipt:
        return {'verified': False, 'reason': 'human_identity_evidence_missing'}
    if not isinstance(receipt, dict):
        return {'verified': False, 'reason': 'human_identity_evidence_malformed'}
    adapter = _IDENTITY_ADAPTERS.get(receipt.get('adapter_id'))
    if adapter is None:
        return {'verified': False, 'reason': 'identity_adapter_unavailable'}
    try:
        ok, reason = adapter(receipt, review, {'project_id': project_id})
    except Exception:  # noqa: BLE001 - a broken adapter is a gap, never a pass
        return {'verified': False, 'reason': 'identity_adapter_error'}
    if ok:
        return {'verified': True, 'reason': None}
    return {'verified': False, 'reason': reason or 'human_identity_rejected'}


def required_professional_dependencies(store, doc, *, selected_output=None) -> dict[str, str]:
    """Runtime-computed minimum dependency set for a final professional review:
    the current PPTX artifact plus every current page's content digest. A
    reviewer-supplied empty array therefore never counts as complete."""
    required: dict[str, str] = {}
    pptx_ref = (doc.get('outputs') or {}).get('pptx')
    if pptx_ref:
        try:
            required['artifact:pptx'] = store.read_object_json(pptx_ref)['file']['sha256']
        except Exception:  # noqa: BLE001 - unreadable output stays a gap
            pass
    for entry in doc.get('pages') or []:
        if entry.get('page'):
            required[f"content:page:{entry['page_id']}"] = entry['page']['sha256']
    if selected_output and selected_output.get("file_sha256"):
        required["artifact:pptx"] = selected_output["file_sha256"]
    return required


def _dependency_key(dep: dict) -> str:
    from .review import _dependency_key as key_of
    return key_of(dep)


def _declared_dependency_problems(review, artifacts):
    from .review import dependency_problems
    return dependency_problems(review, artifacts or {})


def _ref_pair(ref) -> tuple | None:
    if isinstance(ref, dict) and ref.get('path') and ref.get('sha256'):
        return (ref['path'], ref['sha256'])
    return None


def professional_policy(store, doc, *, selected_output=None, read_context=None) -> dict:
    """The single professional-evidence interpretation for delivery.

    Returns required/satisfied/human_signoff plus per-review diagnosis. When
    the policy switch is false, satisfied is trivially true and human_signoff
    false: delivery is not blocked, and no human endorsement is claimed.
    """
    if read_context is not None:
        read_context.require(store, doc)
    policy = doc.get('policy') or {}
    required = bool(policy.get('professional_review_required_for_delivery'))
    result = {
        'required': required,
        'satisfied': not required,
        'human_signoff': False,
        'evidence': {'professional_use': 'not_evaluated', 'desktop_editing': 'not_evaluated'},
        'reviews_considered': 0,
        'gap_reasons': [],
        'reviews': [],
    }

    current_ref = (selected_output or {}).get("subject_ref") or (doc.get('outputs') or {}).get('pptx')
    pptx_pair = _ref_pair(current_ref)
    reviews = []
    for ref in doc.get('reviews') or []:
        try:
            reviews.append((ref, store.read_object_json(ref)))
        except Exception:  # noqa: BLE001 - unreadable review records stay unread
            continue
    # One pass records the verbatim per-kind evidence for every review kind;
    # professional_use records additionally get the full delivery diagnosis.
    for _, review in reviews:
        kind = review.get('kind')
        if kind in result['evidence'] and current_ref and current_ref in (review.get('subjects') or []):
            result['evidence'][kind] = review.get('status') or 'not_evaluated'
    if not required:
        return result

    required_deps = required_professional_dependencies(store, doc, selected_output=selected_output)
    # The same artifact map the shared check summary uses: declared review
    # dependencies are validated against one currentness rule, never two.
    from .editing import _current_artifact_digests
    artifacts = dict(read_context.artifacts) if read_context is not None else _current_artifact_digests(store, doc)
    if selected_output and selected_output.get("file_sha256"):
        artifacts["artifact:pptx"] = selected_output["file_sha256"]
    # Replacement effectiveness (F02, PR107 round 2): recording a replacement
    # is not the same as resolving what it replaces. A record is only retired
    # by a replacement that is itself an effective re-judgment — same logical
    # review (kind + review_id, mirroring the formal adoption rule) and every
    # pass condition satisfied (identity, subject, dependencies, observations,
    # no open must-fix). A host_self / not_evaluated / unverified device, or a
    # replacement still carrying open must-fix findings, stays as history and
    # retires nothing — an earlier pass must not silently revive because a new
    # record merely exists. Explicit withdrawal or arbitration is a trusted
    # action (T02/T07), not re-interpreted here. The provisional judgment
    # excludes supersession itself, so replacement chains cannot cycle.
    provisional = {}
    for ref, review in reviews:
        if review.get('kind') != 'professional_use':
            continue
        provisional[_ref_pair(ref)] = _diagnose(review, ref, doc, pptx_pair, required_deps,
                                                set(), artifacts, project_id=doc.get('project_id'))
    review_ids_by_ref = {_ref_pair(ref): review.get('review_id') for ref, review in reviews}
    replaced = set()
    for ref, review in reviews:
        pair = _ref_pair(review.get('replaces'))
        if not pair or review.get('kind') != 'professional_use':
            continue
        if review_ids_by_ref.get(pair) != review.get('review_id'):
            continue
        if provisional.get(_ref_pair(ref), {}).get('satisfies'):
            replaced.add(pair)

    for ref, review in reviews:
        if review.get('kind') != 'professional_use':
            continue
        result['reviews_considered'] += 1
        entry = _diagnose(review, ref, doc, pptx_pair, required_deps, replaced, artifacts,
                          project_id=doc.get('project_id'))
        result['reviews'].append(entry)

    # A current, non-superseded fail on the selected deck blocks delivery even
    # when another review passes: an earlier pass never masks a newer fail.
    blocking = any(entry['blocking_fail'] for entry in result['reviews'])
    satisfying = [entry for entry in result['reviews'] if entry['satisfies']]
    if satisfying and not blocking:
        result['satisfied'] = True
        result['human_signoff'] = True
    else:
        reasons = []
        for entry in result['reviews']:
            for reason in entry['reasons']:
                if reason not in reasons:
                    reasons.append(reason)
        if blocking:
            reasons.append('professional_review_failed')
        result['gap_reasons'] = _sort_reasons(reasons or ['no_professional_review'])
    return result


def _diagnose(review, ref, doc, pptx_pair, required_deps, replaced, artifacts, *, project_id) -> dict:
    reviewer = review.get('reviewer') or {}
    reasons: list[str] = []
    status = review.get('status')
    if status != 'pass':
        reasons.append('status_not_pass')
    evidence = human_evidence_status(review, project_id=project_id)
    if not evidence['verified']:
        reasons.append(evidence['reason'])
    subjects = {_ref_pair(s) for s in review.get('subjects') or []} - {None}
    subject_current = bool(pptx_pair) and pptx_pair in subjects
    if not subject_current:
        reasons.append('subject_not_current_pptx')
    provided = {}
    for dep in review.get('dependencies') or []:
        try:
            provided[_dependency_key(dep)] = dep.get('sha256')
        except Exception:  # noqa: BLE001
            continue
    missing = sorted(key for key, sha in required_deps.items() if provided.get(key) != sha)
    if missing:
        reasons.append('required_dependencies_incomplete')
    # Every declared dependency must resolve against the current artifact map
    # and match it — the same single rule the shared check summary uses
    # (review.dependency_problems). Required keys are owned by the named
    # required_dependencies_incomplete reason above and are not double-counted.
    declared_problems = [
        problem for problem in _declared_dependency_problems(review, artifacts)
        if problem['key'] not in required_deps
    ]
    if any(p['kind'] == 'sha_mismatch' for p in declared_problems):
        reasons.append('stale_review_dependency')
    if any(p['kind'] != 'sha_mismatch' for p in declared_problems):
        reasons.append('unresolvable_review_dependency')
    observations = [o for o in review.get('observations') or []
                    if isinstance(o, str) and o.strip()]
    if not observations:
        reasons.append('no_substantive_observations')
    if any(f.get('impact') == 'must_fix' and f.get('resolution') == 'open'
           for f in review.get('findings') or []):
        reasons.append('open_must_fix_findings')
    if review.get('review_stage', 'final') != 'final':
        reasons.append('not_final_stage')
    ref_pair = _ref_pair(ref)
    superseded = bool(ref_pair) and ref_pair in replaced
    if superseded:
        reasons.append('superseded')
    # Unlike a pass, a fail needs only its subject to be current to stay
    # effective: incomplete or stale dependencies never soften a fail into
    # invisibility (an earlier pass must never mask a newer fail).
    blocking_fail = (status == 'fail' and not superseded and subject_current)
    return {
        'review_id': review.get('review_id'),
        'reviewer_type': reviewer.get('type'),
        'status': status,
        'subject_current': subject_current,
        'missing_dependencies': missing,
        'declared_dependency_problems': declared_problems,
        'superseded': superseded,
        'satisfies': not reasons,
        'reasons': _sort_reasons(reasons),
        'blocking_fail': blocking_fail,
    }


def _sort_reasons(reasons):
    rank = {name: i for i, name in enumerate(_REASON_ORDER)}
    return sorted(reasons, key=lambda r: (rank.get(r, len(rank)), r))


def selected_output(store, artifact, *, notes_policy=None, file_path=None):
    """Pure exact bytes of the proposed public projection (never a stored approval)."""
    from .exports import resolve_notes_policy, _pptx_projection_notes
    from .export_sanitize import pptx
    from .models import canonical_json_bytes, sha256_bytes, validate_ref
    policy = resolve_notes_policy(store, artifact, notes_policy)
    ref = artifact.get("outputs", {}).get("pptx")
    result = {"artifact_ref": ref, "subject_ref": None, "file_sha256": None,
              "original_file_sha256": None, "notes_policy": policy, "projection": "sanitized_public"}
    if not ref:
        return result
    obj = store.read_object_json(ref)
    source = obj['file']
    validate_ref(source, where='output/file')
    def signature():
        info = (store.ctx.object_stat(source) if hasattr(store, 'ctx') else
                store._resolve_object_path(source['path']).stat())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('output is not a regular file')
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    source_signature = signature()
    notes = _pptx_projection_notes(store, artifact, policy)
    key = (str(store.project_root.resolve()), source['path'], source['sha256'], source_signature,
           canonical_json_bytes([notes, policy]), pptx)
    with _projection_lock:
        metadata = _projection_cache.get(key)
        if metadata is not None:
            _projection_cache.move_to_end(key)
    if metadata is None:
        raw = store.read_object_bytes(source)
        projected = pptx(raw, 'deck.pptx', notes=notes, include_notes=policy['pptx_notes'])
        metadata = (sha256_bytes(projected), len(raw), len(projected))
        if signature() == source_signature:
            with _projection_lock:
                _projection_cache[key] = metadata
                _projection_cache.move_to_end(key)
                while len(_projection_cache) > 8:
                    _projection_cache.popitem(last=False)
    digest, original_size, projected_size = metadata
    result.update(file_sha256=digest, original_file_sha256=obj["file"]["sha256"],
        subject_ref={"path": f".deckmaster/objects/{digest[:2]}/{digest}.pptx", "sha256": digest})
    if file_path is not None:
        from .selected_file import read_selected_file
        _, actual = read_selected_file(file_path, sizes={original_size, projected_size})
        if actual == digest:
            pass
        elif actual == obj["file"]["sha256"]:
            result.update(file_sha256=actual, subject_ref=ref, projection="original_internal")
        else:
            from .store import ConflictError
            raise ConflictError("file_path", "candidate_not_selected_output: file differs from both exact output projections")
    return result


def describe(project, *, revision=None, file_path=None, notes_policy=None):
    """Read-only shared final judgement: selected actual file plus current control."""
    from .store import Store
    from .snapshots import load_snapshot
    store = Store(project)
    control = store.load_document()
    artifact = load_snapshot(store, revision) if revision else control
    return describe_snapshots(store, artifact, control, file_path=file_path, notes_policy=notes_policy)


def describe_snapshots(store, artifact, control, *, file_path=None, notes_policy=None, read_context=None):
    """The same delivery judgement over snapshots already pinned by a reader."""
    from . import eligibility
    from .exports import _facts, _engineering_ready
    selected = selected_output(store, artifact, notes_policy=notes_policy, file_path=file_path)
    facts = _facts(store, artifact, selected_output=selected, control=control, read_context=read_context)
    summary = facts['check_summary']
    professional = facts['professional']
    decision = eligibility.evaluate(store, artifact, control, "export.delivery",
        {"selected_output": selected, "review_read_context": read_context})
    engineering = bool(selected["file_sha256"] and _engineering_ready(artifact, facts))
    codes = list(decision["reason_codes"])
    if not engineering:
        codes.append("engineering_checks_required")
    allowed = engineering and decision["allowed"] and professional["satisfied"]
    return {"status": "ready" if allowed else "blocked", "project_id": control["project_id"],
        "artifact_revision_id": artifact["revision_id"], "control_revision_id": control["revision_id"],
        "revision_id": artifact["revision_id"], "selected_output": selected,
        "engineering_ready": engineering, "engineering": {"ready": engineering, "summary": summary},
        "review_status": summary["status"], "unresolved": {"missing_dimensions": sorted(summary["missing_dimensions"]),
            "failed_dimensions": [k for k,v in summary["dimensions"].items() if v.get("open_must_fix") or v["status"] == "fail"],
            "gaps": facts['gaps'] if not engineering else []},
        "professional": professional, "eligibility": decision, "collaboration": decision,
        "reason_codes": list(dict.fromkeys(codes)), "next_action": decision.get("next_action") or
            ("deliver_selected_file" if allowed else "resolve_named_delivery_gaps")}
