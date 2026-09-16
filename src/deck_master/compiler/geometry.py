"""Function-level extraction from pinned B0, compared with K0; see extraction ledger."""
from __future__ import annotations
import math
import re
from typing import Any

class SvgNativeError(ValueError):
    def __init__(self, message, **context):
        self.context=context
        super().__init__(message)

_IDENTITY=(1.,0.,0.,1.,0.,0.)
_TOKEN_RE=re.compile(r"([AaCcHhLlMmQqSsTtVvZz])|([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)")
_TRANSFORM_RE=re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
_COMMAND_ARGS={"M":2,"L":2,"H":1,"V":1,"C":6,"S":4,"Q":4,"T":2,"A":7,"Z":0}
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

def _finite(value: Any, *, label: str, element_id: str, visual_id: str = "") -> float:
    try:
        parsed = float(str(value).strip().removesuffix("px"))
    except (TypeError, ValueError) as exc:
        raise SvgNativeError(f"SVG {label} is invalid on {element_id}", element_id=element_id, visual_id=visual_id, property_name=label) from exc
    if not math.isfinite(parsed):
        raise SvgNativeError(f"SVG {label} is not finite on {element_id}", element_id=element_id, visual_id=visual_id, property_name=label)
    return parsed
