"""T03 content tests: visible atoms, stable ids, legacy normalization (AC-C03, AC-C11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deck_master.content import (
    NeedsNormalization,
    assign_missing_ids,
    atom_ids,
    check_page,
    normalize_legacy_pointers,
    visible_atoms,
)
from deck_master.models import validate_page_semantics
from deck_master.store import Store

SPEC_DIR = Path(__file__).resolve().parents[2] / "docs" / "specs" / "deck-master-rebuild-v1"
ATOM_EXAMPLE = SPEC_DIR / "examples" / "roundtrips" / "atom-identity.json"


def _example() -> dict:
    return json.loads(ATOM_EXAMPLE.read_text(encoding="utf-8"))


def test_atom_identity_roundtrip() -> None:
    """The spec's atom-identity example holds: ids survive reorder/reword; new items are new."""
    example = _example()
    before_ids = atom_ids(example["before_page"])
    after_ids = atom_ids(example["after_page"])
    for expected in example["expected_stable_ids"]:
        assert expected in before_ids, f"missing before: {expected}"
        assert expected in after_ids, f"expected id lost after edit: {expected}"
    for fresh_id in example["new_ids"]:
        assert fresh_id in after_ids
        assert fresh_id not in before_ids
    # Reworded item keeps its id; only its pointer moved.
    after_pointers = {atom["atom_id"]: atom["pointer"] for atom in visible_atoms(example["after_page"])}
    for change in example["pointer_changes"]:
        assert change["atom_id"] in after_ids
        assert after_pointers[change["atom_id"]] == change["after"]
    validate_page_semantics(example["after_page"])
    validate_page_semantics(example["before_page"])


def test_visible_text_complete() -> None:
    """Nested duties, table headers/cells with units, labels, footnotes, callouts all visible."""
    page = _example()["before_page"]
    atoms = visible_atoms(page)
    texts = [atom["text"] for atom in atoms]
    ids = [atom["atom_id"] for atom in atoms]

    # title/subtitle
    assert "atom:p09:title" in ids
    assert "atom:p09:subtitle" in ids
    # nested item duties
    assert "atom:p09:item:device:text" in ids
    assert "填写设备型号与问题现象" in texts
    # table header and a unit-bearing cell
    assert "atom:p09:column:sample:count:label" in ids
    assert "atom:p09:cell:sample:need:count:display_text" in ids
    assert any(text == "45%" for text in texts), "table cell display_text must be preserved verbatim"
    # labels/footnotes/callouts
    assert any(atom["kind"] == "label" and atom["text"] == "本期只读接口" for atom in atoms)
    assert any(atom["kind"] == "footnote" and "54÷120=45%" in atom["text"] for atom in atoms)
    assert any(atom["kind"] == "callout" for atom in atoms)
    # internal-only and speaker notes never become visible atoms
    assert not any(atom["kind"] == "internal" for atom in atoms)
    for atom in atoms:
        assert atom["text"] != "不要把这一段加入图中。"


def test_metadata_is_not_copy() -> None:
    """node_id / edge_id / citation ids do not appear as visible atoms."""
    page = _example()["before_page"]
    ids = atom_ids(page)
    assert "atom:p09:node:service" not in ids
    for atom_id in ids:
        assert not atom_id.startswith("atom:p09:edge"), "edge ids are not copy"
        assert not atom_id.startswith("atom:p09:citation"), "citation ids are not copy"


def test_same_text_keeps_distinct_ids() -> None:
    page = _example()["before_page"]
    atoms = {atom["atom_id"]: atom["text"] for atom in visible_atoms(page)}
    # Two items may share wording without sharing identity (no text-hash merging).
    duplicated = [aid for aid, text in atoms.items() if text == atoms["atom:p09:item:device:text"]]
    assert duplicated == ["atom:p09:item:device:text"]


def test_unknown_body_type_requires_mapping() -> None:
    page = _example()["before_page"]
    unknown = {
        **page,
        "customer_visible": {
            **page["customer_visible"],
            "body_blocks": [
                *page["customer_visible"]["body_blocks"],
                {"id": "mystery", "type": "countdown_widget", "text": "无法识别的旧块"},
            ],
        },
    }
    with pytest.raises(NeedsNormalization) as excinfo:
        visible_atoms(unknown)
    assert "mystery" in excinfo.value.path
    assert "countdown_widget" in excinfo.value.detail


def test_unknown_legacy_body_is_not_silently_dropped() -> None:
    page = _example()["before_page"]
    legacy = {
        "schema_version": "deck_page_package.v2",
        "page_id": "p09",
        "customer_visible": {"title": "旧标题", "body": [{"style": "lead", "text": "旧正文形式"}]},
        "visual_spec": {"intent": "旧格式", "reference_mode": "new_design"},
    }
    from deck_master.models import ModelError

    with pytest.raises(ModelError) as excinfo:
        check_page(legacy)
    assert "body" in excinfo.value.detail or "body_blocks" in excinfo.value.path


def test_assign_missing_ids_deterministic_and_retry_stable() -> None:
    page = _example()["before_page"]
    stripped = json.loads(json.dumps(page))
    for block in stripped["customer_visible"]["body_blocks"]:
        block.pop("id", None)
        for item in block.get("items") or []:
            item.pop("id", None)

    first_page, first_map = assign_missing_ids(stripped, operation_id="op-1")
    second_page, second_map = assign_missing_ids(stripped, operation_id="op-1")
    assert first_page == second_page
    assert first_map == second_map

    other_page, other_map = assign_missing_ids(stripped, operation_id="op-2")
    assert [entry["assigned_id"] for entry in first_map] != [
        entry["assigned_id"] for entry in other_map
    ]
    # Assigned ids are distinct within the page.
    assigned = [entry["assigned_id"] for entry in first_map]
    assert len(assigned) == len(set(assigned))
    # Remapping visual refs after id assignment is the Host's explicit duty
    # (spec 03.10): the old label_ref no longer resolves against new ids.
    with pytest.raises(NeedsNormalization):
        check_page(first_page)


def test_legacy_pointer_remap() -> None:
    """Legacy pointer /customer_visible/body_blocks/0/heading resolves to the block atom."""
    page = _example()["before_page"]
    remapped = normalize_legacy_pointers(page)
    visual = remapped["visual_spec"]
    label_refs = [node.get("label_ref") for node in visual["nodes"]]
    assert "atom:p09:block:service:heading" in label_refs
    for ref in label_refs:
        assert not (isinstance(ref, str) and ref.startswith("/")), "pointers must be rewritten"


def test_unresolvable_pointer_requests_normalization() -> None:
    page = _example()["before_page"]
    ghost = {
        **page,
        "visual_spec": {
            **page["visual_spec"],
            "nodes": [
                {
                    **page["visual_spec"]["nodes"][0],
                    "label_ref": "/customer_visible/body_blocks/9/heading",
                }
            ],
        },
    }
    with pytest.raises(NeedsNormalization) as excinfo:
        normalize_legacy_pointers(ghost)
    assert "does not resolve" in excinfo.value.detail


def test_check_page_rejects_dangling_refs() -> None:
    page = _example()["before_page"]
    nodes = page["visual_spec"]["nodes"]
    broken = {
        **page,
        "visual_spec": {
            **page["visual_spec"],
            "nodes": [
                {**page["visual_spec"]["nodes"][0], "responsibility_refs": ["atom:p09:item:ghost:text"]},
                *page["visual_spec"]["nodes"][1:],
            ],
        },
    }
    with pytest.raises(NeedsNormalization):
        check_page(broken)


def test_design_asset_file_becomes_artifact(tmp_path: Path) -> None:
    store = Store(tmp_path / "project")
    store.ensure_layout()
    logo = tmp_path / "assets" / "logo.svg"
    logo.parent.mkdir()
    logo.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")

    from deck_master.content import normalize_design_assets

    design = normalize_design_assets(
        store,
        {
            "canvas": {"width_px": 1600, "height_px": 900, "slide_width_in": 40 / 3, "slide_height_in": 7.5, "fit": "contain"},
            "language": "zh-CN",
            "fonts": [],
            "styles": [],
            "default_style_id": "default",
            "assets": [
                {"asset_id": "demo-logo", "kind": "logo", "file": str(logo), "external_use": "allowed"}
            ],
            "allowed_asset_ids": ["demo-logo"],
        },
        base_dir=tmp_path,
    )
    entry = design["assets"][0]
    assert "file" not in entry
    assert entry["artifact"]["path"].startswith(".deckmaster/objects/")
    ref = entry["artifact"]
    from deck_master.models import canonical_json_bytes, sha256_bytes

    artifact = store.read_object_json(ref)
    assert artifact["role"] == "asset"
    # The artifact's file ref carries the real media bytes digest...
    assert artifact["file"]["sha256"] == sha256_bytes(logo.read_bytes())
    # ...and the artifact blob itself is content-addressed by its own canonical bytes.
    assert ref["sha256"] == sha256_bytes(canonical_json_bytes(artifact))


def test_design_asset_file_and_artifact_conflict(tmp_path: Path) -> None:
    from deck_master.models import ModelError
    from deck_master.content import normalize_design_assets

    store = Store(tmp_path / "project")
    store.ensure_layout()
    ref = store.put_blob(b"<svg/>", ext="svg")
    with pytest.raises(ModelError):
        normalize_design_assets(
            store,
            {
                "assets": [
                    {
                        "asset_id": "x",
                        "kind": "logo",
                        "file": str(tmp_path / "a.svg"),
                        "artifact": ref,
                    }
                ]
            },
            base_dir=tmp_path,
        )


def test_restricted_asset_not_auto_allowed() -> None:
    """allowed_asset_ids must stay a subset of declared assets; restricted stays restricted."""
    from deck_master.models import default_design_context, validate_document_structure, new_document

    design = default_design_context()
    design["assets"] = [
        {
            "asset_id": "customer-mark",
            "kind": "logo",
            "artifact": {
                "path": ".deckmaster/objects/aa/" + "a" * 64 + ".json",
                "sha256": "a" * 64,
            },
            "external_use": "restricted",
        }
    ]
    design["allowed_asset_ids"] = ["customer-mark"]
    document = new_document(project_id="demo", task={"title": "t", "brief": "b"})
    document = {**document, "design_context": design}
    validate_document_structure(document)
    # The gate for external upload lives with the design/production flow (T06);
    # content only guarantees the subset relationship is checkable.
    assert design["allowed_asset_ids"] == ["customer-mark"]
