"""Build a clean committed candidate, or verify it using its isolated interpreter.

Examples are verification drivers, never an alternate runtime. The build mode
uses git archive; verify mode refuses source/editable imports. No HOME override,
Host registration, model calls, automatic activation or release publishing.
"""

from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(command, cwd, log):
    started = time.monotonic()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    log.write_text(result.stdout + "\n" + result.stderr)
    assert result.returncode == 0, f"{command}: exit {result.returncode}; see {log}"
    return {"command": command, "exit_code": result.returncode, "seconds": round(time.monotonic() - started, 3), "log": log.name}


def wheel_files(path):
    with zipfile.ZipFile(path) as archive:
        return {name: sha(archive.read(name)) for name in sorted(archive.namelist()) if not name.endswith("/")}


def build(args):
    source = args.source.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", args.ref], text=True).strip()
    archive = subprocess.check_output(["git", "-C", str(source), "archive", commit])
    unpacked = out / "source"
    unpacked.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(unpacked, filter="data")
    distributions = out / "dist"
    distributions.mkdir()
    command = [
        sys.executable,
        "-c",
        "from setuptools import build_meta; build_meta.build_sdist("
        + repr(str(distributions))
        + "); build_meta.build_wheel("
        + repr(str(distributions))
        + ")",
    ]
    timing = run(command, unpacked, out / "build.log")
    wheel = next(distributions.glob("*.whl"))
    sdist = next(distributions.glob("*.tar.gz"))
    rebuilt_source = out / "sdist-source"
    rebuilt_source.mkdir()
    with tarfile.open(sdist) as tar:
        tar.extractall(rebuilt_source, filter="data")
    rebuilt = out / "rebuilt-wheel"
    rebuilt.mkdir()
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(rebuilt),
            str(next(rebuilt_source.iterdir())),
        ],
        out,
        out / "sdist-rebuild.log",
    )
    files = wheel_files(wheel)
    other = wheel_files(next(rebuilt.glob("*.whl")))
    code_resources = {k: v for k, v in files.items() if k.startswith("deck_master/")}
    assert code_resources == {k: v for k, v in other.items() if k.startswith("deck_master/")}, "wheel/sdist runtime mismatch"
    expected = {
        str(p.relative_to(unpacked / "src")): sha(p.read_bytes())
        for p in (unpacked / "src/deck_master/resources").rglob("*")
        if p.is_file()
    }
    expected.update(
        {
            "deck_master/resources/skill/" + str(p.relative_to(unpacked / "skills/deck-master")): sha(p.read_bytes())
            for p in (unpacked / "skills/deck-master").rglob("*")
            if p.is_file()
        }
    )
    assert all(files.get(k) == v for k, v in expected.items()), "missing or changed packaged resource"
    static = [k for k in files if "/static/v2/" in k]
    assert len(static) >= 33
    assert any(k.endswith("/licenses/LICENSE") for k in files)
    assert not any(k.endswith((".woff", ".woff2", ".ttf", ".otf")) for k in files), "system fonts must not be copied"
    manifest = {
        "release_id": commit[:12] + "-" + sha(wheel.read_bytes())[:12],
        "source_sha": commit,
        "source_dirty": False,
        "wheel": wheel.name,
        "wheel_sha256": sha(wheel.read_bytes()),
        "sdist": sdist.name,
        "sdist_sha256": sha(sdist.read_bytes()),
        "files": files,
        "runtime_files": len(code_resources),
        "v2_assets": len(static),
        "sdist_runtime_equal": True,
        "font_policy": "system font stacks; no webfont files or CDN; system font licenses not redistributed",
        "build_timing": timing,
        "professional_evidence": "not_evaluated",
    }
    write(distributions / "release.json", manifest)
    drivers = out / "drivers"
    shutil.copytree(unpacked / "examples/workbench", drivers)
    proof_tests = drivers / "verification-tests"
    proof_tests.mkdir()
    for name in ("test_candidates.py", "page_visual_helpers.py", "test_generation_protocol.py"):
        shutil.copyfile(unpacked / "tests/rebuild" / name, proof_tests / name)
    ui_tests = drivers / "installed-ui-tests"
    shutil.copytree(unpacked / "tests/rebuild", ui_tests)
    bootstrap = (ui_tests / "conftest.py").read_text()
    source_bootstrap = 'SRC_DIR = Path(__file__).resolve().parents[2] / "src"\nif str(SRC_DIR) not in sys.path:\n    sys.path.insert(0, str(SRC_DIR))'
    assert source_bootstrap in bootstrap
    bootstrap = bootstrap.replace(source_bootstrap, 'import deck_master\nassert Path(deck_master.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), "installed package required"')
    (ui_tests / "conftest.py").write_text(bootstrap)
    (drivers / "installed-pytest.ini").write_text('[pytest]\nmarkers =\n    browser: required real browser\n    render: real renderer\n')
    print(json.dumps({"manifest": str(distributions / "release.json"), "source_sha": commit, "v2_assets": len(static)}))


def verify(args):
    import deck_master
    from deck_master.store import Store

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    module = Path(deck_master.__file__).resolve()
    prefix = Path(sys.prefix).resolve()
    assert module.is_relative_to(prefix) and "site-packages" in module.parts, "must run using a non-editable installed wheel"
    manifest = json.loads(args.manifest.read_text())
    package = module.parent
    for name, digest in manifest["files"].items():
        if name.startswith("deck_master/"):
            assert sha((package / name.removeprefix("deck_master/")).read_bytes()) == digest, name
    steps = []
    drivers = Path(__file__).resolve().parent
    steps.append(run([sys.executable, "-m", "pytest", "-c", str(drivers / "installed-pytest.ini"),
                      str(drivers / "installed-ui-tests"), "-m", "browser", "--require-browser", "-q"],
                     out, out / "installed-current-browser.log"))
    steps.append(
        run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                str(drivers / "verification-tests/test_candidates.py"),
                "-k",
                "explicit_assembly_uses_real_pipeline",
            ],
            out,
            out / "installed-assembly.log",
        )
    )
    for name in ("w02_content_plan", "w02_recovery", "w03_first_run", "w06_change_handoff", "w10_recovery", "w09_content_inputs"):
        steps.append(run([sys.executable, str(drivers / (name + ".py")), "--out", str(out / name)], out, out / (name + ".log")))
    for name in ("w03_browser", "w07_candidates_browser", "w09_browser", "w10_browser_recovery"):
        browser_flags = ["--chromium-executable", str(args.chromium_executable)] if args.chromium_executable else []
        steps.append(run([sys.executable, str(drivers / (name + ".py")), "--out", str(out / name), *browser_flags], out, out / (name + ".log")))
    steps.append(
        run(
            [
                sys.executable,
                str(drivers / "w12_offline_browser.py"),
                "--require-installed",
                "--font",
                args.font,
                *(["--chromium-executable", str(args.chromium_executable)] if args.chromium_executable else []),
                "--out",
                str(out / "offline"),
            ],
            out,
            out / "offline.log",
        )
    )
    # Public commands and errors are executed by the above scripts; verify help
    # against this exact interpreter as a separate command-surface check.
    for parts in [
        ("requests", "freeze"),
        ("changes", "plan"),
        ("changes", "commit"),
        ("candidates", "adopt"),
        ("stages", "assemble"),
        ("content", "plan"),
        ("inputs", "update"),
        ("history", "plan-restore"),
        ("history", "commit-restore"),
        ("export",),
        ("install", "rollback"),
    ]:
        steps.append(run([sys.executable, "-I", "-m", "deck_master", *parts, "--help"], out, out / ("help-" + "-".join(parts) + ".txt")))
    projects = []
    for pointer in out.rglob(".deckmaster/current.json"):
        store = Store(pointer.parent.parent)
        doc = store.load_document()
        projects.append(
            {
                "project": str(pointer.parent.parent.relative_to(out)),
                "revision": doc["revision_id"],
                "compatibility": doc.get("compatibility"),
            }
        )
    write(
        out / "checks.json",
        {
            "status": "verified",
            "source_sha": manifest["source_sha"],
            "wheel_sha256": manifest["wheel_sha256"],
            "module": str(module),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "steps": steps,
            "projects": projects,
            "synthetic": True,
            "model_calls": 0,
            "real_host": "pending user project",
            "user_understanding_seconds": None,
            "manual_ppt_pages": None,
            "host_wait_seconds": None,
        },
    )
    print(json.dumps({"status": "verified", "steps": len(steps), "report": str(out / "checks.json")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--source", type=Path, required=True)
    build_cmd.add_argument("--ref", default="HEAD")
    build_cmd.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--out", type=Path, required=True)
    check.add_argument("--font", default="Arial")
    check.add_argument("--chromium-executable", type=Path,
                       help="Explicit installed Chromium; its actual version is recorded by browser drivers.")
    args = parser.parse_args()
    build(args) if args.mode == "build" else verify(args)


if __name__ == "__main__":
    main()
