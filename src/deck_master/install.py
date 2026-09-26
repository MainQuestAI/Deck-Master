"""Isolated candidate releases; activation only inside an explicit prefix.

v1.1 adds the Codex skill chain (§8): each release carries ``skill/deck-master``
extracted from its wheel, ``install activate`` establishes one managed link at
``$CODEX_HOME/skills/deck-master`` → ``<prefix>/.deck-master/current/skill/deck-master``,
rollback retires the link when the previous release predates skills, and a
one-time migration moves the legacy companion layout aside without deleting
anything. The installer never touches third-party skills or config.toml.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import fcntl, hashlib, json, os, re, subprocess, sys, uuid, zipfile

from .errors import HostSkillConflict

@contextmanager
def _locked(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'install.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)

def _replace_link(path,target):
    temp=path.parent/('.'+path.name+'-'+uuid.uuid4().hex)
    try:
        temp.symlink_to(target)
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)

def _release(root,release_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',release_id):raise ValueError('invalid release id')
    path=root/'releases'/release_id
    if path.is_symlink():raise ValueError('release directory cannot be a symlink')
    return path

def _codex_skill_root():
    home=os.environ.get('CODEX_HOME') or os.path.join(os.path.expanduser('~'),'.codex')
    return Path(home)/'skills'

def _managed_target(root):
    """The one link target this installer owns (always through current)."""
    return str(root/'current'/'skill'/'deck-master')

def _link_state(root):
    """managed | absent | conflict(path kind) for the Codex skill entry."""
    link=_codex_skill_root()/'deck-master'
    if link.is_symlink():
        return ('managed' if os.readlink(link)==_managed_target(root) else 'foreign', str(link))
    if link.exists():
        return ('occupied', str(link))
    return ('absent', str(link))

def _extract_skill(release: Path, wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names=[n for n in archive.namelist()
               if n.startswith('deck_master/resources/skill/') and not n.endswith('/')]
        if not any(n=='deck_master/resources/skill/SKILL.md' for n in names):
            raise ValueError('candidate wheel carries no deck-master skill')
        skill_root=release/'skill'/'deck-master'
        skill_root.mkdir(parents=True,exist_ok=True)
        for name in names:
            relative=name[len('deck_master/resources/skill/'):]
            target=skill_root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(name))

def install_candidate(prefix, manifest_path):
    manifest_path=Path(manifest_path).resolve();manifest=json.loads(manifest_path.read_text())
    name=manifest['wheel']
    if Path(name).name!=name:raise ValueError('wheel must be beside manifest')
    wheel=manifest_path.parent/name
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=manifest['wheel_sha256']:raise ValueError('wheel hash mismatch')
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):
        release=_release(root,manifest['release_id']);release.mkdir(parents=True,exist_ok=False)
        record={**manifest,'status':'installing','document_schema':'deck_document.v1'}
        (release/'release.json').write_text(json.dumps(record,indent=2))
        try:
            _extract_skill(release,wheel)
            subprocess.run([sys.executable,'-m','venv',str(release/'venv')],check=True,capture_output=True,timeout=120)
            python=release/'venv/bin/python'
            subprocess.run([str(python),'-I','-m','pip','install',str(wheel)],check=True,capture_output=True,timeout=300)
            probe=subprocess.run([str(python),'-I','-m','deck_master','doctor','--step','compile'],check=True,capture_output=True,text=True,timeout=60)
            info=json.loads(probe.stdout)
            if not Path(info['module_path']).is_relative_to(release):raise RuntimeError('candidate borrowed external module')
            for step in ('compose','view'):
                subprocess.run([str(python),'-I','-m','deck_master','doctor','--step',step],check=True,capture_output=True,timeout=60)
            # Compile a real native shape in the isolated interpreter.
            code='from pathlib import Path; from deck_master.compiler import compile_deck,CompileOptions,SvgInput; p=Path("probe.svg"); p.write_text(\'<svg viewBox="0 0 10 10"><rect width="10" height="10" fill="#123456"/></svg>\'); compile_deck([SvgInput("probe",p)],CompileOptions(),Path("probe-output"))'
            subprocess.run([str(python),'-I','-c',code],cwd=release,check=True,capture_output=True,timeout=60)
            render_probe=subprocess.run([str(python),'-I','-m','deck_master','doctor','--step','render'],check=True,capture_output=True,text=True,timeout=60)
            subprocess.run([str(python),'-I','-c','from deck_master.pipeline import render_deck; render_deck("probe-output/deck.pptx","probe-rendered",fonts={})'],cwd=release,check=True,capture_output=True,timeout=120)
            record.update(status='candidate_ready',probe=info,render_probe=json.loads(render_probe.stdout),
                          skill_sha256=hashlib.sha256((release/'skill'/'deck-master'/'SKILL.md').read_bytes()).hexdigest())
        except Exception as exc:
            record.update(status='failed',error=str(exc))
            (release/'release.json').write_text(json.dumps(record,indent=2));raise
        (release/'release.json').write_text(json.dumps(record,indent=2))
        return {'status':'candidate_ready','release_id':manifest['release_id'],'release':str(release),'activated':False}

# ---------------------------------------------------------------------------
# Legacy companion migration (§8.3): move the old real-directory ``current``
# aside and prune only the dangling deck-* links that pointed into it.

def _migrate_legacy_companion(root, *, dry_run=False):
    report={'migrated':False,'moved':None,'removed_links':[],'skipped_entries':[]}
    current=root/'current'
    if not (current.is_dir() and not current.is_symlink()):
        return report
    entries=sorted(current.iterdir())
    manifest=current/'companion-manifest.json'
    only_manifest=[e.name for e in entries]==['companion-manifest.json'] and manifest.is_file()
    if not only_manifest:
        raise HostSkillConflict(
            str(current),
            'current is a real directory with unexpected contents; refusing to treat it as a '
            'legacy companion layout — resolve it manually')
    try:
        payload=json.loads(manifest.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HostSkillConflict(str(manifest), f'companion manifest is unreadable: {exc}') from exc
    skill_rows=payload.get('skills') if isinstance(payload,dict) else None
    deck_rows=[row for row in skill_rows if isinstance(row,dict) and
               isinstance(row.get('name'),str) and row['name'].startswith('deck-')] \
        if isinstance(skill_rows,list) else []
    if (not isinstance(payload,dict) or
            payload.get('schema_version') != 'deck_master_companion_manifest.v3' or
            not any(row['name']=='deck-master' for row in deck_rows) or
            not all(row.get('adoption_policy')=='bundled_symlink_only' for row in deck_rows)):
        raise HostSkillConflict(
            str(manifest),
            'companion manifest does not match deck_master_companion_manifest.v3 with '
            'bundled_symlink_only on its deck skill rows; refusing to migrate')
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    destination=root/f'legacy-companion-{timestamp}'
    suffix=0
    while destination.exists():
        suffix+=1
        destination=root/f'legacy-companion-{timestamp}-{suffix}'
    if not dry_run:
        os.rename(current,destination)
    report.update(migrated=True,moved={'from':str(current),'to':str(destination)})
    skill_root=_codex_skill_root()
    prefix=str(root/'current'/'skills')+'/'
    if skill_root.is_dir():
        for entry in sorted(skill_root.iterdir()):
            if entry.is_symlink() and re.fullmatch(r'deck-.*',entry.name) \
                    and os.readlink(entry).startswith(prefix):
                if not dry_run:
                    entry.unlink()
                report['removed_links'].append(entry.name)
            else:
                report['skipped_entries'].append(entry.name)
    return report

def _ensure_host_skill_link(root):
    """Create or repair the managed Codex link; refuse anything else."""
    state,path=_link_state(root)
    if state in ('managed','absent'):
        link=Path(path)
        if not link.is_symlink() or os.readlink(link)!=_managed_target(root):
            link.parent.mkdir(parents=True,exist_ok=True)
            _replace_link(link,_managed_target(root))
        return {'host_skill':'registered','skill_link':str(link),'skill_target':_managed_target(root)}
    raise HostSkillConflict(
        path,
        f'the Codex skill path is occupied by a {"real directory or file" if state=="occupied" else "foreign symlink"}; '
        'remove or rename it before activating')

def _retire_host_skill_link(root):
    """Drop the managed link only when it points at this installation."""
    state,path=_link_state(root)
    if state=='managed':
        Path(path).unlink()
    return {'host_skill':'host_skill_unregistered','skill_link':path if state!='absent' else None}

def _sync_host_skill(root, *, register: bool):
    """After a release switch: keep the link valid, retire it without a skill."""
    skill_marker=root/'current'/'skill'/'deck-master'/'SKILL.md'
    if not skill_marker.is_file():
        return _retire_host_skill_link(root)
    if not register:
        state,path=_link_state(root)
        return {'host_skill':'registered' if state=='managed' else 'host_unregistered',
                'skill_link':path if state!='absent' else None}
    return _ensure_host_skill_link(root)

def _preflight_host_skill(root, *, removed_links=()):
    state,path=_link_state(root)
    if state in ('occupied','foreign') and 'deck-master' not in removed_links:
        raise HostSkillConflict(path, 'the Codex skill path belongs to another installation or user; current is unchanged')
    parent=_codex_skill_root()
    while not parent.exists() and parent != parent.parent:
        parent=parent.parent
    if not parent.is_dir():
        raise HostSkillConflict(str(parent), 'Codex skill parent is not a directory; current is unchanged')

def _checked_release(root, release_id):
    release=_release(root, release_id)
    record=json.loads((release/'release.json').read_text())
    if record.get('status')!='candidate_ready':
        raise ValueError('candidate checks incomplete')
    return release

def _activate_locked(root,release_id):
    release=_checked_release(root,release_id)
    current=root/'current';previous=root/'previous'
    for link in (current,previous):
        if link.exists() and not link.is_symlink():raise ValueError('refuse to replace user-owned path: '+str(link))
    launcher=root/'bin'/'deck-master'
    launcher_text='#!/bin/sh\nexec "$(dirname "$0")/../current/venv/bin/python" -I -m deck_master "$@"\n'
    launcher.parent.mkdir(exist_ok=True)
    if launcher.exists():
        if launcher.is_symlink() or launcher.read_text()!=launcher_text:raise ValueError('refuse to replace user-owned launcher')
    else:
        with launcher.open('x') as handle:handle.write(launcher_text)
        launcher.chmod(0o755)
    old=os.readlink(current) if current.is_symlink() else None
    target='releases/'+release_id
    if old==target:return {'status':'already_active','release_id':release_id}
    old_previous=os.readlink(previous) if previous.is_symlink() else None
    if old:_replace_link(previous,old)
    try:_replace_link(current,target)
    except Exception:
        if old_previous:_replace_link(previous,old_previous)
        else:previous.unlink(missing_ok=True)
        raise
    return {'status':'activated','release_id':release_id,'previous':old,'format_boundary':'Older binaries must not write unsupported Document schemas; restore a compatible project copy.'}

def activate(prefix,release_id,*,register_host=True):
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):
        _checked_release(root,release_id)
        migration=_migrate_legacy_companion(root,dry_run=True)
        if register_host:
            # Refuse before switching current: a conflict must not activate.
            _preflight_host_skill(root,removed_links=migration['removed_links'])
        previous=root/'previous'
        if previous.exists() and not previous.is_symlink():
            raise ValueError('refuse to replace user-owned path: '+str(previous))
        migration=_migrate_legacy_companion(root)
        result=_activate_locked(root,release_id)
        result['cli_active']=True
        result['migration']=migration
        registration=_sync_host_skill(root,register=register_host)
        result.update(registration)
        if registration.get('host_skill')=='registered':
            result['skill_release_id']=release_id
        return result

def rollback(prefix,*,register_host=True):
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):
        previous=root/'previous'
        if not previous.is_symlink():raise ValueError('no previous release')
        target=os.readlink(previous)
        if not target.startswith('releases/') or len(Path(target).parts)!=2:raise ValueError('invalid previous release')
        release=_checked_release(root,Path(target).name)
        if register_host and (release/'skill/deck-master/SKILL.md').is_file():
            _preflight_host_skill(root)
        result=_activate_locked(root,Path(target).name)
        registration=_sync_host_skill(root,register=register_host)
        result.update(registration)
        result['cli_active']=True
        if registration.get('host_skill')=='registered':
            result['skill_release_id']=Path(target).name
        return result
