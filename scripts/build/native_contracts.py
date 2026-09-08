"""Materialize native public contracts from observed capabilities and pinned inputs."""
from __future__ import annotations
import json
from pathlib import Path
from native_pptx.contracts import SCHEMA_DIR, ContractError, sha256_file, sha256_json


def validate_contract(kind: str, payload: dict) -> None:
    from jsonschema import Draft202012Validator, FormatChecker
    name = {'task_readiness':'task-readiness', 'native_compile_request':'native-compile-request'}[kind]
    Draft202012Validator(json.loads((SCHEMA_DIR / f'{name}.v1.schema.json').read_text()),format_checker=FormatChecker()).validate(payload)


def _write(path: Path, payload: dict) -> None:
    from workflow.actions import _atomic_json
    _atomic_json(path,payload)


def _ref(root: Path, path: Path) -> dict:
    resolved=path.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ContractError('native contract input reference is missing or outside run')
    return {'path':resolved.relative_to(root.resolve()).as_posix(),'sha256':sha256_file(resolved)}


def write_task_readiness(root: Path, probe: dict, *, task_kind: str) -> dict:
    """An awaiting host action is not evidence that its tool is unavailable."""
    root=Path(root).resolve()
    path=root/'build/probes'/f"{sha256_json(probe)}.json"
    _write(path,probe)
    evidence=[_ref(root,path)]
    checked=probe.get('checked_at')
    components=[]
    for capability,check,source in [('compiler','compile_smoke','bundled_probe'),('renderer','render_smoke','system_probe'),('fonts','fonts','system_probe'),('svg_renderer','rsvg_convert','system_probe')]:
        observed=(probe.get('checks') or {}).get(check)
        state='unknown' if not observed else ('verified' if observed.get('status')=='verified' else 'missing')
        components.append({'capability_id':'deck_native.'+capability,'requirement':'required','status':state,'source':source if observed else 'not_checked','checked_at':checked if observed else None,'evidence_refs':evidence if observed else []})
    hosts={'image_blueprint_build':['image_generation','image_read','svg_authoring'],'direct_svg_build':['svg_authoring']}.get(task_kind,[])
    for capability in hosts:
        components.append({'capability_id':'host.'+capability,'requirement':'required','status':'unknown','source':'not_checked','checked_at':None,'evidence_refs':[]})
    missing=[c['capability_id'] for c in components if c['status']=='missing']
    unknown=[c['capability_id'] for c in components if c['status']=='unknown']
    result={'schema_version':'deck_task_readiness.v1','run_id':root.name,'engine_id':'deck_native','task_kind':task_kind,'status':'blocked' if missing else ('unknown' if unknown else 'ready'),'required_missing':missing,'required_unknown':unknown,'optional_unavailable':[],'components':components,'next_action':'Repair missing runtime capabilities and rerun the probe.' if missing else ('Observe the required host tools; continue the issued task when available.' if unknown else None)}
    validate_contract('task_readiness',result)
    _write(root/'build/task_readiness.json',result)
    return result


def write_compile_request(root: Path, *, revision: str, fingerprint: str, packages: list[dict], scenes: list[dict], locks: dict[str,dict], svg_paths: dict[str,Path], assets: dict[str,dict[str,Path]], native_canvas: bool) -> dict:
    if not native_canvas:
        raise ContractError('legacy HD uses its existing input protocol, not the native contain contract')
    from workflow.actions import revision_input_path, _manifest
    from high_density.scene import canonical_scene_path, scene_path
    from native_pptx.api import ENGINE_VERSION, SVG_SUBSET_VERSION
    from native_pptx.pptx import _svg_elements, SLIDE_HEIGHT_IN
    from xml.etree import ElementTree
    root=Path(root).resolve()
    pages=[]; fonts=set(); dimensions=set()
    folder=root/'build/native_compile_inputs'/fingerprint
    for package,scene in zip(packages,scenes):
        page=str(package['page_id']);svg=svg_paths[page]
        document=ElementTree.parse(svg).getroot()
        viewbox=[float(n) for n in str(document.get('viewBox') or '').replace(',',' ').split()]
        if len(viewbox)!=4 or min(viewbox[2:])<=0:
            raise ContractError('compile request requires a valid SVG viewBox')
        dimensions.add(tuple(viewbox[2:]))
        for element in _svg_elements(svg,scene):
            if element.get('kind')=='text':
                fonts.add(str((element.get('style') or {}).get('font_family') or 'Arial'))
        scene_file=revision_input_path(root,canonical_scene_path(root,page))
        if not scene_file.exists():scene_file=revision_input_path(root,scene_path(root,page))
        lock_file=revision_input_path(root,root/'high_density_build/content_locks'/f'{page}.content_lock.json')
        if not lock_file.exists():lock_file=revision_input_path(root,root/'high_density_build/content_locks'/f'{page}.json')
        asset_file=folder/f'{page}_assets.json'
        _write(asset_file,{'page_id':page,'build_revision':revision,'bindings':package.get('asset_bindings',[]),'assets':{key:_ref(root,revision_input_path(root,path)) for key,path in assets.get(page,{}).items()}})
        if locks[page].get('enrichment',{}).get('framework')!='native_narrative':
            raise ContractError('legacy content cannot use the native contain request')
        if revision=='initial':raise ContractError('native compile requires committed SVG and Scene provenance')
        manifest=_manifest(root,revision)
        svg_hash=sha256_file(svg);scene_hash=sha256_json(scene)
        if not any(r.get('output_sha256')==svg_hash and r.get('scene_sha256')==scene_hash and page in r.get('scope_pages',[]) for r in manifest.get('receipts',{}).values()):
            raise ContractError('native compile provenance does not match the pinned SVG/Scene')
        approval_file=root/'build/revisions'/revision/'revision_manifest.json'
        pages.append({'page_id':page,'order':int(package['order']),'svg_ref':_ref(root,svg),'scene_ref':_ref(root,scene_file),'content_lock_ref':_ref(root,lock_file),'asset_manifest_ref':_ref(root,asset_file),'approval_ref':_ref(root,approval_file)})
    # Each native SVG is uniformly mapped into this shared 16:9 normalized plane.
    # Source per-page viewBoxes remain in the hash-bound SVG references.
    width,height=next(iter(dimensions)) if len(dimensions)==1 else (1672,1672*9/16)
    result={'schema_version':'deck_native_compile_request.v1','run_id':root.name,'build_revision':revision,'engine_id':'deck_native','engine_version':ENGINE_VERSION,'subset_version':SVG_SUBSET_VERSION,'input_fingerprint':fingerprint,'canvas':{'viewbox_width':width,'viewbox_height':height,'slide_width_pt':960,'slide_height_pt':SLIDE_HEIGHT_IN*72,'mapping':'contain'},'font_families':sorted(fonts) or ['Arial'],'pages':pages}
    validate_contract('native_compile_request',result)
    _write(root/'build/native_compile_request.json',result)
    return result
