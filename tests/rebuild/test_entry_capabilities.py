"""B02 entry selection and project-effective capabilities; synthetic only.

Covers the `view --open` entry selection — the default opens the v2
workbench, `--ui legacy` opens the rollback review entry (JSON, exit codes,
service
reuse with `workbench`), the /api/project effective_actions projection
(modern, v1-format, readonly sample, missing capability, future-writer and
unknown-format pointers), and that reading the projection never upgrades or
migrates a project in place.
"""
import json
import urllib.request
from pathlib import Path

import pytest

from deck_master import changes, cli, service, ui_journal, workbench
from deck_master.samples import create_sample
from deck_master.store import SUPPORTED_WRITERS, Store
from deck_master.web import UI_CAPABILITIES, WorkbenchServer, stop_service
from test_workbench_services import auth, http

SKILL = Path(__file__).resolve().parents[2] / "skills" / "deck-master" / "SKILL.md"

V1_PAGE = {"schema_version": "deck_page_package.v2", "page_id": "one",
           "customer_visible": {"title": "Old title", "body_blocks": []},
           "visual_spec": {"intent": "Synthetic audit", "reference_mode": "new_design"}}


@pytest.fixture
def modern(tmp_path):
    path = tmp_path / "modern"
    create_sample(path, page_count=2, readonly=False)
    return path


@pytest.fixture
def readonly_sample(tmp_path):
    path = tmp_path / "readonly"
    create_sample(path, page_count=2, readonly=True)
    return path


@pytest.fixture
def v1_project(tmp_path):
    path = tmp_path / "v1-project"
    service.create(path, brief="Synthetic v1 format audit", draft={"pages": [V1_PAGE]})
    return path


def actions_by_name(info):
    return {item["action"]: item for item in info["effective_actions"]}


def get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read())


def test_effective_actions_modern_project(modern):
    info = ui_journal.project_info(modern, server_capabilities=UI_CAPABILITIES)
    assert info["project_format"] == "workbench.v3"
    assert info["minimum_writer"] == "content-plan.v1"
    assert info["core_writers"] == list(SUPPORTED_WRITERS)
    actions = actions_by_name(info)
    assert set(actions) == {"drafts", "annotations", "changes", "candidates", "content", "inputs",
                            "styles", "run_desk", "exports", "restoration"}
    assert all(item["supported"] and item["writable"] and item["reason_code"] is None
               for item in actions.values())


def test_v1_format_disables_only_real_gates_and_stays_truthful(v1_project):
    info = ui_journal.project_info(v1_project, server_capabilities=UI_CAPABILITIES)
    assert info["project_format"] == "deck_document.v1"
    actions = actions_by_name(info)
    # drafts (journal) and the ungated families stay writable: their write
    # paths really accept v1 projects today, and the projection must not
    # over-disable with a false reason. run_desk keeps a known granularity
    # limit: the family mixes v1-capable /api/feedback with v3-only assemble.
    for name in ("drafts", "inputs", "run_desk", "exports", "restoration"):
        assert actions[name]["writable"] is True and actions[name]["reason_code"] is None
    # these mirror a real workbench.v3 gate at the service layer (B07/G54
    # moved candidates into the gated set together with its endpoint gate)
    for name in ("annotations", "changes", "content", "styles", "candidates"):
        assert actions[name]["writable"] is False
        assert actions[name]["reason_code"] == "unsupported_project_format"
    # reading the projection must not upgrade or migrate the project in place
    pointer = json.loads((v1_project / ".deckmaster" / "current.json").read_text("utf-8"))
    assert pointer["format"] == "deckmaster-current.v1"
    assert Store(v1_project).load_document().get("compatibility") is None


def test_v1_drafts_save_works_over_http_and_does_not_migrate(v1_project):
    # the projection's one positive claim on v1 projects is backed by the real
    # write path: a personal draft saves over HTTP without touching the
    # pointer or the document's compatibility
    server = WorkbenchServer(v1_project)
    try:
        url = server.start()
        doc = Store(v1_project).load_document()
        value = {"schema_version": "ui_draft.v1", "project_id": doc["project_id"],
                 "project_identity": ui_journal.project_info(v1_project)["project_identity"],
                 "draft_id": "d-v1", "target": {"scope": "project", "page_id": None, "layer": "notes"},
                 "base_revision": doc["revision_id"], "base_ref": None,
                 "content": {"text": "v1 项目上的个人草稿"}, "pending": None}
        status, saved = http(url, "/api/drafts/save", {"draft": value}, headers=auth(url))
        assert status == 200 and saved["status"] == "saved"
        pointer = (v1_project / ".deckmaster" / "current.json").read_text("utf-8")
        assert json.loads(pointer)["format"] == "deckmaster-current.v1"
        assert Store(v1_project).load_document().get("compatibility") is None
    finally:
        server.stop()


def test_v1_write_gate_is_unchanged(v1_project):
    # the endpoint gate keeps refusing independently of the projection
    doc = Store(v1_project).load_document()
    intent = {"schema_version": "change_intent.v1", "project_id": doc["project_id"],
              "base_revision": doc["revision_id"], "intent": "repair", "instruction": "spacing",
              "annotation_refs": [], "max_calls": 0,
              "targets": [{"page_id": "one", "page_ref": doc["pages"][0]["page"],
                           "layer": "content", "artifact_ref": doc["pages"][0]["page"]}]}
    with pytest.raises(Exception, match="explicit workbench.v3"):
        changes.plan(v1_project, input=intent)


def test_readonly_sample_disables_every_write(readonly_sample):
    info = ui_journal.project_info(readonly_sample, server_capabilities=UI_CAPABILITIES)
    actions = actions_by_name(info)
    assert all(item["supported"] for item in actions.values())
    assert all(item["writable"] is False and item["reason_code"] == "sample_readonly"
               for item in actions.values())


def test_missing_capability_is_supported_false_without_a_new_reason(modern):
    reduced = [name for name in UI_CAPABILITIES if name != "changes.v1"]
    info = ui_journal.project_info(modern, server_capabilities=reduced)
    actions = actions_by_name(info)
    assert actions["changes"] == {"action": "changes", "supported": False,
                                  "writable": False, "reason_code": None}
    assert actions["drafts"]["writable"] is True


def _rewrite_pointer(project, **patch):
    pointer_path = project / ".deckmaster" / "current.json"
    pointer = json.loads(pointer_path.read_text("utf-8"))
    pointer.update(patch)
    pointer_path.write_text(json.dumps(pointer), "utf-8")


def test_future_writer_pointer_serves_explainable_payload(modern):
    _rewrite_pointer(modern, minimum_writer="future-writer.v9")
    info = ui_journal.project_info(modern, server_capabilities=UI_CAPABILITIES)
    assert info["read_status"]["reason_code"] == "writer_upgrade_required"
    assert info["project_id"] is None and info["revision_id"] is None
    assert all(item["writable"] is False and item["reason_code"] == "writer_upgrade_required"
               for item in info["effective_actions"])
    assert all(item["supported"] for item in info["effective_actions"])


def test_unknown_pointer_format_is_reader_upgrade(modern):
    _rewrite_pointer(modern, format="deckmaster-current.v9")
    info = ui_journal.project_info(modern, server_capabilities=UI_CAPABILITIES)
    assert info["read_status"]["reason_code"] == "reader_upgrade_required"
    assert all(item["writable"] is False and item["reason_code"] == "reader_upgrade_required"
               for item in info["effective_actions"])


def test_http_project_agrees_with_health_and_serves_degraded_payloads(modern):
    # A running service whose project is then upgraded underneath by an
    # independent CLI writer keeps serving an explainable payload instead of
    # failing every read with an unclassified error.
    server = WorkbenchServer(modern)
    try:
        url = server.start().rstrip("/")
        health = get(url + "/api/health")
        assert health["ui_capabilities"] == list(UI_CAPABILITIES)
        assert get(url + "/api/project")["project_format"] == "workbench.v3"
        _rewrite_pointer(modern, minimum_writer="future-writer.v9")
        info = get(url + "/api/project")
        assert info["read_status"]["reason_code"] == "writer_upgrade_required"
        assert all(item["writable"] is False for item in info["effective_actions"])
    finally:
        server.stop()


def test_view_ui_flag_reuses_service_and_matches_workbench(modern, capsys):
    registry = modern.parent / "registry.json"
    try:
        rc = cli.main(["view", "--project", str(modern), "--open", "--no-open", "--json"])
        assert rc == 0
        default_entry = json.loads(capsys.readouterr().out)
        assert default_entry["ui"] is None
        assert default_entry["review_url"].endswith("/v2/")

        rc = cli.main(["view", "--project", str(modern), "--open", "--ui", "legacy", "--no-open", "--json"])
        assert rc == 0
        legacy_entry = json.loads(capsys.readouterr().out)
        assert legacy_entry["ui"] == "legacy" and legacy_entry["review_url"].endswith("/legacy/")
        assert legacy_entry["port"] == default_entry["port"] and legacy_entry["reused"] is True

        rc = cli.main(["view", "--project", str(modern), "--open", "--ui", "v2", "--no-open", "--json"])
        assert rc == 0
        v2_entry = json.loads(capsys.readouterr().out)
        assert v2_entry["ui"] == "v2" and v2_entry["review_url"].endswith("/v2/")
        assert v2_entry["port"] == default_entry["port"] and v2_entry["reused"] is True

        rc = cli.main(["workbench", "--project", str(modern), "--registry", str(registry),
                       "--ui", "v2", "--no-open", "--json"])
        assert rc == 0
        workbench_entry = json.loads(capsys.readouterr().out)
        assert workbench_entry["url"].endswith("/v2/")
        assert workbench_entry["port"] == default_entry["port"] and workbench_entry["reused"] is True

        # the shared service really serves this project's current state
        summary = get(f"http://127.0.0.1:{default_entry['port']}/api/view/summary")
        assert summary["revision_id"] == Store(modern).current_revision_id()
    finally:
        stop_service(modern)


def test_view_ui_requires_open_and_validates_choice(modern, capsys):
    # --ui without --open is a JSON invalid_input with exit code 2
    assert cli.main(["view", "--project", str(modern), "--ui", "v2", "--json"]) == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "invalid_input" and "--ui requires --open" in error["message"]
    # reading options still cannot combine with --open, with or without --ui
    assert cli.main(["view", "--project", str(modern), "--summary", "--open", "--ui", "v2", "--json"]) == 2
    assert "--open" in json.loads(capsys.readouterr().err)["error"]["message"]
    # an unknown choice is argparse's own exit code 2
    with pytest.raises(SystemExit) as exc:
        cli.main(["view", "--project", str(modern), "--open", "--ui", "v3", "--json"])
    assert exc.value.code == 2
    capsys.readouterr()


def test_skill_and_cli_expose_the_entry_contract():
    skill = SKILL.read_text("utf-8")
    assert "view --open --ui v2" in skill and "默认入口已切换为新工作台" in skill
    assert '"--ui", choices=("v2", "legacy")' in (Path(cli.__file__).resolve()).read_text("utf-8")
