from __future__ import annotations

import base64
import hashlib
import inspect
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from high_density import build_high_density_status, prepare_high_density, run_high_density
from high_density.blueprint import BlueprintInvalid, ensure_blueprint_manifest
from high_density.contracts import ContractError, assert_valid, read_json
from production.page_package import PageContent, PagePackageIndex, build_page_package
from runtime.next_step import resolve_next_step
from runtime.run_state import create_run


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "high_density"
FIXTURE = json.loads((FIXTURE_DIR / "fixture.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((FIXTURE_DIR / "expected.json").read_text(encoding="utf-8"))


def _blueprint(run: Path, page_id: str, *, fill: str = "#f7f9fb") -> Path:
    path = run / "high_density_build" / "blueprints" / f"{page_id}.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((FIXTURE_DIR / "blueprint.svg").read_text(encoding="utf-8").replace("#f7f9fb", fill), encoding="utf-8")
    return path


def _package(run_id: str, page: dict) -> dict:
    return build_page_package(
        run_id=run_id,
        content=PageContent(
            page_id=str(page["page_id"]),
            order=int(page["order"]),
            title=str(page["title"]),
            subtitle=str(page["subtitle"]),
            body_blocks=list(page["body_blocks"]),
            labels=list(page["labels"]),
            footnotes=list(page["footnotes"]),
            speaker_notes=str(page["speaker_notes"]),
            claim_bindings=list(page["claim_bindings"]),
            evidence_bindings=list(page["evidence_bindings"]),
            visual_spec={"page_type": page["page_class"]},
        ),
        status="ready_for_build",
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _make_run(tmp_path: Path, *, mode: str, page_count: int) -> tuple[Path, PagePackageIndex]:
    run = create_run(
        tmp_path / "runs",
        {"project_name": "synthetic high density fixture", "run_mode": mode},
        run_id=str(FIXTURE["run_id"]),
        force=True,
    )
    index = PagePackageIndex(run)
    for page in FIXTURE["pages"][:page_count]:
        index.write(_package(str(run.name), page))
    return run, index


def test_seven_page_fixture_completes_native_handback(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=7)
    for order in range(1, 8):
        _blueprint(run, f"P{order:03d}")

    prepared = prepare_high_density(run)
    result = run_high_density(run)

    assert prepared["status"] == "prepared"
    assert result["status"] == "completed"
    manifest = read_json(run / "high_density_build/high_density_manifest.json")
    build_manifest = read_json(run / "build/build_manifest.json")
    artifact_manifest = read_json(run / "build/artifact_manifest.json")
    render_result = read_json(run / "render_results/render_result.json")
    readback = read_json(run / "high_density_build/readback/readback_report.json")
    for kind, payload in (
        ("high_density_manifest", manifest),
        ("build_manifest", build_manifest),
        ("artifact_manifest", artifact_manifest),
        ("render_result", render_result),
    ):
        assert_valid(kind, payload)
    assert len(FIXTURE["pages"]) == EXPECTED["page_count"]
    assert [page["page_id"] for page in manifest["pages"]] == [page["page_id"] for page in FIXTURE["pages"]]
    assert build_manifest["builder_profile"] == "high_density"
    assert readback["slide_count"] == 7
    assert readback["speaker_notes_count"] == 7
    assert readback["status"] == "pass"
    completed_next_step = resolve_next_step(run)
    assert completed_next_step["recommended_skill"] == "deck-quality"
    assert completed_next_step["status"] == "needs_quality_review"
    assert "quality-gate render" in completed_next_step["next_command"]
    first_svg = next((run / "high_density_build/svg").glob("*.svg"))
    assert "<image" not in first_svg.read_text(encoding="utf-8").lower()
    with zipfile.ZipFile(run / "high_density_build/pptx/deck_high_density.pptx") as package:
        assert not any(name.startswith("ppt/media/") for name in package.namelist())


def test_production_waiting_state_is_resumable(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="production", page_count=1)
    prepare_high_density(run)

    waiting = run_high_density(run)
    status = build_high_density_status(run)
    next_step = resolve_next_step(run)
    build_manifest = read_json(run / "build/build_manifest.json")

    assert waiting["status"] == "awaiting_agent_build"
    assert waiting["current_stage"] == "content_lock"
    assert status["status"] == "awaiting_agent_build"
    assert status["next_action"]["kind"] == "agent_nbb_enrich"
    assert build_manifest["status"] == "building"
    assert next_step["status"] == "awaiting_agent_build"
    assert next_step["recommended_skill"] == "deck-builder-high-density"
    assert next_step["next_command"].endswith("--profile high-density")


def test_page_package_change_invalidates_downstream(tmp_path: Path) -> None:
    run, index = _make_run(tmp_path, mode="fixture", page_count=1)
    blueprint = _blueprint(run, "P001")
    prepare_high_density(run)
    first = run_high_density(run)
    old_svg = (run / "high_density_build/svg/P001.svg").read_text(encoding="utf-8")
    old_source_fingerprint = read_json(run / "build/build_manifest.json")["source_fingerprint"]
    assert first["status"] == "completed"

    package = read_json(run / "page_packages/P001.json")
    package["customer_visible"]["title"] = "Changed locked title"
    index.write(package)
    invalidated = run_high_density(run)

    new_source_fingerprint = read_json(run / "build/build_manifest.json")["source_fingerprint"]
    assert invalidated["status"] == "awaiting_agent_build"
    assert invalidated["current_stage"] == "content_lock"
    assert invalidated["next_action"]["kind"] == "agent_nbb_enrich"
    assert not (run / "high_density_build/content_locks/P001.json").exists()
    assert old_source_fingerprint != new_source_fingerprint
    assert not (run / "high_density_build/svg/P001.svg").exists()
    assert not (run / "high_density_build/pptx/deck_high_density.pptx").exists()

    prepare_high_density(run)
    _blueprint(run, "P001", fill="#fff3e8")
    completed = run_high_density(run)
    new_svg = (run / "high_density_build/svg/P001.svg").read_text(encoding="utf-8")
    assert completed["status"] == "completed"
    assert old_svg != new_svg
    assert "Changed locked title" in new_svg
    assert blueprint.exists()


def test_legacy_preview_adapter_is_explicit_in_fixture_mode(tmp_path: Path) -> None:
    run = create_run(
        tmp_path / "runs",
        {"project_name": "legacy adapter fixture", "run_mode": "fixture"},
        run_id="legacy-adapter",
        force=True,
    )
    (run / "preview_manifest.json").write_text(
        json.dumps({"pages": [{"page_id": "P001", "title": "Legacy title", "body": "Legacy body"}]}),
        encoding="utf-8",
    )
    _blueprint(run, "P001")

    prepare_high_density(run)
    adapted = read_json(run / "page_packages/P001.json")
    assert adapted["legacy_inferred"] is True
    assert adapted["status"] == "ready_for_build"
    assert run_high_density(run)["status"] == "completed"


def test_legacy_preview_adapter_rejects_unsafe_page_id(tmp_path: Path) -> None:
    run = create_run(
        tmp_path / "runs",
        {"project_name": "unsafe adapter fixture", "run_mode": "fixture"},
        run_id="unsafe-adapter",
        force=True,
    )
    (run / "preview_manifest.json").write_text(
        json.dumps({"pages": [{"page_id": "../outside", "title": "Unsafe", "body": "Blocked"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        prepare_high_density(run)
    status = build_high_density_status(run)
    assert status["status"] == "blocked"
    assert status["error"]["code"] == "HD_CONTENT_LOCK_INVALID"


def test_blueprint_prompt_drift_requires_regeneration(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    lock = read_json(run / "high_density_build/content_locks/P001.json")

    with pytest.raises(BlueprintInvalid, match="prompt is stale"):
        ensure_blueprint_manifest(run, "P001", lock, style_lock={"canvas": "4:3"})


def test_registered_asset_is_native_and_whole_page_asset_is_blocked(tmp_path: Path) -> None:
    run, index = _make_run(tmp_path, mode="fixture", page_count=1)
    asset_path = run / "assets" / "proof.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
    asset_sha = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    package = read_json(run / "page_packages/P001.json")
    package["asset_bindings"] = [{"asset_id": "proof-asset", "path": "assets/proof.png", "sha256": asset_sha, "approved": True}]
    index.write(package)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"

    scene = read_json(run / "high_density_build/page_scenes/P001.json")
    scene["elements"].append(
        {
            "element_id": "asset.proof",
            "kind": "image",
            "role": "proof_image",
            "priority": "P1",
            "bbox": {"x": 1280, "y": 700, "w": 240, "h": 120},
            "asset_ref": "proof-asset",
            "asset_sha256": asset_sha,
            "editability_target": "registered_asset",
            "asset_policy": "registered",
        }
    )
    from high_density.scene import write_scene

    write_scene(run, scene)
    (run / "high_density_build/reviews/P001.visual_review.json").unlink()
    assert run_high_density(run)["status"] == "completed"
    svg = (run / "high_density_build/svg/P001.svg").read_text(encoding="utf-8")
    assert 'data-pptx-asset="registered"' in svg
    readback = read_json(run / "high_density_build/readback/readback_report.json")
    assert readback["expected_image_count"] == 1
    assert readback["image_shape_count"] == 1

    scene["elements"][-1]["bbox"] = {"x": 0, "y": 0, "w": 1672, "h": 941}
    write_scene(run, scene)
    (run / "high_density_build/reviews/P001.visual_review.json").unlink()
    with pytest.raises(ValueError):
        run_high_density(run)
    status = build_high_density_status(run)
    assert status["error"]["code"] == "HD_ASSET_POLICY_BLOCKED"


def test_basic_path_compiles_to_editable_freeform(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"

    scene = read_json(run / "high_density_build/page_scenes/P001.json")
    scene["elements"].append(
        {
            "element_id": "connector.path",
            "kind": "path",
            "role": "connector",
            "priority": "P1",
            "bbox": {"x": 100, "y": 100, "w": 200, "h": 100},
            "path": "M 100 100 L 300 100 L 300 200 Z",
            "editability_target": "native_shape",
            "asset_policy": "none",
            "style": {"fill": "#dce8f4", "stroke": "#657485", "stroke_width": 1.5},
        }
    )
    scene["elements"].append(
        {
            "element_id": "arrow.polygon",
            "kind": "polygon",
            "role": "connector_arrow",
            "priority": "P1",
            "bbox": {"x": 320, "y": 100, "w": 48, "h": 36},
            "points": [[320, 100], [368, 118], [320, 136]],
            "editability_target": "native_shape",
            "asset_policy": "none",
            "style": {"fill": "#d96b3b", "stroke": "#d96b3b", "stroke_width": 1},
        }
    )
    from high_density.scene import write_scene

    write_scene(run, scene)
    (run / "high_density_build/reviews/P001.visual_review.json").unlink()
    result = run_high_density(run)
    assert result["status"] == "completed"
    trace = read_json(run / "high_density_build/traces/P001.json")
    assert sum(item.get("object_type") == "freeform" for item in trace["trace"]["elements"]) == 2


def test_failed_build_persists_blocked_status(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    scene = read_json(run / "high_density_build/page_scenes/P001.json") if (run / "high_density_build/page_scenes/P001.json").exists() else None
    assert scene is None
    (run / "high_density_build/blueprints/P001.svg").write_text("broken", encoding="utf-8")

    with pytest.raises(ValueError):
        run_high_density(run)

    status = build_high_density_status(run)
    assert status["status"] == "blocked"
    assert status["error"]["code"] == "HD_BLUEPRINT_REGEN_REQUIRED"
    assert status["next_action"]["kind"] == "retry"


def test_blueprint_ratio_drift_blocks_the_page(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    manifest_path = run / "high_density_build/blueprints/P001.manifest.json"
    manifest = read_json(manifest_path)
    manifest["slide_frame"] = {"x": 0, "y": 0, "w": 100, "h": 100}
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        run_high_density(run)

    status = build_high_density_status(run)
    assert status["status"] == "blocked"
    assert status["error"]["code"] == "HD_BLUEPRINT_REGEN_REQUIRED"


def test_overflow_blocks_with_svg_stage_error(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    scene = read_json(run / "high_density_build/page_scenes/P001.json")
    title = next(element for element in scene["elements"] if element["element_id"] == "title.main")
    title["bbox"]["h"] = 8
    from high_density.scene import write_scene

    write_scene(run, scene)
    (run / "high_density_build/reviews/P001.visual_review.json").unlink()

    with pytest.raises(ValueError):
        run_high_density(run)

    status = build_high_density_status(run)
    assert status["error"]["code"] == "HD_SVG_REVIEW_FAILED"
    assert status["error"]["stage"] == "svg"


def test_stale_visual_review_blocks_before_pptx(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    review_path = run / "high_density_build/reviews/P001.visual_review.json"
    review = read_json(review_path)
    review["svg_sha256"] = "0" * 64
    review_path.write_text(json.dumps(review) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        run_high_density(run)

    status = build_high_density_status(run)
    assert status["error"]["code"] == "HD_SVG_REVIEW_FAILED"
    assert status["error"]["stage"] == "visual_review"


def test_unsupported_curved_path_blocks_pptx_stage(tmp_path: Path) -> None:
    run, _ = _make_run(tmp_path, mode="fixture", page_count=1)
    _blueprint(run, "P001")
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    scene = read_json(run / "high_density_build/page_scenes/P001.json")
    scene["elements"].append(
        {
            "element_id": "curve.path",
            "kind": "path",
            "role": "connector",
            "priority": "P2",
            "bbox": {"x": 100, "y": 100, "w": 200, "h": 100},
            "path": "M 100 100 C 160 40 240 260 300 200",
            "editability_target": "native_shape",
            "asset_policy": "none",
            "style": {"fill": "none", "stroke": "#657485", "stroke_width": 1.5},
        }
    )
    from high_density.scene import write_scene

    write_scene(run, scene)
    (run / "high_density_build/reviews/P001.visual_review.json").unlink()

    with pytest.raises(ValueError):
        run_high_density(run)

    status = build_high_density_status(run)
    assert status["error"]["code"] == "HD_PPTX_EDITABILITY_FAILED"
    assert status["error"]["stage"] == "readback"


def test_high_density_contract_rejects_unsafe_lineage_path() -> None:
    payload = {
        "schema_version": "deck_content_lock.v1",
        "run_id": "run",
        "page_id": "P001",
        "page_package_ref": "../private.json",
        "page_package_sha256": "0" * 64,
        "source_fingerprint": "0" * 64,
        "customer_visible": {},
        "evidence_bindings": [],
        "enrichment": {
            "framework": "nbb",
            "version": "v1",
            "analysis": {},
            "derived_claims": [],
            "structure_decisions": [],
        },
        "content_lock_sha256": "0" * 64,
        "created_at": "2026-08-05T00:00:00+00:00",
    }
    with pytest.raises(ContractError):
        assert_valid("content_lock", payload)


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    """Expose pytest-style regression functions to the repository unittest gate."""
    suite = unittest.TestSuite()
    for name, test_fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(test_fn):
            continue

        def invoke(fn: object = test_fn) -> None:
            parameters = inspect.signature(fn).parameters
            with tempfile.TemporaryDirectory() as directory:
                if "tmp_path" in parameters:
                    fn(Path(directory))
                else:
                    fn()

        suite.addTest(unittest.FunctionTestCase(invoke, description=name))
    return suite
