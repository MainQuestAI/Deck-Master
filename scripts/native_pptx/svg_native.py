"""Shared, deterministic SVG semantic normalization for high-density decks.

The validator and the DrawingML compiler both consume this module.  Keeping
path parsing, inherited paint, local ``use`` expansion, and transforms here
prevents the two stages from silently supporting different SVG subsets.
"""

from __future__ import annotations

import math
import re
from typing import Any
from xml.etree import ElementTree

from .contracts import ContractError
from .svg_paint import SvgPaintError, parse_node_paint, parse_svg_paint


class SvgNativeError(ContractError):
    def __init__(
        self,
        message: str,
        *,
        element_id: str = "",
        visual_id: str = "",
        property_name: str = "",
        code: str = "HD_SVG_NATIVE_INVALID",
    ) -> None:
        self.element_id = element_id
        self.visual_id = visual_id
        self.property_name = property_name
        self.code = code
        super().__init__(message)


def svg_recovery_command(page_id: str = "") -> str:
    return f"deck-master build retry --run-dir <run_dir> --profile high-density --stage svg --page-id {page_id or '<page_id>'}"


def format_svg_native_error(error: SvgNativeError, *, page_id: str = "") -> str:
    return (
        f"visual_id={error.visual_id or '<none>'} element_id={error.element_id or '<none>'} "
        f"property={error.property_name or '<none>'} code={error.code} reason={error}; recovery: {svg_recovery_command(page_id)}"
    )


_TOKEN_RE = re.compile(r"([AaCcHhLlMmQqSsTtVvZz])|([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)")
_TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
_COMMAND_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
_LEAF_TAGS = {"text", "rect", "circle", "ellipse", "line", "path", "polygon", "polyline", "image"}
_STRUCTURAL_TAGS = {"svg", "g", "defs", "symbol", "use", "title", "desc", "metadata"}
_STYLE_ATTRS = {
    "fill",
    "stroke",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-dasharray",
    "stroke-dashoffset",
    "fill-rule",
    "filter",
    "color",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
}
_DEFAULT_STYLE = {
    "fill": "#000000",
    "stroke": "none",
    "opacity": 1.0,
    "fill-opacity": 1.0,
    "stroke-opacity": 1.0,
    "stroke-width": 1.0,
    "stroke-linecap": "butt",
    "stroke-linejoin": "miter",
    "fill-rule": "nonzero",
    "filter": "none",
    "color": "#000000",
    "font-family": "Arial",
    "font-size": "16px",
    "font-weight": "400",
    "font-style": "normal",
}
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _tag(node: Any) -> str:
    return str(node.tag).split("}")[-1]


def _finite(value: Any, *, label: str, element_id: str, visual_id: str = "") -> float:
    try:
        parsed = float(str(value).strip().removesuffix("px"))
    except (TypeError, ValueError) as exc:
        raise SvgNativeError(f"SVG {label} is invalid on {element_id}", element_id=element_id, visual_id=visual_id, property_name=label) from exc
    if not math.isfinite(parsed):
        raise SvgNativeError(f"SVG {label} is not finite on {element_id}", element_id=element_id, visual_id=visual_id, property_name=label)
    return parsed


def _matrix_product(first: tuple[float, float, float, float, float, float], second: tuple[float, float, float, float, float, float]) -> tuple[float, float, float, float, float, float]:
    a, b, c, d, e, f = first
    g, h, i, j, k, l = second
    return (a * g + c * h, b * g + d * h, a * i + c * j, b * i + d * j, a * k + c * l + e, b * k + d * l + f)


def _apply_matrix(matrix: tuple[float, float, float, float, float, float], point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def _translation(x: float, y: float) -> tuple[float, float, float, float, float, float]:
    return (1.0, 0.0, 0.0, 1.0, x, y)


def _rotation(degrees: float) -> tuple[float, float, float, float, float, float]:
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    return (cosine, sine, -sine, cosine, 0.0, 0.0)


def _parse_transform(raw: str | None, *, element_id: str, visual_id: str = "") -> tuple[float, float, float, float, float, float]:
    text = str(raw or "").strip()
    if not text:
        return _IDENTITY
    matrix = _IDENTITY
    cursor = 0
    for match in _TRANSFORM_RE.finditer(text):
        if text[cursor : match.start()].strip(" ,\t\r\n"):
            raise SvgNativeError(f"unsupported SVG transform syntax on {element_id}", element_id=element_id, visual_id=visual_id, property_name="transform")
        cursor = match.end()
        name = match.group(1).lower()
        values = [float(token) for token in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", match.group(2))]
        if not all(math.isfinite(value) for value in values):
            raise SvgNativeError(f"SVG transform has a non-finite value on {element_id}", element_id=element_id, visual_id=visual_id, property_name="transform")
        if name == "translate" and len(values) in {1, 2}:
            local = _translation(values[0], values[1] if len(values) == 2 else 0.0)
        elif name == "scale" and len(values) in {1, 2}:
            local = (values[0], 0.0, 0.0, values[1] if len(values) == 2 else values[0], 0.0, 0.0)
        elif name == "rotate" and len(values) in {1, 3}:
            local = _rotation(values[0])
            if len(values) == 3:
                local = _matrix_product(_translation(values[1], values[2]), _matrix_product(local, _translation(-values[1], -values[2])))
        elif name == "matrix" and len(values) == 6:
            local = tuple(values)  # type: ignore[assignment]
            a, b, c, d, _, _ = local
            # A shear changes a glyph/icon's topology in a way the native
            # DrawingML subset cannot reproduce reliably.
            if abs(a * c + b * d) > 1e-6:
                raise SvgNativeError(f"matrix shear is unsupported on {element_id}", element_id=element_id, visual_id=visual_id, property_name="transform", code="HD_SVG_UNSUPPORTED_TRANSFORM")
        else:
            raise SvgNativeError(f"unsupported SVG transform {name} on {element_id}", element_id=element_id, visual_id=visual_id, property_name="transform", code="HD_SVG_UNSUPPORTED_TRANSFORM")
        matrix = _matrix_product(matrix, local)
    if text[cursor:].strip(" ,\t\r\n"):
        raise SvgNativeError(f"unsupported SVG transform syntax on {element_id}", element_id=element_id, visual_id=visual_id, property_name="transform")
    return matrix


def _tokenize_path(path_data: str, *, element_id: str, visual_id: str = "") -> list[str]:
    matches = list(_TOKEN_RE.finditer(path_data))
    cursor = 0
    for match in matches:
        if path_data[cursor : match.start()].strip(" ,\t\r\n"):
            raise SvgNativeError(f"SVG path contains unsupported syntax on {element_id}", element_id=element_id, visual_id=visual_id, property_name="d")
        cursor = match.end()
    if path_data[cursor:].strip(" ,\t\r\n") or not matches:
        raise SvgNativeError(f"SVG path is empty or malformed on {element_id}", element_id=element_id, visual_id=visual_id, property_name="d")
    return [match.group(1) or match.group(2) for match in matches]


def _arc_cubics(start: tuple[float, float], rx: float, ry: float, rotation: float, large_arc: int, sweep: int, end: tuple[float, float]) -> list[dict[str, Any]]:
    if abs(start[0] - end[0]) < 1e-9 and abs(start[1] - end[1]) < 1e-9:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-9 or ry < 1e-9:
        return [{"op": "L", "x": end[0], "y": end[1]}]
    phi = math.radians(rotation % 360.0)
    cosine, sine = math.cos(phi), math.sin(phi)
    dx = (start[0] - end[0]) / 2.0
    dy = (start[1] - end[1]) / 2.0
    x1p = cosine * dx + sine * dy
    y1p = -sine * dx + cosine * dy
    radius_scale = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if radius_scale > 1:
        scale = math.sqrt(radius_scale)
        rx *= scale
        ry *= scale
    numerator = max(0.0, (rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p))
    denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = 0.0 if denominator == 0 else math.sqrt(numerator / denominator)
    if bool(large_arc) == bool(sweep):
        factor = -factor
    cxp = factor * (rx * y1p / ry)
    cyp = factor * (-ry * x1p / rx)
    cx = cosine * cxp - sine * cyp + (start[0] + end[0]) / 2.0
    cy = sine * cxp + cosine * cyp + (start[1] + end[1]) / 2.0

    def unit_angle(u: tuple[float, float], v: tuple[float, float]) -> float:
        dot = u[0] * v[0] + u[1] * v[1]
        cross = u[0] * v[1] - u[1] * v[0]
        return math.atan2(cross, dot)

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    start_angle = unit_angle((1.0, 0.0), (ux, uy))
    delta_angle = unit_angle((ux, uy), (vx, vy))
    if not sweep and delta_angle > 0:
        delta_angle -= 2 * math.pi
    elif sweep and delta_angle < 0:
        delta_angle += 2 * math.pi
    count = max(1, int(math.ceil(abs(delta_angle) / (math.pi / 2))))
    step = delta_angle / count
    result: list[dict[str, Any]] = []

    def ellipse_point(angle: float) -> tuple[float, float]:
        return (cx + rx * cosine * math.cos(angle) - ry * sine * math.sin(angle), cy + rx * sine * math.cos(angle) + ry * cosine * math.sin(angle))

    for index in range(count):
        angle_1 = start_angle + index * step
        angle_2 = angle_1 + step
        alpha = 4.0 / 3.0 * math.tan((angle_2 - angle_1) / 4.0)
        p1 = ellipse_point(angle_1)
        p2 = ellipse_point(angle_2)
        c1 = (p1[0] - alpha * (rx * cosine * math.sin(angle_1) + ry * sine * math.cos(angle_1)), p1[1] - alpha * (rx * sine * math.sin(angle_1) - ry * cosine * math.cos(angle_1)))
        c2 = (p2[0] + alpha * (rx * cosine * math.sin(angle_2) + ry * sine * math.cos(angle_2)), p2[1] + alpha * (rx * sine * math.sin(angle_2) - ry * cosine * math.cos(angle_2)))
        result.append({"op": "C", "x1": c1[0], "y1": c1[1], "x2": c2[0], "y2": c2[1], "x": p2[0], "y": p2[1]})
    return result


def _parse_path(path_data: str, *, element_id: str, visual_id: str = "") -> list[dict[str, Any]]:
    tokens = _tokenize_path(path_data, element_id=element_id, visual_id=visual_id)
    commands: list[dict[str, Any]] = []
    current = (0.0, 0.0)
    subpath_start = current
    command = ""
    index = 0
    previous_cubic_control: tuple[float, float] | None = None
    previous_quadratic_control: tuple[float, float] | None = None

    def number() -> float:
        nonlocal index
        if index >= len(tokens) or re.fullmatch(r"[A-Za-z]", tokens[index]):
            raise SvgNativeError(f"SVG path command has incomplete coordinates on {element_id}", element_id=element_id, visual_id=visual_id, property_name="d")
        value = _finite(tokens[index], label="path coordinate", element_id=element_id, visual_id=visual_id)
        index += 1
        return value

    def point(x: float, y: float, relative: bool) -> tuple[float, float]:
        return (x + current[0], y + current[1]) if relative else (x, y)

    while index < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[index]):
            command = tokens[index]
            index += 1
            if command in "Zz":
                commands.append({"op": "Z"})
                current = subpath_start
                previous_cubic_control = previous_quadratic_control = None
                command = ""
                continue
        if not command or command.upper() not in _COMMAND_ARGS:
            raise SvgNativeError(f"unsupported SVG path command on {element_id}: {command}", element_id=element_id, visual_id=visual_id, property_name="d", code="HD_SVG_UNSUPPORTED_PATH_COMMAND")
        relative = command.islower()
        upper = command.upper()
        arity = _COMMAND_ARGS[upper]
        if index + arity > len(tokens) or any(re.fullmatch(r"[A-Za-z]", token) for token in tokens[index : index + arity]):
            raise SvgNativeError(f"SVG path command has incomplete coordinates on {element_id}", element_id=element_id, visual_id=visual_id, property_name="d")
        if upper == "M":
            target = point(number(), number(), relative)
            commands.append({"op": "M", "x": target[0], "y": target[1]})
            current = subpath_start = target
            command = "l" if relative else "L"
            previous_cubic_control = previous_quadratic_control = None
        elif upper == "L":
            target = point(number(), number(), relative)
            commands.append({"op": "L", "x": target[0], "y": target[1]})
            current = target
            previous_cubic_control = previous_quadratic_control = None
        elif upper == "H":
            x = number() + current[0] if relative else number()
            current = (x, current[1])
            commands.append({"op": "L", "x": current[0], "y": current[1]})
            previous_cubic_control = previous_quadratic_control = None
        elif upper == "V":
            y = number() + current[1] if relative else number()
            current = (current[0], y)
            commands.append({"op": "L", "x": current[0], "y": current[1]})
            previous_cubic_control = previous_quadratic_control = None
        elif upper == "C":
            c1 = point(number(), number(), relative)
            c2 = point(number(), number(), relative)
            target = point(number(), number(), relative)
            commands.append({"op": "C", "x1": c1[0], "y1": c1[1], "x2": c2[0], "y2": c2[1], "x": target[0], "y": target[1]})
            current = target
            previous_cubic_control, previous_quadratic_control = c2, None
        elif upper == "S":
            c1 = (2 * current[0] - previous_cubic_control[0], 2 * current[1] - previous_cubic_control[1]) if previous_cubic_control else current
            c2 = point(number(), number(), relative)
            target = point(number(), number(), relative)
            commands.append({"op": "C", "x1": c1[0], "y1": c1[1], "x2": c2[0], "y2": c2[1], "x": target[0], "y": target[1]})
            current = target
            previous_cubic_control, previous_quadratic_control = c2, None
        elif upper == "Q":
            control = point(number(), number(), relative)
            target = point(number(), number(), relative)
            c1 = (current[0] + 2.0 / 3.0 * (control[0] - current[0]), current[1] + 2.0 / 3.0 * (control[1] - current[1]))
            c2 = (target[0] + 2.0 / 3.0 * (control[0] - target[0]), target[1] + 2.0 / 3.0 * (control[1] - target[1]))
            commands.append({"op": "C", "x1": c1[0], "y1": c1[1], "x2": c2[0], "y2": c2[1], "x": target[0], "y": target[1]})
            current = target
            previous_quadratic_control, previous_cubic_control = control, None
        elif upper == "T":
            control = (2 * current[0] - previous_quadratic_control[0], 2 * current[1] - previous_quadratic_control[1]) if previous_quadratic_control else current
            target = point(number(), number(), relative)
            c1 = (current[0] + 2.0 / 3.0 * (control[0] - current[0]), current[1] + 2.0 / 3.0 * (control[1] - current[1]))
            c2 = (target[0] + 2.0 / 3.0 * (control[0] - target[0]), target[1] + 2.0 / 3.0 * (control[1] - target[1]))
            commands.append({"op": "C", "x1": c1[0], "y1": c1[1], "x2": c2[0], "y2": c2[1], "x": target[0], "y": target[1]})
            current = target
            previous_quadratic_control, previous_cubic_control = control, None
        elif upper == "A":
            rx, ry, rotation = number(), number(), number()
            large_arc, sweep = int(number()), int(number())
            if large_arc not in {0, 1} or sweep not in {0, 1}:
                raise SvgNativeError(f"SVG arc flags must be 0 or 1 on {element_id}", element_id=element_id, visual_id=visual_id, property_name="d")
            target = point(number(), number(), relative)
            arc_segments = _arc_cubics(current, rx, ry, rotation, large_arc, sweep, target)
            commands.extend(arc_segments)
            current = target
            previous_cubic_control = previous_quadratic_control = None
    if not any(item.get("op") == "M" for item in commands):
        raise SvgNativeError(f"SVG path must start with a move command on {element_id}", element_id=element_id, visual_id=visual_id, property_name="d")
    return commands


def _subpaths(commands: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    paths: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for command in commands:
        if command.get("op") == "M" and current:
            paths.append(current)
            current = []
        current.append(command)
    if current:
        paths.append(current)
    return paths


def _sample_subpath(path: list[dict[str, Any]], steps: int = 16) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    for command in path:
        op = command["op"]
        if op == "M":
            current = (float(command["x"]), float(command["y"]))
            points.append(current)
        elif op == "L":
            current = (float(command["x"]), float(command["y"]))
            points.append(current)
        elif op == "C":
            origin = current
            target = (float(command["x"]), float(command["y"]))
            for index in range(1, steps + 1):
                t = index / steps
                inv = 1 - t
                points.append((inv**3 * origin[0] + 3 * inv**2 * t * float(command["x1"]) + 3 * inv * t**2 * float(command["x2"]) + t**3 * target[0], inv**3 * origin[1] + 3 * inv**2 * t * float(command["y1"]) + 3 * inv * t**2 * float(command["y2"]) + t**3 * target[1]))
            current = target
    return points


def _path_bbox(commands: list[dict[str, Any]]) -> dict[str, float]:
    values: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    for command in commands:
        op = command["op"]
        if op in {"M", "L"}:
            current = (float(command["x"]), float(command["y"]))
            values.append(current)
        elif op == "C":
            origin = current
            end = (float(command["x"]), float(command["y"]))
            values.extend([origin, end])
            for coordinate in (0, 1):
                axis = "x" if coordinate == 0 else "y"
                p0, p1, p2, p3 = origin[coordinate], float(command[f"{axis}1"]), float(command[f"{axis}2"]), end[coordinate]
                # Solve the derivative of the cubic Bezier polynomial. The
                # endpoint-only shortcut misses symmetric arches whose two
                # control points share a coordinate.
                a = -p0 + 3 * p1 - 3 * p2 + p3
                b = 2 * (p0 - 2 * p1 + p2)
                c = p1 - p0
                roots: list[float] = []
                if abs(a) < 1e-12:
                    if abs(b) >= 1e-12:
                        roots.append(-c / b)
                else:
                    discriminant = b * b - 4 * a * c
                    if discriminant >= 0:
                        square_root = math.sqrt(discriminant)
                        roots.extend(((-b + square_root) / (2 * a), (-b - square_root) / (2 * a)))
                for root in roots:
                    if 0 < root < 1:
                        inv = 1 - root
                        values.append((inv**3 * origin[0] + 3 * inv**2 * root * float(command["x1"]) + 3 * inv * root**2 * float(command["x2"]) + root**3 * end[0], inv**3 * origin[1] + 3 * inv**2 * root * float(command["y1"]) + 3 * inv * root**2 * float(command["y2"]) + root**3 * end[1]))
        elif op == "Z":
            continue
    if not values:
        raise SvgNativeError("SVG path has no drawable geometry")
    xs, ys = zip(*values)
    return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def _bbox(points: list[tuple[float, float]]) -> dict[str, float]:
    if not points:
        raise SvgNativeError("SVG geometry has no drawable points")
    xs, ys = zip(*points)
    return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def _bbox_contains(outer: dict[str, float], inner: dict[str, float]) -> bool:
    return outer["x"] <= inner["x"] + 1e-6 and outer["y"] <= inner["y"] + 1e-6 and outer["x"] + outer["w"] >= inner["x"] + inner["w"] - 1e-6 and outer["y"] + outer["h"] >= inner["y"] + inner["h"] - 1e-6


def _signed_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return 0.5 * sum(first[0] * second[1] - second[0] * first[1] for first, second in zip(points, points[1:] + points[:1]))


def _segments_intersect(first: tuple[tuple[float, float], tuple[float, float]], second: tuple[tuple[float, float], tuple[float, float]]) -> bool:
    def orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> int:
        value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(value) < 1e-8:
            return 0
        return 1 if value > 0 else -1

    def on_segment(a: tuple[float, float], b: tuple[float, float], point: tuple[float, float]) -> bool:
        return min(a[0], b[0]) - 1e-8 <= point[0] <= max(a[0], b[0]) + 1e-8 and min(a[1], b[1]) - 1e-8 <= point[1] <= max(a[1], b[1]) + 1e-8

    a, b = first
    c, d = second
    first_orientation = orientation(a, b, c)
    second_orientation = orientation(a, b, d)
    third_orientation = orientation(c, d, a)
    fourth_orientation = orientation(c, d, b)
    if first_orientation != second_orientation and third_orientation != fourth_orientation:
        return True
    return (first_orientation == 0 and on_segment(a, b, c)) or (second_orientation == 0 and on_segment(a, b, d)) or (third_orientation == 0 and on_segment(c, d, a)) or (fourth_orientation == 0 and on_segment(c, d, b))


def _self_intersects(points: list[tuple[float, float]], *, closed: bool) -> bool:
    if len(points) < 4:
        return False
    segments = list(zip(points, points[1:]))
    if closed:
        segments.append((points[-1], points[0]))
    for first_index, first in enumerate(segments):
        for second_index in range(first_index + 1, len(segments)):
            if second_index - first_index == 1:
                continue
            if closed and first_index == 0 and second_index == len(segments) - 1:
                continue
            if _segments_intersect(first, segments[second_index]):
                return True
    return False


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        if _segments_intersect((first, second), (point, point)):
            return True
        if (first[1] > y) != (second[1] > y):
            crossing_x = (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1]) + first[0]
            if x < crossing_x:
                inside = not inside
    return inside


def _polygon_contains(outer: list[tuple[float, float]], inner: list[tuple[float, float]]) -> bool:
    return bool(inner) and all(_point_in_polygon(point, outer) for point in inner)


def _reverse_subpath(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path or path[0].get("op") != "M":
        raise SvgNativeError("SVG subpath cannot be reversed safely")
    segments: list[tuple[tuple[float, float], dict[str, Any], tuple[float, float]]] = []
    current = (float(path[0]["x"]), float(path[0]["y"]))
    closed = False
    for command in path[1:]:
        if command["op"] == "Z":
            closed = True
            continue
        target = (float(command["x"]), float(command["y"]))
        segments.append((current, command, target))
        current = target
    if not segments:
        return path
    result: list[dict[str, Any]] = [{"op": "M", "x": segments[-1][2][0], "y": segments[-1][2][1]}]
    for origin, command, target in reversed(segments):
        if command["op"] == "C":
            result.append({"op": "C", "x1": float(command["x2"]), "y1": float(command["y2"]), "x2": float(command["x1"]), "y2": float(command["y1"]), "x": origin[0], "y": origin[1]})
        else:
            result.append({"op": "L", "x": origin[0], "y": origin[1]})
    if closed:
        result.append({"op": "Z"})
    return result


def _normalize_evenodd(commands: list[dict[str, Any]], *, element_id: str, visual_id: str) -> tuple[list[dict[str, Any]], str]:
    paths = _subpaths(commands)
    samples = [_sample_subpath(path) for path in paths]
    if any(not path or path[-1].get("op") != "Z" for path in paths):
        raise SvgNativeError(f"evenodd topology requires closed subpaths on {element_id}", element_id=element_id, visual_id=visual_id, property_name="fill-rule", code="HD_SVG_UNRESOLVED_ICON")
    if any(_self_intersects(points, closed=True) for points in samples):
        raise SvgNativeError(f"evenodd topology self-intersects on {element_id}", element_id=element_id, visual_id=visual_id, property_name="fill-rule", code="HD_SVG_UNRESOLVED_ICON")
    if len(paths) < 2:
        return commands, "nonzero"
    boxes = [_bbox(points) for points in samples]
    contains: list[list[bool]] = [[False] * len(paths) for _ in paths]
    for first_index, first in enumerate(boxes):
        for second_index, second in enumerate(boxes):
            if first_index >= second_index:
                continue
            overlap = not (first["x"] + first["w"] < second["x"] or second["x"] + second["w"] < first["x"] or first["y"] + first["h"] < second["y"] or second["y"] + second["h"] < first["y"])
            first_contains_second = _bbox_contains(first, second) and _polygon_contains(samples[first_index], samples[second_index])
            second_contains_first = _bbox_contains(second, first) and _polygon_contains(samples[second_index], samples[first_index])
            if first_contains_second and second_contains_first:
                raise SvgNativeError(f"evenodd topology has duplicate contours on {element_id}", element_id=element_id, visual_id=visual_id, property_name="fill-rule", code="HD_SVG_UNRESOLVED_ICON")
            if overlap and not first_contains_second and not second_contains_first:
                raise SvgNativeError(f"evenodd topology is ambiguous on {element_id}", element_id=element_id, visual_id=visual_id, property_name="fill-rule", code="HD_SVG_UNRESOLVED_ICON")
            contains[first_index][second_index] = first_contains_second
            contains[second_index][first_index] = second_contains_first
    normalized: list[dict[str, Any]] = []
    for index, path in enumerate(paths):
        depth = sum(1 for other_index in range(len(paths)) if index != other_index and contains[other_index][index])
        area = _signed_area(samples[index])
        if abs(area) < 1e-8:
            raise SvgNativeError(f"evenodd topology is unresolved on {element_id}", element_id=element_id, visual_id=visual_id, property_name="fill-rule", code="HD_SVG_UNRESOLVED_ICON")
        desired_positive = depth % 2 == 0
        normalized.extend(_reverse_subpath(path) if (area > 0) != desired_positive else path)
    return normalized, "nonzero"


def _transform_commands(commands: list[dict[str, Any]], matrix: tuple[float, float, float, float, float, float]) -> list[dict[str, Any]]:
    if matrix == _IDENTITY:
        return [dict(command) for command in commands]
    result: list[dict[str, Any]] = []
    for command in commands:
        current = dict(command)
        if command["op"] in {"M", "L", "C"}:
            target = _apply_matrix(matrix, (float(command["x"]), float(command["y"])))
            current.update({"x": target[0], "y": target[1]})
        if command["op"] == "C":
            control_1 = _apply_matrix(matrix, (float(command["x1"]), float(command["y1"])))
            control_2 = _apply_matrix(matrix, (float(command["x2"]), float(command["y2"])))
            current.update({"x1": control_1[0], "y1": control_1[1], "x2": control_2[0], "y2": control_2[1]})
        result.append(current)
    return result


def _computed_style(node: Any, parent: dict[str, Any]) -> dict[str, Any]:
    style = dict(parent)
    for key in _STYLE_ATTRS:
        if key == "opacity":
            continue
        if node.get(key) is not None:
            style[key] = str(node.get(key))
    parent_opacity = float(parent.get("opacity", 1.0))
    if node.get("opacity") is not None:
        child_opacity = _finite(node.get("opacity"), label="opacity", element_id=str(node.get("id") or _tag(node)))
        style["opacity"] = parent_opacity * child_opacity
    else:
        style["opacity"] = parent_opacity
    if style.get("fill") == "currentColor":
        style["fill"] = style.get("color", "#000000")
    if style.get("stroke") == "currentColor":
        style["stroke"] = style.get("color", "#000000")
    for key in ("opacity", "fill-opacity", "stroke-opacity", "stroke-width", "font-size"):
        style[key] = _finite(style.get(key), label=key, element_id=str(node.get("id") or _tag(node))) if key not in {"font-size"} or style.get(key) is not None else style[key]
    dash = str(style.get("stroke-dasharray") or "none")
    if dash != "none":
        values = [_finite(v, label="stroke-dasharray", element_id=str(node.get("id") or _tag(node))) for v in re.split(r"[\s,]+", dash.strip())]
        if not values or any(v < 0 for v in values):
            raise SvgNativeError("stroke-dasharray must contain non-negative lengths", property_name="stroke-dasharray")
    if _finite(style.get("stroke-dashoffset") or 0, label="stroke-dashoffset", element_id=str(node.get("id") or _tag(node))) != 0:
        raise SvgNativeError("nonzero stroke-dashoffset is unsupported", property_name="stroke-dashoffset", code="HD_SVG_UNSUPPORTED_PROPERTY")
    return style


def _paint(style: dict[str, Any], registry: dict[str, Any], *, element_id: str, visual_id: str) -> dict[str, Any]:
    synthetic = ElementTree.Element("path", {key: str(value) for key, value in style.items() if key in {"fill", "stroke", "opacity", "fill-opacity", "stroke-opacity", "filter"}})
    synthetic.set("id", element_id)
    try:
        return parse_node_paint(synthetic, registry)
    except SvgPaintError as exc:
        raise SvgNativeError(str(exc), element_id=element_id, visual_id=visual_id, code=exc.code) from exc


def _geometry(node: Any, tag: str, matrix: tuple[float, float, float, float, float, float], *, element_id: str, visual_id: str) -> tuple[str, dict[str, float], list[dict[str, Any]] | None]:
    if tag == "path":
        commands = _transform_commands(_parse_path(str(node.get("d") or ""), element_id=element_id, visual_id=visual_id), matrix)
        return "path", _path_bbox(commands), commands
    if tag in {"polygon", "polyline"}:
        values = [float(value) for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", str(node.get("points") or ""))]
        if len(values) < 4 or len(values) % 2:
            raise SvgNativeError(f"SVG {tag} points are invalid on {element_id}", element_id=element_id, visual_id=visual_id)
        points = [_apply_matrix(matrix, (values[index], values[index + 1])) for index in range(0, len(values), 2)]
        commands = [{"op": "M", "x": points[0][0], "y": points[0][1]}] + [{"op": "L", "x": point[0], "y": point[1]} for point in points[1:]]
        if tag == "polygon":
            commands.append({"op": "Z"})
        return "path", _bbox(points), commands
    if tag == "line":
        points = [_apply_matrix(matrix, (_finite(node.get(name), label=name, element_id=element_id, visual_id=visual_id), _finite(node.get(name_2), label=name_2, element_id=element_id, visual_id=visual_id))) for name, name_2 in (("x1", "y1"), ("x2", "y2"))]
        return "line", _bbox(points), None
    if tag == "rect":
        x, y = _finite(node.get("x") or 0, label="x", element_id=element_id, visual_id=visual_id), _finite(node.get("y") or 0, label="y", element_id=element_id, visual_id=visual_id)
        width, height = _finite(node.get("width"), label="width", element_id=element_id, visual_id=visual_id), _finite(node.get("height"), label="height", element_id=element_id, visual_id=visual_id)
        rx = _finite(node.get("rx") if node.get("rx") is not None else (node.get("ry") or 0), label="rx", element_id=element_id, visual_id=visual_id)
        ry = _finite(node.get("ry") if node.get("ry") is not None else (node.get("rx") or 0), label="ry", element_id=element_id, visual_id=visual_id)
        if rx < 0 or ry < 0:
            raise SvgNativeError("rect radii must be non-negative", element_id=element_id, property_name="rx/ry")
        rx, ry = min(rx, width / 2), min(ry, height / 2)
        if rx > 0 and ry > 0:
            # Explicit elliptical arcs preserve SVG radii; Office's roundRect
            # preset uses an unrelated default adjustment.
            d = (f"M {x+rx} {y} L {x+width-rx} {y} A {rx} {ry} 0 0 1 {x+width} {y+ry} "
                 f"L {x+width} {y+height-ry} A {rx} {ry} 0 0 1 {x+width-rx} {y+height} "
                 f"L {x+rx} {y+height} A {rx} {ry} 0 0 1 {x} {y+height-ry} "
                 f"L {x} {y+ry} A {rx} {ry} 0 0 1 {x+rx} {y} Z")
            commands = _transform_commands(_parse_path(d, element_id=element_id, visual_id=visual_id), matrix)
            return "path", _path_bbox(commands), commands
        points = [_apply_matrix(matrix, point) for point in ((x, y), (x + width, y), (x + width, y + height), (x, y + height))]
        if matrix != _IDENTITY:
            commands = [{"op": "M", "x": points[0][0], "y": points[0][1]}] + [{"op": "L", "x": point[0], "y": point[1]} for point in points[1:]] + [{"op": "Z"}]
            return "path", _bbox(points), commands
        return "rect", _bbox(points), None
    if tag in {"circle", "ellipse"}:
        cx, cy = _finite(node.get("cx"), label="cx", element_id=element_id, visual_id=visual_id), _finite(node.get("cy"), label="cy", element_id=element_id, visual_id=visual_id)
        rx = _finite(node.get("r"), label="r", element_id=element_id, visual_id=visual_id) if tag == "circle" else _finite(node.get("rx"), label="rx", element_id=element_id, visual_id=visual_id)
        ry = rx if tag == "circle" else _finite(node.get("ry"), label="ry", element_id=element_id, visual_id=visual_id)
        points = [_apply_matrix(matrix, (cx + rx * math.cos(index * math.pi / 2), cy + ry * math.sin(index * math.pi / 2))) for index in range(4)]
        return "ellipse", _bbox(points), None
    if tag == "image":
        x, y = _finite(node.get("x") or 0, label="x", element_id=element_id, visual_id=visual_id), _finite(node.get("y") or 0, label="y", element_id=element_id, visual_id=visual_id)
        width, height = _finite(node.get("width"), label="width", element_id=element_id, visual_id=visual_id), _finite(node.get("height"), label="height", element_id=element_id, visual_id=visual_id)
        # rx/ry describe rect/ellipse geometry, not SVG image clipping.
        points = [_apply_matrix(matrix, point) for point in ((x, y), (x + width, y), (x + width, y + height), (x, y + height))]
        return "image", _bbox(points), None
    if tag == "text":
        raw = str(node.get("data-pptx-bounds") or "")
        parts = raw.split(",")
        if len(parts) != 4:
            raise SvgNativeError(f"SVG text is missing data-pptx-bounds on {element_id}", element_id=element_id, visual_id=visual_id)
        values = [_finite(part, label="data-pptx-bounds", element_id=element_id, visual_id=visual_id) for part in parts]
        points = [_apply_matrix(matrix, (values[0], values[1])), _apply_matrix(matrix, (values[0] + values[2], values[1] + values[3]))]
        return "text", _bbox(points), None
    raise SvgNativeError(f"unsupported SVG element {tag} on {element_id}", element_id=element_id, visual_id=visual_id, code="HD_SVG_UNSUPPORTED_ELEMENT")


def parse_svg_native(root: ElementTree.Element) -> dict[str, Any]:
    """Return a normalized SVG document with leaf geometry and computed paint."""
    ids: dict[str, Any] = {}
    for node in root.iter():
        node_id = str(node.get("id") or "")
        if node_id:
            if node_id in ids:
                raise SvgNativeError(f"duplicate SVG element id: {node_id}", element_id=node_id, code="HD_SVG_DUPLICATE_ID")
            ids[node_id] = node
        if node.get("style") or node.get("class"):
            raise SvgNativeError(f"external CSS/style attributes are blocked on {node_id or _tag(node)}", element_id=node_id, code="HD_SVG_UNSUPPORTED_PROPERTY")
    try:
        registry = parse_svg_paint(root)
    except SvgPaintError as exc:
        raise SvgNativeError(str(exc), element_id=exc.element_id, code=exc.code) from exc
    symbols = {node_id: node for node_id, node in ids.items() if _tag(node) == "symbol"}
    elements: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    visiting: list[str] = []

    def visit(node: Any, parent_style: dict[str, Any], parent_matrix: tuple[float, float, float, float, float, float], inherited_group: str = "", inherited_visual: str = "", prefix: str = "") -> None:
        tag = _tag(node)
        node_id = str(node.get("id") or tag)
        local_id = f"{prefix}--{node_id}" if prefix else node_id
        style = _computed_style(node, parent_style)
        local_matrix = _parse_transform(node.get("transform"), element_id=node_id, visual_id=inherited_visual)
        matrix = _matrix_product(parent_matrix, local_matrix)
        group_id = inherited_group
        visual_id = inherited_visual
        if tag == "g":
            group_id = str(node.get("data-pptx-group-id") or node.get("data-pptx-visual-id") or inherited_group)
            visual_id = str(node.get("data-pptx-visual-id") or inherited_visual or group_id)
            if group_id:
                groups.setdefault(group_id, {"group_id": group_id, "visual_id": visual_id, "child_ids": [], "source_element_id": node_id})
        elif tag == "use":
            href = str(node.get("href") or node.get("{http://www.w3.org/1999/xlink}href") or "")
            if not href.startswith("#") or href[1:] not in symbols:
                raise SvgNativeError(f"SVG use must reference a local symbol on {node_id}", element_id=node_id, visual_id=visual_id, property_name="href", code="HD_SVG_EXTERNAL_REFERENCE")
            if href[1:] in visiting:
                raise SvgNativeError(f"SVG use cycle detected on {node_id}", element_id=node_id, visual_id=visual_id, code="HD_SVG_UNRESOLVED_ICON")
            group_id = str(node.get("data-pptx-group-id") or node.get("data-pptx-visual-id") or node_id)
            visual_id = str(node.get("data-pptx-visual-id") or group_id)
            groups.setdefault(group_id, {"group_id": group_id, "visual_id": visual_id, "child_ids": [], "source_element_id": node_id})
            use_x = _finite(node.get("x") or 0, label="use x", element_id=node_id, visual_id=visual_id)
            use_y = _finite(node.get("y") or 0, label="use y", element_id=node_id, visual_id=visual_id)
            visiting.append(href[1:])
            reference = symbols[href[1:]]
            reference_style = _computed_style(reference, style)
            reference_matrix = _matrix_product(matrix, _translation(use_x, use_y))
            try:
                viewbox_values = [
                    float(value)
                    for value in re.findall(
                        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
                        str(reference.get("viewBox") or ""),
                    )
                ]
            except ValueError as exc:
                raise SvgNativeError(
                    f"SVG symbol viewBox is invalid on {href[1:]}",
                    element_id=node_id,
                    visual_id=visual_id,
                    property_name="viewBox",
                ) from exc
            width = node.get("width")
            height = node.get("height")
            if (width is not None or height is not None) and len(viewbox_values) == 4:
                view_x, view_y, view_width, view_height = viewbox_values
                if view_width <= 0 or view_height <= 0:
                    raise SvgNativeError(
                        f"SVG symbol viewBox is invalid on {href[1:]}",
                        element_id=node_id,
                        visual_id=visual_id,
                        property_name="viewBox",
                    )
                target_width = _finite(width if width is not None else view_width, label="use width", element_id=node_id, visual_id=visual_id)
                target_height = _finite(height if height is not None else view_height, label="use height", element_id=node_id, visual_id=visual_id)
                if target_width <= 0 or target_height <= 0:
                    raise SvgNativeError(
                        f"SVG use dimensions must be positive on {node_id}",
                        element_id=node_id,
                        visual_id=visual_id,
                        property_name="width/height",
                    )
                symbol_scale = (
                    target_width / view_width,
                    0.0,
                    0.0,
                    target_height / view_height,
                    -view_x * target_width / view_width,
                    -view_y * target_height / view_height,
                )
                reference_matrix = _matrix_product(reference_matrix, symbol_scale)
            for child in list(reference):
                visit(child, reference_style, reference_matrix, group_id, visual_id, prefix=node_id)
            visiting.pop()
            return
        if tag == "defs":
            return
        if tag in {"svg", "symbol"} or tag in {"title", "desc", "metadata"}:
            if tag == "symbol":
                group_id = inherited_group
            for child in list(node):
                visit(child, style, matrix, group_id, visual_id, prefix=prefix)
            return
        if tag == "g":
            for child in list(node):
                visit(child, style, matrix, group_id, visual_id, prefix=prefix)
            return
        if tag not in _LEAF_TAGS:
            raise SvgNativeError(f"unsupported SVG element {tag} on {node_id}", element_id=node_id, visual_id=visual_id, code="HD_SVG_UNSUPPORTED_ELEMENT")
        if not local_id:
            raise SvgNativeError(f"visible SVG element must have a stable id: {tag}", element_id=node_id, visual_id=visual_id)
        normalized_tag, bbox, commands = _geometry(node, tag, matrix, element_id=local_id, visual_id=visual_id)
        if tag == "path":
            fill_rule = str(style.get("fill-rule") or "nonzero").lower()
            if fill_rule not in {"nonzero", "evenodd"}:
                raise SvgNativeError(f"unsupported fill-rule on {local_id}", element_id=local_id, visual_id=visual_id, property_name="fill-rule")
            if fill_rule == "evenodd":
                commands, fill_rule = _normalize_evenodd(commands or [], element_id=local_id, visual_id=visual_id)
                bbox = _path_bbox(commands)
            style["fill-rule"] = fill_rule
        paint = _paint(style, registry, element_id=local_id, visual_id=visual_id)
        element = {
            "element_id": local_id,
            "source_element_id": node_id,
            "visual_id": visual_id,
            "group_id": group_id,
            "tag": tag,
            "normalized_tag": normalized_tag,
            "bbox": bbox,
            "style": style,
            "paint": paint,
            "commands": commands,
            "node": node,
            "z_index": int(node.get("data-pptx-z") or 0),
            "synthetic": local_id != node_id,
        }
        if tag == "text":
            element["text"] = str(node.get("data-pptx-text") or "".join(node.itertext()))
        if tag == "image":
            element["asset_ref"] = str(node.get("data-pptx-asset-id") or "")
        elements.append(element)
        if group_id:
            groups[group_id].setdefault("child_ids", []).append(local_id)

    root_style = dict(_DEFAULT_STYLE)
    visit(root, root_style, _IDENTITY)
    return {"elements": elements, "groups": groups, "ids": ids, "paint": registry}


def commands_to_svg_path(commands: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for command in commands:
        op = command["op"]
        if op in {"M", "L"}:
            parts.append(f"{op} {command['x']:.4f} {command['y']:.4f}")
        elif op == "C":
            parts.append(f"C {command['x1']:.4f} {command['y1']:.4f} {command['x2']:.4f} {command['y2']:.4f} {command['x']:.4f} {command['y']:.4f}")
        elif op == "Z":
            parts.append("Z")
    return " ".join(parts)


__all__ = ["SvgNativeError", "commands_to_svg_path", "format_svg_native_error", "parse_svg_native", "svg_recovery_command"]
