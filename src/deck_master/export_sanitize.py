"""Clean public export copies; immutable originals and visible slide text stay intact."""

from __future__ import annotations
import base64
import io
import re
import struct
import zipfile
import zlib
from lxml import etree as ET
from urllib.parse import urlparse, parse_qs
from .operations import OperationError

PRIVATE = re.compile(
    r"(?:file://|/(?:Users|home|private/tmp|tmp)/|[A-Za-z]:\\|\bBearer\s+[A-Za-z0-9_.-]{8,}|\bsk-[A-Za-z0-9_-]{16,})", re.I
)


def reject(where, reason):
    raise OperationError("export_privacy_blocked", where, reason, exit_code=3, http_status=409)


def text_safe(value, where):
    if value and PRIVATE.search(value):
        reject(where, "public copy contains a local path or credential-like value; review the named content")


def link_safe(value, where):
    text_safe(value, where)
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme not in ("https", "http", "mailto"):
        reject(where, "unsupported external link scheme")
    if (
        parsed.username
        or parsed.password
        or set(parse_qs(parsed.query)) & {"token", "access_token", "api_key", "signature", "authorization"}
    ):
        reject(where, "external link contains authentication data")


def png(data, where):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        reject(where, "invalid PNG payload")
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.getexif().get(274, 1) != 1:
                reject(where, "PNG orientation must be normalized before a public copy")
    except OperationError:
        raise
    except Exception:
        reject(where, "invalid PNG metadata")
    # Preserve compressed pixels/palette/color interpretation, discard metadata chunks.
    keep = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"cHRM", b"gAMA", b"sBIT", b"sRGB", b"pHYs"}
    out = bytearray(data[:8])
    cursor = 8
    ended = False
    while cursor < len(data):
        if cursor + 12 > len(data):
            reject(where, "truncated PNG chunk")
        size = struct.unpack(">I", data[cursor : cursor + 4])[0]
        kind = data[cursor + 4 : cursor + 8]
        end = cursor + 12 + size
        if end > len(data):
            reject(where, "truncated PNG chunk")
        if kind in (b"acTL", b"fcTL", b"fdAT"):
            reject(where, "animated PNG export needs explicit handling")
        if kind == b"iCCP":
            payload = data[cursor + 8 : end - 4]
            try:
                label, compressed = payload.split(b"\0", 1)
                if not compressed or compressed[0] != 0:
                    reject(where, "invalid PNG color profile")
                decoder = zlib.decompressobj()
                profile = decoder.decompress(compressed[1:], 4_000_001)
                if not decoder.eof or len(profile) > 4_000_000:
                    reject(where, "invalid or oversized PNG color profile")
                text_safe((label + b" " + profile).decode("latin1"), where + "/color-profile")
            except (ValueError, zlib.error):
                reject(where, "invalid PNG color profile")
            out.extend(data[cursor:end])
        elif kind in keep:
            out.extend(data[cursor:end])
        elif kind[:1].isupper():
            reject(where, "unknown required PNG chunk")
        cursor = end
        if kind == b"IEND":
            ended = True
            break
    if not ended:
        reject(where, "missing PNG end marker")
    from PIL import Image

    try:
        with Image.open(io.BytesIO(out)) as image:
            image.verify()
    except Exception:
        reject(where, "PNG pixel stream cannot be verified")
    return bytes(out)


def jpeg(data, where):
    if not data.startswith(b"\xff\xd8"):
        reject(where, "invalid JPEG payload")
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.getexif().get(274, 1) != 1:
                reject(where, "JPEG orientation must be normalized before a public copy")
    except OperationError:
        raise
    except Exception:
        reject(where, "invalid JPEG metadata")
    out = bytearray(data[:2])
    cursor = 2
    ended = False
    while cursor < len(data):
        if data[cursor] != 255 or cursor + 1 >= len(data):
            reject(where, "invalid JPEG marker")
        start = cursor
        while cursor + 1 < len(data) and data[cursor + 1] == 255:
            cursor += 1
        marker = data[cursor + 1]
        if marker == 0xD9:
            out.extend(b"\xff\xd9")
            ended = True
            break
        if cursor + 4 > len(data):
            reject(where, "truncated JPEG segment")
        size = int.from_bytes(data[cursor + 2 : cursor + 4], "big")
        end = cursor + 2 + size
        if size < 2 or end > len(data):
            reject(where, "invalid JPEG segment length")
        payload = data[cursor + 4 : end]
        color = (marker == 0xE2 and payload.startswith(b"ICC_PROFILE\0")) or (marker == 0xEE and payload.startswith(b"Adobe"))
        if color:
            text_safe(payload.decode("latin1"), where + "/color-profile")
        if color or not (0xE0 <= marker <= 0xEF or marker == 0xFE):
            out.extend(data[start:end])
        cursor = end
        if marker == 0xDA:
            # Keep entropy-coded samples byte-for-byte, including byte stuffing
            # and restart markers. Metadata after a scan is still filtered.
            scan = cursor
            while cursor < len(data):
                if data[cursor] != 255:
                    cursor += 1
                    continue
                if cursor + 1 >= len(data):
                    reject(where, "truncated JPEG scan")
                following = data[cursor + 1]
                if following == 0 or 0xD0 <= following <= 0xD7:
                    cursor += 2
                    continue
                break
            out.extend(data[scan:cursor])
    if not ended:
        reject(where, "missing JPEG end marker")
    try:
        with Image.open(io.BytesIO(out)) as image:
            image.load()
    except Exception:
        reject(where, "JPEG pixel stream cannot be verified")
    return bytes(out)


SVG_TAGS = {
    "svg",
    "style",
    "g",
    "defs",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "textPath",
    "use",
    "image",
    "a",
    "title",
    "linearGradient",
    "radialGradient",
    "stop",
    "clipPath",
    "mask",
    "pattern",
    "marker",
    "filter",
    "feGaussianBlur",
    "feOffset",
    "feBlend",
    "feColorMatrix",
    "feComposite",
    "feFlood",
    "feMerge",
    "feMergeNode",
}
SVG_ATTRS = set(
    "id class x y x1 x2 y1 y2 dx dy width height viewBox preserveAspectRatio d points cx cy r rx ry fill fill-opacity fill-rule stroke stroke-width stroke-opacity stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset opacity transform font-family font-size font-weight font-style text-anchor dominant-baseline alignment-baseline letter-spacing word-spacing textLength lengthAdjust clip-path clip-rule mask filter offset stop-color stop-opacity gradientUnits gradientTransform spreadMethod fx fy patternUnits patternContentUnits patternTransform marker-start marker-mid marker-end markerWidth markerHeight refX refY orient style href startOffset method spacing version xmlns color visibility display vector-effect shape-rendering text-rendering stdDeviation in in2 result mode values type operator k1 k2 k3 k4 flood-color flood-opacity".split()
)


def xml(data, where):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        reject(where, "XML declarations/entities are not allowed in public exports")
    try:
        root = ET.fromstring(data, parser=ET.XMLParser(resolve_entities=False, no_network=True, remove_comments=True, remove_pis=True))
        if root.getroottree().docinfo.doctype:
            reject(where, "XML declarations/entities are not allowed")
        return root
    except ET.ParseError:
        reject(where, "invalid XML payload")


def _css(value, where):
    # Keep ordinary local paint/styles. Escaped/remote CSS needs explicit review.
    if "\\" in value or re.search(r"@import|@font-face|expression\s*\(", value, re.I):
        reject(where, "unsupported external or active SVG style")
    for item in re.findall(r"url\s*\(([^)]*)\)", value, re.I):
        if not item.strip().strip("\"'").startswith("#"):
            reject(where, "external SVG style resource")
    text_safe(value, where)


def svg(data, where, depth=0):
    if depth > 4:
        reject(where, "nested embedded image limit exceeded")
    root = xml(data, where)
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag.rsplit("}", 1)[-1] in ("metadata", "desc"):
                parent.remove(child)
    for parent in list(root.iter()):
        for child in list(parent):
            tag = child.tag.rsplit("}", 1)[-1]
            if tag in ("metadata", "desc"):
                parent.remove(child)
            elif tag not in SVG_TAGS:
                reject(where + "/" + tag, "unsupported or active SVG element")
        if parent.tag.rsplit("}", 1)[-1] == "style":
            _css(parent.text or "", where + "/style")
        for key, value in list(parent.attrib.items()):
            name = key.rsplit("}", 1)[-1]
            if name.lower().startswith("on"):
                reject(where + "/" + name, "active SVG attribute")
            if name not in SVG_ATTRS:
                del parent.attrib[key]
                continue
            if name == "href":
                if value.startswith("data:image/png;base64,"):
                    try:
                        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
                    except ValueError:
                        reject(where, "invalid embedded PNG")
                    parent.attrib[key] = "data:image/png;base64," + base64.b64encode(png(raw, where + "/image")).decode()
                elif parent.tag.rsplit("}", 1)[-1] == "a":
                    link_safe(value, where + "/link")
                elif not value.startswith("#"):
                    reject(where + "/href", "external SVG assets are not self-contained")
            elif name == "style":
                _css(value, where + "/style")
            elif re.search(r"url\s*\(", value, re.I):
                resources = re.findall(r"url\s*\(([^)]*)\)", value, re.I)
                if not resources or any(not item.strip().strip("\"'").startswith("#") for item in resources):
                    reject(where + "/" + name, "external SVG style resource")
                text_safe(value, where + "/" + name)
            else:
                text_safe(value, where + "/" + name)
        text_safe(parent.text, where + "/text")
        text_safe(parent.tail, where + "/text")
    if root.tag.rsplit("}", 1)[-1] != "svg":
        reject(where, "expected SVG root")
    cleaned = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    text_safe(cleaned.decode("utf-8"), where + "/xml")
    return cleaned


def pptx(data, where):
    import posixpath

    try:
        source = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        reject(where, "invalid PPTX archive")
    names = source.namelist()
    if len(set(names)) != len(names) or any(n.startswith("/") or ".." in n.split("/") for n in names):
        reject(where, "unsafe PPTX part names")
    if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
        reject(where, "PPTX presentation parts missing")
    if any(n.startswith("ppt/embeddings/") or "vbaProject" in n for n in names):
        reject(where, "embedded files or macros require separate review")
    removed = {
        n
        for n in names
        if n.startswith(
            (
                "docProps/",
                "ppt/notesSlides/",
                "ppt/notesMasters/",
                "ppt/comments/",
                "ppt/commentAuthors",
                "customXml/",
                "ppt/persons/",
                "ppt/printerSettings/",
            )
        )
    }
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for name in names:
            if name in removed or name.endswith("/"):
                continue
            raw = source.read(name)
            if name.endswith((".xml", ".rels")):
                root = xml(raw, where + "/" + name)
                for parent in root.iter():
                    local = parent.tag.rsplit("}", 1)[-1]
                    if local == "cNvPr":
                        # Non-visible shape labels and accessibility descriptions
                        # can contain generation prompts. Preserve the drawing ID.
                        for key in ("name", "descr", "title"):
                            parent.attrib.pop(key, None)
                        parent.set("name", "Shape " + parent.get("id", ""))
                    if local == "cSld":
                        parent.attrib.pop("name", None)
                    for child in list(parent):
                        local = child.tag.rsplit("}", 1)[-1]
                        if local == "Override" and child.get("PartName", "").lstrip("/") in removed:
                            parent.remove(child)
                        elif local == "Relationship":
                            uri = child.get("Target", "")
                            if child.get("TargetMode") == "External":
                                link_safe(uri, where + "/" + name)
                            else:
                                base = posixpath.dirname(posixpath.dirname(name)) if "/_rels/" in name else ""
                                resolved = posixpath.normpath(posixpath.join(base, uri)).lstrip("/")
                                if resolved in removed:
                                    parent.remove(child)
                        elif local in ("notesMasterIdLst", "notesMasterId"):
                            parent.remove(child)
                    text_safe(parent.text, where + "/" + name)
                    text_safe(parent.tail, where + "/" + name)
                    for value in parent.attrib.values():
                        text_safe(value, where + "/" + name)
                raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                text_safe(raw.decode("utf-8"), where + "/" + name)
            elif name.lower().endswith(".png"):
                raw = png(raw, where + "/" + name)
            elif name.lower().endswith((".jpg", ".jpeg")):
                raw = jpeg(raw, where + "/" + name)
            elif name.lower().endswith(".svg"):
                raw = svg(raw, where + "/" + name)
            else:
                reject(where + "/" + name, "unsupported non-XML PPTX part requires explicit review")
            part = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            part.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(part, raw)
    return output.getvalue()


def sanitize(data, suffix, where):
    handlers = {".png": png, ".jpg": jpeg, ".jpeg": jpeg, ".svg": svg, ".pptx": pptx}
    if suffix.lower() not in handlers:
        reject(where, "unsupported public artifact format")
    return handlers[suffix.lower()](data, where)
