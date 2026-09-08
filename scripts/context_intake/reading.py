"""Preserve extraction coverage; summaries never constitute a completed read."""
from copy import deepcopy
import hashlib
from pathlib import Path
import re


def reading_errors(source):
    reading = source.get('reading')
    extraction = source.get('extraction')
    if reading is not None and not isinstance(reading,dict):
        return ['reading must be an object']
    if extraction is not None and not isinstance(extraction,dict):
        return ['extraction must be an object']
    if extraction:
        count, total = extraction.get('read_units'), extraction.get('total_units')
        if not isinstance(count,int) or not isinstance(total,int) or count < 0 or total < count:
            return ['extraction unit counts are invalid']
        if extraction.get('status') == 'complete' and (count != total or total == 0 or extraction.get('unread_regions')):
            return ['complete extraction cannot contain unread or missing units']
    if reading:
        if reading.get('coverage') not in {'full','partial','failed','empty','legacy_unknown'}:
            return ['reading coverage is invalid']
        if any(not isinstance(reading.get(k),list) for k in ('read_ranges','unread_ranges','failures')):
            return ['reading requires explicit read_ranges/unread_ranges/failures arrays']
        if reading.get('coverage') == 'full' and (not reading['read_ranges'] or reading['unread_ranges'] or reading['failures']):
            return ['full reading cannot contain missing ranges or failures']
    sha = source.get('file_sha256',source.get('sha256'))
    if sha is not None and not re.fullmatch('[a-f0-9]{64}',str(sha)):
        return ['source SHA256 is invalid']
    if (reading and reading.get('coverage')=='full' or extraction and extraction.get('status')=='complete') and not sha:
        return ['complete reading requires source SHA256']
    return []


def preserved_reading(source):
    if source.get('reading'):
        return deepcopy(source['reading'])
    if source.get('extraction'):
        value=source['extraction']
        return {'method':value['method'],'coverage':{'complete':'full','partial':'partial','failed':'failed'}[value['status']],
                'read_ranges':[{'start_unit':0,'end_unit':value['read_units'],'snapshot_ref':value['snapshot_ref']}] if value['read_units'] else [],
                'unread_ranges':[{'description':x,'critical':True} for x in value['unread_regions']], 'failures':[],
                'read_units':value['read_units'],'total_units':value['total_units'],'tool_ref':value['tool_ref']}
    return {'method':'legacy_unattested','coverage':'legacy_unknown','read_ranges':[],
            'unread_ranges':[{'description':'Legacy extraction has no attested reading coverage','critical':True}], 'failures':[]}


def verify_source_bytes(source, existing=None):
    """Only inspect the source explicitly authorized by registration or this pack."""
    sha=source.get('file_sha256',source.get('sha256'))
    path=str((existing or {}).get('path') or (existing or {}).get('origin_path') or source.get('origin_path') or source.get('origin_ref') or '')
    if not sha:
        return
    if source.get('extraction'):
        snapshot=Path(source['extraction']['snapshot_ref']).expanduser()
        if not snapshot.is_file() or snapshot.stat().st_size == 0:
            raise ValueError('Host extraction snapshot is missing or empty')
    if path.startswith(('https://','http://')):
        # A remote source needs its captured extraction snapshot; never fetch here.
        path=str((source.get('extraction') or {}).get('snapshot_ref') or '')
    target=Path(path).expanduser() if path else None
    if not target or not target.is_file():
        raise ValueError('Hashed context source must have an available authorized local file/snapshot')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
        raise ValueError('Context source SHA256 differs from actual source bytes')
    oldsha=(existing or {}).get('sha256',(existing or {}).get('file_sha256'))
    if oldsha and oldsha!=sha:
        raise ValueError('Registered context source version changed; register the new source version first')


def reading_blockers(context):
    blockers=[]
    for source in context.get('sources',[]):
        reading=source.get('reading')
        # Historical manifests without coverage are not retroactively rewritten.
        # Every new/imported source receives explicit coverage, including legacy.
        if not isinstance(reading,dict):
            continue
        if reading.get('coverage')=='full':
            continue
        unread=reading.get('unread_ranges') or []
        blockers.append({'code':'context_reading_incomplete','conflict_id':'reading:'+str(source.get('source_id')), 'source_id':source.get('source_id'),
                         'coverage':reading.get('coverage','unknown'),'unread_ranges':deepcopy(unread),
                         'failures':deepcopy(reading.get('failures',[])),
                         'required_action':'Read missing source ranges and import a version-bound context pack'})
    return blockers
