"""Read-only legacy-export of a synthetic old project into a neutral archive."""

from __future__ import annotations

import json
from pathlib import Path

from deck_master import cli
from deck_master.content import check_page
from deck_master.legacy_export import FORMAT, export_project
from deck_master.models import new_document, require_writer
from deck_master.pipeline import artifact
from deck_master.project_initialization import collaboration_region
from deck_master.store import Store

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300000002000100cf0001b5e6c21d0000000049454e44ae426082"
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"></svg>'
MATERIAL = "合成材料第一行\n"


def _page() -> dict:
    return check_page(
        {
            "schema_version": "deck_page_package.v2",
            "page_id": "p1",
            "customer_visible": {
                "title": "合成页标题",
                "subtitle": "副题",
                "body_blocks": [
                    {"id": "b1", "type": "paragraph", "text": "合成正文"}
                ],
            },
            "speaker_notes": "合成讲稿",
            "visual_spec": {
                "intent": "说明材料如何进入正文",
                "layout_hint": "先结论后材料",
                "reference_mode": "new_design",
                "nodes": [
                    {
                        "node_id": "n1",
                        "label_ref": "atom:p1:title",
                        "status": "proposed",
                    }
                ],
            },
        }
    )


def _synthetic_project(tmp_path: Path) -> Path:
    project = tmp_path / "old-project"
    store = Store(project)
    store.ensure_layout()
    original = store.put_blob(MATERIAL.encode("utf-8"), ext="txt")
    extract = store.put_json_object(
        {
            "original_uri": "material.txt",
            "original_sha256": original["sha256"],
            "format": "txt",
            "format_kind": "text",
            "status": "read",
            "text": MATERIAL,
            "locators": [],
            "tables": [],
            "image_pages": [],
            "detail": "",
            "original_file": original,
        }
    )
    page = _page()
    page_ref = store.put_json_object(page)
    image_path = tmp_path / "page.png"
    image_path.write_bytes(PNG)
    svg_path = tmp_path / "page.svg"
    svg_path.write_bytes(SVG)
    pptx_path = tmp_path / "deck.pptx"
    pptx_path.write_bytes(b"PK\x03\x04synthetic-pptx")
    blueprint = artifact(
        store,
        image_path,
        "blueprint",
        page_id="p1",
        dependencies=[{"kind": "content", "identity": "page:p1", "sha256": page_ref["sha256"]}],
    )
    svg_ref = artifact(
        store,
        svg_path,
        "svg",
        page_id="p1",
        dependencies=[{"kind": "content", "identity": "page:p1", "sha256": page_ref["sha256"]}],
    )
    pptx_ref = artifact(store, pptx_path, "pptx")
    plan = store.put_json_object(
        {
            "input": {
                "input_summary": "合成主张：材料应进入正文。",
                "chapters": [
                    {"chapter_id": "c1", "title": "材料与正文", "goal_ids": ["g1"]}
                ],
                "goals": [
                    {
                        "goal_id": "g1",
                        "page_id": "p1",
                        "purpose": "说明材料如何进入正文",
                        "source_links": [{"source_id": "s1", "locator": "L1"}],
                        "unresolved_facts": ["待补一项"],
                    }
                ],
                "unresolved_facts": ["整稿待补"],
            }
        }
    )
    review = store.put_json_object(
        {
            "schema_version": "deck_review.v1",
            "review_id": "rev-synth",
            "kind": "content",
            "status": "fail",
            "findings": [{"code": "synthetic", "message": "合成审阅"}],
        }
    )
    authorization = store.put_json_object(
        {
            "schema_version": "collaboration_authorization.v1",
            "authorization_id": "auth-synth",
            "status": "active",
            "mode": "execute",
        }
    )
    task = store.put_json_object(
        {
            "schema_version": "deck_task.v1",
            "task_id": "task-synth",
            "kind": "blueprint",
            "status": "running",
            "call_allowances": [
                {
                    "allowance_id": "call-1",
                    "state": "in_flight",
                    "execution_ref": "synthetic-host",
                    "invocation_ref": None,
                    "evidence": [],
                }
            ],
        }
    )
    document = new_document(
        project_id="synthetic-export",
        task={
            "title": "合成导出",
            "brief": "把材料写成一页说明",
            "audience": "测试读者",
            "scenario": "首提",
            "existing_decisions": ["只使用合成材料"],
        },
        sources=[
            {
                "source_id": "s1",
                "name": "material.txt",
                "original_uri": "material.txt",
                "original_sha256": original["sha256"],
                "format": "txt",
                "extract": extract,
                "external_use": "unspecified",
                "restriction": "",
                "locator_scheme": "line",
            }
        ],
        operation_id="synthetic-export",
    )
    require_writer(document, "collaboration.v1")
    region = collaboration_region()
    region["authorizations"] = [authorization]
    document["collaboration"] = region
    document["content_plan"] = plan
    document["pages"] = [
        {
            "page_id": "p1",
            "page": page_ref,
            "blueprint": blueprint,
            "svg": svg_ref,
            "svg_preview": None,
            "ppt_preview": None,
        }
    ]
    document["reviews"] = [review]
    document["tasks"] = [task]
    document["outputs"] = {"pptx": pptx_ref, "trace": None, "render_report": None}
    store.init_project(document, operation_id="synthetic-export")
    return project


def test_legacy_export_writes_neutral_archive_and_leaves_project_unread(tmp_path: Path) -> None:
    project = _synthetic_project(tmp_path)
    pointer = (project / ".deckmaster" / "current.json").read_bytes()
    out = tmp_path / "archive"
    result = export_project(project, out)
    assert result["status"] == "exported"
    assert result["format"] == FORMAT
    assert result["pages"] == 1
    assert result["materials"] == 1
    assert result["open_calls"] == 1
    assert (project / ".deckmaster" / "current.json").read_bytes() == pointer
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == FORMAT
    assert manifest["source"]["project_id"] == "synthetic-export"
    assert manifest["brief"]["title"] == "合成导出"
    assert manifest["brief"]["audience"] == "测试读者"
    assert manifest["brief"]["task_type"] == "首提"
    assert manifest["brief"]["goal"] == "把材料写成一页说明"
    assert manifest["brief"]["constraints"] == ["只使用合成材料"]
    material = manifest["materials"][0]
    assert material["id"] == "s1"
    assert (out / "files" / material["file"]).read_text(encoding="utf-8") == MATERIAL
    assert (out / "files" / material["text_file"]).read_text(encoding="utf-8") == MATERIAL
    assert manifest["framing"]["thesis"] == "合成主张：材料应进入正文。"
    assert manifest["framing"]["pillars"][0]["title"] == "材料与正文"
    page = manifest["pages"][0]
    assert page["id"] == "p1"
    assert page["content"]["title"] == "合成页标题"
    assert page["notes"] == "合成讲稿"
    assert page["purpose"] == "说明材料如何进入正文"
    assert page["todo"] == ["待补一项"]
    assert page["refs"] == ["s1 L1"]
    assert (out / "files" / page["image"]["file"]).read_bytes() == PNG
    assert (out / "files" / page["svg"]["file"]).read_bytes() == SVG
    assert (out / "files" / manifest["last_export"]["file"]).read_bytes().startswith(b"PK")
    assert manifest["reviews"][0]["review_id"] == "rev-synth"
    assert manifest["authorizations"][0]["authorization_id"] == "auth-synth"
    assert manifest["open_calls"][0]["state"] == "in_flight"
    assert manifest["open_calls"][0]["task_id"] == "task-synth"
    kinds = {item["kind"] for item in manifest["unmapped"]}
    assert "visual_spec" in kinds
    assert "task" in kinds


def test_legacy_export_cli_refuses_existing_out_and_missing_project(tmp_path, capsys) -> None:
    project = _synthetic_project(tmp_path)
    out = tmp_path / "archive"
    assert cli.main(["legacy-export", str(project), str(out)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "exported"
    capsys.readouterr()
    assert cli.main(["legacy-export", str(project), str(out)]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["error"]["code"] == "invalid_input"
    assert "已存在" in error["error"]["message"]
    capsys.readouterr()
    assert cli.main(["legacy-export", str(tmp_path / "missing"), str(tmp_path / "other")]) == 2
    missing = json.loads(capsys.readouterr().err)
    assert missing["error"]["code"] == "invalid_input"
