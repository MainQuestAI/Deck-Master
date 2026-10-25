"""RP-04: UI recovery reads committed receipts before enforcing new-write gates."""
import io
import uuid

import pytest
from PIL import Image

from deck_master import annotation_service, collaboration, eligibility, visual_styles
from deck_master.operations import OperationError
from test_eligibility_enforcement import _project, _start, _declared


@pytest.mark.parametrize('kind', ['annotation', 'reference'])
def test_exact_replay_after_pause_preserves_original_receipt_and_blocks_new_write(tmp_path, kind):
    project, store = _project(tmp_path)
    _start(project, store)
    doc = store.load_document()
    op = str(uuid.uuid4())
    if kind == 'annotation':
        payload = {'schema_version': 'annotation_batch.v1', 'project_id': doc['project_id'], 'annotations': [
            {'schema_version': 'annotation.v1', 'project_id': doc['project_id'], 'base_revision': doc['revision_id'],
             'scope': 'project', 'intent': 'note', 'body': 'Synthetic recovery note',
             'status': 'open', 'location': {'kind': 'whole'}}]}

        def write(operation, base, changed=False):
            data = {**payload, 'annotations': [{**payload['annotations'][0], 'body': 'Changed'}]} if changed else payload
            return annotation_service.save(project, input=data, base_revision=base, operation_id=operation)
    else:
        def png(color):
            output = io.BytesIO()
            Image.new('RGB', (80, 40), color).save(output, format='PNG')
            return output.getvalue()

        def write(operation, base, changed=False):
            return visual_styles.import_reference(project, data=png('black' if changed else 'white'),
                                                  base_revision=base, operation_id=operation)
    first = write(op, doc['revision_id'])
    collaboration.pause_request(project, reason='Synthetic pause after response loss',
        base_revision=store.current_revision_id(), operation_id=str(uuid.uuid4()), instruction_evidence=_declared(store))
    paused = store.read_current()
    before = store.load_document()
    replay = write(op, doc['revision_id'])
    assert replay['status'] == first['status'] == 'committed'
    assert replay['operation_result'] == first['operation_result']
    assert store.read_current() == paused and store.load_document() == before
    with pytest.raises(OperationError):
        write(op, doc['revision_id'], changed=True)
    with pytest.raises(eligibility.EligibilityBlocked):
        write(str(uuid.uuid4()), before['revision_id'])
    assert store.read_current() == paused and store.load_document() == before
