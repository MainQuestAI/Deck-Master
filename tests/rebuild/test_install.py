"""T05 install/package boundary tests (AC-I06 early proof).

Builds a real wheel of the src-layout package and verifies the installed
resources are complete: five schemas, static workbench assets, and the
synced Skill method references. Nothing may be read from the source
checkout at runtime (T16/T20 close the full isolated install).
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _ensure_pip() -> None:
    """uv-created venvs ship without pip; bootstrap it so wheel building works."""
    try:
        import pip  # noqa: F401

        return
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        )


def test_wheel_carries_schema_static_and_methods(tmp_path: Path) -> None:
    _ensure_pip()
    wheel_dir = tmp_path / "wheelhouse"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", str(wheel_dir), str(REPO)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-2000:]
    wheels = list(wheel_dir.glob("deck_master-*.whl"))
    assert wheels, "wheel must be produced"
    names = set()
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    for schema in ("document.v1.schema.json", "page.v2.schema.json", "artifact.v1.schema.json", "task.v1.schema.json", "review.v1.schema.json"):
        assert f"deck_master/resources/contracts/{schema}" in names, f"missing schema in wheel: {schema}"
    for static in ("index.html", "app.js", "style.css"):
        assert f"deck_master/resources/static/{static}" in names, f"missing static in wheel: {static}"
    assert "deck_master/resources/skill/SKILL.md" in names
    with zipfile.ZipFile(wheels[0]) as archive:
        assert archive.read("deck_master/resources/skill/SKILL.md") == (REPO/"skills/deck-master/SKILL.md").read_bytes()
    assert "deck_master/resources/skills-references/source-reading.md" in names
    assert "deck_master/resources/skills-references/content-methods.md" in names
    # AC-I04: the console entry points at the rebuilt CLI (spec 11).
    entry_points_name = next(n for n in names if n.endswith("entry_points.txt"))
    with zipfile.ZipFile(wheels[0]) as archive:
        assert "deck-master = deck_master.cli:main" in archive.read(entry_points_name).decode("utf-8")
    # AC-K15: release artifacts never bundle system/user font files.
    assert not any(n.lower().endswith((".ttf", ".otf", ".ttc", ".woff", ".woff2")) for n in names), \
        "system fonts must not be packaged into the wheel"


def test_resources_resolve_through_importlib() -> None:
    """Schemas and static files load from package resources, not the checkout."""
    import json
    from importlib import resources

    schema_text = resources.files("deck_master").joinpath("resources/contracts/page.v2.schema.json").read_text("utf-8")
    schema = json.loads(schema_text)
    assert schema["required"] == ["schema_version", "page_id", "customer_visible", "visual_spec"]


def test_sdist_rebuild_includes_unique_skill_without_presync(tmp_path):
    import tarfile
    from setuptools import build_meta
    archive=build_meta.build_sdist(str(tmp_path/'sdist'))
    unpacked=tmp_path/'unpacked';unpacked.mkdir()
    with tarfile.open(tmp_path/'sdist'/archive) as tar:
        tar.extractall(unpacked,filter='data')
    source=next(unpacked.iterdir())
    assert (source/'tools/build_hook.py').is_file()
    result=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',str(tmp_path/'wheel'),str(source)],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stderr
    with zipfile.ZipFile(next((tmp_path/'wheel').glob('*.whl'))) as z:
        assert z.read('deck_master/resources/skill/SKILL.md')==(REPO/'skills/deck-master/SKILL.md').read_bytes()
        assert not any(n.startswith(('runtime/','workflow/','build/')) for n in z.namelist())


def test_doctor_step_isolation_and_host_truth(monkeypatch):
    from deck_master.doctor import diagnose
    monkeypatch.setenv('DECK_MASTER_SOFFICE','/missing/soffice')
    compile_result=diagnose('compile')
    assert compile_result['status']=='ready'
    assert not any(c['name']=='soffice' for c in compile_result['checks'])
    result=diagnose('render')
    assert result['status']=='needs_tool'
    assert diagnose('blueprint')['status']=='awaiting_host'
    host=diagnose('blueprint',host_imagegen=True)
    assert any(c['status']=='host_reported_available' for c in host['checks'])
    assert host['professional_evidence']=='not_evaluated'


def test_activation_failure_preserves_current_and_rollback(tmp_path,monkeypatch):
    import json,os
    from deck_master import install
    root=tmp_path/'.deck-master';releases=root/'releases'
    for name in ('one','two','failed'):
        target=releases/name;target.mkdir(parents=True)
        (target/'release.json').write_text(json.dumps({'status':'failed' if name=='failed' else 'candidate_ready'}))
    install.activate(tmp_path,'one')
    with __import__('pytest').raises(ValueError):install.activate(tmp_path,'failed')
    assert os.readlink(root/'current')=='releases/one'
    original=install._replace_link
    def fail_current(path,target):
        if path.name=='current':raise OSError('injected activation failure')
        return original(path,target)
    monkeypatch.setattr(install,'_replace_link',fail_current)
    with __import__('pytest').raises(OSError):install.activate(tmp_path,'two')
    assert os.readlink(root/'current')=='releases/one' and not (root/'previous').exists()
    monkeypatch.setattr(install,'_replace_link',original)
    install.activate(tmp_path,'two');install.rollback(tmp_path)
    assert os.readlink(root/'current')=='releases/one'
    assert os.readlink(root/'previous')=='releases/two'


# ---------------------------------------------------------------------------
# T19 / AC-I08: provenance kept, distribution archives exclude customer runs,
# secrets, bundled fonts and historical sensitive material.

import re as _re
import tarfile

SECRET_PATTERNS = [
    _re.compile(rb"AKIA[0-9A-Z]{16}"),
    _re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    _re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    _re.compile(rb"sk-[A-Za-z0-9]{20,}"),
]
FORBIDDEN_NAME_FRAGMENTS = (
    ".deckmaster", "runs/", "rc_reports", "benchmarks/", "/.env", "credentials",
)


def _iter_wheel_files(wheel_path):
    with zipfile.ZipFile(wheel_path) as archive:
        for name in archive.namelist():
            yield name, archive.read(name)


def _iter_sdist_files(sdist_path):
    with tarfile.open(sdist_path) as archive:
        for member in archive.getmembers():
            if member.isfile():
                yield member.name, archive.extractfile(member).read()


def _assert_archive_clean(files):
    names = [name for name, _ in files]
    for fragment in FORBIDDEN_NAME_FRAGMENTS:
        assert not any(fragment in name.lower() for name in names), \
            f"forbidden path fragment {fragment!r} in archive: {[n for n in names if fragment in n.lower()][:3]}"
    assert not any(name.lower().endswith((".ttf", ".otf", ".ttc", ".woff", ".woff2")) for name in names), \
        "font binaries must not ship in the distribution"
    for name, data in files:
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(data), f"secret pattern {pattern.pattern!r} found in {name}"


def _build_sdist(tmp_path):
    from setuptools import build_meta
    out = tmp_path / "sdist-out"
    out.mkdir()
    return out / build_meta.build_sdist(str(out))


def test_wheel_and_sdist_exclude_customer_material_and_secrets(tmp_path: Path) -> None:
    _ensure_pip()
    wheelhouse = tmp_path / "wheelhouse"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", str(wheelhouse), str(REPO)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-2000:]
    wheel = next(wheelhouse.glob("deck_master-*.whl"))
    sdist = _build_sdist(tmp_path)

    wheel_files = list(_iter_wheel_files(wheel))
    sdist_files = list(_iter_sdist_files(sdist))
    _assert_archive_clean(wheel_files)
    _assert_archive_clean(sdist_files)

    # Positive: runtime resources stay complete — cleaning never removes
    # operating capability (schemas, static workbench, skill references).
    wheel_names = {name for name, _ in wheel_files}
    for schema in ("document.v1", "page.v2", "artifact.v1", "task.v1", "review.v1"):
        assert f"deck_master/resources/contracts/{schema}.schema.json" in wheel_names
    for static in ("index.html", "app.js", "style.css"):
        assert f"deck_master/resources/static/{static}" in wheel_names
    assert "deck_master/resources/skill/SKILL.md" in wheel_names
    assert any(n.startswith("deck_master/resources/skills-references/") for n in wheel_names)

    # Provenance (T19.01): extraction attribution headers ship with the code.
    geometry = dict(wheel_files)["deck_master/compiler/geometry.py"].decode("utf-8")
    assert "Function-level extraction from pinned B0" in geometry
    native = dict(wheel_files)["deck_master/compiler/native.py"].decode("utf-8")
    assert "B0 2a866cf" in native
    # License texts ship and match pyproject metadata.
    license_text = dict(wheel_files)["deck_master-1.0.0.dev2.dist-info/licenses/LICENSE"].decode("utf-8") \
        if any(n.endswith("dist-info/licenses/LICENSE") for n in wheel_names) \
        else dict(wheel_files)["deck_master-1.0.0.dev2.dist-info/LICENSE"].decode("utf-8")
    assert "Apache License" in license_text
    metadata_name = next(n for n in wheel_names if n.endswith("METADATA"))
    metadata_text = dict(wheel_files)[metadata_name].decode("utf-8")
    assert "License: Apache-2.0" in metadata_text or "License-Expression: Apache-2.0" in metadata_text


def test_release_tree_manifest_scans_clean(tmp_path: Path) -> None:
    from tools.build_release import build_release

    manifest = build_release(tmp_path / "release-out")
    assert manifest["source_dirty"] in (True, False)
    assert manifest["entry"] == ["python", "-m", "deck_master"]
    for name in manifest["files"]:
        lowered = name.lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in lowered, f"forbidden path in release manifest: {name}"
        assert not lowered.endswith((".ttf", ".otf", ".ttc", ".woff", ".woff2")), name
