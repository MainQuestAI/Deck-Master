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
    key = f"{dep.get('kind')}:{dep.get('identity')}"
    # Pre-rebuild reviews used svg:<page> and svg_preview:<page>.
    if key.startswith(('svg:', 'svg_preview:', 'ppt_preview:')):
        return 'artifact:' + key
    return key


def finding_closed(reviews: list[dict], review: dict, finding: dict, artifacts: dict) -> bool:
    """Resolve one finding through explicit, current replacement reviews."""
    replacements = {}
    for item in reviews:
        if item.get('replaces'):
            replacements.setdefault(_ref_key(item['replaces']), []).append(item)
    subjects = artifacts.get('_subjects') or {}
    retired_assets = artifacts.get('_retired_assets') or set()
    page_id = finding.get('page_id')

    def changed_on_page(owner, candidate):
        old = [subjects.get(_ref_key(ref)) for ref in owner.get('subjects') or []]
        new = [subjects.get(_ref_key(ref)) for ref in candidate.get('subjects') or []]
        for before in old:
            if not before or before.get('page_id') != page_id or before.get('role') not in ('page', 'svg', 'ppt_preview'):
                continue
            for after in new:
                if (after and after.get('current') and after.get('page_id') == page_id and
                        after.get('role') == before.get('role') and
                        after.get('file_sha') != before.get('file_sha')):
                    return True
        for before in old:
            if not before or before.get('role') != 'pptx' or page_id not in before.get('slides', {}):
                continue
            for after in new:
                if (after and after.get('role') == 'pptx' and after.get('current') and
                        page_id in after.get('slides', {}) and
                        after['slides'][page_id] != before['slides'][page_id]):
                    return True
        # Synthetic fixtures have no Store metadata, and owners may cite only
        # the Page. The same page's dependency must still prove an actual
        # digest change to a current product cited by the candidate.
        old_deps = {_dependency_key(d): d.get('sha256') for d in owner.get('dependencies') or []}
        new_deps = {_dependency_key(d): d.get('sha256') for d in candidate.get('dependencies') or []}
        for key in (f'content:page:{page_id}', f'artifact:svg:{page_id}',
                    f'artifact:ppt_preview:{page_id}'):
            if (key in old_deps and key in new_deps and
                    old_deps[key] != new_deps[key] == artifacts.get(key) and
                    any(ref.get('sha256') in (artifacts[key], artifacts.get(f'{key}:ref'))
                        for ref in candidate.get('subjects') or [])):
                return True
        return False

    def current_page_subject(candidate):
        if subjects:
            return any((info := subjects.get(_ref_key(ref))) and info.get('current') and
                       info.get('page_id') == page_id and info.get('role') == 'page'
                       for ref in candidate.get('subjects') or [])
        return any(ref.get('sha256') == artifacts.get(f'content:page:{page_id}')
                   for ref in candidate.get('subjects') or [])

    def current_preview_subject(candidate):
        if review.get('review_stage', 'final') != 'page_visual':
            return True
        return any((info := subjects.get(_ref_key(ref))) and info.get('current') and
                   info.get('page_id') == page_id and info.get('role') == 'svg_preview'
                   for ref in candidate.get('subjects') or [])

    def current_final_output_changed(owner, candidate):
        if review.get('review_stage', 'final') == 'page_visual':
            return True
        if subjects:
            before = [subjects.get(_ref_key(ref)) for ref in owner.get('subjects') or []]
            after = [subjects.get(_ref_key(ref)) for ref in candidate.get('subjects') or []]
            if not any(b and b.get('role') == 'pptx' for b in before):
                # Owner never cited a deck: the current deck is the output;
                # changed_on_page carries the actual repair proof.
                return any(a and a.get('role') == 'pptx' and a.get('current') for a in after)
            return any(a and a.get('role') == 'pptx' and a.get('current') and
                       b and b.get('role') == 'pptx' and a.get('file_sha') != b.get('file_sha')
                       for a in after for b in before)
        old = {_ref_key(ref) for ref in owner.get('subjects') or []}
        return any(ref.get('sha256') == artifacts.get('artifact:pptx') and _ref_key(ref) not in old
                   for ref in candidate.get('subjects') or [])

    stack = [review]
    seen = set()
    while stack:
        owner = stack.pop()
        owner_ref = owner.get('ref')
        if not owner_ref or _ref_key(owner_ref) in seen:
            continue
        seen.add(_ref_key(owner_ref))
        for candidate in replacements.get(_ref_key(owner_ref), []):
            if (candidate.get('review_id') != review.get('review_id') or
                    candidate.get('kind') != review.get('kind') or
                    candidate.get('review_stage', 'final') != review.get('review_stage', 'final')):
                continue
            followup = next((f for f in candidate.get('findings') or []
                             if f.get('finding_id') == finding.get('finding_id') and
                             f.get('page_id') == page_id), None)
            if followup is None:
                continue
            deps = candidate.get('dependencies') or []
            old_keys = {_dependency_key(dep) for dep in owner.get('dependencies') or []}
            new_keys = {_dependency_key(dep) for dep in deps}
            if f'content:page:{page_id}' not in new_keys:
                continue
            removed = old_keys - new_keys
            old_deps = {_dependency_key(dep): dep for dep in owner.get('dependencies') or []}
            # Untracked legacy keys can never be current again; assets must be
            # verifiably retired. Tracked keys must be re-declared.
            if any((key[6:], old_deps[key].get('sha256')) not in retired_assets
                   if key.startswith('asset:') else key in artifacts
                   for key in removed):
                continue
            if removed and not (followup.get('resolution_reason') or '').strip():
                continue
            current = all(artifacts.get(_dependency_key(dep)) == dep.get('sha256') for dep in deps)
            # Intermediate historical reviews may be stale. Compare the
            # current endpoint with the original finding owner, so a later
            # reversion cannot masquerade as a repair.
            changed = changed_on_page(review, candidate)
            output_changed = current_final_output_changed(review, candidate)
            if current and candidate.get('observations') and followup.get('evidence'):
                resolution = followup.get('resolution')
                if (resolution == 'accepted_variance' and finding.get('impact') == 'needs_judgment' and
                        current_page_subject(candidate) and current_preview_subject(candidate) and
                        (followup.get('resolution_reason') or '').strip() and
                        (not removed or (followup.get('resolution_reason') or '').strip())):
                    return True
                if (resolution == 'fixed' and changed and current_page_subject(candidate) and
                        current_preview_subject(candidate) and
                        output_changed):
                    return True
            stack.append(candidate)
    return False


# Kinds whose pass requires actual reading by a non-tool reviewer
# (spec 07.1/07.2: mechanical tool scans cannot substitute content review).
SUBSTANTIVE_KINDS = {'content', 'blueprint_content', 'blueprint_fidelity'}


def _substance_gate(kind: str, review: dict) -> str | None:
    """Return None when the pass has execution substance, else a typed reason."""
    reviewer_type = (review.get('reviewer') or {}).get('type')
    if reviewer_type == 'tool' and kind in SUBSTANTIVE_KINDS:
        return 'tool_cannot_substance'
    if not review.get('observations'):
        return 'missing_execution_evidence'
    return None


def open_findings(review: dict) -> list[dict]:
    return [f for f in review.get('findings') or []
            if f.get('impact') == 'must_fix' and f.get('resolution') == 'open']


def pending_judgments(review: dict) -> list[dict]:
    return [f for f in review.get('findings') or []
            if f.get('impact') == 'needs_judgment' and f.get('resolution') == 'open']


PAGE_VISUAL_KINDS = ('blueprint_content', 'blueprint_fidelity', 'readability')


def evaluate_page_visual(entry: dict, reviews: list[dict], artifacts: dict,
                         allowed_asset_ids=()) -> dict:
    """Evaluate a current page's pre-compile image/SVG review independently of PPT review."""
    page_id = entry['page_id']
    required_subjects = {_ref_key(entry[slot]) for slot in ('page', 'blueprint', 'svg', 'svg_preview')}
    required_dependencies = {f'content:page:{page_id}', f'blueprint:{page_id}',
                             f'artifact:svg:{page_id}', f'style:{page_id}'}
    required_dependencies.update(f'asset:{asset_id}' for asset_id in allowed_asset_ids)
    current = {}
    for review in reviews:
        if review.get('review_stage') != 'page_visual' or review.get('kind') not in PAGE_VISUAL_KINDS:
            continue
        subjects = {_ref_key(ref) for ref in review.get('subjects') or []}
        if not required_subjects <= subjects:
            continue
        deps = {_dependency_key(dep): dep['sha256'] for dep in review.get('dependencies') or []}
        if not required_dependencies <= deps.keys() or any(artifacts.get(key) != sha for key, sha in deps.items()):
            continue
        current.setdefault(review['kind'], []).append(review)
    missing = [kind for kind in PAGE_VISUAL_KINDS if kind not in current]
    open_findings_by_kind = {}
    judgments = []
    for kind, records in current.items():
        for owner in records:
            for finding in open_findings(owner):
                if finding.get('page_id') == page_id and not finding_closed(reviews, owner, finding, artifacts):
                    outstanding = open_findings_by_kind.setdefault(kind, [])
                    if finding['finding_id'] not in outstanding:
                        outstanding.append(finding['finding_id'])
            for finding in pending_judgments(owner):
                if (finding.get('page_id') == page_id and
                        not finding_closed(reviews, owner, finding, artifacts) and
                        finding['finding_id'] not in judgments):
                    judgments.append(finding['finding_id'])
    unclosed_prior = []
    for owner in reviews:
        if owner.get('review_stage') != 'page_visual' or owner.get('kind') not in PAGE_VISUAL_KINDS:
            continue
        if not any(_dependency_key(dep) == f'content:page:{page_id}'
                   for dep in owner.get('dependencies') or []):
            continue
        for finding in open_findings(owner):
            if finding.get('page_id') == page_id and not finding_closed(reviews, owner, finding, artifacts):
                if finding['finding_id'] not in unclosed_prior:
                    unclosed_prior.append(finding['finding_id'])
    if open_findings_by_kind:
        status = 'fail'
    elif judgments or unclosed_prior:
        status = 'needs_review'
    elif missing:
        status = 'not_evaluated'
    elif all(any(r.get('status') == 'pass' and _substance_gate(kind, r) is None
                 for r in current[kind]) for kind in PAGE_VISUAL_KINDS):
        status = 'pass'
    else:
        status = 'not_evaluated'
    return {'status': status, 'page_id': page_id, 'missing_dimensions': missing,
            'open_must_fix': open_findings_by_kind, 'pending_judgments': judgments,
            'unclosed_prior_findings': unclosed_prior}


def evaluate_current(document: dict, reviews: list[dict], artifacts: dict) -> dict:
    """The one interpretation of the current check state (AC-R01/R02/R03/R10).

    Reviews are interpreted together with hard output facts (P1-01, injected
    by the caller under ``document['_output_facts']``): a failing render
    report fails the deck regardless of review status; missing render_report
    or produced-artifact completeness gaps block a pass. Open must_fix
    findings aggregate per finding_id across ALL current reviews of a
    dimension and only a validated closing review can fix one (P1-02).
    """
    pages = document.get('pages') or []
    current = (document.get('outputs') or {}).get('pptx')
    facts = document.get('_output_facts') or {}
    if not current:
        return {'status': 'not_evaluated', 'current_outputs': None, 'dimensions': {}, 'stale': [],
                'missing_dimensions': [f'{k}:{e["page_id"]}' for k in REQUIRED_KINDS for e in pages],
                'output_facts': facts, 'dimension_reasons': {},
                'reason': 'no current pptx output'}
    tasks = document.get('tasks') or []
    suspended_pages = set()
    for task in tasks:
        if isinstance(task, dict) and task.get('status') in OPEN_TASK_STATUSES:
            suspended_pages.update(task.get('scope_pages') or [])

    def dependencies_current(review):
        # P1-07: a dependency counts as current only when it resolves against
        # the current digest map and the sha matches; anything unresolvable is
        # stale with a typed reason (no silent pass for known prefixes).
        for dep in review.get('dependencies') or []:
            key = _dependency_key(dep)
            if key in artifacts:
                if artifacts[key] != dep.get('sha256'):
                    return False, 'dependency sha does not match the current object'
                continue
            if key.startswith('source:'):
                return False, f'unresolvable source dependency {key!r}'
            return False, f'unverifiable dependency kind {key!r}'
        return True, ''

    dimensions: dict[str, dict] = {}
    dimension_reasons: dict[str, str] = {}
    stale: list[dict] = []
    dim_reviews: dict[tuple, list] = {}
    for review in reviews:
        if review.get('review_stage', 'final') != 'final':
            continue
        subjects = {_ref_key(s) for s in review.get('subjects') or []}
        matched = [e for e in pages if _ref_key(e.get('page') or {}) in subjects]
        if not matched:
            continue
        deps_current, dep_reason = dependencies_current(review)
        for entry in matched:
            key = (review.get('kind'), entry['page_id'])
            if _ref_key(current) not in subjects or not deps_current:
                stale.append({'kind': review.get('kind'), 'page_id': entry['page_id'],
                              'review_id': review.get('review_id'), 'reason': dep_reason or
                              'subjects or dependencies do not match the current outputs'})
                continue
            dim_reviews.setdefault(key, []).append(review)  # adoption order
    for (kind, page_id), reviews_for_dim in dim_reviews.items():
        key = f'{kind}:{page_id}'
        open_by_id: dict[str, dict] = {}
        judgments: list[str] = []
        history_for_dim = [r for r in reviews
                           if r.get('review_stage', 'final') == 'final' and r.get('kind') == kind]
        for review in history_for_dim:
            for finding in open_findings(review):
                if finding.get('page_id') == page_id:
                    open_by_id.setdefault(finding['finding_id'], finding)
            for finding in pending_judgments(review):
                if finding.get('page_id') == page_id and not finding_closed(reviews, review, finding, artifacts):
                    if finding['finding_id'] not in judgments:
                        judgments.append(finding['finding_id'])
        remaining = [fid for fid in open_by_id
                     if any(not finding_closed(reviews, owner, finding, artifacts)
                            for owner in history_for_dim
                            for finding in open_findings(owner)
                            if finding.get('page_id') == page_id and finding.get('finding_id') == fid)]
        closed = [fid for fid in open_by_id if fid not in remaining]
        passing = [review for review in reviews_for_dim if review.get('status') == 'pass']
        viable = [review for review in passing if _substance_gate(kind, review) is None]
        if remaining:
            effective, reason = 'fail', ''
        elif judgments:
            effective, reason = 'needs_review', ''
        elif viable:
            effective, reason = 'pass', ''
        elif passing:
            effective, reason = 'not_evaluated', _substance_gate(kind, passing[-1])
        elif closed:
            effective, reason = 'needs_review', 'fixes_verified_no_passing_review'
        else:
            effective, reason = reviews_for_dim[-1].get('status') or 'not_evaluated', ''
        if reason:
            dimension_reasons[key] = reason
        dimensions[key] = {
            'review_id': reviews_for_dim[-1].get('review_id'),
            'status': effective,
            'reported_status': reviews_for_dim[-1].get('status'),
            'stale': False,
            'open_must_fix': remaining,
            'closed_findings': closed,
            'pending_judgments': judgments,
        }
    missing = [f'{kind}:{entry["page_id"]}' for kind in REQUIRED_KINDS for entry in pages
               if f"{kind}:{entry['page_id']}" not in dimensions]
    if suspended_pages:
        for key in list(dimensions):
            if key.rsplit(':', 1)[1] in suspended_pages:
                del dimensions[key]
                dimension_reasons.pop(key, None)
                if key not in missing:
                    missing.append(key)
    render_failed = facts.get('render_report_status') == 'fail'
    render_report_findings = facts.get('render_report_findings') or []
    completeness_gaps = facts.get('completeness') or []
    render_report_missing = bool(facts.get('render_report_missing'))
    if render_failed or any(d['status'] == 'fail' or d['open_must_fix'] for d in dimensions.values()):
        status = 'fail'
    elif missing or render_report_missing or completeness_gaps or dimension_reasons:
        status = 'not_evaluated'
    elif any(d['pending_judgments'] for d in dimensions.values()):
        status = 'needs_review'
    elif dimensions and all(d['status'] == 'pass' for d in dimensions.values()):
        status = 'pass'
    else:
        status = 'not_evaluated'
    result = {'status': status, 'current_outputs': current, 'dimensions': dimensions,
              'stale': stale, 'missing_dimensions': sorted(missing),
              'output_facts': facts, 'dimension_reasons': dimension_reasons}
    if render_failed:
        result['render_report_findings'] = render_report_findings
    if suspended_pages and status == 'not_evaluated':
        result['reason'] = f'host tasks still open for pages {sorted(suspended_pages)}'
    return result


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
        # Calibrated on three real sample classes (spec 07.4): genuine renderer
        # anti-alias/font variance stays moderate and uniform — well below any
        # structural loss, which the ink rules above already catch as must_fix.
        if ratio <= 0.10 and max_delta <= 200:
            findings.append({'kind': 'render_difference', 'impact': 'accepted_variance',
                             'location': region['region_id'],
                             'detail': f'renderer variance scale {ratio:.5f} max delta {max_delta}'})
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
            # FALSE_FRIENDS are never sensitive by themselves; they must not
            # short-circuit the scan either — any sensitive marker in the same
            # string still reports.
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
