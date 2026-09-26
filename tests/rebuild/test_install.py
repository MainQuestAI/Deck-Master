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

import pytest

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
    # T7 single source: every packaged method file is byte-identical to the
    # canonical skills/deck-master source, and skills-references is gone.
    with zipfile.ZipFile(wheels[0]) as archive:
        assert archive.read("deck_master/resources/skill/SKILL.md") == (REPO/"skills/deck-master/SKILL.md").read_bytes()
        for relative in ("source-reading.md", "content-methods.md", "content-examples.md",
                         "input-update.md", "review-and-repair.md", "blueprint-svg.md"):
            wheel_name = f"deck_master/resources/skill/references/{relative}"
            assert wheel_name in names, f"missing method reference in wheel: {relative}"
            assert archive.read(wheel_name) == (REPO/"skills/deck-master/references"/relative).read_bytes()
    assert not any(n.startswith("deck_master/resources/skills-references") for n in names), \
        "skills-references must no longer ship (single method source)"
    # P1: the packaged installation guide must not teach retired commands.
    with zipfile.ZipFile(wheels[0]) as archive:
        installation = archive.read("deck_master/resources/skill/references/installation.md").decode("utf-8")
    for retired in ("suite-install", "suite-status", "suite-repair", "release-rollback",
                    "release-build", "release-smoke", "preview-gate", "rc-gate"):
        assert retired not in installation, f"packaged installation.md teaches {retired}"
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
    import textwrap
    script = textwrap.dedent(
        "from setuptools import build_meta\n"
        f"print(build_meta.build_sdist({str(tmp_path / 'sdist')!r}))\n")
    archive = subprocess.run([sys.executable, "-c", script], capture_output=True,
                             text=True, check=True, timeout=600).stdout.strip().splitlines()[-1]
    unpacked=tmp_path/'unpacked';unpacked.mkdir()
    with tarfile.open(tmp_path/'sdist'/archive) as tar:
        tar.extractall(unpacked,filter='data')
    source=next(unpacked.iterdir())
    assert (source/'tools/build_hook.py').is_file()
    result=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','-w',str(tmp_path/'wheel'),str(source)],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stderr
    with zipfile.ZipFile(next((tmp_path/'wheel').glob('*.whl'))) as z:
        assert z.read('deck_master/resources/skill/SKILL.md')==(REPO/'skills/deck-master/SKILL.md').read_bytes()
        for relative in ('source-reading.md', 'content-methods.md', 'input-update.md',
                         'review-and-repair.md', 'content-examples.md'):
            name = f'deck_master/resources/skill/references/{relative}'
            assert z.read(name) == (REPO/'skills/deck-master/references'/relative).read_bytes()
        assert not any(n.startswith(('runtime/','workflow/','build/')) for n in z.namelist())


@pytest.mark.render
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
    monkeypatch.setenv('CODEX_HOME',str(tmp_path/'codex-home'))
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
    # In a subprocess: on Python 3.11 something in the pytest process may
    # have imported the stdlib distutils before setuptools, which trips the
    # _distutils_hack assert during an in-process backend import.
    out = tmp_path / "sdist-out"
    out.mkdir()
    import textwrap
    script = textwrap.dedent(
        "from setuptools import build_meta\n"
        f"print(build_meta.build_sdist({str(out)!r}))\n")
    result = subprocess.run([sys.executable, "-c", script],
                            capture_output=True, text=True, check=True, timeout=600)
    return out / result.stdout.strip().splitlines()[-1]


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
    assert any(n.startswith("deck_master/resources/skill/references/") for n in wheel_names)

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
    import deck_master as _dm
    assert manifest["source_sha"] == subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    assert manifest["package_version"] == _dm.__version__
    assert manifest["compiler_version"] == "python-native-v1"
    assert manifest["entry"] == ["python", "-m", "deck_master"]
    for name in manifest["files"]:
        lowered = name.lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in lowered, f"forbidden path in release manifest: {name}"
        assert not lowered.endswith((".ttf", ".otf", ".ttc", ".woff", ".woff2")), name


import hashlib
from pathlib import Path as _Path



# ---------------------------------------------------------------------------
# T20 / AC-I05: isolated installs (wheel AND sdist) run the full local flow
# with an empty HOME — no PPT Master binding, no slide library, no caches,
# and no source-checkout access at runtime.

import json as _json
import os as _os
import shutil as _shutil
import venv as _venv

ENVELOPES = REPO / "docs" / "specs" / "deck-master-rebuild-v1" / "examples" / "roundtrips" / "result-envelope"


@pytest.fixture(scope="module")
def dist_artifacts(tmp_path_factory):
    _ensure_pip()
    work = tmp_path_factory.mktemp("dist-artifacts")
    wheelhouse = work / "wheelhouse"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", str(wheelhouse), str(REPO)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")[-1500:]
    sdist_dir = work / "sdist"
    sdist_dir.mkdir()
    import textwrap
    script = textwrap.dedent(
        "from setuptools import build_meta\n"
        f"print(build_meta.build_sdist({str(sdist_dir)!r}))\n")
    sdist = sdist_dir / subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        check=True, timeout=600).stdout.strip().splitlines()[-1]
    return {"wheel": next(wheelhouse.glob("deck_master-*.whl")), "sdist": sdist,
            "wheel_sha256": hashlib.sha256(next(wheelhouse.glob("deck_master-*.whl")).read_bytes()).hexdigest()}


def _make_isolated_venv(base: Path, artifact: Path) -> Path:
    """Create a venv and install the artifact offline-friendly: pip bootstrap
    falls back when ensurepip is absent (uv-managed interpreters), and the
    sdist path builds with --no-build-isolation against a preinstalled
    setuptools so sandboxes do not fetch a second build backend."""
    home = base / "venv-home"
    home.mkdir()
    # SETUPTOOLS_USE_DISTUTILS=stdlib works around homebrew Python 3.11's
    # _distutils_hack assertion while bootstrapping nested venvs.
    venv_env = {**_os.environ, "SETUPTOOLS_USE_DISTUTILS": "stdlib"}
    created = subprocess.run([sys.executable, "-m", "venv", str(home)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, env=venv_env)
    python = home / "bin" / "python"
    if created.returncode != 0 or not (home / "bin" / "pip").is_file():
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(home)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, env=venv_env)
        bootstrapped = subprocess.run([str(python), "-m", "ensurepip", "--upgrade"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if bootstrapped.returncode != 0:
            subprocess.run([sys.executable, "-m", "pip", "--python", str(python), "install", "pip"],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    pip = home / "bin" / "pip"
    subprocess.run([str(pip), "install", "--quiet", "setuptools>=77", "wheel"],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    subprocess.run([str(pip), "install", "--quiet", "--no-build-isolation", str(artifact)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    return home


@pytest.fixture(scope="module")
def wheel_venv(tmp_path_factory, dist_artifacts):
    return _make_isolated_venv(tmp_path_factory.mktemp("wheel-venv"), dist_artifacts["wheel"])


@pytest.fixture(scope="module")
def sdist_venv(tmp_path_factory, dist_artifacts):
    return _make_isolated_venv(tmp_path_factory.mktemp("sdist-venv"), dist_artifacts["sdist"])


def _isolated_env(venv: Path, home: Path):
    env = {key: value for key, value in _os.environ.items()
           if not (key.startswith(("XDG_", "PYTHONPATH", "DECK_MASTER_")) or key in ("HOME", "USERPROFILE"))}
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / "xdg-config")
    env["XDG_DATA_HOME"] = str(home / "xdg-data")
    env["PATH"] = str(venv / "bin") + _os.pathsep + env.get("PATH", "")
    env["DECK_MASTER_NO_AUTO_VIEW"] = "1"
    return env


def _iso_run(venv: Path, args, home: Path, cwd: Path):
    result = subprocess.run([str(venv / "bin" / "python"), "-I", "-m", "deck_master", *args],
                            capture_output=True, text=True, timeout=600, env=_isolated_env(venv, home), cwd=str(cwd))
    payload = {}
    if result.stdout.strip():
        try:
            payload = _json.loads(result.stdout)
        except _json.JSONDecodeError:
            payload = {"raw": result.stdout}
    return result.returncode, payload, result.stderr


def _resolvable_font_family(venv: Path, home: Path, cwd: Path):
    for candidate in ("Hiragino Sans GB", "Noto Sans CJK SC", "DejaVu Sans", "Helvetica", "Arial"):
        code, payload, _ = _iso_run(venv, ["doctor", "--step", "compile", "--font", candidate], home, cwd)
        checks = {check["name"]: check for check in payload.get("checks", [])}
        if code == 0 and checks.get(f"font:{candidate}", {}).get("status") == "ready":
            return candidate
    pytest.fail("no resolvable font family on this host for the isolated chain")


def _write_material(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    material = directory / "material.txt"
    material.write_text("隔离安装材料正文\n(尾部约束)合成数据不可回写。", encoding="utf-8")
    return material


@pytest.mark.parametrize("venv_fixture", ["wheel_venv", "sdist_venv"])
def test_isolated_install_runs_full_local_flow(venv_fixture, tmp_path, dist_artifacts, request):
    """AC-I05: empty HOME, no bindings/caches, module from the venv — and the
    real create→continue flow still produces a pending Host task."""
    venv = request.getfixturevalue(venv_fixture)
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()

    probe = subprocess.run(
        [str(venv / "bin" / "python"), "-I", "-c",
         "import deck_master, json; print(json.dumps({'file': deck_master.__file__}))"],
        capture_output=True, text=True, env=_isolated_env(venv, home), cwd=str(work))
    module_path = _json.loads(probe.stdout)["file"]
    assert module_path.startswith(str(venv)), f"module must come from the venv, got {module_path}"
    assert not Path(module_path).resolve().is_relative_to(REPO), "module must not be borrowed from the checkout"

    code, payload, _ = _iso_run(venv, ["doctor", "--step", "compose"], home, work)
    assert code == 0 and payload["status"] == "ready", payload
    assert Path(payload["module_path"]).resolve().is_relative_to(venv)
    code, payload, _ = _iso_run(venv, ["doctor", "--step", "render"], home, work)
    assert (code, payload["status"]) in ((0, "ready"), (3, "needs_tool")), payload

    evidence = {
        "interpreter": str(venv / "bin" / "python"),
        "module_path": module_path,
        "package_sha256": dist_artifacts["wheel_sha256"] if venv_fixture == "wheel_venv" else None,
        "doctor_module_path": payload["module_path"],
    }
    code, payload, _ = _iso_run(venv, ["create", "--brief", "隔离建项", "--source",
                                       str(_write_material(work)), "--out", str(work / "proj")], home, work)
    assert code == 0, payload
    assert payload["status"] == "created"
    assert payload["pending_tasks"][0]["kind"] == "compose"
    assert payload["pending_tasks"][0]["status"] == "awaiting_host"
    code, payload, _ = _iso_run(venv, ["continue", "--project", str(work / "proj")], home, work)
    assert code == 3, payload
    assert payload["next_action"] == "submit_host_results"


def test_isolated_resources_resolve_inside_package(tmp_path, wheel_venv):
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    script = (
        "import json; from importlib import resources\n"
        "root = resources.files('deck_master')\n"
        "paths = {name: str(root.joinpath(name)) for name in (\n"
        "    'resources/contracts/page.v2.schema.json',\n"
        "    'resources/static/index.html',\n"
        "    'resources/skill/SKILL.md',\n"
        "    'resources/skill/references/source-reading.md')}\n"
        "print(json.dumps(paths))")
    probe = subprocess.run([str(wheel_venv / "bin" / "python"), "-I", "-c", script],
                           capture_output=True, text=True, env=_isolated_env(wheel_venv, home), cwd=str(work))
    paths = _json.loads(probe.stdout)
    for name, path in paths.items():
        resolved = Path(path)
        assert resolved.is_file(), f"{name} missing at {path}"
        assert resolved.is_relative_to(wheel_venv), f"{name} resolved outside the venv: {path}"


# ---------------------------------------------------------------------------
# T20.02/03: full chain in the installed venv — compose/blueprint/reconstruct/
# produce/export review, then a single-page edit and re-assembly with the
# untouched page keeping its refs. Real soffice rendering; real storage.

from PIL import Image as _Image


def _adopt(venv, home, work, project, kind, envelope, staged=None):
    code, pending, _ = _iso_run(venv, ["continue", "--project", str(project)], home, work)
    assert code == 3 and pending["pending_tasks"][0]["kind"] == kind, (kind, pending)
    task = pending["pending_tasks"][0]
    if staged:
        staging = project / ".deckmaster" / "staging" / task["operation_id"]
        staging.mkdir(parents=True, exist_ok=True)
        for name, data in staged.items():
            (staging / name).write_bytes(data)
    envelope_path = work / f"envelope-{kind}.json"
    envelope_path.write_text(_json.dumps(envelope, ensure_ascii=False))
    code, payload, err = _iso_run(venv, ["task", "accept", "--project", str(project),
                                         "--task-id", task["task_id"], "--operation-id", task["operation_id"],
                                         "--produced-against", task["produced_against"],
                                         "--result", str(envelope_path)], home, work)
    assert code == 0, (payload, err)
    return payload


@pytest.mark.render
def test_isolated_full_chain_and_local_edit(wheel_venv, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    project = work / "chain-proj"
    family = _resolvable_font_family(wheel_venv, home, work)
    material = _write_material(work)

    code, payload, _ = _iso_run(wheel_venv, ["create", "--brief", "隔离全链", "--source", str(material),
                                             "--out", str(project)], home, work)
    assert code == 0, payload
    compose = _json.loads((ENVELOPES / "compose.json").read_text())
    for page in compose["pages"]:
        page.get("visual_spec", {}).pop("nodes", None)
        page.get("visual_spec", {}).pop("edges", None)
    _adopt(wheel_venv, home, work, project, "compose", compose)

    png = work / "reference.png"
    _Image.new("RGB", (64, 36), (245, 246, 250)).save(png)
    blueprint_envelope = {
        "kind": "blueprint",
        "files": [{"file_id": "b", "path": "reference.png", "media_type": "image/png"}],
        "artifact_specs": [{"file_id": "b", "role": "blueprint", "page_id": "p09",
                            "provenance": {"source_type": "unknown", "tool": "host-imagegen",
                                           "invocation_ref": None}}]}
    _adopt(wheel_venv, home, work, project, "blueprint", blueprint_envelope,
           staged={"reference.png": png.read_bytes()})

    blueprint_sha = None
    for obj in (project / ".deckmaster" / "objects").rglob("*.json"):
        try:
            obj_payload = _json.loads(obj.read_text())
        except _json.JSONDecodeError:
            continue
        if obj_payload.get("schema_version") == "deck_artifact.v1" and obj_payload.get("role") == "blueprint":
            blueprint_sha = obj_payload["file"]["sha256"]
    assert blueprint_sha

    def _svg_for_page(view_payload, sha):
        atoms = [atom for page in view_payload["pages"] for atom in page["visible_atoms"]
                 if isinstance(atom.get("text"), str) and atom["text"].strip()]
        height = max(150, len(atoms) * 8 + 24)
        lines = "".join(
            f'<text x="6" y="{16 + 8 * index}" font-family="{family}" font-size="6">{atom["text"]}</text>'
            for index, atom in enumerate(atoms))
        return (f'<svg viewBox="0 0 200 {height}" data-blueprint-sha256="{sha}">'
                f'<rect width="200" height="{height}" fill="#ffffff"/>{lines}</svg>').encode()

    code, view, _ = _iso_run(wheel_venv, ["next-step", "--project", str(project)], home, work)
    _adopt(wheel_venv, home, work, project, "reconstruct",
           {"kind": "reconstruct",
            "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
            "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p09",
                                "provenance": {"source_type": "unknown", "tool": "host-reconstruct",
                                               "invocation_ref": None}}]},
           staged={"page.svg": _svg_for_page(view, blueprint_sha)})

    code, report, err = _iso_run(wheel_venv, ["build", "--project", str(project)], home, work)
    assert code == 0, (report, err)
    assert report["status"] == "pass", report
    code, outcome, _ = _iso_run(wheel_venv, ["export", "--project", str(project),
                                             "--out", str(work / "review-out"), "--purpose", "review"], home, work)
    assert code == 0, outcome
    assert (work / "review-out" / "deck.pptx").is_file()

    # T20.03: single-page edit, host re-delivers SVG, re-assemble.
    code, view, _ = _iso_run(wheel_venv, ["next-step", "--project", str(project)], home, work)
    entry = view["pages"][0]
    page_payload = _json.loads(subprocess.run(
        [str(wheel_venv / "bin" / "python"), "-I", "-c",
         f"from deck_master.store import Store; import json; s=Store({str(project)!r}); "
         f"print(json.dumps(s.read_object_json(s.load_document()['pages'][0]['page']), ensure_ascii=False))"],
        capture_output=True, text=True, env=_isolated_env(wheel_venv, home), cwd=str(work)).stdout)
    page_payload["customer_visible"]["title"] = "将设备条件收集前移(隔离修订)"
    page_file = work / "page.json"
    page_file.write_text(_json.dumps(page_payload, ensure_ascii=False))
    code, edited, err = _iso_run(wheel_venv, ["edit", "--project", str(project), "--page", str(page_file),
                                              "--base-revision", view["revision_id"],
                                              "--page-hash", entry["slots"]["content"]["sha256"],
                                              "--operation-id", "iso-edit-1"], home, work)
    assert code == 0, (edited, err)
    code, view, _ = _iso_run(wheel_venv, ["next-step", "--project", str(project)], home, work)
    _adopt(wheel_venv, home, work, project, "reconstruct",
           {"kind": "reconstruct",
            "files": [{"file_id": "s", "path": "page.svg", "media_type": "image/svg+xml"}],
            "artifact_specs": [{"file_id": "s", "role": "svg", "page_id": "p09",
                                "provenance": {"source_type": "unknown", "tool": "host-reconstruct",
                                               "invocation_ref": None}}]},
           staged={"page.svg": _svg_for_page(view, blueprint_sha)})
    code, report, _ = _iso_run(wheel_venv, ["build", "--project", str(project)], home, work)
    assert code == 0 and report["status"] == "pass", report


def test_isolated_non_default_canvas_font_logo_and_relocation(sdist_venv, tmp_path):
    """T20.04: 4:3 canvas + real font + logo asset through the installed
    compiler; whole-project relocation keeps refs readable; a missing font
    is reported per doctor step without blocking old media."""
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    family = _resolvable_font_family(sdist_venv, home, work)
    logo = work / "logo.png"
    _Image.new("RGB", (12, 12), (20, 60, 180)).save(logo)
    design = {"canvas": {"width_px": 960, "height_px": 720, "slide_width_in": 10.0,
                         "slide_height_in": 7.5, "fit": "contain"},
              "assets": [{"asset_id": "brand-logo", "kind": "logo", "file": str(logo),
                          "external_use": "allowed"}],
              "allowed_asset_ids": ["brand-logo"]}
    design_file = work / "design.json"
    design_file.write_text(_json.dumps(design, ensure_ascii=False))
    project = work / "canvas-proj"
    code, payload, _ = _iso_run(sdist_venv, ["create", "--brief", "画布验收", "--source", str(_write_material(work)),
                                             "--out", str(project), "--design", str(design_file)], home, work)
    assert code == 0, payload
    compose = _json.loads((ENVELOPES / "compose.json").read_text())
    _adopt(sdist_venv, home, work, project, "compose", compose)

    moved = tmp_path / "relocated" / "canvas-proj"
    moved.parent.mkdir()
    _shutil.move(str(project), str(moved))
    code, view, _ = _iso_run(sdist_venv, ["next-step", "--project", str(moved)], home, work)
    assert code == 0 and view["page_count"] == 1, view
    probe = subprocess.run(
        [str(sdist_venv / "bin" / "python"), "-I", "-c",
         f"from deck_master.store import Store; s=Store({str(moved)!r}); d=s.load_document(); "
         f"s.read_object_bytes(d['pages'][0]['page']); print(d['design_context']['canvas']['slide_width_in'])"],
        capture_output=True, text=True, env=_isolated_env(sdist_venv, home), cwd=str(work))
    assert probe.stdout.strip() == "10.0"

    code, payload, _ = _iso_run(sdist_venv, ["doctor", "--step", "compile", "--font", "No Such Font XYZ"],
                                home, work)
    font_check = next((c for c in payload.get("checks", []) if c["name"].startswith("font:")), None)
    assert font_check and font_check["status"] == "unavailable", payload
    code, view, _ = _iso_run(sdist_venv, ["next-step", "--project", str(moved)], home, work)
    assert code == 0, "missing font must not block reading existing media"


def test_isolated_call_budget_and_cancel_via_cli(wheel_venv, tmp_path):
    """T20.05: allocation/begin/settle through the installed CLI entry."""
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    project = work / "budget-proj"
    code, payload, _ = _iso_run(wheel_venv, ["create", "--brief", "额度验收", "--source", str(_write_material(work)),
                                             "--out", str(project)], home, work)
    assert code == 0, payload
    compose_envelope = work / "compose-env.json"
    compose_envelope.write_text((ENVELOPES / "compose.json").read_text())
    code, created_task, _ = _iso_run(wheel_venv, ["continue", "--project", str(project)], home, work)
    code, _, err = _iso_run(wheel_venv, ["task", "accept", "--project", str(project),
                                         "--task-id", created_task["pending_tasks"][0]["task_id"],
                                         "--operation-id", created_task["pending_tasks"][0]["operation_id"],
                                         "--produced-against", created_task["pending_tasks"][0]["produced_against"],
                                         "--result", str(compose_envelope)], home, work)
    assert code == 0, err
    code, pending, _ = _iso_run(wheel_venv, ["continue", "--project", str(project)], home, work)
    task = pending["pending_tasks"][0]
    assert task["kind"] == "blueprint"
    # Allowance repair happens on the next continue (dispatch and repair are separate passes).
    _iso_run(wheel_venv, ["continue", "--project", str(project)], home, work)
    code, _, _ = _iso_run(wheel_venv, ["task", "start", "--project", str(project),
                                       "--task-id", task["task_id"], "--execution-ref", "iso-exec-1"], home, work)
    assert code == 0
    code, begun, begin_err = _iso_run(wheel_venv, ["task", "call", "begin", "--project", str(project),
                                                   "--task-id", task["task_id"], "--allowance-id", "call-1",
                                                   "--execution-ref", "iso-exec-1"], home, work)
    assert code == 0 and begun["status"] == "started", (begun, begin_err[:300])
    code, refused, _ = _iso_run(wheel_venv, ["task", "call", "settle", "--project", str(project), "--task-id", task["task_id"],
                                             "--allowance-id", "call-1", "--outcome", "consumed"], home, work)
    assert code == 2, "consumed requires a real execution report"
    report = work / "tool-report.json"
    report.write_text(_json.dumps({"tool": "image-gen", "calls": 1}))
    code, settled, _ = _iso_run(wheel_venv, ["task", "call", "settle", "--project", str(project), "--task-id", task["task_id"],
                                             "--allowance-id", "call-1", "--outcome", "consumed",
                                             "--report", str(report), "--invocation-ref", "iso-inv-1"], home, work)
    assert code == 0 and settled["status"] == "settled", settled
    code, _, _ = _iso_run(wheel_venv, ["task", "cancel", "--project", str(project),
                                       "--task-id", task["task_id"], "--reason", "iso stop"], home, work)
    assert code == 0
    code, conflict, _ = _iso_run(wheel_venv, ["task", "call", "begin", "--project", str(project), "--task-id", task["task_id"],
                                              "--allowance-id", "call-1", "--execution-ref", "iso-exec-1"], home, work)
    assert code == 5, "cancelled task cannot reacquire calls"


# ---------------------------------------------------------------------------
# T16 close-out: the real candidate install path (build_release manifest →
# install_candidate → activate) plus the existing rollback coverage.


@pytest.mark.render
def test_candidate_install_activate_and_run_doctor(tmp_path, monkeypatch):
    from tools.build_release import build_release
    from deck_master import install as install_mod

    release_dir = tmp_path / "release"
    manifest = build_release(release_dir)
    prefix = tmp_path / "custom prefix with spaces"
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex-home'))
    install_mod.install_candidate(prefix, release_dir / "release.json")
    install_mod.activate(prefix, manifest["release_id"])
    # The default HOME CLI is a trap: the documented binding must use the
    # release reached through CODEX_HOME even outside the repository.
    fake_home = tmp_path / 'fake-home'
    decoy = fake_home / '.deck-master/bin/deck-master'
    decoy.parent.mkdir(parents=True)
    decoy.write_text('#!/bin/sh\nexit 97\n')
    decoy.chmod(0o755)
    monkeypatch.setenv('HOME', str(fake_home))
    skill_entry = tmp_path / 'codex-home/skills/deck-master/SKILL.md'
    skill_text = skill_entry.read_text()
    binding = skill_text.split('```python\n', 1)[1].split('```', 1)[0]
    namespace = {'skill_entry': str(skill_entry)}
    exec(binding, namespace)
    bound = subprocess.run([*namespace['deck_master_cli'], 'doctor', '--step', 'view'],
                           cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert bound.returncode == 0, bound.stderr
    assert _Path(_json.loads(bound.stdout)['module_path']).is_relative_to(skill_entry.resolve().parents[2])
    assert skill_entry.read_bytes() == (REPO / 'skills/deck-master/SKILL.md').read_bytes()
    current = _Path(prefix) / ".deck-master" / "current"
    probe = subprocess.run([str(current / "venv/bin/python"), "-I", "-m", "deck_master", "doctor", "--step", "view"],
                           capture_output=True, text=True, timeout=120)
    assert probe.returncode == 0, probe.stderr
    info = _json.loads(probe.stdout)
    assert info["status"] == "ready", info
    assert _Path(info["module_path"]).is_relative_to(_Path(prefix).resolve()), \
        "activated candidate must not borrow the source checkout"
    assert _Path(prefix, ".deck-master", "current").is_symlink()
    # T9: the candidate release tree carries the skill extracted from the wheel.
    assert _Path(prefix, ".deck-master", "releases", manifest["release_id"], "skill", "deck-master", "SKILL.md").is_file()


def test_warm_build_removes_retired_resources(tmp_path):
    """Execute c93's build hook, then the current hook with build/ retained."""
    import shutil
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    for name in ('src', 'skills', 'tools'):
        shutil.copytree(REPO / name, checkout / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
    for name in ('pyproject.toml', 'setup.py', 'MANIFEST.in', 'README.md',
                 'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(REPO / name, checkout / name)
    hook = checkout / 'tools/build_hook.py'
    current_hook = hook.read_bytes()
    hook.write_bytes((REPO / 'tests/rebuild/fixtures/packaging/legacy_build_hook.py').read_bytes())

    def build(name):
        output = tmp_path / name
        result = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
                                 '--no-build-isolation', '-w', str(output), str(checkout)],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr
        return next(output.glob('*.whl'))

    with zipfile.ZipFile(build('baseline')) as archive:
        assert any('resources/skills-references/' in n for n in archive.namelist())
    assert (checkout / 'build/lib/deck_master/resources/skills-references').is_dir()
    hook.write_bytes(current_hook)
    # The second hook must actually be reimported even on coarse timestamp filesystems.
    shutil.rmtree(checkout / 'tools/__pycache__', ignore_errors=True)
    with zipfile.ZipFile(build('updated')) as archive:
        assert not any('resources/skills-references/' in n for n in archive.namelist())
        for source in (REPO / 'skills/deck-master').rglob('*'):
            if source.is_file():
                relative = source.relative_to(REPO / 'skills/deck-master')
                assert archive.read(f'deck_master/resources/skill/{relative}') == source.read_bytes()


def test_skill_rejects_unmanaged_location(tmp_path):
    text = (REPO / 'skills/deck-master/SKILL.md').read_text()
    entry = tmp_path / 'unmanaged/SKILL.md'
    entry.parent.mkdir()
    entry.write_text(text)
    binding = text.split('```python\n', 1)[1].split('```', 1)[0]
    with pytest.raises(RuntimeError, match='managed release'):
        exec(binding, {'skill_entry': str(entry)})
