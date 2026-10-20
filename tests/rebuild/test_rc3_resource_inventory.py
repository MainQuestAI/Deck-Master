"""Strict resource identity: additions cannot silently pass an old file count."""
import copy
import io
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from tools.build_hook import INVENTORY_PATH, resource_inventory, source_version, validate_wheel_inventory
from deck_master import install

ROOT = Path(__file__).resolve().parents[2]


def _wheel(inventory, *, extra=None, omit=None, corrupt=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(INVENTORY_PATH, json.dumps(inventory))
        for name, row in inventory['files'].items():
            if name != omit:
                archive.writestr(name, b'corrupt' if name == corrupt else (ROOT / row['canonical_source']).read_bytes())
        if extra:
            archive.writestr(extra, 'unknown')
    stream.seek(0)
    return zipfile.ZipFile(stream)


def test_full_source_wheel_and_installer_mapping_is_exact():
    inventory = resource_inventory(ROOT)
    with _wheel(inventory) as archive:
        assert validate_wheel_inventory(archive, root=ROOT) == inventory
        actual, extracted = install._wheel_skills(archive)
        assert actual == inventory
        assert len(extracted) == len(inventory['files'])
        assert all(f'{name}/SKILL.md' in extracted for name in install.PUBLIC_SKILLS)
    assert set(inventory['generated_exceptions']) == {INVENTORY_PATH}


def test_source_version_drift_is_rejected_before_build(tmp_path):
    (tmp_path / 'pyproject.toml').write_text('[project]\nversion="1.0.0rc3"\n')
    module = tmp_path / 'src/deck_master/__init__.py'
    module.parent.mkdir(parents=True)
    module.write_text('__version__ = "1.0.0.dev2"\n')
    with pytest.raises(RuntimeError, match='__version__ differs'):
        source_version(tmp_path)


def test_manifest_file_hash_mismatch_refuses_before_creating_prefix(tmp_path):
    import hashlib
    inventory = resource_inventory(ROOT)
    with _wheel(inventory) as archive:
        raw = archive.fp.getvalue()
    wheel = tmp_path / 'candidate.whl'
    wheel.write_bytes(raw)
    manifest = tmp_path / 'release.json'
    manifest.write_text(json.dumps({'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(raw).hexdigest(),
                                    'files': {}}))
    prefix = tmp_path / 'prefix'
    with pytest.raises(ValueError, match='file inventory differs'):
        install.install_candidate(prefix, manifest)
    assert not prefix.exists()


@pytest.mark.parametrize('mutation', ['unknown', 'missing', 'symlink'])
def test_unknown_missing_or_symlink_canonical_file_fails(tmp_path, mutation):
    shutil.copytree(ROOT / 'skills', tmp_path / 'skills')
    # The build hook loads the shared catalog validator from the source tree.
    module = tmp_path / 'src/deck_master/resource_catalog.py'
    module.parent.mkdir(parents=True)
    shutil.copy2(ROOT / 'src/deck_master/resource_catalog.py', module)
    path = tmp_path / 'skills/deck-master/references/unknown.md'
    if mutation == 'unknown':
        path.write_text('must not silently ship')
    elif mutation == 'missing':
        (tmp_path / 'skills/deck-content/SKILL.md').unlink()
    else:
        path.symlink_to(tmp_path / 'skills/deck-master/SKILL.md')
    with pytest.raises(RuntimeError, match='canonical Skill'):
        resource_inventory(tmp_path)


@pytest.mark.parametrize('mutation', ['extra', 'missing', 'hash', 'canonical'])
def test_wheel_or_canonical_mapping_drift_fails_before_extraction(mutation):
    inventory = copy.deepcopy(resource_inventory(ROOT))
    name = next(iter(inventory['files']))
    kwargs = {}
    if mutation == 'extra':
        kwargs['extra'] = 'deck_master/resources/skills/deck-content/references/secret.md'
    elif mutation == 'missing':
        kwargs['omit'] = name
    elif mutation == 'hash':
        kwargs['corrupt'] = name
    else:
        inventory['files'][name]['canonical_source'] = 'skills/deck-master/references/unknown.md'
        # Use a source that exists to construct the deliberately mismatched zip.
        with _wheel(resource_inventory(ROOT)) as original:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as changed:
                for member in original.namelist():
                    changed.writestr(member, json.dumps(inventory) if member == INVENTORY_PATH else original.read(member))
            stream.seek(0)
            with zipfile.ZipFile(stream) as archive:
                with pytest.raises((RuntimeError, ValueError), match='canonical'):
                    validate_wheel_inventory(archive, root=ROOT)
                with pytest.raises(ValueError, match='canonical'):
                    install._wheel_skills(archive)
        return
    with _wheel(inventory, **kwargs) as archive:
        with pytest.raises((RuntimeError, ValueError)):
            validate_wheel_inventory(archive, root=ROOT)
        with pytest.raises(ValueError):
            install._wheel_skills(archive)
