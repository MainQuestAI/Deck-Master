"""Run from checkout with .venv/bin/python; writes synthetic transport evidence."""
from collections import Counter
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from deck_master import service, method_resources
from deck_master.models import sha256_bytes
from deck_master.store import Store

OUT = Path(__file__).resolve().parent


def main():
    with TemporaryDirectory(prefix='deck-master-n4a-synthetic-') as temporary:
        root = Path(temporary)
        source = root / 'material.txt'; source.write_text('SYNTHETIC_ENGINEERING full source\nKeep the final constraint and notes.\n')
        second_source = root / 'unreferenced.txt'; second_source.write_text('Required source without a Page citation.\n')
        project = root / 'project'
        service.create(project, brief='SYNTHETIC_ENGINEERING context probe', sources=[source, second_source])
        store = Store(project); document = store.load_document()
        task = store.read_object_json(document['tasks'][0])
        second = {**task, 'task_id': 'synthetic-second', 'operation_id': 'synthetic-second'}
        document['tasks'].append(store.put_json_object(second))
        immutable = {ref['sha256'] for ref in document['tasks']} | {s['extract']['sha256'] for s in document['sources']}
        byte_reads, decodes, method_reads, snapshots = Counter(), Counter(), Counter(), Counter()
        original_read, original_loads, original_path_read, original_document = Store.read_object_bytes, json.loads, Path.read_bytes, Store.load_document
        method_root = method_resources.resolve_root()
        def read(self, ref):
            byte_reads[ref['path']] += 1
            return original_read(self, ref)
        def loads(raw, *args, **kwargs):
            digest = sha256_bytes(raw.encode() if isinstance(raw, str) else raw)
            if digest in immutable:
                decodes[digest] += 1
            return original_loads(raw, *args, **kwargs)
        def path_read(path):
            if path.is_relative_to(method_root):
                method_reads[str(path.relative_to(method_root))] += 1
            return original_path_read(path)
        def document_read(self, revision_id=None):
            snapshots[revision_id or self.current_revision_id()] += 1
            return original_document(self, revision_id)
        with patch.object(Store, 'read_object_bytes', read), patch.object(json, 'loads', loads), patch.object(Path, 'read_bytes', path_read), patch.object(Store, 'load_document', document_read):
            v2 = service._pending_host_tasks(document, store, read_protocol='work_context.v2')
            serialized = json.dumps(v2, ensure_ascii=False, sort_keys=True).encode()
        v1 = service._pending_host_tasks(document, store)
        legacy_methods = method_resources.read_skill_methods('deck-content', project=project, task_id=task['task_id'])
        context_methods = method_resources.read_skill_methods('deck-content', project=project, task_id=task['task_id'], read_protocol='work_context.v2')
        repeated = {key: serialized.decode().count(json.dumps(body['content'], ensure_ascii=False)) for key, body in v2['bodies'].items()}
        report = {'evidence_type': 'SYNTHETIC_ENGINEERING', 'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'executed_files_sha256': {name: sha256_bytes(Path(name).read_bytes()) for name in (
                      'src/deck_master/work_context.py', 'src/deck_master/service.py',
                      'src/deck_master/method_resources.py', 'src/deck_master/capabilities.py',
                      'tests/rebuild/test_rc4_work_context.py', str(Path(__file__).relative_to(Path.cwd())))},
                  'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
                  'python': platform.python_version(), 'platform': platform.platform(), 'cache_mode': 'request-only full; no persistent or Host cache',
                  'tasks': len(v2['tasks']), 'required_sources_per_task': len(document['sources']),
                  'actual_immutable_bytes_reader_calls': dict(byte_reads), 'actual_immutable_json_decoder_calls': dict(decodes),
                  'actual_method_path_bytes_reader_calls': dict(method_reads), 'actual_dispatch_document_reads': dict(snapshots),
                  'serialized_unique_body_occurrences': repeated,
                  'v2_skill_unique_body_occurrences': {key: json.dumps(context_methods, ensure_ascii=False).count(json.dumps(body['content'], ensure_ascii=False)) for key, body in context_methods['bodies'].items()},
                  'v1_skill_method_body_occurrences': {item['id']: json.dumps(legacy_methods, ensure_ascii=False).count(json.dumps(item['content'], ensure_ascii=False)) for item in legacy_methods['methods']},
                  'serialized_bytes': {'v1_pending_summaries': len(json.dumps(v1, ensure_ascii=False).encode()), 'v2_full_pending_context': len(serialized),
                                       'v1_skill_task_methods': len(json.dumps(legacy_methods, ensure_ascii=False).encode()),
                                       'v2_skill_task_methods': len(json.dumps(context_methods, ensure_ascii=False).encode())},
                  'limits': ['Synthetic engineering fixtures; no customer performance or model-quality claim',
                             'v1 pending summaries contain method metadata; v2 full adds method bytes, so those byte totals are not an equal-content compression ratio',
                             'Existing source extract format can repeat text in its locators; the immutable extract is transported once without rewriting its schema',
                             'A cache offer alone cannot establish an observed Host session; CLI delta is cold full']}
        assert max(byte_reads.values()) == max(decodes.values()) == max(method_reads.values()) == 1
        assert set(decodes) == immutable and set(repeated.values()) == {1}
        for filename, value in [('N4A-counts.json', report), ('N4A-v1-pending.sample.json', v1), ('N4A-v2-full.sample.json', v2),
                                ('N4A-v1-skill.sample.json', legacy_methods), ('N4A-v2-skill.sample.json', context_methods)]:
            (OUT / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
