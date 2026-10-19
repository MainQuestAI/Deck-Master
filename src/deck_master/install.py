"""Isolated candidate releases; activation only inside an explicit prefix.

RC3 carries four public entries under ``skill/<name>``. Activation registers
all four ``$CODEX_HOME/skills/<name>`` links through the same release current pointer,
rollback retires the link when the previous release predates skills, and a
one-time migration moves the legacy companion layout aside without deleting
anything. The installer never touches third-party skills or config.toml.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os, re, stat, subprocess, sys, uuid, zipfile

from .errors import HostSkillConflict
from .errors import InstallationTransactionError
from .store import locked_file
from . import activation_transaction as journal

PUBLIC_SKILLS = ('deck-master', 'deck-content', 'deck-design', 'deck-review')
_METHOD_INVENTORY = 'deck_master/resources/method-inventory.json'

@contextmanager
def _locked(root):
    if root.is_symlink():
        raise InstallationTransactionError('installation_recovery_unavailable', 'installation control root cannot be a symlink', state='unknown')
    root.mkdir(parents=True,exist_ok=True)
    with locked_file(root/'install.lock'):
        yield

# Every activation mutation routes to the one persisted action currently being
# applied. The fallback primitives also serve the legacy migration helper.
_durable_step = ContextVar('installation_durable_step', default=None)


def _identity(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode))


def _mkdir(path, *, prepared=None):
    if path.is_dir():
        return
    _mkdir(path.parent, prepared=prepared)
    path.mkdir()
    journal.fsync_dir(path.parent)
    if prepared is not None:
        identity = journal.snapshot(path)
        prepared.append({'step_id': 'directory-' + str(len(prepared)), 'kind': 'mkdir',
                         'path': str(path), 'before': None, 'parent_identity': journal.parent_identity(path),
                         'prepared': {'path': str(path), 'identity': identity}, 'identity': identity,
                         'expected_after': identity, 'step_state': 'applied', 'observed': {'state': 'created_parent'}})


def _unlink(path):
    if active := _durable_step.get():
        return active[0].apply(active[1])
    path.unlink()
    journal.fsync_dir(path.parent)


def _move(source, destination):
    if active := _durable_step.get():
        return active[0].apply(active[1])
    if _identity(destination) is not None:
        raise ValueError('migration backup occupied: ' + str(destination))
    journal.rename_noreplace(source, destination, journal.parent_identity(source))


def _replace_link(path, target):
    if active := _durable_step.get():
        return active[0].apply(active[1])
    temp = path.parent / ('.' + path.name + '-' + uuid.uuid4().hex)
    if _identity(path) is not None and not path.is_symlink():
        raise ValueError('refuse to replace occupied path: ' + str(path))
    try:
        temp.symlink_to(target)
        os.replace(temp, path)
        journal.fsync_dir(path.parent)
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
    if not register_host:
        return report
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
def _sync_host_skill(root, *, register: bool):
    """Report the installed public set after the durable actions, without writes."""
    return _registration_result(root, root / 'current', _codex_skill_root().absolute() if register else None)


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


def _release_identity(root, release_id):
    release = _checked_release(root, release_id)
    digest = hashlib.sha256()
    paths = {release / 'release.json'}
    paths.update(path for path in (release / 'skill').rglob('*') if path.is_file())
    record = json.loads((release / 'release.json').read_text())
    for row in record.get('installed_resource_paths', []):
        paths.add(Path(row['installed_package_path']))
    for path in sorted(paths):
        digest.update(str(path.relative_to(release)).encode() + b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _installation_observation(root, host):
    try:
        current = root / 'current'
        if not current.is_symlink():
            raise ValueError('current is not a release pointer')
        target = os.readlink(current)
        if not target.startswith('releases/') or len(Path(target).parts) != 2:
            raise ValueError('current is not a supported release pointer')
        release_id = Path(target).name
        release = _checked_release(root, release_id)
        launcher = root / 'bin/deck-master'
        healthy = (launcher.is_file() and not launcher.is_symlink() and
                   launcher.read_text() == _LAUNCHER_TEXT and bool(launcher.stat().st_mode & 0o111))
        if host is not None:
            for name in PUBLIC_SKILLS:
                path = host / name
                expected = (release / 'skill' / name / 'SKILL.md').is_file()
                healthy = healthy and ((path.is_symlink() and os.readlink(path) == _managed_target(root, name))
                                       if expected else journal.snapshot(path) is None)
        return {'observed_current_release_id': release_id,
                'current_install_state': 'verified' if healthy else 'inconsistent'}
    except (OSError, ValueError, KeyError) as exc:
        return {'observed_current_release_id': None, 'current_install_state': 'unknown',
                'current_install_observation_error': str(exc)}


def _transaction_result(root, record, recovered):
    result = {**record['result'], 'transaction_id': record['transaction_id'],
              'transaction_state': record['state'], 'recovered': recovered}
    # These fields describe current state separately from the historical receipt.
    host = Path(record['request']['host_root']) if record['request']['register_host'] else None
    result.update(_installation_observation(root, host))
    return result


def _registration_result(root, release, host):
    rows = []
    for name in PUBLIC_SKILLS:
        present = (release / 'skill' / name / 'SKILL.md').is_file()
        if host is None:
            rows.append({'name': name, 'status': 'host_unregistered', 'skill_link': None})
        elif present:
            rows.append({'name': name, 'status': 'registered', 'skill_link': str(host / name),
                         'skill_target': _managed_target(root, name)})
        else:
            rows.append({'name': name, 'status': 'unregistered', 'skill_link': None})
    active = any(row['status'] == 'registered' for row in rows)
    result = {'host_skill': 'registered' if active else ('host_skill_unregistered' if host else 'host_unregistered'),
              'skill_link': rows[0]['skill_link'], 'skill_links': rows}
    if rows[0].get('skill_target'):
        result['skill_target'] = rows[0]['skill_target']
    return result


def _prepare_activation(root, verb, release_id, register_host, host, ident, parent_preparations=()):
    # All preflights run again under the Host registration lock.
    release = _checked_release(root, release_id)
    migration = _migrate_legacy_companion(root, dry_run=True, register_host=register_host)
    _preflight_activation(root, release_id, migrating=migration['migrated'])
    if register_host:
        _preflight_host_skill(root, removed_links=migration['removed_links'])
    request = {'verb': verb, 'prefix': str(root.parent), 'target_release_id': release_id,
               'target_release_identity': _release_identity(root, release_id),
               'register_host': register_host, 'host_root': str(host) if host else None,
               'transaction_id': ident}
    plan = journal.Plan(root, request)
    plan.record['created_directories'].extend(parent_preparations)
    old = os.readlink(root / 'current') if (root / 'current').is_symlink() else None
    previous = os.readlink(root / 'previous') if (root / 'previous').is_symlink() else None
    plan.record.update(old_current=old, old_previous=previous, migration=migration)
    if migration['moved']:
        plan.add('move', Path(migration['moved']['from']), destination=Path(migration['moved']['to']))
    for name in migration['removed_links']:
        plan.add('remove', host / name)
    launcher = root / 'bin/deck-master'
    if not launcher.exists() or stat.S_IMODE(launcher.stat().st_mode) != 0o755:
        plan.add('launcher', launcher, _LAUNCHER_TEXT)
    target = 'releases/' + release_id
    if old != target:
        if old:
            plan.add('link', root / 'previous', old)
        plan.add('link', root / 'current', target)
    if host is not None:
        for name in PUBLIC_SKILLS:
            path = host / name
            before = plan.virtual.get(str(path), journal.snapshot(path))
            if (release / 'skill' / name / 'SKILL.md').is_file():
                if before is None:
                    plan.add('link', path, _managed_target(root, name))
            elif before is not None:
                plan.add('remove', path)
    watched = [root / 'current', root / 'previous', launcher]
    if host is not None:
        watched.extend(host / name for name in PUBLIC_SKILLS)
        watched.extend(host / name for name in migration['removed_links'])
    plan.record['watched'] = [
        {'path': str(path), 'before': journal.snapshot(path), 'parent_identity': journal.parent_identity(path)}
        for path in dict.fromkeys(watched)]
    for watched_path in plan.record['watched']:
        plan.anchor(Path(watched_path['path']), watched_path['before'])
    result = {'status': 'already_active' if old == target else 'activated', 'release_id': release_id,
              'cli_active': True, 'migration': migration}
    if old != target:
        result.update(previous=old, format_boundary='Older binaries must not write unsupported Document schemas; restore a compatible project copy.')
    result.update(_registration_result(root, release, host))
    if result['host_skill'] == 'registered':
        result['skill_release_id'] = release_id
    plan.record['planned_result'] = result
    plan.record['host_identity'] = journal.snapshot(host) if host else None
    plan.record['host_parent_identity'] = journal.parent_identity(host / '.deck-master-registration.lock') if host else None
    return plan.persist()


def _check_request(record, root, verb, release_id, register_host, host, *, explicit):
    request = record['request']
    matches = (request['verb'] == verb and request['prefix'] == str(root.parent) and
               request['register_host'] == register_host and request['host_root'] == (str(host) if host else None)
               and (verb == 'rollback' or request['target_release_id'] == release_id))
    if not matches:
        code = 'installation_transaction_conflict' if explicit else 'installation_transaction_pending'
        raise InstallationTransactionError(code, 'another frozen installation request owns this transaction',
                                           transaction_id=record['transaction_id'], state=record['state'])


def _same_host_parent(record):
    host = Path(record['request']['host_root'])
    try:
        return (journal.snapshot(host) == record['host_identity'] and
                journal.parent_identity(host / '.deck-master-registration.lock') == record['host_parent_identity'])
    except OSError:
        return False


def _verify_transaction_target(root, record):
    request = record['request']
    try:
        actual = _release_identity(root, request['target_release_id'])
        if actual != request['target_release_identity']:
            raise ValueError('target fingerprint differs from frozen request')
    except (OSError, ValueError, KeyError) as exc:
        raise InstallationTransactionError('installation_recovery_conflict', 'target release resources changed or no longer verify: ' + str(exc),
                                           transaction_id=record['transaction_id'], state=record['state']) from exc


def _run_activation(root, record, recovered):
    tx = journal.Transaction(root, record)
    if record['state'] == 'completed':
        tx.finish_pointer()
        return _transaction_result(root, record, True)
    if record['state'] == 'rolled_back':
        tx.finish_pointer()
        raise tx.failure(True)
    if record['state'] == 'recovery_conflict':
        raise InstallationTransactionError('installation_recovery_conflict', 'preserved transaction has unresolved ownership conflicts',
                                           transaction_id=record['transaction_id'], state=record['state'],
                                           details={'conflicts': record.get('conflicts', [])})
    if record['state'] == 'compensating':
        try:
            tx.compensate()
        except KeyboardInterrupt as exc:
            raise InstallationTransactionError('installation_interrupted', 'compensation interrupted; resume the original request',
                                               transaction_id=record['transaction_id'], state=record['state']) from exc
        except (OSError, ValueError) as exc:
            raise InstallationTransactionError('installation_recovery_unavailable', 'cannot verify/persist resumed compensation: ' + str(exc),
                                               transaction_id=record['transaction_id'], state='unknown') from exc
        raise tx.failure(True)
    try:
        request = record['request']
        if request['register_host'] and not _same_host_parent(record):
            raise InstallationTransactionError('installation_recovery_conflict', 'Host parent was replaced externally; preserve the old directory and transaction artifacts',
                                               transaction_id=record['transaction_id'], state=record['state'])
        _verify_transaction_target(root, record)
        record['state'] = 'applying'
        tx.save()
        journal.pending(root, record)
        for index, step in enumerate(record['steps']):
            if step['step_state'] == 'applied':
                # Later steps may legitimately reuse a path (legacy migration).
                continue
            record['apply_cursor'] = index
            tx.save()
            token = _durable_step.set((tx, step))
            try:
                path = Path(step['path'])
                if step['kind'] == 'link':
                    _replace_link(path, step['expected_after']['target'])
                elif step['kind'] == 'remove':
                    _unlink(path)
                elif step['kind'] == 'move':
                    _move(path, Path(step['backup']))
                else:
                    tx.apply(step)
            finally:
                _durable_step.reset(token)
        # Registration is now a read-only report; all mutations were planned.
        _sync_host_skill(root, register=request['register_host'])
        # Final verification covers unchanged managed paths as well as actions.
        host = Path(request['host_root']) if request['register_host'] else None
        observed = _installation_observation(root, host)
        if (observed['current_install_state'] != 'verified' or
                observed['observed_current_release_id'] != request['target_release_id']):
            raise InstallationTransactionError('installation_recovery_conflict', 'final installation state failed verification',
                                               transaction_id=record['transaction_id'], state=record['state'], details=observed)
        _verify_transaction_target(root, record)
        # Inodes matter even when link strings or launcher bytes still match.
        finals = {step['path']: step for step in record['steps']}
        for step in finals.values():
            if tx.inspect(step) != 'applied':
                tx.conflict(step, 'published action no longer belongs to this transaction')
        for step in record['steps']:
            if finals[step['path']] is not step:
                tx.check_parent(step)
                if journal.snapshot(Path(step['backup'])) != step['before']:
                    tx.conflict(step, 'legacy original backup changed after its path was reused')
        for watched in record.get('watched', []):
            path = Path(watched['path'])
            if str(path) not in finals and (journal.snapshot(path) != watched['before'] or
                                           journal.parent_identity(path) != watched['parent_identity'] or
                                           not tx.anchors_intact(str(path))):
                raise InstallationTransactionError('installation_recovery_conflict', 'unchanged managed path changed externally',
                                                   transaction_id=record['transaction_id'], state=record['state'],
                                                   details={'path': str(path), 'expected': watched['before'],
                                                            'observed': journal.snapshot(path)})
        journal.checkpoint('before_completed', record)
        record.update(state='completed', result=record['planned_result'])
        tx.save()
        journal.checkpoint('completed', record)
    except (Exception, KeyboardInterrupt) as exc:
        # A completed receipt must never be compensated because ACK/pointer failed.
        if record['state'] == 'completed':
            raise InstallationTransactionError('installation_recovery_unavailable', 'completion acknowledgement could not be verified; replay the original transaction ID: ' + str(exc),
                                               transaction_id=record['transaction_id'], state='unknown') from exc
        code = ('installation_interrupted' if isinstance(exc, KeyboardInterrupt) else
                getattr(exc, 'error_code', 'installation_failed'))
        record['failure'] = {'code': code, 'message': str(exc) or 'installation interrupted', 'type': type(exc).__name__}
        if code == 'installation_recovery_conflict':
            record['conflicts'] = [exc.payload()['error']]
        record['state'] = 'compensating'
        try:
            tx.save()
            journal.checkpoint('compensating', record)
            tx.compensate()
        except KeyboardInterrupt as interrupted:
            raise InstallationTransactionError('installation_interrupted', 'compensation interrupted; resume the original request',
                                               transaction_id=record['transaction_id'], state=record['state']) from interrupted
        except InstallationTransactionError:
            raise
        except (OSError, ValueError) as persistence:
            raise InstallationTransactionError('installation_recovery_unavailable', 'cannot persist/verify compensation; original outcome unknown: ' + str(persistence),
                                               transaction_id=record['transaction_id'], state='unknown') from persistence
        if isinstance(exc, KeyboardInterrupt):
            raise tx.failure(False) from exc
        if isinstance(exc, InstallationTransactionError):
            exc.transaction_state = record['state']
            exc.details.update(old_state_verified=record.get('restoration_verified', False), new_state_verified=False)
            raise
        # Existing Python callers retain the original ordinary exception class.
        exc.transaction_id = record['transaction_id']
        exc.transaction_state = record['state']
        raise
    tx.finish_pointer()
    return _transaction_result(root, record, recovered)


def _activation(prefix, verb, release_id=None, *, register_host=True, transaction_id=None):
    ident = journal.transaction_id(transaction_id)
    root = Path(prefix).resolve() / '.deck-master'
    # Opt-out never even resolves the Host path, including replay/compensation.
    host = _codex_skill_root().absolute() if register_host else None
    with _locked(root):
        active = journal.discover(root)
        selected_path = journal.record_path(root, ident)
        record = journal.read(root, ident) if transaction_id and (selected_path.exists() or selected_path.is_symlink()) else None
        if record is not None:
            _check_request(record, root, verb, release_id, register_host, host, explicit=True)
        elif active is not None:
            if transaction_id and active['transaction_id'] != ident:
                raise InstallationTransactionError('installation_transaction_pending', 'unfinished installation request must be resumed first',
                                                   transaction_id=active['transaction_id'], state=active['state'])
            _check_request(active, root, verb, release_id, register_host, host, explicit=bool(transaction_id))
            record = active
        if record is not None and record['state'] in journal.TERMINAL:
            return _run_activation(root, record, True)
        if record is None:
            if verb == 'rollback':
                previous = root / 'previous'
                if not previous.is_symlink():
                    raise ValueError('no previous release')
                target = os.readlink(previous)
                if not target.startswith('releases/') or len(Path(target).parts) != 2:
                    raise ValueError('invalid previous release')
                release_id = Path(target).name
            _checked_release(root, release_id)
            migration = _migrate_legacy_companion(root, dry_run=True, register_host=register_host)
            _preflight_activation(root, release_id, migrating=migration['migrated'])
            if register_host:
                _preflight_host_skill(root, removed_links=migration['removed_links'])
        # Lock ordering is always prefix -> Host. Host mkdir is bounded parent
        # preparation, never public registration; under the lock recheck all facts.
        if record is not None and host is not None and not _same_host_parent(record):
            # Never create a lock in a replacement external Host directory. The
            # persisted engine can compensate still-owned prefix paths only.
            return _run_activation(root, record, True)
        parent_preparations = []
        if host is not None:
            _mkdir(host, prepared=parent_preparations)
        with locked_file(host / '.deck-master-registration.lock') if host else nullcontext():
            if record is None:
                try:
                    record = _prepare_activation(root, verb, release_id, register_host, host, ident, parent_preparations)
                except KeyboardInterrupt as exc:
                    path = journal.record_path(root, ident)
                    if not path.exists():
                        raise InstallationTransactionError('installation_interrupted', 'interrupted before a recoverable plan was published; no activation was applied',
                                                           transaction_id=ident, state='unknown', details={'old_state_verified': True}) from exc
                    record = journal.read(root, ident)
                    record.update(state='compensating', failure={'code': 'installation_interrupted', 'message': 'installation preparation interrupted', 'type': 'KeyboardInterrupt'})
                    tx = journal.Transaction(root, record)
                    tx.save()
                    tx.compensate()
                    raise tx.failure(False) from exc
                except OSError as exc:
                    raise InstallationTransactionError('installation_recovery_unavailable', 'could not publish the complete activation plan or pending pointer: ' + str(exc),
                                                       transaction_id=ident, state='unknown') from exc
                recovered = False
            else:
                recovered = True
            return _run_activation(root, record, recovered)


def activate(prefix, release_id, *, register_host=True, transaction_id=None):
    return _activation(prefix, 'activate', release_id, register_host=register_host, transaction_id=transaction_id)


def rollback(prefix, *, register_host=True, transaction_id=None):
    return _activation(prefix, 'rollback', register_host=register_host, transaction_id=transaction_id)
