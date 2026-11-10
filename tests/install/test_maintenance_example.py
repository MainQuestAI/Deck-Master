"""Execute the documented single-installation cleanup against synthetic groups."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["obsolete", "current", "outside", "symlink", "busy", "missing-tool", "inspection-error"])
def test_manual_cleanup_preserves_current_and_running_installations(tmp_path: Path, case: str) -> None:
    documentation = (Path(__file__).resolve().parents[2] / "docs/getting-started.md").read_text()
    section = documentation.split("## Remove one confirmed historical installation", 1)[1]
    code = section.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    prefix = tmp_path / "prefix"
    root = prefix / "share/deck/installations"
    old = root / "obsolete"
    old.mkdir(parents=True)
    (old / "author-marker").write_text("old installation")
    current = root / "active"
    current.mkdir()
    (prefix / "share/deck/current").symlink_to(current)
    outside = tmp_path / "author-files"
    outside.mkdir()
    (outside / "keep.txt").write_text("author content")
    (old / "current-link").symlink_to(current)
    (old / "author-link").symlink_to(outside)
    env = os.environ.copy()
    name = old.name
    if case == "current":
        name = current.name
    elif case == "outside":
        name = "../../../../author-files"
    elif case == "symlink":
        name = "linked"
        (root / name).symlink_to(outside)
    elif case in ("missing-tool", "inspection-error"):
        tools = tmp_path / "tools"
        tools.mkdir()
        env["PATH"] = str(tools)
        if case == "inspection-error":
            lsof = tools / "lsof"
            lsof.write_text("#!/bin/sh\necho 'inspection failed' >&2\nexit 1\n")
            lsof.chmod(0o755)
    if case in ("obsolete", "busy"):
        assert shutil.which("lsof"), "Install lsof to verify the documented cleanup"
    process = None
    try:
        if case == "busy":
            executable = old / "deck"
            shutil.copy2(shutil.which("cat"), executable)
            process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            process.stdin.write(b"ready\n")
            process.stdin.flush()
            assert process.stdout.readline() == b"ready\n"
        result = subprocess.run([sys.executable, "-c", code, str(prefix), name], env=env,
                                text=True, capture_output=True, check=False)
        assert (result.returncode == 0) == (case == "obsolete"), result.stderr
        assert old.exists() == (case != "obsolete")
        assert current.is_dir()
        assert (prefix / "share/deck/current").resolve() == current
        assert (outside / "keep.txt").read_text() == "author content"
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
