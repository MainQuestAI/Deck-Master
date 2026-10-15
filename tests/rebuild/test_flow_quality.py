"""Flow Quality software regression coverage (spec v1.1, current RC3 entry).

Host claims/reviews/provider events here are explicit L1 synthetic fixtures.
Render cases execute the actual compiler/renderer; no human/native-image or
professional acceptance is inferred from these unit diagnostics.

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
from deck_master.models import bump_revision, compute_input_digest, ModelError
from deck_master.eligibility import EligibilityBlocked
from deck_master.store import Store
from rc3_fixtures import claim_fixture_task, accept_synthetic_blueprint
from test_content_ops import prepare_editorial_project, v2_revision_envelope
from deck_master import tasks as tasks_mod
from deck_master.content import atom_ids
import copy
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


def test_work_order_exposes_intent_paths_and_only_dispatch_sources(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    created = service.create(project, brief='完整首稿', sources=[_material(tmp_path)])
    task = created['pending_tasks'][0]
    assert task['intent'] == 'initial' and task['method_release']['release_id']
    source = task['source_reading'][0]
    assert Path(source['original_path']).read_bytes() == _material(tmp_path).read_bytes()
    assert Path(source['extract_path']).is_file()
    store = Store(project)
    def change_source(doc):
        extract = store.read_object_json(doc['sources'][0]['extract'])
        extract['text'] = '新材料内容，不属于旧任务'
        doc['sources'][0]['extract'] = store.put_json_object(extract)
    _raw_commit(store, change_source)
    stale = service.task_status(project, task_id=task['task_id'])['pending_tasks'][0]
    assert stale['project_context']['context_status'] == 'stale'
    assert stale['source_reading'][0]['text'] == source['text']


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
    assert method_ids_for("blueprint") == method_ids_for("reconstruct") == ("blueprint-svg", "physical-units")
    assert method_ids_for("review") == ("review-and-repair", "physical-units")
    assert method_ids_for("repair") == ("review-and-repair", "content-methods", "blueprint-svg", "physical-units")
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


def test_package_configuration_omits_retired_method_resources() -> None:
    """Artifact contents and warm rebuilds are exercised by test_install.

    Cleanup code must be allowed to name the retired output directory.
    """
    repo = Path(service.__file__).resolve().parents[2]
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


def _original_copy_hash(page):
    from deck_master.models import canonical_json_bytes, sha256_bytes
    page = copy.deepcopy(page)
    page.pop('content_mapping', None)
    return sha256_bytes(canonical_json_bytes(page))


def _framing_envelope(store, task):
    from test_compose_v2_phases import _framing_narrative
    return {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'framing',
        **{key: task[key] for key in ('task_id', 'operation_id', 'produced_against')},
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
        'payload': {'narrative': _framing_narrative(store.load_document()['project_id'])}, 'usage_events': []}


def _include_new_page_scope(project, page_ids):
    """Explicitly name future Page identities before a membership transaction."""
    from deck_master import collaboration
    store = Store(project)
    doc = store.load_document()
    request = doc['collaboration']['request']
    collaboration.start_request(project, input={'intent': 'full_deck', 'content_intent': None,
        'scope': {**request['scope'], 'page_ids': page_ids},
        'replace_request_id': request['request_id'], 'instruction_evidence': {
            'kind': 'host_attested_instruction', 'text': 'L1 explicitly authorizes membership changes within these named Page identities: ' + ','.join(page_ids)}},
        base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
    prepare_editorial_project(project, review=False)


def _mapped_manuscript_page(value):
    """Author explicit unknown mappings for this imported L1 manuscript."""
    page = copy.deepcopy(value)
    if 'content_mapping' not in page:
        notes = page.get('speaker_notes') or ''
        page['content_mapping'] = {'narrative_ref': None, 'plan_role_page_id': page['page_id'],
            'visible_links': [{'element_ref': atom, 'narrative_node_ids': [], 'source_links': []}
                              for atom in sorted(atom_ids(page))],
            'speech_segments': ([{'segment_id': 'imported-notes', 'start_codepoint': 0,
                'end_codepoint': len(notes), 'narrative_node_ids': [], 'kind': 'cue',
                'estimated_seconds': None}] if notes else [])}
    return page


def _inputs_update(project, **kwargs):
    """Public input transaction; claims are explicit and separate from its receipt."""
    return service.inputs_update(project, **kwargs)


def _accept_result(project, **kwargs):
    store = Store(project)
    task = tasks_mod._lookup_task(store.load_document(), kwargs['task_id'], store)
    value = copy.deepcopy(kwargs['result_payload'])
    if task.get('protocol_version') == 'compose.v2' and task.get('intent') == 'input_revision' and 'content_update' in value:
        update = value['content_update']
        update['upsert_pages'] = [_mapped_manuscript_page(page) for page in update.get('upsert_pages', [])]
        outline = copy.deepcopy(store.read_object_json(store.load_document()['content_plan'])['input'])
        order = update.get('page_order') or outline['page_order']
        old_roles = {role['page_id']: role for role in outline['page_roles']}
        roles = []
        for pid in order:
            if pid in old_roles:
                roles.append(old_roles[pid])
            else:
                roles.append({'page_id': pid, 'role': 'Explicit synthetic imported page',
                    'audience_question': 'Unknown in this manuscript', 'intended_takeaway': 'Unknown in this manuscript',
                    'narrative_node_ids': [], 'source_links': [], 'required_qualifications': [],
                    'content_profile': 'mixed', 'density_rationale': 'Unmeasured imported copy',
                    'timing_seconds': None, 'transition_to_next': None})
        outline['page_roles'] = roles
        outline['page_order'] = order
        if order != store.read_object_json(store.load_document()['content_plan'])['input']['page_order']:
            for chapter in outline['chapters']:
                chapter['page_ids'] = [pid for pid in order if pid in chapter['page_ids']]
            fresh = [pid for pid in order if pid not in old_roles]
            if outline['chapters']:
                outline['chapters'][-1]['page_ids'].extend(fresh)
        value.setdefault('content_plan', outline)
        original = value
        value = v2_revision_envelope(store, task, value)
        if not update.get('upsert_pages') and not update.get('remove_page_ids') and not update.get('unchanged_reason'):
            value['payload']['diff']['summary'] = ''
        for forbidden in ('pages', 'page_order', 'artifact_specs', 'reviews'):
            if original.get(forbidden):
                value[forbidden] = original[forbidden]
    if task.get('protocol_version') == 'generation.v1' and task['kind'] == 'blueprint' and task['status'] in ('awaiting_host', 'running') and tasks_mod.task_inputs_current(store, store.load_document(), task):
        return accept_synthetic_blueprint(project, task=task, result_payload=value,
            execution_ref=task.get('execution_ref') or 'L1-flow-image-host', scenario='Classic flow fixture; isolated synthetic Codex events')
    if task['status'] == 'awaiting_host' and tasks_mod.task_inputs_current(store, store.load_document(), task):
        claim_fixture_task(project, task, execution_ref='L1-flow-host')
    return service.accept_result(project, **{**kwargs, 'result_payload': value})


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
    prepare_editorial_project(project)
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
    result = _inputs_update(
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
    replay = _inputs_update(
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
        _inputs_update(project, patch=patch, base_revision="stale-revision",
                              operation_id="op-conflict", patch_dir=FIXTURES)
    # Same operation id, different content.
    other = {**patch, "reason": "另一个不同的变化"}
    _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="op-dual", patch_dir=FIXTURES)
    with pytest.raises(InputRevisionConflict):
        _inputs_update(project, patch=other, base_revision=store.load_document()["revision_id"],
                              operation_id="op-dual", patch_dir=FIXTURES)


def test_inputs_update_failure_keeps_state(tmp_path: Path) -> None:
    from deck_master.errors import SourceUnreadable

    project, store, _ = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = {"task_patch": {"audience": "新受众"},
             "source_changes": {"add": [{"path": "materials/missing.md"}]},
             "reason": "补一份缺失的材料"}
    with pytest.raises(SourceUnreadable):
        _inputs_update(project, patch=patch, base_revision=document["revision_id"],
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
    result = _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="op-name", patch_dir=FIXTURES)
    assert result["status"] == "unchanged"
    assert result["revision_id"] != document["revision_id"], "display-name change still commits"
    refreshed = store.load_document()
    assert refreshed["sources"][0]["name"] == "公司简介.md"
    assert service.inputs_show(project)["input_alignment"] == "current"
    open_after = [store.read_object_json(ref)["task_id"] for ref in refreshed["tasks"]
                  if store.read_object_json(ref)["status"] in ("awaiting_host", "running")]
    assert open_before == open_after


def test_rename_source_keeps_existing_compose_task_usable(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    created = service.create(project, brief='完整首稿', sources=[_material(tmp_path)])
    task = created['pending_tasks'][0]
    store = Store(project)
    doc = store.load_document()
    _inputs_update(project, patch={'reason': '修正显示名', 'source_changes': {'metadata': [
        {'source_id': doc['sources'][0]['source_id'], 'name': '显示名.md'}]}},
        base_revision=doc['revision_id'], operation_id='rename-during-compose')
    assert service.task_status(project, task_id=task['task_id'])['pending_tasks'][0]['project_context']['context_status'] == 'current'
    result = _accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                                   produced_against=task['produced_against'],
                                   result_payload=_framing_envelope(store, task))
    assert result['status'] == 'accepted'


def test_input_update_preserves_restrictions_and_marks_provided_mode(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    service.create(project, brief='完整首稿', sources=[_material(tmp_path)])
    store = Store(project)
    _raw_commit(store, lambda doc: doc['sources'][0].update(external_use='restricted', restriction='内部材料',
                                                          usage_note='原用途'))
    doc = store.load_document()
    replacement = tmp_path / 'v2.md'
    replacement.write_text('已确认的第二版')
    _inputs_update(project, patch={'reason': '独立阅读与材料升级',
        'task_patch': {'presentation_mode': 'read_alone'}, 'source_changes': {'replace': [
            {'source_id': doc['sources'][0]['source_id'], 'path': str(replacement), 'usage_note': ''}]}},
        base_revision=doc['revision_id'], operation_id='replace-restricted')
    after = store.load_document()
    assert after['task']['presentation_mode_source'] == 'provided'
    assert after['sources'][0]['external_use'] == 'restricted'
    assert after['sources'][0]['restriction'] == '内部材料'
    assert after['sources'][0].get('usage_note', '') == ''


def test_input_update_receipt_survives_failure_after_pointer_swap(tmp_path: Path, monkeypatch) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    patch = {'reason': '更换受众', 'task_patch': {'audience': '财务团队'}}
    before = store.load_document()
    original = Store._commit_locked
    def interrupted(self, **kwargs):
        original(self, **kwargs)
        raise OSError('process interrupted after pointer swap')
    monkeypatch.setattr(Store, '_commit_locked', interrupted)
    with pytest.raises(OSError):
        _inputs_update(project, patch=patch, base_revision=before['revision_id'], operation_id='durable-input')
    monkeypatch.setattr(Store, '_commit_locked', original)
    after = store.load_document()
    result = _inputs_update(project, patch=patch, base_revision=before['revision_id'], operation_id='durable-input')
    assert result['revision_id'] == after['revision_id']
    assert store.load_document() == after


def test_uncommitted_input_receipt_is_not_reported_as_success(tmp_path: Path, monkeypatch) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    before = store.load_document()
    patch = {'reason': '更换受众', 'task_patch': {'audience': '财务团队'}}
    original = Store._commit_locked
    def interrupted(self, **kwargs):
        raise OSError('process interrupted before pointer swap')
    monkeypatch.setattr(Store, '_commit_locked', interrupted)
    with pytest.raises(OSError):
        _inputs_update(project, patch=patch, base_revision=before['revision_id'], operation_id='retry-input')
    assert store.load_document() == before
    monkeypatch.setattr(Store, '_commit_locked', original)
    result = _inputs_update(project, patch=patch, base_revision=before['revision_id'], operation_id='retry-input')
    assert result['revision_id'] == store.load_document()['revision_id'] != before['revision_id']


def test_delivery_reconciliation_reason_before_first_pptx(tmp_path: Path) -> None:
    from deck_master.editing import export_project
    from deck_master.errors import InputReconciliationPending
    project, store, _ = _setup_project_with_pages(tmp_path)
    _inputs_update(project, patch={'reason': '更换受众', 'task_patch': {'audience': '财务团队'}},
                          base_revision=store.load_document()['revision_id'], operation_id='before-first-pptx')
    with pytest.raises((InputReconciliationPending, EligibilityBlocked)):
        export_project(project, output_dir=tmp_path / 'delivery', purpose='delivery')


def test_irrelevant_material_update_still_awaits_host_judgment(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = {"task_patch": {},
             "source_changes": {"add": [{"path": "materials/unrelated-catalog.md"}]},
             "reason": "补一份无关设备清单"}
    result = _inputs_update(project, patch=patch, base_revision=document["revision_id"],
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
    return _accept_result(
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
    _inputs_update(project, patch={"task_patch": {"audience": "董事会"},
                                          "reason": "用户改为董事会汇报"},
                          base_revision=document["revision_id"], operation_id="supersede-input")
    for _ in range(2):
        with pytest.raises(TaskConflict):
            _accept_blueprint_envelope(project, task, page_entry, _png_bytes())
    assert store.load_document()["pages"] == document["pages"]


def test_input_revision_cannot_bypass_partial_update_with_full_pages(tmp_path: Path) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    updated = _inputs_update(
        project, patch={"task_patch": {"audience": "董事会"}, "reason": "调整受众"},
        base_revision=store.load_document()["revision_id"], operation_id="changed-audience")
    task = updated["pending_tasks"][0]
    claim_fixture_task(project, task, execution_ref='L1-invalid-full-result')
    before = store.load_document()
    payload = {"kind": "compose", **_load_fixture("initial-pages.json")}
    with pytest.raises((EnvelopeError, ModelError), match="compose_result|content_update"):
        _accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
                              produced_against=task["produced_against"], result_payload=payload)
    assert store.load_document() == before


@pytest.mark.parametrize("invalid", [
    {"remove_page_ids": [{}]}, {"upsert_pages": {}},
    {"unchanged_reason": 5}, {"impact_summary": []}, {"unknown": "ignored"},
])
def test_content_update_bad_shapes_are_controlled_errors(tmp_path: Path, invalid: dict) -> None:
    project, store, _ = _setup_project_with_pages(tmp_path)
    updated = _inputs_update(
        project, patch={"task_patch": {"audience": "董事会"}, "reason": "调整受众"},
        base_revision=store.load_document()["revision_id"], operation_id="bad-result-shape")
    task = updated["pending_tasks"][0]
    claim_fixture_task(project, task, execution_ref='L1-invalid-input-protocol')
    before = store.load_document()
    raw = tasks_mod._lookup_task(before, task['task_id'], store)
    authored = {'kind': 'compose', 'content_update': {'input_digest': updated['input_digest'],
        'upsert_pages': [], 'remove_page_ids': [], 'page_order': [e['page_id'] for e in before['pages']],
        'unchanged_reason': 'Explicit L1 no-copy impact'},
        'content_plan': store.read_object_json(before['content_plan'])['input']}
    payload = v2_revision_envelope(store, raw, authored)
    if 'remove_page_ids' in invalid:
        payload['payload']['diff']['removed_page_ids'] = invalid['remove_page_ids']
    elif 'upsert_pages' in invalid:
        payload['payload']['proposals'] = invalid['upsert_pages']
    elif 'unknown' in invalid:
        payload['unknown'] = invalid['unknown']
    else:
        payload['payload']['diff']['summary'] = next(iter(invalid.values()))
    with pytest.raises((EnvelopeError, ModelError)):
        service.accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
            produced_against=task['produced_against'], result_payload=payload)
    assert store.load_document() == before


def test_content_update_roundtrip_changes_only_target_page(tmp_path: Path) -> None:
    """AC-11: adopting the V1→V2 interface revision touches only p03."""
    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    # Real blueprints so the changed page keeps its original as history.
    for entry in store.load_document()["pages"]:
        task = service.open_blueprint_task(store, store.load_document(), entry)
        _accept_blueprint_envelope(project, task, entry, _png_bytes())
    # Populate every slot with explicit synthetic test artifacts, so retaining
    # None slots cannot masquerade as preserving existing SVG/preview bytes.
    from deck_master.pipeline import artifact
    svg = tmp_path / 'synthetic.svg'
    svg.write_text('<svg viewBox="0 0 320 180"><rect width="320" height="180" fill="#161b22"/></svg>')
    preview = tmp_path / 'synthetic-preview.png'
    preview.write_bytes(_png_bytes())
    def attach_test_slots(doc):
        for entry in doc['pages']:
            entry['svg'] = artifact(store, svg, 'svg', page_id=entry['page_id'])
            entry['svg_preview'] = artifact(store, preview, 'svg_preview', page_id=entry['page_id'])
            entry['ppt_preview'] = artifact(store, preview, 'ppt_preview', page_id=entry['page_id'])
    _raw_commit(store, attach_test_slots)
    document = store.load_document()
    before = {e["page_id"]: e for e in document["pages"]}
    expected = _load_fixture('expected-effects.json')
    assert {pid: _original_copy_hash(store.read_object_json(entry['page'])) for pid, entry in before.items()} == expected['before_page_hashes']

    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    update = _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="input-update-rt", patch_dir=FIXTURES)
    document = store.load_document()
    task = next(t for t in (store.read_object_json(r) for r in document["tasks"])
                if t.get("intent") == "input_revision")
    payload = _load_fixture("result-input-revision.json")
    payload["content_update"]["input_digest"] = update["input_digest"]
    outcome = _accept_result(
        project, task_id=task["task_id"], operation_id=task["operation_id"],
        produced_against=task["produced_against"], result_payload=payload)
    assert outcome["status"] == "accepted"

    after_doc = store.load_document()
    after = {e["page_id"]: e for e in after_doc["pages"]}
    assert [e["page_id"] for e in after_doc["pages"]] == ["p01", "p02", "p03"]
    for pid in ("p01", "p02"):
        assert after[pid] == before[pid], f"unchanged page {pid} must keep every slot"
        for slot in ('blueprint', 'svg', 'svg_preview', 'ppt_preview'):
            old_file = store.read_object_json(before[pid][slot])['file']
            new_file = store.read_object_json(after[pid][slot])['file']
            assert store.read_object_bytes(old_file) == store.read_object_bytes(new_file)
    assert {pid: _original_copy_hash(store.read_object_json(entry['page'])) for pid, entry in after.items()} == expected['after_page_hashes']
    assert after["p03"]["page"]["sha256"] == outcome["new_page_hashes"]["p03"]
    assert after["p03"]["blueprint"] == before["p03"]["blueprint"], "original blueprint is kept"
    assert after_doc["outputs"] == dict.fromkeys(document["outputs"]), "changed content retires deck outputs"
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
    update = _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                                   operation_id="input-update-rj", patch_dir=FIXTURES)
    document = store.load_document()
    task = next(t for t in (store.read_object_json(r) for r in document["tasks"])
                if t.get("intent") == "input_revision")
    base_payload = _load_fixture("result-input-revision.json")
    base_payload["content_update"]["input_digest"] = update["input_digest"]

    def submit(payload):
        return _accept_result(
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
    no_reason["content_update"]["impact_summary"] = ""
    with pytest.raises(EnvelopeError):
        submit(no_reason)

    with_artifact = json.loads(json.dumps(base_payload, ensure_ascii=False))
    with_artifact["artifact_specs"] = [{"file_id": "x", "role": "svg", "page_id": "p03"}]
    with pytest.raises(EnvelopeError):
        submit(with_artifact)

    # A real initial framing Task cannot accept reconciliation instead.
    other = project.parent / 'initial-protocol'
    initial = service.create(other, brief='L1 initial request')['pending_tasks'][0]
    claim_fixture_task(other, initial)
    wrong = _framing_envelope(Store(other), initial)
    wrong['variant'] = 'input_revision'
    wrong['payload'] = {'changed_layers': ['plan'], 'proposals': [], 'diff': {'summary': 'Wrong phase'}}
    with pytest.raises((EnvelopeError, ModelError, TaskConflict)):
        service.accept_result(other, task_id=initial['task_id'], operation_id=initial['operation_id'],
            produced_against=initial['produced_against'], result_payload=wrong)


def test_needs_reconciliation_gates_delivery_and_handoff(tmp_path: Path) -> None:
    from deck_master.editing import export_project
    from deck_master.errors import InputReconciliationPending
    from deck_master.handoff import check_handoff

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="input-update-gate", patch_dir=FIXTURES)

    # Keep a valid PPTX so review export also exercises privacy sanitation.
    document = store.load_document()
    from pptx import Presentation
    from deck_master.pipeline import artifact
    ppt_file=tmp_path/'valid.pptx'
    presentation = Presentation()
    for _ in document['pages']:
        presentation.slides.add_slide(presentation.slide_layouts[6])
    presentation.save(ppt_file)
    from deck_master.compiler.native import attach_notes
    ppt_file.write_bytes(attach_notes(ppt_file.read_bytes(), [{'page_id': entry['page_id'],
        'notes': store.read_object_json(entry['page']).get('speaker_notes', '')} for entry in document['pages']]))
    pptx_ref=artifact(store,ppt_file,'pptx')
    from deck_master.models import bump_revision as _bump
    bumped = _bump(document, {"operation_id": "probe-output", "kind": "task_update",
                              "description": "probe output", "read_set": []})
    bumped["outputs"]["pptx"] = pptx_ref
    store._commit_locked(base_revision=document["revision_id"], document=bumped, blobs=[])

    with pytest.raises((InputReconciliationPending, EligibilityBlocked)):
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
    _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="input-update-view", patch_dir=FIXTURES)
    view = project_view(project)
    assert view["input_alignment"] == "needs_reconciliation"
    assert view["reconciliation"]["notice"] == "待按新要求更新"
    assert view["reconciliation"]["reason"] == patch["reason"]
    # A later display-name-only commit must not hide the outstanding reason.
    _inputs_update(project, patch={"reason": "只改显示名", "source_changes": {"metadata": [
        {"source_id": id_by_name["company.md"], "name": "公司简介.md"}]}},
        base_revision=store.load_document()["revision_id"], operation_id="rename-after-input-update")
    assert project_view(project)["reconciliation"]["reason"] == patch["reason"]
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


def _force_fake_output(store):
    """Attach an actual synthetic PPTX; no engineering/professional approval."""
    from pptx import Presentation
    from deck_master.pipeline import artifact
    document = store.load_document()
    ppt = Presentation()
    for entry in document['pages']:
        slide = ppt.slides.add_slide(ppt.slide_layouts[6])
        slide.shapes.add_textbox(0, 0, 100, 100).text = entry['page_id']
    path = store.staging_dir / 'L1-flow-review.pptx'
    path.parent.mkdir(parents=True, exist_ok=True)
    ppt.save(path)
    from deck_master.compiler.native import attach_notes
    path.write_bytes(attach_notes(path.read_bytes(), [{'page_id': entry['page_id'],
        'notes': store.read_object_json(entry['page']).get('speaker_notes', '')} for entry in document['pages']]))
    ref = artifact(store, path, 'pptx')
    bumped = bump_revision(document, {'operation_id': 'probe-output', 'kind': 'task_update',
        'description': 'Actual L1 synthetic PPTX, no production approval', 'read_set': []})
    bumped['outputs']['pptx'] = ref
    store._commit_locked(base_revision=document['revision_id'], document=bumped, blobs=[])


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
    _inputs_update(project, patch=patch, base_revision=store.load_document()["revision_id"],
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
    update = _inputs_update(
        project, patch={"task_patch": {"audience": "新评审团队"}, "reason": "更换受众"},
        base_revision=before["revision_id"], operation_id="update-after-review")
    task = update["pending_tasks"][0]
    _accept_result(project, task_id=task["task_id"], operation_id=task["operation_id"],
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
    assert entries == ["RESOLVER.md", "deck-content", "deck-design", "deck-master", "deck-review"]
    resolver = (skills / "RESOLVER.md").read_text(encoding="utf-8").strip()
    assert all(name in resolver for name in ("deck-master", "deck-content", "deck-design", "deck-review"))
    assert all(name in resolver for name in ("deck-master", "deck-content", "deck-design", "deck-review"))


def test_old_skill_names_gone_from_living_surfaces(monkeypatch) -> None:
    import re

    monkeypatch.setenv("PATH", "")  # This check needs no system search executable.

    repo = Path(service.__file__).resolve().parents[2]
    pattern = ("deck-autopilot|deck-brief|deck-builder|deck-doctor|deck-init|deck-learn|"
               "deck-planner|deck-producer|deck-quality|deck-setup|"
               "deck-sourcing|deck-upgrade|ppt-deck-pro-max|ppt-quality-gate|ppt-master")
    excluded = {'__pycache__', '.pytest_cache', '.venv', 'venv', 'node_modules',
                'build', 'dist', 'skills-references'}
    generated_skill = repo / 'src/deck_master/resources/skill'
    files = []
    for name in ('src', 'tools', 'tests', 'pyproject.toml', 'AGENTS.md', 'skills'):
        root = repo / name
        for path in sorted(root.rglob('*')) if root.is_dir() else [root]:
            if (not path.is_file() or path.is_symlink() or path.resolve() == Path(__file__).resolve()
                    or generated_skill in path.parents
                    or any(part in excluded or part.endswith('.egg-info') or part.startswith('_ap_')
                           for part in path.relative_to(repo).parts)):
                continue
            data = path.read_bytes()
            if b'\x00' in data:
                continue
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                continue
            files.extend(f'{path.relative_to(repo)}:{index}' for index, line in enumerate(text.splitlines(), 1)
                         if re.search(pattern, line))
    assert files == [], f"living references to removed skills: {files}"



def test_delivery_gate_surfaces_exit_3_code_via_cli(tmp_path: Path, capsys) -> None:
    from deck_master.editing import export_project

    project, store, id_by_name = _setup_project_with_pages(tmp_path)
    document = store.load_document()
    patch = _load_fixture("update-interface.json")
    patch["source_changes"]["replace"][0]["source_id"] = id_by_name["interface-v1.md"]
    _inputs_update(project, patch=patch, base_revision=document["revision_id"],
                          operation_id="input-update-cli", patch_dir=FIXTURES)
    _force_fake_output(store)
    code = cli.main(["export", "--project", str(project), "--out", str(tmp_path / "gate-out"),
                     "--purpose", "delivery"])
    assert code == 3
    payload = json.loads(capsys.readouterr().err)
    assert payload['error']['code'] in ('input_reconciliation_pending', 'eligibility_blocked')
    assert 'input_reconciliation_pending' in json.dumps(payload)
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


@pytest.mark.parametrize('mode', ['reorder', 'remove', 'add', 'edit', 'noop'])
def test_revision_invalidates_changed_deck_outputs(tmp_path, mode):
    import copy
    project, store, _ = _setup_project_with_pages(tmp_path)
    _force_fake_output(store)
    if mode == 'add':
        _include_new_page_scope(project, ['p01', 'p02', 'p03', 'p04'])
    before = store.load_document()
    update = _inputs_update(project, patch={'reason': 'review regression', 'task_patch': {'audience': 'new audience'}},
                                   base_revision=before['revision_id'], operation_id='rev-output')
    assert store.load_document()['outputs'] == before['outputs']
    order = [entry['page_id'] for entry in before['pages']]
    upserts, removes = [], []
    if mode == 'reorder':
        order.reverse()
    elif mode == 'remove':
        removes = [order.pop()]
    elif mode in ('add', 'edit'):
        page = copy.deepcopy(store.read_object_json(before['pages'][0]['page']))
        if mode == 'add':
            from test_content_ops import derived_page
            page = derived_page(page, 'p04')
            order.append('p04')
        page['customer_visible']['title'] = 'Changed title'
        upserts = [page]
    task = update['pending_tasks'][0]
    _accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                          produced_against=task['produced_against'], result_payload={'kind': 'compose', 'content_update': {
                              'input_digest': update['input_digest'], 'upsert_pages': upserts,
                              'remove_page_ids': removes, 'page_order': order, 'unchanged_reason': 'Only ordering or no content change'}})
    after = store.load_document()
    assert after['outputs'] == (before['outputs'] if mode == 'noop' else dict.fromkeys(before['outputs']))
    assert store.load_document(before['revision_id'])['outputs'] == before['outputs']


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('changed_input', [False, True])
def test_restore_keeps_historical_content_basis(tmp_path, legacy, changed_input):
    from deck_master.editing import restore
    project, store, _ = _setup_project_with_pages(tmp_path)
    if legacy:
        _raw_commit(store, lambda doc: doc.pop('content_basis', None))
    past = store.load_document()
    if changed_input:
        update = _inputs_update(project, patch={'reason': 'reading mode', 'task_patch': {'presentation_mode': 'read_alone'}},
                                       base_revision=past['revision_id'], operation_id='restore-input')
        task = update['pending_tasks'][0]
        page = store.read_object_json(past['pages'][0]['page'])
        page['customer_visible']['title'] = 'New reading copy'
        _accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                              produced_against=task['produced_against'], result_payload={'kind': 'compose', 'content_update': {
                                  'input_digest': update['input_digest'], 'upsert_pages': [page],
                                  'remove_page_ids': [], 'page_order': [e['page_id'] for e in past['pages']]}})
    current = store.load_document()
    restore(project, revision_id=past['revision_id'], base_revision=current['revision_id'], operation_id='restore-probe')
    after = store.load_document()
    assert after['pages'] == past['pages']
    assert after['task'] == current['task'] and after['policy'] == current['policy']
    assert after['content_basis']['input_digest'] == compute_input_digest(past)
    assert service.inputs_show(project)['input_alignment'] == ('needs_reconciliation' if changed_input else 'current')


def test_cancelled_revision_recovers_once_and_refuses_late_result(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    project, store, _ = _setup_project_with_pages(tmp_path)
    patch = {'reason': 'new audience', 'task_patch': {'audience': 'new audience'}}
    update = _inputs_update(project, patch=patch, base_revision=store.load_document()['revision_id'], operation_id='cancel-input')
    old = update['pending_tasks'][0]
    service.task_cancel(project, task_id=old['task_id'])
    assert _inputs_update(project, patch=patch, base_revision=store.load_document()['revision_id'], operation_id='same-patch')['status'] == 'unchanged'
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: service.continue_project(project), range(2)))
    pending = [r['pending_tasks'][0] for r in responses]
    assert all(t['kind'] == 'compose' and t['intent'] == 'input_revision' for t in pending)
    assert len({t['task_id'] for t in pending}) == 1
    assert pending[0]['task_id'] != old['task_id']
    new = service.continue_project(project)['pending_tasks'][0]
    assert new['task_id'] == pending[0]['task_id']
    assert service.task_status(project, task_id=old['task_id'])['status'] == 'cancelled'
    with pytest.raises(TaskConflict):
        _accept_result(project, task_id=old['task_id'], operation_id=old['operation_id'], produced_against=old['produced_against'],
                              result_payload={'kind': 'compose', 'content_update': {'input_digest': update['input_digest'],
                                  'upsert_pages': [], 'remove_page_ids': [], 'page_order': ['p01', 'p02', 'p03'], 'unchanged_reason': 'no change'}})


def test_restore_empty_removes_basis_and_preserves_stop_policy(tmp_path):
    from deck_master.editing import restore
    project = tmp_path / 'empty'
    service.create(project, brief='empty baseline')
    store = Store(project)
    empty = store.load_document()
    _include_new_page_scope(project, ['p01', 'p02', 'p03'])
    service.import_draft(project, draft_payload=_load_fixture('initial-pages.json'),
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()))
    _raw_commit(store, lambda doc: doc.update(content_basis={'input_digest': compute_input_digest(doc)},
                                             policy={**doc['policy'], 'user_stop': True}))
    current = store.load_document()
    restore(project, revision_id=empty['revision_id'], base_revision=current['revision_id'], operation_id='empty-restore')
    after = store.load_document()
    assert not after['pages'] and 'content_basis' not in after
    assert after['policy']['user_stop'] is True
    assert service.inputs_show(project)['input_alignment'] == 'no_content'


def test_restore_reconciliation_dispatch_uses_restore_operation(tmp_path):
    from deck_master.editing import restore
    project, store, _ = _setup_project_with_pages(tmp_path)
    old = store.load_document()
    _inputs_update(project, patch={'reason': 'new audience', 'task_patch': {'audience': 'other'}},
                          base_revision=old['revision_id'], operation_id='changed-audience')
    restore(project, revision_id=old['revision_id'], base_revision=store.load_document()['revision_id'], operation_id='restore-old')
    response = service.continue_project(project)
    task = response['pending_tasks'][0]
    assert task['intent'] == 'input_revision'
    stored = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                  if store.read_object_json(ref)['task_id'] == task['task_id'])
    assert stored['input_revision_id'] == 'restore-old'
    assert stored['scope_pages'] == ['p01', 'p02', 'p03']
    assert stored['input_digest'] == compute_input_digest(store.load_document())
    assert store.load_document(stored['dispatch_revision'])['revision_id'] == stored['dispatch_revision']


@pytest.mark.render
@pytest.mark.parametrize('mode', ['reorder', 'remove', 'add', 'edit'])
def test_revised_deck_recompiles_real_slide_order(tmp_path, resolvable_font_family, mode):
    import io
    import zipfile
    import xml.etree.ElementTree as ET
    from PIL import Image
    from page_visual_helpers import pass_page_review
    from deck_master.pipeline import artifact, produce
    from deck_master.editing import export_project
    from deck_master.handoff import check_handoff
    from deck_master.store import StoreError

    def page(pid):
        return {'schema_version': 'deck_page_package.v2', 'page_id': pid,
                'customer_visible': {'title': pid, 'body_blocks': []},
                'visual_spec': {'intent': 'synthetic regression', 'reference_mode': 'new_design'}}

    project = tmp_path / 'real-deck'
    service.create(project, brief='Synthetic render regression', draft={'pages': [page('p01'), page('p02'), page('p03')]})
    if mode == 'add':
        _include_new_page_scope(project, ['p01', 'p02', 'p03', 'p04'])
    prepare_editorial_project(project)
    store = Store(project)
    png = tmp_path / 'reference.png'
    Image.new('RGB', (960, 540), 'white').save(png)

    def attach_missing_svgs(doc):
        for entry in doc['pages']:
            if entry.get('svg'):
                continue
            content = store.read_object_json(entry['page'])
            svg = tmp_path / (entry['page_id'] + '.svg')
            svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">'
                           f'<rect width="960" height="540" fill="#ffffff"/>'
                           f'<text x="40" y="100" font-family="{resolvable_font_family}" font-size="32">'
                           f'{content["customer_visible"]["title"]}</text></svg>')
            if not entry.get('blueprint'):
                entry['blueprint'] = artifact(store, png, 'blueprint', page_id=entry['page_id'])
            entry['svg'] = artifact(store, svg, 'svg', page_id=entry['page_id'])

    _raw_commit(store, attach_missing_svgs)
    from test_tasks import qualify_render_fixture
    qualify_render_fixture(project)
    assert produce(project)['status'] == 'pass'
    before = store.load_document()
    old_file = tmp_path / 'old.pptx'
    old_file.write_bytes(store.read_object_bytes(store.read_object_json(before['outputs']['pptx'])['file']))
    def assert_old_file_refused():
        report = check_handoff(project, file_path=old_file, purpose='review')
        assert report['status'] == 'blocked'
        assert 'candidate_not_current_output' in report['gaps']
        assert report['file_sha256'] == hashlib.sha256(old_file.read_bytes()).hexdigest()
        with pytest.raises(StoreError):
            check_handoff(project, file_path=old_file, purpose='delivery')

    update = _inputs_update(project, patch={'reason': 'revised deck', 'task_patch': {'audience': 'new audience'}},
                                   base_revision=before['revision_id'], operation_id='render-update')
    order, remove, upserts = ['p01', 'p02', 'p03'], [], []
    if mode == 'reorder':
        order.reverse()
    elif mode == 'remove':
        remove = [order.pop()]
    elif mode == 'add':
        order.append('p04')
        upserts = [page('p04')]
    else:
        changed = page('p01')
        changed['customer_visible']['title'] = 'Updated'
        upserts = [changed]
    task = update['pending_tasks'][0]
    _accept_result(project, task_id=task['task_id'], operation_id=task['operation_id'],
                          produced_against=task['produced_against'], result_payload={'kind': 'compose', 'content_update': {
                              'input_digest': update['input_digest'], 'upsert_pages': upserts, 'remove_page_ids': remove,
                              'page_order': order, 'unchanged_reason': 'Only ordering'}})
    assert store.load_document()['outputs']['pptx'] is None
    with pytest.raises(StoreError):
        export_project(project, output_dir=tmp_path / 'delivery', purpose='delivery')
    assert_old_file_refused()
    prepare_editorial_project(project)
    _raw_commit(store, attach_missing_svgs)
    qualify_render_fixture(project)
    for _ in range(6):
        response = service.continue_project(project)
        task = response['pending_tasks'][0]
        if task.get('review_stage') != 'page_visual':
            break
        pass_page_review(project, task)
    assert task['kind'] == 'review' and task.get('review_stage') == 'final'
    current = store.load_document()
    assert current['outputs']['pptx'] != before['outputs']['pptx']
    data = store.read_object_bytes(store.read_object_json(current['outputs']['pptx'])['file'])
    with zipfile.ZipFile(io.BytesIO(data)) as deck:
        slides = sorted(name for name in deck.namelist() if name.startswith('ppt/slides/slide') and name.endswith('.xml'))
        texts = [''.join(ET.fromstring(deck.read(name)).itertext()) for name in slides]
    assert texts == [('Updated' if mode == 'edit' and pid == 'p01' else pid) for pid in order]
    assert_old_file_refused()


def test_resume_keeps_retired_task_history_and_original_change_reason(tmp_path):
    from deck_master.view import project_view
    project, store, ids = _setup_project_with_pages(tmp_path)
    repair = service.open_host_task(store, kind='repair', page_ids=['p01'], instruction='obsolete page repair')
    update = _inputs_update(project, patch={'reason': 'Original requirement', 'task_patch': {'audience': 'new team'}},
                                   base_revision=store.load_document()['revision_id'], operation_id='original-input')
    old = update['pending_tasks'][0]
    service.task_cancel(project, task_id=old['task_id'])
    _inputs_update(project, patch={'reason': 'Only display name', 'source_changes': {'metadata': [
        {'source_id': ids['company.md'], 'name': 'Renamed.md'}]}},
        base_revision=store.load_document()['revision_id'], operation_id='rename')
    resumed = service.continue_project(project)['pending_tasks'][0]
    pending = service.continue_project(project)['pending_tasks']
    assert [t['task_id'] for t in pending] == [resumed['task_id']]
    assert service.task_status(project, task_id=repair['task_id'])['status'] == 'superseded'
    assert project_view(project)['reconciliation']['reason'] == 'Original requirement'
    stored = next(store.read_object_json(ref) for ref in store.load_document()['tasks']
                  if store.read_object_json(ref)['task_id'] == resumed['task_id'])
    assert stored['input_revision_id'] == 'original-input'
    result = _accept_result(project, task_id=resumed['task_id'], operation_id=resumed['operation_id'],
                                   produced_against=resumed['produced_against'], result_payload={'kind': 'compose', 'content_update': {
                                       'input_digest': stored['input_digest'], 'upsert_pages': [], 'remove_page_ids': [],
                                       'page_order': ['p01', 'p02', 'p03'], 'unchanged_reason': 'Checked current copy'}})
    assert result['status'] == 'accepted'
    assert service.inputs_show(project)['input_alignment'] == 'current'
