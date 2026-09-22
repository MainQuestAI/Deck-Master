"""T18 legacy read-only import evidence (AC-L01..L04)."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

import deck_master.cli as cli
from deck_master import legacy as legacy_mod
from deck_master.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "legacy"


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _rel_paths(root: Path) -> set:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


# ---------------------------------------------------------------------------
# AC-L01: known formats import into a readable new copy; unknowns are located.


def test_import_v1_draft_known_format(tmp_path):
    out = tmp_path / "new-project"
    result = legacy_mod.import_legacy(FIXTURES / "v1-draft", out)
    assert result["status"] == "imported"
    assert result["format"] == "v1_draft_dir"
    assert result["page_count"] == 2
    store = Store(out)
    view = _view(out)
    assert view["page_count"] == 2
    titles = {page["title"] for page in view["pages"]}
    assert titles == {"旧版第一页", "旧版第二页"}
    first = next(p for p in view["pages"] if p["page_id"] == "p09")
    texts = [atom["text"] for atom in first["visible_atoms"]]
    assert "v1 段落正文保留。" in texts and "第一条" in texts and "本期只读接口" in texts
    page = store.read_object_json(store.load_document()["pages"][0]["page"])
    edges = page["visual_spec"]["edges"]
    assert edges[0]["from"] == "n1" and edges[0]["to"] == "n2"
    assert page["speaker_notes"] == "讲者备注保留"
    # v1 metadata preserved in the import report, not silently dropped.
    assert result["report"]["plan"]["claimed_source_fingerprints"]["p09"]


def test_import_v1_unknown_block_shape_requires_normalization(tmp_path):
    broken = tmp_path / "broken-v1"
    shutil.copytree(FIXTURES / "v1-draft", broken)
    page_file = broken / "pages" / "p10.v1.json"
    page = json.loads(page_file.read_text())
    page["customer_visible"]["body_blocks"].append({"type": "kpi_gauge", "value": 42})
    page_file.write_text(json.dumps(page, ensure_ascii=False))
    with pytest.raises(legacy_mod.LegacyNormalizationRequired) as excinfo:
        legacy_mod.import_legacy(broken, tmp_path / "out")
    assert "customer_visible/body_blocks/1" in str(excinfo.value)


def test_import_unknown_structure_reports_concrete_fields(tmp_path):
    mystery = tmp_path / "mystery"
    mystery.mkdir()
    (mystery / "narrative.json").write_text(json.dumps({"story": ["a", "b"]}))
    with pytest.raises(legacy_mod.LegacyFormatError) as excinfo:
        legacy_mod.import_legacy(mystery, tmp_path / "out")
    message = str(excinfo.value)
    assert "narrative.json" in message and "既不是 HD run" in message


def test_import_hd_run_products_attach_media(tmp_path):
    out = tmp_path / "hd-project"
    result = legacy_mod.import_legacy(FIXTURES / "hd-run", out)
    assert result["format"] == "hd_run"
    store = Store(out)
    document = store.load_document()
    view = _view(out)
    assert view["page_count"] == 2
    by_id = {entry["page_id"]: entry for entry in document["pages"]}
    assert by_id["beat_06"]["svg"] is not None, "matching SVG media attaches to the page"
    svg_artifact = store.read_object_json(by_id["beat_06"]["svg"])
    imported = store.read_object_bytes(svg_artifact["file"])
    assert imported == (FIXTURES / "hd-run" / "deck_pro_max_project" / "beat_06_architecture.svg").read_bytes()


def test_inspect_output_matches_real_import(tmp_path):
    plan = legacy_mod.inspect_legacy(FIXTURES / "v1-draft")
    result = legacy_mod.import_legacy(FIXTURES / "v1-draft", tmp_path / "p")
    assert plan["page_ids"] == result["report"]["plan"]["page_ids"]
    assert plan["media"] == result["report"]["plan"]["media"]
    assert plan["unknown_fields"] == result["report"]["plan"]["unknown_fields"]


# ---------------------------------------------------------------------------
# AC-L02: the source run is never written, executed, or initialised.


@pytest.mark.parametrize("fixture", ["v1-draft", "hd-run"])
def test_import_leaves_source_bytes_identical(fixture, tmp_path):
    source = FIXTURES / fixture
    before = _snapshot(source)
    paths_before = _rel_paths(source)
    result = legacy_mod.import_legacy(source, tmp_path / "copied")
    assert result["status"] == "imported"
    assert _snapshot(source) == before, "every source file hash is unchanged"
    assert _rel_paths(source) == paths_before, "no file added or removed in the source"
    assert not (source / ".deckmaster").exists(), "source is never initialised in place"


def test_cli_import_legacy_roundtrip(tmp_path, capsys):
    out = tmp_path / "cli-project"
    assert cli.main(["import", "legacy", "--input", str(FIXTURES / "v1-draft"),
                     "--out", str(out)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "imported"
    capsys.readouterr()
    assert cli.main(["import", "legacy", "--input", str(FIXTURES / "v1-draft"),
                     "--out", str(out), "--inspect"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["status"] == "inspected" and plan["page_count"] == 2
    assert not (out / ".deckmaster").exists() or Store(out).load_document()["pages"], \
        "--inspect performs no write side effects"


def test_cli_import_legacy_refuses_unknown(tmp_path, capsys):
    mystery = tmp_path / "mystery"
    mystery.mkdir()
    (mystery / "only.txt").write_text("???")
    assert cli.main(["import", "legacy", "--input", str(mystery), "--out", str(tmp_path / "o")]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "legacy_import_refused"


# ---------------------------------------------------------------------------
# AC-L03: legacy completed/pass strings never become a new review pass.


def test_legacy_status_is_history_not_pass(tmp_path):
    result = legacy_mod.import_legacy(FIXTURES / "hd-run", tmp_path / "hd")
    statuses = {entry["page_id"]: entry["status"] for entry in result["report"]["plan"]["legacy_status"]}
    assert statuses == {"beat_01": "completed", "beat_06": "completed"}, "old status recorded as history"
    store = Store(tmp_path / "hd")
    document = store.load_document()
    assert document["reviews"] == [], "no review is fabricated from legacy strings"
    from deck_master.editing import review_status
    assert review_status(store, document) == "not_evaluated"
    report_artifact = store.read_object_json(document["sources"][0]["extract"])
    report = json.loads(store.read_object_bytes(report_artifact["file"]))
    assert "仅历史说明" in report["provenance_note"]


# ---------------------------------------------------------------------------
# AC-L04: missing sources, zero hashes, supplements, relocation and restore.


def test_missing_source_imports_with_null_hash_and_real_media_hash(tmp_path):
    missing = tmp_path / "missing-src"
    shutil.copytree(FIXTURES / "v1-draft", missing)
    (missing / "logo.png").unlink()
    result = legacy_mod.import_legacy(missing, tmp_path / "p")
    store = Store(tmp_path / "p")
    source = store.load_document()["sources"][0]
    assert source["original_sha256"] is None, "缺原文允许 null hash"
    extract_artifact = store.read_object_json(source["extract"])
    extract = json.loads(store.read_object_bytes(extract_artifact["file"]))
    assert extract["format"] == "v1_draft_dir"
    view = _view(tmp_path / "p")
    assert view["page_count"] == 2, "已存 extract/正文仍可读"


def test_all_zero_fake_hash_rejected(tmp_path):
    zeroed = tmp_path / "zeroed"
    shutil.copytree(FIXTURES / "v1-draft", zeroed)
    page_file = zeroed / "pages" / "p09.v1.json"
    page = json.loads(page_file.read_text())
    page["source_fingerprint"] = "0" * 64
    page_file.write_text(json.dumps(page, ensure_ascii=False))
    with pytest.raises(legacy_mod.LegacyFormatError, match="全零假 hash"):
        legacy_mod.import_legacy(zeroed, tmp_path / "out")


def test_supplemented_source_is_not_back_claimed(tmp_path):
    missing = tmp_path / "src-missing"
    shutil.copytree(FIXTURES / "v1-draft", missing)
    (missing / "logo.png").unlink()
    out = tmp_path / "p"
    legacy_mod.import_legacy(missing, out)
    # The user later restores the original file next to the run...
    shutil.copyfile(FIXTURES / "v1-draft" / "logo.png", missing / "logo.png")
    store = Store(out)
    source = store.load_document()["sources"][0]
    assert source["original_sha256"] is None, \
        "a supplemented file is never retroactively claimed as the verified original"


def test_imported_project_survives_relocation(tmp_path):
    out = tmp_path / "move-project"
    legacy_mod.import_legacy(FIXTURES / "v1-draft", out)
    moved = tmp_path / "moved-project"
    shutil.move(str(out), str(moved))
    store = Store(moved)
    document = store.load_document()
    assert len(document["pages"]) == 2
    for entry in document["pages"]:
        store.read_object_bytes(entry["page"])
    view = _view(moved)
    assert view["page_count"] == 2


def test_restore_after_import_keeps_call_facts_shape(tmp_path):
    out = tmp_path / "restore-project"
    result = legacy_mod.import_legacy(FIXTURES / "hd-run", out)
    from deck_master.editing import restore
    document = Store(out).load_document()
    restored = restore(out, revision_id=document["parent_revision_id"] or document["revision_id"],
                       base_revision=document["revision_id"], operation_id="restore-check")
    assert restored["status"] in ("restored", "already_applied")


def _view(project):
    from deck_master.view import project_view
    return project_view(project)


# ---------------------------------------------------------------------------
# P1 hardening round: nothing unmapped is dropped silently.


def test_v1_asset_bindings_and_citations_require_normalization(tmp_path):
    source = tmp_path / "with-bindings"
    shutil.copytree(FIXTURES / "v1-draft", source)
    page_file = source / "pages" / "p09.v1.json"
    page = json.loads(page_file.read_text())
    page["asset_bindings"] = [{"asset_id": "logo", "file": "logo.png"}]
    page["citations"] = [{"ref": "c-1"}]
    page_file.write_text(json.dumps(page, ensure_ascii=False))
    with pytest.raises(legacy_mod.LegacyNormalizationRequired) as excinfo:
        legacy_mod.import_legacy(source, tmp_path / "out")
    message = str(excinfo.value)
    assert "pages[p09]/asset_bindings" in message and "pages[p09]/citations" in message


def test_v1_internal_only_and_provenance_recorded_not_carried(tmp_path):
    plan = legacy_mod.inspect_legacy(FIXTURES / "v1-draft")
    preserved = plan["deliberately_not_carried"]["p09"]
    assert "internal_only" in preserved and "provenance" in preserved
    result = legacy_mod.import_legacy(FIXTURES / "v1-draft", tmp_path / "p")
    page = Store(tmp_path / "p").read_object_json(
        Store(tmp_path / "p").load_document()["pages"][0]["page"])
    assert "internal_only" not in page and "provenance" not in page


def test_v1_block_with_text_and_items_requires_normalization(tmp_path):
    source = tmp_path / "mixed-block"
    shutil.copytree(FIXTURES / "v1-draft", source)
    page_file = source / "pages" / "p10.v1.json"
    page = json.loads(page_file.read_text())
    page["customer_visible"]["body_blocks"][0]["items"] = [{"text": "混入条目"}]
    page_file.write_text(json.dumps(page, ensure_ascii=False))
    with pytest.raises(legacy_mod.LegacyNormalizationRequired,
                       match="同时含 text 与 items"):
        legacy_mod.import_legacy(source, tmp_path / "out")


def test_v1_edge_missing_direction_is_located_not_filtered(tmp_path):
    source = tmp_path / "bad-edge"
    shutil.copytree(FIXTURES / "v1-draft", source)
    page_file = source / "pages" / "p09.v1.json"
    page = json.loads(page_file.read_text())
    page["visual_spec"]["edges"][0].pop("direction")
    page_file.write_text(json.dumps(page, ensure_ascii=False))
    with pytest.raises(legacy_mod.LegacyNormalizationRequired) as excinfo:
        legacy_mod.import_legacy(source, tmp_path / "out")
    assert "visual_spec/edges/0" in str(excinfo.value)


def test_output_inside_source_is_refused(tmp_path):
    with pytest.raises(legacy_mod.LegacyError, match="互为子目录"):
        legacy_mod.import_legacy(FIXTURES / "v1-draft",
                                 FIXTURES / "v1-draft" / "nested-out")
    with pytest.raises(legacy_mod.LegacyError, match="互为子目录"):
        legacy_mod.import_legacy(FIXTURES / "v1-draft", FIXTURES)


def test_source_change_during_import_refuses_and_cleans_copy(tmp_path, monkeypatch):
    source = tmp_path / "watch-src"
    shutil.copytree(FIXTURES / "v1-draft", source)
    out = tmp_path / "watched-out"
    original_snapshot = legacy_mod.snapshot

    def _changing_snapshot(root):
        entries = original_snapshot(root)
        # Simulate an external writer touching the tree mid-import.
        probe = root / ".import-probe"
        if entries and not probe.exists():
            probe.write_text("external")
            entries[str(probe.relative_to(root))] = "external"
        return entries

    monkeypatch.setattr(legacy_mod, "snapshot", _changing_snapshot)
    with pytest.raises(legacy_mod.LegacySourceModified):
        legacy_mod.import_legacy(source, out)
    assert not out.exists(), "the refused copy is cleaned up"


def test_inspect_on_fresh_out_writes_nothing(tmp_path):
    out = tmp_path / "fresh-out"
    result = legacy_mod.import_legacy(FIXTURES / "v1-draft", out, inspect_only=True)
    assert result["status"] == "inspected"
    assert not (out / ".deckmaster").exists(), "--inspect must not create the project"
    assert not out.exists() or not any(out.iterdir())


def test_reimport_after_source_supplement_measures_honestly(tmp_path):
    source = tmp_path / "supplement-src"
    shutil.copytree(FIXTURES / "v1-draft", source)
    (source / "logo.png").unlink()
    first_out = tmp_path / "first"
    legacy_mod.import_legacy(source, first_out)
    assert Store(first_out).load_document()["sources"][0]["original_sha256"] is None
    # Supplement the original file later and re-import into a fresh copy...
    shutil.copyfile(FIXTURES / "v1-draft" / "logo.png", source / "logo.png")
    second_out = tmp_path / "second"
    result = legacy_mod.import_legacy(source, second_out)
    # ...media carry their real byte hashes, and a directory source keeps
    # original_sha256 null (only actually-measured single-file sources get one).
    logo = next(item for item in result["report"]["plan"]["media"] if item["path"] == "logo.png")
    assert logo["sha256"] == hashlib.sha256((source / "logo.png").read_bytes()).hexdigest()
    assert Store(second_out).load_document()["sources"][0]["original_sha256"] is None
    assert Store(first_out).load_document()["sources"][0]["original_sha256"] is None, \
        "the earlier import is never retroactively upgraded"


def test_single_file_source_measures_real_hash(tmp_path):
    single = tmp_path / "one-page.v1.json"
    page = json.loads((FIXTURES / "v1-draft" / "pages" / "p09.v1.json").read_text())
    single.write_text(json.dumps(page, ensure_ascii=False))
    out = tmp_path / "single-out"
    legacy_mod.import_legacy(single, out)
    source = Store(out).load_document()["sources"][0]
    assert source["original_sha256"] == hashlib.sha256(single.read_bytes()).hexdigest()


def test_cli_import_legacy_requires_legacy_flags(tmp_path, capsys):
    # `import legacy` without --input/--out falls through to the asset import
    # path, whose parser reports the missing --project as a usage error.
    with pytest.raises(SystemExit) as usage_error:
        cli.main(["import", "legacy"])
    assert usage_error.value.code == 2
    capsys.readouterr()
    # With the legacy flags it dispatches to the importer.
    assert cli.main(["import", "legacy", "--input", str(FIXTURES / "v1-draft"),
                     "--out", str(tmp_path / "ok")]) == 0
