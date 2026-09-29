"""Explicit assembly uses the normal compiler and current page review gates."""
from __future__ import annotations

from . import operations
from .local_state import project_path
from .models import input_alignment, validate_schema


def require_assembly_ready(store, document):
    from .editing import page_visual_summary
    from .tasks import _validate_svg_reference
    if not document['pages']:
        raise operations.OperationError('stage_prerequisite_missing', 'pages', 'assembly requires current pages')
    if input_alignment(document) not in ('current', 'legacy_current'):
        raise operations.OperationError('stage_prerequisite_missing', 'content_basis', 'reconcile current content inputs before assembly')
    for entry in document['pages']:
        objects = {}
        for slot in ('blueprint', 'svg', 'svg_preview'):
            if not entry.get(slot):
                raise operations.OperationError('stage_prerequisite_missing', f"pages/{entry['page_id']}/{slot}", 'assembly requires original image, current SVG and its preview')
            artifact = store.read_object_json(entry[slot]); validate_schema('artifact', artifact)
            if artifact['role'] != slot or artifact['page_id'] != entry['page_id']:
                raise operations.OperationError('stage_prerequisite_missing', slot, 'artifact belongs to another page or stage')
            store.read_object_bytes(artifact['file']); objects[slot] = artifact
        _validate_svg_reference(store.read_object_bytes(objects['svg']['file']), objects['blueprint']['file']['sha256'])
        if entry['svg'] not in objects['svg_preview'].get('derived_from', []):
            raise operations.OperationError('stage_prerequisite_missing', 'svg_preview', 'preview does not belong to the current SVG')
        check = page_visual_summary(store, document, entry)
        if check['status'] != 'pass':
            raise operations.OperationError('stage_quality_blocked', f"pages/{entry['page_id']}/page_visual", 'current page visual review must pass before assembly')


@operations.public
def assemble(project, *, base_revision, operation_id):
    from .pipeline import produce, NeedsTool, RendererError
    try:
        return produce(project_path(project), base_revision=base_revision, operation_id=operation_id)
    except NeedsTool as exc:
        raise operations.OperationError('needs_tool', 'toolchain', str(exc), exit_code=3, http_status=503) from exc
    except RendererError as exc:
        raise operations.OperationError('renderer_execution_failed', 'toolchain', str(exc), exit_code=4, http_status=503) from exc
