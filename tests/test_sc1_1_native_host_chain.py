"""Native authoring starts from approved packages, without pre-running HD."""

import json
from pathlib import Path
import pytest
from PIL import Image
from production.page_package import PageContent, PagePackageIndex, build_page_package
from runtime.run_state import create_run, write_json
from runtime.build import run_build
from high_density.content import load_content_lock


def new_run(tmp_path, mode="image_blueprint"):
    root = create_run(tmp_path, {"project_name": "Native host chain", "run_mode": "production"}, run_id="native-new", force=True)
    package = build_page_package(
        run_id=root.name,
        content=PageContent(page_id="P001", order=1, title="Project overview", body_blocks=[], visual_spec={"page_role": "cover"}),
        status="ready_for_build",
    )
    PagePackageIndex(root).write(package)
    request = json.loads((root / "request.json").read_text())
    request.update(profile="native", authoring_mode=mode)
    write_json(root / "request.json", request)
    return root


def test_new_run_creates_content_lock_without_mbb_interview(tmp_path):
    root = new_run(tmp_path, "direct_svg")
    result = run_build(root)
    assert result["status"] == "awaiting_svg_authoring"
    lock = load_content_lock(root, "P001")
    assert lock["customer_visible"]["title"] == "Project overview"
    assert lock["enrichment"]["framework"] == "native_narrative"
    assert not (root / "high_density_build/mbb").exists()
    task = json.loads((root / result["host_task"]).read_text())
    assert task["pages"][0]["output_contract"]["kind"] == "svg_and_scene"


@pytest.mark.parametrize("extension", ["png", "jpg", "jpeg"])
def test_host_raster_resume_persists_reconstruction_task(tmp_path, extension):
    root = new_run(tmp_path)
    first = run_build(root)
    folder = root / "high_density_build/blueprints"
    folder.mkdir(parents=True, exist_ok=True)
    image = tmp_path / f"host.{extension}"
    Image.new("RGB", (1672, 941), "white").save(image)
    from build.native_tasks import submit_blueprint

    action = first["pages"][0]
    submit_blueprint(
        root,
        "P001",
        action_id=action["action_id"],
        produced_against=action["produced_against"],
        image_path=image,
        observation={"tool": "imagegen", "request_id": "test-generation", "description": "White 16:9 test image"},
    )
    result = run_build(root)
    assert result["status"] == "awaiting_agent_reconstruct"
    persisted = json.loads((root / result["host_task"]).read_text())
    assert persisted["status"] == result["status"]
    assert persisted["pages"][0]["output_contract"]["kind"] == "svg_and_scene"
    assert persisted["pages"][0]["blueprint_ref"].endswith("png" if extension == "png" else "jpg")
    again = run_build(root)
    assert again["pages"][0]["action_id"] == result["pages"][0]["action_id"]


def host_scene(root, lock):
    # Explicit host output for a real one-page cover, no fixture renderer.
    component = lock["required_component_ids"][0]
    return {
        "schema_version": "deck_page_scene.v2",
        "run_id": root.name,
        "page_id": "P001",
        "page_role": "cover",
        "canvas": {"width": 1672, "height": 941, "unit": "px"},
        "blueprint": {},
        "blueprint_sha256": "0" * 64,
        "content_lock_sha256": lock["content_lock_sha256"],
        "required_component_ids": [component],
        "required_text_refs": lock["required_text_refs"],
        "component_signature": [{"component_id": component, "present": True}],
        "visual_registry": [],
        "elements": [
            {
                "element_id": "P001.bg",
                "kind": "rect",
                "role": "background",
                "priority": "P2",
                "bbox": {"x": 0, "y": 0, "w": 1672, "h": 941},
                "z_index": 0,
                "style": {"fill": "#ffffff", "stroke": "none", "stroke_width": 0},
                "asset_policy": "none",
                "editability_target": "native_shape",
            },
            {
                "element_id": "P001.title",
                "kind": "text",
                "role": "title",
                "priority": "P0",
                "component_id": component,
                "bbox": {"x": 80, "y": 120, "w": 1450, "h": 100},
                "z_index": 1,
                "text": "Project overview",
                "text_ref": "content_lock.customer_visible.title",
                "style": {"fill": "#18212b", "font_family": "Arial", "font_weight": "bold"},
                "text_fit": {"preferred_size_px": 48, "min_size_px": 32, "max_lines": 1},
                "asset_policy": "none",
                "editability_target": "native_text",
            },
        ],
        "overflow_policy": {},
        "created_at": "2026-09-09T00:00:00Z",
    }


def test_submit_validates_pair_commits_and_replays(tmp_path):
    from build.native_engine import submit_approved_svg
    from high_density.svg import compile_svg
    from high_density.scene import load_scene

    root = new_run(tmp_path, "direct_svg")
    task = run_build(root)["pages"][0]
    lock = load_content_lock(root, "P001")
    scene = host_scene(root, lock)
    svg = compile_svg(scene, tmp_path / "host.svg").read_text()
    kwargs = dict(action_id=task["action_id"], produced_against=task["produced_against"], scene=scene)
    result = submit_approved_svg(root, "P001", svg, **kwargs)
    assert result["status"] == "svg_staged"
    assert load_scene(root, "P001") == scene
    assert submit_approved_svg(root, "P001", svg, **kwargs)["status"] == "already_applied"
    with pytest.raises(Exception, match="different"):
        submit_approved_svg(root, "P001", svg + " ", **kwargs)


def test_invalid_host_outputs_exhaust_real_budget(tmp_path):
    from build.native_engine import submit_approved_svg
    from workflow.actions import check_action_budget

    root = new_run(tmp_path, "direct_svg")
    task = run_build(root)["pages"][0]
    for _ in range(3):
        with pytest.raises(Exception, match="both SVG and Scene"):
            submit_approved_svg(root, "P001", "<svg/>", action_id=task["action_id"], produced_against=task["produced_against"])
    assert check_action_budget(root, task["task_id"], max_actions=3)["exhausted"]
    assert not (root / "high_density_build/svg/P001.svg").exists()
    with pytest.raises(Exception, match="budget exhausted"):
        run_build(root)


def test_unreceipted_raster_is_not_an_approved_blueprint(tmp_path):
    root = new_run(tmp_path)
    run_build(root)
    folder = root / "high_density_build/blueprints"
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1672, 941), "white").save(folder / "P001.png")
    assert run_build(root)["status"] == "awaiting_agent_imagegen"


def test_late_blueprint_cannot_replace_new_content(tmp_path):
    from build.native_tasks import submit_blueprint

    root = new_run(tmp_path)
    task = run_build(root)["pages"][0]
    package = root / "page_packages/P001.json"
    package.write_text(package.read_text() + "\n")
    image = tmp_path / "host.png"
    Image.new("RGB", (1672, 941), "white").save(image)
    with pytest.raises(Exception, match="stale"):
        submit_blueprint(
            root,
            "P001",
            action_id=task["action_id"],
            produced_against=task["produced_against"],
            image_path=image,
            observation={"tool": "imagegen", "request_id": "late", "description": "test"},
        )
    assert not (root / "high_density_build/blueprints/P001.png").exists()


def test_new_native_build_emits_real_complete_artifact_chain(tmp_path):
    import shutil

    if not shutil.which("soffice") or not shutil.which("pdftoppm"):
        pytest.skip("real native renderer is unavailable")
    import jsonschema
    from build.native_engine import submit_approved_svg
    from high_density.svg import compile_svg
    from runtime.build import build_status

    root = new_run(tmp_path, "direct_svg")
    task = run_build(root)["pages"][0]
    scene = host_scene(root, load_content_lock(root, "P001"))
    svg = compile_svg(scene, tmp_path / "host.svg").read_text()
    submit_approved_svg(root, "P001", svg, action_id=task["action_id"], produced_against=task["produced_against"], scene=scene)
    result = run_build(root)
    assert result["status"] == "completed"
    payload = json.loads((root / "build/native_compile_result.json").read_text())
    schema = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs/specs/sc1.1-native-deck-core/contracts/native-compile-result.v1.schema.json"
        ).read_text()
    )
    jsonschema.validate(payload, schema)
    assert payload["pages"][0]["text_objects"] == 1
    assert payload["pages"][0]["shape_objects"] == 1
    artifacts = json.loads((root / "build/artifact_manifest.json").read_text())
    assert {item["kind"] for item in artifacts["artifacts"]} == {"deck_pptx", "deck_pdf", "page_png", "deck_html"}
    assert all((root / item["path"]).is_file() for item in artifacts["artifacts"])
    # downstream status must not reject the native input-fingerprint contract
    assert build_status(root)["status"] == "completed"


def test_svg_blueprint_and_null_provider_request_id(tmp_path):
    from build.native_tasks import submit_blueprint

    root = new_run(tmp_path)
    task = run_build(root)["pages"][0]
    image = tmp_path / "host.svg"
    image.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900"><rect width="1600" height="900" fill="white"/></svg>')
    submit_blueprint(
        root,
        "P001",
        action_id=task["action_id"],
        produced_against=task["produced_against"],
        image_path=image,
        observation={"tool": "imagegen", "request_id": None, "tool_call_id": "call-local-1", "description": "Observed host image"},
    )
    result = run_build(root)
    assert result["status"] == "awaiting_agent_reconstruct"
    assert result["pages"][0]["blueprint_ref"].endswith(".svg")


def test_scene_identity_rejected_without_publishing_svg(tmp_path):
    from build.native_engine import submit_approved_svg

    root = new_run(tmp_path, "direct_svg")
    task = run_build(root)["pages"][0]
    scene = host_scene(root, load_content_lock(root, "P001"))
    scene["run_id"] = "other-run"
    with pytest.raises(Exception, match="identity"):
        submit_approved_svg(root, "P001", "<svg/>", action_id=task["action_id"], produced_against=task["produced_against"], scene=scene)
    assert not (root / "high_density_build/svg/P001.svg").exists()


def test_content_update_is_committed_before_new_host_task(tmp_path):
    from workflow.actions import revision_read, revision_input_path

    root = new_run(tmp_path, "direct_svg")
    old = run_build(root)["pages"][0]
    package = root / "page_packages/P001.json"
    payload = json.loads(package.read_text())
    payload["customer_visible"]["title"] = "Updated approved title"
    write_json(package, payload)
    new = run_build(root)["pages"][0]
    assert new["action_id"] != old["action_id"]
    with revision_read(root):
        lock = load_content_lock(root, "P001")
        current = json.loads(revision_input_path(root, package).read_text())
        assert lock["customer_visible"]["title"] == current["customer_visible"]["title"] == "Updated approved title"


def test_partial_imagegen_resume_only_dispatches_missing_pages(tmp_path):
    from build.native_tasks import submit_blueprint

    root = new_run(tmp_path)
    package = build_page_package(
        run_id=root.name,
        content=PageContent(page_id="P002", order=2, title="Second page", body_blocks=[], visual_spec={"page_role": "cover"}),
        status="ready_for_build",
    )
    PagePackageIndex(root).write(package)
    first = run_build(root)
    action = next(p for p in first["pages"] if p["page_id"] == "P001")
    image = tmp_path / "host.png"
    Image.new("RGB", (1672, 941), "white").save(image)
    submit_blueprint(
        root,
        "P001",
        action_id=action["action_id"],
        produced_against=action["produced_against"],
        image_path=image,
        observation={"tool": "imagegen", "description": "test image"},
    )
    pending = run_build(root)
    assert pending["status"] == "awaiting_agent_imagegen"
    assert [page["page_id"] for page in pending["pages"]] == ["P002"]
