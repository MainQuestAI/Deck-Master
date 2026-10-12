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


def required_professional_dependencies(store, doc) -> dict[str, str]:
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
    return required


def _dependency_key(dep: dict) -> str:
    from .review import _dependency_key as key_of
    return key_of(dep)


def _ref_pair(ref) -> tuple | None:
    if isinstance(ref, dict) and ref.get('path') and ref.get('sha256'):
        return (ref['path'], ref['sha256'])
    return None


def professional_policy(store, doc) -> dict:
    """The single professional-evidence interpretation for delivery.

    Returns required/satisfied/human_signoff plus per-review diagnosis. When
    the policy switch is false, satisfied is trivially true and human_signoff
    false: delivery is not blocked, and no human endorsement is claimed.
    """
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

    current_ref = (doc.get('outputs') or {}).get('pptx')
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

    required_deps = required_professional_dependencies(store, doc)
    # Only a same-logical-review replacement (same kind, same review_id —
    # mirroring the formal adoption path's rule) can supersede a record.
    # Defense in depth: the predicate does not trust arbitrary replaces
    # pointers from other kinds.
    review_ids_by_ref = {_ref_pair(ref): review.get('review_id') for ref, review in reviews}
    replaced = set()
    for _, review in reviews:
        pair = _ref_pair(review.get('replaces'))
        if (pair and review.get('kind') == 'professional_use'
                and review_ids_by_ref.get(pair) == review.get('review_id')):
            replaced.add(pair)

    for ref, review in reviews:
        if review.get('kind') != 'professional_use':
            continue
        result['reviews_considered'] += 1
        entry = _diagnose(review, ref, doc, pptx_pair, required_deps, replaced,
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


def _diagnose(review, ref, doc, pptx_pair, required_deps, replaced, *, project_id) -> dict:
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
        'superseded': superseded,
        'satisfies': not reasons,
        'reasons': _sort_reasons(reasons),
        'blocking_fail': blocking_fail,
    }


def _sort_reasons(reasons):
    rank = {name: i for i, name in enumerate(_REASON_ORDER)}
    return sorted(reasons, key=lambda r: (rank.get(r, len(rank)), r))
