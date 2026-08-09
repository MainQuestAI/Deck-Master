from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from high_density.contracts import read_json
from high_density.engine import prepare_high_density, run_high_density
from high_density.icon_external_acceptance import TARGET_PAGE_IDS, build_icon_external_acceptance
from high_density.pptx import _line_cap_value, _line_join_value
from high_density.scene import load_scene
from high_density.svg_native import SvgNativeError, commands_to_svg_path, parse_svg_native
from high_density.svg import SvgVisualError, validate_svg
from high_density.visual import (
    VISUAL_QUALITY_POLICY,
    VISUAL_QUALITY_POLICY_SHA256,
    _best_local_alignment,
    _crop_image,
    _load_image,
    _object_checks,
    _silhouette_iou,
    VisualMetricsError,
    renderer_fingerprint,
)
from production.page_package import PagePackageIndex
from runtime.run_state import create_run

from test_high_density_builder_v2 import _prepared_fixture
from test_high_density_distinct_acceptance import FIXTURE, _package


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "high_density"


def _native_fixture(number: int) -> dict:
    path = FIXTURE_DIR / f"icon_fixture_{number:02d}.svg"
    return parse_svg_native(ElementTree.fromstring(path.read_text(encoding="utf-8")))


def _icon_run(tmp_path: Path, page_count: int = 7) -> Path:
    run = create_run(
        tmp_path / "runs",
        {"project_name": "synthetic high density icon stability", "run_mode": "fixture"},
        run_id="hd-icon-stability",
        force=True,
    )
    index = PagePackageIndex(run)
    for page in FIXTURE["pages"][:page_count]:
        index.write(_package(run.name, page))
    blueprint_dir = run / "high_density_build" / "blueprints"
    blueprint_dir.mkdir(parents=True, exist_ok=True)
    for order in range(1, page_count + 1):
        source = FIXTURE_DIR / f"icon_fixture_{order:02d}.svg"
        (blueprint_dir / f"P{order:03d}.svg").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return run


def test_group_inherited_icon_style_survives_pptx(tmp_path: Path) -> None:
    native = _native_fixture(1)
    icon = next(item for item in native["elements"] if item.get("group_id"))
    assert icon["style"]["stroke"] == "#419bfd"
    assert icon["style"]["stroke-linecap"] == "round"
    assert icon["style"]["stroke-linejoin"] == "round"

    run = _icon_run(tmp_path, page_count=1)
    assert run_high_density(run)["status"] == "completed"
    trace = read_json(run / "high_density_build" / "traces" / "pptx_trace.json")
    child = next(item for item in trace["elements"] if item.get("element_id") == "icon.header.P001.path")
    assert child["stroke_linecap"] == "round"
    assert child["stroke_linejoin"] == "round"
    assert child["fidelity"] == "native_normalized"


def test_symbol_use_expands_to_native_group() -> None:
    native = _native_fixture(2)
    group = native["groups"]["icon.header"]
    assert group["child_ids"] == ["blueprint.icon.header.use--icon.symbol.folder.path"]
    icon = next(item for item in native["elements"] if item.get("group_id"))
    assert icon["synthetic"] is True
    assert icon["bbox"] == {"x": 1500.0, "y": 68.0, "w": 54.0, "h": 40.0}


def test_symbol_use_applies_viewbox_scaling() -> None:
    source = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<defs><symbol id="symbol" viewBox="10 20 54 40"><path id="symbol.path" d="M10 20 L64 20 L64 60 L10 60 Z"/></symbol></defs>'
        '<use id="use" data-pptx-visual-id="icon.scaled" xlink:href="#symbol" x="100" y="200" width="108" height="80"/></svg>'
    )
    native = parse_svg_native(source)
    icon = native["elements"][0]
    assert icon["bbox"] == {"x": 100.0, "y": 200.0, "w": 108.0, "h": 80.0}


def test_nested_group_opacity_is_composed() -> None:
    source = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg"><g id="outer" opacity="0.5"><g id="icon" data-pptx-visual-id="icon.opacity" opacity="0.8"><path id="path" d="M0 0 L20 0 L20 20 Z" fill="#419bfd"/></g></g></svg>'
    )
    native = parse_svg_native(source)
    icon = next(item for item in native["elements"] if item.get("group_id"))
    assert icon["style"]["opacity"] == pytest.approx(0.4)


def test_multi_subpath_does_not_add_connector() -> None:
    native = _native_fixture(1)
    commands = next(item["commands"] for item in native["elements"] if item.get("group_id"))
    assert [item["op"] for item in commands].count("M") == 2
    serialized = commands_to_svg_path(commands)
    assert "Z M" in serialized
    assert serialized.count("M") == 2


def test_cubic_and_arc_paths_remain_curved() -> None:
    native = _native_fixture(4)
    commands = next(item["commands"] for item in native["elements"] if item.get("group_id"))
    operations = [item["op"] for item in commands]
    assert operations.count("C") >= 3
    assert set(operations) <= {"M", "C", "Z"}
    assert "A" not in commands_to_svg_path(commands)


def test_smooth_and_quadratic_paths_normalize_to_cubic() -> None:
    native = _native_fixture(3)
    commands = next(item["commands"] for item in native["elements"] if item.get("group_id"))
    operations = [item["op"] for item in commands]
    assert operations.count("C") >= 7
    assert set(operations) <= {"M", "C", "L", "Z"}


def test_linecap_join_and_stroke_opacity_roundtrip(tmp_path: Path) -> None:
    native = _native_fixture(6)
    first, second = [item for item in native["elements"] if item.get("group_id")]
    assert _line_cap_value(first["style"]) == "round"
    assert _line_join_value(first["style"]) == "round"
    assert first["style"]["stroke-opacity"] == pytest.approx(0.72)
    assert second["style"]["opacity"] == pytest.approx(0.82)

    run = _icon_run(tmp_path, page_count=6)
    assert run_high_density(run)["status"] == "completed"
    trace = read_json(run / "high_density_build" / "traces" / "pptx_trace.json")
    first_trace = next(item for item in trace["elements"] if item.get("element_id") == "icon.header.P006.path.01")
    second_trace = next(item for item in trace["elements"] if item.get("element_id") == "icon.header.P006.path.02")
    assert first_trace["stroke_opacity"] == pytest.approx(0.72)
    assert second_trace["stroke_opacity"] == pytest.approx(0.5904)


def test_evenodd_hole_survives_render() -> None:
    native = _native_fixture(5)
    icon = next(item for item in native["elements"] if item.get("group_id"))
    assert icon["style"]["fill-rule"] == "nonzero"
    assert [item["op"] for item in icon["commands"]].count("M") == 2
    assert commands_to_svg_path(icon["commands"]).count("Z") == 2


def test_ambiguous_evenodd_fails_closed() -> None:
    source = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg"><path id="ambiguous" fill-rule="evenodd" d="M0 0 L80 0 L80 80 L0 80 Z M40 -10 L100 -10 L100 50 L40 50 Z"/></svg>'
    )
    with pytest.raises(SvgNativeError, match="evenodd topology is ambiguous"):
        parse_svg_native(source)


def test_self_intersecting_or_open_evenodd_fails_closed() -> None:
    self_intersecting = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg"><path id="self-intersecting" fill-rule="evenodd" d="M0 0 L100 100 L0 100 L100 0 Z"/></svg>'
    )
    open_contour = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg"><path id="open-contour" fill-rule="evenodd" d="M0 0 L100 0 L100 100 L0 100"/></svg>'
    )
    with pytest.raises(SvgNativeError, match="evenodd topology self-intersects"):
        parse_svg_native(self_intersecting)
    with pytest.raises(SvgNativeError, match="evenodd topology requires closed subpaths"):
        parse_svg_native(open_contour)


def test_native_failure_contains_recovery_context(tmp_path: Path) -> None:
    path = tmp_path / "unsupported.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><path id="unsupported" transform="skewX(10)" d="M0 0 L10 0 Z"/></svg>',
        encoding="utf-8",
    )
    with pytest.raises(SvgVisualError, match=r"visual_id=<none> element_id=unsupported property=transform.*recovery: deck-master build retry"):
        validate_svg(path, page_id="P001")


def test_tiny_visual_registry_object_fails_crop_gate(tmp_path: Path) -> None:
    from PIL import Image

    with pytest.raises(VisualMetricsError, match="smaller than 8x8px"):
        _crop_image(Image.new("RGB", (256, 256), "white"), {"x": 20, "y": 20, "w": 7, "h": 20}, tmp_path / "tiny.png")


def test_small_visual_registry_object_uses_high_resolution_crop(tmp_path: Path) -> None:
    from PIL import Image

    output = _crop_image(Image.new("RGB", (256, 256), "white"), {"x": 20, "y": 20, "w": 8, "h": 12}, tmp_path / "small.png")
    assert Image.open(output).size == (512, 512)


def test_wrong_icon_same_bbox_fails_local_gate() -> None:
    from PIL import Image, ImageDraw

    source = Image.new("RGB", (256, 256), "white")
    candidate = Image.new("RGB", (256, 256), "white")
    source_draw = ImageDraw.Draw(source)
    candidate_draw = ImageDraw.Draw(candidate)
    source_draw.rounded_rectangle((48, 72, 208, 184), radius=18, outline="#419bfd", width=10)
    source_draw.line((48, 104, 208, 104), fill="#419bfd", width=10)
    candidate_draw.polygon([(58, 128), (184, 72), (184, 104), (214, 104), (128, 184), (42, 104), (72, 104), (72, 72)], fill="#419bfd")
    aligned, _, _ = _best_local_alignment(source, candidate)
    assert _silhouette_iou(source, aligned) < float(VISUAL_QUALITY_POLICY["svg_vs_pptx"]["silhouette_iou_min"])


def test_missing_p2_icon_fails_local_gate(tmp_path: Path) -> None:
    run, _, scene = _prepared_fixture(tmp_path)
    svg = run / "high_density_build" / "svg" / "P001.svg"
    document = ElementTree.parse(svg)
    parents = {child: parent for parent in document.getroot().iter() for child in list(parent)}
    icon_group = next(node for node in document.getroot().iter() if node.get("data-pptx-visual-id") == "icon.header.P001")
    parents[icon_group].remove(icon_group)
    document.write(svg, encoding="utf-8", xml_declaration=True)
    preview = run / "high_density_build" / "previews" / "P001.png"
    image = _load_image(preview)
    checks = _object_checks(
        run,
        scene,
        image,
        image,
        reference_path=preview,
        candidate_path=preview,
        comparison="blueprint_vs_svg",
        candidate_geometry=None,
    )
    assert checks[0]["status"] == "failed"
    assert checks[0]["finding"]["code"] == "missing_visual_registry_object"


def test_every_icon_has_crop_and_metrics(tmp_path: Path) -> None:
    run = _icon_run(tmp_path, page_count=1)
    assert run_high_density(run)["status"] == "completed"
    scene = load_scene(run, "P001")
    metrics = read_json(run / "high_density_build" / "reviews" / "P001.metrics.json")
    checks = {str(item["visual_id"]): item for item in metrics["object_checks"]}
    assert set(checks) == {str(item["visual_id"]) for item in scene["visual_registry"]}
    for check in checks.values():
        assert check["status"] == "pass"
        assert check["values"]["ssim"] >= 0.80
        for field in ("source_crop_path", "svg_crop_path"):
            assert (run / check[field]).is_file()
        assert len(check["source_crop_sha256"]) == 64
        assert len(check["svg_crop_sha256"]) == 64


def test_native_group_children_match_readback(tmp_path: Path) -> None:
    run = _icon_run(tmp_path, page_count=6)
    assert run_high_density(run)["status"] == "completed"
    report = read_json(run / "high_density_build" / "readback" / "readback_report.json")
    assert report["group_readback"]["status"] == "pass"
    assert report["local_visual_parity"] == report["visual_parity"]
    page = next(item for item in report["group_readback"]["pages"] if item["page_id"] == "P006")
    assert page["groups"][0]["child_element_ids"] == ["icon.header.P006.path.01", "icon.header.P006.path.02"]


def test_renderer_fingerprint_is_complete() -> None:
    fingerprint = renderer_fingerprint()
    assert {"python", "platform", "pillow", "numpy", "python_pptx", "librsvg", "libreoffice", "poppler", "font", "commands"} <= set(fingerprint)
    assert {"path", "sha256"} <= set(fingerprint["font"])
    assert len(fingerprint["font"]["sha256"]) == 64
    assert {"svg", "pptx_to_pdf", "pdf_to_png"} <= set(fingerprint["commands"])
    assert VISUAL_QUALITY_POLICY_SHA256 == read_json(ROOT / "docs/qa/high-density-builder-v2/visual-quality-policy.v1.json")["sha256"]


def test_seven_page_high_density_icon_end_to_end(tmp_path: Path) -> None:
    run = _icon_run(tmp_path)
    assert run_high_density(run)["status"] == "completed"
    report = read_json(run / "high_density_build" / "readback" / "readback_report.json")
    assert report["group_readback"]["expected_group_count"] == 7
    assert report["group_readback"]["actual_group_count"] == 7
    assert report["group_readback"]["status"] == "pass"
    trace = read_json(run / "high_density_build" / "traces" / "pptx_trace.json")
    assert len([item for item in trace["elements"] if item.get("object_type") == "group"]) == 7
    for index in range(1, 8):
        metrics = read_json(run / "high_density_build" / "reviews" / f"P{index:03d}.svg_vs_pptx.metrics.json")
        assert metrics["status"] == "pass"
        assert all(item["status"] == "pass" for item in metrics["object_checks"])
    with zipfile.ZipFile(run / "high_density_build" / "pptx" / "deck_high_density.pptx") as package:
        assert not any(name.startswith("ppt/media/") for name in package.namelist())


def test_external_icon_acceptance_blocks_without_local_six_page_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "icon-external-acceptance.json"
    evidence = build_icon_external_acceptance(tmp_path / "missing-external-run", output=output)
    assert evidence["status"] == "blocked_missing_local_benchmark_artifacts"
    assert evidence["target_page_ids"] == list(TARGET_PAGE_IDS)
    assert len(evidence["blockers"]) >= len(TARGET_PAGE_IDS)
    assert output.is_file()
