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


def test_old_file_disposition_executed() -> None:
    """T24: every frozen old path is now either deleted from the working tree
    (disposition executed, history kept in git) or still present with a
    recorded reason. The T01 "no premature deletion" rule is superseded by
    the T24 cutover (WP04 entry switched, AC-L05)."""
    tracked = _git_tracked_paths()
    rows = _read_old_files()
    still_present = [row["path"] for row in rows if row["path"].strip() in tracked]
    deleted = [row["path"] for row in rows if row["path"].strip() not in tracked]
    # The old implementation tree is retired; surviving paths must be ones
    # the disposition table explicitly keeps (none today under scripts/).
    assert not still_present, (
        f"T24 must retire every frozen old path or record a keep reason; still present: {still_present[:10]}"
    )
    assert deleted, "T24 disposition must actually delete the retired tree"
    evidence = INVENTORY_DIR / "reference-scan.md"
    assert evidence.is_file(), "per-path reference scan evidence must be committed"


def test_retired_tree_has_zero_living_references() -> None:
    """AC-L05: no living surface (new code, rebuild tests, build tools, living
    skill, CI, root config) still references the retired scripts tree."""
    living_roots = ["src/", "tests/rebuild/", "tools/", "skills/deck-master/",
                    ".github/workflows/rebuild.yml", "pyproject.toml", "MANIFEST.in"]
    for root in living_roots:
        target = REPO_ROOT / root
        files = [target] if target.is_file() else sorted(target.rglob("*"))
        offenders = []
        for path in files:
            if path.resolve() == Path(__file__).resolve():
                continue  # this scanner's own needles are not references
            if path.is_file() and path.suffix in {".py", ".md", ".toml", ".yml", ".yaml", ".in", ".txt"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for needle in ("scripts/deck_master.py", "scripts/runtime", "scripts/workflow",
                               "scripts/high_density", "import runtime", "import workflow",
                               "from runtime", "from workflow", "from high_density"):
                    if needle in text:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {needle!r}")
        assert not offenders, f"living references to the retired tree: {offenders[:10]}"


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
