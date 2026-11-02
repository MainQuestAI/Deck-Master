"""Read-only legacy-export of a synthetic old project into a neutral archive."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from deck_master import cli
from deck_master.content import check_page
from deck_master.legacy_export import FORMAT, LegacyExportError, export_project
from deck_master.models import (new_document, require_writer, validate_content_plan_semantics,
                                validate_narrative_semantics)
from deck_master.pipeline import artifact
from deck_master.project_initialization import collaboration_region
from deck_master.store import Store

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300000002000100cf0001b5e6c21d0000000049454e44ae426082"
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"></svg>'
MATERIAL = "合成材料第一行\n"


def _narrative(nodes, *, central=None, issues=None):
    return {
        "schema_version": "narrative.v1", "narrative_id": "synthetic-narrative",
        "version": 1, "project_id": "synthetic-export", "origin": "user_imported",
        "maturity": "argument" if central else "framing", "input_basis": [],
        "communication_job": {"mode": "explain", "audience_fact_key": "audience",
                              "audience_question": "What is supported?", "desired_outcome": "Approve the next step",
                              "observable_success": "Choose the next step", "use_mode": "live", "primary_use": "live"},
        "central_node_id": central, "nodes": nodes, "edges": [], "issues": issues or [],
        "alternatives": [], "previous_ref": None,
    }


def _node(node_id, authority, *, role="evidence", links=None, issues=None):
    return {"node_id": node_id, "role": role, "statement": f"Synthetic {node_id} statement",
            "authority": authority, "source_links": links or [],
            "qualification_node_ids": [], "unresolved_issue_ids": issues or []}


def _issue(issue_id, resolution="open", *, affected=None):
    return {"issue_id": issue_id, "question": f"Which scope applies to {issue_id}?",
            "impact": "blocker", "affected_node_ids": affected or [],
            "resolution": resolution, "resolution_ref": None}


def _complete_v2_plan(plan):
    ref = {"path": ".deckmaster/objects/aa/" + "a" * 64 + ".json", "sha256": "a" * 64}
    plan.update({"plan_id": "synthetic-plan", "version": 1, "project_id": "synthetic-export",
                 "task_id": None, "origin": "user_imported", "basis": {"revision_id": "rev-1", "input_digest": "b" * 64},
                 "previous_ref": None, "mode": "bound", "narrative_ref": None, "imported_manuscript": None,
                 "page_links": [{"page_id": "p1", "page_ref": ref, "plan_role_page_id": "p1"}]})
    plan["input"].update({"page_order": ["p1"], "page_budget": {"exact": 1, "target": 1, "max": 1},
                          "time_budget": {"total_seconds": 60, "speaking_seconds": 60, "interaction_seconds": 0, "constraint": "soft"},
                          "speech_policy": {"mode": "cues", "source": "provided", "output": "pptx_notes"},
                          "tradeoff_issue_ids": []})
    for role in plan["input"]["page_roles"]:
        role.update({"audience_question": "What is supported?", "narrative_node_ids": [],
                     "required_qualifications": [], "content_profile": "evidence", "density_rationale": "One fact",
                     "timing_seconds": 60, "transition_to_next": None})
        for link in role["source_links"]:
            link["source_version"] = {"original_sha256": "c" * 64, "extract": ref}
    for issue in plan["input"]["issues"]:
        issue.update({"impact": "needs_judgment", "resolution_ref": None})
    validate_content_plan_semantics(plan)
    return plan


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


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, int], ...]:
    rows: list[tuple[str, str, int]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        base = Path(dirpath)
        rel_dir = base.relative_to(root).as_posix()
        dir_key = "" if rel_dir == "." else rel_dir + "/"
        rows.append((dir_key, "", base.stat().st_mtime_ns))
        for name in sorted(filenames):
            path = base / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                digest = hashlib.sha256(os.readlink(path).encode()).hexdigest()
                mtime = path.lstat().st_mtime_ns
            else:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                mtime = path.stat().st_mtime_ns
            rows.append((rel, digest, mtime))
    return tuple(sorted(rows))


def _default_plan() -> dict:
    return {
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


def _synthetic_project(
    tmp_path: Path,
    *,
    plan: dict | None = None,
    narrative: dict | None = None,
    unread_source: bool = False,
) -> Path:
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
    from pptx import Presentation

    pptx = Presentation()
    slide = pptx.slides.add_slide(pptx.slide_layouts[6])
    slide.notes_slide.notes_text_frame.text = "Historical synthetic notes"
    pptx.save(pptx_path)
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
    plan_ref = store.put_json_object(_default_plan() if plan is None else plan)
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
        design_context={
            "canvas": {
                "width_px": 1920,
                "height_px": 1080,
                "slide_width_in": 13.333,
                "slide_height_in": 7.5,
                "fit": "contain",
            }
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
            },
            *(
                [
                    {
                        "source_id": "s2",
                        "name": "unread.txt",
                        "original_uri": "unread.txt",
                        "original_sha256": None,
                        "format": "txt",
                        "extract": None,
                        "external_use": "unspecified",
                        "restriction": "",
                        "locator_scheme": "line",
                    }
                ]
                if unread_source
                else []
            ),
        ],
        operation_id="synthetic-export",
    )
    require_writer(document, "collaboration.v1")
    region = collaboration_region()
    region["authorizations"] = [authorization]
    document["collaboration"] = region
    document["content_plan"] = plan_ref
    if narrative is not None:
        document["narrative"] = store.put_json_object(narrative)
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
    before = _tree_snapshot(project)
    out = tmp_path / "archive"
    result = export_project(project, out)
    assert result["status"] == "exported"
    assert result["format"] == FORMAT
    assert result["pages"] == 1
    assert result["materials"] == 1
    assert result["open_calls"] == 1
    assert _tree_snapshot(project) == before
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
    assert manifest["framing"]["pillars"][0]["points"] == ["说明材料如何进入正文"]
    assert manifest["framing"]["questions"] == ["整稿待补", "待补一项"]
    assert material["file"] and material["text_file"]
    page = manifest["pages"][0]
    assert list(page["image"]) == ["file"]
    assert list(page["svg"]) == ["file"]
    assert page["preview"] is None
    assert page["id"] == "p1"
    assert page["content"]["title"] == "合成页标题"
    assert page["notes"] == "合成讲稿"
    assert page["purpose"] == "说明材料如何进入正文"
    assert page["layout"] == "先结论后材料"
    assert page["todo"] == ["待补一项"]
    assert page["refs"] == ["s1 L1"]
    assert manifest["style"]["canvas"]["width_px"] == 1920
    assert manifest["style"]["canvas"]["height_px"] == 1080
    assert manifest["style"]["canvas"]["slide_width_in"] == 13.333
    assert manifest["style"]["canvas"]["slide_height_in"] == 7.5
    assert manifest["style"]["palette"] == ["#1478FF", "#FFFFFF", "#14213D"]
    assert manifest["style"]["fonts"] == ["Noto Sans CJK SC"]
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


def test_legacy_export_refuses_out_inside_project(tmp_path, capsys) -> None:
    project = _synthetic_project(tmp_path)
    before = _tree_snapshot(project)
    inside = project / "archive"
    with pytest.raises(LegacyExportError, match="之内"):
        export_project(project, inside)
    assert not inside.exists()
    dotted = project / "sub" / ".." / "also-inside"
    assert cli.main(["legacy-export", str(project), str(dotted)]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["error"]["code"] == "invalid_input"
    assert "之内" in error["error"]["message"]
    assert not (project / "also-inside").exists()
    sibling = Path(str(project) + "-archive")
    assert export_project(project, sibling)["status"] == "exported"
    assert sibling.is_dir()
    assert _tree_snapshot(project) == before


def test_legacy_export_maps_content_plan_v2_page_roles(tmp_path: Path) -> None:
    plan = {
        "schema_version": "content_plan.v2",
        "input": {
            "schema_version": "content_plan_input.v2",
            "chapters": [
                {"chapter_id": "c1", "title": "材料与正文", "page_ids": ["p1"]}
            ],
            "page_roles": [
                {
                    "page_id": "p1",
                    "role": "说明页",
                    "intended_takeaway": "材料进入正文",
                    "source_links": [{"source_id": "s1", "locator": "L1"}],
                }
            ],
            "issues": [
                {
                    "issue_id": "i-open",
                    "question": "待补出处",
                    "resolution": "open",
                    "affected_page_ids": ["p1"],
                },
                {
                    "issue_id": "i-done",
                    "question": "已解决的问题",
                    "resolution": "resolved",
                    "affected_page_ids": ["p1"],
                },
                {
                    "issue_id": "i-limit",
                    "question": "接受的限制",
                    "resolution": "accepted_limit",
                    "affected_page_ids": ["p1"],
                },
            ],
        },
    }
    project = _synthetic_project(tmp_path, plan=_complete_v2_plan(plan))
    out = tmp_path / "archive"
    export_project(project, out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    pillar = manifest["framing"]["pillars"][0]
    assert pillar["title"] == "材料与正文"
    assert pillar["points"] == ["材料进入正文"]
    assert manifest["framing"]["questions"] == ["待补出处"]
    page = manifest["pages"][0]
    assert page["purpose"] == "说明页"
    assert page["refs"] == ["s1 L1"]
    assert page["todo"] == ["待补出处"]
    assert "已解决的问题" not in manifest["framing"]["questions"]
    assert "接受的限制" not in page["todo"]
    for question in ("已解决的问题", "接受的限制"):
        assert any(question in item["reason"] for item in manifest["unmapped"])


def test_legacy_export_maps_open_narrative_questions(tmp_path: Path) -> None:
    nodes = [_node("central", "hypothesis", role="claim"),
             _node("fact", "reported_fact", issues=["open"])]
    narrative = _narrative(nodes, central="central", issues=[
        _issue("open", affected=["fact"]), _issue("done", "resolved"), _issue("limit", "accepted_limit")])
    validate_narrative_semantics(narrative)
    project = _synthetic_project(tmp_path, narrative=narrative)
    out = tmp_path / "archive"
    export_project(project, out)
    manifest = json.loads((out / "manifest.json").read_text())
    framing = manifest["framing"]
    assert framing["thesis"] == nodes[0]["statement"]
    assert framing["assumptions"] == [nodes[0]["statement"]]
    assert framing["facts"] == [nodes[1]["statement"]]
    assert framing["questions"] == ["整稿待补", "待补一项", narrative["issues"][0]["question"]]
    for issue in narrative["issues"][1:]:
        assert any(issue["question"] in item["reason"] and issue["resolution"] in item["reason"]
                   for item in manifest["unmapped"])


@pytest.mark.parametrize("authority", ["reported_fact", "calculation", "hypothesis", "inference", "recommendation", "target", "instruction"])
@pytest.mark.parametrize("role", ["evidence", "claim"])
def test_migration_classifies_authority_independently_of_role(tmp_path, authority, role):
    node = _node("value", authority, role=role, issues=["pending"])
    narrative = _narrative([node], issues=[_issue("pending", affected=["value"])])
    validate_narrative_semantics(narrative)
    project = _synthetic_project(tmp_path, narrative=narrative)
    archive = tmp_path / "archive"
    export_project(project, archive)
    result = json.loads((archive / "manifest.json").read_text())
    framing = result["framing"]
    assert framing["facts"] == ([node["statement"]] if authority in ("reported_fact", "calculation") else [])
    assert framing["assumptions"] == ([node["statement"]] if authority == "hypothesis" else [])
    assert narrative["issues"][0]["question"] in framing["questions"]
    if authority not in ("reported_fact", "calculation", "hypothesis"):
        assert any(node["statement"] in item["reason"] and authority in item["reason"]
                   for item in result["unmapped"])


def test_sourced_calculation_and_empty_framing_keep_their_meaning():
    from deck_master.legacy_export import _apply_narrative

    link = {"source_id": "s1", "source_version": {"original_sha256": "a" * 64,
            "extract": {"path": ".deckmaster/objects/bb/" + "b" * 64 + ".json", "sha256": "b" * 64}}, "locator": "L1"}
    node = _node("calculation", "calculation", links=[link])
    narrative = _narrative([node])
    validate_narrative_semantics(narrative)
    framing = {"thesis": "", "pillars": [], "facts": [], "assumptions": [], "questions": []}
    unmapped = []
    _apply_narrative(narrative, framing, unmapped)
    assert framing["thesis"] == ""
    assert framing["facts"] == [node["statement"]]
    assert any(narrative["communication_job"]["desired_outcome"] in item["reason"] for item in unmapped)


def test_legacy_export_records_empty_extract_ref(tmp_path: Path) -> None:
    project = _synthetic_project(tmp_path, unread_source=True)
    out = tmp_path / "archive"
    export_project(project, out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    unread = next(item for item in manifest["materials"] if item["id"] == "s2")
    assert unread["status"] == "needs_tool"
    assert unread["file"] == ""
    assert unread["text_file"] == ""
    assert any(
        item["kind"] == "material" and item["id"] == "s2" and "引用为空" in item["reason"]
        for item in manifest["unmapped"]
    )


def test_exported_archive_imports_with_deck(tmp_path: Path) -> None:
    binary = Path(os.environ["DECK_BIN"]) if os.environ.get("DECK_BIN") else (
        Path(__file__).resolve().parents[2] / "rust" / "target" / "debug" / "deck"
    )
    if not binary.is_file():
        pytest.skip("deck binary is not built")
    project = _synthetic_project(tmp_path)
    out = tmp_path / "archive"
    export_project(project, out)
    dest = tmp_path / "new-deck"
    imported = subprocess.run(
        [str(binary), "import", str(out), str(dest)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr
    report = json.loads(imported.stdout)
    assert report["pages"] == 1
    assert report["materials"] == 1
    shown = subprocess.run(
        [str(binary), "--project", str(dest), "show"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert shown.returncode == 0, shown.stderr
    status = json.loads(shown.stdout)["artifact_status"]
    assert status["stale_images"] == ["p1"]
    assert status["stale_pages"] == ["p1"]
    exported = subprocess.run(
        [str(binary), "--project", str(dest), "export", "pptx"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout)["input_changed"] is True
