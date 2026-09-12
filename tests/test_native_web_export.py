"""Both Review Desk projections preserve the shared native export decision."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_preview_server import MockHandler, preview_server as server, workspace_api as workspace
from build.build_route import persist_route, resolve_build_route


def test_native_web_exports_show_missing_approval_without_legacy_manifest(tmp_path, monkeypatch):
    (tmp_path / 'request.json').write_text(json.dumps({'run_id': tmp_path.name, 'run_mode': 'fixture'}))
    persist_route(tmp_path, resolve_build_route({'profile': 'native', 'run_mode': 'fixture'}))
    decision = {'pages': [], 'blocked_pages': [{'page_id': 'p1', 'quality_block_reason': 'Final artifact approval is missing.'}], 'blocked_count': 1}
    calls = []
    def shared_queue(root, decisions, **kwargs):
        calls.append((root, decisions, kwargs))
        return decision
    monkeypatch.setattr(server, 'export_queue', shared_queue)
    monkeypatch.setattr(workspace, 'export_queue', shared_queue)
    handler = MockHandler(run_dir=tmp_path, runs_dir=tmp_path.parent)
    status, queue = handler.request('GET', '/api/export-queue/' + tmp_path.name + '?queue_type=client')
    assert status == 200 and queue == decision
    payload = workspace.build_workspace_payload(tmp_path)
    assert payload['run_summary']['export_queue'] == {'ready': 0, 'blocked': 1}
    assert len(calls) == 2
    assert all(call[2]['queue_type'] == 'client' for call in calls)
    assert not (tmp_path / 'preview_manifest.json').exists()
