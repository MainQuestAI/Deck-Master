"""T02 contract tests: five valid objects and cross-reference negatives."""

from __future__ import annotations

import pytest

from deck_master.models import (
    ModelError,
    canonical_json_bytes,
    default_design_context,
    new_document,
    sha256_bytes,
    validate_artifact_semantics,
    validate_ref,
    validate_document_semantics,
    validate_page_semantics,
    validate_review_semantics,
    validate_task_semantics,
)

OBJECT_REF = {
    "path": ".deckmaster/objects/aa/" + "a" * 64 + ".json",
    "sha256": "a" * 64,
}


def _valid_page() -> dict:
    return {
        "schema_version": "deck_page_package.v2",
        "page_id": "p01",
        "customer_visible": {
            "title": "架构页",
            "body_blocks": [
                {
                    "id": "layer",
                    "type": "bullets",
                    "heading": "平台层",
                    "items": [
                        {"id": "engine", "text": "工单引擎自动分派"},
                        {"id": "knowledge", "text": "知识库返回引用"},
                    ],
                }
            ],
        },
        "speaker_notes": "合成样本。",
        "visual_spec": {
            "intent": "两层结构，双向关系可见。",
            "layout_hint": "上下两框。",
            "reference_mode": "new_design",
            "nodes": [
                {
                    "node_id": "platform",
                    "label_ref": "atom:p01:block:layer:heading",
                    "status": "proposed",
                    "responsibility_refs": [
                        "atom:p01:item:engine:text",
                        "atom:p01:item:knowledge:text",
                    ],
                }
            ],
            "edges": [
                {
                    "edge_id": "link",
                    "from": "platform",
                    "to": "platform",
                    "direction": "both",
                    "relationship": "互调",
                }
            ],
            "style_ref": "default",
        },
    }


def _valid_task() -> dict:
    return {
        "schema_version": "deck_task.v1",
        "task_id": "task-1",
        "operation_id": "op-1",
        "kind": "compose",
        "status": "awaiting_host",
        "scope_pages": [],
        "instruction": "写完第一页正文。",
        "inputs": [],
        "dependencies": [],
        "dispatch_revision": "rev-1",
        "produced_against": sha256_bytes(b"rev-1"),
        "result_refs": [],
        "error": None,
        "execution_ref": None,
        "created_at": "2026-09-16T00:00:00Z",
        "updated_at": "2026-09-16T00:00:00Z",
        "cost_class": "host_reasoning",
        "usage": {"source": "not_reported", "external_calls": None},
        "call_allowances": [
            {
                "allowance_id": "call-1",
                "state": "reserved",
                "execution_ref": None,
                "invocation_ref": None,
                "evidence": [],
            }
        ],
    }


def _valid_artifact() -> dict:
    return {
        "schema_version": "deck_artifact.v1",
        "artifact_id": "art-1",
        "page_id": "p01",
        "role": "blueprint",
        "file": OBJECT_REF,
        "media_type": "image/png",
        "created_at": "2026-09-16T00:00:00Z",
        "dependencies": [
            {"kind": "content", "identity": "atom:p01:title", "sha256": "b" * 64}
        ],
        "derived_from": [],
        "provenance": {"source_type": "unknown"},
        "reference_regions": [
            {
                "region_id": "r1",
                "description": "平台层模块区",
                "bbox_normalized": [0.1, 0.2, 0.5, 0.4],
                "importance": "essential",
            }
        ],
        "limitations": [],
        "editability": "unknown",
    }


def _valid_review() -> dict:
    return {
        "schema_version": "deck_review.v1",
        "review_id": "rev-obj-1",
        "kind": "conversion",
        "status": "fail",
        "subjects": [OBJECT_REF],
        "dependencies": [],
        "reviewer": {
            "type": "tool",
            "id": "pixel-check",
            "execution_ref": None,
            "independence_confirmed": False,
        },
        "observations": [],
        "findings": [],
        "created_at": "2026-09-16T00:00:00Z",
        "replaces": None,
    }


def test_five_valid_objects() -> None:
    document = new_document(
        project_id="demo",
        task={"title": "Demo deck", "brief": "Build a demo deck."},
    )
    page = _valid_page()
    task = _valid_task()
    artifact = _valid_artifact()
    review = _valid_review()
    validate_document_semantics(document)
    validate_page_semantics(page)
    validate_task_semantics(task)
    validate_artifact_semantics(artifact)
    validate_review_semantics(review)
    # Canonical encoding is stable and hash-consistent.
    blob = canonical_json_bytes(document)
    assert sha256_bytes(blob) == sha256_bytes(canonical_json_bytes(document))
    assert default_design_context()["canvas"]["width_px"] == 1600


def test_invalid_references_report_paths() -> None:
    # Duplicate page ids
    document = new_document(
        project_id="demo",
        task={"title": "t", "brief": "b"},
    )
    page_entry_slots = {"blueprint": None, "svg": None, "svg_preview": None, "ppt_preview": None}
    bad_document = {
        **document,
        "pages": [
            {"page_id": "p01", "page": OBJECT_REF, **page_entry_slots},
            {"page_id": "p01", "page": OBJECT_REF, **page_entry_slots},
        ],
    }
    with pytest.raises(ModelError) as excinfo:
        validate_document_semantics(bad_document)
    assert "duplicate page_id" in excinfo.value.detail

    # Cross-project / escaping object path
    escaping_ref = {"path": "../outside.json", "sha256": "a" * 64}
    with pytest.raises(ModelError) as excinfo:
        validate_ref(escaping_ref, where="document/pages/p01/page")
    assert ".deckmaster/objects" in excinfo.value.detail

    # Zero digest is never a valid unknown
    with pytest.raises(ModelError):
        validate_ref({"path": ".deckmaster/objects/00/" + "0" * 64 + ".json", "sha256": "0" * 64}, where="x")

    # Edge with missing endpoint
    page = _valid_page()
    page = {
        **page,
        "visual_spec": {
            **page["visual_spec"],
            "edges": [
                {
                    "edge_id": "bad",
                    "from": "ghost",
                    "to": "platform",
                    "direction": "forward",
                    "relationship": "幽灵端点",
                }
            ],
        },
    }
    with pytest.raises(ModelError) as excinfo:
        validate_page_semantics(page)
    assert "edges/bad" in excinfo.value.path

    # allowed_asset_ids referencing undeclared asset
    design = default_design_context()
    design["allowed_asset_ids"] = ["nope"]
    from deck_master.models import validate_document_structure

    with pytest.raises(ModelError) as excinfo:
        validate_document_structure({**document, "design_context": design})
    assert "allowed_asset_ids" in excinfo.value.path

    # Fallback cycle
    design = default_design_context()
    design["fonts"] = [
        {"font_id": "a", "family": "A", "face": "R", "weight": 400, "asset_id": None, "fallback_font_ids": ["b"]},
        {"font_id": "b", "family": "B", "face": "R", "weight": 400, "asset_id": None, "fallback_font_ids": ["a"]},
    ]
    design["styles"] = [
        {
            "style_id": "s",
            "colors": {"ink": "#14213D"},
            "typography": {
                "body_font_id": "a",
                "heading_font_id": "b",
                "body_size_pt": 18,
                "heading_size_pt": 30,
                "auxiliary_size_pt": 12,
            },
            "layout_notes": "cycle probe",
        }
    ]
    design["default_style_id"] = "s"
    with pytest.raises(ModelError) as excinfo:
        validate_document_structure({**document, "design_context": design})
    assert "fallback cycle" in excinfo.value.detail

    # bbox with zero area
    artifact = _valid_artifact()
    artifact = {
        **artifact,
        "reference_regions": [
            {"region_id": "r", "description": "零面积反例", "bbox_normalized": [0.5, 0.5, 0.0, 0.2], "importance": "essential"}
        ],
    }
    with pytest.raises(ModelError) as excinfo:
        validate_artifact_semantics(artifact)
    assert "positive area" in excinfo.value.detail
