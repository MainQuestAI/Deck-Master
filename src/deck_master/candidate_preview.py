"""Actual single-slide candidate checks, isolated from the current Document.

Caches are disposable and content/toolchain-bound. Adoption revalidates every
file and persists the check report via its normal operation receipt.
"""
from __future__ import annotations
import fcntl
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import tempfile
import threading
import zipfile
import xml.etree.ElementTree as ET

from . import candidates, icons, operations, pipeline
from .compiler import CompileOptions, SvgInput, compile_deck
from .compiler.svg import parse_svg
from .local_state import project_path
from .models import canonical_json_bytes
from .snapshots import load_snapshot
from .store import Store, _atomic_write_bytes

_LOCK=threading.Lock()
_JOBS={}
_EXECUTOR=ThreadPoolExecutor(max_workers=2,thread_name_prefix='candidate-preview')


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _context(project,candidate_id):
    store=Store(project_path(project));doc=load_snapshot(store)
    candidate,ref,task=candidates._lookup(candidates._records(store,doc),candidate_id)
    if candidate.get('stage')!='svg':icons.fail('candidate_id','actual single-page preview requires an SVG candidate')
    base=load_snapshot(store,candidate['base_revision']);entry=icons._entry(base,candidate['page_id'])
    artifact=store.read_object_json(candidate['result_ref']);data=store.read_object_bytes(artifact['file'])
    scope=icons.check_scope(store,doc,task,data)
    with tempfile.TemporaryDirectory(prefix='icon-context-',dir=store.staging_dir) as temp:
        assets=pipeline.page_asset_paths(store,base,entry,Path(temp))
        parsed=parse_svg(data,page_id=entry['page_id'],assets=assets)
        fonts=pipeline.resolve_fonts([parsed]);asset_hashes={k:_sha(v) for k,v in assets.items()}
    tools={}
    for name in ('soffice','pdftoppm','rsvg-convert'):
        path=Path(pipeline.executable(name)).resolve();stat=path.stat()
        tools[name]={'path':str(path),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
    compiler=Path(__file__).parent/'compiler'
    identity={'candidate_ref':ref,'page_ref':entry['page'],'blueprint_ref':entry['blueprint'],
              'canvas':base['design_context']['canvas'],'fonts':{k:_sha(v) for k,v in fonts.items()},'assets':asset_hashes,
              'tools':tools,'compiler':{p.name:_sha(p) for p in compiler.glob('*.py')},
              'preview_implementation':_sha(__file__),'pipeline':_sha(pipeline.__file__),
              'python_pptx':importlib.metadata.version('python-pptx')}
    key=icons.digest(identity)
    return store,doc,base,entry,candidate,task,data,scope,fonts,identity,key


def _folder(store):
    path=store.deck_root/'cache/candidate-previews';path.mkdir(parents=True,exist_ok=True);return path


def _cached(store,key,identity):
    folder=_folder(store)/key;path=folder/'report.json'
    if not path.exists():return None
    try:
        report=json.loads(path.read_text())
        if report['identity']!=identity or report['cache_key']!=key:return None
        if report['status'] not in ('ready','failed') or set(report['files']) != {'candidate.png','candidate.svg','candidate.pptx','readback.json'}:return None
        if report['candidate_ref']!=identity['candidate_ref']:return None
        if report['status']=='ready' and (report['native_check']!='pass' or report['readback']['status']!='pass'):return None
        for name,record in report['files'].items():
            if name not in ('candidate.png','candidate.svg','candidate.pptx','readback.json'):return None
            if _sha(folder/name)!=record['sha256']:return None
        return report
    except (OSError,ValueError,KeyError):return None


def _public(report):
    # Tool/font paths are internal cache identity, not browser/customer content.
    result={k:v for k,v in report.items() if k!='identity'}
    result['files']={n:{**v,'file':{'path':f".deckmaster/cache/candidate-previews/{report['cache_key']}/{n}",'sha256':v['sha256']},'url':f"/api/candidate-preview/file?cache_key={report['cache_key']}&name={n}"} for n,v in report['files'].items()}
    return result


def _generate(project,candidate_id,context):
    store,doc,base,entry,candidate,task,data,scope,fonts,identity,key=context
    folder=_folder(store);job=(str(store.project_root),key)
    try:
        # Cross-process serialization also isolates LibreOffice invocations.
        with (folder/'compile.lock').open('a+b') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            existing=_cached(store,key,identity)
            if existing and existing['status']=='ready':
                with _LOCK:_JOBS.pop(job,None)
                return
            with _LOCK:_JOBS[job]={'status':'running','cache_key':key}
            with tempfile.TemporaryDirectory(prefix='candidate-check-',dir=store.staging_dir) as tmp:
                work=Path(tmp);assets=pipeline.page_asset_paths(store,base,entry,work)
                path=work/'page.svg';path.write_bytes(data)
                parsed=parse_svg(data,page_id=entry['page_id'],assets=assets)
                canvas=base['design_context']['canvas']
                result=compile_deck([SvgInput(entry['page_id'],path)],CompileOptions(width_px=canvas['slide_width_in']*96,
                    height_px=canvas['slide_height_in']*96,fonts=fonts,assets={entry['page_id']:assets}),work/'compiled')
                renders=pipeline.render_deck(result.pptx_path,work/'rendered',fonts=fonts)
                if len(renders)!=1:raise ValueError('candidate rendering must return exactly one slide')
                readback=pipeline.readback(result.pptx_path,[parsed],[store.read_object_json(entry['page'])])
                ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
                with zipfile.ZipFile(result.pptx_path) as z:
                    xml=ET.fromstring(z.read('ppt/slides/slide1.xml'))
                    pictures=len(xml.findall('.//p:pic',ns));native=len(xml.findall('.//p:sp',ns))
                expected_pictures=sum(s['kind']=='image' for s in parsed['shapes'])
                native_ok=pictures==expected_pictures and native==sum(s['kind']!='image' for s in parsed['shapes'])
                final_context=_context(project,candidate_id)
                if final_context[-1]!=key:raise ValueError('candidate or toolchain changed during compilation; no result published')
                files={'candidate.png':Path(renders[0]).read_bytes(),'candidate.svg':data,'candidate.pptx':result.pptx_path.read_bytes(),
                       'readback.json':canonical_json_bytes(readback)}
                destination=folder/key;destination.mkdir(exist_ok=True)
                report={'schema_version':'candidate_preview.v1','status':'ready' if readback['status']=='pass' and native_ok else 'failed',
                        'cache_key':key,'candidate_id':candidate_id,'candidate_ref':identity['candidate_ref'],
                        'identity':identity,'scope_check':scope,'readback':readback,'native_shapes':native,'pictures':pictures,
                        'native_check':'pass' if native_ok else 'fail','visual_review':'not_evaluated','files':{}}
                for name,raw in files.items():
                    _atomic_write_bytes(destination/name,raw);report['files'][name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
                _atomic_write_bytes(destination/'report.json',canonical_json_bytes(report))
                with _LOCK:_JOBS.pop(job,None)
    except Exception as exc:
        with _LOCK:_JOBS[job]={'status':'needs_tool' if isinstance(exc,pipeline.NeedsTool) else 'failed','cache_key':key,
                              'error':{'code':'candidate_preview_failed','message':str(exc)}}


@operations.public
def request(project, *, candidate_id, retry=False, wait=True):
    try:context=_context(project,candidate_id)
    except pipeline.NeedsTool as exc:return {'status':'needs_tool','error':{'code':'needs_tool','message':str(exc)}}
    store=context[0];identity,key=context[-2:];cached=_cached(store,key,identity)
    if cached and (cached['status']=='ready' or not retry):return _public(cached)
    job=(str(store.project_root),key)
    with _LOCK:
        state=_JOBS.get(job)
        if state and (state['status'] in ('queued','running') or not retry):return dict(state)
        if sum(v['status'] in ('queued','running') for v in _JOBS.values()) >= 64:
            return {'status':'busy','cache_key':key,'retry_after_ms':2000}
        for old in list(_JOBS):
            if len(_JOBS) < 128: break
            if _JOBS[old]['status'] not in ('queued','running'): _JOBS.pop(old)
        _JOBS[job]={'status':'queued','cache_key':key}
    if wait:
        _generate(project,candidate_id,context);return status(project,candidate_id=candidate_id)
    _EXECUTOR.submit(_generate,project,candidate_id,context)
    return {'status':'queued','cache_key':key}


@operations.public
def status(project, *, candidate_id):
    try:context=_context(project,candidate_id)
    except pipeline.NeedsTool as exc:return {'status':'needs_tool','error':{'code':'needs_tool','message':str(exc)}}
    store=context[0];identity,key=context[-2:];cached=_cached(store,key,identity)
    if cached:return _public(cached)
    with _LOCK:return dict(_JOBS.get((str(store.project_root),key),{'status':'not_requested','cache_key':key}))


def require_ready(project,candidate_id):
    result=status(project,candidate_id=candidate_id)
    if result['status']!='ready' or result.get('scope_check',{}).get('status')!='pass' or result.get('native_check')!='pass':
        raise operations.OperationError('icon_preview_required','candidate_id','run actual candidate PPT checks before adopting this icon trial',http_status=409)
    return result


def freeze_check(store,candidate_id):
    """Adoption proof survives cache eviction and engineering bundle recovery."""
    report=require_ready(store.project_root,candidate_id)
    files={}
    for name,record in report['files'].items():
        raw,_=file_bytes(store.project_root,cache_key=report['cache_key'],name=name)
        files[name]={'file':store.put_blob(raw,ext=name.rsplit('.',1)[-1]),'bytes':record['bytes']}
    return store.put_json_object({**report,'files':files})


@operations.public
def file_bytes(project, *, cache_key, name):
    if not re_key(cache_key) or name not in ('candidate.png','candidate.svg','candidate.pptx','readback.json'):icons.fail('file','unknown preview file')
    store=Store(project_path(project));folder=_folder(store)/cache_key
    try:report=json.loads((folder/'report.json').read_text())
    except (OSError,ValueError):icons.fail('file','preview is not available')
    context=_context(project,report['candidate_id'])
    if context[-1]!=cache_key or not _cached(store,cache_key,context[-2]):icons.fail('file','preview basis or bytes changed')
    media={'candidate.png':'image/png','candidate.svg':'image/svg+xml','candidate.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','readback.json':'application/json'}
    return (folder/name).read_bytes(),media[name]


def re_key(value):return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)
