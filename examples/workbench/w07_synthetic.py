"""Explicit browser-test fixture using real W07 services and synthetic tool events.

This module never calls a model. Its fake runtime events are confined to a
new test directory and a scoped observation-root patch; no real Codex session
or HOME file is changed. Do not use this factory in production runs.
"""
from __future__ import annotations

import base64
import io
import json
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
from deck_master import candidates, changes, generation, observations, service, tasks
from deck_master.models import canonical_json_bytes
from deck_master.samples import create_sample
from deck_master.store import Store

THREAD = '11111111-1111-7111-8111-111111111111'
TURN = '22222222-2222-7222-8222-222222222222'
EXECUTION = f'codex:{THREAD}:{TURN}'


class SyntheticW07:
    def __init__(self, root, pages=3):
        self.root = Path(root); self.project = self.root / 'synthetic-project'
        create_sample(self.project, page_count=pages, readonly=False)
        self.store = Store(self.project)
        self.runtime = self.root / 'local-only' / 'synthetic-runtime'

    def dispatch(self, page_id='p01', *, mode='trial', stage='blueprint', reference_page=None, instruction='Synthetic browser flow'):
        doc = self.store.load_document(); entry = next(p for p in doc['pages'] if p['page_id'] == page_id)
        original = stage == 'blueprint'; slot = 'blueprint' if original else 'svg'
        value = {'schema_version': 'change_intent.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
                 'mode': mode, 'intent': 'synthetic_browser', 'instruction': instruction, 'annotation_refs': [], 'max_calls': int(original),
                 'targets': [{'page_id': page_id, 'page_ref': entry['page'], 'layer': 'original_image' if original else 'svg',
                              'stage': stage, 'artifact_ref': entry.get(slot)}]}
        if reference_page:
            reference = next(p for p in doc['pages'] if p['page_id'] == reference_page)
            value['references'] = [{'page_id': reference_page, 'revision_id': doc['revision_id'], 'artifact_ref': reference['blueprint'], 'role': 'reference'}]
        planned = changes.plan(self.project, input=value)
        result = changes.commit(self.project, plan_id=planned['plan_id'], base_revision=doc['revision_id'], operation_id=str(uuid.uuid4()))
        return self.task(result['operation_result']['task_ids'][0])

    def task(self, task_id):
        return tasks._lookup_task(self.store.load_document(), task_id, self.store)

    def start(self, task):
        service.task_start(self.project, task_id=task['task_id'], execution_ref=EXECUTION,
                           supported_protocols=['generation.v1', 'changes.v1'],
                           capabilities=[*generation.CAPABILITIES, 'change_plan', 'candidate_result'])

    def image(self, task, variant=1):
        self.start(task)
        prepared = generation.prepared_input(self.store, self.store.load_document(), task)
        prepared['parameters'] = {'transparent_background': False}
        frozen = generation.freeze(self.project, task_id=task['task_id'], input=prepared,
                                    base_revision=self.store.current_revision_id(), operation_id=str(uuid.uuid4()))
        attempt = tasks.call_begin(self.store, task_id=task['task_id'], allowance_id=task['call_allowances'][0]['allowance_id'],
                                   execution_ref=EXECUTION, request_id=frozen['request_id'])
        started = time.time_ns() // 1000000
        image = Image.new('RGB', (960, 540), ['#f5f7f0', '#eef5f4', '#fff6e7'][variant % 3]); draw = ImageDraw.Draw(image)
        draw.rectangle((55, 60, 63, 466), fill='#148564')
        draw.text((94, 65), f'SYNTHETIC CANDIDATE {variant} / {task["scope_pages"][0]}', fill='#17261f', font_size=30)
        for i, text in enumerate(('Preserve page facts', 'Compare the fixed reference', 'Adopt only after review')):
            y = 150 + i * 92
            draw.rounded_rectangle((94 + variant * 4, y, 860, y + 62), radius=8, fill=['#d4e7d9', '#c5ddd5', '#e3e1c7'][(variant + i) % 3])
            draw.text((115, y + 17), text, fill='#243a30', font_size=23)
        draw.text((94, 464), 'Synthetic protocol evidence. No model call or quality approval.', fill='#53635a', font_size=18)
        output = io.BytesIO(); image.save(output, 'PNG'); raw = output.getvalue()
        item_id = 'exec-' + str(uuid.uuid4()); saved = self.runtime / 'generated_images' / THREAD / (item_id + '.png')
        saved.parent.mkdir(parents=True, exist_ok=True); saved.write_bytes(raw)
        session = self.runtime / 'sessions/2026/09/29' / ('rollout-2026-09-29T00-00-00-' + THREAD + '.jsonl')
        session.parent.mkdir(parents=True, exist_ok=True)
        if not session.exists(): session.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': THREAD, 'cli_version': 'synthetic-w07-test'}}) + '\n')
        arguments = {'prompt': prepared['prompt'], 'transparent_background': False}
        if prepared['references']:
            arguments['referenced_image_paths'] = [str(self.store.project_root / r['file']['path']) for r in prepared['references']]
        call_id = 'synthetic-call-' + uuid.uuid4().hex
        code = 'const result = await tools.image_gen__imagegen(' + json.dumps(arguments) + ');generatedImage(result);'
        events = [
            {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec', 'call_id': call_id, 'input': code}},
            {'type': 'event_msg', 'payload': {'type': 'item_completed', 'thread_id': THREAD, 'turn_id': TURN,
             'started_at_ms': started, 'completed_at_ms': time.time_ns() // 1000000,
             'item': {'type': 'Extension', 'kind': 'image_gen.generation', 'id': item_id, 'status': 'completed',
                      'revisedPrompt': prepared['prompt'], 'transparentBackground': False, 'result': base64.b64encode(raw).decode(), 'savedPath': str(saved), 'failure': None}}},
            {'type': 'response_item', 'payload': {'type': 'custom_tool_call_output', 'call_id': call_id,
             'output': [{'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(raw).decode()}]}}]
        with session.open('a') as file:
            for event in events: file.write(json.dumps(event) + '\n')
        selector = {'source': 'codex_session.v1', 'thread_id': THREAD, 'turn_id': TURN, 'item_id': item_id}
        with patch.object(observations, '_session_root', lambda: self.runtime / 'sessions'):
            tasks.call_settle(self.store, task_id=task['task_id'], allowance_id=attempt['allowance_id'], attempt_id=attempt['attempt_id'],
                              outcome='consumed', report_bytes=canonical_json_bytes(selector))
        staging = self.store.staging_dir / task['operation_id']; staging.mkdir(exist_ok=True); (staging / 'candidate.png').write_bytes(raw)
        result = service.accept_result(self.project, **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')}, result_payload={
            'kind': 'blueprint', 'files': [{'file_id': 'png', 'path': 'candidate.png', 'media_type': 'image/png'}],
            'generation_result': {'request_id': frozen['request_id'], 'attempt_id': attempt['attempt_id']},
            'artifact_specs': [{'file_id': 'png', 'role': 'blueprint', 'page_id': task['scope_pages'][0],
                                'provenance': {'source_type': 'host_generated', 'tool': 'synthetic-runtime-adapter'}}]})
        return result

    def svg(self, task, variant=1):
        self.start(task); doc = self.store.load_document(); entry = next(e for e in doc['pages'] if e['page_id'] == task['scope_pages'][0])
        original = self.store.read_object_json(entry['blueprint'])['file']['sha256']
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" data-blueprint-sha256="{original}">
<rect width="960" height="540" fill="#f5f7f0"/><rect x="55" y="60" width="8" height="406" fill="#148564"/>
<text x="94" y="95" font-family="Arial" font-size="30" fill="#17261f">SYNTHETIC SVG {variant}</text>
<rect x="94" y="160" width="766" height="90" fill="#d4e7d9"/><rect x="94" y="280" width="{650+variant*10}" height="90" fill="#c5ddd5"/>
<text x="115" y="215" font-family="Arial" font-size="24" fill="#243a30">Editable shapes, unchanged original</text>
<text x="115" y="335" font-family="Arial" font-size="24" fill="#243a30">Synthetic mechanism proof only</text></svg>'''
        staging = self.store.staging_dir / task['operation_id']; staging.mkdir(exist_ok=True); (staging / 'page.svg').write_text(svg)
        return service.accept_result(self.project, **{k: task[k] for k in ('task_id', 'operation_id', 'produced_against')}, result_payload={
            'kind': task['kind'], 'files': [{'file_id': 'svg', 'path': 'page.svg', 'media_type': 'image/svg+xml'}],
            'artifact_specs': [{'file_id': 'svg', 'role': 'svg', 'page_id': entry['page_id'],
                                'provenance': {'source_type': 'unknown', 'tool': 'synthetic-svg-test'}}]})

    def adopt(self, ids):
        doc = self.store.load_document(); plan = candidates.plan(self.project, input={'schema_version': 'candidate_selection.v1',
            'project_id': doc['project_id'], 'base_revision': doc['revision_id'], 'candidate_ids': ids})['plan']
        return candidates.adopt(self.project, input=plan, base_revision=plan['base_revision'], operation_id=str(uuid.uuid4()))
