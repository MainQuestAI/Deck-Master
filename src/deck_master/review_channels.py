"""Stage-specific reviewer discovery; never starts a review or mints evidence."""
from __future__ import annotations

from . import review_evidence
from .native_review_transport import probe_native_client

STAGES = ('content_preproduction', 'original_image_expression', 'svg_conversion', 'final_delivery')


def describe(*, check_native=False, adapter_context=None, project=None):
    registry = review_evidence.current_registry()
    providers = registry.describe()['providers']
    capabilities = review_evidence.reviewer_capabilities(adapter_context)
    native = probe_native_client(check_login=check_native)

    def receipt_channel(name):
        installed = [provider for provider in providers if name in provider['channels']]
        if capabilities[name]:
            return 'receipt_available'
        return 'provider_unavailable' if installed else 'receipt_not_configured'

    stages = []
    for stage in STAGES:
        channels = []
        native_supported = stage == 'content_preproduction'
        channels.append({'mode': 'native_independent', 'supported': native_supported,
            'status': native['status'] if native_supported else 'unsupported',
            'receipt_requirement': 'owned native completion bound to the Task and manuscript',
            'receipt_status': 'created_only_after_observed_completion' if native_supported else 'unsupported',
            'next_action': native['next_action'] if native_supported else
                'Native content review does not implement this stage; use an applicable review Task/channel.'})
        for mode, channel in (('independent_host', 'independent_review_receipts'),
                              ('human', 'human_review_receipts')):
            status = receipt_channel(channel)
            channels.append({'mode': mode, 'supported': True, 'status': status,
                'receipt_requirement': channel, 'receipt_status': receipt_channel(channel),
                'execution_verified': False,
                'next_action': ('Read the real review Task with deck-review; perform the scoped review and submit its bound authenticated receipt.'
                    if status == 'receipt_available' else
                    'Inspect the registered provider health; do not treat a failed transport as an absent reviewer.'
                    if status == 'provider_unavailable' else
                    'A trusted controller must provide the applicable authenticated receipt channel; do not self-sign JSON.')})
        stages.append({'stage': stage, 'task_stage': {'content_preproduction': 'preproduction',
            'original_image_expression': 'original_image', 'svg_conversion': 'page_visual',
            'final_delivery': 'final'}[stage], 'channels': channels,
            'execution_verified': False,
            'required_host_capabilities': ['original_expression_review.v1'] if stage == 'original_image_expression' else []})
    result = {'schema_version': 'review_channel_discovery.v1', 'status': 'described',
        'native_client': native, 'stages': stages,
        'limitations': ['Discovery never proves an independent review occurred or grants permission.',
            'Native content review is not original-image, SVG, final-delivery or human professional approval.',
            'Receipt availability does not prove the reviewer can inspect the selected artifacts.',
            'Host-self review requires the existing explicit policy; it is not an independent channel.']}
    if project is not None:
        from pathlib import Path
        from .store import Store
        store = Store(Path(project).expanduser())
        document = store.load_document()
        from .native_review_startup import describe as startup_history
        history = startup_history(store)
        result['native_startup_history'] = {key: value for key, value in history.items() if key != 'failures'}
        result['native_startup_failures'] = history['failures']
        result['project_id'] = document['project_id']
        result['revision_id'] = document['revision_id']
        # Historical failures remain visible, separate from live channel health.
        result['native_executions'] = [
            {'task_id': task['task_id'], 'status': task['status'],
             'execution_ref': task.get('execution_ref'),
             'error_code': (task.get('error') or {}).get('code'),
             'next_action': 'Inspect this Task and its evidence; do not infer a new review is needed from discovery.'}
            for ref in document.get('tasks') or []
            if (task := store.read_object_json(ref)).get('review_stage') == 'preproduction'
            and ((task.get('execution_ref') or '').startswith('codex-native:')
                 or (task.get('error') or {}).get('code') == 'native_review_failed')]
    return result
