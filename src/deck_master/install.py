"""Isolated candidate releases; activation only inside an explicit prefix."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import fcntl, hashlib, json, os, re, subprocess, sys, uuid

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
            record.update(status='candidate_ready',probe=info,render_probe=json.loads(render_probe.stdout))
        except Exception as exc:
            record.update(status='failed',error=str(exc))
            (release/'release.json').write_text(json.dumps(record,indent=2));raise
        (release/'release.json').write_text(json.dumps(record,indent=2))
        return {'status':'candidate_ready','release_id':manifest['release_id'],'release':str(release),'activated':False}

def _activate_locked(root,release_id):
    release=_release(root,release_id);record=json.loads((release/'release.json').read_text())
    if record.get('status')!='candidate_ready':raise ValueError('candidate checks incomplete')
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

def activate(prefix,release_id):
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):return _activate_locked(root,release_id)

def rollback(prefix):
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):
        previous=root/'previous'
        if not previous.is_symlink():raise ValueError('no previous release')
        target=os.readlink(previous)
        if not target.startswith('releases/') or len(Path(target).parts)!=2:raise ValueError('invalid previous release')
        return _activate_locked(root,Path(target).name)
