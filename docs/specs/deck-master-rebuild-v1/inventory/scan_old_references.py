"""Per-path reference scanner for the T24 old-file disposition (AC-L05).

For every path frozen in inventory/old-files.csv, count textual references
across consumer classes: new code (src/), rebuild tests, build/packaging
tools, CI workflows, root config, living docs, and the root skill. References
from the old tree itself and from the to-be-retired legacy test suite are
reported separately and do NOT block deletion (they retire together with the
tree). Output: inventory/reference-scan.md.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INVENTORY = REPO / "docs" / "specs" / "deck-master-rebuild-v1" / "inventory"

BLOCKING_SCOPES = {
    "src": "src/",
    "rebuild-tests": "tests/rebuild/",
    "tools": "tools/",
    "ci": ".github/",
    "root-config": None,  # filled below
    "skill": "skills/deck-master/",
    "docs": "docs/",
}
NON_BLOCKING_SCOPES = {
    "legacy-tests": "tests/",
    "old-tree": "scripts/",
}
# The migration guide and the scanner/boundary tests name old paths on purpose.
SELF_DOCUMENTING = ("docs/migration-to-rebuilt-core.md",
                    "docs/specs/deck-master-rebuild-v1/inventory/scan_old_references.py",
                    "tests/rebuild/test_package_boundary.py")
ROOT_CONFIG_FILES = ("pyproject.toml", "MANIFEST.in", "setup.py", "setup.cfg",
                     "README.md", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md")


def _git_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"], check=True,
                         stdout=subprocess.PIPE, text=True, timeout=120)
    return out.stdout.splitlines()


def _grep(path_fragment: str, files: list[str]) -> list[str]:
    if not files:
        return []
    result = subprocess.run(["grep", "-lF", "--", path_fragment, *files],
                            stdout=subprocess.PIPE, text=True, cwd=REPO, timeout=300)
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    files = _git_files()
    scope_files: dict[str, list[str]] = {}
    for name, prefix in BLOCKING_SCOPES.items():
        if prefix is None:
            scope_files[name] = [f for f in files if f in ROOT_CONFIG_FILES]
        elif prefix == "docs/":
            scope_files[name] = [f for f in files
                                 if f.startswith(prefix) and not f.startswith("docs/archive/")
                                 and not f.startswith("docs/specs/deck-master-rebuild-v1/")]
        else:
            scope_files[name] = [f for f in files
                                 if f.startswith(prefix) and "__pycache__" not in f
                                 and not f.endswith((".pyc", ".png", ".jpg", ".zip"))]
    # legacy-tests = tests/ minus rebuild; old-tree = scripts/
    scope_files["legacy-tests"] = []
    scope_files["old-tree"] = [f for f in files if f.startswith("scripts/")]
    scope_files["old-tree"] = [f for f in files if f.startswith("scripts/")]

    rows = list(csv.DictReader((INVENTORY / "old-files.csv").open(encoding="utf-8-sig", newline="")))
    lines = ["# Old-file reference scan (T24 / AC-L05)",
             "",
             "Run after the T24 retirement: the retired tree is gone, so this scan is the",
             "zero-residue evidence. Historical docs (docs/archive/, dated records) and the",
             "rebuild spec pack itself are history, not blocking surfaces.",
             "",
             "| path | blocking refs | non-blocking refs |",
             "| --- | --- | --- |"]
    total_blocking = 0
    for row in rows:
        path = row["path"]
        blocking = []
        for scope, scope_list in scope_files.items():
            if scope in NON_BLOCKING_SCOPES:
                continue
            hits = [hit for hit in _grep(path, scope_list) if hit not in SELF_DOCUMENTING]
            blocking.extend(f"{scope}:{hit}" for hit in hits)
        non_blocking = []
        for scope in NON_BLOCKING_SCOPES:
            hits = _grep(path, scope_files[scope])
            non_blocking.extend(f"{scope}:{hit}" for hit in hits)
        total_blocking += len(blocking)
        b = "; ".join(blocking) if blocking else "0"
        nb = f"{len(non_blocking)} ({'; '.join(non_blocking[:3])}{'…' if len(non_blocking) > 3 else ''})" if non_blocking else "0"
        lines.append(f"| {path} | {b} | {nb} |")
    lines += ["", f"Total blocking references: **{total_blocking}**", ""]
    (INVENTORY / "reference-scan.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"scanned {len(rows)} paths; blocking references: {total_blocking}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
