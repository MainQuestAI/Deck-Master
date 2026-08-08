from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from high_density.content import load_nbb_plan, load_page_packages
from high_density.contracts import assert_valid, read_json, sha256_file, sha256_json, write_json
from high_density.engine import prepare_high_density, run_high_density
from high_density.provider_smoke import ProviderSmokeError, build_provider_smoke_evidence
from high_density.scene import load_scene
from high_density.visual import compute_visual_metrics, normalize_blueprint
from production.page_package import PageContent, PagePackageIndex, build_page_package
from runtime.run_state import create_run


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "high_density"
FIXTURE = json.loads((FIXTURE_DIR / "fixture.json").read_text(encoding="utf-8"))
LAYOUTS = ["framework", "process", "table", "comparison", "architecture", "data_story", "dense_narrative"]


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


def _distinct_run(tmp_path: Path, page_count: int = 7) -> Path:
    run = create_run(
        tmp_path / "runs",
        {"project_name": "synthetic high density fixture distinct acceptance", "run_mode": "fixture"},
        run_id="hd-distinct-test",
        force=True,
    )
    index = PagePackageIndex(run)
    for page in FIXTURE["pages"][:page_count]:
        index.write(_package(run.name, page))
    blueprint_dir = run / "high_density_build" / "blueprints"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    for order in range(1, page_count + 1):
        source = ROOT / "tests" / "fixtures" / "high_density" / f"distinct_blueprint_{order:02d}.svg"
        (blueprint_dir / f"P{order:03d}.svg").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return run


def test_seven_page_distinct_acceptance_has_independent_lineage(tmp_path: Path) -> None:
    run = _distinct_run(tmp_path)
    prepare_high_density(run)
    result = run_high_density(run)

    assert result["status"] == "completed"
    packages = load_page_packages(run, expected_run_id=run.name)
    plan = load_nbb_plan(run, packages=packages, expected_run_id=run.name, require_approved=True)
    assert len(plan["storyline_candidates"]) == 3
    assert len({candidate["management_conclusion"] for candidate in plan["storyline_candidates"]}) == 3
    assert str(plan["scr"]["situation"]).startswith("The deck contains evidence-backed material about Synthetic")
    assert all(plan["scr"][field] for field in ("situation", "complication", "resolution", "evidence_refs", "decision_implication"))
    assert all("Page Package context" not in json.dumps(candidate) for candidate in plan["storyline_candidates"])
    ledger_ids = {str(item["evidence_id"]) for item in plan["evidence_ledger"]}
    for page, package in zip(plan["pages"], packages, strict=True):
        package_ids = {str(item.get("evidence_id") if isinstance(item, dict) else item) for item in package["evidence_bindings"]}
        assert set(page["evidence_refs"]).issubset(package_ids)
        assert set(page["evidence_refs"]).issubset(ledger_ids)
        assert page["caveat"] and page["so_what"] and page["handoff"]
        assert page["material_pool"]
        assert page["components"] and page["required_text_refs"]
        assert all(set(claim["evidence_refs"]).issubset(set(page["evidence_refs"])) for claim in page["derived_claims"])

    manifest = read_json(run / "high_density_build/high_density_manifest.json")
    blueprint_hashes = [str(page["blueprint"]["sha256"]) for page in manifest["pages"]]
    scene_payloads = [load_scene(run, f"P{index:03d}") for index in range(1, 8)]
    scene_signatures = [str(scene["scene_signature"]) for scene in scene_payloads]
    svg_hashes = [sha256_file(run / "high_density_build" / "svg" / f"P{index:03d}.svg") for index in range(1, 8)]
    render_hashes = [sha256_file(run / "high_density_build" / "previews" / f"P{index:03d}.pptx.png") for index in range(1, 8)]

    assert len(set(blueprint_hashes)) == 7
    assert len(set(scene_signatures)) == 7
    assert {str(scene["layout_id"]) for scene in scene_payloads} == set(LAYOUTS)
    assert len(set(svg_hashes)) == 7
    assert len(set(render_hashes)) == 7
    readback = read_json(run / "high_density_build/readback/readback_report.json")
    assert readback["status"] == "pass"
    assert readback["shape_readback"]["status"] == "pass"
    assert readback["media_relationships"]["status"] == "pass"


def test_blueprint_mutation_fails_old_visual_gate_before_fixture_rebuild(tmp_path: Path) -> None:
    run = _distinct_run(tmp_path, page_count=1)
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    scene = load_scene(run, "P001")
    manifest = read_json(run / "high_density_build/blueprints/P001.blueprint_manifest.json")
    blueprint = run / "high_density_build/blueprints/P001.svg"
    blueprint.write_text(blueprint.read_text(encoding="utf-8").replace("#f7f9fb", "#102030", 1), encoding="utf-8")
    mutated_blueprint = normalize_blueprint(run, manifest)
    old_svg_preview = run / "high_density_build/previews/P001.png"
    metrics = compute_visual_metrics(run, scene, mutated_blueprint, old_svg_preview)

    assert metrics["status"] == "failed"
    assert any(item["code"] in {"visual_ssim_below_threshold", "region_color_delta_high"} for item in metrics["findings"])

    rebuilt = run_high_density(run)
    assert rebuilt["status"] == "completed"
    assert load_scene(run, "P001")["blueprint_sha256"] != scene["blueprint_sha256"]


def test_provider_smoke_evidence_requires_real_provider_metadata(tmp_path: Path) -> None:
    run = _distinct_run(tmp_path, page_count=1)
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"

    with pytest.raises(ProviderSmokeError, match="production or benchmark run mode"):
        build_provider_smoke_evidence(run, page_id="P001")

    prompt = read_json(run / "high_density_build/prompts/P001.blueprint_prompt.json")
    challenge = prompt["provider_challenge"]
    provider = {
        "tool": "image_gen",
        "model": "fresh-provider-fixture",
        "request_id": "request-fixture-001",
        "challenge_nonce": challenge["nonce"],
        "prompt_sha256": prompt["prompt_sha256"],
        "requested_at": challenge["issued_at"],
        "responded_at": challenge["issued_at"],
    }
    provider["request_sha256"] = sha256_json(
        {key: provider[key] for key in ("tool", "model", "request_id", "challenge_nonce", "prompt_sha256", "requested_at")}
    )
    for filename in ("P001.blueprint_manifest.json", "P001.manifest.json"):
        manifest_path = run / "high_density_build" / "blueprints" / filename
        manifest = read_json(manifest_path)
        manifest["provider"] = provider
        write_json(manifest_path, manifest)

    with pytest.raises(ProviderSmokeError, match="production or benchmark run mode"):
        build_provider_smoke_evidence(run, page_id="P001")


def test_provider_challenge_lineage_cannot_use_stale_artifacts(tmp_path: Path) -> None:
    run = _distinct_run(tmp_path, page_count=1)
    prepare_high_density(run)
    assert run_high_density(run)["status"] == "completed"
    prompt = read_json(run / "high_density_build/prompts/P001.blueprint_prompt.json")
    request_path = run / "request.json"
    request = read_json(request_path)
    request["run_mode"] = "production"
    write_json(request_path, request)

    for filename in ("P001.blueprint_manifest.json", "P001.manifest.json"):
        manifest_path = run / "high_density_build" / "blueprints" / filename
        manifest = read_json(manifest_path)
        manifest["approval"]["source"] = "explicit_user"
        provider = manifest["provider"]
        provider["challenge_nonce"] = "0" * 32
        provider["request_sha256"] = sha256_json(
            {key: provider[key] for key in ("tool", "model", "request_id", "challenge_nonce", "prompt_sha256", "requested_at")}
        )
        write_json(manifest_path, manifest)

    assert prompt["provider_challenge"]["nonce"] != "0" * 32
    with pytest.raises(ProviderSmokeError, match="provider challenge is stale"):
        build_provider_smoke_evidence(run, page_id="P001")


def test_committed_provider_smoke_evidence_is_sanitized_and_valid() -> None:
    evidence = read_json(ROOT / "docs/qa/high-density-builder-v2/phase-4-provider-smoke-evidence.json")

    assert_valid("provider_smoke", evidence)
    serialized = json.dumps(evidence, ensure_ascii=False)
    assert "/Users/" not in serialized
    assert "/private/" not in serialized
    assert evidence["raw_provider_payload_included"] is False
    assert evidence["run_mode"] in {"production", "benchmark"}


def test_committed_73_page_evidence_has_sanitized_per_page_lineage() -> None:
    evidence = read_json(ROOT / "docs/qa/high-density-builder-v2/phase-4-73-page-external-mvp-index.json")
    pages = evidence["pages"]

    assert evidence["status"] == "pass_external_image_to_svg_mvp_evidence"
    assert evidence["reported_page_count"] == evidence["indexed_page_count"] == len(pages) == 73
    assert len({page["page_id"] for page in pages}) == 73
    assert all(page["status"] == "review_pass" for page in pages)
    assert all(len(page["artifacts"]) == 8 for page in pages)
    assert all(len(artifact["sha256"]) == 64 for page in pages for artifact in page["artifacts"].values())
    serialized = json.dumps(evidence, ensure_ascii=False)
    assert "/Users/" not in serialized
    assert "/private/" not in serialized
    assert "云南白药" not in serialized
