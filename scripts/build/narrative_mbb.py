"""On-demand MBB compatibility view. Public Narrative remains the sole source."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from native_pptx.contracts import ContractError, assert_v2, read_json, sha256_file, sha256_json, safe_run_path

PROJECTION_PATH = Path('high_density_build/mbb/narrative_projection.json')


def native_authority(root: Path) -> bool:
    from build.build_route import load_persisted_route
    return load_persisted_route(root).get('engine_id') == 'deck_native'


def reject_compatibility_write(root: Path) -> None:
    if native_authority(root):
        raise ContractError('New native runs use public Narrative as the only storyline authority; update it through the public planning workflow.')


def project_narrative_mbb(root: Path) -> dict[str, Any]:
    from workflow.actions import revision_read, revision_input_path
    from build.native_engine import _approved_packages
    root = Path(root).expanduser().resolve()
    with revision_read(root) as revision:
        if not native_authority(root):
            raise ContractError('Narrative MBB projection requires a persisted native route')
        narrative_path = revision_input_path(root, root / 'narrative_plan.json')
        narrative = read_json(narrative_path)
        if narrative.get('run_id') not in {None, '', root.name}:
            raise ContractError('public Narrative belongs to another run')
        packages = _approved_packages(root)
        refs = [{'ref': f"page_packages/{p['page_id']}.json", 'sha256': sha256_file(revision_input_path(root, root / f"page_packages/{p['page_id']}.json"))} for p in packages]
        source_hash = sha256_file(narrative_path)
        result = {
            'schema_version': 'deck_mbb_projection.v1', 'run_id': root.name,
            'authority': 'public_narrative', 'source_narrative_ref': 'narrative_plan.json',
            'source_narrative_sha256': source_hash, 'source_revision': revision,
            'input_fingerprint': sha256_json({'narrative': source_hash, 'packages': refs}),
            'candidates': narrative.get('candidates') or [],
            'recommended_candidate_id': narrative.get('recommended_candidate_id') or None,
            'selected_candidate_id': narrative.get('selected_candidate_id') or None,
            'selection_decision_ref': narrative.get('selection_decision_ref') or '',
            'narrative_pages': narrative.get('beats') or narrative.get('pages') or narrative.get('page_jobs') or [],
            'package_refs': refs,
        }
        result['projection_sha256'] = sha256_json(result)
        assert_v2('mbb_projection', result)
        # This is a disposable cache, never an input to planning or build.
        # Recompute on every compatibility read; edits to this file have no authority.
        path = safe_run_path(root, PROJECTION_PATH.as_posix())
        data = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if path.is_file() and path.read_text() == data:
            return result
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw = tempfile.mkstemp(prefix='.narrative-projection-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(data)
            os.replace(raw, path)
        finally:
            Path(raw).unlink(missing_ok=True)
        return result


def refresh_requested_projection(root: Path) -> None:
    if (root / PROJECTION_PATH).exists() and native_authority(root):
        project_narrative_mbb(root)
