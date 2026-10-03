"""Required text coverage in the declared native compiler subset.

Bindings are authoritative. Unbound atoms require independent character
intervals whose visibility is provable without choosing a favorable match.
"""
import math

from .content import visible_atoms

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}


def _normalize(text):
    return ''.join(str(text).split())


def _color_alpha(color):
    if color is None or color.tag.rsplit('}', 1)[-1] != 'srgbClr':
        return None
    value = color.get('val', '')
    if len(value) != 6 or any(c not in '0123456789abcdefABCDEF' for c in value):
        return None
    alpha = 1.0
    for child in color:
        kind = child.tag.rsplit('}', 1)[-1]
        if not kind.startswith('alpha'):
            continue  # RGB/luminance transforms do not change opacity.
        if kind not in ('alpha', 'alphaMod', 'alphaOff'):
            return None
        try:
            fraction = float(child.get('val')) / 100000
        except (ValueError, TypeError):
            return None
        if not math.isfinite(fraction) or not (-1 if kind == 'alphaOff' else 0) <= fraction <= 1:
            return None
        alpha = fraction if kind == 'alpha' else alpha * fraction if kind == 'alphaMod' else alpha + fraction
        alpha = min(1.0, max(0.0, alpha))
    return alpha


def _gradient_state(paint):
    """A same-position group has an incoming first and outgoing last alpha.

    Intermediate stops and clipped endpoint sides have zero paint area. Do
    not collapse to just the last stop: the incoming side can still be visible.
    """
    groups = []
    for stop in paint.findall('a:gsLst/a:gs', NS):
        try:
            position = int(stop.get('pos'))
        except (ValueError, TypeError):
            return 'unverifiable'
        alpha = _color_alpha(stop[0]) if len(stop) == 1 else None
        if (alpha is None or not 0 <= position <= 100000 or
                groups and position < groups[-1][0]):
            return 'unverifiable'
        if groups and position == groups[-1][0]:
            groups[-1][2] = alpha
        else:
            groups.append([position, alpha, alpha])
    if not groups:
        return 'unverifiable'
    # Explicit pad extends the first/last color to the gradient bounds.
    if groups[0][0] > 0 and groups[0][1] > 0:
        return 'visible'
    if groups[-1][0] < 100000 and groups[-1][2] > 0:
        return 'visible'
    if any(left[2] > 0 or right[1] > 0 for left, right in zip(groups, groups[1:])):
        return 'visible'
    # A radial/path gradient may pad beyond its outer circle inside the
    # rectangular text box. A last-stop-only endpoint needs geometry proof.
    if paint.find('a:path', NS) is not None and groups[-1][2] > 0:
        return 'unverifiable'
    return 'unreadable'


def _run_state(props):
    """visible / unreadable / unverifiable; never guess inherited fill."""
    if props is None:
        return 'unverifiable'
    try:
        size = float(props.get('sz', ''))
    except (TypeError, ValueError):
        return 'unverifiable'
    if not math.isfinite(size) or size < 0:
        return 'unverifiable'
    if size < 600:
        return 'unreadable'
    paints = [child for child in props if child.tag.rsplit('}', 1)[-1] in
              ('noFill', 'solidFill', 'gradFill', 'blipFill', 'pattFill', 'grpFill')]
    if len(paints) != 1:
        return 'unverifiable'
    paint = paints[0]; kind = paint.tag.rsplit('}', 1)[-1]
    if kind == 'noFill':
        return 'unreadable'
    if kind == 'solidFill':
        alphas = [_color_alpha(paint[0])] if len(paint) == 1 else [None]
    elif kind == 'gradFill':
        return _gradient_state(paint)
    else:
        return 'unverifiable'
    if not alphas or any(alpha is None for alpha in alphas):
        return 'unverifiable'
    return 'visible' if any(alpha > 0 for alpha in alphas) else 'unreadable'


def _covers(runs, wanted):
    stream = ''.join(run['text'] for run in runs)
    offsets = []; offset = 0
    for run in runs:
        offsets.append((offset, offset + len(run['text']), run)); offset += len(run['text'])
    covers = []; start = stream.find(wanted)
    while start >= 0:
        end = start + len(wanted)
        selected = [run for left, right, run in offsets if right > left and right > start and left < end]
        covers.append({'start': start, 'end': end, 'runs': selected})
        start = stream.find(wanted, start + 1)
    return covers


def _check_required_text(root, source, page):
    native = [shape for shape in root.findall('.//p:sp', NS) if shape.findall('.//a:t', NS)]
    original = [shape for shape in source['shapes'] if shape['kind'] == 'text']
    atoms = [atom for atom in visible_atoms(page) if _normalize(atom.get('text', ''))]
    valid = len(native) == len(original); runs = []; findings = []
    for index, shape in enumerate(native):
        ir = original[index] if index < len(original) else {}
        text = ''.join(node.text or '' for node in shape.findall('.//a:t', NS))
        name = shape.find('p:nvSpPr/p:cNvPr', NS); bound = ir.get('atom_id')
        if text != ir.get('text') or (bound and (name is None or name.get('name') != bound)):
            valid = False
        for run in shape.findall('.//a:r', NS):
            props = run.find('a:rPr', NS)
            runs.append({'text': _normalize(''.join(node.text or '' for node in run.findall('a:t', NS))),
                         'bound': bound, 'element': ir.get('id', f'text:{index}'),
                         'size': props.get('sz') if props is not None else None, 'state': _run_state(props)})

    def finding(atom, code, detail, covers):
        elements = sorted({run['element'] for cover in covers for run in cover['runs']})
        if code == 'unreadable_text':
            bad = next(run for cover in covers for run in cover['runs'] if run['state'] == 'unreadable')
            detail = f"run renders at sz={bad['size']!r} (or has no visible native fill) for a required atom"
        findings.append({'page_id': page['page_id'], 'atom_id': atom['atom_id'], 'code': code,
                         'svg_elements': elements, 'detail': detail})

    if atoms and not valid:
        findings.append({'page_id': page['page_id'], 'code': 'unverifiable_text_mapping',
                         'detail': 'native text objects do not match their source text and atom bindings'})
    if valid:
        unbound = {}
        for atom in atoms:
            wanted = _normalize(atom['text']); bound = [run for run in runs if run['bound'] == atom['atom_id']]
            if not bound:
                unbound.setdefault(wanted, []).append(atom)
                continue
            covers = _covers(bound, wanted)
            if any(all(run['state'] == 'visible' for run in cover['runs']) for cover in covers):
                continue
            unknown = any(run['state'] == 'unverifiable' for cover in covers for run in cover['runs'])
            finding(atom, 'unverifiable_text_mapping' if not covers or unknown else 'unreadable_text',
                    'required bound text has no provable readable coverage; inspect the named SVG objects', covers)

        # Keep original offsets, including bindings as barriers. Removing bound
        # runs before searching would fabricate a body across another atom.
        candidates = {wanted: [cover for cover in _covers(runs, wanted)
                               if all(run['bound'] is None for run in cover['runs'])] for wanted in unbound}
        # A complete, mandatory set for one text reserves its intervals.
        # For example AB + B has a unique disjoint allocation: B inside AB
        # belongs to AB, while the separate B supplies the second atom.
        changed = True
        while changed:
            changed = False
            for wanted, group in unbound.items():
                covers = candidates[wanted]
                ordered = sorted(covers, key=lambda cover: cover['start'])
                if len(ordered) != len(group) or any(
                        left['end'] > right['start'] for left, right in zip(ordered, ordered[1:])):
                    continue
                for other in unbound:
                    if other == wanted:
                        continue
                    remaining = [cover for cover in candidates[other] if not any(
                        cover['start'] < fixed['end'] and cover['end'] > fixed['start'] for fixed in ordered)]
                    if len(remaining) != len(candidates[other]):
                        candidates[other] = remaining; changed = True
        overlaps = set(); active = []
        intervals = sorted((cover['start'], cover['end'], wanted)
                           for wanted, covers in candidates.items() for cover in covers)
        for start, end, wanted in intervals:
            active = [(stop, word) for stop, word in active if stop > start]
            for _, word in active:
                if word != wanted:
                    overlaps.update((word, wanted))
            active.append((end, wanted))
        for wanted, group in unbound.items():
            covers = candidates[wanted]; count = 0; last_end = -1
            for cover in sorted(covers, key=lambda cover: cover['end']):
                if cover['start'] >= last_end:
                    count += 1; last_end = cover['end']
            states = {'unverifiable' if any(run['state'] == 'unverifiable' for run in cover['runs']) else
                      'unreadable' if any(run['state'] == 'unreadable' for run in cover['runs']) else 'visible'
                      for cover in covers}
            ambiguous = wanted in overlaps or count < len(group) or 'unverifiable' in states
            # Visibility must not select a preferred match. A duplicate mix
            # could be hidden required text or unrelated decoration.
            ambiguous |= 'visible' in states and 'unreadable' in states
            if ambiguous:
                for atom in group:
                    finding(atom, 'unverifiable_text_mapping',
                            'unbound required text has ambiguous or insufficient distinct coverage; '
                            f'add data-atom-id="{atom["atom_id"]}" to its SVG text objects', covers)
            elif 'unreadable' in states:
                for atom in group:
                    finding(atom, 'unreadable_text', 'required text is under 6pt or has no visible native fill', covers)
    if runs and all(run['state'] == 'unreadable' for run in runs):
        findings.append({'page_id': page['page_id'], 'code': 'hidden_or_tiny_text',
                         'detail': 'all text runs are invisible or under 6pt'})
    return findings
