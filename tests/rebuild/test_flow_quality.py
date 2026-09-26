"""Flow Quality v1.1 acceptance tests (A-class evidence, spec v1.1).

Covers, one section per task:
- T1  work-order task projection, per-kind method dispatch, method_release;
- T2  CLI task fields and --task-file merge rules;
- T3  directory material entry with adopted/skipped/errored lists;
- T4  inputs show/update, content_basis and the update transaction;
- T5  content_update adoption and the task-fact staleness fix;
- T6  gap-based final review dispatch.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest

from deck_master import service
from deck_master.method_resources import method_resources, methods_sha256, resolve_root
from deck_master.models import bump_revision, compute_input_digest
from deck_master.store import Store
from deck_master.tasks import TaskConflict

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "flow-quality"


def _material(tmp_path: Path) -> Path:
    material = tmp_path / "material.md"
    material.write_text(
        "# 材料\n向运营团队说明条件自动处理方案。\n\n（尾部约束）合成材料，不可回写。",
        encoding="utf-8",
    )
    return material


def _raw_commit(store: Store, mutate) -> None:
    """Simulate a direct task-fact revision (any future write path)."""
    document = store.load_document()
    updated = {**document}
    mutate(updated)
    bumped = bump_revision(
        updated,
        {"operation_id": f"raw-{uuid.uuid4().hex[:12]}", "kind": "task_update",
         "description": "task fact corrected", "read_set": []},
    )
    store._commit_locked(base_revision=document["revision_id"], document=bumped, blobs=[])


# ---------------------------------------------------------------------------
# T1: work-order task projection and method dispatch


def test_work_order_carries_full_task_facts(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    response = service.create(
        project, brief="说明方案", sources=[_material(tmp_path)],
        audience="运营负责人", scenario="首次交流", presentation_mode="read_alone",
        page_limit=8, existing_decisions=["沿用现有门户"],
    )
    context = response["pending_tasks"][0]["project_context"]
    task = context["task"]
    for field in ("title", "brief", "audience", "scenario", "presentation_mode",
                  "page_limit", "existing_decisions", "presentation_mode_source"):
        assert field in task
    assert task["presentation_mode"] == "read_alone"
    assert task["presentation_mode_source"] == "provided"
    assert context["context_status"] == "current"
    assert context["input_alignment"] == "no_content"
    assert len(context["input_digest"]) == 64
    assert context["dispatch_revision"] == response["pending_tasks"][0]["dispatch_revision"]

    # continue and task status project the same facts (AC-01).
    continued = service.continue_project(project)
    assert continued["pending_tasks"][0]["project_context"]["task"]["audience"] == "运营负责人"
    status = service.task_status(project, task_id=response["pending_tasks"][0]["task_id"])
    assert status["pending_tasks"][0]["project_context"]["task"]["brief"] == "说明方案"


def test_default_presentation_mode_is_never_reported_as_provided(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    response = service.create(project, brief="说明方案", sources=[_material(tmp_path)])
    task = response["pending_tasks"][0]["project_context"]["task"]
    assert task["presentation_mode"] == "live"
    assert task["presentation_mode_source"] == "default"


def test_method_resources_dispatch_by_kind_and_are_readable(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    response = service.create(project, brief="说明方案", sources=[_material(tmp_path)])
    compose = response["pending_tasks"][0]
    compose_ids = [item["id"] for item in compose["method_resources"]]
    assert compose_ids == ["source-reading", "content-methods", "content-examples"]
    for item in compose["method_resources"]:
        path = Path(item["path"])
        assert path.is_file()
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert item["relative_path"].endswith(item["id"] + ".md")

    from deck_master.method_resources import method_release

    stored = Store(project).read_object_json(
        next(ref for ref in Store(project).load_document()["tasks"]
             if Store(project).read_object_json(ref)["task_id"] == compose["task_id"]))
    assert stored["method_release"]["methods_sha256"] == methods_sha256(compose["method_resources"])
    assert stored["method_release"]["release_id"]


def test_method_dispatch_mapping_by_kind_and_intent() -> None:
    from deck_master.method_resources import method_ids_for

    assert method_ids_for("compose", intent="initial") == (
        "source-reading", "content-methods", "content-examples")
    assert method_ids_for("compose", intent="input_revision") == (
        "source-reading", "content-methods", "content-examples", "input-update")
    assert method_ids_for("blueprint") == method_ids_for("reconstruct") == ("blueprint-svg",)
    assert method_ids_for("review") == ("review-and-repair",)
    assert method_ids_for("repair") == ("review-and-repair", "content-methods", "blueprint-svg")
    assert method_ids_for("compile") == ()
    # The dispatched entry list stays different between compose and review (AC-02).
    assert method_ids_for("compose") != method_ids_for("review")


def test_context_status_stale_after_task_facts_move(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    response = service.create(project, brief="说明方案", sources=[_material(tmp_path)])
    task_id = response["pending_tasks"][0]["task_id"]
    store = Store(project)
    _raw_commit(store, lambda doc: doc["task"].update(audience="新的受众"))
    status = service.task_status(project, task_id=task_id)
    context = status["pending_tasks"][0]["project_context"]
    assert context["context_status"] == "stale"
    assert "continue" in context["hint"]
    # The stale work order still binds to the dispatch snapshot facts.
    assert context["task"]["audience"] == ""


def test_dispatch_snapshot_sources_survive_current_mutation(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    response = service.create(project, brief="说明方案", sources=[_material(tmp_path)])
    task_id = response["pending_tasks"][0]["task_id"]
    store = Store(project)
    _raw_commit(store, lambda doc: doc.update(sources=[]))
    status = service.task_status(project, task_id=task_id)
    # Valid task: sources come from the dispatch snapshot, not the mutated current.
    assert status["pending_tasks"][0]["sources"], "dispatch snapshot sources must survive"
    assert status["pending_tasks"][0]["project_context"]["context_status"] == "stale"


# ---------------------------------------------------------------------------
# T2: CLI task fields and --task-file merge rules

from deck_master import cli


def _run_cli(argv, capsys):
    code = cli.main(argv)
    out, err = capsys.readouterr()
    stream = out if code == 0 else err
    payload = json.loads(stream) if stream.strip() else {}
    return code, payload


def test_cli_task_fields_land_in_document(tmp_path: Path, capsys) -> None:
    project = tmp_path / "proj"
    code, payload = _run_cli([
        "create", "--brief", "需求说明", "--source", str(_material(tmp_path)), "--out", str(project),
        "--audience", "运营负责人", "--scenario", "首次交流", "--presentation-mode", "read_alone",
        "--page-limit", "8", "--decision", "沿用现有门户", "--decision", "本期接口只读",
    ], capsys)
    assert code == 0, payload
    task = Store(project).load_document()["task"]
    assert task["audience"] == "运营负责人"
    assert task["scenario"] == "首次交流"
    assert task["presentation_mode"] == "read_alone"
    assert task["presentation_mode_source"] == "provided"
    assert task["page_limit"] == 8
    assert task["existing_decisions"] == ["沿用现有门户", "本期接口只读"]


def test_task_file_merge_cli_overrides_only_explicit_flags(tmp_path: Path, capsys) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({
        "title": "文件里的标题",
        "brief": "文件里的brief",
        "audience": "文件受众",
        "scenario": "文件场景",
        "presentation_mode": "mixed",
        "page_limit": 6,
        "existing_decisions": ["沿用现有门户"],
    }, ensure_ascii=False), encoding="utf-8")
    project = tmp_path / "proj"
    code, payload = _run_cli([
        "create", "--source", str(_material(tmp_path)), "--out", str(project),
        "--task-file", str(task_file), "--audience", "CLI受众",
    ], capsys)
    assert code == 0, payload
    task = Store(project).load_document()["task"]
    assert task["title"] == "文件里的标题"
    assert task["brief"] == "文件里的brief"
    assert task["audience"] == "CLI受众", "explicit CLI flag overrides the file value"
    assert task["scenario"] == "文件场景"
    assert task["presentation_mode"] == "mixed"
    assert task["presentation_mode_source"] == "provided"
    assert task["page_limit"] == 6
    assert task["existing_decisions"] == ["沿用现有门户"]


def test_decision_and_task_file_conflict_exit_2(tmp_path: Path, capsys) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({
        "brief": "文件brief", "existing_decisions": ["沿用现有门户"]}, ensure_ascii=False),
        encoding="utf-8")
    code, payload = _run_cli([
        "create", "--source", str(_material(tmp_path)), "--out", str(tmp_path / "proj"),
        "--task-file", str(task_file), "--decision", "CLI决定",
    ], capsys)
    assert code == 2
    assert payload["error"]["code"] == "task_field_conflict"
    assert not (tmp_path / "proj" / ".deckmaster").exists()


def test_unknown_task_file_field_exit_2(tmp_path: Path, capsys) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({"brief": "b", "narrative_plan": {}}, ensure_ascii=False),
                         encoding="utf-8")
    code, payload = _run_cli([
        "create", "--source", str(_material(tmp_path)), "--out", str(tmp_path / "proj"),
        "--task-file", str(task_file),
    ], capsys)
    assert code == 2
    assert payload["error"]["code"] == "task_field_conflict"


def test_brief_conflicts_and_empty_merge_exit_2(tmp_path: Path, capsys) -> None:
    brief_file = tmp_path / "brief.md"
    brief_file.write_text("文件brief", encoding="utf-8")
    code, payload = _run_cli([
        "create", "--brief", "CLI brief", "--brief-file", str(brief_file),
        "--source", str(_material(tmp_path)), "--out", str(tmp_path / "proj"),
    ], capsys)
    assert code == 2 and payload["error"]["code"] == "task_field_conflict"

    empty_file = tmp_path / "empty-task.json"
    empty_file.write_text(json.dumps({"brief": ""}, ensure_ascii=False), encoding="utf-8")
    code, payload = _run_cli([
        "create", "--source", str(_material(tmp_path)), "--out", str(tmp_path / "proj2"),
        "--task-file", str(empty_file),
    ], capsys)
    assert code == 2 and payload["error"]["code"] == "task_field_conflict"


# ---------------------------------------------------------------------------
# T3: directory material entry

from deck_master.errors import SourceUnreadable, SourceUnsupported
from deck_master.sources import discover_sources


def test_directory_expansion_skips_noise_and_keeps_output_named_dirs(tmp_path: Path) -> None:
    root = tmp_path / "materials"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "config.txt").write_text("noise", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "dep.md").write_text("noise", encoding="utf-8")
    (root / "output").mkdir()
    (root / "output" / "history.md").write_text("用户明确提供的历史方案", encoding="utf-8")
    (root / "~$report.docx").write_bytes(b"lock-bytes")
    (root / "empty.md").write_bytes(b"")
    (root / "real.md").write_text("真实材料", encoding="utf-8")
    (root / "binary.xyz").write_bytes(b"not supported")
    outside = tmp_path / "outside.txt"
    outside.write_text("外部材料", encoding="utf-8")
    (root / "escape-link.md").symlink_to(outside)
    (root / "inside-target.md").write_text("根内链接材料", encoding="utf-8")
    (root / "inside-link.md").symlink_to(root / "inside-target.md")

    result = discover_sources([root])
    adopted_names = {p.name for p in result["adopted"]}
    assert adopted_names == {"real.md", "history.md", "inside-link.md", "inside-target.md"}
    skipped = {Path(item["path"]).name: item["reason"] for item in result["skipped"]}
    assert "tool directory" in skipped[".git"]
    assert "tool directory" in skipped["node_modules"]
    assert "office lock file" in skipped["~$report.docx"]
    assert "zero-byte" in skipped["empty.md"]
    assert "unsupported format" in skipped["binary.xyz"]
    assert "symlink outside" in skipped["escape-link.md"]
    assert result["errored"] == []
    # `output/` is an ordinary directory name: never skipped as a whole.
    assert not any(Path(item["path"]).name == "output" for item in result["skipped"])


def test_explicit_files_keep_call_order_and_dir_contents_sort_stably(tmp_path: Path) -> None:
    second = tmp_path / "b-second.md"
    first = tmp_path / "a-first.md"
    second.write_text("2", encoding="utf-8")
    first.write_text("1", encoding="utf-8")
    directory = tmp_path / "dir"
    directory.mkdir()
    (directory / "z.md").write_text("z", encoding="utf-8")
    (directory / "a.md").write_text("a", encoding="utf-8")
    result = discover_sources([second, directory, first])
    assert [p.name for p in result["adopted"]] == ["b-second.md", "a.md", "z.md", "a-first.md"]


def test_create_with_directory_reports_three_lists(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "brief.md").write_text("正式要求正文", encoding="utf-8")
    (materials / ".git").mkdir()
    (materials / ".git" / "x.md").write_text("n", encoding="utf-8")
    (materials / "~$c.docx").write_bytes(b"l")
    project = tmp_path / "proj"
    response = service.create(project, brief="说明方案", sources=[materials])
    assert response["status"] == "created"
    assert [item["name"] for item in response["sources_adopted"]] == ["brief.md"]
    assert response["sources_errored"] == []
    reasons = " | ".join(item["reason"] for item in response["sources_skipped"])
    assert "tool directory" in reasons and "office lock" in reasons
    document = Store(project).load_document()
    import re
    assert re.fullmatch(r"src-[0-9a-f]{8}", document["sources"][0]["source_id"])


def test_explicit_bad_file_fails_whole_create_without_document(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.xyz"
    bad.write_bytes(b"junk")
    missing = tmp_path / "gone.md"
    project = tmp_path / "proj"
    for source, exc_type in ((bad, SourceUnsupported), (missing, SourceUnreadable)):
        with pytest.raises(exc_type):
            service.create(project, brief="说明方案", sources=[source])
    assert not (project / ".deckmaster").exists(), "no half-built Document may remain"
    code = cli.main(["create", "--brief", "b", "--source", str(bad), "--out", str(project)])
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] in ("source_unsupported", "source_unreadable")


def test_out_directory_inside_source_root_is_skipped(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "a.md").write_text("材料", encoding="utf-8")
    project = materials / "proj"
    project.mkdir()
    response = service.create(project, brief="说明方案", sources=[materials])
    skipped_paths = [item["path"] for item in response["sources_skipped"]]
    assert any(path.endswith("proj") for path in skipped_paths)
    assert [item["name"] for item in response["sources_adopted"]] == ["a.md"]


# ---------------------------------------------------------------------------
# T7: single method source

import subprocess


def test_resolve_root_ignores_cwd_and_fake_files(tmp_path: Path, monkeypatch) -> None:
    """A fake SKILL.md in the working directory must never be adopted."""
    (tmp_path / "SKILL.md").write_text("fake", encoding="utf-8")
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "content-methods.md").write_text("fake", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    root = resolve_root()
    assert root.name == "deck-master"
    assert "fake" not in (root / "SKILL.md").read_text(encoding="utf-8")


def test_canonical_methods_have_no_legacy_terms_or_paired_d1d2() -> None:
    root = Path(service.__file__).resolve().parents[2] / "skills" / "deck-master"
    assert root.is_dir(), "canonical skill must live in the repo"
    for path in [root / "SKILL.md", *(root / "references").glob("*.md")]:
        text = path.read_text(encoding="utf-8")
        for needle in ("deck_brief", "narrative_plan", "claim_map", "D1｜", "D2｜",
                       "成对方法", "skills-references"):
            assert needle not in text, f"{path.name} still contains {needle!r}"
    assert (root / "references" / "input-update.md").is_file()
    assert not (root / "prompts").exists()
    assert not (root / "schemas").exists()


def test_doctor_compose_reports_ready_method_root() -> None:
    from deck_master.doctor import diagnose

    result = diagnose("compose")
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["method_root"]["status"] == "ready", result
    assert checks["method:references/content-methods.md"]["status"] == "ready"
    assert result["status"] == "ready"


def test_wheel_matches_sdist_wheel_methods() -> None:
    """Heavy check guarded by the render marker set: reused from test_install
    (AC-15 lives there); here we only assert the build hook keeps the wheel
    self-consistent without the retired compatibility copies."""
    from pathlib import Path as _P

    repo = _P(service.__file__).resolve().parents[2]
    hook = (repo / "tools" / "build_hook.py").read_text(encoding="utf-8")
    assert "skills-references" not in hook
    data = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "skills-references" not in data


# ---------------------------------------------------------------------------
# T4: inputs show/update, content_basis and the update transaction


def _load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_input_digest_fixtures_recompute(tmp_path: Path) -> None:
    """AC-08: the packaged fixture digests must recompute under §5.1."""
    before = _load_fixture("input-context-before.json")
    after = _load_fixture("input-context-after.json")
    assert compute_input_digest(before) == before["input_digest"]
    assert compute_input_digest(after) == after["input_digest"]
    # Usage-note-only edits move the digest; display names never do.
    renamed = {**before, "sources": [{**s, "name": "显示名已改.md"} for s in before["sources"]]}
    assert compute_input_digest(renamed) == before["input_digest"]
    noted = {**before, "sources": [{**s, "usage_note": "新用途"} for s in before["sources"]]}
    assert compute_input_digest(noted) != before["input_digest"]


def _setup_project_with_pages(tmp_path: Path):
    """A project whose pages exist (draft-adopted fixtures) and whose inputs
    match the live fixtures."""
    materials = FIXTURES / "materials"
    project = tmp_path / "proj"
    task = _load_fixture("request-live.json")
    pages = _load_fixture("initial-pages.json")
    service.create(
        project, brief=task["brief"], title=task["title"],
        sources=[materials / "company.md", materials / "operations.md", materials / "interface-v1.md"],
        audience=task["audience"], scenario=task["scenario"],
        presentation_mode=task["presentation_mode"], page_limit=task["page_limit"],
        existing_decisions=task["existing_decisions"],
        draft={"pages": pages["pages"], "page_order": pages["page_order"]},
    )
    store = Store(project)
    document = store.load_document()
    # Map fixture source ids onto the real uuid ids by file name.
    id_by_name = {entry["name"]: entry["source_id"] for entry in document["sources"]}
    _raw_commit(store, lambda doc: doc.update(
        content_basis={"input_digest": compute_input_digest(document),
                       "input_revision_id": None, "resolved_by_task_id": None}))
    return project, store, id_by_name


def test_inputs_show_returns_current_facts(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    shown = service.inputs_show(project)
    assert shown["status"] == "ok"
    assert shown["input_alignment"] == "current"
    assert shown["content_basis"]["input_digest"] == shown["input_digest"]
    assert {entry["name"] for entry in shown["sources"]} == {"company.md", "operations.md", "interface-v1.md"}


def test_inputs_update_supersedes_and_dispatches(tmp_path: Path) -> None:
    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    # An open production task exists before the update (continue opens it).
    opened = service.continue_project(project)
    assert opened["pending_tasks"] and opened["pending_tasks"][0]["kind"] == "blueprint"
    before_revision = store.load_document()["revision_id"]
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    operation_id = "input-update-1"
    result = service.inputs_update(
        project, patch=patch, base_revision=before_revision,
        operation_id=operation_id, patch_dir=FIXTURES)
    assert result["status"] == "updated"
    assert result["input_alignment"] == "needs_reconciliation"
    assert result["superseded_tasks"], "open tasks must be superseded"
    document = store.load_document()
    tasks = [store.read_object_json(ref) for ref in document["tasks"]]
    superseded_ids = set(result["superseded_tasks"])
    assert opened["pending_tasks"][0]["task_id"] in superseded_ids
    open_now = [task for task in tasks if task["status"] in ("awaiting_host", "running")]
    assert len(open_now) == 1 and open_now[0].get("intent") == "input_revision"
    dispatched = next(service.task_summary(store, document, task)
                      for task in tasks if task.get("intent") == "input_revision")
    assert dispatched["kind"] == "compose"
    assert dispatched["project_context"]["input_digest"] == result["input_digest"]
    assert [item["id"] for item in dispatched["method_resources"]] == [
        "source-reading", "content-methods", "content-examples", "input-update"]
    # Pages, reviews and outputs all survive; only the interface source changed.
    replaced = next(entry for entry in document["sources"]
                    if entry["source_id"] == id_by_name["interface-v1.md"])
    assert replaced["name"] == "interface-v2.md"
    assert replaced["original_sha256"] == _load_fixture("input-context-after.json")["sources"][2]["original_sha256"]
    assert replaced["usage_note"] == "V2替代只读范围，允许草稿保存但不自动正式提交"
    replaced = next(entry for entry in document["sources"]
                    if entry["source_id"] == id_by_name["interface-v1.md"])
    assert replaced["name"] == "interface-v2.md"
    assert replaced["original_sha256"] == _load_fixture("input-context-after.json")["sources"][2]["original_sha256"]

    # Idempotent retry returns the original result without a new revision.
    replay = service.inputs_update(
        project, patch=patch, base_revision=result["revision_id"],
        operation_id=operation_id, patch_dir=FIXTURES)
    assert replay == result


def test_inputs_update_conflicts(tmp_path: Path) -> None:
    from deck_master.errors import InputRevisionConflict

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]

    with pytest.raises(InputRevisionConflict):
        service.inputs_update(project, patch=patch, base_revision="stale-revision",
                              operation_id="op-conflict", patch_dir=FIXTURES)
    # Same operation id, different content.
    other = {**patch, "reason": "另一个不同的变化"}
    service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="op-dual", patch_dir=FIXTURES)
    with pytest.raises(InputRevisionConflict):
        service.inputs_update(project, patch=other, base_revision=store.load_document()["revision_id"],
                              operation_id="op-dual", patch_dir=FIXTURES)


def test_inputs_update_failure_keeps_state(tmp_path: Path) -> None:
    from deck_master.errors import SourceUnreadable

    project, store, _ = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = {"task_patch": {"audience": "新受众"},
             "source_changes": {"add": [{"path": "materials/missing.md"}]},
             "reason": "补一份缺失的材料"}
    with pytest.raises(SourceUnreadable):
        service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                              operation_id="op-fail", patch_dir=FIXTURES)
    after = store.load_document()
    assert after["revision_id"] == document["revision_id"]
    assert after["task"]["audience"] == document["task"]["audience"]
    assert service.inputs_show(project)["input_alignment"] == "current"


def test_inputs_update_display_name_only_does_not_dispatch(tmp_path: Path) -> None:
    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    open_before = [store.read_object_json(ref)["task_id"] for ref in document["tasks"]
                   if store.read_object_json(ref)["status"] in ("awaiting_host", "running")]
    patch = {"task_patch": {},
             "source_changes": {"metadata": [{"source_id": id_by_name["company.md"],
                                              "name": "公司简介.md"}]},
             "reason": "只改显示名"}
    result = service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="op-name", patch_dir=FIXTURES)
    assert result["status"] == "unchanged"
    assert result["revision_id"] != document["revision_id"], "display-name change still commits"
    refreshed = store.load_document()
    assert refreshed["sources"][0]["name"] == "公司简介.md"
    assert service.inputs_show(project)["input_alignment"] == "current"
    open_after = [store.read_object_json(ref)["task_id"] for ref in refreshed["tasks"]
                  if store.read_object_json(ref)["status"] in ("awaiting_host", "running")]
    assert open_before == open_after


def test_irrelevant_material_update_still_awaits_host_judgment(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = {"task_patch": {},
             "source_changes": {"add": [{"path": "materials/unrelated-catalog.md"}]},
             "reason": "补一份无关设备清单"}
    result = service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="op-noise", patch_dir=FIXTURES)
    assert result["status"] == "updated"
    assert result["input_alignment"] == "needs_reconciliation"
    dispatched = result["pending_tasks"][0]
    assert dispatched["project_context"]["input_digest"] == result["input_digest"]


# ---------------------------------------------------------------------------
# T5: content_update adoption and staleness fixes

import io as _io

from PIL import Image as _Image

from deck_master.tasks import EnvelopeError


def _png_bytes(color=(245, 246, 250)) -> bytes:
    buffer = _io.BytesIO()
    _Image.new("RGB", (320, 180), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _accept_blueprint_envelope(project: Path, task: dict, page_entry: dict, png: bytes) -> dict:
    staging = project / ".deckmaster" / "staging" / task["operation_id"]
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "reference.png").write_bytes(png)
    envelope = {
        "kind": "blueprint",
        "files": [{"file_id": "b", "path": "reference.png", "media_type": "image/png"}],
        "artifact_specs": [{
            "file_id": "b", "role": "blueprint", "page_id": page_entry["page_id"],
            "derived_from": [page_entry["page"]],
            "provenance": {"source_type": "unknown", "tool": "host-imagegen",
                           "invocation_ref": None, "generated_from_page": page_entry["page"]},
        }],
    }
    return service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload=envelope)


def test_task_fact_change_rejects_old_scoped_result(tmp_path: Path) -> None:
    """T5④ (c93 defect): a Document.task change must invalidate open scoped
    results even when pages/design/sources did not move."""
    project, store, _ = _setup_project_with_pages(tmp_path)
    opened = service.continue_project(project)
    task = opened["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    document = store.load_document()
    page_entry = next(e for e in document["pages"] if e["page_id"] == task["scope_pages"][0])
    _raw_commit(store, lambda doc: doc["task"].update(audience="已变更的受众"))
    with pytest.raises(TaskConflict):
        _accept_blueprint_envelope(project, task, page_entry, _png_bytes())


def test_superseded_task_late_result_is_refused(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    opened = service.continue_project(project)
    task = opened["pending_tasks"][0]
    document = store.load_document()
    page_entry = next(e for e in document["pages"] if e["page_id"] == task["scope_pages"][0])
    service.inputs_update(project, patch={"task_patch": {"audience": "董事会"},
                                          "reason": "用户改为董事会汇报"},
                          base_revision=document["revision_id"], operation_id="supersede-input")
    from deck_master.tasks import StaleInputContext
    for _ in range(2):
        with pytest.raises(StaleInputContext):
            _accept_blueprint_envelope(project, task, page_entry, _png_bytes())
    assert store.load_document()["pages"] == document["pages"]


def test_input_revision_cannot_bypass_partial_update_with_full_pages(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    updated = service.inputs_update(
        project, patch={"task_patch": {"audience": "董事会"}, "reason": "调整受众"},
        base_revision=store.load_document()["revision_id"], operation_id="changed-audience")
    task = updated["pending_tasks"][0]
    before = store.load_document()
    payload = {"kind": "compose", **_load_fixture("initial-pages.json")}
    with pytest.raises(EnvelopeError, match="content_update"):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=payload)
    assert store.load_document() == before


@pytest.mark.parametrize("invalid", [
    {"remove_page_ids": [{}]}, {"upsert_pages": {}},
    {"unchanged_reason": 5}, {"impact_summary": []}, {"unknown": "ignored"},
])
def test_content_update_bad_shapes_are_controlled_errors(tmp_path: Path, invalid: dict) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    updated = service.inputs_update(
        project, patch={"task_patch": {"audience": "董事会"}, "reason": "调整受众"},
        base_revision=store.load_document()["revision_id"], operation_id="bad-result-shape")
    task = updated["pending_tasks"][0]
    before = store.load_document()
    update = {"input_digest": updated["input_digest"], "upsert_pages": [],
              "remove_page_ids": [], "page_order": [e["page_id"] for e in before["pages"]],
              "impact_summary": "逐页核对后没有正文变化", "unchanged_reason": "现有正文适合新受众",
              **invalid}
    with pytest.raises(EnvelopeError):
        service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"],
                              result_payload={"kind": "compose", "content_update": update})
    assert store.load_document() == before


def test_content_update_roundtrip_changes_only_target_page(tmp_path: Path) -> None:
    """AC-11: adopting the V1→V2 interface revision touches only p03."""
    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    # Real blueprints so the changed page keeps its original as history.
    for entry in store.load_document()["pages"]:
        task = service.open_blueprint_task(store, store.load_document(), entry)
        _accept_blueprint_envelope(project, task, entry, _png_bytes())
    document = store.load_document()
    before = {e["page_id"]: e for e in document["pages"]}

    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    update = service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="input-update-rt", patch_dir=FIXTURES)
    document = store.load_document()
    task = next(t for t in (store.read_object_json(r) for r in document["tasks"])
                if t.get("intent") == "input_revision")
    payload = _load_fixture("result-input-revision.json")
    payload["content_update"]["input_digest"] = update["input_digest"]
    outcome = service.accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload=payload)
    assert outcome["status"] == "accepted"

    after_doc = store.load_document()
    after = {e["page_id"]: e for e in after_doc["pages"]}
    assert [e["page_id"] for e in after_doc["pages"]] == ["p01", "p02", "p03"]
    for pid in ("p01", "p02"):
        assert after[pid] == before[pid], f"unchanged page {pid} must keep every slot"
    assert after["p03"]["page"]["sha256"] == outcome["new_page_hashes"]["p03"]
    assert after["p03"]["blueprint"] == before["p03"]["blueprint"], "original blueprint is kept"
    assert after_doc["outputs"] == document["outputs"], "outputs stay put during reconciliation"
    assert after["p03"]["svg"] is None and after["p03"]["svg_preview"] is None
    basis = after_doc["content_basis"]
    assert basis["input_digest"] == update["input_digest"]
    assert basis["input_revision_id"] == "input-update-rt"
    assert basis["resolved_by_task_id"] == task["task_id"]
    p03 = store.read_object_json(after["p03"]["page"])
    text = json.dumps(p03, ensure_ascii=False)
    import re as _re
    def _asserted(claim: str) -> bool:
        # A claim counts only when asserted; negated mentions (不得/不能/禁止…)
        # are exactly how the revised page states the boundary.
        for clause in _re.split("[。；;\n]", text):
            index = clause.find(claim)
            while index != -1:
                prefix = clause[:index]
                if not _re.search(r"(不得|不允许|禁止|不能|不会|不可|并非|不是|不扩大)", prefix):
                    return True
                index = clause.find(claim, index + 1)
        return False
    for claim in _load_fixture("expected-effects.json")["forbidden_claims"]:
        assert not _asserted(claim), f"forbidden claim asserted: {claim}"
    assert service.inputs_show(project)["input_alignment"] == "current"


def test_content_update_rejections(tmp_path: Path) -> None:
    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    update = service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="input-update-rj", patch_dir=FIXTURES)
    document = store.load_document()
    task = next(t for t in (store.read_object_json(r) for r in document["tasks"])
                if t.get("intent") == "input_revision")
    base_payload = _load_fixture("result-input-revision.json")
    base_payload["content_update"]["input_digest"] = update["input_digest"]

    def submit(payload):
        return service.accept_result(
            project, task_id=task["task_id"], operation_id=task["operation_id"],
            produced_against=task["produced_against"], result_payload=payload)

    stale = json.loads(json.dumps(base_payload, ensure_ascii=False))
    stale["content_update"]["input_digest"] = "0" * 64
    with pytest.raises(TaskConflict):
        submit(stale)

    ghost = json.loads(json.dumps(base_payload, ensure_ascii=False))
    ghost["content_update"]["page_order"] = ["p01", "p02", "p03", "p99"]
    with pytest.raises(EnvelopeError):
        submit(ghost)

    duplicate = json.loads(json.dumps(base_payload, ensure_ascii=False))
    duplicate["content_update"]["page_order"] = ["p01", "p02", "p02"]
    with pytest.raises(EnvelopeError):
        submit(duplicate)

    omission = json.loads(json.dumps(base_payload, ensure_ascii=False))
    omission["content_update"]["page_order"] = ["p01", "p02"]
    with pytest.raises(EnvelopeError):
        submit(omission)

    no_reason = json.loads(json.dumps(base_payload, ensure_ascii=False))
    no_reason["content_update"]["upsert_pages"] = []
    no_reason["content_update"].pop("unchanged_reason", None)
    with pytest.raises(EnvelopeError):
        submit(no_reason)

    with_artifact = json.loads(json.dumps(base_payload, ensure_ascii=False))
    with_artifact["artifact_specs"] = [{"file_id": "x", "role": "svg", "page_id": "p03"}]
    with pytest.raises(EnvelopeError):
        submit(with_artifact)

    # A plain (initial) compose task must not accept content_update.
    initial = next(t for t in (store.read_object_json(r) for r in document["tasks"])
                   if t["kind"] == "compose" and t.get("intent", "initial") == "initial"
                   and t["status"] == "completed")
    # Refused either as an envelope error (wrong task intent) or as a journal
    # conflict (this operation already produced a different result).
    with pytest.raises((EnvelopeError, TaskConflict)):
        service.accept_result(
            project, task_id=initial["task_id"], operation_id=initial["operation_id"],
            produced_against=initial["produced_against"], result_payload=base_payload)


def test_needs_reconciliation_gates_delivery_and_handoff(tmp_path: Path) -> None:
    from deck_master.editing import export_project
    from deck_master.errors import InputReconciliationPending
    from deck_master.handoff import check_handoff

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="input-update-gate", patch_dir=FIXTURES)

    # Give the project a current (fake) PPTX output so the export gate is the
    # thing under test, not the missing-output check.
    document = store.load_document()
    pptx_ref = store.put_json_object({"schema_version": "deck_artifact.v1",
                                      "artifact_id": "probe-pptx", "page_id": None,
                                      "role": "probe", "file": document["pages"][0]["page"],
                                      "media_type": "application/json", "created_at": "1970",
                                      "dependencies": [], "derived_from": [], "provenance": {},
                                      "reference_regions": [], "limitations": [],
                                      "editability": "probe"})
    from deck_master.models import bump_revision as _bump
    bumped = _bump(document, {"operation_id": "probe-output", "kind": "task_update",
                              "description": "probe output", "read_set": []})
    bumped["outputs"]["pptx"] = pptx_ref
    store._commit_locked(base_revision=document["revision_id"], document=bumped, blobs=[])

    with pytest.raises(InputReconciliationPending):
        export_project(project, output_dir=tmp_path / "delivery-out", purpose="delivery")
    fake_pptx = tmp_path / "candidate.pptx"
    fake_pptx.write_bytes(b"PK\x03\x04 not a real deck")
    handoff = check_handoff(project, file_path=fake_pptx, purpose="review")
    assert handoff["status"] == "blocked"
    assert "input_reconciliation_pending" in handoff["gaps"]

    # Review purpose still works and carries the annotation.
    exported = export_project(project, output_dir=tmp_path / "review-out", purpose="review")
    assert exported["status"] == "exported"
    report = json.loads((tmp_path / "review-out" / "delivery.json").read_text(encoding="utf-8"))
    assert report["input_alignment"] == "needs_reconciliation"
    assert report["notice"] == "待按新要求更新"


def test_view_carries_reconciliation_banner_data(tmp_path: Path) -> None:
    from deck_master.view import project_view

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="input-update-view", patch_dir=FIXTURES)
    view = project_view(project)
    assert view["input_alignment"] == "needs_reconciliation"
    assert view["reconciliation"]["notice"] == "待按新要求更新"
    assert "input-update-view" in (view["reconciliation"]["reason"] or "")
    # After adoption the banner data disappears (covered by the roundtrip test's
    # alignment); legacy projects report legacy_current without content_basis.
    _raw_commit(store, lambda doc: doc.pop("content_basis", None))
    assert project_view(project)["input_alignment"] == "legacy_current"


# ---------------------------------------------------------------------------
# T6: gap-based final review dispatch

from deck_master.review import REVIEW_DIMENSIONS, final_review_units, describe_review_units


def test_review_dimensions_defined_once() -> None:
    """AC-14: the six-dimension definition exists exactly once in the code."""
    src_root = Path(service.__file__).resolve().parent
    offenders = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "'content', 'blueprint_content', 'blueprint_fidelity', 'conversion'" in text and \
                path.name != "review.py":
            offenders.append(path.name)
    assert not offenders, f"dimension tuple re-declared in: {offenders}"
    assert len(REVIEW_DIMENSIONS) == 6
    from deck_master.review import REQUIRED_KINDS, PAGE_VISUAL_KINDS
    assert REQUIRED_KINDS is REVIEW_DIMENSIONS
    assert PAGE_VISUAL_KINDS == ("blueprint_content", "blueprint_fidelity", "readability")


def _add_final_review(store, doc, kind, page_ids, status="pass") -> None:
    """Craft a schema-valid final review bound to the current products."""
    from deck_master.editing import _current_artifact_digests

    digests = _current_artifact_digests(store, doc)
    pptx_ref = doc["outputs"]["pptx"]
    assert pptx_ref, "final reviews require a current pptx output"
    entries = {e["page_id"]: e for e in doc["pages"]}
    dependencies = [{"kind": "artifact", "identity": "pptx", "sha256": digests["artifact:pptx"]}]
    subjects = [pptx_ref]
    for pid in page_ids:
        dependencies.append({"kind": "content", "identity": f"page:{pid}",
                             "sha256": digests[f"content:page:{pid}"]})
        dependencies.append({"kind": "style", "identity": pid,
                             "sha256": digests[f"style:{pid}"]})
        subjects.append(entries[pid]["page"])
    review = {
        "schema_version": "deck_review.v1",
        "review_id": f"final-{kind}-{uuid.uuid4().hex[:8]}",
        "kind": kind,
        "status": status,
        "review_stage": "final",
        "subjects": subjects,
        "dependencies": dependencies,
        "reviewer": {"type": "host_self", "id": "host", "execution_ref": None,
                     "independence_confirmed": False},
        "observations": ["实际查看当前产物后记录"],
        "findings": [],
        "created_at": "2026-09-25T00:00:00Z",
        "replaces": None,
    }
    doc["reviews"] = list(doc.get("reviews") or []) + [store.put_json_object(review)]


def _force_fake_output(store) -> None:
    document = store.load_document()
    pptx_ref = store.put_json_object({"schema_version": "deck_artifact.v1",
                                      "artifact_id": "probe-pptx", "page_id": None,
                                      "role": "probe", "file": document["pages"][0]["page"],
                                      "media_type": "application/json", "created_at": "1970",
                                      "dependencies": [], "derived_from": [], "provenance": {},
                                      "reference_regions": [], "limitations": [],
                                      "editability": "probe"})
    bumped = bump_revision(document, {"operation_id": "probe-output", "kind": "task_update",
                                      "description": "probe output", "read_set": []})
    bumped["outputs"]["pptx"] = pptx_ref
    store._commit_locked(base_revision=document["revision_id"], document=bumped, blobs=[])


def test_final_units_list_only_real_gaps(tmp_path: Path) -> None:
    from deck_master.editing import check_summary

    project, store, _ = _setup_project_with_pages(tmp_path)
    _force_fake_output(store)
    doc = store.load_document()
    # p01 already has valid conversion + readability passes; nothing else valid.
    _add_final_review(store, doc, "conversion", ["p01"])
    _add_final_review(store, doc, "readability", ["p01"])
    store._commit_locked(base_revision=doc["revision_id"],
                         document=bump_revision(doc, {"operation_id": "add-reviews",
                                                      "kind": "review_update",
                                                      "description": "add final reviews",
                                                      "read_set": []}), blobs=[])
    doc = store.load_document()
    summary = check_summary(store, doc)
    units = final_review_units(doc, summary, input_alignment="current")
    covered = {(unit["kind"], pid) for unit in units for pid in unit["page_ids"]}
    assert ("conversion", "p01") not in covered, "valid dimension must not be required again"
    assert ("readability", "p01") not in covered
    assert ("conversion", "p02") in covered
    for kind in ("content", "blueprint_content", "blueprint_fidelity", "privacy"):
        assert (kind, "p01") in covered
    reasons = {(unit["kind"], unit["reason"]) for unit in units}
    assert ("conversion", "missing") in reasons
    # Per-page passes never promote themselves to a final pass:
    assert summary["status"] != "pass"


def test_units_relist_content_and_privacy_after_input_change(tmp_path: Path) -> None:
    from deck_master.editing import check_summary

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    _force_fake_output(store)
    doc = store.load_document()
    _add_final_review(store, doc, "content", ["p01", "p02", "p03"])
    _add_final_review(store, doc, "privacy", ["p01", "p02", "p03"])
    store._commit_locked(base_revision=doc["revision_id"],
                         document=bump_revision(doc, {"operation_id": "add-reviews",
                                                      "kind": "review_update",
                                                      "description": "add final reviews",
                                                      "read_set": []}), blobs=[])
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    service.inputs_update(project, patch=patch, base_revision=store.load_document()["revision_id"],
                          operation_id="input-update-units", patch_dir=FIXTURES)
    doc = store.load_document()
    summary = check_summary(store, doc)
    units = final_review_units(doc, summary, input_alignment="needs_reconciliation")
    for kind in ("content", "privacy"):
        unit = next(u for u in units if u["kind"] == kind)
        assert unit["reason"] == "changed_input"
        assert set(unit["page_ids"]) == {"p01", "p02", "p03"}


def test_reconciliation_without_page_changes_still_requires_new_input_review(tmp_path: Path) -> None:
    from deck_master.editing import check_summary

    project, store, _ = _setup_project_with_pages(tmp_path)
    _force_fake_output(store)
    doc = store.load_document()
    page_ids = [entry["page_id"] for entry in doc["pages"]]
    for kind in REVIEW_DIMENSIONS:
        _add_final_review(store, doc, kind, page_ids)
    _raw_commit(store, lambda current: current.update(reviews=doc["reviews"]))
    before = store.load_document()
    update = service.inputs_update(
        project, patch={"task_patch": {"audience": "新评审团队"}, "reason": "更换受众"},
        base_revision=before["revision_id"], operation_id="update-after-review")
    task = update["pending_tasks"][0]
    service.accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                          produced_against=task["produced_against"], result_payload={
                              "kind": "compose", "content_update": {
                                  "input_digest": update["input_digest"], "upsert_pages": [],
                                  "remove_page_ids": [], "page_order": page_ids,
                                  "unchanged_reason": "新受众已掌握相同背景，逐页核对后无需改正文"}})
    doc = store.load_document()
    assert doc["pages"] == before["pages"] and doc["reviews"] == before["reviews"]
    assert service.inputs_show(project)["input_alignment"] == "current"
    summary = check_summary(store, doc)
    units = final_review_units(doc, summary)
    assert {(u["kind"], u["reason"]) for u in units} == {
        ("content", "changed_input"), ("privacy", "changed_input")}
    # New observations under the new input close the gap, even though old
    # review history still contains stale records for those dimensions.
    for kind in ("content", "privacy"):
        _add_final_review(store, doc, kind, page_ids)
    _raw_commit(store, lambda current: current.update(reviews=doc["reviews"]))
    doc = store.load_document()
    assert final_review_units(doc, check_summary(store, doc)) == []


def test_final_work_order_instruction_from_units(tmp_path: Path) -> None:
    units = [{"kind": "conversion", "page_ids": ["p02"], "reason": "missing"},
             {"kind": "privacy", "page_ids": ["p01", "p03"], "reason": "changed_input"}]
    instruction = describe_review_units(units)
    assert "conversion" in instruction and "p02" in instruction and "missing" in instruction
    assert "privacy" in instruction and "changed_input" in instruction
    assert "已经有效的维度不再要求" in instruction
    empty = describe_review_units([])
    assert "已经有效" in empty or "均已有效" in empty


def test_open_final_review_task_carries_review_plan(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    units = [{"kind": "conversion", "page_ids": [e["page_id"] for e in document["pages"]],
              "reason": "missing"}]
    task = service.open_host_task(store, kind="review",
                                  page_ids=[e["page_id"] for e in document["pages"]],
                                  instruction=describe_review_units(units),
                                  review_stage="final", review_units=units)
    summary = service.task_summary(store, store.load_document(), task)
    assert summary["review_plan"]["units"] == units


# ---------------------------------------------------------------------------
# T8: old skills removed; single resolver line (AC-16)


def test_skills_tree_reduced_to_deck_master_and_resolver() -> None:
    repo = Path(service.__file__).resolve().parents[2]
    skills = repo / "skills"
    entries = sorted(p.name for p in skills.iterdir())
    assert entries == ["RESOLVER.md", "deck-master"]
    resolver = (skills / "RESOLVER.md").read_text(encoding="utf-8").strip()
    assert "skills/deck-master/SKILL.md" in resolver
    assert len(resolver.splitlines()) == 1


def test_old_skill_names_gone_from_living_surfaces() -> None:
    import subprocess as _subprocess

    repo = Path(service.__file__).resolve().parents[2]
    pattern = ("deck-autopilot|deck-brief|deck-builder|deck-doctor|deck-init|deck-learn|"
               "deck-planner|deck-producer|deck-quality|deck-review|deck-setup|"
               "deck-sourcing|deck-upgrade|ppt-deck-pro-max|ppt-quality-gate|ppt-master")
    result = _subprocess.run(
        ["rg", "-l", pattern, "src/", "tools/", "tests/", "pyproject.toml", "AGENTS.md", "skills/"],
        cwd=repo, capture_output=True, text=True)
    me = str(Path(__file__).relative_to(repo))
    files = [line for line in result.stdout.splitlines() if line.strip() and line != me]
    assert files == [], f"living references to removed skills: {files}"


def test_delivery_gate_surfaces_exit_3_code_via_cli(tmp_path: Path, capsys) -> None:
    from deck_master.editing import export_project

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    service.inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="input-update-cli", patch_dir=FIXTURES)
    # Minimal current output so the delivery gate (not the missing-output
    # check) is what refuses.
    document = store.load_document()
    pptx_ref = store.put_json_object({"schema_version": "deck_artifact.v1",
                                      "artifact_id": "probe-pptx", "page_id": None,
                                      "role": "probe", "file": document["pages"][0]["page"],
                                      "media_type": "application/json", "created_at": "1970",
                                      "dependencies": [], "derived_from": [], "provenance": {},
                                      "reference_regions": [], "limitations": [],
                                      "editability": "probe"})
    bumped = bump_revision(document, {"operation_id": "probe-output-cli", "kind": "task_update",
                                      "description": "probe output", "read_set": []})
    bumped["outputs"]["pptx"] = pptx_ref
    store._commit_locked(base_revision=document["revision_id"], document=bumped, blobs=[])
    code = cli.main(["export", "--project", str(project), "--out", str(tmp_path / "gate-out"),
                     "--purpose", "delivery"])
    assert code == 3
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "input_reconciliation_pending"
    assert not (tmp_path / "gate-out").exists()


def test_stale_scoped_result_reports_stale_input_context(tmp_path: Path) -> None:
    """§9: the input-moved refusal carries code stale_input_context (exit 5)."""
    from deck_master.tasks import StaleInputContext

    project, store, _ = _setup_project_with_pages(tmp_path)
    opened = service.continue_project(project)
    task = opened["pending_tasks"][0]
    document = store.load_document()
    page_entry = next(e for e in document["pages"] if e["page_id"] == task["scope_pages"][0])
    _raw_commit(store, lambda doc: doc["task"].update(audience="已变更的受众"))
    with pytest.raises(StaleInputContext):
        _accept_blueprint_envelope(project, task, page_entry, _png_bytes())
