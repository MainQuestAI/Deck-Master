"""T06 prompt projection and Codex blueprint dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from deck_master import service
from deck_master import tasks as tasks_mod
from deck_master.models import default_design_context
from deck_master.production import project_prompt


def test_continue_reconstructs_first_page_before_next_blueprint(tmp_path: Path) -> None:
    """An accepted image gets SVG feedback before another page consumes ImageGen."""
    from PIL import Image
    from deck_master.models import bump_revision
    from deck_master.pipeline import artifact
    from deck_master.store import Store

    first = _page()
    second = {"schema_version": "deck_page_package.v2", "page_id": "p10",
              "customer_visible": {"title": "第二页", "body_blocks": []},
              "visual_spec": {"intent": "第二页图", "reference_mode": "new_design"}}
    project = tmp_path / "project"
    service.create(project, brief="two-page order", draft={"pages": [first, second]})
    store = Store(project)
    image_path = tmp_path / "first.png"
    Image.new("RGB", (120, 80), "white").save(image_path)
    document = store.load_document()
    updated = bump_revision(document, {"operation_id": "first-blueprint", "kind": "task_update",
                                       "description": "attach first image", "read_set": []})
    updated["pages"][0]["blueprint"] = artifact(store, image_path, "blueprint", page_id="p09")
    store.commit_change(base_revision=document["revision_id"], document=updated,
                        operation_id="first-blueprint")

    response = service.continue_project(project)
    assert response["next_action"] == "codex_reconstruct_svg"
    assert response["pending_tasks"][0]["scope_pages"] == ["p09"]

SPEC = Path(__file__).resolve().parents[2] / "docs/specs/deck-master-rebuild-v1"
COMPOSE = SPEC / "examples/roundtrips/result-envelope/compose.json"


def _page() -> dict:
    return json.loads(COMPOSE.read_text("utf-8"))["pages"][0]


def test_prompt_projects_all_visible_fields_and_excludes_internal_notes() -> None:
    design = default_design_context()
    request = project_prompt(_page(), design, [])
    prompt = request["prompt"]
    for marker in (
        "将设备条件收集前移",
        "建议在现有售后门户嵌入",
        "填写设备型号与问题现象",
        "120条",
        "45%",
        "本期只读接口",
        "54÷120=45%",
        "先改变信息收集环节",
        "提交完整设备条件",
        "转交需进一步判断的问题",
    ):
        assert marker in prompt
    assert "不要把这一段加入图中" not in prompt
    assert "所有企业与数字均为合成输入" not in prompt
    assert "do not add claims or invent numeric values" in prompt
    assert "use an unlabeled schematic marked 示意数据" in prompt


def test_only_allowed_assets_enter_prompt() -> None:
    design = default_design_context()
    design["allowed_asset_ids"] = ["brand-logo"]
    permitted = [
        {"asset_id": "brand-logo", "kind": "logo", "external_use": "allowed"},
        {"asset_id": "private-photo", "kind": "image", "external_use": "forbidden"},
    ]
    request = project_prompt(_page(), design, permitted)
    assets = request["projection"]["permitted_assets"]
    assert [asset["asset_id"] for asset in assets] == ["brand-logo"]
    assert "private-photo" not in request["prompt"]


def test_blueprint_task_exposes_only_allowed_asset_bytes(tmp_path: Path) -> None:
    logo = tmp_path / "logo.svg"
    logo.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='80' height='20'/>")
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.create(
        project,
        brief="brand test",
        draft=draft,
        design={
            "assets": [
                {"asset_id": "brand-logo", "kind": "logo", "file": str(logo), "external_use": "allowed"}
            ],
            "allowed_asset_ids": ["brand-logo"],
        },
    )
    task = service.continue_project(project)["pending_tasks"][0]
    files = task["production_request"]["permitted_asset_files"]
    assert len(files) == 1
    assert files[0]["asset_id"] == "brand-logo"
    assert files[0]["media_type"] == "image/svg+xml"
    assert files[0]["file"]["path"].startswith(".deckmaster/objects/")


def test_continue_dispatches_one_codex_blueprint_with_allowance(tmp_path: Path) -> None:
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.import_draft(project, draft_payload=draft)
    response = service.continue_project(project)
    assert response["status"] == "awaiting_host"
    assert response["next_action"] == "codex_generate_blueprint"
    assert len(response["pending_tasks"]) == 1
    task = response["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    assert task["scope_pages"] == ["p09"]
    assert task["production_request"]["host"] == "codex_imagegen"
    assert task["call_allowances"][0]["state"] == "reserved"

    repeated = service.continue_project(project)
    assert repeated["pending_tasks"][0]["task_id"] == task["task_id"]


def test_prompt_is_stable_and_page_specific() -> None:
    design = default_design_context()
    first = project_prompt(_page(), design, [])
    changed = _page()
    changed["customer_visible"]["title"] = "另一页的独立标题"
    second = project_prompt(changed, design, [])
    assert first["prompt_sha256"] != second["prompt_sha256"]
    assert first == project_prompt(_page(), design, [])


def test_settle_records_invocation_ref_and_can_enrich_old_consumed_fact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.import_draft(project, draft_payload=draft)
    task = service.continue_project(project)["pending_tasks"][0]
    store = service.Store(project)
    service.task_start(project, task_id=task["task_id"], execution_ref="codex-test")
    tasks_mod.call_begin(
        store, task_id=task["task_id"], allowance_id="call-1", execution_ref="codex-test"
    )
    tasks_mod.call_settle(
        store,
        task_id=task["task_id"],
        allowance_id="call-1",
        outcome="consumed",
        report_bytes=b"{}",
        invocation_ref="exec-test-1",
    )
    current = store.load_document()
    saved = tasks_mod._lookup_task(current, task["task_id"], store)
    assert saved["call_allowances"][0]["invocation_ref"] == "exec-test-1"


def test_call_operation_ids_include_task_identity(tmp_path: Path) -> None:
    """Two pages/tasks may both own call-1 without transaction collisions."""
    project = tmp_path / "project"
    draft = json.loads(COMPOSE.read_text("utf-8"))
    service.import_draft(project, draft_payload=draft)
    first = service.continue_project(project)["pending_tasks"][0]
    store = service.Store(project)
    service.task_start(project, task_id=first["task_id"], execution_ref="exec-1")
    tasks_mod.call_begin(store, task_id=first["task_id"], allowance_id="call-1", execution_ref="exec-1")
    tasks_mod.call_settle(
        store, task_id=first["task_id"], allowance_id="call-1", outcome="consumed",
        report_bytes=b"{}", invocation_ref="inv-1"
    )
    service.task_cancel(project, task_id=first["task_id"])
    # A second task deliberately reuses the allowance's local name.
    document = store.load_document()
    page_entry = document["pages"][0]
    second_obj = service.open_blueprint_task(store, document, page_entry)
    service.task_start(project, task_id=second_obj["task_id"], execution_ref="exec-2")
    tasks_mod.call_begin(store, task_id=second_obj["task_id"], allowance_id="call-1", execution_ref="exec-2")
    result = tasks_mod.call_settle(
        store, task_id=second_obj["task_id"], allowance_id="call-1", outcome="consumed",
        report_bytes=b"{}", invocation_ref="inv-2"
    )
    assert result["status"] == "settled"


# ---------------------------------------------------------------------------
# T07 AC-B03 / AC-B05 / AC-B10 evidence (original preservation, copy roundtrip,
# reference direction, redesign and supersede semantics).

import io
import uuid
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest

from deck_master.models import sha256_bytes

from PIL import Image

from deck_master import tasks as tasks_mod
from deck_master.editing import edit_page, review_status
from deck_master.models import content_identity
from deck_master.production import project_prompt
from deck_master.store import Store

ENVELOPES_DIR = SPEC / "examples/roundtrips/result-envelope"
from hostenv import resolve_host_font

FAMILY = resolve_host_font()

ROUNDTRIP_PAGE = {
    "schema_version": "deck_page_package.v2",
    "page_id": "p1",
    "customer_visible": {
        "title": "设备条件收集前移",
        "body_blocks": [{"id": "b1", "type": "paragraph", "text": "在现有售后门户嵌入设备条件表单。"}],
    },
    "visual_spec": {"intent": "forward intake", "reference_mode": "new_design"},
}


def _create_project(tmp_path: Path) -> Path:
    material = tmp_path / "material.txt"
    material.write_text("季度对照正文\n(尾部约束)合成数据不可回写。", encoding="utf-8")
    project = tmp_path / "proj"
    service.create(project, brief="原图往返", sources=[material],
                   draft={"pages": [deepcopy(ROUNDTRIP_PAGE)]})
    return project


def _real_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (320, 180), (245, 246, 250)).save(buffer, format="PNG")
    return buffer.getvalue()


def _blueprint_envelope(page_ref: dict, png_bytes: bytes, prompt_text: str) -> dict:
    return {
        "kind": "blueprint",
        "files": [
            {"file_id": "blueprint_file", "path": "reference.png", "media_type": "image/png"},
            {"file_id": "prompt_file", "path": "submitted-prompt.txt", "media_type": "text/plain"},
        ],
        "artifact_specs": [{
            "file_id": "blueprint_file",
            "role": "blueprint",
            "page_id": "p1",
            "derived_from": [page_ref],
            "provenance": {
                "source_type": "unknown",
                "tool": "host-imagegen",
                "invocation_ref": None,
                "submitted_prompt_file_id": "prompt_file",
                "generated_from_page": page_ref,
            },
            "reference_regions": [{
                "region_id": "main", "description": "全页蓝图",
                "bbox_normalized": [0.0, 0.0, 1.0, 1.0], "importance": "essential",
            }],
        }],
        "notes": prompt_text,
    }


def _adopt_blueprint(tmp_path: Path, project: Path) -> dict:
    response = service.continue_project(project)
    task = response["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    store = Store(project)
    page_ref = store.load_document()["pages"][0]["page"]
    envelope = _blueprint_envelope(page_ref, _real_png(), "提交给宿主的真实 prompt")
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "reference.png").write_bytes(_real_png())
    (staging / "submitted-prompt.txt").write_bytes("提交给宿主的真实 prompt".encode("utf-8"))
    outcome = service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                    produced_against=task["produced_against"], result_payload=envelope)
    assert outcome["status"] == "accepted"
    return Store(project).load_document()


def _open_host_task(project: Path, kind: str) -> dict:
    store = Store(project)
    return service.open_host_task(store, kind=kind, page_ids=["p1"], instruction=f"{kind} 指令")


def _reconstruct_envelope(svg_bytes: bytes) -> dict:
    return {
        "kind": "reconstruct",
        "files": [{"file_id": "svg_file", "path": "page.svg", "media_type": "image/svg+xml"}],
        "artifact_specs": [{
            "file_id": "svg_file", "role": "svg", "page_id": "p1",
            "provenance": {"source_type": "unknown", "tool": "host-reconstruct", "invocation_ref": None},
        }],
    }


def _accept_reconstruct(project: Path, task: dict, svg_bytes: bytes) -> dict:
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "page.svg").write_bytes(svg_bytes)
    return service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                                 produced_against=task["produced_against"],
                                 result_payload=_reconstruct_envelope(svg_bytes))


def test_copy_roundtrip_keeps_original_page_prompt_and_blueprint(tmp_path: Path) -> None:
    # AC-B03: adopting blueprint copy edits produces a NEW Page revision while
    # the original page object, the generated_from blueprint artifact, and the
    # submitted prompt blob stay byte-identical (immutable objects).
    project = _create_project(tmp_path)
    document = _adopt_blueprint(tmp_path, project)
    store = Store(project)
    entry = document["pages"][0]
    page_ref = entry["page"]
    blueprint_ref = entry["blueprint"]
    original_page_bytes = store.read_object_bytes(page_ref)
    blueprint_bytes = store.read_object_bytes(Store(project).read_object_json(blueprint_ref)["file"])
    prompt_ref = store.read_object_json(blueprint_ref)["provenance"]["submitted_prompt"]
    prompt_bytes = store.read_object_bytes(prompt_ref)
    page_obj = store.read_object_json(page_ref)

    # The prompt projection is stable for the same Page.
    design = store.load_document()["design_context"]
    first = project_prompt(page_obj, design, [])
    second = project_prompt(page_obj, design, [])
    assert first["prompt_sha256"] == second["prompt_sha256"]

    # Copy edit (new wording) -> new Page object + new revision.
    changed = deepcopy(page_obj)
    changed["customer_visible"]["body_blocks"][0]["text"] = "在售后门户与小程序双端嵌入设备条件表单。"
    result = edit_page(store.project_root, page=changed, base_revision=document["revision_id"],
                       page_hash=page_ref["sha256"], operation_id="copy-edit-1")
    assert result["status"] == "edited"

    # Original objects are untouched and still readable through their old refs.
    assert store.read_object_bytes(page_ref) == original_page_bytes
    after = store.load_document()
    new_entry = after["pages"][0]
    assert new_entry["page"] != page_ref
    assert store.read_object_bytes(Store(project).read_object_json(new_entry["blueprint"])["file"]) == blueprint_bytes
    assert store.read_object_bytes(
        store.read_object_json(new_entry["blueprint"])["provenance"]["submitted_prompt"]) == prompt_bytes
    assert new_entry["blueprint"] == blueprint_ref

    # A small copy edit forces SVG rework (not regeneration of the original
    # image): the next step is a reconstruct task, not a new blueprint task.
    response = service.continue_project(project)
    assert response["next_action"] == "codex_reconstruct_svg"
    assert response["pending_tasks"][0]["kind"] == "reconstruct"


def test_previews_never_become_reference_and_reencode_fails_binding(tmp_path: Path) -> None:
    # AC-B05: svg/ppt previews (even byte-re-encoded) never enter
    # reference_images; a re-encoded original has a new identity and the
    # data-blueprint-sha256 binding rejects it.
    project = _create_project(tmp_path)
    document = _adopt_blueprint(tmp_path, project)
    store = Store(project)
    blueprint_ref = document["pages"][0]["blueprint"]
    blueprint_artifact = store.read_object_json(blueprint_ref)
    blueprint_bytes = store.read_object_bytes(blueprint_artifact["file"])

    # Valid reconstruction bound to the exact original bytes.
    correct_sha = blueprint_artifact["file"]["sha256"]
    svg_ok = (f'<svg viewBox="0 0 320 180" data-blueprint-sha256="{correct_sha}">'
              f'<rect width="320" height="180" fill="#ffffff"/>'
              f'<text x="20" y="90" font-family="{FAMILY}" font-size="20">设备条件收集前移</text></svg>').encode()
    task = _open_host_task(project, "reconstruct")
    outcome = _accept_reconstruct(project, task, svg_ok)
    assert outcome["status"] == "accepted"

    # Re-encoded preview derivatives (new bytes, new identity) registered as previews.
    reencoded = io.BytesIO()
    reimage = Image.open(io.BytesIO(blueprint_bytes)).convert("RGB")
    reimage.putpixel((0, 0), (244, 246, 249))  # lossless re-encode: new bytes, same image
    reimage.save(reencoded, format="PNG")
    preview_file = tmp_path / "preview.png"
    preview_file.write_bytes(reencoded.getvalue())
    assert reencoded.getvalue() != blueprint_bytes
    page_ref = store.load_document()["pages"][0]["page"]
    svg_preview_ref = artifact_helper(store, preview_file, "svg_preview", page_ref)
    ppt_preview_ref = artifact_helper(store, preview_file, "ppt_preview", page_ref)
    current = store.load_document()
    bumped = tasks_mod.bump_revision(current, {"operation_id": "attach-previews", "kind": "task_update",
                                               "description": "attach previews", "read_set": []})
    bumped["pages"][0]["svg_preview"] = svg_preview_ref
    bumped["pages"][0]["ppt_preview"] = ppt_preview_ref
    store.commit_change(base_revision=current["revision_id"], document=bumped, operation_id="attach-previews")

    # reference_images still comes only from entry['blueprint'].
    task = _open_host_task(project, "reconstruct")
    summary = service.task_summary(store, store.load_document(), task)
    references = summary["reference_images"]
    assert len(references) == 1
    assert references[0]["artifact"] == store.load_document()["pages"][0]["blueprint"]
    assert "immutable image" in references[0]["requirement"]
    preview_paths = {store.read_object_json(r)["file"]["path"] for r in (svg_preview_ref, ppt_preview_ref)}
    assert all(ref["file"]["path"] not in preview_paths for ref in references)

    # A re-encoded "original" carries a different sha: the binding rejects it.
    wrong_task = _open_host_task(project, "reconstruct")
    forged_sha = sha256_bytes(reencoded.getvalue())
    svg_bad = (f'<svg viewBox="0 0 320 180" data-blueprint-sha256="{forged_sha}">'
               f'<rect width="320" height="180"/></svg>').encode()
    from deck_master.tasks import EnvelopeError
    with pytest.raises(EnvelopeError, match="different original image"):
        _accept_reconstruct(project, wrong_task, svg_bad)


def artifact_helper(store: Store, path: Path, role: str, page_ref: dict) -> dict:
    from deck_master.pipeline import artifact
    dependencies = [{"kind": "content", "identity": "page:p1", "sha256": page_ref["sha256"]}]
    return artifact(store, path, role, page_id="p1", dependencies=dependencies, derived_from=[page_ref])


def _review_task(project: Path, label: str) -> dict:
    store = Store(project)
    document = store.load_document()
    page_ref = document["pages"][0]["page"]
    task = tasks_mod.new_task(
        task_id=uuid.uuid4().hex[:12], operation_id=label, kind="review", scope_pages=["p1"],
        instruction="review the current outputs", inputs=[page_ref],
        dependencies=[{"kind": "content", "identity": "page:p1", "sha256": page_ref["sha256"]}],
        dispatch_revision=document["revision_id"], produced_against=content_identity(document),
    )
    task_ref = store.put_json_object(task)
    bumped = tasks_mod.bump_revision(document, {"operation_id": label + "-dispatch", "kind": "task_update",
                                                "description": "open review", "read_set": []})
    bumped["tasks"] = list(bumped.get("tasks") or []) + [task_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id=label + "-dispatch")
    return task


def _review_envelope(task: dict, status: str, subjects: list, finding: bool) -> dict:
    findings = []
    if finding:
        findings.append({
            "finding_id": "f-1", "kind": "conversion", "impact": "must_fix", "page_id": "p1",
            "element_refs": ["atom:p1:block:b1:text"], "message": "正文缺失模块",
            "expected": "完整正文", "actual": "缺一段", "evidence": [],
            "resolution": "open",
        })
    review = {
        "schema_version": "deck_review.v1",
        "review_id": task["operation_id"] + "-" + status,
        "kind": "conversion",
        "status": status,
        "subjects": subjects,
        "dependencies": [{"kind": "content", "identity": "page:p1",
                          "sha256": task["inputs"][0]["sha256"]}],
        "reviewer": {"type": "host_self", "id": "test", "execution_ref": None,
                     "independence_confirmed": False},
        "observations": ["工程测试记录"],
        "findings": findings,
        "created_at": "2026-09-20T00:00:00Z",
        "replaces": None,
    }
    return {"kind": "review", "files": [], "reviews": [review]}


def test_new_design_mode_and_failed_review_is_preserved(tmp_path: Path) -> None:
    # AC-B10: reference_mode='new_design' reaches the prompt projection, and a
    # failed review stays preserved (readable, still failed) instead of being
    # back-filled by a later passing review or by supersede.
    project = _create_project(tmp_path)
    store = Store(project)
    document = store.load_document()
    page_obj = store.read_object_json(document["pages"][0]["page"])
    request = project_prompt(page_obj, document["design_context"], [])
    assert request["projection"]["visual_spec"]["reference_mode"] == "new_design"
    assert '"reference_mode": "new_design"' in request["prompt"]

    # Adopt blueprint + SVG, then really produce; an open review task is
    # superseded by production, not rewritten as passed.
    document = _adopt_blueprint(tmp_path, project)
    blueprint_sha = store.read_object_json(document["pages"][0]["blueprint"])["file"]["sha256"]
    svg_bytes = (f'<svg viewBox="0 0 320 180" data-blueprint-sha256="{blueprint_sha}">'
                 f'<rect width="320" height="180" fill="#ffffff"/>'
                 f'<text x="20" y="60" font-family="{FAMILY}" font-size="20">设备条件收集前移</text>'
                 f'<text x="20" y="120" font-family="{FAMILY}" font-size="14">在现有售后门户嵌入设备条件表单。</text>'
                 f'</svg>').encode()
    task = _open_host_task(project, "reconstruct")
    _accept_reconstruct(project, task, svg_bytes)
    stale_review = _open_host_task(project, "review")
    from deck_master.pipeline import produce
    produce(project)

    superseded = store.read_object_json(store.load_document()["tasks"][-1])
    assert superseded["task_id"] == stale_review["task_id"]
    assert superseded["status"] == "superseded"

    # A failing review on the current outputs makes review_status fail...
    document = store.load_document()
    subjects = [document["outputs"]["pptx"], document["pages"][0]["page"]]
    fail_task = _review_task(project, "review-fail")
    outcome = service.accept_result(project, task_id=fail_task["task_id"], operation_id=fail_task["operation_id"],
                                    produced_against=fail_task["produced_against"],
                                    result_payload=_review_envelope(fail_task, "fail", subjects, finding=True))
    assert outcome["status"] == "accepted"
    fail_ref = store.load_document()["reviews"][-1]
    fail_bytes = store.read_object_bytes(fail_ref)
    assert review_status(store, store.load_document()) == "fail"

    # ...and later passing reviews never rewrite the failed record. All six
    # required review kinds must pass before the status turns pass.
    required = ("content", "blueprint_content", "blueprint_fidelity",
                "conversion", "readability", "privacy")
    for kind in required:
        pass_task = _review_task(project, f"review-pass-{kind}")
        envelope = _review_envelope(pass_task, "pass", subjects, finding=False)
        envelope["reviews"][0]["kind"] = kind
        outcome = service.accept_result(project, task_id=pass_task["task_id"],
                                        operation_id=pass_task["operation_id"],
                                        produced_against=pass_task["produced_against"],
                                        result_payload=envelope)
        assert outcome["status"] == "accepted"
    document = store.load_document()
    assert len(document["reviews"]) == 1 + len(required)
    assert store.read_object_bytes(fail_ref) == fail_bytes
    assert store.read_object_json(fail_ref)["status"] == "fail"
    # P1-02: the preserved fail keeps its finding open — a plain stack of
    # passing reviews cannot clear it; only a validated closing review can.
    assert review_status(store, document) == "fail"
    from deck_master.pipeline import artifact as pipeline_artifact
    work = store.staging_dir / "closing-fix"
    work.mkdir(parents=True, exist_ok=True)
    fixed_svg = work / "p1-fixed.svg"
    fixed_svg.write_text('<svg viewBox="0 0 320 180"><rect width="320" height="180"/></svg>')
    fix_ref = pipeline_artifact(store, fixed_svg, "svg", page_id="p1")
    document = store.load_document()
    bumped = tasks_mod.bump_revision(document, {"operation_id": "attach-fix-svg", "kind": "task_update",
                                                "description": "fixed svg", "read_set": []})
    bumped["pages"][0]["svg"] = fix_ref
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="attach-fix-svg")
    after_fix = store.load_document()
    closing = {
        "schema_version": "deck_review.v1",
        "review_id": "r-fail",
        "kind": "conversion",
        "status": "pass",
        "subjects": subjects + [fix_ref],
        "dependencies": [{"kind": "content", "identity": "page:p1",
                          "sha256": after_fix["pages"][0]["page"]["sha256"]}],
        "reviewer": {"type": "host_self", "id": "host-1", "execution_ref": None,
                     "independence_confirmed": False},
        "observations": ["复查新 SVG 产物:正文缺失已修复。"],
        "findings": [{"finding_id": "f-1", "kind": "conversion", "impact": "must_fix", "page_id": "p1",
                      "element_refs": ["atom:p1:block:b1:text"], "message": "正文缺失", "expected": "有",
                      "actual": "无", "evidence": [store.put_blob(b"recheck", ext="png")],
                      "resolution": "fixed"}],
        "created_at": "2026-09-23T00:00:00Z",
        "replaces": fail_ref,
    }
    closing_ref = store.put_json_object(closing)
    document = store.load_document()
    bumped = tasks_mod.bump_revision(document, {"operation_id": "close-fail-review", "kind": "task_update",
                                                "description": "closing review", "read_set": []})
    bumped["reviews"] = list(bumped.get("reviews") or []) + [closing_ref]
    store.commit_change(base_revision=document["revision_id"], document=bumped, operation_id="close-fail-review")
    assert store.read_object_bytes(fail_ref) == fail_bytes, "R0 stays immutable history"
    assert review_status(store, store.load_document()) == "pass"
