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
