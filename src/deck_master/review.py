"""Unified review interpretation (spec 07.2): one pure explanation shared by
review acceptance, load, continue, UI and export.

No storage access here: callers resolve object refs and pass the current
document, the review records (each carrying its own immutable ``ref`` under
the ``ref`` key) and the current dependency digests. Status semantics
(07.2): any open must_fix -> fail; a required dimension without an execution
record -> not_evaluated; executed dimensions with unhandled needs_judgment ->
needs_review; only fully executed, resolved dimensions pass.
"""
from __future__ import annotations

import io
import re
from typing import Any

REQUIRED_KINDS = ('content', 'blueprint_content', 'blueprint_fidelity',
                  'conversion', 'readability', 'privacy')
OPEN_TASK_STATUSES = ('awaiting_host', 'running')

# 07.8: real leak markers only — never an open-ended banned-word list.
SENSITIVE_PATTERNS = ('内部资料', '内部使用', '机密', 'confidential', 'internal only', '[internal]')
# Business words that are never leaks by themselves.
FALSE_FRIENDS = ('缩略图', '左屏', '右屏', '页角色', 'thumbnail', 'speaker')
TEACHING_MARKERS = ('教学', '教程', '培训', 'how-to', 'how to', '制作ppt', '制作幻灯片')


def _ref_key(ref: dict) -> tuple:
    return (ref.get('path'), ref.get('sha256'))


def validate_independence(reviewer: dict) -> bool:
    """Effective independence (AC-R05, spec 07.5).

    host_self/tool can never certify independence, whatever id strings are
    claimed; independent_host needs a real execution_ref; human types need an
    evidence ref too — the model must never fill these in.
    """
    if not reviewer.get('independence_confirmed'):
        return False
    kind = reviewer.get('type')
    if kind in ('tool', 'host_self'):
        return False
    if kind in ('independent_host', 'human_internal', 'human_external'):
        return bool(reviewer.get('execution_ref'))
    return False


def _dependency_key(dep: dict) -> str:
    return f"{dep.get('kind')}:{dep.get('identity')}"


def closing_review(reviews: list[dict], review: dict, artifacts: dict) -> dict | None:
    """Return the R1 record that validly closes an open must_fix of ``review``.

    A close is valid only when a new review R1 exists with: replaces pointing
    at this exact R0 ref; the same finding_id with resolution fixed; at least
    one subject that is a NEW product (not an R0 subject) and is current per
    ``artifacts``; and real recheck records (non-empty observations and
    finding evidence). Old R0 records are never modified.
    """
    current_shas = set(artifacts.values())
    review_ref = review.get('ref')
    if not review_ref:
        return None
    for candidate in reviews:
        if candidate is review:
            continue
        replaced = candidate.get('replaces')
        if not replaced or _ref_key(replaced) != _ref_key(review_ref):
            continue
        old_subjects = {_ref_key(s) for s in review.get('subjects') or []}
        added = {_ref_key(s) for s in candidate.get('subjects') or []} - old_subjects
        if not added or not any(sha in current_shas for _, sha in added):
            continue
        if not candidate.get('observations'):
            continue
        followups = {f.get('finding_id'): f for f in candidate.get('findings') or []}
        for finding in review.get('findings') or []:
            followup = followups.get(finding.get('finding_id'))
            if followup and followup.get('resolution') == 'fixed' and followup.get('evidence'):
                return candidate
    return None


def open_findings(review: dict) -> list[dict]:
    return [f for f in review.get('findings') or []
            if f.get('impact') == 'must_fix' and f.get('resolution') == 'open']


def pending_judgments(review: dict) -> list[dict]:
    return [f for f in review.get('findings') or []
            if f.get('impact') == 'needs_judgment' and f.get('resolution') == 'open']


def evaluate_current(document: dict, reviews: list[dict], artifacts: dict) -> dict:
    """The one interpretation of the current check state (AC-R01/R02/R03/R10)."""
    pages = document.get('pages') or []
    current = (document.get('outputs') or {}).get('pptx')
    if not current:
        return {'status': 'not_evaluated', 'current_outputs': None, 'dimensions': {}, 'stale': [],
                'missing_dimensions': [f'{k}:{e["page_id"]}' for k in REQUIRED_KINDS for e in pages],
                'reason': 'no current pptx output'}
    tasks = document.get('tasks') or []
    if any(isinstance(t, dict) and t.get('status') in OPEN_TASK_STATUSES for t in tasks):
        return {'status': 'not_evaluated', 'current_outputs': current, 'dimensions': {}, 'stale': [],
                'missing_dimensions': [], 'reason': 'host tasks still open'}

    dimensions: dict[str, dict] = {}
    stale: list[dict] = []
    latest: dict[tuple, dict] = {}
    for review in reviews:
        subjects = {_ref_key(s) for s in review.get('subjects') or []}
        matched = [e for e in pages if _ref_key(e.get('page') or {}) in subjects]
        if not matched:
            continue
        deps_current = all(artifacts.get(_dependency_key(d)) in (None, d.get('sha256'))
                           for d in review.get('dependencies') or [])
        for entry in matched:
            key = (review.get('kind'), entry['page_id'])
            if _ref_key(current) not in subjects or not deps_current:
                stale.append({'kind': review.get('kind'), 'page_id': entry['page_id'],
                              'review_id': review.get('review_id'),
                              'reason': 'subjects or dependencies do not match the current outputs'})
                continue
            latest[key] = review  # same kind+page: the most recently adopted current review wins
    for (kind, page_id), review in latest.items():
        open_must = open_findings(review)
        remaining = [f['finding_id'] for f in open_must if not closing_review(reviews, review, artifacts)]
        closed = [f['finding_id'] for f in open_must if f['finding_id'] not in remaining]
        judgments = [f['finding_id'] for f in pending_judgments(review)]
        if remaining:
            effective = 'fail'
        elif judgments:
            effective = 'needs_review'
        elif closed or review.get('status') == 'pass':
            effective = 'pass'
        else:
            effective = review.get('status') or 'not_evaluated'
        dimensions[f'{kind}:{page_id}'] = {
            'review_id': review.get('review_id'),
            'status': effective,
            'reported_status': review.get('status'),
            'stale': False,
            'open_must_fix': remaining,
            'closed_findings': closed,
            'pending_judgments': judgments,
        }
    missing = [f'{kind}:{entry["page_id"]}' for kind in REQUIRED_KINDS for entry in pages
               if f'{kind}:{entry["page_id"]}' not in dimensions]
    if any(d['status'] == 'fail' or d['open_must_fix'] for d in dimensions.values()):
        status = 'fail'
    elif missing:
        status = 'not_evaluated'
    elif any(d['pending_judgments'] for d in dimensions.values()):
        status = 'needs_review'
    elif dimensions and all(d['status'] == 'pass' for d in dimensions.values()):
        status = 'pass'
    else:
        status = 'not_evaluated'
    return {'status': status, 'current_outputs': current, 'dimensions': dimensions,
            'stale': stale, 'missing_dimensions': missing}


# ---------------------------------------------------------------------------
# Pixel-difference triage (AC-R04, spec 07.4). Deterministic ordered rules —
# never a vote of correlated metrics.


def _load_raster(source) -> Any:
    from PIL import Image
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(bytes(source))).convert('RGB')
    return Image.open(source).convert('RGB')


def _ink_ratio(crop) -> float:
    data = crop.convert('L').tobytes()
    dark = sum(1 for v in data if v < 128)
    return dark / max(1, len(data))


def triage_render_difference(expected, actual, regions: list[dict] | None = None) -> list[dict]:
    """Classify one expected/actual image pair into located findings.

    Rules, in order, per region: large ink-coverage loss -> must_fix
    (deleted element); strong ink-profile change -> must_fix (e.g. rounding
    lost); tiny low-amplitude diff -> accepted_variance candidate; anything
    else -> needs_judgment located at the region (measurement cannot decide
    alone).
    """
    exp = _load_raster(expected)
    act = _load_raster(actual)
    if exp.size != act.size:
        return [{'kind': 'render_difference', 'impact': 'needs_judgment',
                 'location': 'canvas', 'detail': f'size mismatch {exp.size} vs {act.size}'}]
    width, height = exp.size
    if regions is None:
        regions = [{'region_id': 'canvas', 'bbox': (0, 0, width, height)}]
    findings = []
    for region in regions:
        x0, y0, x1, y1 = region['bbox']
        exp_crop = exp.crop((x0, y0, x1, y1))
        act_crop = act.crop((x0, y0, x1, y1))
        exp_ink = _ink_ratio(exp_crop)
        act_ink = _ink_ratio(act_crop)
        if exp_ink >= 0.02 and act_ink <= exp_ink * 0.4:
            findings.append({'kind': 'render_difference', 'impact': 'must_fix',
                             'location': region['region_id'],
                             'detail': f'ink coverage collapsed from {exp_ink:.3f} to {act_ink:.3f}'})
            continue
        if abs(exp_ink - act_ink) > 0.15:
            findings.append({'kind': 'render_difference', 'impact': 'must_fix',
                             'location': region['region_id'],
                             'detail': f'ink profile changed from {exp_ink:.3f} to {act_ink:.3f}'})
            continue
        diff_pixels = 0
        max_delta = 0
        exp_px = exp_crop.load()
        act_px = act_crop.load()
        for y in range(exp_crop.size[1]):
            for x in range(exp_crop.size[0]):
                delta = max(abs(a - b) for a, b in zip(exp_px[x, y], act_px[x, y]))
                max_delta = max(max_delta, delta)
                if delta > 32:
                    diff_pixels += 1
        ratio = diff_pixels / max(1, exp_crop.size[0] * exp_crop.size[1])
        if ratio < 0.005 and max_delta <= 64:
            findings.append({'kind': 'render_difference', 'impact': 'accepted_variance',
                             'location': region['region_id'],
                             'detail': f'anti-alias scale {ratio:.5f} max delta {max_delta}'})
        else:
            findings.append({'kind': 'render_difference', 'impact': 'needs_judgment',
                             'location': region['region_id'],
                             'detail': f'unresolved diff ratio {ratio:.5f} max delta {max_delta}'})
    return findings


# ---------------------------------------------------------------------------
# Privacy / internal-language scan (AC-R07, spec 07.8).


def privacy_findings(page: dict, *, intent: str = '') -> list[dict]:
    """Locate real internal/sensitive material without banning business words.

    Structural fields (internal_only, speaker-note markers, sensitive markers)
    are must_fix; a short explicit sensitive-pattern list covers prose leaks;
    false friends and teaching-task phrasing are never reported.
    """
    findings = []
    lowered_intent = intent.lower()

    def scan(value, pointer):
        if isinstance(value, dict):
            if value.get('sensitive') is True or value.get('internal_only') is True:
                findings.append({'kind': 'privacy', 'impact': 'must_fix', 'location': pointer,
                                 'detail': 'explicit sensitive/internal_only marker'})
            for key, item in value.items():
                if key in ('internal_only', 'speaker_notes', 'speakerNote'):
                    findings.append({'kind': 'privacy', 'impact': 'must_fix',
                                     'location': pointer + '/' + key,
                                     'detail': f'internal field {key!r} present in visible payload'})
                scan(item, pointer + '/' + str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                scan(item, f'{pointer}/{index}')
        elif isinstance(value, str):
            text = value.lower()
            if any(word in text for word in FALSE_FRIENDS):
                return
            for marker in SENSITIVE_PATTERNS:
                if marker in text:
                    findings.append({'kind': 'privacy', 'impact': 'must_fix', 'location': pointer,
                                     'detail': f'sensitive marker {marker!r}'})
                    return
            teaching = any(t in lowered_intent for t in TEACHING_MARKERS)
            if not teaching and ('如何制作ppt' in text or 'how to make slides' in text):
                findings.append({'kind': 'privacy', 'impact': 'needs_judgment', 'location': pointer,
                                 'detail': 'production-instruction phrasing outside a teaching task'})

    scan(page.get('customer_visible') or {}, '/customer_visible')
    return findings


# ---------------------------------------------------------------------------
# Finding classification (AC-C05): fact vs calculation vs advice.


def classify_finding(text: str) -> dict:
    """Classify one piece of review content.

    Calculations are recomputed and wrong arithmetic is must_fix; quantitative
    claims without a basis need judgment; conditional advice is advisory and
    read-only for automation.
    """
    calc = re.search(r'(\d+(?:\.\d+)?)\s*([÷/×x*])\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)\s*(%)?', text)
    if calc:
        left = float(calc.group(1))
        right = float(calc.group(3))
        result = float(calc.group(4))
        operations = {'÷': left / right if right else None, '/': left / right if right else None,
                      '×': left * right, 'x': left * right, '*': left * right}
        value = operations[calc.group(2)]
        if value is None:
            return {'category': 'calculation', 'impact': 'needs_judgment', 'detail': 'division by zero'}
        expected = value * 100 if calc.group(5) else value
        if abs(expected - result) <= 0.51:
            return {'category': 'calculation', 'impact': 'advisory',
                    'detail': 'arithmetic recomputes correctly'}
        return {'category': 'calculation', 'impact': 'must_fix',
                'detail': f'{left:g}{calc.group(2)}{right:g} is {expected:g}, not {result:g}'}
    if re.search(r'(提升|增长|下降|降低|节省|缩短)\s*\d+(?:\.\d+)?\s*%', text) \
            and not re.search(r'(依据|来源|基准)', text):
        return {'category': 'unsupported_number', 'impact': 'needs_judgment',
                'detail': 'quantitative claim without a stated basis'}
    if re.match(r'\s*(建议|可考虑|推荐)', text) or re.search(r'如果.*则建议', text):
        return {'category': 'advice', 'impact': 'advisory', 'detail': 'conditional advice, read-only'}
    return {'category': 'fact', 'impact': 'advisory', 'detail': 'statement of fact'}


# ---------------------------------------------------------------------------
# Source-image expectations stay independent of the SVG registry (AC-B07).


def source_expectations(reference_regions: list[dict], svg_registry: list[str]) -> dict:
    """Map blueprint reference_regions to current confirmation state.

    Removing or shrinking SVG registry entries never shrinks the source
    expectations; unrecognized dimensions stay not_evaluated instead of
    claiming full coverage.
    """
    registered = set(svg_registry or [])
    regions = [{'region_id': region.get('region_id'), 'importance': region.get('importance'),
                'status': 'confirmed' if region.get('region_id') in registered else 'not_evaluated'}
               for region in reference_regions or []]
    coverage = (sum(1 for r in regions if r['status'] == 'confirmed') / len(regions)) \
        if regions and all(r['status'] == 'confirmed' for r in regions) else None
    return {'regions': regions, 'coverage': coverage}
