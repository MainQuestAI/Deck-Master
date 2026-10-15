"""Isolated candidate releases; activation only inside an explicit prefix.

RC3 carries four public entries under ``skill/<name>``. Activation registers
all four ``$CODEX_HOME/skills/<name>`` links through the same release current pointer,
rollback retires the link when the previous release predates skills, and a
one-time migration moves the legacy companion layout aside without deleting
anything. The installer never touches third-party skills or config.toml.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import fcntl, hashlib, json, os, re, stat, subprocess, sys, uuid, zipfile

from .errors import HostSkillConflict

PUBLIC_SKILLS = ('deck-master', 'deck-content', 'deck-design', 'deck-review')
_METHOD_INVENTORY = 'deck_master/resources/method-inventory.json'

@contextmanager
def _locked(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'install.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)

# Only active inside the installation lock; never persisted across processes.
_transaction = ContextVar('installation_transaction', default=None)


def _identity(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


class _Undo:
    def __init__(self):
        self.actions = []
        self.backups = []

    def record(self, path, expected, restore):
        parent = path.parent.stat()
        parent_identity = (parent.st_dev, parent.st_ino)
        def undo():
            parent_now = path.parent.stat()
            if (parent_now.st_dev, parent_now.st_ino) != parent_identity:
                raise RuntimeError('parent changed externally; refusing compensation')
            actual = _identity(path)
            if actual != expected:
                raise RuntimeError('path changed externally; refusing compensation')
            restore()
        self.actions.append((path, undo))

    def compensate(self, original):
        failures = []
        for path, undo in reversed(self.actions):
            try:
                undo()
            except Exception as exc:
                failures.append(f'{path}: {exc}')
        if failures:
            raise RuntimeError(f'installation failed: {original}; compensation incomplete: '
                               + '; '.join(failures) + '; backups: ' + ', '.join(self.backups)) from original


@contextmanager
def _compensated():
    transaction = _Undo()
    token = _transaction.set(transaction)
    try:
        yield
    except Exception as exc:
        # Undo operations must not add new actions to the log.
        _transaction.reset(token)
        token = None
        transaction.compensate(exc)
        raise
    finally:
        if token is not None:
            _transaction.reset(token)


def _mkdir(path):
    if path.is_dir():
        return
    _mkdir(path.parent)
    path.mkdir()
    if transaction := _transaction.get():
        transaction.record(path, _identity(path), path.rmdir)


def _unlink(path):
    target = os.readlink(path)
    path.unlink()
    if transaction := _transaction.get():
        transaction.record(path, None, lambda: path.symlink_to(target))


def _move(source, destination):
    if _identity(destination) is not None:
        raise ValueError('migration backup occupied: ' + str(destination))
    os.rename(source, destination)
    if transaction := _transaction.get():
        def restore():
            if _identity(source) is not None:
                raise RuntimeError(f'original location occupied: {source}')
            os.rename(destination, source)
        transaction.backups.append(str(destination))
        transaction.record(destination, _identity(destination), restore)


def _replace_link(path,target):
    temp=path.parent/('.'+path.name+'-'+uuid.uuid4().hex)
    old = os.readlink(path) if path.is_symlink() else None
    if _identity(path) is not None and old is None:
        raise ValueError('refuse to replace occupied path: ' + str(path))
    try:
        temp.symlink_to(target)
        os.replace(temp,path)
        if transaction := _transaction.get():
            def restore():
                if old is None:
                    path.unlink()
                else:
                    _replace_link(path, old)
            transaction.record(path, _identity(path), restore)
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

def _managed_target(root, name='deck-master'):
    """Only links through this installation's current pointer are managed."""
    return str(root / 'current' / 'skill' / name)


def _link_state(root, name='deck-master'):
    link = _codex_skill_root() / name
    if link.is_symlink():
        return ('managed' if os.readlink(link) == _managed_target(root, name) else 'foreign', str(link))
    if link.exists():
        return ('occupied', str(link))
    return ('absent', str(link))


def _wheel_skills(archive):
    """Validate the whole Skill namespace before extracting any candidate file."""
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError('duplicate wheel members')
    try:
        inventory = json.loads(archive.read(_METHOD_INVENTORY))
    except (KeyError, ValueError) as exc:
        raise ValueError('candidate wheel lacks a readable strict method inventory') from exc
    if inventory.get('schema_version') != 'method_resource_inventory.v1' or inventory.get('public_skills') != list(PUBLIC_SKILLS):
        raise ValueError('unsupported candidate Skill inventory')
    if set(inventory.get('generated_exceptions', {})) != {_METHOD_INVENTORY}:
        raise ValueError('unknown generated method exception')
    rows = inventory.get('files', {})
    from .method_resources import RELATIVE_PATHS
    expected_sources = {'skills/RESOLVER.md'}
    expected_sources.update(f'skills/{skill}/{name}' for skill in PUBLIC_SKILLS
                            for name in ('SKILL.md', 'agents/openai.yaml'))
    expected_sources.update('skills/deck-master/' + relative
                            for relative in (*RELATIVE_PATHS.values(), 'references/installation.md'))
    if {row.get('canonical_source') for row in rows.values()} != expected_sources:
        raise ValueError('unknown or missing canonical source in candidate inventory')
    actual = {name for name in names if not name.endswith('/') and
              (name.startswith('deck_master/resources/skill/') or name.startswith('deck_master/resources/skills/'))}
    if set(rows) != actual:
        raise ValueError('wheel has unknown or missing canonical Skill files')
    extracted = {}
    sources = set()
    for name, row in rows.items():
        if name.startswith('deck_master/resources/skill/'):
            relative = 'deck-master/' + name.removeprefix('deck_master/resources/skill/')
        else:
            relative = name.removeprefix('deck_master/resources/skills/')
        parts = Path(relative).parts
        if not parts or any(part in ('.', '..') for part in parts) or Path(relative).is_absolute():
            raise ValueError('invalid Skill resource path')
        if relative == 'RESOLVER.md':
            canonical = 'skills/RESOLVER.md'
        elif parts[0] in PUBLIC_SKILLS and len(parts) > 1:
            canonical = 'skills/' + relative
            if parts[0] != 'deck-master' and (len(parts) > 3 or '/references/' in relative):
                raise ValueError('shared methods must not be copied into other Skills')
        else:
            raise ValueError('unknown canonical Skill resource')
        if row.get('canonical_source') != canonical or canonical in sources:
            raise ValueError('canonical Skill source mapping mismatch')
        sources.add(canonical)
        raw = archive.read(name)
        if hashlib.sha256(raw).hexdigest() != row.get('sha256'):
            raise ValueError('candidate method bytes differ from inventory: ' + name)
        extracted[relative] = raw
    for skill in PUBLIC_SKILLS:
        for required in ('SKILL.md', 'agents/openai.yaml'):
            if f'{skill}/{required}' not in extracted:
                raise ValueError('candidate missing public Skill resource: ' + skill + '/' + required)
    return inventory, extracted


def _extract_skill(release: Path, wheel: Path) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        inventory, extracted = _wheel_skills(archive)
    # The fresh release is private until candidate_ready and activation.
    for relative, raw in extracted.items():
        target = release / 'skill' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (release / 'method-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    return inventory


def _installed_resource_paths(release, inventory):
    rows = []
    for wheel_path, row in inventory['files'].items():
        if wheel_path.startswith('deck_master/resources/skill/'):
            extracted = release / 'skill/deck-master' / wheel_path.removeprefix('deck_master/resources/skill/')
        else:
            extracted = release / 'skill' / wheel_path.removeprefix('deck_master/resources/skills/')
        rows.append({**row, 'wheel_path': wheel_path, 'host_path': str(extracted),
                     'package_relative_path': wheel_path})
    return rows


def _verify_installed_resources(python, release, inventory, version):
    """Ask the isolated interpreter for its actual resource roots and bytes."""
    code = '''import hashlib,json,importlib.metadata
from pathlib import Path
import deck_master
root=Path(deck_master.__file__).resolve().parent
paths=json.loads(__import__('sys').argv[1])
print(json.dumps({'version':deck_master.__version__,'metadata_version':importlib.metadata.version('deck-master'),
 'module_path':str(root/'__init__.py'),
 'files':{p:{'path':str(root.parent/p),'sha256':hashlib.sha256((root.parent/p).read_bytes()).hexdigest()} for p in paths}}))'''
    result = subprocess.run([str(python), '-I', '-c', code, json.dumps(list(inventory['files']))],
                            check=True, capture_output=True, text=True, timeout=60)
    actual = json.loads(result.stdout)
    if (actual['version'] != version or actual['metadata_version'] != version
            or not Path(actual['module_path']).is_relative_to(release)):
        raise ValueError('candidate version or module origin differs from isolated release')
    rows = _installed_resource_paths(release, inventory)
    for row in rows:
        installed = actual['files'][row['wheel_path']]
        if not Path(installed['path']).is_relative_to(release) or installed['sha256'] != row['sha256']:
            raise ValueError('installed method differs from canonical wheel bytes: ' + row['wheel_path'])
        if hashlib.sha256(Path(row['host_path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('extracted Host method differs from canonical wheel bytes: ' + row['host_path'])
        row['installed_package_path'] = installed['path']
    return rows

def install_candidate(prefix, manifest_path):
    manifest_path=Path(manifest_path).resolve();manifest=json.loads(manifest_path.read_text())
    name=manifest['wheel']
    if Path(name).name!=name:raise ValueError('wheel must be beside manifest')
    wheel=manifest_path.parent/name
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=manifest['wheel_sha256']:raise ValueError('wheel hash mismatch')
    with zipfile.ZipFile(wheel) as archive:
        actual_files = {name: hashlib.sha256(archive.read(name)).hexdigest()
                        for name in archive.namelist() if not name.endswith('/')}
        if actual_files != manifest.get('files'):
            raise ValueError('release file inventory differs from actual wheel bytes')
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):
        release=_release(root,manifest['release_id']);release.mkdir(parents=True,exist_ok=False)
        record={**manifest,'status':'installing','document_schema':'deck_document.v1'}
        (release/'release.json').write_text(json.dumps(record,indent=2))
        try:
            inventory = _extract_skill(release,wheel)
            if manifest.get('method_resource_inventory') != inventory:
                raise ValueError('release manifest method inventory differs from wheel')
            subprocess.run([sys.executable,'-m','venv',str(release/'venv')],check=True,capture_output=True,timeout=120)
            python=release/'venv/bin/python'
            subprocess.run([str(python),'-I','-m','pip','install',str(wheel)],check=True,capture_output=True,timeout=300)
            installed_paths = _verify_installed_resources(python, release, inventory, manifest['package_version'])
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
                          skill_sha256=hashlib.sha256((release/'skill'/'deck-master'/'SKILL.md').read_bytes()).hexdigest(),
                          public_skills=list(PUBLIC_SKILLS), method_resource_inventory=inventory,
                          installed_resource_paths=installed_paths)
        except Exception as exc:
            record.update(status='failed',error=str(exc))
            (release/'release.json').write_text(json.dumps(record,indent=2));raise
        (release/'release.json').write_text(json.dumps(record,indent=2))
        return {'status':'candidate_ready','release_id':manifest['release_id'],'release':str(release),'activated':False}

# ---------------------------------------------------------------------------
# Legacy companion migration (§8.3): move the old real-directory ``current``
# aside and prune only the dangling deck-* links that pointed into it.

def _migrate_legacy_companion(root, *, dry_run=False, register_host=True, plan=None):
    if plan is not None:
        if plan['moved']:
            _move(Path(plan['moved']['from']), Path(plan['moved']['to']))
        for name in plan['removed_links']:
            path = _codex_skill_root() / name
            if not path.is_symlink() or not os.readlink(path).startswith(str(root / 'current/skills') + '/'):
                raise HostSkillConflict(str(path), 'legacy link changed after preflight')
            _unlink(path)
        return plan
    report={'migrated':False,'moved':None,'removed_links':[],'skipped_entries':[]}
    current=root/'current'
    moving=current.is_dir() and not current.is_symlink()
    if not moving:
        # A prior opt-out activation preserved both the manifest and Host links.
        for backup in sorted(root.glob('legacy-companion-*')):
            if backup.is_symlink() or not backup.is_dir():
                continue
            try:
                _validate_legacy_companion(backup)
            except (HostSkillConflict, OSError):
                continue
            break
        else:
            return report
    else:
        _validate_legacy_companion(current)
    if moving:
        timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        destination=root/f'legacy-companion-{timestamp}'
        suffix=0
        while destination.exists() or destination.is_symlink():
            suffix+=1
            destination=root/f'legacy-companion-{timestamp}-{suffix}'
        if not dry_run:
            _move(current,destination)
        report.update(migrated=True,moved={'from':str(current),'to':str(destination)})
    skill_root=_codex_skill_root()
    prefix=str(root/'current'/'skills')+'/'
    if skill_root.is_dir():
        for entry in sorted(skill_root.iterdir()):
            if register_host and entry.is_symlink() and re.fullmatch(r'(?:deck|ppt)-.*',entry.name) \
                    and os.readlink(entry).startswith(prefix):
                if not dry_run:
                    _unlink(entry)
                report['removed_links'].append(entry.name)
            else:
                report['skipped_entries'].append(entry.name)
    return report


def _validate_legacy_companion(current):
    entries=sorted(current.iterdir())
    manifest=current/'companion-manifest.json'
    only_manifest=[e.name for e in entries]==['companion-manifest.json'] and manifest.is_file() and not manifest.is_symlink()
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
def _ensure_host_skill_link(root, name='deck-master'):
    state, path = _link_state(root, name)
    if state not in ('managed', 'absent'):
        raise HostSkillConflict(path, 'the Host Skill path belongs to another installation or user')
    link = Path(path)
    if state != 'managed':
        _mkdir(link.parent)
        _replace_link(link, _managed_target(root, name))
    return {'name': name, 'status': 'registered', 'skill_link': str(link), 'skill_target': _managed_target(root, name)}


def _retire_host_skill_link(root, name='deck-master'):
    state, path = _link_state(root, name)
    if state == 'managed':
        _unlink(Path(path))
    return {'name': name, 'status': 'unregistered', 'skill_link': path if state != 'absent' else None}


def _sync_host_skill(root, *, register: bool):
    rows = []
    for name in PUBLIC_SKILLS:
        marker = root / 'current/skill' / name / 'SKILL.md'
        if not register:
            state, path = _link_state(root, name)
            rows.append({'name': name, 'status': 'registered' if state == 'managed' and marker.is_file() else 'host_unregistered',
                         'skill_link': path if state != 'absent' else None})
        elif marker.is_file():
            rows.append(_ensure_host_skill_link(root, name))
        else:
            rows.append(_retire_host_skill_link(root, name))
    active = [row for row in rows if row['status'] == 'registered']
    master = rows[0]
    result = {'host_skill': 'registered' if active else ('host_skill_unregistered' if register else 'host_unregistered'),
              'skill_link': master['skill_link'], 'skill_links': rows}
    if master.get('skill_target'):
        result['skill_target'] = master['skill_target']
    return result


def _preflight_host_skill(root, *, removed_links=()):
    # Check every name before any migration, launcher or pointer mutation.
    parent = _codex_skill_root().absolute()
    for component in reversed((parent, *parent.parents)):
        try:
            if component.is_symlink():
                component.resolve(strict=True)
                if not component.is_dir():
                    raise ValueError('symlink does not resolve to a directory')
            elif component.exists() and not component.is_dir():
                raise ValueError('not a directory')
        except (OSError, RuntimeError, ValueError) as exc:
            raise HostSkillConflict(str(component), f'invalid Codex Skill parent: {exc}; current is unchanged') from exc
    for name in PUBLIC_SKILLS:
        state, path = _link_state(root, name)
        if state in ('occupied', 'foreign') and name not in removed_links:
            raise HostSkillConflict(path, 'the Host Skill path belongs to another installation or user; current is unchanged')

def _checked_release(root, release_id):
    release=_release(root, release_id)
    record=json.loads((release/'release.json').read_text())
    if record.get('status')!='candidate_ready':
        raise ValueError('candidate checks incomplete')
    if record.get('public_skills') is not None:
        if record['public_skills'] != list(PUBLIC_SKILLS):
            raise ValueError('candidate public Skill set is incomplete')
        rows = record.get('installed_resource_paths', [])
        expected = set((record.get('method_resource_inventory') or {}).get('files', {}))
        if not expected or {row.get('wheel_path') for row in rows} != expected:
            raise ValueError('candidate installed method path inventory is incomplete')
        actual_host = {str(path) for path in (release / 'skill').rglob('*') if path.is_file()}
        if actual_host != {row['host_path'] for row in rows}:
            raise ValueError('candidate Host Skill tree has unknown or missing files')
        for row in rows:
            for key in ('host_path', 'installed_package_path'):
                path = Path(row[key])
                if (not path.resolve().is_relative_to(release) or not path.is_file()
                        or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
                    raise ValueError('candidate method resource changed after installation: ' + str(path))
        for name in PUBLIC_SKILLS:
            if not (release / 'skill' / name / 'SKILL.md').is_file():
                raise ValueError('candidate public Skill missing: ' + name)
    return release

_LAUNCHER_TEXT='#!/bin/sh\nexec "$(dirname "$0")/../current/venv/bin/python" -I -m deck_master "$@"\n'


def _preflight_activation(root, release_id, *, migrating=False):
    _checked_release(root,release_id)
    for link in (root/'current', root/'previous'):
        if link.name == 'current' and migrating:
            continue
        if link.exists() and not link.is_symlink():
            raise ValueError('refuse to replace user-owned path: '+str(link))
    launcher=root/'bin/deck-master'
    if launcher.parent.is_symlink() or (launcher.parent.exists() and not launcher.parent.is_dir()):
        raise ValueError('refuse to use user-owned launcher parent')
    if launcher.is_symlink() or (launcher.exists() and
            (not launcher.is_file() or launcher.read_text()!=_LAUNCHER_TEXT)):
        raise ValueError('refuse to replace user-owned launcher')


def _activate_locked(root,release_id):
    _preflight_activation(root,release_id)
    current=root/'current';previous=root/'previous'
    launcher=root/'bin/deck-master'
    _mkdir(launcher.parent)
    if not launcher.exists():
        with launcher.open('x') as handle:
            if transaction := _transaction.get():
                transaction.record(launcher, _identity(launcher), launcher.unlink)
            handle.write(_LAUNCHER_TEXT)
        launcher.chmod(0o755)
    old=os.readlink(current) if current.is_symlink() else None
    target='releases/'+release_id
    if old==target:return {'status':'already_active','release_id':release_id}
    if old:_replace_link(previous,old)
    _replace_link(current,target)
    return {'status':'activated','release_id':release_id,'previous':old,'format_boundary':'Older binaries must not write unsupported Document schemas; restore a compatible project copy.'}

def activate(prefix,release_id,*,register_host=True):
    root=Path(prefix).resolve()/'.deck-master'
    with _locked(root):
        _checked_release(root,release_id)
        migration=_migrate_legacy_companion(root,dry_run=True,register_host=register_host)
        _preflight_activation(root,release_id,migrating=migration['migrated'])
        if register_host:
            # Refuse before switching current: a conflict must not activate.
            _preflight_host_skill(root,removed_links=migration['removed_links'])
        with _compensated():
            migration=_migrate_legacy_companion(root,register_host=register_host,plan=migration)
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
        _checked_release(root,Path(target).name)
        _preflight_activation(root,Path(target).name)
        if register_host:
            _preflight_host_skill(root)
        with _compensated():
            result=_activate_locked(root,Path(target).name)
            registration=_sync_host_skill(root,register=register_host)
            result.update(registration)
            result['cli_active']=True
            if registration.get('host_skill')=='registered':
                result['skill_release_id']=Path(target).name
            return result
