"""Runtime contracts and validation for the rebuilt core.

Document v1, PagePackage v2, Artifact v1, Task v1, Review v1 and the W02
frozen GenerationRequest/Attempt records share immutable object Refs.
JSON Schema (Draft 2020-12) checks
format/required fields/enums; cross-object semantics are explicit functions
here, not schema tricks (spec 03.1, 03.9).

Schemas are read from installed package resources via importlib.resources
(spec 01.3). Never hash the URI for an unknown original; ``original_sha256``
is null/omitted when unknown and never the all-zero digest (spec 03.2).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

SCHEMA_FILES = {
    "document": "document.v1.schema.json",
    "page": "page.v2.schema.json",
    "artifact": "artifact.v1.schema.json",
    "task": "task.v1.schema.json",
    "review": "review.v1.schema.json",
    "generation_input": "generation-input.v1.schema.json",
    "generation_request": "generation-request.v1.schema.json",
    "generation_attempt": "generation-attempt.v1.schema.json",
    "tool_observation": "tool-observation.v1.schema.json",
}

REF_PATH_PATTERN = r"^\.deckmaster/objects/[a-f0-9]{2}/[a-f0-9]{64}\.[a-z0-9]+$"
SHA256_PATTERN = r"^[a-f0-9]{64}$"
ZERO_SHA256 = "0" * 64

OBJECT_EXT_FOR_SCHEMA = {
    "document": "json",
    "page": "json",
    "artifact": "json",
    "task": "json",
    "review": "json",
}

DEFAULT_CANVAS = {    "width_px": 1600,
    "height_px": 900,
    "slide_width_in": 40 / 3,
    "slide_height_in": 7.5,
    "fit": "contain",
}


class ModelError(ValueError):
    """A contract violation with the offending path spelled out."""

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


def canonical_json_bytes(obj: Any) -> bytes:
    """Unified canonical encoding used for every JSON object hash (spec 03.2)."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_schema(kind: str) -> dict[str, Any]:
    try:
        filename = SCHEMA_FILES[kind]
    except KeyError as exc:  # pragma: no cover - caller bug
        raise ModelError("(schema)", f"unknown schema kind {kind!r}") from exc
    text = resources.files("deck_master").joinpath(f"resources/contracts/{filename}").read_text("utf-8")
    return json.loads(text)


def _validator(kind: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(kind))


def validate_schema(kind: str, obj: Any) -> None:
    """Schema-format validation; errors carry the failing JSON path."""
    errors = sorted(_validator(kind).iter_errors(obj), key=lambda e: list(e.absolute_path))
    worst = best_match(errors) if errors else None
    if worst is None:
        return
    path = "/".join(str(part) for part in worst.absolute_path) or "(root)"
    raise ModelError(f"{kind}/{path}", worst.message)


def validate_ref(ref: Any, *, where: str) -> dict[str, str]:
    """Object Ref shape: project-relative immutable object path plus its hash."""
    if not isinstance(ref, dict):
        raise ModelError(where, "ref must be an object with path and sha256")
    path = ref.get("path")
    sha = ref.get("sha256")
    if not isinstance(path, str) or not path.startswith(".deckmaster/objects/"):
        raise ModelError(where, f"ref.path must live under .deckmaster/objects/, got {path!r}")
    parts = path.split("/")
    stem, _, ext = parts[3].rpartition(".") if len(parts) == 4 else ("", "", "")
    hex_ok = len(stem) == 64 and all(c in "0123456789abcdef" for c in stem)
    if (
        len(parts) != 4
        or parts[1] != "objects"
        or len(parts[2]) != 2
        or parts[2] != stem[:2]
        or not hex_ok
        or not ext.isalnum()
        or ext != ext.lower()
    ):
        raise ModelError(
            where, f"ref.path must be .deckmaster/objects/<sha2>/<sha>.<ext>, got {path!r}"
        )
    if not isinstance(sha, str) or len(sha) != 64:
        raise ModelError(where, "ref.sha256 must be a 64-hex digest")
    for char in sha:
        if char not in "0123456789abcdef":
            raise ModelError(where, "ref.sha256 must be lowercase hex")
    if sha == ZERO_SHA256:
        raise ModelError(where, "all-zero digest is not a valid unknown marker")
    if sha != stem:
        raise ModelError(
            where, f"ref.sha256 {sha[:8]}… does not match object path stem {stem[:8]}…"
        )
    return ref


def validate_reference_regions(artifact: dict[str, Any]) -> None:
    """bbox_normalized is x/y/w/h in [0,1] with positive area (spec 03.5)."""
    regions = artifact.get("reference_regions") or []
    for index, region in enumerate(regions):
        where = f"artifact/reference_regions[{index}]"
        bbox = region.get("bbox_normalized")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ModelError(where, "bbox_normalized must be [x, y, w, h]")
        x, y, w, h = bbox
        if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in bbox):
            raise ModelError(where, f"bbox values must be numbers in [0,1], got {bbox}")
        if w <= 0 or h <= 0:
            raise ModelError(where, f"bbox must have positive area, got w={w} h={h}")
        if x + w > 1 or y + h > 1:
            raise ModelError(
                where, f"bbox leaves the canvas, got x+w={x + w} y+h={y + h}"
            )
        importance = region.get("importance")
        if importance not in ("essential", "supporting", "decorative"):
            raise ModelError(
                where, f"importance must be essential/supporting/decorative, got {importance!r}"
            )


def validate_artifact_semantics(artifact: dict[str, Any]) -> None:
    validate_schema("artifact", artifact)
    validate_ref(artifact["file"], where="artifact/file")
    validate_reference_regions(artifact)


def validate_page_semantics(page: dict[str, Any]) -> None:
    validate_schema("page", page)
    visual = page.get("visual_spec") or {}
    nodes = visual.get("nodes") or []
    edges = visual.get("edges") or []
    node_ids = [node.get("node_id") for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ModelError("page/visual_spec", "duplicate node_id")
    for edge in edges:
        where = f"page/visual_spec/edges/{edge.get('edge_id')}"
        if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
            raise ModelError(
                where, f"edge endpoints must exist in nodes, got {edge.get('from')}->{edge.get('to')}"
            )


def validate_task_semantics(task: dict[str, Any]) -> None:
    validate_schema("task", task)
    for index, allowance in enumerate(task.get("call_allowances") or []):
        state = allowance.get("state")
        if state not in ("reserved", "in_flight", "consumed", "released", "unknown"):
            raise ModelError(f"task/call_allowances[{index}]", f"unknown allowance state {state!r}")


def validate_review_semantics(review: dict[str, Any]) -> None:
    validate_schema("review", review)


def validate_document_structure(document: dict[str, Any]) -> None:
    """Schema plus structural checks reachable without loading other objects."""
    validate_schema("document", document)
    receipt = (document.get("change") or {}).get("operation_receipt")
    if receipt is not None and receipt["response"]["revision_id"] != document["revision_id"]:
        raise ModelError("document/change/operation_receipt/response/revision_id",
                         "operation receipt must name its own Document revision")
    pages = document.get("pages") or []
    page_ids = [entry.get("page_id") for entry in pages]
    if len(page_ids) != len(set(page_ids)):
        duplicated = sorted({pid for pid in page_ids if page_ids.count(pid) > 1})
        raise ModelError(
            "document/pages", f"duplicate page_id entries: {duplicated}"
        )
    for entry in pages:
        page_id = entry.get("page_id")
        validate_ref(entry["page"], where=f"document/pages/{page_id}/page")
        for slot in ("blueprint", "svg", "svg_preview", "ppt_preview"):
            if entry.get(slot):
                validate_ref(entry[slot], where=f"document/pages/{page_id}/{slot}")
    for index, ref in enumerate(document.get("tasks") or []):
        validate_ref(ref, where=f"document/tasks[{index}]")
    for index, ref in enumerate(document.get("reviews") or []):
        validate_ref(ref, where=f"document/reviews[{index}]")
    outputs = document.get("outputs") or {}
    for slot in ("pptx", "trace"):
        if outputs.get(slot):
            validate_ref(outputs[slot], where=f"document/outputs/{slot}")
    design = document.get("design_context") or {}
    style_ids = [style.get("style_id") for style in (design.get("styles") or [])]
    if len(style_ids) != len(set(style_ids)):
        raise ModelError("document/design_context/styles", "duplicate style_id")
    font_ids = [font.get("font_id") for font in (design.get("fonts") or [])]
    if len(font_ids) != len(set(font_ids)):
        raise ModelError("document/design_context/fonts", "duplicate font_id")
    asset_ids = [asset.get("asset_id") for asset in (design.get("assets") or [])]
    if len(asset_ids) != len(set(asset_ids)):
        raise ModelError("document/design_context/assets", "duplicate asset_id")
    allowed = design.get("allowed_asset_ids") or []
    unknown_allowed = [aid for aid in allowed if aid not in asset_ids]
    if unknown_allowed:
        raise ModelError(
            "document/design_context/allowed_asset_ids",
            f"allowed ids not present in assets: {unknown_allowed}",
        )
    default_style = design.get("default_style_id")
    if style_ids and default_style not in style_ids:
        raise ModelError(
            "document/design_context/default_style_id",
            f"default_style_id {default_style!r} not in styles",
        )
    for style in design.get("styles") or []:
        typography = style.get("typography") or {}
        for slot in ("body_font_id", "heading_font_id"):
            fid = typography.get(slot)
            if fid is not None and fid not in font_ids:
                raise ModelError(
                    f"document/design_context/styles/{style.get('style_id')}",
                    f"typography {slot} {fid!r} not declared in fonts",
                )
    for font in design.get("fonts") or []:
        fallback = font.get("fallback_font_ids") or []
        for fid in fallback:
            if fid not in font_ids:
                raise ModelError(
                    f"document/design_context/fonts/{font.get('font_id')}",
                    f"fallback font {fid!r} not declared",
                )
    _assert_no_fallback_cycle(design)


def _assert_no_fallback_cycle(design: dict[str, Any]) -> None:
    graph = {
        font.get("font_id"): list(font.get("fallback_font_ids") or [])
        for font in (design.get("fonts") or [])
    }

    def visit(node: str, chain: list[str]) -> None:
        if node in chain:
            cycle = " -> ".join(chain + [node])
            raise ModelError(
                "document/design_context/fonts", f"fallback cycle: {cycle}"
            )
        for neighbor in graph.get(node, ()):
            visit(neighbor, chain + [node])

    for font_id in graph:
        visit(font_id, [])


def validate_document_semantics(document: dict[str, Any]) -> None:
    validate_document_structure(document)


def default_design_context() -> dict[str, Any]:
    """Persisted at create time; consumers parse this snapshot with no extra defaults (spec 03.3a)."""
    return {
        "canvas": dict(DEFAULT_CANVAS),
        "language": "zh-CN",
        "fonts": [
            {
                "font_id": "body",
                "family": "Noto Sans CJK SC",
                "face": "Regular",
                "weight": 400,
                "asset_id": None,
                "fallback_font_ids": [],
            },
            {
                "font_id": "heading",
                "family": "Noto Sans CJK SC",
                "face": "Bold",
                "weight": 700,
                "asset_id": None,
                "fallback_font_ids": [],
            },
        ],
        "styles": [
            {
                "style_id": "default",
                "colors": {
                    "background": "#FFFFFF",
                    "text": "#14213D",
                    "accent": "#1478FF",
                },
                "typography": {
                    "body_font_id": "body",
                    "heading_font_id": "heading",
                    "body_size_pt": 18,
                    "heading_size_pt": 30,
                    "auxiliary_size_pt": 12,
                },
                "layout_notes": "默认样式在 create 时固化；字体名称是配置需求，不是本机安装证明。",
            }
        ],
        "default_style_id": "default",
        "assets": [],
        "allowed_asset_ids": [],
    }


def normalize_design_context(partial: dict[str, Any] | None) -> dict[str, Any]:
    """Fill persisted defaults at create time; unknown keys are the caller's problem."""
    design = default_design_context()
    partial = partial or {}
    for key, value in partial.items():
        design[key] = value
    if partial.get("canvas"):
        design["canvas"] = {**dict(DEFAULT_CANVAS), **partial["canvas"]}
        if design["canvas"].get("fit") != "contain":
            raise ModelError("design_context/canvas/fit", "fit must be contain in this version")
    validate_schema("document", {**_minimal_document_shell(), "design_context": design})
    return design


def _minimal_document_shell() -> dict[str, Any]:
    return {
        "schema_version": "deck_document.v1",
        "project_id": "probe",
        "revision_id": uuid.uuid4().hex,
        "parent_revision_id": None,
        "created_at": "1970-01-01T00:00:00Z",
        "task": {
            "title": "probe",
            "brief": "probe",
            "audience": "",
            "scenario": "",
            "presentation_mode": "live",
            "page_limit": None,
            "existing_decisions": [],
        },
        "sources": [],
        "pages": [],
        "tasks": [],
        "reviews": [],
        "outputs": {"pptx": None, "trace": None, "render_report": None},
        "policy": {
            "authoring_mode": "image_blueprint",
            "external_call_limit": None,
            "user_stop": False,
            "professional_review_required_for_delivery": False,
        },
        "change": {
            "operation_id": uuid.uuid4().hex,
            "kind": "create",
            "description": "shell",
            "read_set": [],
        },
    }


def bump_revision(document: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    """Advance to a new immutable revision: new id, parent link, and change record."""
    return {
        **document,
        "revision_id": uuid.uuid4().hex,
        "parent_revision_id": document["revision_id"],
        "change": change,
    }


CONTENT_KEYS = ("project_id", "task", "sources", "pages", "design_context", "policy", "outputs")


def content_identity(document: dict[str, Any]) -> str:
    """Hash of the content a Host task depends on — revision/task-list agnostic.

    Task-management revisions (dispatch, claim, allocation) never move this
    identity; an adopted result or a real content change does. Accept uses it
    to decide whether work is still fresh, without blocking legitimate claims.
    """
    projection = {key: document.get(key) for key in CONTENT_KEYS}
    return sha256_bytes(canonical_json_bytes(projection))


INPUT_SOURCE_KEYS = ("source_id", "original_sha256", "extract_sha256", "usage_note",
                     "external_use", "restriction")


def compute_input_digest(document: dict[str, Any]) -> str:
    """Digest of the task facts and source semantics the content is built on.

    Canonical JSON over ``{"task": Document.task, "sources": [...]}`` where
    each source contributes only its semantic fields (spec v1.1 §5.1):
    storage paths, display names, timestamps, tasks, reviews and outputs are
    excluded so a display-name change never invalidates the content basis.
    Unset ``usage_note`` counts as the empty string.
    """
    sources = []
    for source in sorted(document.get("sources") or [], key=lambda s: s.get("source_id") or ""):
        extract = source.get("extract") or {}
        sources.append(
            {
                "source_id": source.get("source_id"),
                "original_sha256": source.get("original_sha256"),
                "extract_sha256": extract.get("sha256"),
                "usage_note": source.get("usage_note") or "",
                "external_use": source.get("external_use"),
                "restriction": source.get("restriction"),
            }
        )
    payload = {"task": document.get("task"), "sources": sources}
    return sha256_bytes(canonical_json_bytes(payload))


def input_alignment(document: dict[str, Any]) -> str:
    """Derived, never stored (spec v1.1 §5.1): how current content maps to inputs."""
    if not document.get("pages"):
        return "no_content"
    basis = document.get("content_basis")
    if not basis:
        return "legacy_current"
    return "current" if basis.get("input_digest") == compute_input_digest(document) \
        else "needs_reconciliation"


def new_document(
    *,
    project_id: str,
    task: dict[str, Any],
    design_context: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal valid Document v1 snapshot (no pages yet)."""
    document = {
        "schema_version": "deck_document.v1",
        "project_id": project_id,
        "revision_id": uuid.uuid4().hex,
        "parent_revision_id": None,
        "created_at": _utc_now_iso(),
        "task": {
            "title": task.get("title", ""),
            "brief": task.get("brief", ""),
            "audience": task.get("audience", ""),
            "scenario": task.get("scenario", ""),
            "presentation_mode": task.get("presentation_mode", "live"),
            "presentation_mode_source": task.get("presentation_mode_source") or "default",
            "page_limit": task.get("page_limit"),
            "existing_decisions": task.get("existing_decisions", []),
        },
        "sources": sources or [],
        "pages": [],
        "tasks": [],
        "reviews": [],
        "outputs": {"pptx": None, "trace": None, "render_report": None},
        "policy": policy
        or {
            "authoring_mode": "image_blueprint",
            "external_call_limit": None,
            "user_stop": False,
            "professional_review_required_for_delivery": False,
        },
        "change": {
            "operation_id": operation_id or uuid.uuid4().hex,
            "kind": "create",
            "description": "project created",
            "read_set": [],
        },
        "design_context": normalize_design_context(design_context),
    }
    validate_document_semantics(document)
    return document


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def page_limit_violation(document):
    """A task limit constrains the resulting deck, not just changed pages."""
    limit = (document.get('task') or {}).get('page_limit')
    count = len(document.get('pages') or [])
    if limit is not None and count > limit:
        return f'page_limit={limit}, resulting page count={count}; reduce the deck or update the page limit'
    return None
