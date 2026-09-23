"""T17 entry-matrix evidence (AC-I04): new commands, 09.6 legacy mapping
classes (alias / guidance / retired / old-format rejection), and the plain
material-directory create path (AC-C06 handoff input)."""
import json
import sys
from pathlib import Path

import pytest

import deck_master.cli as cli
import deck_master.service as service


def _material(tmp_path: Path) -> Path:
    material = tmp_path / "material.txt"
    material.write_text("入口矩阵材料\n(尾部约束)合成数据不可回写。", encoding="utf-8")
    return material


def _create(tmp_path, capsys):
    project = tmp_path / "proj"
    code = cli.main(["create", "--brief", "入口矩阵", "--source", str(_material(tmp_path)),
                     "--out", str(project)])
    return code, project, json.loads(capsys.readouterr().out)


# ---------------------------------------------------------------------------
# New commands keep working through the same entry (T17.02 core loop).


def test_create_continue_view_export_loop(tmp_path, capsys):
    code, project, payload = _create(tmp_path, capsys)
    assert code == 0 and payload["status"] == "created"
    assert payload["pending_tasks"], "create hands the Host a pending task"
    assert (project / ".deckmaster" / "current.json").is_file()
    # continue reports awaiting_host with exit 3 (09.3), not a failure.
    capsys.readouterr()
    assert cli.main(["continue", "--project", str(project)]) == 3
    continued = json.loads(capsys.readouterr().out)
    assert continued["next_action"] == "submit_host_results"
    # view (no open) reports service status without starting anything.
    assert cli.main(["view", "--project", str(project)]) == 0
    viewed = json.loads(capsys.readouterr().out)
    assert viewed["view_status"] in ("not_running", "running", "stale")


def test_plain_material_directory_enters_new_flow_without_config(tmp_path, capsys):
    """AC-C06 handoff: a plain material directory, no library/cache/template,
    goes straight from create into the Host task queue."""
    project = tmp_path / "plain-proj"
    assert cli.main(["create", "--brief", "普通材料目录", "--source", str(_material(tmp_path)),
                     "--out", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert not (tmp_path / "library").exists()
    assert not (tmp_path / "workspace").exists()
    assert not (project / "preview_manifest.json").exists()
    task = payload["pending_tasks"][0]
    assert task["kind"] == "compose" and task["status"] == "awaiting_host"
    assert task["sources"], "the work order derives from the real source entries"


# ---------------------------------------------------------------------------
# 09.6 alias class: old entry executes the new semantics.


def test_agent_doctor_alias_runs_step_diagnostics(tmp_path, capsys):
    code = cli.main(["agent-doctor", "--mode", "preview"])
    payload = json.loads(capsys.readouterr().out)
    assert code in (0, 3)
    assert payload["status"] in ("ready", "needs_tool", "awaiting_host")


def test_next_step_alias_returns_project_view(tmp_path, capsys):
    _, project, _ = _create(tmp_path, capsys)
    capsys.readouterr()
    assert cli.main(["next-step", "--project", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "deck_view.v1"
    assert payload["next_action"] == "submit_host_results"


def test_run_state_alias_matches_next_step(tmp_path, capsys):
    _, project, _ = _create(tmp_path, capsys)
    capsys.readouterr()
    assert cli.main(["run-state", "--project", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "deck_view.v1"


def test_final_readiness_alias_reports_real_check_state(tmp_path, capsys):
    _, project, _ = _create(tmp_path, capsys)
    capsys.readouterr()
    assert cli.main(["final-readiness", "--project", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked", "no current PPT, no passing checks"
    assert payload["review_status"] == "not_evaluated"


def test_import_plan_alias_accepts_v2_draft_and_rejects_v1(tmp_path, capsys):
    project = tmp_path / "proj-import"
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"pages": [{
        "schema_version": "deck_page_package.v2", "page_id": "d1",
        "customer_visible": {"title": "导入页", "body_blocks": []},
        "visual_spec": {"intent": "import", "reference_mode": "new_design"}}]}, ensure_ascii=False))
    assert cli.main(["import-plan", "--input", str(draft), "--project", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "accepted"
    legacy_plan = tmp_path / "legacy-plan.json"
    legacy_plan.write_text(json.dumps({"narrative_plan": {"beats": []}, "sourcing_plan": {}}))
    assert cli.main(["import-plan", "--input", str(legacy_plan), "--project", str(project)]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "legacy_plan_format"
    assert "narrative_plan" in payload["error"]["message"]


def test_build_legacy_subcommands_map_or_reject(tmp_path, capsys):
    _, project, _ = _create(tmp_path, capsys)
    capsys.readouterr()
    assert cli.main(["build", "status", "--project", str(project)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["page_count"] == 0 and payload["status"] == "awaiting_content"
    assert cli.main(["build", "retry", "--project", str(project)]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "retired_command"


# ---------------------------------------------------------------------------
# 09.6 guidance class: clear pointer, non-zero exit, no implicit rule draft.


@pytest.mark.parametrize("command", ["start-conversation", "autoplan", "search-library"])
def test_guidance_commands_point_to_create(command, capsys):
    assert cli.main([command]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "legacy_guidance"
    assert "create" in payload["error"]["message"]


def test_library_guidance_names_the_boundary(capsys):
    assert cli.main(["library-status"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert "新核心不实现整页库流程" in payload["error"]["message"]


# ---------------------------------------------------------------------------
# 09.6 retired class: controlled refusal, never a new-task prerequisite.


@pytest.mark.parametrize("command", ["rc-gate", "preview-gate", "backend", "render"])
def test_retired_commands_refuse_explicitly(command, capsys):
    assert cli.main([command]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "retired_command"


def test_legacy_map_lists_every_real_old_command(capsys):
    assert cli.main(["legacy-map"]) == 0
    table = json.loads(capsys.readouterr().out)
    for key in ("alias", "guidance", "retired", "legacy_build_subcommands"):
        assert table[key], key
    assert "agent-doctor" in table["alias"]
    assert "search-library" in table["guidance"]
    assert "rc-gate" in table["retired"]
    assert "build retry" in table["retired"]


# ---------------------------------------------------------------------------
# Old-format run paths are recognised and refused (no in-place migration).


def _legacy_run(tmp_path: Path) -> Path:
    run = tmp_path / "old-run"
    run.mkdir()
    (run / "preview_manifest.json").write_text(json.dumps({"pages": []}))
    (run / "run.json").write_text(json.dumps({"stage": "completed"}))
    return run


@pytest.mark.parametrize("argv_tail", [
    ["next-step"], ["final-readiness"], ["build", "status"], ["view"],
])
def test_legacy_run_dir_refused_not_migrated(argv_tail, tmp_path, capsys):
    run = _legacy_run(tmp_path)
    argv = [argv_tail[0]]
    if argv_tail[0] == "build":
        argv += ["status"]
    argv += ["--run-dir", str(run)] if argv_tail[0] in ("next-step", "final-readiness", "build") else ["--project", str(run)]
    if argv_tail[0] == "view":
        argv = ["view", "--project", str(run)]
    assert cli.main(argv) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "legacy_run_format"
    assert "migration-to-rebuilt-core" in payload["error"]["message"]
    # Nothing was initialised or migrated in place.
    assert not (run / ".deckmaster").exists()


def test_create_refuses_legacy_run_target(tmp_path, capsys):
    run = _legacy_run(tmp_path)
    assert cli.main(["create", "--brief", "x", "--out", str(run)]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "legacy_run_format"
    assert not (run / ".deckmaster").exists()


def test_task_commands_reject_legacy_project(tmp_path, capsys):
    run = _legacy_run(tmp_path)
    assert cli.main(["task", "start", "--project", str(run), "--task-id", "t",
                     "--execution-ref", "e"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "legacy_run_format"


# ---------------------------------------------------------------------------
# One entry everywhere: module, __main__ and console entry share cli.main.


def test_python_dash_m_uses_same_entry(tmp_path, capsys):
    project = tmp_path / "m-proj"
    code = cli.main(["create", "--brief", "m", "--source", str(_material(tmp_path)),
                     "--out", str(project)])
    assert code == 0
    capsys.readouterr()
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "deck_master", "view", "--project", str(project), "--json"],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["view_status"] in ("not_running", "running", "stale")
