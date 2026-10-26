"""Original-image expression review, before any SVG or rendered preview exists.

Runtime validates provenance and explicit observed graph claims. It never
pretends to infer the depicted graph from pixels; that is the independent
reviewer's job and must arrive through the authenticated receipt bridge.
"""
from __future__ import annotations

from pathlib import Path
from . import content_review, models, review_evidence, service, tasks
from .store import Store

STAGE = 'original_image'


def packet(store, document, page_id, *, candidate_id=None, frozen_design=None):
    entry = next((row for row in document['pages'] if row['page_id'] == page_id), None)
    if entry is None:
        raise tasks.EnvelopeError('original_review/page_id', 'page is not current')
    original = entry.get('blueprint')
    if candidate_id:
        from .candidates import show
        candidate = show(store.project_root, candidate_id=candidate_id)
        record = candidate['candidate']
        if record['page_id'] != page_id or record['stage'] != 'blueprint' or candidate['generation_basis']['status'] != 'current':
            raise tasks.StaleInputContext('original_review/candidate', 'candidate must be an original of this current Page basis')
        original = record['result_ref']
    if not original:
        raise tasks.EnvelopeError('original_review/original', 'an immutable original image is required; SVG is not required')
    image = store.read_object_json(original)
    models.validate_schema('artifact', image)
    if image.get('role') != 'blueprint' or image.get('page_id') != page_id or image.get('media_type') not in ('image/png', 'image/jpeg', 'image/webp'):
        raise tasks.EnvelopeError('original_review/original', 'review requires this page’s original raster image')
    raw = store.read_object_bytes(image['file'])
    from io import BytesIO
    from PIL import Image
    try:
        with Image.open(BytesIO(raw)) as pixels:
            pixels.load()
            if Image.MIME.get(pixels.format) != image['media_type']:
                raise ValueError('declared raster format differs')
    except (OSError, ValueError) as exc:
        raise tasks.EnvelopeError('original_review/image', 'original bytes are not a decodable declared raster image') from exc
    page = store.read_object_json(entry['page'])
    from .production import frozen_design_options, resolve_generation_design, adopted_blueprint_design
    owned = adopted_blueprint_design(store, document, {**entry, 'blueprint': original})
    recipe_ref = owned['recipe_ref'] if owned else None
    # A frozen packet's design contract decides which fields this recompute
    # may supply; new dispatches keep the full current projection.
    design = resolve_generation_design(store, document, entry, recipe_ref=recipe_ref,
        **frozen_design_options(frozen_design) if frozen_design is not None else {})
    from .effective_requirements import packet_requirements
    return {'schema_version': 'original_review_packet.v1', 'project_id': document['project_id'],
        'page_id': page_id, 'candidate_id': candidate_id, 'page_ref': entry['page'],
        'original_ref': original, 'image_ref': image['file'], 'page': page,
        'resolved_design': design, 'generation_recipe_ref': recipe_ref,
        'effective_requirements': packet_requirements(store, document, page_ids=[page_id], units=['page_copy']),
        'subjects': [entry['page'], original, image['file']],
        'dependencies': [{'kind': 'content', 'identity': 'page:' + page_id, 'sha256': entry['page']['sha256']},
                         {'kind': 'blueprint', 'identity': page_id, 'sha256': image['file']['sha256']}],
        'review_instructions': 'Inspect the actual original image. Report observed node IDs and directed edge endpoints, hierarchy and reading path. A fixed A→B drawn A→C is must_fix now, even if every label exists. Unknown is never pass. This does not assess SVG/PPT conversion or editability.'}


def task_packet(store, task):
    packets = []
    for ref in task.get('inputs') or []:
        if ref['path'].endswith('.json'):
            obj = store.read_object_json(ref)
            if isinstance(obj, dict) and obj.get('schema_version') == 'original_review_packet.v1':
                packets.append((ref, obj))
    if len(packets) != 1:
        raise tasks.EnvelopeError('original_review/packet', 'exactly one fixed original-image packet is required')
    return packets[0]


def semantic_packet(store, fixed):
    from .production import consumed_design
    return {**fixed, 'resolved_design': consumed_design(fixed['resolved_design'], store=store)}


def inputs_current(store, document, task):
    _, fixed = task_packet(store, task)
    try:
        return semantic_packet(store, fixed) == semantic_packet(store, packet(
            store, document, fixed['page_id'], candidate_id=fixed['candidate_id'],
            frozen_design=fixed['resolved_design']))
    except (tasks.EnvelopeError, tasks.StaleInputContext, models.ModelError):
        return False


def author_executions(store, document, fixed):
    # The image is bound by its original Artifact; binary pixels have no
    # editorial JSON ancestry. The producing Task's artifact result still counts.
    return content_review.author_execution_refs(store, document,
        [ref for ref in fixed['subjects'] if ref['path'].endswith('.json')])


def dispatch(project, *, page_id, candidate_id=None, adapter_context=None):
    store = Store(Path(project).expanduser())
    document = store.load_document()
    fixed = packet(store, document, page_id, candidate_id=candidate_id)
    ref = store.put_json_object(fixed)
    capabilities = review_evidence.reviewer_capabilities(adapter_context)
    if not any(capabilities[key] for key in ('independent_review_receipts', 'human_review_receipts')):
        return {'status': 'needs_reviewer', 'review_stage': STAGE, 'packet_ref': ref, 'packet': fixed,
                'reason': 'Original-image inspection requires an applicable authenticated independent or human receipt; native text review is not image inspection.'}
    task = service.open_host_task(store, kind='review', page_ids=[page_id], review_stage=STAGE,
        instruction=fixed['review_instructions'], extra_inputs=[ref, *fixed['subjects']], executor_type='external_reviewer',
        review_units=[{'kind': 'visual_expression', 'page_ids': [page_id], 'reason': 'missing'}])
    return {'status': 'review_dispatched', 'task': task, 'packet_ref': ref, 'packet': fixed}


def validate_result(store, document, task, envelope, *, adapter_context=None):
    _, fixed = task_packet(store, task)
    if not inputs_current(store, document, task):
        raise tasks.StaleInputContext('original_review/basis', 'original image or its requirements changed')
    rows = envelope.get('reviews') or []
    if len(rows) != 1 or rows[0].get('kind') != 'visual_expression':
        raise tasks.EnvelopeError('original_review/kind', 'exactly one visual_expression review is required')
    row = rows[0]
    models.validate_review_semantics(row)
    if row['subjects'] != fixed['subjects'] or row['dependencies'] != fixed['dependencies']:
        raise tasks.EnvelopeError('original_review/basis', 'review must bind the exact frozen Page and original image')
    review_evidence.validate_review_context(adapter_context, store, document, task, envelope)
    reviewer = row['reviewer']
    if reviewer['type'] in ('human_internal', 'human_external'):
        receipt = content_review._human_receipt(adapter_context, row, fixed['subjects'])
    elif reviewer['type'] == 'independent_host' and reviewer.get('independence_confirmed'):
        receipt = content_review._independent_receipt(adapter_context, row, fixed['subjects'],
            author_executions(store, document, fixed))
    else:
        receipt = None
    if receipt is None:
        raise review_evidence.EvidenceRejected('original_review/reviewer', 'no applicable independent image-review receipt')
    if not row.get('observations'):
        raise tasks.EnvelopeError('original_review/observations', 'record actual image observations; empty status assertions are not an inspection')
    checks = row.get('expression_checks')
    if not checks:
        raise tasks.EnvelopeError('original_review/checks', 'explicit observed graph, hierarchy and reading-path checks are required')
    spec = fixed['page']['visual_spec']
    expected_nodes = sorted(node['node_id'] for node in spec.get('nodes') or [])
    expected_edges = sorted((edge['edge_id'], edge['from'], edge['to'], edge['direction']) for edge in spec.get('edges') or [])
    observed_edges = sorted((edge['edge_id'], edge['from'], edge['to'], edge['direction']) for edge in checks['observed_edges'])
    mismatch = sorted(checks['observed_nodes']) != expected_nodes or observed_edges != expected_edges
    unknown = any(checks[key] == 'unknown' for key in ('graph', 'hierarchy', 'reading_path'))
    failed = (mismatch and checks['graph'] != 'unknown') or any(checks[key] == 'fail' for key in ('graph', 'hierarchy', 'reading_path'))
    unresolved = any(f['impact'] in ('must_fix', 'needs_judgment') and f.get('resolution', 'open') == 'open' for f in row['findings'])
    if row['status'] == 'pass' and (unknown or failed or unresolved):
        raise tasks.EnvelopeError('original_review/checks', 'unknown or wrong fixed endpoints cannot pass original-image expression review')
    if failed and (row['status'] != 'fail' or not any(f['impact'] == 'must_fix' and f.get('resolution', 'open') == 'open' for f in row['findings'])):
        raise tasks.EnvelopeError('original_review/findings', 'known graph/expression errors require fail and a must_fix finding before SVG')
    if any(f.get('page_id') != fixed['page_id'] for f in row['findings']):
        raise tasks.EnvelopeError('original_review/findings', 'findings must target this original-image page')
    if row['status'] == 'pass' and retained_image_findings(store, document, semantic_packet(store, fixed)):
        raise tasks.EnvelopeError('original_review/findings', 'the same image retains a known applicable must_fix finding; unrelated Page edits or an ownerless pass cannot erase it')
    return [receipt['receipt_ref']]


def accepted_history(store, document):
    """Only completed original Tasks carrying the existing authenticated proof."""
    for ref in document.get('tasks') or []:
        task = store.read_object_json(ref)
        if task.get('review_stage') != STAGE or task.get('status') != 'completed':
            continue
        _, fixed = task_packet(store, task)
        proofs = [store.read_object_json(r) for r in task.get('result_refs') or [] if r['path'].endswith('.json')]
        if not any(p.get('schema_version') == 'authenticated_review_receipt.v1' and p['claims'].get('task_id') == task['task_id'] for p in proofs):
            continue
        for row in proofs:
            if row.get('schema_version') == 'deck_review.v2' and row.get('review_stage') == STAGE:
                yield semantic_packet(store, fixed), row


def finding_requirement_unchanged(before, current, finding):
    """Compare an identified graph requirement, not the Page object version.

    Changed/removed endpoints are genuinely new requirements. Notes and
    unrelated nodes, edges or relationship labels never erase a fixed-edge defect.
    Unlocalized findings remain conservative: unrelated document changes cannot
    establish that their requirement was withdrawn.
    """
    old, new = before['page'], current['page']
    targets = finding.get('element_refs') or []
    comparisons = []
    for target in targets:
        for prefix, collection, identity in (('edge:', 'edges', 'edge_id'), ('node:', 'nodes', 'node_id')):
            if target.startswith(prefix):
                key = target[len(prefix):]
                a = next((r for r in old['visual_spec'].get(collection, []) if r[identity] == key), None)
                b = next((r for r in new['visual_spec'].get(collection, []) if r[identity] == key), None)
                fields = ('from', 'to', 'direction') if collection == 'edges' else ('node_id',)
                comparisons.append(a is None or (b is not None and all(a.get(field) == b.get(field) for field in fields)))
    if comparisons:
        return any(comparisons)
    return True


def retained_image_findings(store, document, current, *, history=None):
    result = []
    for before, row in accepted_history(store, document) if history is None else history:
        if before['page_id'] != current['page_id'] or before['image_ref']['sha256'] != current['image_ref']['sha256']:
            continue
        for finding in row.get('findings') or []:
            if (finding.get('impact') == 'must_fix' and finding.get('resolution', 'open') == 'open'
                    and finding_requirement_unchanged(before, current, finding)):
                result.append({'review_id': row['review_id'], 'finding_id': finding['finding_id']})
    return result


def reference_status(store, document, page_id, *, candidate_id=None, use='expand'):
    if use not in ('expand', 'view', 'compare', 'repair_reference'):
        raise ValueError('unknown original-image reference use')
    current = semantic_packet(store, packet(store, document, page_id, candidate_id=candidate_id))
    accepted = []
    history = list(accepted_history(store, document))
    retained = retained_image_findings(store, document, current, history=history)
    for fixed, row in history:
        keys = ('page_ref', 'image_ref', 'resolved_design', 'effective_requirements')
        try:
            # Each accepted history stays readable under its own frozen design
            # contract; an unreadable contract keeps that row conservative.
            aligned = semantic_packet(store, packet(store, document, fixed['page_id'],
                candidate_id=fixed['candidate_id'], frozen_design=fixed['resolved_design']))
        except models.ModelError:
            continue
        if all(fixed[key] == aligned[key] for key in keys):
            accepted.append(row)
    # Never let a later pass erase a known error on the exact same image.
    state = 'fail' if retained or any(r['status'] == 'fail' for r in accepted) else ('pass' if any(r['status'] == 'pass' for r in accepted) else 'not_evaluated')
    return {'status': state, 'use': use, 'allowed': state == 'pass' or use != 'expand',
            'original_ref': current['original_ref'], 'retained_findings': retained,
            'limitations': ['Repair references retain their known issues; the next image needs a fresh applicable independent check before expansion.']}
