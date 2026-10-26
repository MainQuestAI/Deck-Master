"""Real CLI acceptance chain (review-repair verification, 2026-09-16).

Drives the rebuilt core through its public CLI exactly as a Host would:
create → continue → capability-aware framing claim/accept → explicit
source-bound manuscript import → detached view → honest bounded continuation. Both draft import entries are covered. Exit codes
follow spec 09.3.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from deck_master.cli import main as cli_main

REPO = Path(__file__).resolve().parents[2]
ENVELOPE = REPO / "docs" / "specs" / "deck-master-rebuild-v1" / "examples" / "roundtrips" / "result-envelope" / "compose.json"


@pytest.fixture(autouse=True)
def owned_cli_services(monkeypatch):
    from deck_master import local_runtime
    owned = []
    ensure = local_runtime.ensure
    def track(desc, **kwargs):
        state = ensure(desc, **kwargs)
        if not state.get('reused'):
            owned.append((desc, state['instance_id']))
        return state
    monkeypatch.setattr(local_runtime, 'ensure', track)
    try:
        yield
    finally:
        for desc, instance in reversed(owned):
            state = local_runtime.read_state(desc)
            if state and state.get('instance_id') == instance:
                local_runtime.stop(desc)


def cli_main(argv: list[str]) -> int:
    """Run one CLI command in-process and return its exit code."""
    from deck_master.cli import main

    return main(argv)


def _material(tmp_path: Path) -> Path:
    material = tmp_path / "materials" / "brief.txt"
    material.parent.mkdir()
    material.write_text(
        "## 任务\n向运营团队说明条件自动处理方案。\n\n"
        "（材料尾部约束）合成材料，不可回写。",
        encoding="utf-8",
    )
    return material


def _draft_payload() -> dict:
    return {
        "pages": [
            {
                "schema_version": "deck_page_package.v2",
                "page_id": "d1",
                "customer_visible": {
                    "title": "导入稿标题",
                    "body_blocks": [{"id": "intro", "type": "paragraph", "text": "完整正文。"}],
                },
                "visual_spec": {"intent": "纯正文页", "reference_mode": "new_design"},
            }
        ]
    }


def test_full_cli_chain_create_start_accept_view_continue(tmp_path: Path) -> None:
    """Current framing claim/accept, explicit manuscript import and detached view."""
    from deck_master.service import continue_project
    from deck_master.store import Store
    from deck_master.web import ensure_service, stop_service
    project = tmp_path / 'proj'
    assert cli_main(['create', '--brief', 'Explain the bounded process', '--audience', 'operators',
                     '--source', str(_material(tmp_path)), '--out', str(project)]) == 0
    assert cli_main(['continue', '--project', str(project)]) == 3
    task = continue_project(project)['pending_tasks'][0]
    start = ['task', 'start', '--project', str(project), '--task-id', task['task_id'],
             '--execution-ref', 'L1-synthetic-cli-author', '--supported-protocol', 'compose.v2']
    for capability in task['required_capabilities']:
        start += ['--capability', capability]
    assert cli_main(start) == 0
    narrative = {'schema_version': 'narrative.v1', 'narrative_id': 'cli-frame', 'version': 1,
        'project_id': Store(project).load_document()['project_id'], 'origin': 'host_composed',
        'maturity': 'framing', 'input_basis': [], 'communication_job': {
            'mode': 'train', 'audience_fact_key': 'task.audience', 'audience_question': 'What action comes next?',
            'desired_outcome': 'Follow the bounded process', 'observable_success': 'Select the proper action',
            'use_mode': 'live', 'primary_use': 'live'}, 'central_node_id': None,
        'nodes': [], 'edges': [], 'issues': [], 'alternatives': [], 'previous_ref': None}
    envelope = {'schema_version': 'compose_result.v2', 'kind': 'compose', 'variant': 'framing',
        'task_id': task['task_id'], 'operation_id': task['operation_id'], 'produced_against': task['produced_against'],
        'eligibility_digest': task['collaboration_binding']['eligibility_digest'],
        'payload': {'narrative': narrative}, 'usage_events': []}
    result = tmp_path / 'framing.json'
    result.write_text(json.dumps(envelope))
    assert cli_main(['task', 'accept', '--project', str(project), '--task-id', task['task_id'],
        '--operation-id', task['operation_id'], '--produced-against', task['produced_against'], '--result', str(result)]) == 0
    assert Store(project).load_document()['pages'] == []
    draft = tmp_path / 'explicit-draft.json'
    draft.write_text(json.dumps(_draft_payload()))
    evidence = tmp_path / 'instruction.json'
    evidence.write_text(json.dumps({'kind': 'host_attested_instruction',
        'text': 'Import this confirmed manuscript exactly', 'source_locator': 'L1:cli-import'}))
    document = Store(project).load_document()
    replacement = tmp_path / 'import-request.json'
    replacement.write_text(json.dumps({'base_revision': document['revision_id'], 'operation_id': 'L1-cli-import-request',
        'request': {'intent': 'full_deck', 'content_intent': None,
            'replace_request_id': document['collaboration']['request']['request_id'],
            'scope': {**document['collaboration']['request']['scope'], 'page_ids': ['d1']},
            'instruction_evidence': json.loads(evidence.read_text())}}))
    assert cli_main(['collaboration', 'request', 'replace', str(project), '--input', str(replacement)]) == 0
    assert cli_main(['import-draft', '--project', str(project), '--input', str(draft),
        '--base-revision', Store(project).current_revision_id(), '--operation-id', 'L1-cli-manuscript-import',
        '--instruction-evidence', str(evidence)]) == 0
    assert [entry['page_id'] for entry in Store(project).load_document()['pages']] == ['d1']
    try:
        state = ensure_service(project)
        with urllib.request.urlopen(state['url'].rstrip('/') + '/api/view', timeout=5) as response:
            view = json.loads(response.read())
        assert view['page_count'] == 1
        assert view['pages'][0]['slots']['content']['path'].startswith('.deckmaster/objects/')
        again = ensure_service(project)
        assert again['reused'] is True and again['url'] == state['url']
        follow_up = continue_project(project)
        assert follow_up['status'] == 'needs_input'
        assert not follow_up['pending_tasks']
        assert not Store(project).load_document()['collaboration']['authorizations']
    finally:
        stop_service(project)


def test_import_draft_cli_entry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('DECK_MASTER_NO_AUTO_VIEW', '1')
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps(_draft_payload(), ensure_ascii=False), encoding="utf-8")
    project = tmp_path / "proj-draft"
    assert cli_main(["import-draft", "--project", str(project), "--input", str(draft_file)]) == 0
    view = _load_view(project)
    assert view["page_count"] == 1
    assert view["pages"][0]["page_id"] == "d1"
    from deck_master.service import continue_project

    follow_up = continue_project(project)
    assert follow_up["status"] == "needs_input"
    assert follow_up["pending_tasks"] == []


def test_create_with_draft_adopts_pages(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('DECK_MASTER_NO_AUTO_VIEW', '1')
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps(_draft_payload(), ensure_ascii=False), encoding="utf-8")
    project = tmp_path / "proj-draft2"
    assert cli_main([
        "create", "--brief", "带稿创建", "--draft", str(draft_file), "--out", str(project)
    ]) == 0
    view = _load_view(project)
    assert view["page_count"] == 1
    from deck_master.service import continue_project

    follow_up = continue_project(project)
    assert follow_up["status"] == "needs_input"
    assert follow_up["pending_tasks"] == []


def test_invalid_result_json_exits_2(tmp_path: Path) -> None:
    from deck_master.service import continue_project

    project = tmp_path / "proj"
    material = _material(tmp_path)
    cli_main(["create", "--brief", "简报", "--source", str(material), "--out", str(project)])
    pending = continue_project(project)["pending_tasks"]
    assert pending, "continue must hand the Host a pending task"
    task_id = pending[0]["task_id"]
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    code = cli_main([
        "task", "accept",
        "--project", str(project),
        "--task-id", task_id,
        "--operation-id", pending[0]["operation_id"],
        "--produced-against", pending[0]["produced_against"],
        "--result", str(bad),
    ])
    assert code == 2, "unreadable JSON must map to exit code 2, not a traceback"


def _load_view(project: Path) -> dict:
    from deck_master.view import project_view

    return project_view(project)


def _read_document(project: Path) -> dict:
    from deck_master.store import Store

    return Store(project).load_document()


def _read_view(project: Path) -> dict:
    return _load_view(project)
