"""AC-L07 package boundary tests (T01).

T01 freezes the per-path disposition/reference baseline; it does not require
reference-zeroing (that is T24 / AC-L05). These tests enforce:

1. The old-file disposition inventory is complete and well-formed.
2. No old file has been deleted prematurely (old code and user material stay).
3. The new ``src/deck_master`` package never imports the old namespaces
   (spec 01.2 reverse-import forbidden zone).
"""

from __future__ import annotations

import ast
import csv
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_DIR = REPO_ROOT / "docs" / "specs" / "deck-master-rebuild-v1" / "inventory"
NEW_PACKAGE = REPO_ROOT / "src" / "deck_master"

ALLOWED_ACTIONS = {"RETIRE_THEN_DELETE", "EXTRACT_THEN_DELETE", "DELETE_AFTER_CUTOVER", "REPLACE"}
EXPECTED_OLD_FILE_COUNT = 177

# spec 01.2: old namespaces the new package must never import. "build" appears
# in the spec only as build.native_* of the old runtime's build package.
FORBIDDEN_IMPORT_ROOTS = ("runtime", "workflow", "high_density", "preview", "build")


def _read_old_files() -> list[dict[str, str]]:
    with (INVENTORY_DIR / "old-files.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _git_tracked_paths() -> set[str]:
    output = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    return set(output.stdout.decode("utf-8").splitlines())


def test_disposition_inventory_is_complete() -> None:
    rows = _read_old_files()
    assert len(rows) == EXPECTED_OLD_FILE_COUNT, (
        f"old-files.csv must freeze all {EXPECTED_OLD_FILE_COUNT} script paths, got {len(rows)}"
    )
    for row in rows:
        path = row["path"].strip()
        assert path, f"row {row.get('id')} has an empty path"
        assert row["action"].strip() in ALLOWED_ACTIONS, (
            f"{path}: unknown disposition {row['action']!r}"
        )
        if row["action"].strip() == "EXTRACT_THEN_DELETE":
            assert row["target"].strip(), (
                f"{path}: EXTRACT_THEN_DELETE must name the new target module"
            )


def test_no_premature_old_file_deletion() -> None:
    tracked = _git_tracked_paths()
    missing = [row["path"] for row in _read_old_files() if row["path"].strip() not in tracked]
    assert not missing, f"T01 must not delete old files; missing from git: {missing[:10]}"


def test_new_package_has_no_forbidden_imports() -> None:
    if not NEW_PACKAGE.is_dir():
        return  # T01 runs before the package exists; later tasks keep this green.
    offenders: list[str] = []
    for path in sorted(NEW_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    offenders.append(f"{path.name}: import {name}")
    assert not offenders, f"new package imports old namespace (spec 01.2): {offenders[:10]}"
