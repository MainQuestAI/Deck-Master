"""D00a only: verify fixed inputs and exercise the existing zero-call entry.

Run with the checkout's editable development Python. Outputs are local runs,
never benchmark content or professional acceptance. No model client is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from deck_master import method_resources, service
from deck_master.sources import read_source
from deck_master.store import Store


ROOT = Path(__file__).resolve().parent


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def run(out: Path) -> dict:
    # Refuse to overwrite prior evidence, including incomplete/failed runs.
    out.mkdir(parents=True, exist_ok=False)
    report = {
        'schema_version': 'business_expression_input_triage.v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'code_base': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'status': 'running', 'model_calls': 0, 'professional_evidence': 'not_evaluated',
        'material_manifest_sha256': digest((ROOT / 'manifest.json').read_bytes()),
        'materials': [], 'projects': [], 'x01': 'inactive',
    }
    try:
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        raw_tasks = (ROOT / 'tasks.json').read_bytes()
        if digest(raw_tasks) != manifest['tasks_sha256']:
            raise ValueError('tasks.json differs from the selected material manifest')
        tasks = json.loads(raw_tasks)['tasks']
        sources = {}
        for pack in manifest['packs']:
            path = ROOT / pack['path']
            raw = path.read_bytes()
            if digest(raw) != pack['sha256'] or len(raw) != pack['bytes']:
                raise ValueError(f"selected input changed: {pack['id']}")
            if pack['split'] == 'holdout':
                report['materials'].append({
                    'pack_id': pack['id'], 'split': 'holdout', 'sha256': pack['sha256'],
                    'bytes': len(raw), 'status': 'hash_verified_not_extracted',
                })
                continue
            extract = read_source(path)
            if extract.status != 'read' or extract.text.encode('utf-8') != raw:
                raise ValueError(f"input not fully readable: {pack['id']} ({extract.status})")
            if extract.original_sha256 != pack['sha256']:
                raise ValueError(f"extract hash mismatch: {pack['id']}")
            tail = next(line for line in reversed(extract.text.splitlines()) if line.strip())
            if '材料尾部约束' not in tail or not any(row['text'] == tail for row in extract.locators):
                raise ValueError(f"input lost its tail constraint: {pack['id']}")
            sources[pack['id']] = path
            save(out / 'extracts' / f"{pack['id']}.json", {
                'sha256': extract.original_sha256, 'text': extract.text, 'locators': extract.locators,
            })
            report['materials'].append({
                'pack_id': pack['id'], 'split': 'development', 'sha256': pack['sha256'],
                'bytes': len(raw), 'status': extract.status, 'full_text_equal': True,
                'locators': len(extract.locators), 'tail_constraint_retained': True,
            })
        for definition in tasks:
            if definition['split'] != 'development':
                continue
            project = out / 'projects' / definition['id']
            result = service.create(
                project, brief=definition['brief'], title=definition['title'],
                sources=[sources[definition['pack_id']]], audience=definition['audience'],
                scenario=definition['scenario'], presentation_mode=definition['presentation_mode'],
                page_limit=definition['page_limit'], existing_decisions=definition['existing_decisions'],
                request_input=definition['request_input'],
                selected_resource_ids=definition['method_selection']['framing'],
            )
            store = Store(project)
            document = store.load_document()
            task_id = result['pending_tasks'][0]['task_id']
            task = next(store.read_object_json(ref) for ref in document['tasks']
                        if store.read_object_json(ref)['task_id'] == task_id)
            consumed = method_resources.read_task_methods(project, task_id)
            request = document['collaboration']['request']
            if (document['pages'] or request['intent'] != 'content_only'
                    or request['content_intent'] != 'plan_only'
                    or request['scope']['layers'] != ['narrative', 'plan']
                    or task['status'] != 'awaiting_host' or consumed['status'] != 'current'):
                raise ValueError(f"entry scope or frozen method basis mismatch: {definition['id']}")
            actual_methods = []
            for method in consumed['methods']:
                raw = method['content'].encode('utf-8')
                if digest(raw) != method['sha256']:
                    raise ValueError(f"returned method bytes mismatch: {method['id']}")
                path = out / 'methods' / method['sha256'] / Path(method['relative_path']).name
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                actual_methods.append({
                    'id': method['id'], 'relative_path': method['relative_path'],
                    'sha256': method['sha256'], 'bytes': len(raw),
                })
            # Full, unsanitized work orders are local-only evidence.
            save(out / 'workorders' / f"{definition['id']}.json", consumed)
            report['projects'].append({
                'task_definition_id': definition['id'], 'project_id': document['project_id'],
                'revision_id': document['revision_id'], 'task_id': task_id,
                'source_hash': document['sources'][0]['original_sha256'],
                'page_count': len(document['pages']), 'request_intent': request['intent'],
                'content_intent': request['content_intent'], 'layers': request['scope']['layers'],
                'phase': task['collaboration_binding']['phase'], 'task_status': task['status'],
                'method_basis_status': consumed['status'], 'methods': actual_methods,
                'method_total_bytes': sum(item['bytes'] for item in actual_methods),
            })
        report['status'] = 'pass'
        report['conclusion'] = 'D00a readable inputs and scoped pending tasks only; D00 has not passed'
    except Exception as exc:
        report['status'] = 'fail'
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        save(out / 'input-triage.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(run(options.out.expanduser().resolve()), ensure_ascii=False, indent=2))
