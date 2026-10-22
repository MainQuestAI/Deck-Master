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
import re
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match
from referencing import Registry, Resource

SCHEMA_FILES = {
    "ui_arguments": "ui-arguments.v1.schema.json",
    "ui_argument": "ui-argument.v1.schema.json",
    "ui_page_evidence": "ui-page-evidence.v1.schema.json",
    "ui_review_reading": "ui-review-reading.v1.schema.json",
    "ui_content_requirements": "ui-content-requirements.v1.schema.json",
    "ui_task_methods": "ui-task-methods.v1.schema.json",
    "ui_method_preview": "ui-method-preview.v1.schema.json",
    "work_context.v2": "work-context.v2.schema.json",
    "collaboration": "collaboration.v1.schema.json",
    "collaboration_decision": "collaboration-decision.v1.schema.json",
    "collaboration_authorization": "collaboration-authorization.v1.schema.json",
    "narrative": "narrative.v1.schema.json",
    "content_plan_input_v2": "content-plan-input.v2.schema.json",
    "content_plan_v2": "content-plan.v2.schema.json",
    "compose_result_v2": "compose-result.v2.schema.json",
    "review_v2": "review.v2.schema.json",
    "native_review_checkpoint": "native-review-checkpoint.v1.schema.json",
    "authenticated_review_receipt": "authenticated-review-receipt.v1.schema.json",
    "native_image_receipt": "native-image-receipt.v1.schema.json",
    "content_requirements": "content-requirements.v1.schema.json",
    "content_basis": "content-basis.v1.schema.json",
    "asset_inputs": "asset-inputs.v1.schema.json",
    "style_reference": "style-reference.v1.schema.json",
    "visual_style_spec": "visual-style-spec.v1.schema.json",
    "style_input_v2": "style-input.v2.schema.json",
    "style_proposal_v2": "style-proposal.v2.schema.json",
    "style_recipe_v2": "style-recipe.v2.schema.json",
    "style_input_v3": "style-input.v3.schema.json",
    "style_proposal_v3": "style-proposal.v3.schema.json",
    "style_recipe_v3": "style-recipe.v3.schema.json",
    "icon_input": "icon-input.v1.schema.json",
    "icon_recipe": "icon-recipe.v1.schema.json",
    "action_targets": "action-targets.v1.schema.json",
    "restore_plan": "restore-plan.v1.schema.json",
    "export_manifest": "export-manifest.v1.schema.json",
    "content_operation_input": "content-operation-input.v1.schema.json",
    "content_operation_plan": "content-operation-plan.v1.schema.json",
    "page_derivation": "page-derivation.v1.schema.json",
    "style_input": "style-input.v1.schema.json",
    "style_proposal": "style-proposal.v1.schema.json",
    "style_recipe": "style-recipe.v1.schema.json",
    "candidate": "candidate.v1.schema.json",
    "candidate_selection": "candidate-selection.v1.schema.json",
    "candidate_adoption": "candidate-adoption.v1.schema.json",
    "candidate_decision": "candidate-decision.v1.schema.json",
    "change_handoff": "handoff.v1.schema.json",
    "change_intent": "change-intent.v1.schema.json",
    "change_plan": "change-plan.v1.schema.json",
    "change_set": "change-set.v1.schema.json",
    "annotation": "annotation.v1.schema.json",
    "annotation_batch": "annotation-batch.v1.schema.json",
    "annotation_list": "annotation-list.v1.schema.json",
    "operation_commit": "operation-commit.v1.schema.json",
    "document": "document.v1.schema.json",
    "page": "page.v2.schema.json",
    "artifact": "artifact.v1.schema.json",
    "task": "task.v1.schema.json",
    "review": "review.v1.schema.json",
    "generation_input": "generation-input.v1.schema.json",
    "generation_request": "generation-request.v1.schema.json",
    "generation_attempt": "generation-attempt.v1.schema.json",
    "tool_observation": "tool-observation.v1.schema.json",
    "content_plan_input": "content-plan-input.v1.schema.json",
    "content_plan": "content-plan.v1.schema.json",
    "ui_draft": "ui-draft.v1.schema.json",
    "ui_draft_record": "ui-draft-record.v1.schema.json",
    "ui_draft_recovery": "ui-draft-recovery.v1.schema.json",
    "ui_position": "ui-position.v1.schema.json",
    "ui_gallery": "ui-gallery.v1.schema.json",
    "result_reading": "result-reading.v1.schema.json",
    "ui_overview": "ui-overview.v1.schema.json",
    "ui_clear_plan": "ui-clear-plan.v1.schema.json",
    "ui_clear_result": "ui-clear-result.v1.schema.json",
    "ui_clear_backup": "ui-clear-backup.v1.schema.json",
    "thumbnail": "thumbnail.v1.schema.json",
    "text_range": "text-range.v1.schema.json",
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


@lru_cache(maxsize=None)
def _contract_registry() -> Registry:
    """Cross-file $ref support: contracts reference each other by file name
    (e.g. document.v1 -> collaboration.v1.schema.json). Every registered
    contract is loaded once; a bare filename resolves against this registry."""
    registry = Registry()
    for filename in sorted(set(SCHEMA_FILES.values())):
        schema = json.loads(
            resources.files("deck_master").joinpath(f"resources/contracts/{filename}").read_text("utf-8")
        )
        registry = registry.with_resource(filename, Resource.from_contents(schema))
    return registry


@lru_cache(maxsize=None)
def _validator(kind: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(kind), registry=_contract_registry())


# schema_version dispatch: the same logical kind maps to newer contract files
# without replacing the default validator, so old objects stay readable
# (MIGRATION §2.2). Read-only dispatch; writers are gated by the writer rank.
_VERSIONED_KINDS = {
    "content_plan": {"content_plan.v2": "content_plan_v2"},
    "content_plan_input": {"content_plan_input.v2": "content_plan_input_v2"},
    "review": {"deck_review.v2": "review_v2"},
}


def validate_schema(kind: str, obj: Any) -> None:
    """Schema-format validation; errors carry the failing JSON path."""
    if isinstance(obj, dict):
        dispatched = _VERSIONED_KINDS.get(kind, {}).get(obj.get("schema_version"))
        if dispatched:
            kind = dispatched
    if kind in ("style_input", "style_proposal", "style_recipe") and isinstance(obj, dict):
        for version in ("v2", "v3"):
            if obj.get("schema_version") == kind + "." + version:
                kind += "_" + version
                break
    errors = sorted(_validator(kind).iter_errors(obj), key=lambda e: list(e.absolute_path))
    worst = best_match(errors) if errors else None
    if worst is None:
        return
    path = "/".join(str(part) for part in worst.absolute_path) or "(root)"
    raise ModelError(f"{kind}/{path}", worst.message)


@lru_cache(maxsize=8192)
def _known_valid_ref(path: str, sha: str) -> bool:
    parts = path.split('/')
    stem, _, ext = parts[3].rpartition('.') if len(parts) == 4 else ('', '', '')
    return (path.startswith('.deckmaster/objects/') and len(parts) == 4
            and parts[2] == stem[:2] and len(parts[2]) == 2
            and re.fullmatch('[0-9a-f]{64}', stem) is not None
            and ext.isalnum() and ext == ext.lower()
            and sha == stem and sha != ZERO_SHA256)


def validate_ref(ref: Any, *, where: str) -> dict[str, str]:
    """Object Ref shape: project-relative immutable object path plus its hash."""
    if not isinstance(ref, dict):
        raise ModelError(where, "ref must be an object with path and sha256")
    path = ref.get("path")
    sha = ref.get("sha256")
    # Only cache short immutable string grammar, never file existence or
    # integrity. Filesystem checks still execute at every object access. The
    # original slow path preserves precise errors for malformed references.
    if (isinstance(path, str) and isinstance(sha, str) and len(path) <= 256 and len(sha) == 64
            and _known_valid_ref(path, sha)):
        return ref
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
    policy = visual.get("design_policy")
    if policy:
        table_ids = {block["id"] for block in page["customer_visible"].get("body_blocks", [])
                     if block["type"] == "table"}
        roles = [item["block_id"] for item in policy["table_roles"]]
        if len(roles) != len(set(roles)) or not set(roles) <= table_ids:
            raise ModelError("page/visual_spec/design_policy/table_roles", "roles must name unique actual tables")
    mapping = page.get("content_mapping")
    if mapping:
        atom_refs = [link.get("element_ref") for link in mapping.get("visible_links") or []]
        if len(atom_refs) != len(set(atom_refs)):
            raise ModelError("page/content_mapping/visible_links",
                             "each visible atom gets exactly one mapping entry")
        from .content import atom_ids
        expected_atoms = atom_ids(page)
        mapped_atoms = {link.get("element_ref") for link in mapping.get("visible_links") or []}
        missing_atoms = sorted(expected_atoms - mapped_atoms)
        unknown_atoms = sorted(mapped_atoms - expected_atoms)
        if missing_atoms:
            raise ModelError("page/content_mapping/visible_links",
                             f"every visible atom needs exactly one mapping entry; missing: {missing_atoms}")
        if unknown_atoms:
            raise ModelError("page/content_mapping/visible_links",
                             f"mapping references atoms that are not visible content: {unknown_atoms}")
        segments = mapping.get("speech_segments") or []
        segment_ids = [segment.get("segment_id") for segment in segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ModelError("page/content_mapping/speech_segments", "duplicate segment_id")
        previous_end = 0
        for segment in sorted(segments, key=lambda s: s.get("start_codepoint", 0)):
            start, end = segment.get("start_codepoint"), segment.get("end_codepoint")
            where = f"page/content_mapping/speech_segments/{segment.get('segment_id')}"
            if start is None or end is None or start >= end:
                raise ModelError(where, "speech ranges are half-open and must be non-empty")
            if start < previous_end:
                raise ModelError(where, "speech ranges must not overlap")
            previous_end = end
        notes = page.get("speaker_notes") or ""
        if segments:
            cursor = 0
            for segment in sorted(segments, key=lambda s: s.get("start_codepoint", 0)):
                if segment.get("start_codepoint") != cursor:
                    raise ModelError("page/content_mapping/speech_segments",
                                     "speech segments must cover the notes contiguously")
                cursor = segment.get("end_codepoint")
            if cursor != len(notes):
                raise ModelError("page/content_mapping/speech_segments",
                                 f"speech segments must cover all {len(notes)} codepoints of speaker_notes")
        elif notes:
            raise ModelError("page/content_mapping/speech_segments",
                             "non-empty speaker notes must be covered by speech segments")


def validate_task_semantics(task: dict[str, Any]) -> None:
    validate_schema("task", task)
    if "method_manifest" in task:
        manifest = task["method_manifest"]
        from .resource_catalog import relative_path
        for item in manifest:
            try:
                relative_path(item["relative_path"])
            except ValueError as exc:
                raise ModelError("task/method_manifest", str(exc)) from exc
        if len({item["id"] for item in manifest}) != len(manifest):
            raise ModelError("task/method_manifest", "duplicate method id")
        digest = sha256_bytes(canonical_json_bytes([[item["relative_path"], item["sha256"]] for item in manifest]))
        if (task.get("method_release") or {}).get("methods_sha256") != digest:
            raise ModelError("task/method_release", "method digest must match the frozen ordered manifest")
    for index, allowance in enumerate(task.get("call_allowances") or []):
        state = allowance.get("state")
        if state not in ("reserved", "in_flight", "consumed", "released", "unknown"):
            raise ModelError(f"task/call_allowances[{index}]", f"unknown allowance state {state!r}")


_REVIEW_ASSURANCE_FLOORS = {
    "human_internal": ("verified_user",),
    "human_external": ("verified_user",),
    "independent_host": ("host_attested",),
    "host_self": ("host_attested", "unverified"),
    "tool": ("host_attested", "unverified"),
}


def require_task_binding(document: dict[str, Any], task: dict[str, Any]) -> None:
    """MIGRATION §2.2: newly dispatched tasks in a collaboration.v1 project
    must carry a valid collaboration binding (current request, and any bound
    authorization/decision must be referenced by the current region)."""
    if not collaboration_required(document):
        if task.get('collaboration_binding') is not None:
            raise ModelError('task/collaboration_binding',
                             'a collaboration task needs an actual migrated control region')
        return
    binding = task.get("collaboration_binding")
    if not binding:
        raise ModelError("task/collaboration_binding",
                         "a collaboration.v1 project requires the task's collaboration binding")
    region = document.get("collaboration") or {}
    request = region.get("request")
    if request is None or binding.get("request_id") != request.get("request_id"):
        raise ModelError("task/collaboration_binding/request_id",
                         "the binding must name the current work request")
    for key, family, id_field in (("authorization_ref", "authorizations", "authorization_id"),
                                  ("decision_refs", "decisions", "decision_id")):
        refs = binding.get(key)
        if refs is None:
            continue
        refs = refs if isinstance(refs, list) else [refs]
        known = {(ref.get("path"), ref.get("sha256"))
                 for ref in region.get(family) or []}
        for index, ref in enumerate(refs):
            if (ref.get("path"), ref.get("sha256")) not in known:
                raise ModelError(f"task/collaboration_binding/{key}[{index}]",
                                 "bound records must be referenced by the current collaboration region")


def validate_review_semantics(review: dict[str, Any]) -> None:
    validate_schema("review", review)
    if review.get("schema_version") != "deck_review.v2":
        return  # v1 records stay readable with their original identity labels
    reviewer = review.get("reviewer") or {}
    allowed = _REVIEW_ASSURANCE_FLOORS.get(reviewer.get("type"))
    if allowed is not None and reviewer.get("assurance") not in allowed:
        raise ModelError(
            "review/reviewer/assurance",
            f"{reviewer.get('type')} reviewers must record assurance "
            f"{allowed[0]!r}; identity evidence is verified by its receipt, not by a claimed level",
        )
    if reviewer.get("assurance") == "verified_user" and not reviewer.get("identity_receipt"):
        raise ModelError("review/reviewer/identity_receipt",
                         "verified_user review evidence requires an identity receipt; adoption verifies its adapter")


def validate_narrative_semantics(narrative: dict[str, Any], *, policy: str | None = None) -> None:
    """Narrative semantics (CONTRACTS §11.1): reference integrity across
    nodes/edges/issues, argument maturity requirements, and the authority
    floor for reported facts and calculations. Source support quality stays a
    content-review question; this checks what can be checked structurally."""
    validate_schema("narrative", narrative)
    nodes = narrative.get("nodes") or []
    node_ids = [node.get("node_id") for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ModelError("narrative/nodes", "duplicate node_id")
    known = set(node_ids)
    issues = narrative.get("issues") or []
    issue_ids = [issue.get("issue_id") for issue in issues]
    if len(issue_ids) != len(set(issue_ids)):
        raise ModelError("narrative/issues", "duplicate issue_id")
    blocker_ids = {issue.get("issue_id") for issue in issues
                   if issue.get("impact") == "blocker" and issue.get("resolution") == "open"}

    def require_known(ids, where):
        unknown = sorted(set(ids) - known)
        if unknown:
            raise ModelError(where, f"unknown node ids: {unknown}")

    for node in nodes:
        where = f"narrative/nodes/{node.get('node_id')}"
        require_known(node.get("qualification_node_ids") or [], where + "/qualification_node_ids")
        unknown_issues = sorted(set(node.get("unresolved_issue_ids") or []) - set(issue_ids))
        if unknown_issues:
            raise ModelError(where + "/unresolved_issue_ids", f"unknown issue ids: {unknown_issues}")
        if node.get("authority") in ("reported_fact", "calculation"):
            has_source = bool(node.get("source_links"))
            has_blocker = bool(set(node.get("unresolved_issue_ids") or []) & blocker_ids)
            if not (has_source or has_blocker):
                raise ModelError(
                    where,
                    f"{node.get('authority')} needs a verifiable source locator or an explicit blocker issue",
                )
    for index, edge in enumerate(narrative.get("edges") or []):
        endpoints = [edge.get("from_node_id"), edge.get("to_node_id")]
        require_known(endpoints, f"narrative/edges[{index}]")
    for issue in issues:
        require_known(issue.get("affected_node_ids") or [], f"narrative/issues/{issue.get('issue_id')}/affected_node_ids")
    for alternative in narrative.get("alternatives") or []:
        require_known(alternative.get("affected_node_ids") or [],
                      f"narrative/alternatives/{alternative.get('option_id')}/affected_node_ids")
    central = narrative.get("central_node_id")
    if narrative.get("maturity") == "argument":
        if central is None or central not in known:
            raise ModelError("narrative/central_node_id",
                             "an argument narrative needs a central node that exists in nodes")
    elif central is not None and central not in known:
        raise ModelError("narrative/central_node_id", "central node id must exist in nodes")

    if policy is not None and policy != "argument-connectivity.v1":
        raise ModelError("narrative/policy", "unsupported content validation policy")
    if policy == "argument-connectivity.v1" and narrative.get("maturity") == "argument":
        adjacent = {node_id: set() for node_id in node_ids}
        for edge in narrative.get("edges") or []:
            left, right = edge["from_node_id"], edge["to_node_id"]
            adjacent[left].add(right)
            adjacent[right].add(left)
        for node in nodes:
            for qualifier in node.get("qualification_node_ids") or []:
                adjacent[node["node_id"]].add(qualifier)
                adjacent[qualifier].add(node["node_id"])
        reached, pending = set(), [central]
        while pending:
            node_id = pending.pop()
            if node_id not in reached:
                reached.add(node_id)
                pending.extend(adjacent[node_id] - reached)
        unreachable = sorted(known - reached)
        if unreachable:
            raise NarrativeDisconnected(central, unreachable)


class NarrativeDisconnected(ModelError):
    http_status = 400
    error_code = "narrative_disconnected"
    exit_code = 2

    def __init__(self, central, unreachable):
        super().__init__("payload.narrative.nodes",
                         f"argument-connectivity.v1: nodes {unreachable} are disconnected from {central}; "
                         "add genuine support/explanation/qualification relations or move unrelated material out")
        self.central_node_id = central
        self.unreachable_node_ids = unreachable
        self.policy = "argument-connectivity.v1"
        self.error_details = {"central_node_id": central, "unreachable_node_ids": unreachable,
                              "policy": self.policy}


def validate_content_plan_semantics(plan: dict[str, Any], *, require_page_links=True) -> None:
    """ContentPlan v2 semantics (CONTRACTS §11.2): stable page order, role
    coverage, local issue registry, budget coherence and mode-specific
    requirements. Equality with the committed Document.pages order (mode=bound)
    is checked at the write point that has the document."""
    validate_schema("content_plan", plan)
    if plan.get("schema_version") != "content_plan.v2":
        return
    data = plan.get("input") or {}
    page_order = data.get("page_order") or []
    if len(page_order) != len(set(page_order)):
        raise ModelError("content_plan/input/page_order", "duplicate page ids")
    roles = [role.get("page_id") for role in data.get("page_roles") or []]
    if len(roles) != len(set(roles)):
        raise ModelError("content_plan/input/page_roles", "duplicate page role entries")
    unknown = sorted(set(roles) - set(page_order))
    if unknown:
        raise ModelError("content_plan/input/page_roles", f"roles for pages outside page_order: {unknown}")
    if plan.get("mode") != "imported_mapping" and set(roles) != set(page_order):
        raise ModelError("content_plan/input/page_roles", "every planned page requires exactly one role")
    for chapter in data.get("chapters") or []:
        unknown = sorted(set(chapter.get("page_ids") or []) - set(page_order))
        if unknown:
            raise ModelError(f"content_plan/input/chapters/{chapter.get('chapter_id')}",
                             f"chapter pages outside page_order: {unknown}")
    chapter_pages = [pid for chapter in data.get('chapters') or [] for pid in chapter.get('page_ids') or []]
    if (plan.get('mode') != 'imported_mapping' or chapter_pages) and (
            set(chapter_pages) != set(page_order) or len(chapter_pages) != len(set(chapter_pages))):
        raise ModelError('content_plan/input/chapters', 'chapters cover every planned page exactly once')
    issue_ids = [issue.get("issue_id") for issue in data.get("issues") or []]
    if len(issue_ids) != len(set(issue_ids)):
        raise ModelError("content_plan/input/issues", "duplicate issue_id")
    unknown = sorted(set(data.get("tradeoff_issue_ids") or []) - set(issue_ids))
    if unknown:
        raise ModelError("content_plan/input/tradeoff_issue_ids", f"unknown issue ids: {unknown}")
    budget = data.get("page_budget") or {}
    if (budget.get("exact") is not None and budget.get("max") is not None
            and budget["exact"] > budget["max"]):
        raise ModelError("content_plan/input/page_budget",
                         "exact page budget exceeds the hard max; resolve the tradeoff first")
    if budget.get("exact") is not None and budget["exact"] != len(page_order):
        raise ModelError("content_plan/input/page_budget/exact", "exact page budget must equal page_order count")
    if budget.get("max") is not None and len(page_order) > budget["max"]:
        raise ModelError("content_plan/input/page_budget/max", "page_order exceeds the hard maximum")
    mode = plan.get("mode")
    if mode == "imported_mapping" and not plan.get("imported_manuscript"):
        raise ModelError("content_plan/imported_manuscript",
                         "imported_mapping requires the manuscript source and its claimed-confirmation evidence")
    if plan.get("imported_manuscript"):
        validate_evidence_semantics(plan["imported_manuscript"]["claimed_confirmation_evidence"],
                                    "content_plan/imported_manuscript/claimed_confirmation_evidence")
    if require_page_links and mode in ("bound", "imported_mapping"):
        links = [link.get("page_id") for link in plan.get("page_links") or []]
        if len(links) != len(set(links)) or set(links) != set(page_order):
            raise ModelError("content_plan/page_links",
                             "a bound plan must link every page_order page exactly once")


def validate_compose_result_semantics(result: dict[str, Any]) -> None:
    """Compose v2 envelope shape (CONTRACTS §11.5). Variant payload contents
    are parsed by the task protocol branch; this checks the envelope only."""
    validate_schema("compose_result_v2", result)


WRITER_RANK = {None: 0, "generation.v1": 1, "content-plan.v1": 2,
               "changes.v1": 3, "candidates.v1": 4, "run-desk.v1": 5, "style-recipes.v1": 6, "content-ops.v1": 7,
               "content-candidates.v1": 8, "icon-quality.v1": 9, "workbench-quality.v1": 10,
               "collaboration.v1": 11, "rc3.v1": 12, "rc3-entry.v1": 13, "rc4-content.v1": 14, "method-catalog.v1": 15, "design-policy.v1": 16, "asset-inputs.v1": 17, "original-review.v1": 18}


def require_writer(document, minimum):
    """Advance a feature boundary without downgrading already stored facts."""
    current = document.get("compatibility", {}).get("minimum_writer")
    if current not in WRITER_RANK or minimum not in WRITER_RANK:
        raise ModelError("document/compatibility", "unsupported writer boundary")
    document["compatibility"] = {"project_format": "workbench.v3", "minimum_writer":
                                 current if WRITER_RANK[current] >= WRITER_RANK[minimum] else minimum}


def _writer_rank_of(document) -> int:
    """Unknown/absent writers rank below every named boundary (MIGRATION §2.6:
    one rank comparison helper instead of hand-written writer lists)."""
    return WRITER_RANK.get(document.get("compatibility", {}).get("minimum_writer"), -1)


def writer_at_least(document, minimum: str) -> bool:
    return _writer_rank_of(document) >= WRITER_RANK[minimum]


def collaboration_required(document) -> bool:
    """A feature support floor does not manufacture a historical migration.

    A real region remains mandatory once it exists; the original collaboration
    writer also keeps its mandatory initial-region contract.
    """
    return (document.get('collaboration') is not None or
            document.get('compatibility', {}).get('minimum_writer') in (
                'collaboration.v1', 'rc3-entry.v1', 'rc4-content.v1', 'method-catalog.v1'))


# Central registry of accepted proposal projections (CONTRACTS §3.1). A
# decision binds a registered slice only — never an arbitrary JSONPath; the
# list grows with the cards that introduce new projections (T03/T05/T06).
REGISTERED_PROJECTIONS = (
    "direction", "page_roles", "page_order", "visible_copy", "speech",
    "style.palette", "style.density", "style.typography", "style.composition",
    "style.spacing", "style.lines", "style.icons",
)


def validate_evidence_semantics(evidence: dict[str, Any], where: str) -> None:
    """Evidence shape plus the fixed assurance floors (CONTRACTS §4). Client
    payloads cannot upgrade assurance: the Runtime adapter context is the only
    source that computes verified_user, and this check keeps recorded kinds
    from carrying mismatch assurance (service paths enforce the rest)."""
    floors = {
        "host_attested_instruction": ("host_attested",),
        "imported_unknown": ("unverified",),
        "user_event": ("verified_user",),
        "approved_document": ("unverified", "host_attested"),
        "delegated": ("host_attested",),
    }
    allowed = floors.get(evidence.get("kind"))
    if allowed is not None and evidence.get("assurance") not in allowed:
        raise ModelError(
            f"{where}/assurance",
            f"{evidence.get('kind')} evidence must carry assurance "
            f"{allowed[0]!r}; assurance is never client-upgradable",
        )


def _validate_scope_semantics(scope: dict[str, Any], where: str) -> None:
    page_ids = scope.get("page_ids") or []
    if len(page_ids) != len(set(page_ids)):
        raise ModelError(f"{where}/page_ids", "duplicate page ids in scope")
    layers = scope.get("layers") or []
    if len(layers) != len(set(layers)):
        raise ModelError(f"{where}/layers", "duplicate layers in scope")


def validate_collaboration_region(region: dict[str, Any]) -> None:
    """Structure and record semantics of the single collaboration region
    (CONTRACTS §2). Field completeness and semantic quality are separate
    checks; this one only enforces what the contract fixes structurally."""
    validate_schema("collaboration", region)
    for index, ref in enumerate(region.get("decisions") or []):
        validate_ref(ref, where=f"collaboration/decisions[{index}]")
    for index, ref in enumerate(region.get("authorizations") or []):
        validate_ref(ref, where=f"collaboration/authorizations[{index}]")
    profile = region.get("quality_profile") or {}
    requirement = profile.get("content_review_requirement")
    origin = profile.get("requirement_origin")
    if requirement == "host_self" and not profile.get("override_decision_ref"):
        raise ModelError(
            "collaboration/quality_profile/override_decision_ref",
            "a host_self content-review downgrade must bind the explicit decision that explains it",
        )
    if requirement == "fidelity_only" and origin != "confirmed_manuscript":
        raise ModelError(
            "collaboration/quality_profile/requirement_origin",
            "fidelity_only is only valid for a confirmed-manuscript mapping",
        )
    request = region.get("request")
    if request is not None:
        validate_evidence_semantics(request["instruction_evidence"], "collaboration/request/instruction_evidence")
        _validate_scope_semantics(request["scope"], "collaboration/request/scope")
        if bool(request.get("paused")) != bool(request.get("pause_reason")):
            raise ModelError(
                "collaboration/request/pause_reason",
                "pause_reason must be present exactly when the request is paused",
            )
        if bool(request.get("closed")) != bool(request.get("closed_reason")):
            raise ModelError(
                "collaboration/request/closed_reason",
                "closed_reason must be present exactly when the request is closed",
            )


def validate_decision_semantics(decision: dict[str, Any]) -> None:
    """Decision record semantics (CONTRACTS §3.1). authority_mode names the
    claimed source; trust comes only from evidence.assurance."""
    validate_schema("collaboration_decision", decision)
    validate_evidence_semantics(decision["evidence"], "decision/evidence")
    mode = decision.get("authority_mode")
    if mode == "delegated" and not decision.get("delegation_ref"):
        raise ModelError(
            "decision/delegation_ref",
            "a delegated decision must reference the covering authorization",
        )
    if mode != "delegated" and decision.get("delegation_ref"):
        raise ModelError(
            "decision/delegation_ref",
            "delegation_ref is only valid for authority_mode=delegated",
        )
    _validate_scope_semantics(decision["scope"], "decision/scope")
    for index, proposal in enumerate(decision.get("subject_refs") or []):
        projection = proposal.get("projection")
        if projection not in REGISTERED_PROJECTIONS:
            raise ModelError(
                f"decision/subject_refs[{index}]/projection",
                f"projection {projection!r} is not a registered slice",
            )


def validate_authorization_semantics(authorization: dict[str, Any]) -> None:
    """Authorization record semantics (CONTRACTS §3.2). Every execution grant
    carries an integer call ceiling; delegate mode names its topics."""
    validate_schema("collaboration_authorization", authorization)
    validate_evidence_semantics(authorization["evidence"], "authorization/evidence")
    mode = authorization.get("mode")
    topics = authorization.get("delegated_topics") or []
    if mode == "delegate" and not topics:
        raise ModelError(
            "authorization/delegated_topics",
            "delegate mode must declare the topics it covers",
        )
    if mode == "execute" and topics:
        raise ModelError(
            "authorization/delegated_topics",
            "delegated_topics belong to delegate mode; an execute grant names decisions and scope",
        )
    _validate_scope_semantics(authorization["scope"], "authorization/scope")
    if authorization.get("expires_at") is not None:
        parse_authorization_expiry(authorization["expires_at"])


def parse_authorization_expiry(value):
    """RFC3339-style expiration, with an explicit timezone; never guess local time."""
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None or "T" not in value:
            raise ValueError("timezone required")
    except (TypeError, ValueError, AttributeError) as exc:
        raise ModelError("authorization/expires_at", "expires_at must be a valid timestamp with an explicit timezone") from exc
    return parsed


def validate_document_structure(document: dict[str, Any]) -> None:
    """Schema plus structural checks reachable without loading other objects."""
    validate_schema("document", document)
    if document.get("narrative"):
        validate_ref(document["narrative"], where="document/narrative")
        if (not writer_at_least(document, "collaboration.v1") or
                document.get('collaboration') is None):
            raise ModelError("document/compatibility",
                             "a Narrative pointer requires the collaboration.v1 writer boundary and real control region")
    if document.get("collaboration") is not None:
        if not writer_at_least(document, "collaboration.v1"):
            raise ModelError("document/compatibility",
                             "the collaboration region requires the collaboration.v1 writer boundary")
        validate_collaboration_region(document["collaboration"])
    elif collaboration_required(document):
        raise ModelError("document/collaboration",
                         "the collaboration.v1 writer boundary requires the collaboration region")
    if document.get("content_plan"):
        validate_ref(document["content_plan"], where="document/content_plan")
        if not writer_at_least(document, "content-plan.v1"):
            raise ModelError("document/compatibility", "content plans require the content-plan.v1 writer boundary")
    receipt = (document.get("change") or {}).get("operation_receipt")
    if receipt is not None and receipt["response"]["revision_id"] != document["revision_id"]:
        raise ModelError("document/change/operation_receipt/response/revision_id",
                         "operation receipt must name its own Document revision")
    if (document.get("annotations") or document.get("changes") or document.get("change", {}).get("operation_commit")):
        if not writer_at_least(document, "changes.v1"):
            raise ModelError("document/compatibility", "change records require the changes.v1 writer boundary")
    if document.get('candidates') or document.get('candidate_adoptions'):
        if not writer_at_least(document, "candidates.v1"):
            raise ModelError('document/compatibility', 'candidate records require the candidates.v1 writer boundary')

    if document.get("style_recipes") and not writer_at_least(document, "style-recipes.v1"):
        raise ModelError("document/compatibility", "style recipes require the style-recipes.v1 writer boundary")
    if document.get("page_derivations"):
        if not writer_at_least(document, "content-ops.v1"):
            raise ModelError("document/compatibility", "page derivations require content-ops.v1")
        for ref in document["page_derivations"]:
            validate_ref(ref, where="document/page_derivations")
    if document.get("icon_recipes"):
        if not writer_at_least(document, "icon-quality.v1"):
            raise ModelError("document/compatibility", "icon recipes require icon-quality.v1")
        for ref in document["icon_recipes"]: validate_ref(ref, where="document/icon_recipes")
    if document.get("style_references") or document.get("committed_at"):
        if document.get("compatibility", {}).get("project_format") == "workbench.v3" and not writer_at_least(document, "workbench-quality.v1"):
            raise ModelError("document/compatibility", "new workbench facts require workbench-quality.v1")
        for ref in document.get("style_references", []):
            validate_ref(ref, where="document/style_references")
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
    updated = {
        **document,
        "revision_id": uuid.uuid4().hex,
        "parent_revision_id": document["revision_id"],
        "change": change,
    }
    if document.get("compatibility", {}).get("project_format") == "workbench.v3":
        from datetime import datetime, timezone
        updated["committed_at"] = datetime.now(timezone.utc).isoformat()
        require_writer(updated, "workbench-quality.v1")
    return updated



CONTENT_KEYS = ("project_id", "task", "sources", "pages", "design_context", "policy", "outputs")


def content_identity(document: dict[str, Any]) -> str:
    """Hash of the content a Host task depends on — revision/task-list agnostic.

    Task-management revisions (dispatch, claim, allocation) never move this
    identity; an adopted result or a real content change does. Accept uses it
    to decide whether work is still fresh, without blocking legitimate claims.
    """
    projection = {key: document.get(key) for key in CONTENT_KEYS}
    if document.get("content_plan"):
        projection["content_plan"] = document["content_plan"]
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
