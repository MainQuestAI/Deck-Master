"""W03 isolated core/CLI/HTTP proof. No HOME registry or model call is used.

Run with the candidate installed, or PYTHONPATH=src from its checkout. --out
must name a new directory. Kept evidence uses logical path labels and excludes
session tokens. The project and registry stay under --out for inspection.
"""
from __future__ import annotations

import argparse
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

from deck_master import local_runtime as runtime, ui_journal
from deck_master.models import content_identity
from deck_master.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root = Path(args.out).expanduser().absolute()
    root.mkdir(parents=True, exist_ok=False)
    evidence = root / 'evidence'
    evidence.mkdir()
    registry = root / 'config' / 'projects.json'
    project = root / 'project'
    timings = []

    def save(name, payload):
        def redact(value):
            if isinstance(value, dict):
                return {key: redact(val) for key, val in value.items() if key.lower() not in ('token', 'x-deck-token')}
            if isinstance(value, list):
                return [redact(val) for val in value]
            if isinstance(value, str):
                value = value.replace(str(root), '<example>').replace(str(Path(__file__).resolve().parents[2]), '<checkout>')
                if value.startswith('/'):
                    return '<local-resource>/' + Path(value).name
                return value
            return value
        (evidence / (name + '.json')).write_text(json.dumps(redact(payload), ensure_ascii=False, indent=2) + '\n')

    def command(name, *flags):
        start = time.monotonic()
        run = subprocess.run([sys.executable, '-m', 'deck_master', *flags], capture_output=True, text=True)
        raw = run.stdout or run.stderr
        try:
            response = json.loads(raw)
        except ValueError:
            response = {'output': raw}
        result = {'exit_code': run.returncode, 'response': response}
        save(name, result)
        timings.append({'step': name, 'seconds': round(time.monotonic() - start, 4)})
        return result

    def request(url, path, data=None):
        parts = urlsplit(url)
        connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=5)
        headers = {}
        if data is not None:
            token = request(url, '/api/session')[1]['token']
            headers = {'Origin': f'http://{parts.hostname}:{parts.port}', 'X-Deck-Token': token}
        try:
            connection.request('POST' if data is not None else 'GET', path,
                body=json.dumps(data).encode() if data is not None else None, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    launch_desc = runtime.descriptor(registry=registry)
    project_desc = None
    try:
        boot = command('01-launcher', 'workbench', '--registry', str(registry), '--no-open')
        assert boot['exit_code'] in (0, 3)
        launch = boot['response']
        assert launch['role'] == 'launcher' and launch['project_id'] is None
        code, listing = request(launch['url'], '/api/projects')
        assert code == 200 and listing['projects'] == []
        save('02-empty-project-list', listing)
        code, created = request(launch['url'], '/api/projects/create',
            {'path': str(project), 'title': '合成新建验证', 'brief': '说明工作台使用流程', 'audience': '首次使用者'})
        assert code == 200 and created['registered'] and created['model_started'] is False
        save('03-create', created)
        initial_task = created['pending_tasks'][0]['task_id']
        code, opened = request(launch['url'], '/api/projects/open', {'entry_id': created['project']['entry_id'], 'ui': 'legacy'})
        assert code == 200 and opened['ui_available']
        save('04-open-legacy', opened)
        project_desc = runtime.descriptor(project=project)
        project_url = opened['url']
        source = root / 'facts.md'
        source.write_text('# 合成事实\n本材料只解释工作台流程，不提供客户成效。\n')
        store = Store(project)
        code, update = request(project_url, '/api/inputs/update',
            {'patch': {'reason': '补充材料', 'source_changes': {'add': [{'path': str(source)}]}},
             'base_revision': store.current_revision_id(), 'operation_id': 'add-material'})
        assert code == 200
        save('05-input-update', update)
        before_handoff = store.current_revision_id()
        code, handoff = request(project_url, '/api/compose/handoff')
        assert code == 200 and handoff['task_id'] != initial_task
        assert request(project_url, '/api/compose/handoff')[1] == handoff
        assert store.current_revision_id() == before_handoff
        save('06-handoff', handoff)
        info = request(project_url, '/api/project')[1]
        draft = {'schema_version': 'ui_draft.v1', 'project_id': info['project_id'], 'project_identity': info['project_identity'],
                 'draft_id': 'example-draft', 'target': {'scope': 'project', 'page_id': None, 'layer': 'notes'},
                 'base_revision': info['revision_id'], 'base_ref': None, 'content': {'text': '等待 Host 整理；这是个人草稿。'}, 'pending': None}
        before = (store.deck_root / 'current.json').read_bytes(), content_identity(store.load_document())
        code, saved = request(project_url, '/api/drafts/save', {'draft': draft})
        assert code == 200 and saved['status'] == 'saved'
        assert request(project_url, '/api/drafts/save', {'draft': draft})[1]['replayed']
        save('07-draft-ack', saved)
        unsent = {**draft, 'draft_id': 'offline-draft', 'content': {'text': '尚未同步的独立恢复副本'}}
        recovery = ui_journal.recovery_file(project, draft=unsent)
        save('08-recovery-file', recovery)
        first = runtime.read_state(project_desc)
        runtime.stop(project_desc)
        with socket.socket() as occupied:
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            occupied.bind(('127.0.0.1', first['port']))
            occupied.listen()
            second = runtime.ensure(project_desc)
            assert second['port'] != first['port']
            loaded = request(second['url'], '/api/drafts')[1]
            assert len(loaded['records']) == 1
            save('09-cross-port-ack-only', {'first_port': first['port'], 'second_port': second['port'], 'drafts': loaded})
            imported = request(second['url'], '/api/drafts/import', {'recovery': recovery})
            assert imported[0] == 200
            save('10-explicit-recovery-import', imported[1])
            assert ((store.deck_root / 'current.json').read_bytes(), content_identity(store.load_document())) == before
            runtime.stop(launch_desc)
            assert runtime.healthy(second, project_desc)
            runtime.ensure(launch_desc)
            runtime.stop(project_desc)
            assert runtime.healthy(runtime.read_state(launch_desc), launch_desc)
        save('checks', {'evidence_level': 'core/CLI/HTTP/real local process; synthetic project',
            'empty_launcher': True, 'one_eligible_compose_after_material_update': True, 'handoff_no_new_task': True,
            'draft_keeps_business_revision_and_content_identity': True, 'ack_recovers_on_new_port': True,
            'unsent_draft_requires_explicit_import': True, 'independent_shutdown': True,
            'model_calls': 0, 'browser_verified': False, 'real_home_changed': False, 'installed_package_verified': False,
            'core_cli_timings': timings, 'installation_download_host_time': 'not measured', 'user_help_requests': 'not measured'})
        print(json.dumps({'status': 'verified', 'evidence': str(evidence)}, ensure_ascii=False))
    finally:
        if project_desc:
            runtime.stop(project_desc)
        runtime.stop(launch_desc)


if __name__ == '__main__':
    main()
