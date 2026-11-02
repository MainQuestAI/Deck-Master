"""Located Page relationship checks on actual editable native text geometry.

Atom bindings locate text; they do not by themselves prove the table cell or
node owns that text. These checks consume native PPTX coordinates, so a later
conversion that moves a carrier is checked as well as the source SVG.
"""
from __future__ import annotations

import math
from collections import defaultdict

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
EMU_PER_PX = 9525


def _geometry(shape):
    transform = shape.find("p:spPr/a:xfrm", NS)
    if transform is None:
        return None
    offset, extent = transform.find("a:off", NS), transform.find("a:ext", NS)
    if offset is None or extent is None:
        return None
    x, y = int(offset.get("x")) / EMU_PER_PX, int(offset.get("y")) / EMU_PER_PX
    width, height = int(extent.get("cx")) / EMU_PER_PX, int(extent.get("cy")) / EMU_PER_PX
    angle = math.radians(int(transform.get('rot', '0')) / 60000)
    if angle:
        cx, cy = x + width / 2, y + height / 2
        width, height = (abs(width * math.cos(angle)) + abs(height * math.sin(angle)),
                         abs(width * math.sin(angle)) + abs(height * math.cos(angle)))
        x, y = cx - width / 2, cy - height / 2
    return {"x": x, "y": y, "width": width, "height": height,
            "cx": x + width / 2, "cy": y + height / 2}


def _inside(item, bounds):
    # Two EMUs account only for independently rounded native offsets/extents.
    epsilon = 2 / EMU_PER_PX
    left, top, right, bottom = bounds
    return (item['x'] >= left - epsilon and item['y'] >= top - epsilon
            and item['x'] + item['width'] <= right + epsilon
            and item['y'] + item['height'] <= bottom + epsilon)



def _inside_perimeter(item, perimeter):
    """Contain all carrier corners in an already verified convex frame.

    Keep the same two-EMU rounding allowance as rectangular cell containment;
    an axis-aligned frame envelope cannot replace its actual sloped edges.
    """
    edges = list(zip(perimeter, perimeter[1:] + perimeter[:1]))
    winding = 1 if sum(a[0]*b[1] - b[0]*a[1] for a, b in edges) > 0 else -1
    corners = [(x, y) for x in (item['x'], item['x'] + item['width'])
               for y in (item['y'], item['y'] + item['height'])]
    return all(winding * ((b[0]-a[0])*(y-a[1]) - (b[1]-a[1])*(x-a[0]))
               >= -(2 / EMU_PER_PX) * math.dist(a, b)
               for a, b in edges for x, y in corners)


def _native_grid_shape(native, *, frame):
    """A narrow native grid subset, not a DrawingML bounding-box inference.

    Literal single-path line segments and closed convex polygonal frames
    (including the emitter's rounded-rect outline) are supported, as is an
    unadjusted native rect preset. Other geometry/paint stays unverified.
    """
    try:
        if (native.find('p:spPr/a:scene3d', NS) is not None
                or native.find('p:spPr/a:sp3d', NS) is not None):
            return None
        transform = native.find('p:spPr/a:xfrm', NS)
        offset, extent = transform.find('a:off', NS), transform.find('a:ext', NS)
        x, y = int(offset.get('x')) / EMU_PER_PX, int(offset.get('y')) / EMU_PER_PX
        width, height = int(extent.get('cx')) / EMU_PER_PX, int(extent.get('cy')) / EMU_PER_PX
        rotation = int(transform.get('rot', '0'))
        if min(width, height) <= 0 or rotation % 5400000:
            return None
        flips = [transform.get(key, '0') for key in ('flipH', 'flipV')]
        if any(value not in ('0', '1', 'true', 'false') for value in flips):
            return None
        line = native.find('p:spPr/a:ln', NS)
        color = line.find('a:solidFill/a:srgbClr', NS) if line is not None else None
        if line is None or int(line.get('w', '0')) <= 0 or color is None:
            return None
        if (len(line.findall('a:solidFill', NS)) != 1
                or len(line.find('a:solidFill', NS)) != 1
                or line.find('a:noFill', NS) is not None or line.find('a:gradFill', NS) is not None
                or any(child.tag != '{' + NS['a'] + '}alpha' for child in color)
                or len(color) > 1):
            return None
        if len(color) and not 0 < int(color[0].get('val')) <= 100000:
            return None
        dash = line.find('a:prstDash', NS)
        if line.find('a:custDash', NS) is not None or (dash is not None and dash.get('val') != 'solid'):
            return None
        custom = native.find('p:spPr/a:custGeom', NS)
        preset = native.find('p:spPr/a:prstGeom', NS)
        if (custom is None) == (preset is None):
            return None
        if preset is not None:
            if not frame or preset.get('prst') != 'rect' or preset.findall('a:avLst/*', NS):
                return None
            local = [(0, 0), (1, 0), (1, 1), (0, 1)]
        else:
            paths = custom.findall('a:pathLst/a:path', NS)
            if len(paths) != 1:
                return None
            path = paths[0]
            pw, ph = int(path.get('w')), int(path.get('h'))
            if min(pw, ph) <= 0 or path.get('stroke', 'true') not in ('1', 'true'):
                return None
            commands = list(path)
            tags = [c.tag.rsplit('}', 1)[-1] for c in commands]
            if frame:
                if len(tags) < 5 or tags[0] != 'moveTo' or tags[-1] != 'close' or set(tags[1:-1]) != {'lnTo'}:
                    return None
                commands = commands[:-1]
            elif tags != ['moveTo', 'lnTo']:
                return None
            local = []
            for command in commands:
                if len(command) != 1 or command[0].tag != '{' + NS['a'] + '}pt':
                    return None
                px, py = int(command[0].get('x')), int(command[0].get('y'))
                if not (0 <= px <= pw and 0 <= py <= ph):
                    return None
                local.append((px / pw, py / ph))
        angle = math.radians(rotation / 60000)
        points = []
        for px, py in local:
            dx, dy = (px - .5) * width, (py - .5) * height
            dx *= -1 if flips[0] in ('1', 'true') else 1
            dy *= -1 if flips[1] in ('1', 'true') else 1
            points.append((x + width / 2 + dx * math.cos(angle) - dy * math.sin(angle),
                           y + height / 2 + dx * math.sin(angle) + dy * math.cos(angle)))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    epsilon = 2 / EMU_PER_PX
    if frame and math.dist(points[0], points[-1]) <= epsilon:
        points.pop()
    left, top = min(p[0] for p in points), min(p[1] for p in points)
    right, bottom = max(p[0] for p in points), max(p[1] for p in points)
    geometry = dict(x=left, y=top, width=right-left, height=bottom-top)
    if not frame:
        return geometry if math.dist(*points) > epsilon else None
    if len(points) < 4 or min(right-left, bottom-top) <= epsilon:
        return None
    edges = list(zip(points, points[1:] + points[:1]))
    turns = []
    for first, second in zip(edges, edges[1:] + edges[:1]):
        a, b = (first[1][i] - first[0][i] for i in (0, 1))
        c, d = (second[1][i] - second[0][i] for i in (0, 1))
        if math.hypot(a, b) <= epsilon:
            return None
        turns.append(math.atan2(a*d-b*c, a*c+b*d))
    if (not math.isclose(abs(sum(turns)), math.tau, abs_tol=1e-7)
            or (any(t > 1e-9 for t in turns) and any(t < -1e-9 for t in turns))):
        return None
    sides = {'left': [], 'right': [], 'top': [], 'bottom': []}
    for a, b in edges:
        for key, value in (('left', left), ('right', right)):
            if abs(a[0]-value) <= epsilon and abs(b[0]-value) <= epsilon:
                sides[key].append(sorted((a[1], b[1])))
        for key, value in (('top', top), ('bottom', bottom)):
            if abs(a[1]-value) <= epsilon and abs(b[1]-value) <= epsilon:
                sides[key].append(sorted((a[0], b[0])))
    return {**geometry, 'sides': sides, 'perimeter': tuple(points)} if all(sides.values()) else None


def _table_grid(records, table_id, columns, rows, atoms, page_id, incomplete):
    """Recover a declared table's complete grid from actual native geometry.

    No text width/alignment is a column boundary. A tagged frame needs all
    full-span native rules and correctly located headers before it proves cell
    bounds. An absent/ambiguous grid is unverified, never an enlarged tolerance.
    """
    grids = set()
    for record in records:
        if not record.get('table_frame') or record.get('table_id') != table_id:
            continue
        frame = record.get('grid_geometry')
        if frame is None:
            continue
        left, top = frame['x'], frame['y']
        right, bottom = left + frame['width'], top + frame['height']
        # Native emitters give a zero-width/height line a 0.01px extent.
        # This epsilon identifies coincident rules; it is not cell text slop.
        epsilon = .02
        vertical, horizontal = [], []
        for record in records:
            if record['kind'] != 'line' or record.get('grid_geometry') is None:
                continue
            rule = record['grid_geometry']
            if (rule['width'] <= epsilon and left < rule['x'] < right
                    and abs(rule['y'] - top) <= epsilon
                    and abs(rule['height'] - frame['height']) <= epsilon):
                vertical.append(rule['x'])
            if (rule['height'] <= epsilon and top < rule['y'] < bottom
                    and abs(rule['x'] - left) <= epsilon
                    and abs(rule['width'] - frame['width']) <= epsilon):
                horizontal.append(rule['y'])
        if len(vertical) != len(columns) - 1 or len(horizontal) != len(rows):
            continue
        # Every divider must actually meet both drawn frame sides, including
        # rounded frames. A closed bounding envelope alone is not a perimeter.
        if any(not any(a-epsilon <= value <= b+epsilon for a, b in frame['sides'][side])
               for values, sides in ((vertical, ('top', 'bottom')), (horizontal, ('left', 'right')))
               for value in values for side in sides):
            continue
        xs, ys = (left, *sorted(vertical), right), (top, *sorted(horizontal), bottom)
        if any(b - a <= epsilon for values in (xs, ys) for a, b in zip(values, values[1:])):
            continue
        valid = True
        for index, column in enumerate(columns):
            atom_id = f'atom:{page_id}:column:{table_id}:{column}:label'
            headers = atoms.get(atom_id, [])
            if (not headers or atom_id in incomplete
                    or any(not _inside(item, (xs[index], ys[0], xs[index + 1], ys[1]))
                           or not _inside_perimeter(item, frame['perimeter']) for item in headers)):
                valid = False
                break
        if valid:
            grids.add((xs, ys, frame['perimeter']))
    return next(iter(grids)) if len(grids) == 1 else None


def _table_identity(table, index):
    table_id = table.get("id") or f"table-{index + 1}"
    columns = [column.get("id") or f"col-{i + 1}" for i, column in enumerate(table["columns"])]
    rows = [{**row, "id": row.get("id") or f"row-{i + 1}"} for i, row in enumerate(table["rows"])]
    return table_id, columns, rows


def check_native_table_content(page, table_id, cells):
    """Reuse the native reader's cell membership; content supplies the text truth."""
    positions = defaultdict(set)
    for position, cell in cells.items():
        for member in cell['members']:
            if member.get('atom_id'):
                positions[member['atom_id']].add(position)
    page_id = page['page_id']
    findings = []
    for index, table in enumerate(page['customer_visible'].get('body_blocks', [])):
        if table['type'] != 'table' or (table.get('id') or f'table-{index + 1}') != table_id:
            continue
        _, columns, rows = _table_identity(table, index)
        expected = [(f'atom:{page_id}:column:{table_id}:{column}:label', None, column, 0, c,
                     table['columns'][c].get('label') or '') for c, column in enumerate(columns)]
        for r, row in enumerate(rows, 1):
            for cell in row['cells']:
                column = cell['column_id']
                expected.append((f"atom:{page_id}:cell:{table_id}:{row['id']}:{column}:display_text",
                                 row['id'], column, r, columns.index(column), cell.get('display_text') or ''))
        for atom, row_id, column, r, c, text in expected:
            location = {'page_id': page_id, 'table_id': table_id, 'row_id': row_id,
                        'column_id': column, 'atom_id': atom, 'row': r, 'column': c}
            if not text and (r, c) in cells and not cells[r, c]['text'].strip():
                continue
            if not positions[atom] or (r, c) not in cells:
                findings.append({**location, 'code': 'unverifiable_table_ownership'})
            elif positions[atom] != {(r, c)}:
                findings.append({**location, 'code': 'table_cell_ownership_mismatch'})
            elif ''.join(text.split()) != ''.join(cells[r, c]['text'].split()):
                findings.append({**location, 'code': 'table_cell_text_mismatch',
                                 'expected': text, 'actual': cells[r, c]['text']})
    return findings


def check_native_relations(root, source, page):
    parents = {child: parent for parent in root.iter() for child in parent}
    shapes = defaultdict(list)
    for native in root.findall(".//p:sp", NS):
        identity = native.find("p:nvSpPr/p:cNvPr", NS)
        if identity is not None:
            shapes[identity.get("name")].append(native)
    originals = defaultdict(list)
    for original in source['shapes']:
        originals[original.get('atom_id') or original['id']].append(original)
    atoms = {}
    nodes = {}
    texts = []
    records = []
    incomplete = set()
    for name, group in originals.items():
        carriers = shapes.get(name, [])
        if len(carriers) != len(group):
            incomplete.add(name)
        # Both emitters preserve source order. Match occurrences, never reuse
        # the last same-named shape for every line of a multiline atom. Keep
        # extra native occurrences too; count/geometry gaps remain unverified.
        for index, native in enumerate(carriers):
            original = group[min(index, len(group) - 1)]
            geometry = _geometry(native)
            if geometry is None:
                incomplete.add(name)
                continue
            identity = native.find('p:nvSpPr/p:cNvPr', NS)
            record = {**geometry, 'element': original['id'], 'native_shape_id': identity.get('id'),
                      'node_ref': original.get('node_ref'), 'kind': original['kind'],
                      'table_id': original.get('table_id'), 'table_frame': original.get('table_frame')}
            ancestor = parents.get(native)
            grouped = False
            while ancestor is not None:
                grouped |= ((ancestor.tag == '{' + NS['p'] + '}grpSp' and not _identity_group(ancestor))
                            or (ancestor.tag == '{' + NS['p'] + '}spTree'
                                and ancestor.find('p:grpSpPr/a:xfrm', NS) is not None))
                ancestor = parents.get(ancestor)
            if grouped:
                incomplete.add(name)  # local xfrm lacks the ancestor transform
            elif original['kind'] == 'line' or original.get('table_frame'):
                record['grid_geometry'] = _native_grid_shape(native, frame=bool(original.get('table_frame')))
            records.append(record)
            if original['kind'] == 'text':
                record['text'] = ''.join(item.text or '' for item in native.findall('.//a:t', NS))
                texts.append(record)
            if original.get('atom_id'):
                atoms.setdefault(original['atom_id'], []).append(record)
            if original.get('node_ref'):
                nodes.setdefault(original['node_ref'], []).append(record)
    findings = []
    page_id = page["page_id"]
    from .atoms import visible_atoms
    for atom in visible_atoms(page):
        if atom["atom_id"] not in atoms and atom.get("text"):
            matching = [record for record in texts if record["text"] == atom["text"]]
            if len(matching) == 1:
                atoms[atom["atom_id"]] = matching
    for table_index, table in enumerate(page["customer_visible"].get("body_blocks", [])):
        if table["type"] != "table" or not table.get("columns") or not table.get("rows"):
            continue
        table_id, columns, rows = _table_identity(table, table_index)
        declared_grid = any(item.get('table_id') == table_id and item.get('table_frame')
                            for item in source['shapes'])
        grid = _table_grid(records, table_id, columns, rows, atoms, page_id, incomplete) if declared_grid else None
        header_x = {}
        for column_id in columns:
            carriers = atoms.get(f"atom:{page_id}:column:{table_id}:{column_id}:label", [])
            if carriers:
                header_x[column_id] = min(item["x"] for item in carriers)
        row_y = {}
        key_column = columns[0]
        for row in rows:
            carriers = atoms.get(f"atom:{page_id}:cell:{table_id}:{row['id']}:{key_column}:display_text", [])
            if carriers:
                row_y[row["id"]] = min(item["y"] for item in carriers)
        gaps_x = [abs(first - second) for index, first in enumerate(header_x.values())
                  for second in list(header_x.values())[index + 1:] if abs(first - second) > 1]
        gaps_y = [abs(first - second) for index, first in enumerate(row_y.values())
                  for second in list(row_y.values())[index + 1:] if abs(first - second) > 1]
        tolerance_x = min(gaps_x) / 2 if gaps_x else float("inf")
        tolerance_y = min(gaps_y) / 2 if gaps_y else float("inf")
        for row_index, row in enumerate(rows):
            for cell in row["cells"]:
                column_id = cell["column_id"]
                atom_id = f"atom:{page_id}:cell:{table_id}:{row['id']}:{column_id}:display_text"
                carriers = atoms.get(atom_id, [])
                if (not carriers or atom_id in incomplete
                        or (declared_grid and grid is None)):
                    findings.append({"page_id": page_id, "code": "unverifiable_table_ownership",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "readback_layer": "native_pptx",
                                     "expected_carrier_count": len(originals.get(atom_id, [])),
                                     "actual_carrier_count": len(shapes.get(atom_id, [])),
                                     "native_shape_ids": [sp.find('p:nvSpPr/p:cNvPr', NS).get('id')
                                                          for sp in shapes.get(atom_id, [])],
                                     "native_carriers": [{key: item[key] for key in
                                         ('native_shape_id', 'element', 'x', 'y', 'width', 'height')}
                                         for item in carriers],
                                     "detail": 'missing/extra native carriers or insufficient table grid geometry'})
                    continue
                x, y = min(item["x"] for item in carriers), min(item["y"] for item in carriers)
                if grid is not None:
                    xs, ys, perimeter = grid
                    column_index = columns.index(column_id)
                    bounds = (xs[column_index], ys[row_index + 1], xs[column_index + 1], ys[row_index + 2])
                    mismatch = any(not _inside(item, bounds) or not _inside_perimeter(item, perimeter)
                                   for item in carriers)
                else:
                    bounds = None
                    mismatch = any(abs(item['x'] - header_x.get(column_id, item['x'])) > tolerance_x
                                   or abs(item['y'] - row_y.get(row['id'], item['y'])) > tolerance_y
                                   for item in carriers)
                if column_id not in header_x or row["id"] not in row_y:
                    findings.append({"page_id": page_id, "code": "unverifiable_table_ownership",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "readback_layer": "native_pptx"})
                elif mismatch:
                    findings.append({"page_id": page_id, "code": "table_cell_ownership_mismatch",
                                     "atom_id": atom_id, "table_id": table_id,
                                     "row_id": row["id"], "column_id": column_id,
                                     "svg_elements": [item["element"] for item in carriers],
                                     "readback_layer": "native_pptx", "position": [x, y],
                                     "cell_bounds": bounds,
                                     **({"native_frame_perimeter": perimeter} if grid is not None else {}),
                                     "native_carriers": [{key: item[key] for key in
                                         ('native_shape_id', 'element', 'x', 'y', 'width', 'height')}
                                         for item in carriers],
                                     "expected_column_x": header_x[column_id], "expected_row_y": row_y[row["id"]]})
    centers = {}
    for node_id, carriers in nodes.items():
        # A declared native node container anchors geometry; text-only nodes
        # use their label, never a stray responsibility to widen ownership.
        containers = [item for item in carriers if item["kind"] != "text"]
        selected = max(containers, key=lambda item: item["width"] * item["height"]) if containers else None
        if selected is not None:
            centers[node_id] = (selected["cx"], selected["cy"])
    for node in page.get("visual_spec", {}).get("nodes", []):
        node_id = node["node_id"]
        if node_id not in centers:
            label = atoms.get(node.get("label_ref"), [])
            if label:
                centers[node_id] = (label[0]["cx"], label[0]["cy"])
    for node in page.get("visual_spec", {}).get("nodes", []):
        node_id = node["node_id"]
        for atom_id in [node.get("label_ref"), *(node.get("responsibility_refs") or [])]:
            for carrier in atoms.get(atom_id, []):
                assigned = carrier["node_ref"]
                wrong_label = assigned is not None and assigned != node_id
                point = (carrier["cx"], carrier["cy"])
                own = centers.get(node_id)
                nearest = min(centers, key=lambda key: math.dist(point, centers[key])) if centers else None
                wrong_geometry = (own is not None and nearest is not None and nearest != node_id
                                  and math.dist(point, centers[nearest]) + 8 < math.dist(point, own))
                if wrong_label or wrong_geometry:
                    findings.append({"page_id": page_id, "code": "node_atom_ownership_mismatch",
                                     "atom_id": atom_id, "node_id": node_id,
                                     "actual_node_id": assigned if wrong_label else nearest,
                                     "svg_elements": [carrier["element"]], "readback_layer": "native_pptx"})
    return findings


def _identity_group(group):
    transform = group.find('p:grpSpPr/a:xfrm', NS)
    if transform is None or transform.get('rot', '0') != '0':
        return False
    if any(transform.get(key, '0') not in ('0', 'false') for key in ('flipH', 'flipV')):
        return False
    off, child_off = transform.find('a:off', NS), transform.find('a:chOff', NS)
    ext, child_ext = transform.find('a:ext', NS), transform.find('a:chExt', NS)
    return (off is not None and child_off is not None and ext is not None and child_ext is not None
            and off.attrib == child_off.attrib and ext.attrib == child_ext.attrib)
