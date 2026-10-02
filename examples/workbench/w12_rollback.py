"""Exercise only an explicit temporary installation and synthetic project.

Both release IDs must already be candidate_ready. Host registration is disabled
on every switch. Stopping the project service removes its browser write surface;
this is not a global lock against someone invoking an independent CLI writer.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
from deck_master.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prefix", "project", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("previous", "candidate"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    prefix = args.prefix.resolve()
    project = args.project.resolve()
    assert prefix.is_relative_to(Path("/tmp").resolve()) and project.is_relative_to(Path("/tmp").resolve()), "temporary paths required"
    store = Store(project)
    before = store.read_current()
    doc = store.load_document()
    files = {
        str(p.relative_to(store.deck_root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in store.objects_dir.rglob("*") if p.is_file()
    }
    records = []

    def command(*flags, installed=False):
        command = [str(prefix / ".deck-master/bin/deck-master"), *flags] if installed else [sys.executable, "-I", "-m", "deck_master", *flags]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        value = json.loads(result.stdout)
        records.append({"command": command, "exit_code": result.returncode, "result": value})
        return value

    def switch(release):
        return command("install", "activate", "--prefix", str(prefix), "--release-id", release, "--no-host-registration")

    switch(args.previous)
    switch(args.candidate)
    registry = out / "registry.json"
    state = command("workbench", "--project", str(project), "--registry", str(registry), "--no-open")
    command("workbench", "--project", str(project), "--stop")
    try:
        urllib.request.urlopen(state["url"] + "api/health", timeout=2)
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        pass
    else:
        raise AssertionError("project server still accepts requests after stop")
    rolled = command("install", "rollback", "--prefix", str(prefix), "--no-host-registration")
    assert rolled["release_id"] == args.previous
    launcher = prefix / ".deck-master/bin/deck-master"
    probe = subprocess.run([str(launcher), "doctor", "--step", "compose"], capture_output=True, text=True, check=True)
    assert args.previous in str(Path(json.loads(probe.stdout)["module_path"]).resolve())
    old = command("workbench", "--project", str(project), "--registry", str(registry), "--no-open", installed=True)
    try:
        with urllib.request.urlopen(old["url"], timeout=5) as response:
            assert response.status == 200 and b"<html" in response.read().lower()
    finally:
        command("workbench", "--project", str(project), "--stop")
    switch(args.candidate)
    assert store.read_current() == before
    assert all(hashlib.sha256((store.deck_root / name).read_bytes()).hexdigest() == digest for name, digest in files.items())
    report = {
        "status": "verified",
        "records": records,
        "project_revision": doc["revision_id"],
        "compatibility": doc.get("compatibility"),
        "immutable_files_unchanged": len(files),
        "candidate_count": len(doc.get("candidates", [])),
        "host_registration": "disabled",
        "default_entry_changed": False,
        "global_cli_write_lock": False,
        "final_active_release": args.candidate,
    }
    (out / "checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "verified"}))


if __name__ == "__main__":
    main()
