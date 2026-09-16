"""Step-specific, observed environment diagnostics; never a content-quality verdict."""
from __future__ import annotations
from importlib import resources, metadata
from pathlib import Path
import subprocess
import sys
from . import __version__
from .pipeline import executable, NeedsTool

STEPS=('compose','blueprint','compile','render','view','export')

def diagnose(step, *, fonts=(), host_imagegen=False):
    if step not in STEPS:
        raise ValueError('unknown diagnostic step')
    checks=[]
    def add(name,status,detail,required=True):
        checks.append({'name':name,'status':status,'detail':detail,'required':required})
    add('python','ready' if (3,12)<=sys.version_info[:2]<(3,14) else 'unavailable',{'executable':sys.executable,'version':sys.version.split()[0]})
    root=resources.files('deck_master')
    required=['resources/contracts/document.v1.schema.json']
    if step=='compose':required+=['resources/skill/SKILL.md','resources/skill/references/content-methods.md']
    if step=='view':required+=['resources/static/index.html','resources/static/app.js','resources/static/style.css']
    for resource in required:
        add(resource,'ready' if root.joinpath(resource).is_file() else 'unavailable',str(root.joinpath(resource)))
    if step=='blueprint':
        add('codex_imagegen','host_reported_available' if host_imagegen else 'awaiting_host',{'evidence':'caller report only; no image call performed','next_action':'Host must inspect its available ImageGen tool'})
    if step=='compile':
        for package in ('python-pptx','Pillow'):
            try:add(package,'ready',metadata.version(package))
            except metadata.PackageNotFoundError:add(package,'unavailable','not installed')
    if step=='render':
        for name in ('soffice','pdftoppm','rsvg-convert'):
            try:
                path=executable(name)
                flag='-v' if name=='pdftoppm' else '--version'
                result=subprocess.run([path,flag],capture_output=True,text=True,timeout=15)
                add(name,'ready' if result.returncode==0 else 'unavailable',{'path':path,'version':(result.stdout+result.stderr).strip()[:1000]})
            except (NeedsTool,OSError,subprocess.TimeoutExpired) as exc:add(name,'unavailable',str(exc))
    for font in fonts if step in ('compile','render') else ():
        try:
            result=subprocess.run([executable('fc-match'),'-f','%{family}\n%{file}',font],capture_output=True,text=True,timeout=10,check=True)
            family,path=result.stdout.split('\n',1)
            exact=font.casefold() in [name.strip().casefold() for name in family.split(',')]
            add('font:'+font,'ready' if exact and Path(path).is_file() else 'unavailable',{'matched_family':family,'file':path,'requested':font})
        except (NeedsTool,OSError,ValueError,subprocess.SubprocessError) as exc:add('font:'+font,'unavailable',str(exc))
    release=None
    for parent in Path(str(root)).parents:
        if parent.name=='venv' and (parent.parent/'release.json').is_file():
            import json
            record=json.loads((parent.parent/'release.json').read_text())
            release={key:record.get(key) for key in ('release_id','source_sha','source_dirty','wheel_sha256')}
            break
    status='needs_tool' if any(c['required'] and c['status']=='unavailable' for c in checks) else ('awaiting_host' if any(c['status']=='awaiting_host' for c in checks) else 'ready')
    return {'status':status,'step':step,'package_version':__version__,'release':release,'module_path':str(root),'checks':checks,'professional_evidence':'not_evaluated','desktop_editing':'not_evaluated'}
