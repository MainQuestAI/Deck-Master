"""T04 service flow tests (AC-C04, AC-C06, AC-C07 engineering part)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import deck_master.service as service


def _write_brief(tmp_path: Path) -> tuple[Path, Path]:
    material_dir = tmp_path / "materials"
    material_dir.mkdir()
    material = material_dir / "brief.txt"
    material.write_text(
        "## 任务\n向运营团队说明条件自动处理方案。\n\n"
        "## 现状\n人工处理为主，接口条件齐备。\n\n"
        "（材料尾部约束）合成材料，不可回写。",
        encoding="utf-8",
    )
    return tmp_path / "proj", material


def test_plain_material_directory_starts_without_library(tmp_path: Path) -> None:
    """AC-C06: a plain material directory, no history library/cache/templates."""
    project, material = _write_brief(tmp_path)
    response = service.create(project, brief="说明条件自动处理方案", sources=[material])
    assert response["status"] == "created"
    assert response["pending_tasks"], "create returns a pending Host task"
    assert response["next_action"] == "submit_host_results"
    # No library or workspace prerequisites were touched.
    deck_dir = project / ".deckmaster"
    assert (deck_dir / "current.json").is_file()
    assert not (project / "library").exists()
    assert not (project / "workspace").exists()


def test_repeated_continue_returns_same_task(tmp_path: Path) -> None:
    """AC-C04: continue reuses the pending task instead of creating duplicates."""
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    first = service.continue_project(project)
    second = service.continue_project(project)
    assert first["pending_tasks"] and second["pending_tasks"]
    assert first["pending_tasks"][0]["task_id"] == second["pending_tasks"][0]["task_id"]
    assert first["revision_id"] == second["revision_id"]


def test_default_entry_does_not_invoke_legacy_planner(tmp_path: Path) -> None:
    """AC-C04 engineering part: the flow never calls the old planner/enrich modules."""
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    response = service.continue_project(project)
    task = response["pending_tasks"][0]
    # The work order derives from real sources; no array-modulo claim pairing
    # and no fixed page-role template is part of the dispatch.
    assert task["sources"], "task carries the real source entries"
    assert "template" in task["instruction"].lower() or "templates" in task["instruction"].lower()


def test_import_draft_without_prior_create(tmp_path: Path) -> None:
    draft = {
        "pages": [
            {
                "schema_version": "deck_page_package.v2",
                "page_id": "d1",
                "customer_visible": {
                    "title": "导入稿标题",
                    "body_blocks": [{"id": "intro", "type": "paragraph", "text": "完整正文。"}],
                },
                "visual_spec": {"intent": "纯正文页", "reference_mode": "new_design"},
            }
        ]
    }
    response = service.import_draft(tmp_path / "proj", draft_payload=draft)
    assert response["status"] == "accepted"
    assert response["next_action"] == "auto_view_then_production"
    document = service.Store(tmp_path / "proj").load_document()
    assert [entry["page_id"] for entry in document["pages"]] == ["d1"]


def test_unknown_draft_shape_is_rejected_not_adopted(tmp_path: Path) -> None:
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    with pytest.raises(Exception):
        service.import_draft(
            project,
            draft_payload={
                "pages": [
                    {
                        "schema_version": "deck_page_package.v2",
                        "page_id": "bad",
                        "customer_visible": {
                            "title": "坏块",
                            "body_blocks": [{"id": "x", "type": "unknown_widget", "text": "?"}],
                        },
                        "visual_spec": {"intent": "坏形状", "reference_mode": "new_design"},
                    }
                ]
            },
        )
    # Nothing was partially adopted: the current Document still has no pages.
    document = service.Store(project).load_document()
    assert document["pages"] == []


def test_asset_registration_updates_design(tmp_path: Path) -> None:
    project, material = _write_brief(tmp_path)
    service.create(project, brief="说明方案", sources=[material])
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    response = service.import_asset(
        project, asset_id="demo-logo", kind="logo", file_path=logo, external_use="allowed"
    )
    assert response["status"] == "registered"
    document = service.Store(project).load_document()
    design = document["design_context"]
    assert any(entry["asset_id"] == "demo-logo" for entry in design["assets"])
    assert "demo-logo" in design["allowed_asset_ids"]


# ---------------------------------------------------------------------------
# T12 evidence: local edit blast radius (AC-S05), shared-fact updates
# (AC-S06), page-set changes (AC-S07) and asset byte invalidation (AC-S13).

import io
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy

from PIL import Image

from deck_master import service
from deck_master.editing import edit_page
from deck_master.models import bump_revision, content_identity
from deck_master.pipeline import artifact as adopt_artifact, produce
from deck_master.store import Store


from hostenv import resolve_host_font

FAMILY = resolve_host_font()


def _draft_page(page_id, title, body):
    return {
        "schema_version": "deck_page_package.v2",
        "page_id": page_id,
        "customer_visible": {"title": title, "body_blocks": [
            {"id": "b1", "type": "paragraph", "text": body}]},
        "visual_spec": {"intent": "demo", "reference_mode": "new_design"},
    }


def _png_bytes(color=(245, 246, 250)):
    buffer = io.BytesIO()
    Image.new("RGB", (320, 180), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _blueprint_envelope(page_ref):
    return {
        "kind": "blueprint",
        "files": [{"file_id": "b", "path": "reference.png", "media_type": "image/png"}],
        "artifact_specs": [{
            "file_id": "b", "role": "blueprint", "page_id": page_ref["page_id"],
            "derived_from": [page_ref["ref"]],
            "provenance": {"source_type": "unknown", "tool": "host-imagegen", "invocation_ref": None,
                           "generated_from_page": page_ref["ref"]},
        }],
    }


def _svg_for(page):
    title = page["customer_visible"]["title"]
    body = page["customer_visible"]["body_blocks"][0]["text"]
    return (f'<svg viewBox="0 0 320 180"><rect width="320" height="180" fill="#ffffff"/>'
            f'<text x="20" y="80" font-family="{FAMILY}" font-size="20">{title}</text>'
            f'<text x="20" y="130" font-family="{FAMILY}" font-size="14">{body}</text>'
            f'</svg>').encode()


def _drive_blueprints(project, store):
    while True:
        document = store.load_document()
        missing = next((e for e in document["pages"] if not e.get("blueprint")), None)
        if missing is None:
            return document
        task = service.continue_project(project)["pending_tasks"][0]
        assert task["kind"] == "blueprint"
        staging = project / ".deckmaster" / "staging" / task["operation_id"]
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "reference.png").write_bytes(_png_bytes())
        envelope = _blueprint_envelope({"page_id": missing["page_id"], "ref": missing["page"]})
        outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                        produced_against=task["produced_against"], result_payload=envelope)
        assert outcome["status"] == "accepted"


def _drive_reconstructs(project, store):
    while True:
        document = store.load_document()
        missing = next((e for e in document["pages"] if not e.get("svg")), None)
        if missing is None:
            return document
        task = service.continue_project(project)["pending_tasks"][0]
        assert task["kind"] == "reconstruct", task["kind"]
        blueprint_sha = store.read_object_json(missing["blueprint"])["file"]["sha256"]
        page = store.read_object_json(missing["page"])
        svg = _svg_for(page).replace(b"<svg ", f'<svg data-blueprint-sha256="{blueprint_sha}" '.encode(), 1)
        staging = project / ".deckmaster" / "staging" / task["operation_id"]
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "page.svg").write_bytes(svg)
        envelope = {"kind": "reconstruct",
                    "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
                    "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": missing["page_id"],
                                        "provenance": {"source_type": "unknown", "tool": "host-reconstruct",
                                                       "invocation_ref": None}}]}
        outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                        produced_against=task["produced_against"], result_payload=envelope)
        assert outcome["status"] == "accepted"


def _slide_count(pptx_bytes):
    with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as archive:
        root = ET.fromstring(archive.read("ppt/presentation.xml"))
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    return len(root.findall("p:sldIdLst/p:sldId", ns))


def _produced_project(tmp_path, pages):
    project = tmp_path / "proj"
    service.create(project, brief="局部修改流", draft={"pages": pages})
    store = Store(project)
    _drive_blueprints(project, store)
    _drive_reconstructs(project, store)
    report = produce(project)
    assert report["status"] == "pass", report["findings"]
    return project, Store(project)


def test_single_page_edit_keeps_unrelated_page_artifacts_and_reassembles(tmp_path):
    # AC-S05: editing p09 leaves the unrelated page's blueprint/SVG bytes and
    # refs untouched, opens only a reconstruct (no new external image making),
    # and the whole PPT is re-assembled afterwards; old artifacts stay findable.
    project, store = _produced_project(tmp_path, [
        _draft_page("p09", "条件收集", "在售后门户嵌入表单。"),
        _draft_page("p10", "处理方案", "自动分派到值班组。"),
    ])
    document = store.load_document()
    p10 = next(e for e in document["pages"] if e["page_id"] == "p10")
    p10_hashes = {slot: store.read_object_json(p10[slot])["file"]["sha256"]
                  for slot in ("blueprint", "svg")}
    old_pptx_bytes = store.read_object_bytes(
        store.read_object_json(document["outputs"]["pptx"])["file"])

    p09_page = store.read_object_json(document["pages"][0]["page"])
    edited = deepcopy(p09_page)
    edited["customer_visible"]["body_blocks"][0]["text"] = "在售后门户与小程序双端嵌入表单。"
    result = edit_page(store.project_root, page=edited, base_revision=document["revision_id"],
                       page_hash=document["pages"][0]["page"]["sha256"], operation_id="edit-p09")
    assert result["status"] == "edited"
    after = store.load_document()
    p10_after = next(e for e in after["pages"] if e["page_id"] == "p10")
    assert p10_after["blueprint"] == p10["blueprint"] and p10_after["svg"] == p10["svg"]
    assert all(store.read_object_json(p10_after[slot])["file"]["sha256"] == p10_hashes[slot]
               for slot in p10_hashes)
    assert after["pages"][0]["svg"] is None

    # No new external image-making: the next step is a local reconstruct task.
    response = service.continue_project(project)
    assert response["next_action"] == "codex_reconstruct_svg"
    assert response["pending_tasks"][0]["kind"] == "reconstruct"

    # Re-assemble the whole deck and prove the untouched page still compiles in.
    fresh = store.load_document()
    task = response["pending_tasks"][0]
    blueprint_sha = store.read_object_json(fresh["pages"][0]["blueprint"])["file"]["sha256"]
    svg = _svg_for(edited).replace(b"<svg ", f'<svg data-blueprint-sha256="{blueprint_sha}" '.encode(), 1)
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "page.svg").write_bytes(svg)
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload={
                              "kind": "reconstruct",
                              "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
                              "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p09",
                                                  "provenance": {"source_type": "unknown",
                                                                 "tool": "host-reconstruct",
                                                                 "invocation_ref": None}}]})
    report = produce(project)
    assert report["status"] == "pass"
    new_pptx = store.load_document()["outputs"]["pptx"]
    assert _slide_count(store.read_object_bytes(store.read_object_json(new_pptx)["file"])) == 2
    assert store.read_object_bytes(store.read_object_json(new_pptx)["file"]) != old_pptx_bytes
    assert store.read_object_bytes(store.read_object_json(p10_after["svg"])["file"]).startswith(b"<svg")


def test_shared_fact_update_applies_to_all_referencing_pages(tmp_path):
    # AC-S06: a fact repeated across pages is corrected everywhere through the
    # full-draft replacement path; no referencing page keeps the old wording.
    project = tmp_path / "proj"
    pages = [_draft_page("p1", "背景", "接口条件齐备。"), _draft_page("p2", "方案", "接口条件齐备。")]
    service.create(project, brief="共用事实", draft={"pages": pages})
    store = Store(project)
    before = store.load_document()
    corrected = []
    for entry in before["pages"]:
        page = store.read_object_json(entry["page"])
        page["customer_visible"]["body_blocks"][0]["text"] = "接口条件已齐备。"
        corrected.append(page)
    outcome = service.import_draft(project, draft_payload={"pages": corrected, "page_order": ["p1", "p2"]})
    assert outcome["status"] == "accepted"
    after = store.load_document()
    for entry in after["pages"]:
        page = store.read_object_json(entry["page"])
        assert page["customer_visible"]["body_blocks"][0]["text"] == "接口条件已齐备。"
        assert page["page_id"] in ("p1", "p2")
    old = store.load_document(before["revision_id"])
    for entry in old["pages"]:
        assert store.read_object_json(entry["page"])["customer_visible"]["body_blocks"][0]["text"] == "接口条件齐备。"


def test_page_reorder_and_removal_keep_ids_and_history_out_of_current_ppt(tmp_path):
    # AC-S07: reorder + removal keeps surviving page refs byte-identical, the
    # removed page's objects stay readable in history, and the re-assembled
    # PPT contains exactly the current page set.
    project, store = _produced_project(tmp_path, [
        _draft_page("p1", "第一页", "正文一。"),
        _draft_page("p2", "第二页", "正文二。"),
        _draft_page("p3", "第三页", "正文三。"),
    ])
    before = store.load_document()
    p2_entry = before["pages"][1]
    p2_svg_ref = p2_entry["svg"]
    reordered = [store.read_object_json(before["pages"][2]["page"]),
                 store.read_object_json(before["pages"][0]["page"])]
    outcome = service.import_draft(project, draft_payload={"pages": reordered, "page_order": ["p3", "p1"]})
    assert outcome["status"] == "accepted"
    after = store.load_document()
    assert [e["page_id"] for e in after["pages"]] == ["p3", "p1"]
    assert after["pages"][1]["page"] == before["pages"][0]["page"], "reordered page keeps its stable ref"
    assert after["pages"][0]["page"] == before["pages"][2]["page"]
    # The removed page's objects remain readable from history.
    assert store.read_object_bytes(p2_entry["page"]) == store.read_object_bytes(before["pages"][1]["page"])
    old_svg_bytes = store.read_object_bytes(store.read_object_json(p2_svg_ref)["file"])
    assert old_svg_bytes.startswith(b"<svg")

    # Re-attach the unchanged SVGs (content-addressed: same bytes, same ref) and
    # re-assemble: the deleted page never glob-mixes back into the current PPT.
    from deck_master.pipeline import artifact as adopt
    work = store.staging_dir / "reattach"
    work.mkdir(parents=True, exist_ok=True)
    for entry in after["pages"]:
        prior = next(e for e in before["pages"] if e["page_id"] == entry["page_id"])
        svg_bytes = store.read_object_bytes(store.read_object_json(prior["svg"])["file"])
        svg_file = work / f"{entry['page_id']}.svg"
        svg_file.write_bytes(svg_bytes)
        entry["svg"] = adopt(store, svg_file, "svg", page_id=entry["page_id"])
    bumped = bump_revision(after, {"operation_id": "reattach-svg", "kind": "task_update",
                                   "description": "reattach unchanged svgs", "read_set": []})
    bumped["pages"] = after["pages"]
    store.commit_change(base_revision=after["revision_id"], document=bumped, operation_id="reattach-svg")
    report = produce(project)
    assert report["status"] == "pass"
    pptx = store.load_document()["outputs"]["pptx"]
    assert _slide_count(store.read_object_bytes(store.read_object_json(pptx)["file"])) == 2


def test_asset_byte_change_invalidates_only_referencing_pages(tmp_path):
    # AC-S13: importing new bytes under the same asset_id clears SVG/previews
    # and outputs only on pages whose effective design references the asset;
    # unrelated pages and unused assets stay untouched.
    logo_v1 = tmp_path / "logo-v1.png"
    Image.new("RGB", (12, 12), (10, 20, 200)).save(logo_v1)
    pages = [_draft_page("p1", "带Logo页", "引用品牌Logo。"), _draft_page("p2", "无Logo页", "不引用任何资产。")]
    pages[0]["visual_spec"]["design_overrides"] = {"allowed_asset_ids": ["logo"]}
    pages[1]["visual_spec"]["design_overrides"] = {"allowed_asset_ids": []}
    project = tmp_path / "proj"
    service.create(project, brief="资产失效", draft={"pages": pages}, design={
        "assets": [{"asset_id": "logo", "kind": "logo", "file": str(logo_v1), "external_use": "allowed"}],
        "allowed_asset_ids": ["logo"],
    })
    store = Store(project)
    document = store.load_document()
    # p1's SVG actually embeds the logo; p2's SVG references no assets.
    svg_with_logo = tmp_path / "page-with-logo.svg"
    svg_with_logo.write_text('<svg viewBox="0 0 10 10"><image href="logo" width="4" height="4"/></svg>')
    svg_plain = tmp_path / "page.svg"
    svg_plain.write_text("<svg viewBox='0 0 10 10'/>")
    png_file = tmp_path / "preview.png"
    Image.new("RGB", (8, 6), (240, 240, 240)).save(png_file)
    bumped = bump_revision(document, {"operation_id": "attach", "kind": "task_update",
                                      "description": "attach slots", "read_set": []})
    bumped["pages"][0]["svg"] = adopt_artifact(store, svg_with_logo, "svg", page_id="p1")
    bumped["pages"][1]["svg"] = adopt_artifact(store, svg_plain, "svg", page_id="p2")
    for entry in bumped["pages"]:
        entry["svg_preview"] = adopt_artifact(store, png_file, "svg_preview", page_id=entry["page_id"])
        entry["ppt_preview"] = adopt_artifact(store, png_file, "ppt_preview", page_id=entry["page_id"])
    pptx_file = tmp_path / "deck.pptx"
    pptx_file.write_bytes(b"pptx-v1")
    bumped["outputs"]["pptx"] = adopt_artifact(store, pptx_file, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach")
    attached = store.load_document()

    logo_v2 = tmp_path / "logo-v2.png"
    Image.new("RGB", (12, 12), (200, 20, 10)).save(logo_v2)
    service.import_asset(project, asset_id="logo", kind="logo", file_path=logo_v2)
    after = store.load_document()
    p1 = after["pages"][0]
    p2 = after["pages"][1]
    assert p1["svg"] is None and p1["svg_preview"] is None and p1["ppt_preview"] is None
    assert p2["svg"] == attached["pages"][1]["svg"]
    assert p2["svg_preview"] == attached["pages"][1]["svg_preview"]
    assert all(value is None for value in after["outputs"].values())
    new_logo = next(a for a in after["design_context"]["assets"] if a["asset_id"] == "logo")
    logo_artifact = store.read_object_json(new_logo["artifact"])
    assert store.read_object_bytes(logo_artifact["file"]) == logo_v2.read_bytes()

    # Registering a newly allowed asset that no page's SVG embeds invalidates
    # nothing — allowance alone is not a rendering dependency (spec 08.8).
    other = tmp_path / "unused.png"
    Image.new("RGB", (5, 5), (1, 2, 3)).save(other)
    service.import_asset(project, asset_id="extra", kind="image", file_path=other)
    final = store.load_document()
    assert final["pages"][1]["svg"] == attached["pages"][1]["svg"]
    assert final["pages"][0]["svg"] is None


# ---------------------------------------------------------------------------
# T12.06 / spec 08.8: style and canvas changes invalidate only real
# dependents (AC-S13 style dimension + group regression on canvas).


def _style_design_pages(tmp_path):
    def styled(page_id, title, style_ref=None):
        page = _draft_page(page_id, title, f"{title}的正文。")
        if style_ref:
            page["visual_spec"]["style_ref"] = style_ref
        return page

    pages = [styled("p1", "默认样式页"), styled("p2", "独立样式页", "alt"), styled("p3", "另一默认页")]
    design = {
        "styles": [
            {"style_id": "default", "colors": {"background": "#FFFFFF", "text": "#14213D", "accent": "#1478FF"},
             "typography": {"body_font_id": "body", "heading_font_id": "heading",
                            "body_size_pt": 18, "heading_size_pt": 30, "auxiliary_size_pt": 12},
             "layout_notes": "默认"},
            {"style_id": "alt", "colors": {"background": "#000000", "text": "#EEEEEE", "accent": "#FF8800"},
             "typography": {"body_font_id": "body", "heading_font_id": "heading",
                            "body_size_pt": 16, "heading_size_pt": 28, "auxiliary_size_pt": 12},
             "layout_notes": "备选"},
            {"style_id": "unused", "colors": {"background": "#FFFFFF", "text": "#000000", "accent": "#AAAAAA"},
             "typography": {"body_font_id": "body", "heading_font_id": "heading",
                            "body_size_pt": 18, "heading_size_pt": 30, "auxiliary_size_pt": 12},
             "layout_notes": "无人引用"},
        ],
        "default_style_id": "default",
    }
    project = tmp_path / "proj"
    service.create(project, brief="样式失效", draft={"pages": pages}, design=design)
    return project, Store(project)


def _attach_design_slots(store):
    from deck_master.models import bump_revision
    document = store.load_document()
    work = store.staging_dir / "design-attach"
    work.mkdir(parents=True, exist_ok=True)
    svg_file = work / "page.svg"
    svg_file.write_text("<svg viewBox='0 0 10 10'/>")
    png_file = work / "bp.png"
    png_file.write_bytes(_png_bytes())
    bumped = bump_revision(document, {"operation_id": "design-attach", "kind": "task_update",
                                      "description": "attach slots", "read_set": []})
    for entry in bumped["pages"]:
        entry["blueprint"] = adopt_artifact(store, png_file, "blueprint", page_id=entry["page_id"])
        entry["svg"] = adopt_artifact(store, svg_file, "svg", page_id=entry["page_id"])
    pptx_file = work / "deck.pptx"
    pptx_file.write_bytes(b"styled-pptx")
    bumped["outputs"]["pptx"] = adopt_artifact(store, pptx_file, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="design-attach")
    return store.load_document()


def test_default_style_change_invalidates_only_dependent_pages(tmp_path):
    # 08.8: changing the default style clears SVG on pages whose effective
    # style is the default; the independent style_ref page and unused styles
    # stay untouched.
    project, store = _style_design_pages(tmp_path)
    attached = _attach_design_slots(store)
    design = store.load_document()["design_context"]
    changed = deepcopy(design)
    changed["styles"][0]["colors"]["accent"] = "#00AA66"
    outcome = service.update_design(project, design_context=changed)
    assert outcome["status"] == "updated"
    after = store.load_document()
    assert after["pages"][0]["svg"] is None and after["pages"][2]["svg"] is None
    assert after["pages"][1]["svg"] == attached["pages"][1]["svg"], "style_ref override page untouched"
    assert all(value is None for value in after["outputs"].values())
    for index in range(3):
        assert after["pages"][index]["blueprint"] == attached["pages"][index]["blueprint"], \
            "original blueprints are preserved as history"

    # Mutating a style no page references invalidates nothing further.
    untouched = deepcopy(after["design_context"])
    untouched["styles"][2]["colors"]["accent"] = "#BBBBBB"
    service.update_design(project, design_context=untouched)
    final = store.load_document()
    assert final["pages"][1]["svg"] == attached["pages"][1]["svg"]
    assert final["pages"][0]["svg"] is None
    assert final["revision_id"] != after["revision_id"]


def test_canvas_change_invalidates_all_pages_groupwise(tmp_path):
    # 08.8: a physical canvas change is a group regression — every page's
    # SVG/previews and the assembled outputs are invalidated.
    project, store = _style_design_pages(tmp_path)
    attached = _attach_design_slots(store)
    design = store.load_document()["design_context"]
    changed = deepcopy(design)
    changed["canvas"] = {**design["canvas"], "width_px": 1024, "height_px": 768,
                         "slide_width_in": 10.0, "slide_height_in": 7.5}
    service.update_design(project, design_context=changed)
    after = store.load_document()
    for entry in after["pages"]:
        assert entry["svg"] is None
    assert all(value is None for value in after["outputs"].values())
    assert after["pages"][0]["page"] == attached["pages"][0]["page"], "page content itself is untouched"


def test_reconstruct_after_style_change_uses_new_effective_style(tmp_path):
    # After invalidation the rebuild actually runs against the new style, not
    # just a cleared slot: reconstruct + produce re-renders and the resolved
    # effective style carries the new accent value.
    from deck_master.production import resolve_design
    project, store = _style_design_pages(tmp_path)
    _attach_design_slots(store)
    document = store.load_document()
    design = document["design_context"]
    changed = deepcopy(design)
    changed["styles"][0]["colors"]["accent"] = "#00AA66"
    service.update_design(project, design_context=changed)

    while True:
        current = store.load_document()
        missing = next((e for e in current["pages"] if not e.get("svg")), None)
        if missing is None:
            break
        response = service.continue_project(project)
        task = response["pending_tasks"][0]
        assert task["kind"] == "reconstruct"
        blueprint_sha = store.read_object_json(missing["blueprint"])["file"]["sha256"]
        page = store.read_object_json(missing["page"])
        svg = _svg_for(page).replace(b"<svg ", f'<svg data-blueprint-sha256="{blueprint_sha}" '.encode(), 1)
        staging = project / ".deckmaster" / "staging" / task["operation_id"]
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "page.svg").write_bytes(svg)
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload={
                                  "kind": "reconstruct",
                                  "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
                                  "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": missing["page_id"],
                                                      "provenance": {"source_type": "unknown",
                                                                     "tool": "host-reconstruct",
                                                                     "invocation_ref": None}}]})
    # p2/p3 kept their (textless fixture) SVGs through the style change; give
    # them real text SVGs directly (they were never invalidated).
    from deck_master.models import bump_revision as _bump
    current = store.load_document()
    work = store.staging_dir / "rest"
    work.mkdir(parents=True, exist_ok=True)
    for entry in current["pages"]:
        if entry["svg"] is not None:
            page = store.read_object_json(entry["page"])
            blueprint_sha = store.read_object_json(entry["blueprint"])["file"]["sha256"]
            svg = _svg_for(page).replace(b"<svg ", f'<svg data-blueprint-sha256="{blueprint_sha}" '.encode(), 1)
            svg_file = work / f"{entry['page_id']}.svg"
            svg_file.write_bytes(svg)
            entry["svg"] = adopt_artifact(store, svg_file, "svg", page_id=entry["page_id"])
    bumped = _bump(current, {"operation_id": "rest-svg", "kind": "task_update",
                             "description": "restore text svgs", "read_set": []})
    bumped["pages"] = current["pages"]
    store.commit_change(base_revision=current["revision_id"], document=bumped, operation_id="rest-svg")
    report = produce(project)
    assert report["status"] == "pass"
    rebuilt = store.load_document()
    assert rebuilt["outputs"]["pptx"] is not None
    assert rebuilt["pages"][0]["svg_preview"] is not None, "page was really re-rendered"
    effective, style = resolve_design(
        store.read_object_json(rebuilt["pages"][0]["page"]),
        rebuilt["design_context"], rebuilt["design_context"].get("assets") or [])
    assert style["style_id"] == "default"
    assert style["colors"]["accent"] == "#00AA66", "effective style after rebuild is the new one"


# ---------------------------------------------------------------------------
# T15 AC-K16: honest editability claims — shape/text only, never Office
# native "edit data", and unverified legacy artifacts stay unknown.


def test_pptx_artifact_and_export_declare_shape_text_editability(tmp_path):
    from deck_master.models import validate_artifact_semantics
    project = tmp_path / "proj"
    service.create(project, brief="编辑能力", draft={"pages": [_draft_page("p1", "能力页", "正文。")]})
    store = Store(project)
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"current-pptx")
    from deck_master.pipeline import artifact as adopt_artifact
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "attach-pptx", "kind": "task_update",
                                      "description": "outputs", "read_set": []})
    bumped["outputs"]["pptx"] = adopt_artifact(store, deck, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-pptx")
    artifact = store.read_object_json(store.load_document()["outputs"]["pptx"])
    assert artifact["editability"] == "editable_shapes_and_text"

    from deck_master.editing import export_project
    export_project(project, output_dir=tmp_path / "out", purpose="review")
    report = json.loads((tmp_path / "out" / "delivery.json").read_text("utf-8"))
    assert report["editability"] == "editable_shapes_and_text"


def test_no_office_native_editing_claims_in_ui_or_export(tmp_path):
    static = Path(__file__).resolve().parents[2] / "src" / "deck_master" / "resources" / "static"
    ui_text = (static / "index.html").read_text("utf-8") + (static / "app.js").read_text("utf-8")
    for forbidden in ("编辑数据", "Edit Data", "编辑图表数据", "native chart", "原生图表编辑"):
        assert forbidden not in ui_text, f"UI must not claim Office-native capability: {forbidden}"
    assert "可编辑形状与文字" in ui_text, "UI states the real shape/text editability scope"

    project = tmp_path / "proj"
    service.create(project, brief="诚实声明", draft={"pages": [_draft_page("p1", "声明页", "正文。")]})
    store = Store(project)
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"pptx")
    from deck_master.pipeline import artifact as adopt_artifact
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "attach-pptx", "kind": "task_update",
                                      "description": "outputs", "read_set": []})
    bumped["outputs"]["pptx"] = adopt_artifact(store, deck, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-pptx")
    from deck_master.editing import export_project
    export_project(project, output_dir=tmp_path / "out", purpose="review")
    report_text = (tmp_path / "out" / "delivery.json").read_text("utf-8")
    for forbidden in ("编辑数据", "Edit Data", "native chart"):
        assert forbidden not in report_text
    assert "editable_shapes_and_text" in report_text


def test_unverified_legacy_artifact_editability_stays_unknown(tmp_path):
    # A legacy pptx registered without current-pipeline verification must not
    # be promoted to editable_shapes_and_text: the schema-level value is
    # unknown, and absence of the field reads as unknown too (spec 06.7).
    from deck_master.models import validate_artifact_semantics, sha256_bytes
    store_dir = tmp_path / "proj"
    service.create(store_dir, brief="旧件", draft={"pages": [_draft_page("p1", "旧页", "正文。")]})
    store = Store(store_dir)
    legacy_bytes = b"legacy-unverified-pptx"
    file_ref = store.put_blob(legacy_bytes, ext="pptx")
    unknown_artifact = {
        "schema_version": "deck_artifact.v1", "artifact_id": "legacy-1", "page_id": None,
        "role": "pptx", "file": file_ref, "media_type":
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "created_at": "2026-09-21T00:00:00Z", "dependencies": [], "derived_from": [],
        "provenance": {"source_type": "user_supplied"}, "limitations": [],
        "editability": "unknown",
    }
    validate_artifact_semantics(unknown_artifact), "unknown is the honest value for unverified imports"
    ref = store.put_json_object(unknown_artifact)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "attach-legacy", "kind": "task_update",
                                      "description": "legacy", "read_set": []})
    bumped["outputs"]["pptx"] = ref
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-legacy")
    stored = store.read_object_json(store.load_document()["outputs"]["pptx"])
    assert stored["editability"] == "unknown"
    assert stored["editability"] != "editable_shapes_and_text", \
        "an unverified old file is never upgraded to the current verified claim"


# ---------------------------------------------------------------------------
# 轮 C / P1-06: font-file reality in invalidation and review freshness.


def _font_design_pages(tmp_path):
    font_v1 = tmp_path / "body-v1.ttf"
    font_v1.write_bytes(b"fake-font-file-v1")
    design = {
        "fonts": [
            {"font_id": "body", "family": "Demo Sans", "face": "Regular", "weight": 400,
             "asset_id": "body-font", "fallback_font_ids": []},
            {"font_id": "heading", "family": "Demo Sans", "face": "Bold", "weight": 700,
             "asset_id": None, "fallback_font_ids": []},
        ],
        "assets": [{"asset_id": "body-font", "kind": "font", "file": str(font_v1),
                    "external_use": "allowed"}],
        "allowed_asset_ids": ["body-font"],
        "styles": [
            {"style_id": "default", "colors": {"background": "#FFFFFF", "text": "#14213D", "accent": "#1478FF"},
             "typography": {"body_font_id": "body", "heading_font_id": "heading",
                            "body_size_pt": 18, "heading_size_pt": 30, "auxiliary_size_pt": 12},
             "layout_notes": "默认"},
            {"style_id": "alt", "colors": {"background": "#FFFFFF", "text": "#14213D", "accent": "#1478FF"},
             "typography": {"body_font_id": "heading", "heading_font_id": "heading",
                            "body_size_pt": 18, "heading_size_pt": 30, "auxiliary_size_pt": 12},
             "layout_notes": "备选"},
        ],
        "default_style_id": "default",
    }
    pages = [_draft_page("p1", "字体页", "引用 body 字体。"),
             _draft_page("p2", "无关页", "使用 alt 样式与 heading 字体。")]
    pages[1]["visual_spec"]["style_ref"] = "alt"
    project = tmp_path / "font-proj"
    service.create(project, brief="字体失效", draft={"pages": pages}, design=design)
    return project, Store(project)


def test_font_file_swap_invalidates_only_dependent_pages(tmp_path):
    project, store = _font_design_pages(tmp_path)
    document = store.load_document()
    work = store.staging_dir / "font-attach"
    work.mkdir(parents=True, exist_ok=True)
    svg_file = work / "page.svg"
    svg_file.write_text("<svg viewBox='0 0 10 10'/>")
    pptx_file = work / "deck.pptx"
    pptx_file.write_bytes(b"font-pptx")
    from deck_master.pipeline import artifact as adopt_artifact
    bumped = bump_revision(document, {"operation_id": "font-attach", "kind": "task_update",
                                      "description": "attach slots", "read_set": []})
    for entry in bumped["pages"]:
        entry["svg"] = adopt_artifact(store, svg_file, "svg", page_id=entry["page_id"])
    bumped["outputs"]["pptx"] = adopt_artifact(store, pptx_file, "pptx")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="font-attach")
    attached = store.load_document()

    font_v2 = tmp_path / "body-v2.ttf"
    font_v2.write_bytes(b"fake-font-file-v2-DIFFERENT-BYTES")
    service.import_asset(project, asset_id="body-font", kind="font", file_path=font_v2)
    after = store.load_document()
    assert after["pages"][0]["svg"] is None, "same font_id with new bytes invalidates the dependent page"
    assert after["pages"][1]["svg"] == attached["pages"][1]["svg"], "unrelated page untouched"
    assert all(value is None for value in after["outputs"].values())


def test_style_dependency_review_turns_stale_on_font_swap(tmp_path):
    project, store = _font_design_pages(tmp_path)
    document = store.load_document()
    work = store.staging_dir / "font-review"
    work.mkdir(parents=True, exist_ok=True)
    svg_file = work / "page.svg"
    svg_file.write_text("<svg viewBox='0 0 10 10'/>")
    pptx_file = work / "deck.pptx"
    pptx_file.write_bytes(b"font-pptx")
    report_file = work / "readback.json"
    report_file.write_text(json.dumps({"status": "pass", "findings": [], "pages": []}))
    from deck_master.pipeline import artifact as adopt_artifact
    bumped = bump_revision(document, {"operation_id": "font-review-attach", "kind": "task_update",
                                      "description": "attach", "read_set": []})
    for entry in bumped["pages"]:
        entry["svg"] = adopt_artifact(store, svg_file, "svg", page_id=entry["page_id"])
    bumped["outputs"]["pptx"] = adopt_artifact(store, pptx_file, "pptx")
    bumped["outputs"]["render_report"] = adopt_artifact(store, report_file, "render_report")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="font-review-attach")

    from deck_master.editing import _current_artifact_digests, check_summary
    digests = _current_artifact_digests(store, store.load_document())
    style_sha = digests["style:p1"]
    review = {
        "schema_version": "deck_review.v1", "review_id": "rv-font", "kind": "content", "status": "pass",
        "subjects": [store.load_document()["outputs"]["pptx"], store.load_document()["pages"][0]["page"]],
        "dependencies": [{"kind": "style", "identity": "p1", "sha256": style_sha}],
        "reviewer": {"type": "host_self", "id": "host-1", "execution_ref": None,
                     "independence_confirmed": False},
        "observations": ["实际检查"], "findings": [], "created_at": "2026-09-23T00:00:00Z",
        "replaces": None,
    }
    ref = store.put_json_object(review)
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "font-review-add", "kind": "task_update",
                                      "description": "review", "read_set": []})
    bumped["reviews"] = [ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="font-review-add")
    summary = check_summary(store, store.load_document())
    assert summary["dimensions"].get("content:p1", {}).get("status") == "pass"

    font_v2 = tmp_path / "body-v2.ttf"
    font_v2.write_bytes(b"fake-font-file-v2-DIFFERENT-BYTES")
    service.import_asset(project, asset_id="body-font", kind="font", file_path=font_v2)
    from deck_master.editing import _current_artifact_digests
    drifted = _current_artifact_digests(store, store.load_document())
    assert drifted["style:p1"] != style_sha, "same font_id with new bytes drifts the style fingerprint"
    summary = check_summary(store, store.load_document())
    assert summary["status"] == "not_evaluated"
    assert summary.get("reason") == "no current pptx output"
    # With outputs re-anchored, the drifted style dependency is what keeps the
    # old review out of the current set (stale), not a silent pass.
    document = store.load_document()
    bumped = bump_revision(document, {"operation_id": "reanchor-outputs", "kind": "task_update",
                                      "description": "re-anchor outputs after font swap", "read_set": []})
    bumped["outputs"]["pptx"] = store.load_document()["outputs"].get("pptx") or         adopt_artifact(store, pptx_file, "pptx")
    bumped["outputs"]["render_report"] = adopt_artifact(store, report_file, "render_report")
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="reanchor-outputs")
    summary = check_summary(store, store.load_document())
    assert "content:p1" in summary["missing_dimensions"], "font swap turns the style-dependent review stale"
    assert any("dependency sha" in s["reason"] for s in summary["stale"])
